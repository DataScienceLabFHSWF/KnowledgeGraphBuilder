import sys
import os
import types
from pathlib import Path

# ensure `src` is on path so package imports work during tests
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

# provide a stub "ollama" module so import of kgbuilder.rag succeeds
ollama_stub = types.SimpleNamespace()
ollama_stub.Client = lambda *args, **kwargs: None
sys.modules["ollama"] = ollama_stub

import pytest
from typing import Any

from kgbuilder.rag import StandardRAGPipeline, RAGResponse


class DummyVectorStore:
    """Minimal vector store stub used for unit tests."""

    def __init__(self, results: list[tuple[str, float, dict[str, Any]]]) -> None:
        self._results = results

    def search(self, embedding: Any, top_k: int = 5) -> list[tuple[str, float, dict[str, Any]]]:
        return self._results


class DummyLLMProvider:
    """Simple LLM provider stub with predictable output."""

    def __init__(self, answer: str = "dummy answer") -> None:
        self.model = "dummy-model"
        self.last_prompt: str | None = None
        self._answer = answer

    def generate(self, prompt: str, max_tokens: int = 0) -> str:
        self.last_prompt = prompt
        return self._answer


class DummyOllamaClient:
    """Stub for ollama.Client used by StandardRAGPipeline.retrieve()."""

    def __init__(self, host: str | None = None) -> None:
        self.host = host

    class EmbeddingResp:
        def __init__(self, embeddings: list[list[float]]) -> None:
            self.embeddings = embeddings

    def embed(self, model: str, input: str) -> Any:
        return DummyOllamaClient.EmbeddingResp(embeddings=[[1.0, 2.0, 3.0]])


@pytest.fixture(autouse=True)
def patch_ollama(monkeypatch: Any):
    monkeypatch.setattr("kgbuilder.rag.ollama.Client", DummyOllamaClient)
    yield


def test_retrieve_formats_results() -> None:
    dummy_results = [
        ("doc1", 0.9, {"content": "hello world", "extra": 1}),
        ("doc2", 0.5, {}),
    ]
    vs = DummyVectorStore(dummy_results)
    rag = StandardRAGPipeline(vector_store=vs, llm_provider=DummyLLMProvider())

    docs = rag.retrieve("any query")
    assert isinstance(docs, list)
    assert len(docs) == 2
    assert docs[0]["id"] == "doc1"
    assert docs[0]["content"] == "hello world"
    assert docs[0]["score"] == pytest.approx(0.9)
    assert docs[0]["metadata"]["extra"] == 1
    assert docs[1]["content"] == ""


def test_generate_includes_context_and_query() -> None:
    provider = DummyLLMProvider(answer="42")
    rag = StandardRAGPipeline(vector_store=DummyVectorStore([]), llm_provider=provider)

    ctx = [
        {"content": "doc1 text"},
        {"content": "doc2 text"},
    ]
    answer = rag.generate("what is the answer?", ctx)
    assert answer == "42"
    assert provider.last_prompt is not None
    assert "what is the answer?" in provider.last_prompt
    assert "doc1 text" in provider.last_prompt
    assert "doc2 text" in provider.last_prompt


def test_answer_computes_confidence_and_timing(monkeypatch: Any) -> None:
    provider = DummyLLMProvider(answer="ok")

    class QuickRAG(StandardRAGPipeline):
        def retrieve(self, query: str):
            return [{"score": 0.2}, {"score": 0.8}]

        def generate(self, query: str, context: list[dict[str, Any]]):
            return "ok"

    rag = QuickRAG(vector_store=DummyVectorStore([]), llm_provider=provider)

    resp = rag.answer("q")
    assert isinstance(resp, RAGResponse)
    assert resp.answer == "ok"
    assert resp.confidence == pytest.approx(0.5)
    assert resp.retrieval_time_ms is not None
    assert resp.generation_time_ms is not None


def test_error_handling_in_retrieve(monkeypatch: Any) -> None:
    class BadStore(DummyVectorStore):
        def search(self, embedding, top_k=0):
            raise RuntimeError("oops")

    rag = StandardRAGPipeline(vector_store=BadStore([]), llm_provider=DummyLLMProvider())
    docs = rag.retrieve("q")
    assert docs == []


def test_error_handling_in_generate(monkeypatch: Any) -> None:
    provider = DummyLLMProvider()

    rag = StandardRAGPipeline(vector_store=DummyVectorStore([]), llm_provider=provider)
    def bad_generate(prompt: str, max_tokens: int = 0):
        raise ValueError("fail")
    rag.llm.generate = bad_generate  # type: ignore
    answer = rag.generate("q", [])
    assert answer == "Error generating response"


def test_error_handling_in_answer(monkeypatch: Any) -> None:
    rag = StandardRAGPipeline(vector_store=DummyVectorStore([]), llm_provider=DummyLLMProvider())
    def bad_retrieve(q):
        raise RuntimeError("bad")
    rag.retrieve = bad_retrieve  # type: ignore

    resp = rag.answer("q")
    assert resp.answer == "Error processing query"
    assert resp.confidence == 0.0
    assert resp.retrieved_docs == []
