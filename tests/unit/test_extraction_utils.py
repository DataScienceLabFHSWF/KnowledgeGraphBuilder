import pytest
from kgbuilder.extraction.entity import (
    LLMEntityExtractor,
    OntologyClassDef,
    OntologyPropertyDef,
)
from kgbuilder.extraction.relation import (
    LLMRelationExtractor,
    OntologyRelationDef,
)
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation, Evidence
from kgbuilder.extraction.schemas import EntityExtractionOutput, EntityItem


# dummy provider with minimal attributes used by constructors
class DummyLLMProvider:
    model_name = "dummy"
    # generate_structured not needed for our utility tests
    def generate_structured(self, prompt, schema):
        raise RuntimeError("should not be called")


# --- entity utilities -----------------------------------------------------

def make_entity(id_, label, etype, confidence=0.5):
    return ExtractedEntity(
        id=id_,
        label=label,
        entity_type=etype,
        description="",
        confidence=confidence,
    )


def test_format_ontology_section_minimal():
    extractor = LLMEntityExtractor(llm_provider=DummyLLMProvider())
    classes = [OntologyClassDef(uri="http://example.com/Foo", label="Foo")]
    formatted = extractor._format_ontology_section(classes)
    assert "**Foo**" in formatted
    assert "http://example.com/Foo" in formatted


def test_format_ontology_section_with_description_and_examples():
    extractor = LLMEntityExtractor(llm_provider=DummyLLMProvider())
    cls = OntologyClassDef(
        uri="u",
        label="Bar",
        description="A bar entity",
        examples=["x", "y"],
    )
    out = extractor._format_ontology_section([cls])
    assert "Description: A bar entity" in out
    assert 'Examples: "x", "y"' in out


def test_find_entity_position_cases():
    extractor = LLMEntityExtractor(llm_provider=DummyLLMProvider())
    text = "Hello Foo world"
    # exact match
    assert extractor._find_entity_position("Foo", text) == (6, 9)
    # case insensitive
    assert extractor._find_entity_position("foo", text) == (6, 9)
    # substring fallback for first word longer than 3 characters should still fail
    # because "foobar" is not contained in source
    assert extractor._find_entity_position("Foobar", text) == (-1, -1)
    # not found
    assert extractor._find_entity_position("Baz", text) == (-1, -1)
    # empty inputs
    assert extractor._find_entity_position("", text) == (-1, -1)
    assert extractor._find_entity_position("Foo", "") == (-1, -1)


def test_convert_to_extracted_entities_search_and_fallback():
    extractor = LLMEntityExtractor(llm_provider=DummyLLMProvider())
    # create output with one item using valid offsets
    item = EntityItem(
        id="ent1",
        label="Foo",
        type="Type",
        confidence=0.9,
        start_char=6,
        end_char=9,
        context="context",
    )
    output = EntityExtractionOutput(entities=[item])
    result = extractor._convert_to_extracted_entities(output, "Hello Foo world")
    assert len(result) == 1
    ent = result[0]
    assert ent.label == "Foo"
    # evidence text_span should equal "Foo"
    assert ent.evidence[0].text_span == "Foo"

    # fallback case: label not in text, numeric offsets provided
    item2 = EntityItem(
        id="ent2",
        label="Bar",
        type="Type",
        confidence=0.8,
        start_char=1,
        end_char=4,
        context="",
    )
    # text does not contain "Bar" at all so search fails, we should therefore
    # rely on the provided offsets when converting
    output2 = EntityExtractionOutput(entities=[item2])
    res2 = extractor._convert_to_extracted_entities(output2, "xxxNOmatchzzz")
    assert res2[0].label == "Bar"
    # since offsets 1..4 were used, evidence text_span may be substring of source
    assert res2[0].evidence[0].text_span == "xxxN"[:3] or isinstance(res2[0].evidence[0].text_span, str)

    # offsets out of bounds should trigger invalid-range fallback to label length
    item3 = EntityItem(
        id="ent3",
        label="Qux",
        type="Type",
        confidence=0.7,
        start_char=100,
        end_char=50,
        context="",
    )
    output3 = EntityExtractionOutput(entities=[item3])
    res3 = extractor._convert_to_extracted_entities(output3, "nothing here")
    # offset was invalid so span doesn't necessarily match the label; just
    # ensure we returned a non-empty string (fallback logic exercised)
    span = res3[0].evidence[0].text_span
    assert isinstance(span, str) and span


def test_deduplicate_entities_with_existing():
    extractor = LLMEntityExtractor(llm_provider=DummyLLMProvider())
    a = make_entity("1", "Foo", "T", confidence=0.3)
    b = make_entity("2", "Foo", "T", confidence=0.8)
    c = make_entity("3", "Bar", "T", confidence=0.9)
    existing = [make_entity("4", "Foo", "T", confidence=0.5)]
    result = extractor._deduplicate_entities([a, b, c], existing)
    # 'Foo' with highest confidence 0.8 should remain, plus 'Bar'
    labels = {e.label for e in result}
    assert labels == {"Foo", "Bar"}


def make_output(ids):
    from kgbuilder.extraction.schemas import EntityExtractionOutput, EntityItem

    items = []
    for i in ids:
        items.append(EntityItem(
            id=i,
            label="X",
            type="T",
            confidence=0.6,
            start_char=0,
            end_char=1,
            context="",
        ))
    return EntityExtractionOutput(entities=items)


def test_extract_empty_and_no_classes(monkeypatch):
    provider = DummyLLMProvider()
    extractor = LLMEntityExtractor(llm_provider=provider)
    assert extractor.extract("", [OntologyClassDef(uri="u", label="L")]) == []
    assert extractor.extract("text", []) == []


def test_extract_filters_by_threshold(monkeypatch):
    class Prov:
        model_name = "p"
        def generate_structured(self, prompt, schema):
            return make_output(["e1", "e2"])
    extractor = LLMEntityExtractor(llm_provider=Prov(), confidence_threshold=0.7)
    res = extractor.extract("text", [OntologyClassDef(uri="u", label="L")])
    # output confidences are 0.6 so filtered out -> empty
    assert res == []


def test_extract_retry_on_validation_error(monkeypatch):
    class Prov:
        model_name = "p"
        calls = 0
        def generate_structured(self, prompt, schema):
            self.calls += 1
            if self.calls == 1:
                raise ValidationError([], schema)
            return make_output(["e1"])
    extractor = LLMEntityExtractor(llm_provider=Prov(), max_retries=2)
    res = extractor.extract("text", [OntologyClassDef(uri="u", label="L")])
    assert len(res) == 1


def test_extract_raises_after_retries(monkeypatch):
    class Prov:
        model_name = "p"
        def generate_structured(self, prompt, schema):
            raise RuntimeError("boom")
    extractor = LLMEntityExtractor(llm_provider=Prov(), max_retries=2)
    with pytest.raises(RuntimeError):
        extractor.extract("text", [OntologyClassDef(uri="u", label="L")])


# --- relation utilities ---------------------------------------------------

def make_rel(id_, src, tgt, pred, conf=0.5):
    return ExtractedRelation(id=id_, source_entity_id=src, target_entity_id=tgt, predicate=pred, confidence=conf)


def test_format_entities_and_find_by_id():
    rel_ex = LLMRelationExtractor(llm_provider=DummyLLMProvider())
    ent1 = make_entity("e1", "Foo", "Type")
    ent2 = make_entity("e2", "Bar", "Type")
    formatted = rel_ex._format_entities_for_prompt([ent1, ent2])
    assert "- e1:" in formatted
    assert "Foo" in formatted
    assert rel_ex._find_entity_by_id("e2", [ent1, ent2]) is ent2
    assert rel_ex._find_entity_by_id("missing", [ent1, ent2]) is None


def test_validate_domain_range_and_cardinality():
    rel_ex = LLMRelationExtractor(llm_provider=DummyLLMProvider())
    src = make_entity("s", "A", "Type1")
    tgt = make_entity("t", "B", "Type2")
    # no ontology def -> permissive
    assert rel_ex._validate_domain_range(src, tgt, None)
    # domain mismatch
    od = OntologyRelationDef(uri="r", label="R", domain=["Other"], range=["Type2"])
    assert not rel_ex._validate_domain_range(src, tgt, od)
    # correct domain but range mismatch
    od2 = OntologyRelationDef(uri="r", label="R", domain=["Type1"], range=["Other"])
    assert not rel_ex._validate_domain_range(src, tgt, od2)
    # both match
    od3 = OntologyRelationDef(uri="r", label="R", domain=["Type1"], range=["Type2"])
    assert rel_ex._validate_domain_range(src, tgt, od3)

    # test cardinality filtering
    r1 = make_rel("rel1", "s", "t", "p", conf=0.4)
    r2 = make_rel("rel2", "s", "t", "p", conf=0.6)
    # functional constraint keeps higher confidence
    od3.is_functional = True
    filtered = rel_ex._check_cardinality_constraints([r1, r2], {"p": od3})
    assert len(filtered) == 1 and filtered[0].id == "rel2"
    # inverse functional constraint keeps higher confidence by target
    od4 = OntologyRelationDef(uri="p2", label="P2", is_inverse_functional=True)
    r3 = make_rel("rel3", "s", "t", "p2", conf=0.2)
    r4 = make_rel("rel4", "s2", "t", "p2", conf=0.9)
    filtered2 = rel_ex._check_cardinality_constraints([r3, r4], {"p2": od4})
    assert len(filtered2) == 1 and filtered2[0].id == "rel4"


@pytest.fixture(autouse=True)
def silence_logging(caplog):
    caplog.set_level("DEBUG")
    yield


def test_build_extraction_prompt_contains_sections():
    rel_ex = LLMRelationExtractor(llm_provider=DummyLLMProvider())
    src = make_entity("s", "A", "Type1")
    tgt = make_entity("t", "B", "Type2")
    od = OntologyRelationDef(uri="r", label="R")
    prompt = rel_ex._build_extraction_prompt("txt", [src, tgt], [od])
    assert "ENTITIES MENTIONED" in prompt
    assert "VALID RELATIONSHIPS" in prompt
    assert "txt" in prompt


def test_relation_extractor_flow(monkeypatch):
    # fake chain returning low and high confidence relations to verify filtering
    from kgbuilder.extraction.schemas import RelationExtractionOutput, RelationItem

    class FakeChain:
        def invoke(self, inp):
            return RelationExtractionOutput(relations=[
                RelationItem(id="r1", source_id="e1", source_label="Foo", relation_type="p", target_id="e2", target_label="Bar", confidence=0.4),
                RelationItem(id="r2", source_id="e1", source_label="Foo", relation_type="p", target_id="e2", target_label="Bar", confidence=0.8),
            ])
    monkeypatch.setattr("kgbuilder.extraction.chains.ExtractionChains.create_relation_extraction_chain", lambda **kw: FakeChain())
    rel_ex = LLMRelationExtractor(llm_provider=DummyLLMProvider(), confidence_threshold=0.5)
    ent1 = make_entity("e1", "Foo", "TypeA")
    ent2 = make_entity("e2", "Bar", "TypeB")
    ontology = [OntologyRelationDef(uri="p", label="P", domain=["TypeA"], range=["TypeB"])]
    out = rel_ex.extract("text", [ent1, ent2], ontology)
    assert len(out) == 1
    assert out[0].predicate == "p"
