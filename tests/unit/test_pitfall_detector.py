"""Tests for OOPS! ontology pitfall detection (SEMANTiCS 2026 Phase C)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from kgbuilder.validation.pitfall_detector import OOPSPitfallDetector, PitfallScanResult

_SUCCESS_RESPONSE = """<?xml version="1.0"?>
<rdf:RDF
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:oops="http://oops.linkeddata.es/def#">
  <rdf:Description rdf:about="http://oops.linkeddata.es/data/pitfall1">
    <oops:hasCode rdf:datatype="http://www.w3.org/2001/XMLSchema#string">P10</oops:hasCode>
    <oops:hasName rdf:datatype="http://www.w3.org/2001/XMLSchema#string">
Missing disjointness</oops:hasName>
    <oops:hasDescription rdf:datatype="http://www.w3.org/2001/XMLSchema#string">desc</oops:hasDescription>
    <oops:hasImportanceLevel rdf:datatype="http://www.w3.org/2001/XMLSchema#string">Important</oops:hasImportanceLevel>
    <rdf:type rdf:resource="http://oops.linkeddata.es/def#pitfall"/>
  </rdf:Description>
  <rdf:Description rdf:about="http://oops.linkeddata.es/data/resp1">
    <oops:hasPitfall rdf:resource="http://oops.linkeddata.es/data/pitfall1"/>
    <rdf:type rdf:resource="http://oops.linkeddata.es/def#response"/>
  </rdf:Description>
</rdf:RDF>
"""

_ERROR_RESPONSE = """<?xml version="1.0"?>
<rdf:RDF
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:oops="http://oops.linkeddata.es/def#">
  <rdf:Description rdf:about="http://www.oeg-upm.net/oops/unexpected_error">
    <oops:hasTitle rdf:datatype="http://www.w3.org/2001/XMLSchema#string">
OOPS! something went wrong.</oops:hasTitle>
    <rdf:type rdf:resource="http://oops.linkeddata.es/def#response"/>
  </rdf:Description>
</rdf:RDF>
"""

_MINIMAL_OWL = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
         xmlns:owl="http://www.w3.org/2002/07/owl#">
  <owl:Class rdf:about="http://ex.org/Annotated">
    <rdfs:label>Annotated</rdfs:label>
  </owl:Class>
  <owl:Class rdf:about="http://ex.org/Bare"/>
  <owl:ObjectProperty rdf:about="http://ex.org/hasFullSpec">
    <rdfs:domain rdf:resource="http://ex.org/Annotated"/>
    <rdfs:range rdf:resource="http://ex.org/Bare"/>
  </owl:ObjectProperty>
  <owl:ObjectProperty rdf:about="http://ex.org/hasNoDomainOrRange"/>
</rdf:RDF>
"""


def _client_returning(status_code: int, text: str) -> MagicMock:
    response = MagicMock(status_code=status_code, text=text)
    client = MagicMock()
    client.post.return_value = response
    return client


class TestOOPSApiPath:
    def test_scan_parses_real_pitfall_response(self, tmp_path: Path) -> None:
        onto_path = tmp_path / "onto.owl"
        onto_path.write_text(_MINIMAL_OWL)
        client = _client_returning(200, _SUCCESS_RESPONSE)

        result = OOPSPitfallDetector(http_client=client).scan(onto_path)

        assert result.source == "oops_api"
        assert result.error is None
        assert len(result.pitfalls) == 1
        assert result.pitfalls[0].code == "P10"
        assert result.pitfalls[0].importance == "Important"

    def test_scan_falls_back_when_oops_reports_internal_error(self, tmp_path: Path) -> None:
        onto_path = tmp_path / "onto.owl"
        onto_path.write_text(_MINIMAL_OWL)
        client = _client_returning(200, _ERROR_RESPONSE)

        result = OOPSPitfallDetector(http_client=client).scan(onto_path)

        assert result.source == "local_fallback"
        assert result.error is not None
        assert "went wrong" in result.error

    def test_scan_falls_back_on_non_200_status(self, tmp_path: Path) -> None:
        onto_path = tmp_path / "onto.owl"
        onto_path.write_text(_MINIMAL_OWL)
        client = _client_returning(500, "internal server error")

        result = OOPSPitfallDetector(http_client=client).scan(onto_path)

        assert result.source == "local_fallback"
        assert "500" in result.error

    def test_scan_reports_error_for_missing_file(self, tmp_path: Path) -> None:
        result = OOPSPitfallDetector(http_client=MagicMock()).scan(tmp_path / "nope.owl")

        assert result.source == "local_fallback"
        assert result.error is not None


class TestLocalFallbackScan:
    def test_local_fallback_detects_missing_annotations_and_domain_range(
        self, tmp_path: Path,
    ) -> None:
        onto_path = tmp_path / "onto.owl"
        onto_path.write_text(_MINIMAL_OWL)

        result = OOPSPitfallDetector()._scan_local(onto_path)

        by_code = {p.code: p for p in result.pitfalls}
        assert "P08" in by_code
        assert "http://ex.org/Bare" in by_code["P08"].affected_elements
        assert "http://ex.org/Annotated" not in by_code["P08"].affected_elements
        assert "P11" in by_code
        assert "http://ex.org/hasNoDomainOrRange" in by_code["P11"].affected_elements
        assert "http://ex.org/hasFullSpec" not in by_code["P11"].affected_elements

    def test_local_fallback_reports_no_pitfalls_for_well_formed_ontology(
        self, tmp_path: Path,
    ) -> None:
        well_formed = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
         xmlns:owl="http://www.w3.org/2002/07/owl#">
  <owl:Class rdf:about="http://ex.org/A"><rdfs:label>A</rdfs:label></owl:Class>
  <owl:ObjectProperty rdf:about="http://ex.org/rel">
    <rdfs:domain rdf:resource="http://ex.org/A"/>
    <rdfs:range rdf:resource="http://ex.org/A"/>
  </owl:ObjectProperty>
</rdf:RDF>
"""
        onto_path = tmp_path / "onto.owl"
        onto_path.write_text(well_formed)

        result = OOPSPitfallDetector()._scan_local(onto_path)

        assert result.pitfalls == []


class TestPitfallScanResultAndPitfall:
    def test_critical_count_and_to_dict(self) -> None:
        from kgbuilder.validation.pitfall_detector import Pitfall

        result = PitfallScanResult(
            pitfalls=[
                Pitfall(
                    code="P01", name="n", description="d", importance="Critical",
                    affected_elements=["a"],
                ),
                Pitfall(
                    code="P02", name="n2", description="d2", importance="Minor",
                    affected_elements=[],
                ),
            ],
            source="oops_api",
        )

        assert result.critical_count == 1
        as_dict = result.to_dict()
        assert as_dict["total_count"] == 2
        assert as_dict["critical_count"] == 1
        assert as_dict["pitfalls"][0]["num_affected_elements"] == 1
