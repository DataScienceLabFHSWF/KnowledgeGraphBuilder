import sys
from pathlib import Path

# ensure package import works
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import pytest
import rdflib

from kgbuilder.validation.scorer import (
    _FileOntologyService,
    KGQualityReport,
    W_CONSISTENCY,
    W_ACCEPTANCE,
    W_COVERAGE,
    W_SHACL,
)


def test_weight_constants_sum_to_one() -> None:
    total = W_CONSISTENCY + W_ACCEPTANCE + W_COVERAGE + W_SHACL
    assert pytest.approx(total, rel=1e-9) == 1.0


def test_quality_report_dataclass() -> None:
    report = KGQualityReport(
        consistency=0.5,
        violations=3,
        acceptance_rate=0.8,
        class_coverage=0.75,
        shacl_score=0.9,
        combined_score=0.85,
        details={"foo": "bar"},
        shacl_report_path="/tmp/foo.json",
    )
    d = report.__dict__
    assert d["consistency"] == 0.5
    assert d["violations"] == 3
    assert d["details"]["foo"] == "bar"
    # repr should contain class name
    assert "KGQualityReport" in repr(report)


def test_file_ontology_service_parses_classes(tmp_path: Path) -> None:
    owl_text = """<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"
         xmlns:owl=\"http://www.w3.org/2002/07/owl#\"
         xmlns:rdfs=\"http://www.w3.org/2000/01/rdf-schema#\">
    <owl:Class rdf:about=\"http://example.org/A\"/>
    <owl:Class rdf:about=\"http://example.org/B\">
        <rdfs:subClassOf rdf:resource=\"http://example.org/A\"/>
    </owl:Class>
</rdf:RDF>"""
    path = tmp_path / "test.owl"
    path.write_text(owl_text)

    svc = _FileOntologyService(path)
    classes = svc.get_all_classes()
    # Expect two classes A and B
    labels = {c["label"] for c in classes}
    assert labels == {"A", "B"}
    # verify parent relationship recorded
    b_entry = next(c for c in classes if c["label"] == "B")
    assert b_entry["parent_uri"].endswith("A")
    # other methods return empty lists by design
    assert svc.get_class_properties("A") == []
    assert svc.get_special_properties() == []


def test_file_ontology_service_handles_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.owl"
    path.write_text("")
    # rdflib will raise a parse error on empty file; ensure it surfaces
    with pytest.raises(Exception):
        _FileOntologyService(path)

