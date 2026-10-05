import sys
from pathlib import Path

# ensure package import
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import pytest
import requests

from kgbuilder.core.exceptions import LLMError
from kgbuilder.embedding.ollama import OllamaProvider


class DummySession:
    def post(self, *args, **kwargs):
        raise requests.exceptions.Timeout("timeout")


def test_embedding_timeout_raises_llmerror(monkeypatch):
    # disable network check in constructor
    monkeypatch.setattr(OllamaProvider, "_check_connection", lambda self: None)
    provider = OllamaProvider(model="qwen3", base_url="http://fake")
    # monkeypatch session to dummy
    provider.session = DummySession()

    with pytest.raises(LLMError, match="timeout"):
        provider.embed_query("text")


def test_generation_timeout_raises_llmerror(monkeypatch):
    monkeypatch.setattr(OllamaProvider, "_check_connection", lambda self: None)
    provider = OllamaProvider(model="qwen3", base_url="http://fake")
    class DummyResp:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": []}

    def fake_post(*args, **kwargs):
        raise requests.exceptions.Timeout("gen-timeout")

    provider.session = type("S", (), {"post": fake_post})()

    with pytest.raises(LLMError, match="gen-timeout"):
        provider.generate("prompt")


def test_structured_generation_forwards_temperature_once(monkeypatch):
    from kgbuilder.extraction.schemas import EntityExtractionOutput

    captured_kwargs = {}

    def fake_generate(self, prompt, **kwargs):
        captured_kwargs.update(kwargs)
        return '{"entities": []}'

    monkeypatch.setattr(OllamaProvider, "_check_connection", lambda self: None)
    monkeypatch.setattr(OllamaProvider, "generate", fake_generate)
    provider = OllamaProvider(model="qwen3", base_url="http://fake")

    result = provider.generate_structured(
        "Extract entities",
        EntityExtractionOutput,
        temperature=0.2,
    )

    assert result == EntityExtractionOutput(entities=[])
    assert captured_kwargs["temperature"] == 0.2
    assert captured_kwargs["format"] == "json"
    assert captured_kwargs["use_cache"] is False
