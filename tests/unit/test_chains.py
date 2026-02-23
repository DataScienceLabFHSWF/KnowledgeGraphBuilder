import pytest

from kgbuilder.core.models import ExtractedEntity
from kgbuilder.extraction.chains import ExtractionChains
from kgbuilder.extraction.entity import OntologyClassDef
from kgbuilder.extraction.relation import OntologyRelationDef


class DummyRunnable:
    def __init__(self, result):
        self.result = result
    def invoke(self, inp):
        return self.result


@pytest.mark.parametrize("expr,expected", [
    ('"end_char": 10 + 5,', '"end_char": 15,'),
    ('"id": 1 + 2 + 3}', '"id": 6}'),
    ('{"foo": 4-1}', '{"foo": 3}'),
    ('no change here', 'no change here'),
])
def test_fix_json_arithmetic(expr, expected):
    fixed = ExtractionChains._fix_json_arithmetic(expr)
    assert fixed == expected


def test_safe_parse_valid(monkeypatch):
    class FakeParser:
        def parse(self, text):
            return text.upper()
    # include trailing comma to satisfy regex suffix requirement
    fake = type("X", (), {"content": '"a": 1+1,'})
    result = ExtractionChains._safe_parse(FakeParser(), fake)
    # should have fixed arithmetic and uppercased  (no surrounding braces)
    assert result == '"A": 2,'  # number computed and letters uppercased



def test_safe_parse_errors(monkeypatch):
    class FakeParser:
        def parse(self, text):
            raise ValueError("bad")
    fake = type("X", (), {"content": 'dummy'})
    result = ExtractionChains._safe_parse(FakeParser(), fake)
    # on failure returns EntityExtractionOutput instance
    from kgbuilder.extraction.schemas import EntityExtractionOutput
    assert isinstance(result, EntityExtractionOutput)
    assert result.entities == []


def test_format_entities_and_relations_sections():
    ent = ExtractedEntity(id="e1", label="Foo", entity_type="T", description="", confidence=0.9)
    formatted = ExtractionChains.format_entities_list([ent])
    assert "e1" in formatted and "Foo" in formatted

    rel = OntologyRelationDef(uri="u", label="R", domain=["T1"], range=["T2"], is_functional=True)
    formatted_rel = ExtractionChains.format_relations_section([rel])
    assert "R" in formatted_rel and "Domain" in formatted_rel


def test_build_extraction_pipeline_returns_runnables(monkeypatch):
    # patch ChatOllama with fake LLM object that returns a .content attribute
    class FakeLLM:
        def __init__(self, *_args, **_kwargs):
            pass
        def __call__(self, inp):
            return type("R", (), {"content": "{\"entities\": []}"})
    monkeypatch.setattr("kgbuilder.extraction.chains.ChatOllama", FakeLLM)
    from kgbuilder.extraction.chains import build_extraction_pipeline

    entity_chain, relation_chain = build_extraction_pipeline()
    # both should be callable/runable
    assert hasattr(entity_chain, "invoke")
    assert hasattr(relation_chain, "invoke")

    # invoking the entity chain should return an EntityExtractionOutput object
    res = entity_chain.invoke({"text": "x", "ontology_section": "", "format_instructions": ""})
    from kgbuilder.extraction.schemas import EntityExtractionOutput
    assert isinstance(res, EntityExtractionOutput)
