"""Unit tests for storage protocol and in-memory graph store."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kgbuilder.storage.protocol import (
    Edge,
    GraphStatistics,
    InMemoryGraphStore,
    Node,
    QueryResult,
    create_graph_store,
)


def test_node_to_from_dict_roundtrip():
    node = Node(id="n1", node_type="TypeA", label="Label", properties={"a": 1})
    d = node.to_dict()
    assert d["id"] == "n1"
    assert d["type"] == "TypeA"
    assert "created_at" in d["metadata"]

    node2 = Node.from_dict(d)
    assert node2.id == node.id
    assert node2.node_type == node.node_type
    assert node2.properties == node.properties
    assert node2.metadata == node.metadata


def test_edge_to_from_dict_roundtrip():
    edge = Edge(
        id="e1",
        source_id="n1",
        target_id="n2",
        edge_type="RELATED",
        source_node_type="TypeA",
        target_node_type="TypeB",
        properties={"conf": 0.5},
    )
    d = edge.to_dict()
    assert d["id"] == "e1"
    assert d["source_id"] == "n1"
    assert d["type"] == "RELATED"
    assert "created_at" in d["metadata"]

    edge2 = Edge.from_dict(d)
    assert edge2.id == edge.id
    assert edge2.source_id == edge.source_id
    assert edge2.target_id == edge.target_id
    assert edge2.edge_type == edge.edge_type
    assert edge2.source_node_type == edge.source_node_type
    assert edge2.target_node_type == edge.target_node_type


def test_query_result_and_stats_dataclasses():
    qr = QueryResult(records=[{"a": 1}], columns=["a"], summary={"count": 1})
    assert qr.records[0]["a"] == 1
    gs = GraphStatistics(node_count=2, edge_count=1)
    assert gs.node_count == 2
    assert gs.edge_count == 1


def test_inmemory_store_basic_node_operations():
    store = InMemoryGraphStore()
    n1 = Node(id="n1", node_type="A")
    n2 = Node(id="n2", node_type="B")

    assert store.add_node(n1) == "n1"
    assert store.get_node("n1") is n1
    assert store.get_nodes_by_type("A") == [n1]
    assert store.update_node("n1", {"foo": "bar"})
    assert store.get_node("n1").properties["foo"] == "bar"
    # updating non-existent node returns False
    assert not store.update_node("missing", {})

    # delete node without edges
    assert store.delete_node("n1")
    assert store.get_node("n1") is None
    assert not store.delete_node("n1")


def test_inmemory_store_edge_operations_and_queries():
    store = InMemoryGraphStore()
    n1 = Node(id="n1", node_type="A")
    n2 = Node(id="n2", node_type="A")
    store.add_node(n1)
    store.add_node(n2)

    # adding edge with missing node fails
    with pytest.raises(ValueError):
        store.add_edge(Edge(id="e1", source_id="n1", target_id="missing", edge_type="rel"))

    # add valid edge
    e = Edge(id="e1", source_id="n1", target_id="n2", edge_type="rel")
    assert store.add_edge(e) == "e1"
    assert store.get_edge("e1") is e
    # directional queries
    assert store.get_edges_for_node("n1", direction="outgoing") == [e]
    assert store.get_edges_for_node("n2", direction="incoming") == [e]
    assert store.get_edges_for_node("n1", direction="both") == [e]

    # query returns node dictionaries
    result_all = store.query("*")
    assert isinstance(result_all, QueryResult)
    assert len(result_all.records) == 2
    result_type = store.query("A")
    assert len(result_type.records) == 2


def test_inmemory_store_batch_and_statistics():
    store = InMemoryGraphStore()
    nodes = [Node(id=f"n{i}", node_type="T", properties={"confidence": i * 0.1}) for i in range(3)]
    edges = [
        Edge(id=f"e{i}", source_id=f"n{i}", target_id=f"n{(i+1)%3}", edge_type="rel")
        for i in range(3)
    ]
    count_nodes = store.add_nodes_batch(nodes)
    assert count_nodes == 3
    count_edges = store.add_edges_batch(edges)
    # all edges should be added as nodes exist
    assert count_edges == 3

    stats = store.get_statistics()
    assert stats.node_count == 3
    assert stats.edge_count == 3
    assert stats.nodes_by_type == {"T": 3}
    assert stats.edges_by_type == {"rel": 3}
    assert pytest.approx(stats.avg_confidence, rel=1e-9) == sum(n.properties["confidence"] for n in nodes) / 3
    # density: 3 edges, 3 nodes -> 3/(3*2)=0.5
    assert pytest.approx(stats.density, rel=1e-9) == 0.5


def test_inmemory_store_iteration_clear_and_export(tmp_path: Path):
    store = InMemoryGraphStore()
    n = Node(id="n1", node_type="X")
    store.add_node(n)
    e = Edge(id="e1", source_id="n1", target_id="n1", edge_type="self")
    store.add_edge(e)

    nodes = list(store.get_all_nodes())
    edges = list(store.get_all_edges())
    assert nodes == [n]
    assert edges == [e]

    data = store.to_dict()
    assert data["metadata"]["node_count"] == 1
    assert data["metadata"]["edge_count"] == 1
    # round-trip
    store2 = InMemoryGraphStore.from_dict(data)
    assert store2.get_node("n1") is not None
    assert store2.get_edge("e1") is not None

    json_str = store.to_json()
    parsed = json.loads(json_str)
    assert parsed["metadata"]["node_count"] == 1

    store.clear()
    assert list(store.get_all_nodes()) == []
    assert list(store.get_all_edges()) == []


def test_create_graph_store_factory():
    mem = create_graph_store("memory")
    assert isinstance(mem, InMemoryGraphStore)
    with pytest.raises(ValueError):
        create_graph_store("unknown")
