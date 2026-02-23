import sys
from pathlib import Path

# ensure package import
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import pytest
import requests

from kgbuilder.embedding.ollama import OllamaProvider
from kgbuilder.core.exceptions import LLMError


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
