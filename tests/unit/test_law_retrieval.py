"""Tests for law retrieval service logic."""

from __future__ import annotations

import json
import pytest

from kgbuilder.storage.law_retrieval import (
    LawContext,
    LawGraphRetriever,
)


class DummyEmbedding:
    def embed_text(self, text: str):
        return [0.1, 0.2, 0.3]


class DummyQdrant:
    def __init__(self, results=None):
        # results should be list of tuples (id, score, meta)
        self._results = results or []
        self.last_vec = None

    def search(self, vec, top_k=5):
        self.last_vec = vec
        return self._results


class DummyNeo4j:
    def __init__(self, records=None):
        self._records = records or []
        self.last_query = None

    def query(self, query, params=None):
        self.last_query = (query, params)
        # return simple object with attribute records
        class R:
            def __init__(self, records):
                self.records = records

        return R(self._records)


@pytest.fixture
def retriever():
    return LawGraphRetriever(
        neo4j_store=DummyNeo4j(),
        qdrant_store=DummyQdrant(),
        embedding_provider=DummyEmbedding(),
        max_results=2,
    )


def test_retrieve_for_text_empty(retriever):
    assert retriever.retrieve_for_text("") == []
    assert retriever.retrieve_for_text("   ") == []


def test_retrieve_for_text_success(monkeypatch, retriever):
    q = DummyQdrant(results=[("p1", 0.9, {"law": "L1", "paragraph": "§1", "title": "T", "text": "abc"})])
    retriever.qdrant_store = q
    results = retriever.retrieve_for_text("some text")
    assert len(results) == 1
    ctx = results[0]
    assert isinstance(ctx, LawContext)
    assert ctx.paragraph_id == "p1"
    # embedding provider should have been called with prefix of text
    assert q.last_vec is not None

    # error path returns []
    class BadQ(DummyQdrant):
        def search(self, *args, **kwargs):
            raise RuntimeError("fail")
    retriever.qdrant_store = BadQ()
    assert retriever.retrieve_for_text("x") == []


def test_retrieve_for_entity_and_error(retriever):
    # successful record with properties json
    props = json.dumps({"law_abbreviation": "L2", "enbez": "2", "title": "X", "description": "long text"})
    rec = {"id": "i1", "label": "L2 something", "properties": props}
    retriever.neo4j_store = DummyNeo4j(records=[rec])
    res = retriever.retrieve_for_entity("entity")
    assert len(res) == 1
    assert res[0].law_abbreviation == "L2"

    # missing law_abbreviation -> derive from label
    props2 = json.dumps({"enbez": "3"})
    rec2 = {"id": "i2", "label": "LA123", "properties": props2}
    retriever.neo4j_store = DummyNeo4j(records=[rec2])
    res2 = retriever.retrieve_for_entity("x")
    assert res2[0].law_abbreviation == "LA123"

    # error path
    class BadNeo(DummyNeo4j):
        def query(self, *args, **kwargs):
            raise Exception("boom")
    retriever.neo4j_store = BadNeo()
    assert retriever.retrieve_for_entity("e") == []


def test_retrieve_cross_refs_and_error(retriever):
    props = json.dumps({"law_abbreviation": "L3", "enbez": "5", "title": "Y", "description": "desc"})
    rec = {"id": "i9", "label": "L3 abc", "properties": props}
    retriever.neo4j_store = DummyNeo4j(records=[rec])
    x = retriever.retrieve_cross_references("pid")
    assert len(x) == 1
    assert x[0].paragraph_id == "i9"

    retriever.neo4j_store = DummyNeo4j(records=[])
    assert retriever.retrieve_cross_references("p") == []

    class BadN(DummyNeo4j):
        def query(self, *args, **kwargs):
            raise RuntimeError("fail")
    retriever.neo4j_store = BadN()
    assert retriever.retrieve_cross_references("p") == []



def test_format_as_prompt_context(retriever):
    # ensure the helper works with empty and non-empty context lists
    assert retriever.format_as_prompt_context([]) == ""
    ctxs = [LawContext("p", "L", "1", "T", "text", 0.5)]
    out = retriever.format_as_prompt_context(ctxs)
    assert "RELEVANT LEGAL CONTEXT" in out
    assert "[L 1]" in out
