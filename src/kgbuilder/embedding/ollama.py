"""Ollama LLM provider implementation for QWEN and other local models.

Provides LLM capabilities through Ollama API for structured extraction.
Supports:
- Text generation (unstructured)
- Structured JSON output with Pydantic validation
- Multiple model support (QWEN3, qwen3-next, etc.)
- Embedding generation via embedding models
- Resilient retry with exponential backoff + jitter
- Connection pooling and circuit breaker
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import requests
import structlog
from pydantic import BaseModel, ValidationError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = structlog.get_logger(__name__)


class OllamaProvider:
    # Class-level token usage counters
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    """Ollama-based LLM provider for local model inference.

    Supports QWEN3, qwen3-next, and other Ollama-available models.
    Provides both unstructured and structured (JSON) output generation.
    """

    _DEFAULT_BASE_URL = "http://localhost:18134"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        timeout: int = 600,
    ) -> None:
        """Initialize Ollama provider with resilient connection pooling and retry logic.

        Args:
            model: Model name (default: OLLAMA_LLM_MODEL or qwen3:8b)
            base_url: Ollama API base URL
            temperature: Sampling temperature (0-2)
            top_p: Top-p nucleus sampling
            timeout: Request timeout in seconds (600s default for Docker Ollama)

        Raises:
            ConnectionError: If Ollama service is not running
        """
        self.model = model or os.environ.get("OLLAMA_LLM_MODEL", os.environ.get("OLLAMA_MODEL", "qwen3:8b"))
        self.base_url = base_url or os.environ.get("OLLAMA_URL", self._DEFAULT_BASE_URL)
        self.temperature = temperature
        self.top_p = top_p
        self.timeout = timeout
        
        # Circuit breaker state for fault tolerance
        self.consecutive_timeouts = 0
        self.circuit_breaker_threshold = 5  # Open circuit after 5 consecutive timeouts
        self.circuit_breaker_open = False
        self.last_circuit_reset = time.time()
        self.circuit_reset_interval = 60  # Reset circuit every 60s

        # Test connection and log detected models
        self._check_connection()

        # Cached model metadata (lazy-loaded from Ollama API)
        self._dimension: int | None = None
        
        # PERSISTENT CACHE (New Optimization)
        self.cache_dir = Path(".cache/ollama")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_hits = 0
        self._cache_misses = 0

    def _get_cache_key(self, prompt: str, **kwargs: Any) -> str:
        """Generate unique key for prompt and params."""
        params_str = json.dumps(kwargs, sort_keys=True)
        content = f"{self.model}:{prompt}:{params_str}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _load_cache(self, key: str) -> str | None:
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    self._cache_hits += 1
                    return data["response"]
            except Exception:
                return None
        return None

    def _save_cache(self, key: str, response: str) -> None:
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, "w") as f:
                json.dump({"response": response, "timestamp": time.time()}, f)
            self._cache_misses += 1
        except Exception:
            pass

    def _check_connection(self) -> None:
        """Verify connection to Ollama and log available models."""
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
                logger.info(
                    "ollama_connection_verified",
                    base_url=self.base_url,
                    available_models=models,
                    configured_model=self.model
                )
                if self.model not in models and ":" not in self.model:
                    # Try to find a match if version tag is missing
                    matches = [m for m in models if m.startswith(f"{self.model}:")]
                    if matches:
                        old_model = self.model
                        self.model = matches[0]
                        logger.warning(
                            "model_version_resolved",
                            requested=old_model,
                            resolved=self.model,
                            hint="Explicitly set version tag in config to avoid this warning"
                        )
            else:
                logger.warning(
                    "ollama_connection_status_error",
                    status=response.status_code,
                    base_url=self.base_url
                )
        except Exception as e:
            logger.error(
                "ollama_connection_failed",
                error=str(e),
                base_url=self.base_url,
                hint="Check if Ollama is running and accessible"
            )
        self._max_tokens: int | None = None

        # Connection pooling with retry configuration
        self.session = self._create_session()

        # Verify connection
        self._verify_connection()

    def _create_session(self) -> requests.Session:
        """Create requests Session with connection pooling and retry strategy.
        
        Returns:
            Configured requests.Session with resilience
        """
        session = requests.Session()
        
        # Retry strategy: exponential backoff for transient failures
        retry_strategy = Retry(
            total=3,  # Total number of retries
            backoff_factor=0.5,  # Exponential backoff: 0.5s, 1s, 2s
            status_forcelist=[408, 502, 503, 504],  # Retry on these HTTP codes
            allowed_methods=["GET", "POST"],  # Allow retries on these methods
        )
        
        # Mount adapters for HTTP and HTTPS
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def _check_circuit_breaker(self) -> None:
        """Check and potentially reset circuit breaker.
        
        Raises:
            RuntimeError: If circuit breaker is open (too many recent timeouts)
        """
        # Attempt to reset circuit breaker after interval
        if self.circuit_breaker_open:
            if time.time() - self.last_circuit_reset > self.circuit_reset_interval:
                logger.info("Circuit breaker reset interval reached, attempting recovery")
                self.circuit_breaker_open = False
                self.consecutive_timeouts = 0
                self.last_circuit_reset = time.time()
            else:
                raise RuntimeError(
                    f"Circuit breaker OPEN: Too many timeouts ({self.consecutive_timeouts}). "
                    f"Ollama service may be unavailable. Will retry in {self.circuit_reset_interval}s."
                )

    def _record_timeout(self) -> None:
        """Record timeout and potentially open circuit breaker."""
        self.consecutive_timeouts += 1
        if self.consecutive_timeouts >= self.circuit_breaker_threshold:
            self.circuit_breaker_open = True
            self.last_circuit_reset = time.time()
            logger.error(
                f"Circuit breaker OPENED: {self.consecutive_timeouts} consecutive timeouts"
            )

    def _record_success(self) -> None:
        """Record successful call and reset timeout counter."""
        self.consecutive_timeouts = 0
        if self.circuit_breaker_open:
            logger.info("Circuit breaker recovered, resuming normal operation")
            self.circuit_breaker_open = False

    def _verify_connection(self) -> None:
        """Verify Ollama service is running and model is available.

        Raises:
            ConnectionError: If service unreachable
            ValueError: If model not available
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]

            if not model_names:
                logger.warning("No models found in Ollama", base_url=self.base_url)
            else:
                logger.info(
                    "ollama_connection_verified",
                    base_url=self.base_url,
                    model_count=len(model_names),
                    available_models=model_names
                )

            if model_names and not any(self.model in name for name in model_names):
                logger.warning(
                    f"Target model {self.model} not found in available models",
                    target_model=self.model,
                    available_models=model_names
                )
            
            self._record_success()
        except requests.exceptions.Timeout:
            raise ConnectionError(
                f"Ollama connection timeout at {self.base_url}. "
                f"Service may be slow or unavailable. Try increasing timeout."
            )
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
        """Generate unstructured text output with exponential backoff retry.

        Args:
            prompt: Input prompt
            **kwargs: Optional generation parameters (temperature, top_p, etc.)

        Returns:
            Generated text

        Raises:
            RuntimeError: If API call fails after retries or circuit breaker is open
        """
        # Check cache first
        cache_key = self._get_cache_key(prompt, **kwargs)
        cached = self._load_cache(cache_key)
        if cached:
            logger.debug("ollama_cache_hit", model=self.model, key=cache_key[:8])
            return cached

        # Check circuit breaker before attempting
        self._check_circuit_breaker()
        
        # Simple token count: whitespace split
        prompt_tokens = len(prompt.split())
        params = {
            "model": self.model,
            "prompt": prompt,
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
            "stream": False,
            "format": kwargs.get("format", None),  # Support native JSON format if specified
        }

        max_retries = 3
        base_delay = 1.0  # Start with 1 second
        
        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    f"{self.base_url}/api/generate",
                    json=params,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                result = response.json()
                completion = result.get("response", "")
                completion_tokens = len(completion.split())
                
                # Save to cache
                self._save_cache(cache_key, completion)

                # Accumulate totals
                OllamaProvider.total_prompt_tokens += prompt_tokens
                OllamaProvider.total_completion_tokens += completion_tokens
                logger.debug(
                    f"OllamaProvider: prompt_tokens={prompt_tokens}, "
                    f"completion_tokens={completion_tokens}, "
                    f"total_prompt={OllamaProvider.total_prompt_tokens}, "
                    f"total_completion={OllamaProvider.total_completion_tokens}"
                )
                
                # Record success and reset consecutive timeout counter
                self._record_success()
                return completion
                
            except requests.exceptions.Timeout as e:
                self._record_timeout()
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Ollama timeout (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {delay:.2f}s... (consecutive timeouts: {self.consecutive_timeouts})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Generation failed: Timeout after {max_retries} attempts. "
                        f"Ollama may be overloaded or unresponsive."
                    )
                    raise RuntimeError(f"LLM generation timeout after {max_retries} retries: {e}") from e
                    
            except requests.exceptions.ConnectionError as e:
                self._record_timeout()
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Connection error (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Generation failed: Connection error after {max_retries} attempts")
                    raise RuntimeError(f"LLM connection failed: {e}") from e
                    
            except Exception as e:
                logger.error(f"Generation failed: {type(e).__name__}: {e}")
                raise RuntimeError(f"LLM generation error: {e}") from e
        
        # Shouldn't reach here due to exceptions, but just in case
        raise RuntimeError("Generation failed: Unknown error after all retries")
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

    def embed_text(self, text: str) -> Any:
        """Generate embedding for text (EmbeddingProvider protocol).

        Delegates to embed_query with the default embedding model.

        Args:
            text: Text to embed

        Returns:
            Numpy array of embeddings
        """
        return self.embed_query(text)

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> Any:
        """Generate embeddings for multiple texts (EmbeddingProvider protocol).

        Args:
            texts: List of texts to embed
            batch_size: Batch size (currently processes sequentially)

        Returns:
            List of numpy arrays
        """
        return [self.embed_text(t) for t in texts]

    def _fetch_model_info(self, model_name: str | None = None) -> dict[str, Any]:
        """Fetch model metadata from Ollama /api/show endpoint.

        Args:
            model_name: Model to query (defaults to self.model)

        Returns:
            Model info dict from Ollama API
        """
        name = model_name or self.model
        try:
            response = self.session.post(
                f"{self.base_url}/api/show",
                json={"name": name},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch model info for {name}: {e}")
            return {}

    @property
    def dimension(self) -> int:
        """Embedding vector dimension, queried from Ollama model metadata."""
        if self._dimension is None:
            info = self._fetch_model_info()
            model_info = info.get("model_info", {})
            # Ollama exposes embedding_length in model_info
            for key, value in model_info.items():
                if "embedding_length" in key and isinstance(value, int):
                    self._dimension = value
                    break
            if self._dimension is None:
                # Fallback: generate a single embedding and measure
                try:
                    test_emb = self.embed_text("test")
                    self._dimension = len(test_emb)
                except Exception:
                    logger.warning("Could not determine embedding dimension, using 0")
                    self._dimension = 0
            logger.debug(f"Embedding dimension for {self.model}: {self._dimension}")
        return self._dimension

    @property
    def max_tokens(self) -> int:
        """Maximum context length, queried from Ollama model metadata."""
        if self._max_tokens is None:
            info = self._fetch_model_info()
            model_info = info.get("model_info", {})
            # Ollama exposes context_length in model_info
            for key, value in model_info.items():
                if "context_length" in key and isinstance(value, int):
                    self._max_tokens = value
                    break
            if self._max_tokens is None:
                # Check modelfile parameters
                params = info.get("parameters", "")
                if "num_ctx" in params:
                    try:
                        for line in params.split("\n"):
                            if "num_ctx" in line:
                                self._max_tokens = int(line.split()[-1])
                                break
                    except (ValueError, IndexError):
                        pass
            if self._max_tokens is None:
                logger.warning("Could not determine max_tokens from model info, defaulting to 0")
                self._max_tokens = 0
            logger.debug(f"Max tokens for {self.model}: {self._max_tokens}")
        return self._max_tokens

    def embed_query(self, query: str, embedding_model: str | None = None) -> Any:
        """Generate embedding for a query using Ollama embedding model with resilient retry.

        Args:
            query: Text to embed
            embedding_model: Embedding model name (default: OLLAMA_EMBED_MODEL env var or qwen3-embedding)

        Returns:
            Numpy array of embeddings

        Raises:
            RuntimeError: If embedding API call fails after retries
        """
        if embedding_model is None:
            embedding_model = os.environ.get("OLLAMA_EMBED_MODEL", "qwen3-embedding")
            
        # Check circuit breaker before attempting
        self._check_circuit_breaker()
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                response = self.session.post(
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
                
                # Record success
                self._record_success()
                
                # Return first embedding (embeddings is list of lists)
                return np.array(embeddings[0], dtype=np.float32)
                
            except requests.exceptions.Timeout as e:
                self._record_timeout()
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Embedding timeout (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Embedding failed: Timeout after {max_retries} attempts")
                    raise RuntimeError(f"Embedding timeout after {max_retries} retries: {e}") from e
                    
            except requests.exceptions.ConnectionError as e:
                self._record_timeout()
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Embedding connection error (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Embedding failed: Connection error after {max_retries} attempts")
                    raise RuntimeError(f"Embedding connection failed: {e}") from e
                    
            except Exception as e:
                logger.error(f"Embedding failed: {type(e).__name__}: {e}")
                raise RuntimeError(f"Embedding error: {e}") from e
        
        raise RuntimeError("Embedding failed: unknown error after all retries")

