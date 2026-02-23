import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from kgbuilder.storage.export import KGExporter, ExportConfig, export_kg
from kgbuilder.storage.protocol import InMemoryGraphStore, Node, Edge


def make_store_with_sample_data():
    store = InMemoryGraphStore()
    node1 = Node(id="n1", node_type="TypeA", label="Node1", properties={"confidence": 0.9})
    node2 = Node(id="n2", node_type="TypeB", label="Node2")
    store.add_node(node1)
    store.add_node(node2)
    edge = Edge(id="e1", source_id="n1", target_id="n2", edge_type="rel", properties={"confidence": 0.8})
    store.add_edge(edge)
    return store


def test_export_config_defaults():
    cfg = ExportConfig()
    assert cfg.base_uri.startswith("http://")
    assert cfg.pretty_print


def test_json_and_jsonld_exports():
    store = make_store_with_sample_data()
    exporter = KGExporter(store)
    j = exporter.to_json()
    parsed = json.loads(j)
    assert "nodes" in parsed and "edges" in parsed
    jl = exporter.to_jsonld()
    assert "@context" in jl
    assert "kg:TypeA" in jl


def test_turtle_and_cypher_and_graphml():
    store = make_store_with_sample_data()
    exporter = KGExporter(store)
    turtle = exporter.to_turtle()
    assert "@prefix kg:" in turtle
    assert "Node1" in turtle
    cypher = exporter.to_cypher()
    assert "CREATE" in cypher and "rel" in cypher
    graphml = exporter.to_graphml()
    # basic well-formedness
    assert graphml.startswith("<?xml") or "<graphml" in graphml
    assert "node id=\"n1\"" in graphml


def test_export_to_file_and_bad_format(tmp_path):
    store = make_store_with_sample_data()
    exporter = KGExporter(store)
    path = tmp_path / "out.json"
    exporter.export_to_file(path, format="json")
    assert path.exists()
    assert path.read_text().strip().startswith("{")
    with pytest.raises(ValueError):
        exporter.export_to_file(path, format="foo")


def test_helper_methods_and_export_kg(tmp_path):
    store = InMemoryGraphStore()
    exporter = KGExporter(store)
    assert exporter._sanitize_cypher_label("123abc").startswith("_")
    assert "'" in exporter._cypher_value("O'Neil")
    assert exporter._cypher_properties({"a": 1, "b": []}) == {"a": 1}
    elem = ET.Element("test")
    exporter._add_graphml_data(elem, "key", "val")
    assert elem.find("data").text == "val"

    # convenience function
    filep = tmp_path / "kg.json"
    export_kg(store, filep, format="json")
    assert filep.exists()
