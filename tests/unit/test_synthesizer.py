import pytest

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation, Evidence
from kgbuilder.extraction.synthesizer import FindingsSynthesizer, SynthesizedEntity


def make_entity(id: str, label: str, etype: str, conf: float = 0.5, desc: str = "") -> ExtractedEntity:
    return ExtractedEntity(
        id=id,
        label=label,
        entity_type=etype,
        description=desc,
        confidence=conf,
    )


def test_calculate_similarity_identical():
    s = FindingsSynthesizer()
    e1 = make_entity("e1", "Foo", "T", 0.5)
    e2 = make_entity("e2", "Foo", "T", 0.8)
    assert s._calculate_similarity(e1, e2) == pytest.approx(1.0)


def test_find_duplicates_and_merge():
    s = FindingsSynthesizer(similarity_threshold=0.1)  # aggressive merge
    e1 = make_entity("a", "Bar", "X", 0.2)
    e2 = make_entity("b", "bar", "X", 0.8)
    groups = s._find_duplicates([e1, e2])
    assert len(groups) == 1
    merged = s._merge_group(groups[0])
    assert isinstance(merged, SynthesizedEntity)
    assert merged.merged_count == 2
    # average confidence = 0.5, boost = min(0.05*(2-1),0.1)=0.05 -> 0.55
    assert merged.confidence == pytest.approx(0.55)


def test_synthesize_empty_and_simple():
    s = FindingsSynthesizer()
    assert s.synthesize([]) == []
    # with simple duplicates
    s2 = FindingsSynthesizer(similarity_threshold=0.1)
    e1 = make_entity("x", "One", "A", 0.3)
    e2 = make_entity("y", "one", "A", 0.7)
    result = s2.synthesize([e1, e2])
    assert len(result) == 1
    assert result[0].id in {"x", "y"}


def test_deduplicate_entities():
    s = FindingsSynthesizer(similarity_threshold=0.1)
    e1 = make_entity("1", "Dup", "T", 0.1)
    e2 = make_entity("2", "dup", "T", 0.2)
    mapping = s.deduplicate_entities([e1, e2])
    assert len(mapping) == 1
    canonical = next(iter(mapping))
    assert mapping[canonical] == [e1, e2]


def test_detect_conflicts():
    s = FindingsSynthesizer()
    e1 = make_entity("e", "L", "T", 0.1, desc="a")
    e2 = make_entity("e", "L", "T", 0.2, desc="b")
    conflicts = s.detect_conflicts([e1, e2])
    assert "e" in conflicts
    assert conflicts["e"][0][0] == "description"


def test_consolidate_and_export():
    s = FindingsSynthesizer()
    e = make_entity("e1", "L", "T", 0.5)
    # create a relation pointing from e to unknown other
    r = ExtractedRelation(id="r1", source_entity_id="e1", target_entity_id="e2", predicate="rel", confidence=0.4)
    findings = s.consolidate([e], [r])
    assert "e1" in findings
    yaml = s.export_yaml(findings)
    assert "id: e1" in yaml
    assert "rel" in yaml


def test_export_yaml_attributes():
    # ensure attributes and relations sections formatted correctly
    s = FindingsSynthesizer()
    synth = SynthesizedEntity(id="e", label="L", entity_type="T", confidence=0.1)
    finding = s.consolidate([make_entity("e", "L", "T", 0.1)], [])
    # manually insert attributes to verify export formatting
    finding["e"].attributes = {"foo": ["bar", "baz"]}
    out = s.export_yaml(finding)
    assert "attributes:" in out
    assert "foo" in out
