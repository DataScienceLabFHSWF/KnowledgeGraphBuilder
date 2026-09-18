"""Tests for the provenance/rationale log (SEMANTiCS 2026 plan, Phase A)."""

from __future__ import annotations

from kgbuilder.core.models import ExtractedEntity, RationaleEntry
from kgbuilder.provenance.rationale_log import RationaleLog


def _make_entity(entity_id: str = "ent-1") -> ExtractedEntity:
    return ExtractedEntity(
        id=entity_id, label="Reactor A", entity_type="Facility", description="", confidence=0.9,
    )


def test_record_appends_to_both_log_and_subject_rationale() -> None:
    log = RationaleLog()
    entity = _make_entity()

    entry = log.record(
        entity, agent="module_extraction_agent:Assets", action="extracted",
        reason="matched Facility class", triggered_by="q1",
    )

    assert isinstance(entry, RationaleEntry)
    assert entity.rationale == [entry]
    assert log.entries_for("ent-1") == [entry]
    assert len(log) == 1


def test_record_for_id_does_not_require_a_rationale_carrier() -> None:
    log = RationaleLog()

    entry = log.record_for_id(
        "q-vcq", agent="validation_agent", action="validated",
        reason="VCQ validation result: {'valid': True}", triggered_by="q-vcq",
    )

    assert log.entries_for("q-vcq") == [entry]


def test_export_jsonld_shapes_entries_with_prov_vaem_dc_terms() -> None:
    log = RationaleLog()
    entity = _make_entity()
    log.record(entity, agent="agent-1", action="extracted", reason="reason-1", triggered_by="cq-1")

    doc = log.export_jsonld(base_uri="http://example.org/kg/")

    assert doc["@context"]["prov"] == "http://www.w3.org/ns/prov#"
    assert doc["@context"]["vaem"] == "http://www.linkedmodel.org/schema/vaem#"
    assert doc["@context"]["dc"] == "http://purl.org/dc/terms/"
    node = doc["@graph"][0]
    assert node["@id"] == "http://example.org/kg/ent-1"
    record = node["vaem:rationale"][0]
    assert record["prov:wasGeneratedBy"] == "agent-1"
    assert record["dc:source"] == "cq-1"
    assert record["vaem:rationale"] == "reason-1"
    assert record["action"] == "extracted"
