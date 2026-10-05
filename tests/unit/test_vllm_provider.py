from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import requests
from pydantic import BaseModel

from kgbuilder.core.exceptions import LLMError
from kgbuilder.embedding.vllm import VLLMProvider


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class PersonOutput(BaseModel):
    name: str


def make_provider() -> VLLMProvider:
    return VLLMProvider(
        model="test-chat",
        base_url="http://vllm:8000",
        embeddings_model="test-embeddings",
        embeddings_base_url="http://embed:8000/v1",
    )


def test_generate_uses_openai_chat_api_and_records_server_token_usage() -> None:
    provider = make_provider()
    requests: list[dict[str, Any]] = []

    def post(url: str, **kwargs: Any) -> FakeResponse:
        requests.append({"url": url, **kwargs})
        return FakeResponse(
            {
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 17, "completion_tokens": 3, "total_tokens": 20},
            }
        )

    provider._session.post = post  # type: ignore[method-assign]

    assert provider.generate("say hello") == "hello"
    assert requests[0]["url"] == "http://vllm:8000/v1/chat/completions"
    assert requests[0]["json"]["model"] == "test-chat"
    assert provider.last_usage == {
        "prompt_tokens": 17,
        "completion_tokens": 3,
        "total_tokens": 20,
        "source": "server",
    }


def test_generate_passes_seed_sampling_and_chat_template_options() -> None:
    provider = VLLMProvider(
        model="kolibri",
        base_url="http://vllm:8000",
        embeddings_model="test-embeddings",
        temperature=1.0,
        top_p=0.97,
        seed=42,
        chat_template_kwargs={"enable_thinking": False},
    )
    request_payloads: list[dict[str, Any]] = []

    def post(_url: str, **kwargs: Any) -> FakeResponse:
        request_payloads.append(kwargs["json"])
        return FakeResponse({"choices": [{"message": {"content": "ok"}}]})

    provider._session.post = post  # type: ignore[method-assign]

    provider.generate("Extract entities.")

    assert request_payloads[0]["temperature"] == 1.0
    assert request_payloads[0]["top_p"] == 0.97
    assert request_payloads[0]["seed"] == 42
    assert request_payloads[0]["chat_template_kwargs"] == {"enable_thinking": False}


def test_generate_structured_validates_schema_and_requests_json() -> None:
    provider = make_provider()
    request_payloads: list[dict[str, Any]] = []

    def post(_url: str, **kwargs: Any) -> FakeResponse:
        request_payloads.append(kwargs["json"])
        return FakeResponse(
            {
                "choices": [{"message": {"content": '{"name": "Ada"}'}}],
                "usage": {},
            }
        )

    provider._session.post = post  # type: ignore[method-assign]

    result = provider.generate_structured("Extract a name.", PersonOutput)

    assert result == PersonOutput(name="Ada")
    assert request_payloads[0]["response_format"] == {"type": "json_object"}
    assert "Extract a name." in request_payloads[0]["messages"][0]["content"]
    assert '"name"' in request_payloads[0]["messages"][0]["content"]


def test_embed_batch_sends_configured_model_and_preserves_response_order() -> None:
    provider = make_provider()
    requests: list[dict[str, Any]] = []

    def post(url: str, **kwargs: Any) -> FakeResponse:
        requests.append({"url": url, **kwargs})
        return FakeResponse(
            {
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ]
            }
        )

    provider._session.post = post  # type: ignore[method-assign]

    vectors = provider.embed_batch(["first", "second"])

    assert requests[0]["url"] == "http://embed:8000/v1/embeddings"
    assert requests[0]["json"] == {"model": "test-embeddings", "input": ["first", "second"]}
    np.testing.assert_array_equal(vectors[0], np.array([0.1, 0.2], dtype=np.float32))
    np.testing.assert_array_equal(vectors[1], np.array([0.3, 0.4], dtype=np.float32))


def test_embed_batch_rejects_invalid_batch_size() -> None:
    provider = make_provider()

    with pytest.raises(ValueError, match="batch_size"):
        provider.embed_batch(["text"], batch_size=0)


def test_generation_surfaces_http_errors_as_llm_error() -> None:
    provider = make_provider()

    def post(_url: str, **_kwargs: Any) -> FakeResponse:
        raise requests.ConnectionError("server unavailable")

    provider._session.post = post  # type: ignore[method-assign]

    with pytest.raises(LLMError, match="vLLM chat generation failed"):
        provider.generate("test")
