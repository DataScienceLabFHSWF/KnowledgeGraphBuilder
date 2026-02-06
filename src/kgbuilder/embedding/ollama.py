"""Ollama LLM provider implementation for QWEN and other local models.

Provides LLM capabilities through Ollama API for structured extraction.
Supports:
- Text generation (unstructured)
- Structured JSON output with Pydantic validation
- Multiple model support (QWEN3, qwen3-next, etc.)
- Embedding generation via embedding models
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import requests
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class OllamaProvider:
    # Class-level token usage counters
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    """Ollama-based LLM provider for local model inference.

    Supports QWEN3, qwen3-next, and other Ollama-available models.
    Provides both unstructured and structured (JSON) output generation.
    """

    def __init__(
        self,
        model: str = "qwen3",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: int = 300,
    ) -> None:
        """Initialize Ollama provider.

        Args:
            model: Model name (e.g., 'qwen3', 'qwen3-next', 'llama2')
            base_url: Ollama API base URL
            temperature: Sampling temperature (0-2)
            top_p: Top-p nucleus sampling
            timeout: Request timeout in seconds (300s for docker Ollama performance)

        Raises:
            ConnectionError: If Ollama service is not running
        """
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.top_p = top_p
        self.timeout = timeout

        # Verify connection
        self._verify_connection()

    def _verify_connection(self) -> None:
        """Verify Ollama service is running and model is available.

        Raises:
            ConnectionError: If service unreachable
            ValueError: If model not available
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]

            if not model_names:
                logger.warning("No models found in Ollama")
            elif not any(self.model in name for name in model_names):
                logger.warning(
                    f"Model {self.model} not found in Ollama. Available: {model_names}"
                )
            logger.info(f"✓ Connected to Ollama ({len(model_names)} models)")
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Is Ollama running? Error: {e}"
            ) from e
        except Exception as e:
            raise ConnectionError(f"Ollama verification failed: {e}") from e

    @property
    def model_name(self) -> str:
        """Get model identifier."""
        return self.model

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate unstructured text output.

        Args:
            prompt: Input prompt
            **kwargs: Optional generation parameters (temperature, top_p, etc.)

        Returns:
            Generated text

        Raises:
            RuntimeError: If API call fails
        """
        # Simple token count: whitespace split
        prompt_tokens = len(prompt.split())
        params = {
            "model": self.model,
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
            "stream": False,
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            completion = result.get("response", "")
            completion_tokens = len(completion.split())
            # Accumulate totals
            OllamaProvider.total_prompt_tokens += prompt_tokens
            OllamaProvider.total_completion_tokens += completion_tokens
            logger.debug(f"OllamaProvider: prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, total_prompt={OllamaProvider.total_prompt_tokens}, total_completion={OllamaProvider.total_completion_tokens}")
            return completion
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise RuntimeError(f"LLM generation error: {e}") from e
    @classmethod
    def log_total_token_usage(cls) -> None:
        """Log total token usage for all OllamaProvider calls."""
        logger.info(
            f"Total Ollama token usage: prompts={cls.total_prompt_tokens}, completions={cls.total_completion_tokens}, total={cls.total_prompt_tokens + cls.total_completion_tokens}"
        )

    def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        max_retries: int = 3,
        **kwargs: Any,
    ) -> Any:
        """Generate structured JSON output matching Pydantic schema.

        Uses strict pydantic validation with retry logic for robustness.
        
        Strategy:
        1. Add JSON schema instruction to prompt
        2. Call generate() to get text output
        3. Parse with JSON recovery strategies
        4. Validate with pydantic (strict mode)
        5. Retry on validation failure with schema hints

        Args:
            prompt: Input prompt
            schema: Pydantic BaseModel class for validation
            max_retries: Maximum retry attempts on validation failure
            **kwargs: Optional generation parameters

        Returns:
            Instance of schema class

        Raises:
            ValidationError: If output doesn't match schema after retries
            RuntimeError: If generation fails
        """
        import re
        
        # Append schema instructions to prompt
        schema_json = schema.model_json_schema()
        schema_instruction = (
            f"\n\nRespond with ONLY valid JSON matching this schema:\n"
            f"{json.dumps(schema_json, indent=2)}\n\n"
            f"Critical: JSON must be valid. Return raw JSON only, no markdown."
        )
        
        temperature = kwargs.get("temperature", max(0.3, self.temperature - 0.2))
        retry_count = 0
        last_error: Exception | None = None
        
        while retry_count < max_retries:
            try:
                augmented_prompt = prompt + schema_instruction
                if retry_count > 0:
                    # Add retry hint
                    augmented_prompt += f"\n\nAttempt {retry_count + 1}/{max_retries}. "
                    augmented_prompt += "Ensure ALL required fields are present and valid."
                
                raw_output = self.generate(
                    augmented_prompt,
                    temperature=temperature,
                    **kwargs,
                )

                # Extract JSON from response (handle markdown code blocks)
                json_str = self._extract_json_from_response(raw_output)
                
                # Fix common JSON issues
                json_str = self._fix_json_string(json_str)
                
                # Parse with pydantic's model_validate_json for better error messages
                try:
                    result = schema.model_validate_json(json_str)
                    logger.debug(f"✓ Structured output validated: {type(result).__name__}")
                    return result
                except json.JSONDecodeError:
                    # Attempt JSON recovery strategies
                    logger.debug(f"JSON parse error, attempting recovery...")
                    recovered_json = self._attempt_json_recovery(json_str)
                    if recovered_json:
                        result = schema.model_validate_json(recovered_json)
                        logger.info("✓ JSON recovery successful")
                        return result
                    raise

            except ValidationError as e:
                last_error = e
                retry_count += 1
                
                if retry_count < max_retries:
                    # Extract validation errors for next prompt
                    error_details = self._extract_validation_errors(e)
                    schema_instruction += f"\n\nValidation failed: {error_details}"
                    logger.warning(f"Validation failed (attempt {retry_count}/{max_retries}): {error_details}")
                    continue
                else:
                    logger.error(f"Schema validation failed after {max_retries} retries: {e}")
                    raise
                    
            except json.JSONDecodeError as e:
                last_error = e
                retry_count += 1
                
                if retry_count < max_retries:
                    logger.warning(f"JSON parse failed (attempt {retry_count}/{max_retries}): {e}")
                    continue
                else:
                    logger.error(f"JSON parsing failed after {max_retries} retries: {e}")
                    raise RuntimeError(f"JSON parsing failed: {e}") from e
                    
            except Exception as e:
                last_error = e
                logger.error(f"Structured generation failed: {e}")
                raise RuntimeError(f"Structured generation error: {e}") from e
        
        # Should not reach here, but as safety net
        if last_error:
            raise RuntimeError(f"Structured generation failed after {max_retries} retries") from last_error
        raise RuntimeError("Structured generation failed: unknown error")

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from response, handling markdown and extra text."""
        json_str = response.strip()
        
        # Remove markdown code blocks
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        
        json_str = json_str.strip()
        
        # Find first { and last }
        start_idx = json_str.find("{")
        end_idx = json_str.rfind("}")
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = json_str[start_idx:end_idx+1]
        
        return json_str
    
    def _fix_json_string(self, json_str: str) -> str:
        """Apply common JSON fixes before parsing."""
        import re
        
        # Fix unescaped backslashes (LLM sometimes generates these)
        json_str = re.sub(r'\\(?!\\|")', r'\\\\', json_str)
        
        # Fix single quotes to double quotes (but preserve apostrophes in text)
        # Only replace quotes that bound field names/values, not inside strings
        
        return json_str
    
    def _extract_validation_errors(self, error: ValidationError) -> str:
        """Extract human-readable validation errors."""
        errors = error.errors()
        if not errors:
            return str(error)
        
        error_msgs = []
        for err in errors[:3]:  # First 3 errors
            field = ".".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "")
            error_msgs.append(f"{field}: {msg}")
        
        return "; ".join(error_msgs)

    def _attempt_json_recovery(self, json_str: str) -> str | None:
        """Attempt to recover malformed JSON.
        
        Strategies:
        1. Find balanced braces and trim incomplete parts
        2. Add missing closing brackets
        3. Fix common JSON issues (trailing commas, etc.)
        
        Args:
            json_str: Potentially malformed JSON string
            
        Returns:
            Recovered JSON string or None if recovery failed
        """
        if not json_str.strip():
            return None
        
        # Strategy 1: Find balanced braces
        open_braces = json_str.count("{")
        close_braces = json_str.count("}")
        
        if close_braces < open_braces:
            # Add missing closing braces
            missing = open_braces - close_braces
            recovered = json_str + "}" * missing
            try:
                json.loads(recovered)
                logger.debug(f"Recovery: added {missing} closing braces")
                return recovered
            except json.JSONDecodeError:
                pass
        
        # Strategy 2: Find last balanced position
        depth = 0
        last_valid_pos = 0
        for i, char in enumerate(json_str):
            if char == "{":
                depth += 1
                last_valid_pos = i
            elif char == "}":
                depth -= 1
                last_valid_pos = i
        
        # Try truncating to last valid position
        if last_valid_pos > 0 and depth > 0:
            recovered = json_str[:last_valid_pos + 1] + "}" * abs(depth)
            try:
                json.loads(recovered)
                logger.debug(f"Recovery: truncated to position {last_valid_pos}")
                return recovered
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Remove trailing incomplete fields
        # Look for pattern: "key": " without closing
        import re
        recovered = re.sub(r',\s*"[^"]*":\s*$', '}', json_str)
        if recovered != json_str:
            try:
                json.loads(recovered)
                logger.debug("Recovery: removed incomplete trailing field")
                return recovered
            except json.JSONDecodeError:
                pass
        
        return None

    def embed_query(self, query: str, embedding_model: str = "qwen3-embedding") -> Any:
        """Generate embedding for a query using Ollama embedding model.

        Args:
            query: Text to embed
            embedding_model: Embedding model name (default: qwen3-embedding)

        Returns:
            Numpy array of embeddings

        Raises:
            RuntimeError: If embedding API call fails
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": embedding_model,
                    "input": query,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            embeddings = result.get("embeddings", [])
            
            if not embeddings or not embeddings[0]:
                raise RuntimeError("No embeddings returned from Ollama")
            
            # Return first embedding (embeddings is list of lists)
            return np.array(embeddings[0], dtype=np.float32)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise RuntimeError(f"Embedding error: {e}") from e

