from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.storage.protocol import Node, Edge, QueryResult, GraphStatistics


class FakeResult:
    def __init__(self, records=None, single=None, keys=None, summary=None):
        self._records = records or []
        self._single = single
        self._keys = keys or []
        self._summary = summary or SimpleNamespace(
            counters=SimpleNamespace(
                nodes_created=0,
                nodes_deleted=0,
                relationships_created=0,
                relationships_deleted=0,
            )
        )

    def single(self):
        return self._single

    def __iter__(self):
        return iter(self._records)

    def keys(self):
        return self._keys

    def consume(self):
        return self._summary


class FakeSession:
    def __init__(self):
        self.last_query = None
        self.last_params = None
        # queue of results to return on successive run calls
        self._queue: list[FakeResult] = []

    def run(self, query: str, params: Any = None, **kwargs: Any) -> FakeResult:
        # signature matches driver.run(query, params)
        self.last_query = query.strip()
        # prefer params dict if provided
        self.last_params = params if params is not None else kwargs
        if self._queue:
            return self._queue.pop(0)
        return FakeResult(single=None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class FakeDriver:
    def __init__(self):
        self.session_obj = FakeSession()

    def session(self, database=None):
        # ignore database
        return self.session_obj

    def close(self):
        pass


@pytest.fixture(autouse=True)
def fake_driver(monkeypatch):
    """Patch GraphDatabase.driver to return our fake driver."""
    monkeypatch.setattr(
        "kgbuilder.storage.neo4j_store.GraphDatabase.driver",
        lambda uri, auth: FakeDriver(),
    )


def test_add_and_get_node():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    session = store._driver.session_obj

    # configure return for add_node
    session._queue.append(FakeResult(single={"id": "n1"}))
    n = Node(id="n1", label="L", node_type="T")
    assert store.add_node(n) == "n1"
    assert "MERGE" in session.last_query
    assert session.last_params["id"] == "n1"

    # get_node when missing
    session._queue.append(FakeResult(single=None))
    assert store.get_node("n1") is None

    # get_node when present
    props = {"foo": "bar"}
    record = {"id": "n1", "label": "L", "node_type": "T", "properties": json.dumps(props)}
    session._queue.append(FakeResult(single=record))
    got = store.get_node("n1")
    assert got.id == "n1" and got.properties == props


def test_update_and_delete_node():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    s = store._driver.session_obj

    s._queue.append(FakeResult(single={"count": 1}))
    assert store.update_node("n1", {"a": 1}) is True
    s._queue.append(FakeResult(single={"count": 0}))
    assert store.update_node("n2", {}) is False

    s._queue.append(FakeResult(single={"count": 1}))
    assert store.delete_node("n1") is True
    s._queue.append(FakeResult(single={"count": 0}))
    assert store.delete_node("n2") is False


def test_get_nodes_by_type():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    s = store._driver.session_obj
    rec = {"id": "1", "label": "L", "node_type": "T", "properties": json.dumps({})}
    s._queue.append(FakeResult(records=[rec]))
    nodes = store.get_nodes_by_type("T")
    assert len(nodes) == 1 and nodes[0].id == "1"


def test_add_edge_missing_node():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    s = store._driver.session_obj
    # simulate count 0 -> missing node
    s._queue.append(FakeResult(single={"count": 0}))
    with pytest.raises(ValueError):
        store.add_edge(Edge(id="e", source_id="a", target_id="b", edge_type="t"))


def test_add_and_delete_edge():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    s = store._driver.session_obj
    # simulate exist
    s._queue.extend([FakeResult(single={"count": 1}), FakeResult(single={"id": "e1"})])
    edge = Edge(id="e1", source_id="a", target_id="b", edge_type="t")
    assert store.add_edge(edge) == "e1"

    s._queue.append(FakeResult(single={"count": 1}))
    assert store.delete_edge("e1") is True
    s._queue.append(FakeResult(single={"count": 0}))
    assert store.delete_edge("miss") is False


def test_get_edges_for_node_directions():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    s = store._driver.session_obj
    rec = {"id": "e", "source_id": "a", "target_id": "b", "edge_type": "t", "properties": json.dumps({})}
    for diropt in ("out", "in", "both"):
        s._queue.append(FakeResult(records=[rec]))
        edges = store.get_edges_for_node("n", direction=diropt)
        assert len(edges) == 1 and edges[0].edge_type == "t"


def test_batch_operations():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    s = store._driver.session_obj
    # batch_create_nodes uses add_node, so we simulate
    s._queue.append(FakeResult(single={"id": "n1"}))
    ids = store.batch_create_nodes([Node(id="n1", label="", node_type="T")])
    assert ids == ["n1"]

    # batch_create_edges: first add fails value error
    edge = Edge(id="e", source_id="a", target_id="b", edge_type="t")
    # make add_edge raise
    def fail_run(q, **p):
        raise ValueError("boom")
    s.run = fail_run
    ids2 = store.batch_create_edges([edge])
    assert ids2 == []


def test_query_and_get_subgraph():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    s = store._driver.session_obj
    # query simple
    fake_summary = SimpleNamespace(counters=SimpleNamespace(nodes_created=1,nodes_deleted=2,relationships_created=3,relationships_deleted=4))
    s._queue.append(FakeResult(records=[{"a": 1}], keys=["a"], summary=fake_summary))
    qr = store.query("MATCH () RETURN 1")
    assert isinstance(qr, QueryResult)
    assert qr.records == [{"a": 1}]
    assert qr.summary["nodes_created"] == 1

    # get_subgraph: return one node and one edge using dict-like records
    node_obj = {"id": "n1", "label": "L", "properties": json.dumps({}), "node_type": "T"}
    class EdgeObj(dict):
        def __init__(self, base, start_node, end_node, type):
            super().__init__(base)
            self.start_node = start_node
            self.end_node = end_node
            self.type = type
    edge_obj = EdgeObj({"id": "e1", "properties": json.dumps({})}, start_node={"id": "n1"}, end_node={"id": "n2"}, type="t")
    s._queue.append(FakeResult(single={"nodes": [node_obj], "edges": [edge_obj]}))
    nodes, edges = store.get_subgraph(["n1"], depth=2)
    assert len(nodes) == 1 and len(edges) == 1


def test_get_statistics_and_health_and_clear():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    s = store._driver.session_obj
    stats_record = {"nodes_by_type": [{"type": "T", "count": 5}], "total_nodes": 5}
    # queue both returns: statistics then edge count
    s._queue.extend([FakeResult(single=stats_record), FakeResult(single={"count": 7})])
    stats = store.get_statistics()
    assert isinstance(stats, GraphStatistics)
    assert stats.edge_count == 7

    # health_check success
    assert store.health_check() is True
    # health_check failure by temporarily overriding run then restoring
    orig_run = s.run
    def raise_run(q, params=None, **p):
        raise RuntimeError
    s.run = raise_run
    assert store.health_check() is False
    # restore the original so clear works
    s.run = orig_run

    # clear should not raise
    store.clear()


def test_get_all_iterators():
    store = Neo4jGraphStore("bolt://x", ("u", "p"))
    s = store._driver.session_obj
    rec1 = {"id": "n", "label": "L", "node_type": "T", "properties": json.dumps({})}
    s._queue.append(FakeResult(records=[rec1]))
    nodes = list(store.get_all_nodes())
    assert nodes and nodes[0].id == "n"

    rec2 = {"id": "e", "source_id": "a", "target_id": "b", "edge_type": "t", "properties": json.dumps({})}
    s._queue.append(FakeResult(records=[rec2]))
    edges = list(store.get_all_edges())
    assert edges and edges[0].id == "e"
