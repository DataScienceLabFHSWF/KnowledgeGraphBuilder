import re

import pytest

from kgbuilder.core.models import ExtractedEntity, Evidence, ExtractedRelation
from kgbuilder.extraction.rules import (
    RuleBasedExtractor,
    RulePattern,
    RuleBasedRelationExtractor,
)


def test_add_pattern_and_default_patterns():
    rbe = RuleBasedExtractor()
    # default patterns should include Facility etc
    assert "Facility" in rbe.patterns
    old_count = sum(len(v) for v in rbe.patterns.values())
    rbe.add_pattern("Test", "TestType", r"foo", confidence=0.5)
    assert "TestType" in rbe.patterns
    assert any(p.label == "Test" for p in rbe.patterns["TestType"])
    new_count = sum(len(v) for v in rbe.patterns.values())
    assert new_count == old_count + 1


def test_extract_empty_text():
    rbe = RuleBasedExtractor()
    assert rbe.extract("", []) == []
    assert rbe.extract("   ", [type]) == []


def test_extract_pattern_matching():
    rbe = RuleBasedExtractor()
    # add simple pattern
    rbe.add_pattern("foo", "Bar", r"\bfoo\b", confidence=0.6)
    text = "this foo is a foo"
    results = rbe.extract(text, ontology_classes=[type("C", (), {"label": "Bar"})])
    assert len(results) == 1
    ent = results[0]
    assert ent.label.lower() == "foo"
    assert ent.entity_type == "Bar"
    assert ent.confidence == pytest.approx(0.6)
    assert ent.evidence and isinstance(ent.evidence[0], Evidence)


def test_extract_duplicates():
    rbe = RuleBasedExtractor()
    rbe.add_pattern("baz", "BazType", r"\bbaz\b", confidence=1.0)
    text = "baz baz"
    results = rbe.extract(text, ontology_classes=[type("C", (), {"label": "BazType"})])
    # same label/type should de-duplicate
    assert len(results) == 1


def test_extract_filter_by_ontology():
    rbe = RuleBasedExtractor()
    rbe.add_pattern("foo", "FooType", r"foo")
    # provide unrelated ontology class; expect no results
    results = rbe.extract("foo", ontology_classes=[type("C", (), {"label": "Other"})])
    assert results == []


def test_relation_extractor_basic():
    rrel = RuleBasedRelationExtractor()
    # craft two entities with evidence positions such that text between contains " in "
    e1 = ExtractedEntity(
        id="e1", label="A", entity_type="Facility", description="", confidence=0.5,
        evidence=[Evidence(source_type="x", source_id="_0_1", text_span="A", confidence=1.0)],
    )
    # place B at index 5-6 so that between_text = " in "
    e2 = ExtractedEntity(
        id="e2", label="B", entity_type="Location", description="", confidence=0.5,
        evidence=[Evidence(source_type="x", source_id="_5_6", text_span="B", confidence=1.0)],
    )
    text = "A in B"
    relations = rrel.extract(text, [e1, e2])
    assert len(relations) == 1
    rel = relations[0]
    assert rel.predicate == "locatedIn"
    assert rel.source_entity_id == "e1"
    assert rel.target_entity_id == "e2"


def test_relation_extractor_insufficient_entities():
    rrel = RuleBasedRelationExtractor()
    assert rrel.extract("foo", []) == []


def test_relation_extractor_type_constraint():
    rrel = RuleBasedRelationExtractor()
    # pattern locatedIn requires source Facility and target Location
    e1 = ExtractedEntity(
        id="e1", label="A", entity_type="Other", description="", confidence=0.5,
        evidence=[Evidence(source_type="x", source_id="_0_1", text_span="A", confidence=1.0)],
    )
    e2 = ExtractedEntity(
        id="e2", label="B", entity_type="Location", description="", confidence=0.5,
        evidence=[Evidence(source_type="x", source_id="_3_4", text_span="B", confidence=1.0)],
    )
    text = "A in B"
    relations = rrel.extract(text, [e1, e2])
    assert relations == []
