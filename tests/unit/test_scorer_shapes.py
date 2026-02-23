import sys
from pathlib import Path

# ensure package import works
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import rdflib
import pytest

from kgbuilder.validation.scorer import KGQualityScorer
from kgbuilder.validation.shacl_validator import SHACLValidator


def test_ensure_shapes_graph_reads_existing_file(tmp_path: Path) -> None:
    # create a trivial shapes graph and serialize it
    g = rdflib.Graph()
    g.add((rdflib.URIRef("http://ex/A"), rdflib.RDF.type, rdflib.URIRef("http://ex/B")))
    shapes_file = tmp_path / "shapes.ttl"
    g.serialize(destination=str(shapes_file), format="turtle")

    scorer = KGQualityScorer()  # no ontology needed for this path
    loaded = scorer._ensure_shapes_graph(shapes_path=shapes_file)
    assert isinstance(loaded, rdflib.Graph)
    assert len(loaded) >= 1
    # shapes_file should have been recorded
    assert scorer._shapes_file == shapes_file


def test_ensure_shapes_graph_generates_from_owl(tmp_path: Path, monkeypatch) -> None:
    owl = tmp_path / "ont.owl"
    owl.write_text(
        """<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" \
            xmlns:owl="http://www.w3.org/2002/07/owl#">\n"
        "  <owl:Class rdf:about="http://example.org/C"/>\n"
        "</rdf:RDF>"""
    )
    # redirect report directory to temp so test is isolated
    monkeypatch.setattr(KGQualityScorer, "REPORT_DIR", tmp_path / "reports")

    scorer = KGQualityScorer(ontology_owl_path=owl)
    generated = scorer._ensure_shapes_graph()
    assert isinstance(generated, rdflib.Graph)
    assert len(generated) > 0
    # persisted shapes file exists
    out_file = tmp_path / "reports" / "shapes.ttl"
    assert out_file.exists()
    # ontology class count recorded
    assert scorer._ontology_class_count == 1
    assert scorer._shapes_file == out_file


def test_ensure_shapes_graph_no_source_returns_none() -> None:
    scorer = KGQualityScorer()
    result = scorer._ensure_shapes_graph(shapes_path=Path("nonexistent"))
    assert result is None


def test_ensure_shacl_validator_injected(monkeypatch, tmp_path: Path) -> None:
    # a shapes graph with something
    g = rdflib.Graph()
    g.add((rdflib.URIRef("http://x"), rdflib.RDF.type, rdflib.URIRef("http://y")))
    validator = SHACLValidator(g)
    scorer = KGQualityScorer(shacl_validator=validator)
    returned = scorer._ensure_shacl_validator()
    assert returned is validator


def test_ensure_shacl_validator_created_from_shapes(tmp_path: Path, monkeypatch) -> None:
    owl = tmp_path / "o.owl"
    owl.write_text(
        """<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" \
            xmlns:owl="http://www.w3.org/2002/07/owl#">\n"
        "  <owl:Class rdf:about="http://example.org/D"/>\n"
        "</rdf:RDF>"""
    )
    monkeypatch.setattr(KGQualityScorer, "REPORT_DIR", tmp_path / "reports")
    scorer = KGQualityScorer(ontology_owl_path=owl)
    val = scorer._ensure_shacl_validator()
    assert isinstance(val, SHACLValidator)
    # shapes graph should have some triples
    assert scorer._shapes_graph is not None and len(scorer._shapes_graph) > 0
