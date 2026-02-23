import pytest
import numpy as np
from types import SimpleNamespace

from kgbuilder.retrieval import FusionRAGRetriever, RetrievalResult


class DummyLLM:
    def __init__(self):
        self.generated = []

    def embed_query(self, query: str) -> np.ndarray:
        # return a fixed embedding vector
        return np.ones((1, 3), dtype=np.float32)

    def generate(self, prompt: str, max_tokens: int = 200) -> str:
        # simple variant generator returning two lines
        return "variant1\nvariant2\n"


class DummyHttpClient:
    def __init__(self, points):
        self.points = points

    def post(self, path, json):
        # ignore request details, return all points once
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"result": {"points": self.points, "next_page_offset": None}},
        )


class DummyQdrant:
    def __init__(self, points=None):
        self.url = "http://dummy"
        self.collection_name = "col"
        self.http_client = DummyHttpClient(points or [])
        self.last_search = None

    def search(self, embedding, top_k=10):
        self.last_search = (embedding, top_k)
        # emit two dummy docs with descending score
        return [("d1", 0.5, {"content": "foo"}), ("d2", 0.2, {"content": "bar"})]


def test_index_and_sparse_retrieval():
    retriever = FusionRAGRetriever(qdrant_store=DummyQdrant(), llm_provider=DummyLLM())
    docs = {"a": "hello world", "b": "foo bar"}
    retriever.index_documents(docs)
    assert retriever._index_built
    assert retriever._documents == docs
    # sparse retrieve computes jaccard
    sparse = retriever._sparse_retrieve("hello")
    assert "a" in sparse
    assert sparse["a"].retrieval_method == "sparse"


def test_dense_and_fusion():
    q = DummyQdrant()
    retriever = FusionRAGRetriever(qdrant_store=q, llm_provider=DummyLLM(), dense_weight=0.7, sparse_weight=0.3, top_k=1)
    # ensure index built so sparse returns nothing
    retriever._index_built = True
    retriever._documents = {"a": "foo"}
    results = retriever.retrieve("query")
    # should call Qdrant.search
    assert q.last_search is not None
    assert isinstance(results, list) and results
    # after fusion the method may be marked 'fused' (weights applied)
    assert results[0].retrieval_method in {"dense", "sparse", "fused"}
    assert len(results) == 1  # top_k limit


def test_retrieve_with_expansion_averaging(monkeypatch):
    q = DummyQdrant()
    retriever = FusionRAGRetriever(qdrant_store=q, llm_provider=DummyLLM(), top_k=2)
    # patch retrieve so we can control scores
    def fake_retrieve(query, query_embedding=None, top_k=None):
        return [RetrievalResult(doc_id="d", content="x", score=0.5, metadata={}, retrieval_method="dense")]
    monkeypatch.setattr(retriever, "retrieve", fake_retrieve)
    # call expansion; variants list will be two strings per DummyLLM
    results = retriever.retrieve_with_expansion("q")
    assert len(results) == 1
    assert results[0].score == 0.5


def test_build_sparse_index_from_qdrant(monkeypatch):
    # create qdrant with some points in payload
    points = [{"id": 1, "payload": {"id": "doc1", "content": "zzz"}}]
    q = DummyQdrant(points=points)
    retriever = FusionRAGRetriever(qdrant_store=q, llm_provider=DummyLLM())
    # initially not indexed
    assert not retriever._index_built
    # call retrieve to trigger lazy build (sparse and dense, but qdrant search returns basic)
    retriever.retrieve("foo")
    assert retriever._index_built
    assert "doc1" in retriever._documents


@pytest.fixture(autouse=True)
def silence_logging(caplog):
    caplog.set_level("DEBUG")
    yield
