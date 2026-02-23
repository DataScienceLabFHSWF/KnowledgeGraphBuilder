"""Tests for KG export functionality in storage/export.py"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kgbuilder.storage.export import (
    ExportConfig,
    KGExporter,
    export_kg,
)
from kgbuilder.storage.protocol import InMemoryGraphStore, Node, Edge


def create_sample_store() -> InMemoryGraphStore:
    store = InMemoryGraphStore()
    # add two nodes with various properties to trigger branches
    n1 = Node(id="node1", node_type="Type A", label="Alpha", properties={"confidence": 0.75})
    n2 = Node(
        id="node/2", node_type="123Number", label='Beta "quote"', properties={"description": "has\nnewline"}
    )
    store.add_node(n1)
    store.add_node(n2)
    # add edge with unusual type and self-loop
    e = Edge(id="edge1", source_id="node1", target_id="node/2", edge_type="rel-1", properties={"confidence": 0.5})
    store.add_edge(e)
    return store


def test_export_to_json_and_jsonld(tmp_path: Path):
    store = create_sample_store()
    exporter = KGExporter(store)

    json_text = exporter.to_json()
    data = json.loads(json_text)
    assert "nodes" in data and len(data["nodes"]) == 2
    assert data["statistics"]["node_count"] == 2

    jsonld_text = exporter.to_jsonld()
    doc = json.loads(jsonld_text)
    assert "@context" in doc and "@graph" in doc
    # ensure edge produced as a property on source node
    graph = doc["@graph"]
    assert any(
        "kg:rel-1" in node for node in graph
    )


def test_export_to_turtle_and_sanitize_helpers():
    store = create_sample_store()
    exporter = KGExporter(store)
    t = exporter.to_turtle()
    # should contain prefixes and node labels
    assert "@prefix kg:" in t
    assert "rdfs:label \"Alpha\"" in t
    # sanitized uri for second node should use percent encoding (contains slash)
    assert "%2F" in t

    # helper methods
    assert exporter._sanitize_uri("") == ""
    assert exporter._sanitize_uri("safe_name") == "safe_name"
    assert exporter._sanitize_uri("needs space") == "needs_space"
    assert exporter._escape_turtle('A"B\\C\n') == 'A\\"B\\\\C\\n'
    assert exporter._sanitize_cypher_label("1start") == "_1start"
    assert exporter._sanitize_cypher_label("good-label") == "good_label"

    props = exporter._cypher_properties({"a": 1, "b": object()})
    assert props == {"a": 1}
    assert exporter._cypher_value("foo") == "'foo'"
    assert exporter._cypher_value(True) == "true"
    assert exporter._cypher_value(3.14) == "3.14"
    assert "'None'" == exporter._cypher_value(None)


def test_export_to_cypher_and_graphml(tmp_path: Path):
    store = create_sample_store()
    exporter = KGExporter(store)

    cypher = exporter.to_cypher()
    # should create CREATE statements for nodes and relationships
    assert "CREATE" in cypher
    assert "node1" in cypher
    assert "rel_1" in cypher or "rel-1" in cypher

    graphml = exporter.to_graphml()
    # parse xml
    root = ET.fromstring(graphml)
    assert root.tag.endswith("graphml")
    # should have node and edge elements
    assert root.findall(".//{http://graphml.graphdrawing.org/xmlns}node")
    assert root.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")


def test_export_to_file_and_convenience(tmp_path: Path):
    store = create_sample_store()
    exporter = KGExporter(store)
    json_path = tmp_path / "out.json"
    exporter.export_to_file(json_path, format="json")
    assert json_path.exists()
    text = json_path.read_text()
    assert "kgbuilder-json" in text

    # unsupported format raises
    with pytest.raises(ValueError):
        exporter.export_to_file(tmp_path / "bad.txt", format="bogus")

    # confirm convenience function works
    export_kg(store, tmp_path / "conv.json", format="json")
    assert (tmp_path / "conv.json").exists()
