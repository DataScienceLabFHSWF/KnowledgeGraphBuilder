import pytest

from kgbuilder.storage.protocol import Edge, Node
from kgbuilder.validation.rules_engine import (
    InversePropertyRule,
    TransitiveRule,
    DomainRangeRule,
    FunctionalPropertyRule,
    RulesEngine,
)
from kgbuilder.validation.models import RuleViolation


class DummyStore:
    def __init__(self, edges=None, nodes=None):
        self._edges = edges or []
        self._nodes = nodes or []

    def get_all_edges(self):
        return self._edges

    def get_all_nodes(self):
        return self._nodes


def make_edge(id_, src, tgt, typ):
    return Edge(id=id_, source_id=src, target_id=tgt, edge_type=typ)


def make_node(id_, ntype):
    return Node(id=id_, node_type=ntype)


def test_inverse_helper_and_rule():
    e1 = make_edge("e1", "A", "B", "knows")
    # missing inverse
    e2 = make_edge("e2", "C", "D", "knows")
    # present inverse for C
    e3 = make_edge("e3", "D", "C", "knows")
    edges = [e1, e2, e3]
    violations = InversePropertyRule._find_missing_inverses(
        edges, "knows", "knows", "test", "desc"
    )
    assert len(violations) == 1
    assert violations[0].subject_id == "B"

    store = DummyStore(edges=edges)
    rule = InversePropertyRule(property_uri="knows", inverse_uri="knows")
    out = rule.check(store)
    assert len(out) == len(violations)
    assert out[0].subject_id == violations[0].subject_id



def test_transitive_helper_and_rule():
    # create a path A->B, B->C but no A->C
    e1 = make_edge("e1", "A", "B", "partOf")
    e2 = make_edge("e2", "B", "C", "partOf")
    e3 = make_edge("e3", "A", "C", "different")
    edges = [e1, e2, e3]
    v = TransitiveRule._find_missing_transitives(edges, "partOf", "t", "d")
    assert len(v) == 1
    assert v[0].object_id == "C"

    store = DummyStore(edges=edges)
    rule = TransitiveRule(property_uri="partOf")
    results = rule.check(store)
    assert len(results) == len(v)
    assert results[0].object_id == v[0].object_id



def test_domain_range_rule():
    e1 = make_edge("e1", "A", "B", "rel")
    nA = make_node("A", "GoodType")
    nB = make_node("B", "BadType")
    store = DummyStore(edges=[e1], nodes=[nA, nB])
    rule = DomainRangeRule(property_uri="rel", domain_types=["GoodType"], range_types=["GoodType"])
    res = rule.check(store)
    assert len(res) == 1
    assert "Range violation" in res[0].reason


def test_functional_property_rule():
    e1 = make_edge("e1", "S", "O1", "fun")
    e2 = make_edge("e2", "S", "O2", "fun")
    store = DummyStore(edges=[e1, e2])
    rule = FunctionalPropertyRule(property_uri="fun")
    res = rule.check(store)
    assert len(res) == 1


def test_rules_engine_operations():
    # instantiate rule via a dummy subclass to satisfy ABC
    class DummyInverse(InversePropertyRule):
        def check(self, store):
            return []
    r1 = DummyInverse(property_uri="p", inverse_uri="inv")
    engine = RulesEngine([r1])
    assert engine.get_rule(r1.name) is r1
    assert engine.disable_rule(r1.name)
    assert not r1.enabled
    assert engine.enable_rule(r1.name)
    assert r1.enabled

    # from_ontology_service just needs to not crash with empty
    class DummyOnt:
        def get_special_properties(self):
            return {"transitive": [], "symmetric": [], "functional": [], "inverse": []}
    eng2 = RulesEngine.from_ontology_service(DummyOnt())
    assert isinstance(eng2, RulesEngine)

    # execute_rules with no violations
    store = DummyStore()
    result = engine.execute_rules(store)
    assert result.rule_violations == []

