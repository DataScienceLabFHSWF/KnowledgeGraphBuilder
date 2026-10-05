from __future__ import annotations

import pytest

import kgbuilder.api.dependencies as dependencies
from kgbuilder.embedding.vllm import VLLMProvider


def test_vllm_is_selected_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies, "_LLM_BACKEND", "vllm")
    monkeypatch.setattr(dependencies, "_LLM_MODEL", "test-chat")
    monkeypatch.setattr(dependencies, "_VLLM_BASE_URL", "http://vllm:8000/v1")
    monkeypatch.setattr(dependencies, "_VLLM_EMBEDDING_BASE_URL", "http://embed:8000/v1")
    monkeypatch.setattr(dependencies, "_VLLM_EMBEDDING_MODEL", "test-embeddings")
    dependencies.get_llm_provider.cache_clear()

    try:
        provider = dependencies.get_llm_provider()
    finally:
        dependencies.get_llm_provider.cache_clear()

    assert isinstance(provider, VLLMProvider)
    assert provider.model_name == "test-chat"
    assert provider.base_url == "http://vllm:8000/v1"
    assert provider.embeddings_model == "test-embeddings"


def test_unsupported_provider_name_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependencies, "_LLM_BACKEND", "unknown")
    dependencies.get_llm_provider.cache_clear()

    try:
        with pytest.raises(ValueError, match="Supported values: ollama, vllm"):
            dependencies.get_llm_provider()
    finally:
        dependencies.get_llm_provider.cache_clear()
