import numpy as np
import pytest
from types import SimpleNamespace

from kgbuilder.storage.vector import QdrantStore


class DummyHttpClient:
    def __init__(self, base_url):
        self.base_url = base_url


class DummyQdrantClient:
    def __init__(self, url, api_key=None):
        self.url = url
        self.api_key = api_key
        self._collections = {}

    def get_collections(self):
        return list(self._collections.keys())

    def get_collection(self, name):
        if name in self._collections:
            return SimpleNamespace(points_count=self._collections[name])
        raise Exception("no collection")

    def create_collection(self, collection_name, vectors_config):
        self._collections[collection_name] = 0

    def upsert(self, collection_name, points):
        self._collections.setdefault(collection_name, 0)
        self._collections[collection_name] += len(points)


def test_get_base_url_with_env(monkeypatch):
    from kgbuilder.core.env import get_base_url

    monkeypatch.delenv("OLLAMA_URL", raising=False)
    assert get_base_url(None) == "http://localhost:18134"
    monkeypatch.setenv("OLLAMA_URL", "http://custom")
    assert get_base_url(None) == "http://custom"
    # passing explicit url bypasses env when not localhost
    assert get_base_url("http://foo") == "http://foo"


def test_qdrant_store_count_and_store(monkeypatch):
    # patch external dependencies
    monkeypatch.setattr("qdrant_client.QdrantClient", DummyQdrantClient)
    monkeypatch.setattr("httpx.Client", DummyHttpClient)

    store = QdrantStore(url="http://dummy", collection_name="testcol")
    # initial get_points_count should handle missing collection and return 0
    assert store.get_points_count() == 0

    # store one vector
    vec = np.array([0.1, 0.2], dtype=np.float32)
    store.store(ids=["id1"], embeddings=[vec], metadata=[{"foo": "bar"}])

    # now count should reflect stored points
    assert store.get_points_count() == 1

    # storing another with empty metadata should default to {}
    store.store(ids=["id2"], embeddings=[vec], metadata=None)
    assert store.get_points_count() == 2

    # make sure point_counter incremented
    assert store._point_counter == 2


def test_qdrant_store_handles_create_failure(monkeypatch):
    # simulate get_collection raising so that create_collection path is triggered
    class BrokenClient(DummyQdrantClient):
        def get_collection(self, name):
            raise Exception("oops")

    monkeypatch.setattr("qdrant_client.QdrantClient", BrokenClient)
    monkeypatch.setattr("httpx.Client", DummyHttpClient)

    store = QdrantStore(url="http://dummy", collection_name="colx")
    # storing should still not raise and counter should increment
    vec = np.zeros(3, dtype=np.float32)
    store.store(ids=["x"], embeddings=[vec])
    assert store._point_counter == 1
