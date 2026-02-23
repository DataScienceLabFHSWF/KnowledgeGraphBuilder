from __future__ import annotations

import pytest
from types import SimpleNamespace

import rdflib

from kgbuilder.validation.shacl_validator import SHACLValidator
from kgbuilder.storage.protocol import Node, Edge


class DummyStore:
    def __init__(self, nodes=None, edges=None, stats=None):
        self._nodes = nodes or []
        self._edges = edges or []
        self._stats = stats

    def get_all_nodes(self):
        return list(self._nodes)

    def get_all_edges(self):
        return list(self._edges)

    def get_node(self, nid):
        for n in self._nodes:
            if n.id == nid:
                return n
        return None

    def get_statistics(self):
        if self._stats:
            return self._stats
        raise RuntimeError("no stats")

    def query(self, q):
        # dummy query returning empty records
        return SimpleNamespace(records=[])


def test_init_rejects_none():
    with pytest.raises(ValueError):
        SHACLValidator(None)


def test_validate_node_and_edge_basic():
    validator = SHACLValidator(rdflib.Graph())
    n = Node(id="", node_type="")
    res = validator.validate_node(n)
    assert not res.valid
    assert any(v.path == "id" for v in res.violations)
    e = Edge(id="e1", source_id="", target_id="t", edge_type="")
    res2 = validator.validate_edge(e)
    assert not res2.valid
    assert any(v.path == "source_id" for v in res2.violations)

    # confidence not numeric
    e2 = Edge(id="e2", source_id="s", target_id="t", edge_type="typ", properties={"confidence": "high"})
    res3 = validator.validate_edge(e2)
    assert any("confidence" in v.path for v in res3.violations)

    # valid edge
    e3 = Edge(id="e3", source_id="s", target_id="t", edge_type="typ", properties={"confidence": 0.5})
    res4 = validator.validate_edge(e3)
    assert res4.valid


def test_validation_models_behavior() -> None:
    from kgbuilder.validation.models import ValidationViolation, ValidationResult, ViolationSeverity

    v = ValidationViolation(
        severity="error",
        path="p",
        message="msg",
        value=123,
        expected="exp",
        focus_node="nid",
        shape_uri="shape",
    )
    d = v.to_dict()
    assert d["severity"] == "ERROR"
    assert d["value"] == "123"

    res = ValidationResult(node_count=2, edge_count=1)
    assert res.pass_rate == 1.0
    res.add_violation(v)
    assert not res.valid
    assert res.violations_by_severity.get("error") == 1


def test_convert_store_to_rdf_and_errors():
    validator = SHACLValidator(rdflib.Graph())
    # simple nodes/edges
    n1 = Node(id="1", node_type="A", label="Lab", properties={"foo": "bar"})
    e1 = Edge(id="e", source_id="1", target_id="2", edge_type="rel")
    store = DummyStore(nodes=[n1], edges=[e1])
    g = validator._convert_store_to_rdf(store)
    assert isinstance(g, rdflib.Graph)
    # should contain type triple for node
    assert any(str(o).endswith("/A") for s, p, o in g.triples((None, rdflib.RDF.type, None)))

    # store missing get_all_edges triggers ValueError
    class BrokenStore:
        def get_all_nodes(self):
            return []
    with pytest.raises(ValueError):
        validator._convert_store_to_rdf(BrokenStore())


def test_validate_flow_monkeypatched(monkeypatch):
    graph = rdflib.Graph()
    validator = SHACLValidator(graph)
    store = DummyStore(nodes=[Node(id="1", node_type="T")], edges=[])

    # patch pyshacl.validate to return both conformance states
    # original validate signature expects shacl_graph keyword
    def fake_validate(data_graph, shacl_graph=None, inference=None):
        return (True, None, "")

    monkeypatch.setattr("kgbuilder.validation.shacl_validator.validate", fake_validate)
    res = validator.validate(store)
    assert res.valid
    # node_count may not be set on success, only validity matters

    def fake_validate2(data_graph, shacl_graph=None, inference=None):
        return (False, graph, "text")

    monkeypatch.setattr("kgbuilder.validation.shacl_validator.validate", fake_validate2)
    # also patch parser to avoid complicated RDF traversal
    monkeypatch.setattr(SHACLValidator, "_parse_shacl_results", lambda self, g: [
        SimpleNamespace(severity="error", path="x", message="m", value=None, expected="", focus_node="", shape_uri="")
    ])
    res2 = validator.validate(store)
    assert not res2.valid
    assert res2.violations


def test_validate_handles_conversion_error(monkeypatch):
    validator = SHACLValidator(rdflib.Graph())
    store = DummyStore()
    monkeypatch.setattr(SHACLValidator, "_convert_store_to_rdf", lambda self, s: (_ for _ in ()).throw(RuntimeError("boom")))
    res = validator.validate(store)
    assert not res.valid
    assert any("boom" in v.message for v in res.violations)
