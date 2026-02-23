import pytest
from types import SimpleNamespace

from pydantic import ValidationError

from kgbuilder.extraction.entity import (
    LLMEntityExtractor,
    OntologyClassDef,
)
from kgbuilder.extraction.relation import (
    LLMRelationExtractor,
    OntologyRelationDef,
)
from kgbuilder.extraction.schemas import (
    EntityExtractionOutput,
    EntityItem,
    RelationExtractionOutput,
    RelationItem,
)
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.chains import ExtractionChains


class DummyProvider:
    """Simple LLM provider that returns a sequence of outputs or raises."""

    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = 0
        self.model_name = "dummy"

    def generate_structured(self, prompt, schema):
        if self.calls >= len(self.outputs):
            raise RuntimeError("no more outputs configured")
        out = self.outputs[self.calls]
        self.calls += 1
        if isinstance(out, Exception):
            raise out
        return out


def test_entity_build_prompt_contains_sections():
    extractor = LLMEntityExtractor(llm_provider=DummyProvider([]))
    classes = [OntologyClassDef(uri="u1", label="Type1"), OntologyClassDef(uri="u2", label="Type2")]
    prompt = extractor._build_extraction_prompt("some text", classes)
    assert "VALID ENTITY TYPES" in prompt
    assert "Type1" in prompt and "Type2" in prompt
    assert "TEXT TO ANALYZE" in prompt and "some text" in prompt


def test_entity_extract_basic_behavior():
    # provider returns two entities, one below threshold
    items = [
        EntityItem(id="e1", label="Foo", type="T", confidence=0.9, start_char=0, end_char=3, context=""),
        EntityItem(id="e2", label="Bar", type="T", confidence=0.4, start_char=4, end_char=7, context=""),
    ]
    out = EntityExtractionOutput(entities=items)
    provider = DummyProvider([out])
    extractor = LLMEntityExtractor(llm_provider=provider, confidence_threshold=0.5)
    classes = [OntologyClassDef(uri="u", label="T")]
    result = extractor.extract("Foo Bar", ontology_classes=classes)
    assert len(result) == 1
    assert result[0].label == "Foo"


def test_entity_extract_retries_and_failure():
    good_out = EntityExtractionOutput(entities=[EntityItem(id="e", label="X", type="T", confidence=0.8, start_char=0, end_char=1, context="")])
    # first two attempts raise generic error (caught same as ValidationError), third returns good output
    validation_exc = Exception("boom")
    provider = DummyProvider([validation_exc, validation_exc, good_out])
    extractor = LLMEntityExtractor(llm_provider=provider, max_retries=3)
    classes = [OntologyClassDef(uri="u", label="T")]
    result = extractor.extract("X", ontology_classes=classes)
    assert result and result[0].label == "X"

    # now failure after max retries
    provider2 = DummyProvider([validation_exc, validation_exc, validation_exc])
    extractor2 = LLMEntityExtractor(llm_provider=provider2, max_retries=2)
    with pytest.raises(RuntimeError):
        extractor2.extract("X", ontology_classes=classes)


def test_entity_extract_edge_cases():
    provider = DummyProvider([EntityExtractionOutput(entities=[])])
    extractor = LLMEntityExtractor(llm_provider=provider)
    classes = [OntologyClassDef(uri="u", label="T")]
    assert extractor.extract("", ontology_classes=classes) == []
    assert extractor.extract("text", ontology_classes=[]) == []


@ pytest.fixture(autouse=True)
def patch_relation_chain(monkeypatch):
    # patch extraction chain so we can control output
    def fake_chain(model, base_url, temperature=0.5):
        return SimpleNamespace(invoke=lambda kwargs: fake_chain.output)
    monkeypatch.setattr(ExtractionChains, "create_relation_extraction_chain", fake_chain)
    yield


def make_rel_item(src, tgt, type_, conf=0.9):
    return RelationItem(
        id="r",
        source_id=src,
        source_label="",
        relation_type=type_,
        target_id=tgt,
        target_label="",
        confidence=conf,
    )


def test_relation_extract_basic_and_constraints():
    # prepare input entities
    src_ent = ExtractedEntity(id="s", label="S", entity_type="Type1", description="", confidence=1.0)
    tgt_ent = ExtractedEntity(id="t", label="T", entity_type="Type2", description="", confidence=1.0)
    ontology = [OntologyRelationDef(uri="rel", label="R", domain=["Type1"], range=["Type2"], is_functional=True)]

    # good result
    rel_output = RelationExtractionOutput(relations=[make_rel_item("s","t","rel")])
    ExtractionChains.create_relation_extraction_chain.output = rel_output

    rel_ex = LLMRelationExtractor(llm_provider=DummyProvider([]))
    results = rel_ex.extract("text", [src_ent, tgt_ent], ontology)
    assert len(results) == 1
    assert results[0].source_entity_id == "s"

    # low confidence should be filtered
    rel_output_low = RelationExtractionOutput(relations=[make_rel_item("s","t","rel", conf=0.1)])
    ExtractionChains.create_relation_extraction_chain.output = rel_output_low
    assert rel_ex.extract("text", [src_ent, tgt_ent], ontology) == []

    # domain mismatch should be filtered
    bad_onto = [OntologyRelationDef(uri="rel", label="R", domain=["Other"], range=["Type2"])]
    ExtractionChains.create_relation_extraction_chain.output = rel_output
    assert rel_ex.extract("text", [src_ent, tgt_ent], bad_onto) == []

    # relation with missing entity ids should be dropped
    rel_missing = RelationExtractionOutput(relations=[make_rel_item("x","y","rel")])
    ExtractionChains.create_relation_extraction_chain.output = rel_missing
    assert rel_ex.extract("text", [src_ent, tgt_ent], ontology) == []


def test_relation_extract_no_inputs():
    rel_ex = LLMRelationExtractor(llm_provider=DummyProvider([]))
    assert rel_ex.extract("", [], []) == []
    assert rel_ex.extract("foo", [], [OntologyRelationDef(uri="r", label="R")]) == []
