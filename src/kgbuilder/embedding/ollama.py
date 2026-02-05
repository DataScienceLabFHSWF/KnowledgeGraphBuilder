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
        """Generate unstructured text output and count tokens."""
        # Simple token count: whitespace split
        prompt_tokens = len(prompt.split())
        """Generate unstructured text output.

        Args:
            prompt: Input prompt
            **kwargs: Optional generation parameters (temperature, top_p, etc.)

        Returns:
            Generated text

        Raises:
            RuntimeError: If API call fails
        """
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
        **kwargs: Any,
    ) -> Any:
        """Generate structured JSON output matching Pydantic schema.

        Strategy:
        1. Add JSON schema instruction to prompt
        2. Call generate() to get text output
        3. Parse and validate against schema
        4. Return validated model instance

        Args:
            prompt: Input prompt
            schema: Pydantic BaseModel class for validation
            **kwargs: Optional generation parameters

        Returns:
            Instance of schema class

        Raises:
            ValidationError: If output doesn't match schema
            RuntimeError: If generation fails
        """
        # Append schema instructions to prompt
        schema_json = schema.model_json_schema()
        schema_instruction = (
            f"\n\nRespond with ONLY valid JSON matching this schema:\n"
            f"{json.dumps(schema_json, indent=2)}\n\n"
            f"JSON response (no markdown, no extra text):"
        )
        augmented_prompt = prompt + schema_instruction

        # Generate with higher temperature for creativity, lower for structured output
        temperature = kwargs.get("temperature", max(0.3, self.temperature - 0.2))

        try:
            raw_output = self.generate(
                augmented_prompt,
                temperature=temperature,
                **kwargs,
            )

            # Extract JSON from response (handle markdown code blocks)
            json_str = raw_output.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

            # Fix unescaped backslashes in JSON (LLM sometimes generates these)
            # Replace single backslashes not followed by another backslash or quote
            import re
            json_str = re.sub(r'\\(?!\\|")', r'\\\\', json_str)

            # Parse and validate
            data = json.loads(json_str)
            result = schema.model_validate(data)

            logger.debug(f"✓ Structured output validated: {type(result).__name__}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {raw_output}")
            raise RuntimeError(f"JSON parsing failed: {e}") from e
        except ValidationError as e:
            logger.error(f"Schema validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Structured generation failed: {e}")
            raise RuntimeError(f"Structured generation error: {e}") from e

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

