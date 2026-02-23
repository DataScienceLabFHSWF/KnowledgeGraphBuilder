import pytest

from kgbuilder.storage.protocol import Node, Edge, QueryResult, GraphStatistics


def test_node_dict_roundtrip(monkeypatch):
    # ensure created_at is set automatically
    node = Node(id="n1", node_type="TypeA", label="Name")
    assert "created_at" in node.metadata

    d = node.to_dict()
    # dictionary should contain all expected keys
    assert d["id"] == "n1"
    assert d["type"] == "TypeA"
    # from_dict should reconstruct equivalent object
    node2 = Node.from_dict(d)
    assert node2.id == node.id
    assert node2.node_type == node.node_type
    assert "created_at" in node2.metadata


def test_edge_dict_roundtrip():
    edge = Edge(
        id="e1",
        source_id="s1",
        target_id="t1",
        edge_type="REL",
        source_node_type="SType",
        target_node_type="TType",
    )
    assert "created_at" in edge.metadata
    d = edge.to_dict()
    assert d["id"] == "e1"
    assert d["type"] == "REL"
    assert d["source_node_type"] == "SType"
    # from_dict should accept older key names
    edge2 = Edge.from_dict({
        "id": "e1",
        "source_id": "s1",
        "target_id": "t1",
        "edge_type": "REL",
        "properties": {},
        "metadata": {},
    })
    assert edge2.edge_type == "REL"


def test_queryresult_and_graph_statistics():
    qr = QueryResult(records=[{"a": 1}], columns=["a"], summary={"r": 2})
    assert qr.records == [{"a": 1}]
    assert qr.columns == ["a"]
    stats = GraphStatistics(node_count=10, edge_count=5)
    assert stats.node_count == 10
    assert stats.edge_count == 5
    # default values
    stats2 = GraphStatistics()
    assert stats2.avg_confidence == 0.0
