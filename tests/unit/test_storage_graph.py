"""Tests for storage.graph module and Neo4jStore functionality."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

import pytest

from kgbuilder.storage import graph


class DummyStore:
    def add_node(self, node_id: str, label: str, properties: dict[str, Any]) -> None:
        pass

    def add_edge(self, source_id: str, target_id: str, relation_type: str, properties: dict[str, Any]) -> None:
        pass

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        return []


def test_graphstore_protocol_check():
    # runtime_checkable protocol should recognize DummyStore
    assert isinstance(DummyStore(), graph.GraphStore)


class FakeResult:
    def __init__(self, records=None):
        # records may be list of dicts or tuples returned by neo4j
        self._records = records or []

    def consume(self):
        pass

    def __iter__(self):
        # unwrap singleton tuples to make dict() happy
        for r in self._records:
            if isinstance(r, tuple) and len(r) == 1:
                yield r[0]
            else:
                yield r


class FakeSession:
    def __init__(self, record_data=None, capture=None):
        self.record_data = record_data
        self.capture = capture

    def run(self, cypher, params=None, **kwargs):
        # capture cypher and any provided params/kwargs for assertion
        if self.capture is not None:
            self.capture.append((cypher, params or kwargs))
        return FakeResult(self.record_data)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class FakeDriver:
    def __init__(self, uri, auth=None, session_obj=None):
        self.uri = uri
        self.auth = auth
        self.session_obj = session_obj or FakeSession()

    def session(self):
        return self.session_obj


class FakeNeo4jModule(ModuleType):
    def __init__(self):
        super().__init__("neo4j")
        self.GraphDatabase = self

    @staticmethod
    def driver(uri, auth=None):
        # return a FakeDriver with ability to capture queries
        return FakeDriver(uri, auth, session_obj=FakeSession())


@pytest.fixture(autouse=True)
def fake_neo4j(monkeypatch):
    """Insert a fake neo4j module so Neo4jStore doesn't need a real database."""
    fake = FakeNeo4jModule()
    monkeypatch.setitem(sys.modules, "neo4j", fake)
    yield
    # cleanup not necessary; fixture ends


def test_neo4jstore_basic_operations(monkeypatch):
    # prepare a driver that records calls
    captured = []
    fake_driver = FakeDriver("bolt://fake", auth=None, session_obj=FakeSession(capture=captured))

    # monkeypatch GraphDatabase.driver to return our fake_driver
    import neo4j  # this will be our fake module from fixture

    monkeypatch.setattr(neo4j, "driver", lambda uri, auth=None: fake_driver)

    store = graph.Neo4jStore(uri="bolt://fake")
    # __init__ should have run verify and constraints via captured
    assert captured, "expected some cypher executed during init"

    # clear captured and test add_node
    captured.clear()
    store.add_node("n1", "Label", {"foo": "bar"})
    assert any("MERGE" in c[0] for c in captured)

    captured.clear()
    store.add_edge("n1", "n2", "REL", {"p": 1})
    assert any("MATCH" in c[0] for c in captured)

    # test query returns list of dicts
    fake_driver.session_obj.record_data = [({"x": 1},)]
    res = store.query("RETURN 1 as x")
    assert isinstance(res, list)


def test_neo4jstore_add_entities(monkeypatch):
    # create simple fake driver/session as before
    captured = []
    fake_driver = FakeDriver("bolt://fake", auth=None, session_obj=FakeSession(capture=captured))
    import neo4j
    monkeypatch.setattr(neo4j, "driver", lambda uri, auth=None: fake_driver)

    store = graph.Neo4jStore(uri="bolt://fake")
    # create dummy entities
    from kgbuilder.core.models import ExtractedEntity

    ent = ExtractedEntity(
        id="e1",
        label="lbl",
        entity_type="Type",
        confidence=0.9,
        description="desc",
        evidence=[],
    )
    store.add_entities([ent])
    # ensure some query executed for adding node
    assert any("MERGE" in c[0] for c in captured)
