"""vLLM provider using its OpenAI-compatible chat and embeddings APIs."""

from __future__ import annotations

import json
import os
from typing import Any

import numpy as np
import requests  # type: ignore[import-untyped]
import structlog
from pydantic import BaseModel, ValidationError

from kgbuilder.core.exceptions import LLMError

logger = structlog.get_logger(__name__)


def _openai_api_base(url: str) -> str:
    """Normalize a server URL to its OpenAI-compatible API root."""
    return f"{url.rstrip('/')}/v1" if not url.rstrip("/").endswith("/v1") else url.rstrip("/")


class VLLMProvider:
    """Generate text and embeddings from OpenAI-compatible vLLM endpoints.

    Chat generation and embeddings can use separate model servers. Embeddings
    must match the model and dimensionality used to index the existing Qdrant
    collection.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        embeddings_model: str,
        embeddings_base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 600,
        temperature: float = 0.2,
        top_p: float = 0.9,
        seed: int | None = None,
        chat_template_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("vLLM generation model must not be empty")
        if not embeddings_model.strip():
            raise ValueError("vLLM embeddings model must not be empty")
        self.model = model
        self.model_name = model
        self.base_url = _openai_api_base(base_url)
        self.embeddings_model = embeddings_model
        self.embeddings_base_url = _openai_api_base(embeddings_base_url or base_url)
        self.timeout = timeout
        self.temperature = temperature
        self.top_p = top_p
        self.seed = seed
        self.chat_template_kwargs = chat_template_kwargs or {}
        self._headers = {
            "Authorization": f"Bearer {api_key or os.getenv('VLLM_API_KEY', 'EMPTY')}",
            "Content-Type": "application/json",
        }
        self._session = requests.Session()
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.usage_history: list[dict[str, Any]] = []
        self.last_usage: dict[str, Any] = {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "source": "server",
        }

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text via `/v1/chat/completions`."""
        options = dict(kwargs)
        options.pop("use_cache", None)
        output_format = options.pop("format", None)
        temperature = options.pop("temperature", self.temperature)
        top_p = options.pop("top_p", self.top_p)
        max_tokens = options.pop("max_tokens", None)
        seed = options.pop("seed", self.seed)
        chat_template_kwargs = options.pop(
            "chat_template_kwargs", self.chat_template_kwargs
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": top_p,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if seed is not None:
            payload["seed"] = seed
        if chat_template_kwargs:
            payload["chat_template_kwargs"] = chat_template_kwargs
        if output_format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            response = self._session.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("chat completion did not contain text content")
            usage = result.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            self.last_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": usage.get(
                    "total_tokens",
                    (prompt_tokens + completion_tokens)
                    if prompt_tokens is not None and completion_tokens is not None
                    else None,
                ),
                "source": "server" if usage else "unavailable",
            }
            self.usage_history.append(self.last_usage.copy())
            if prompt_tokens is not None:
                self.total_prompt_tokens += prompt_tokens
            if completion_tokens is not None:
                self.total_completion_tokens += completion_tokens
            return content
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"vLLM chat generation failed: {exc}") from exc

    def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        max_retries: int = 3,
        **kwargs: Any,
    ) -> Any:
        """Generate and validate JSON matching a Pydantic schema."""
        if max_retries < 1:
            raise ValueError("max_retries must be at least one")
        schema_instruction = (
            "\n\nReturn only a JSON object matching this schema:\n"
            f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        )
        last_error: Exception | None = None
        for attempt in range(max_retries):
            retry_prompt = prompt + schema_instruction
            if attempt:
                retry_prompt += (
                    f"\nThe previous response was invalid: {last_error}. Return valid JSON."
                )
            try:
                output = self.generate(retry_prompt, format="json", **kwargs)
                return schema.model_validate_json(output)
            except (ValidationError, ValueError, LLMError) as exc:
                last_error = exc
        raise LLMError(
            f"vLLM failed to produce valid {schema.__name__} JSON after {max_retries} attempts: "
            f"{last_error}"
        ) from last_error

    def embed_query(self, query: str, embedding_model: str | None = None) -> np.ndarray:
        """Generate a single embedding using `/v1/embeddings`."""
        embeddings = self.embed_batch(
            [query],
            embedding_model=embedding_model,
        )
        return embeddings[0]

    def embed_text(self, text: str) -> np.ndarray:
        """EmbeddingProvider-compatible alias for a single query."""
        return self.embed_query(text)

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        embedding_model: str | None = None,
    ) -> list[np.ndarray]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []
        if batch_size < 1:
            raise ValueError("batch_size must be greater than zero")
        model = embedding_model or self.embeddings_model
        vectors: list[np.ndarray | None] = [None] * len(texts)
        try:
            for offset in range(0, len(texts), batch_size):
                batch = texts[offset : offset + batch_size]
                response = self._session.post(
                    f"{self.embeddings_base_url}/embeddings",
                    headers=self._headers,
                    json={"model": model, "input": batch},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                result = response.json()
                for item in result["data"]:
                    index = offset + item.get("index", 0)
                    vectors[index] = np.asarray(item["embedding"], dtype=np.float32)
            if any(vector is None for vector in vectors):
                raise LLMError("vLLM embeddings response omitted one or more vectors")
            return [vector for vector in vectors if vector is not None]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"vLLM embeddings request failed: {exc}") from exc

    @property
    def dimension(self) -> int:
        """Return the embedding dimensionality after a sample request."""
        return len(self.embed_text("dimension probe"))

    @property
    def max_tokens(self) -> int:
        """Return zero when the server does not expose model context metadata."""
        return 0
