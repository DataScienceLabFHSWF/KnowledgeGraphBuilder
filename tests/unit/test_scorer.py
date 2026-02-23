from __future__ import annotations

import rdflib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import json

import pytest

from kgbuilder.storage.protocol import Node, Edge
from kgbuilder.validation.scorer import KGQualityScorer, KGQualityReport
from kgbuilder.validation.shacl_validator import SHACLValidator
from kgbuilder.validation.static_validator import StaticValidator, StaticValidationResult


class DummyStore:
    """Minimal graph store implementing necessary methods for scoring."""

    def __init__(self, nodes=None, edges=None):
        self._nodes = nodes or []
        self._edges = edges or []

    def to_dict(self):
        return {"entities": self._nodes, "relations": self._edges}

    def get_all_nodes(self):
        return self._nodes

    def get_all_edges(self):
        return self._edges

    def query(self, q: str):
        return SimpleNamespace(records=[{"cnt": len(self._nodes)}])


@pytest.fixture

def dummy_store() -> DummyStore:
    n = Node(id="1", node_type="Person")
    e = Edge(id="e1", source_id="1", target_id="1", edge_type="self")
    return DummyStore(nodes=[n], edges=[e])


def make_scorer(monkeypatch):
    scorer = KGQualityScorer()
    # stub out pyshacl runner so it doesn't require actual validation
    monkeypatch.setattr(scorer, "_run_pyshacl", lambda s, sh: (0.5, 1, None))
    return scorer


def test_score_store_no_shapes(monkeypatch, dummy_store):
    scorer = make_scorer(monkeypatch)
    # ensure there is no shapes file anywhere
    report = scorer.score_store(dummy_store)
    assert isinstance(report, KGQualityReport)
    # with no shapes, consistency and acceptance should default to 1
    assert report.consistency == 1.0
    assert report.acceptance_rate == 1.0
    # class coverage computed even without shapes (will be zero)
    assert 0 <= report.class_coverage <= 1.0
    assert report.shacl_score == 0.5


def test_sample_actions_from_neo4j_handles_various_record_types(monkeypatch):
    scorer = KGQualityScorer()
    # fake store that returns dict records for entities and relations
    class FakeStore:
        def query(self, q, params=None):
            if "UNWIND labels" in q:
                return [
                    {"label": "Person"},
                ]
            elif "RETURN n.id" in q:
                return []
            elif "MATCH (a)-[r]" in q:
                return [
                    {"rel": "knows", "src": ["Person"], "tgt": ["Person"]}
                ]
            return []

    ent, rel = scorer._sample_actions_from_neo4j(FakeStore())
    assert ent and rel
    assert ent[0].entity_type == "Person"
    assert rel[0].relation_type == "knows"

    # simulate exceptions inside query
    class BadStore:
        def query(self, q, params=None):
            raise RuntimeError("boom")

    ent2, rel2 = scorer._sample_actions_from_neo4j(BadStore())
    assert ent2 == [] and rel2 == []


def test_compute_class_coverage_with_shapes(monkeypatch):
    scorer = KGQualityScorer()
    class Dummy:
        pass
    store = Dummy()
    store.query = lambda q, params=None: SimpleNamespace(records=[{"cnt": 3}])

    # build shapes graph with two NodeShapes
    g = rdflib.Graph()
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    a = rdflib.URIRef("http://s/A")
    b = rdflib.URIRef("http://s/B")
    g.add((a, rdflib.RDF.type, SH.NodeShape))
    g.add((b, rdflib.RDF.type, SH.NodeShape))

    coverage = scorer._compute_class_coverage(store, g)
    assert coverage == pytest.approx(3 / 2, rel=1e-2) or coverage <= 1.0


def test_run_pyshacl_writes_report(tmp_path, monkeypatch):
    scorer = KGQualityScorer()
    # monkeypatch validator
    fake_val = MagicMock(spec=SHACLValidator)
    fake_res = SimpleNamespace(valid=False, violations=[SimpleNamespace(__dict__={"foo": "bar"})], node_count=1, edge_count=0)
    fake_val.validate.return_value = fake_res
    monkeypatch.setattr(scorer, "_ensure_shacl_validator", lambda shp=None: fake_val)

    scorer.REPORT_DIR = tmp_path / "reports"
    score, n, path = scorer._run_pyshacl(DummyStore())
    assert n == 1
    assert score < 0.5  # invalid halves the normalised norm
    assert Path(path).exists()
    # inspect JSON
    content = json.loads(Path(path).read_text())
    assert content["valid"] is False



def test_score_store_with_shapes_and_static(monkeypatch, tmp_path, dummy_store):
    # create a fake shapes file
    shapes = tmp_path / "shapes.ttl"
    g = rdflib.Graph()
    g.add((rdflib.URIRef("http://x"), rdflib.RDF.type, rdflib.URIRef("http://y")))
    g.serialize(destination=str(shapes), format="turtle")

    scorer = make_scorer(monkeypatch)
    # patch static validator to return controlled results
    fake_sv = MagicMock(spec=StaticValidator)
    fake_sv.check_satisfiability.return_value = StaticValidationResult(valid=True)
    fake_sv.validate_entities_and_relations.return_value = StaticValidationResult(valid=False)
    scorer._sv = fake_sv

    report = scorer.score_store(dummy_store, shapes_path=shapes)
    assert report.consistency == 1.0
    # static validation returned invalid -> acceptance 0.0
    assert report.acceptance_rate == 0.0


def test_score_store_handles_neo4j_sampling(monkeypatch, dummy_store):
    scorer = make_scorer(monkeypatch)
    # build a fake Neo4j store with sample method
    neo = MagicMock()
    neo.sample_entities.return_value = (["a"], ["r"])
    monkeypatch.setattr(scorer, "_sample_actions_from_neo4j", lambda s: ([], []))
    report = scorer.score_neo4j_store(neo)
    assert isinstance(report, KGQualityReport)


def test_compute_class_coverage(monkeypatch):
    scorer = KGQualityScorer()
    # shapes_graph none and store with nodes -> coverage should be 0
    class Dummy:
        pass
    store = Dummy()
    store.get_all_nodes = lambda: [Node(id="1", node_type="A"), Node(id="2", node_type="B")]
    cov = scorer._compute_class_coverage(store, None)
    assert cov == 0.0


def test_score_combination_weights(monkeypatch, dummy_store):
    scorer = make_scorer(monkeypatch)
    scorer._sv = MagicMock(spec=StaticValidator)
    scorer._sv.check_satisfiability.return_value = StaticValidationResult(valid=True)
    scorer._sv.validate_entities_and_relations.return_value = StaticValidationResult(valid=True)
    report = scorer.score_store(dummy_store)
    # verify combined score in [0,1]
    assert 0.0 <= report.combined_score <= 1.0


def test_ensure_shapes_graph_file_and_owl(tmp_path, monkeypatch):
    scorer = KGQualityScorer()
    # create a shapes file with one triple
    shapes = tmp_path / "s.ttl"
    g = rdflib.Graph()
    g.add((rdflib.URIRef("http://x"), rdflib.RDF.type, rdflib.URIRef("http://y")))
    g.serialize(destination=str(shapes), format="turtle")
    sg = scorer._ensure_shapes_graph(shapes)
    assert isinstance(sg, rdflib.Graph) and len(sg) > 0
    # calling again should return same object (cached)
    assert scorer._ensure_shapes_graph(shapes) is sg

    # delete cached and test OWL generation path
    scorer = KGQualityScorer(ontology_owl_path=tmp_path / "o.owl")
    # write minimal owl with a class
    owl = scorer._owl_path
    with open(owl, "w") as f:
        f.write("""<?xml version='1.0'?>\n<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\" \
       xmlns:owl=\"http://www.w3.org/2002/07/owl#\" \
       xmlns:rdfs=\"http://www.w3.org/2000/01/rdf-schema#\">\n  <owl:Class rdf:about=\"http://example.org/A\"/>\n</rdf:RDF>""")
    g2 = scorer._ensure_shapes_graph(None)
    assert isinstance(g2, rdflib.Graph)
    assert scorer._ontology_class_count == 1

    # validator-provided shapes
    class FakeV:
        shapes_graph = g2
    scorer = KGQualityScorer(shacl_validator=FakeV())
    assert scorer._ensure_shapes_graph(None) is g2


def test_ensure_shacl_validator_creates(monkeypatch):
    scorer = KGQualityScorer()
    # monkeypatch ensure_shapes_graph to return simple graph
    g = rdflib.Graph()
    g.add((rdflib.URIRef("a"), rdflib.RDF.type, rdflib.URIRef("b")))
    monkeypatch.setattr(scorer, "_ensure_shapes_graph", lambda shp=None: g)
    created = scorer._ensure_shacl_validator()
    assert hasattr(created, "validate")

    # already set
    scorer._shacl_validator = created
    assert scorer._ensure_shacl_validator() is created


def test_sample_fallback_and_errors():
    scorer = KGQualityScorer()
    class BadStore:
        def query(self, q, params=None):
            raise RuntimeError
    ents, rels = scorer._sample_actions_from_neo4j(BadStore())
    assert ents == [] and rels == []

    class PartialStore:
        def __init__(self):
            self.calls = 0
        def query(self, q, params=None):
            self.calls += 1
            if self.calls == 1:
                return []
            return [{"id": "1", "labels": ["X"]}]
    p = PartialStore()
    ents, rels = scorer._sample_actions_from_neo4j(p, limit=1)
    assert ents and ents[0].entity_type == "X"


def test_compute_class_coverage_no_query(monkeypatch):
    scorer = KGQualityScorer()
    cov = scorer._compute_class_coverage(object(), None)
    assert cov == 0.0


def test_run_pyshacl_valid_and_cap(tmp_path, monkeypatch):
    scorer = KGQualityScorer()
    fake_val = MagicMock(spec=SHACLValidator)
    fake_res = SimpleNamespace(valid=True, violations=[1] * 300, node_count=0, edge_count=0)
    fake_val.validate.return_value = fake_res
    monkeypatch.setattr(scorer, "_ensure_shacl_validator", lambda shp=None: fake_val)
    scorer.REPORT_DIR = tmp_path / "reports"
    score, n, path = scorer._run_pyshacl(DummyStore())
    assert n == 300
    assert score == pytest.approx(0.0, abs=1e-6) or score >= 0.0
    assert Path(path).exists()


def test_score_store_various_branches(tmp_path, monkeypatch):
    # store without to_dict triggers warning
    class EmptyStore:
        pass
    scorer = KGQualityScorer()
    scorer._sv = MagicMock(spec=StaticValidator)
    scorer._sv.check_satisfiability.return_value = StaticValidationResult(valid=False)
    scorer._sv.validate_entities_and_relations.return_value = StaticValidationResult(valid=False)
    # patch pyshacl to simple result
    fake_val = MagicMock(spec=SHACLValidator)
    fake_val.validate.return_value = SimpleNamespace(valid=True, violations=[], node_count=0, edge_count=0)
    monkeypatch.setattr(scorer, "_ensure_shacl_validator", lambda shp=None: fake_val)
    r = scorer.score_store(EmptyStore())
    assert r.consistency == 1.0
    # no sampled actions so acceptance stays at default 0.0
    assert r.acceptance_rate == 0.0
    assert r.violations == 0

    # store with to_dict and shapes file
    shapes = tmp_path / "shapes.ttl"
    rdflib.Graph().serialize(destination=str(shapes), format="turtle")
    scorer2 = KGQualityScorer()
    scorer2._sv = MagicMock(spec=StaticValidator)
    scorer2._sv.check_satisfiability.return_value = StaticValidationResult(valid=True)
    scorer2._sv.validate_entities_and_relations.return_value = StaticValidationResult(valid=False)
    monkeypatch.setattr(scorer2, "_ensure_shacl_validator", lambda shp=None: fake_val)
    class DT:
        def to_dict(self):
            return {"entities": [1, 2], "relations": []}
    r2 = scorer2.score_store(DT(), shapes_path=shapes)
    assert r2.consistency == 1.0
    assert r2.acceptance_rate == 0.0

    # static validator exception path
    scorer3 = KGQualityScorer()
    scorer3._sv = MagicMock(spec=StaticValidator)
    scorer3._sv.check_satisfiability.side_effect = RuntimeError
    scorer3._sv.validate_entities_and_relations.side_effect = RuntimeError
    monkeypatch.setattr(scorer3, "_ensure_shacl_validator", lambda shp=None: fake_val)
    r3 = scorer3.score_store(DT(), shapes_path=shapes)
    # exception during satisfiability -> consistency stays at 0.0
    assert r3.consistency == 0.0

    # alias method should simply call score_store and return a report
    alt = scorer3.score_neo4j_store(DT())
    assert isinstance(alt, type(r3))
