import pytest

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.relation import (
    LLMRelationExtractor,
    OntologyRelationDef,
)


def make_entity(id_, typ):
    return ExtractedEntity(id=id_, label=id_, entity_type=typ, description="", confidence=1.0)


def test_format_entities_for_prompt():
    ent = make_entity("e1", "TypeA")
    formatted = LLMRelationExtractor._format_entities_for_prompt([ent])
    assert "e1" in formatted and "TypeA" in formatted


def test_find_entity_by_id():
    e1 = make_entity("foo", "T")
    e2 = make_entity("bar", "T")
    assert LLMRelationExtractor._find_entity_by_id("foo", [e1, e2]) is e1
    assert LLMRelationExtractor._find_entity_by_id("missing", [e1, e2]) is None


def test_validate_domain_range():
    e1 = make_entity("e1", "A")
    e2 = make_entity("e2", "B")
    # no ontology def -> always valid
    assert LLMRelationExtractor._validate_domain_range(e1, e2, None)
    # domain mismatch fails
    onto = OntologyRelationDef(uri="u", label="R", domain=["X"], range=["B"])
    assert not LLMRelationExtractor._validate_domain_range(e1, e2, onto)
    # with correct types passes
    onto2 = OntologyRelationDef(uri="u", label="R", domain=["A"], range=["B"])
    assert LLMRelationExtractor._validate_domain_range(e1, e2, onto2)


def test_check_cardinality_constraints():
    # functional constraint keeps only highest-confidence relation between same source
    r1 = ExtractedRelation(id="r1", source_entity_id="s", target_entity_id="t1", predicate="p", confidence=0.3)
    r2 = ExtractedRelation(id="r2", source_entity_id="s", target_entity_id="t2", predicate="p", confidence=0.8)
    ont = {"p": OntologyRelationDef(uri="u", label="P", is_functional=True)}
    filtered = LLMRelationExtractor._check_cardinality_constraints([r1, r2], ont)
    assert len(filtered) == 1 and filtered[0] is r2

    # inverse functional constraint
    r3 = ExtractedRelation(id="r3", source_entity_id="s1", target_entity_id="t", predicate="q", confidence=0.4)
    r4 = ExtractedRelation(id="r4", source_entity_id="s2", target_entity_id="t", predicate="q", confidence=0.6)
    ont2 = {"q": OntologyRelationDef(uri="u", label="Q", is_inverse_functional=True)}
    filtered2 = LLMRelationExtractor._check_cardinality_constraints([r3, r4], ont2)
    assert len(filtered2) == 1 and filtered2[0] is r4

    # no constraints -> all kept
    r5 = ExtractedRelation(id="r5", source_entity_id="s", target_entity_id="t", predicate="r", confidence=1.0)
    assert LLMRelationExtractor._check_cardinality_constraints([r5], {}) == [r5]
