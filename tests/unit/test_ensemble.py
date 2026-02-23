import pytest

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.ensemble import (
    TieredExtractor,
    TieredRelationExtractor,
    EnsembleExtractor,
)


class DummyRuleExtractor:
    def __init__(self, results):
        self._results = results
        self.called = False

    def extract(self, text, ontology_classes=None, existing_entities=None):
        self.called = True
        return self._results


class DummyLLMExtractor(DummyRuleExtractor):
    pass


class FailingExtractor:
    def extract(self, *args, **kwargs):
        raise RuntimeError("boom")


@pytest.fixture

def sample_entity():
    return ExtractedEntity(
        id="e1",
        label="Foo",
        entity_type="Type",
        description="",
        confidence=0.5,
    )


@pytest.fixture

def sample_relation(sample_entity):
    e2 = ExtractedEntity(
        id="e2",
        label="Bar",
        entity_type="Type",
        description="",
        confidence=0.4,
    )
    return ExtractedRelation(
        id="r1",
        source_entity_id="e1",
        target_entity_id="e2",
        predicate="rel",
    )


def test_tiered_extractor_rules_sufficient(sample_entity):
    rule = DummyRuleExtractor([sample_entity])
    llm = DummyLLMExtractor([ExtractedEntity(id="e2", label="X", entity_type="T", description="", confidence=0.1)])
    te = TieredExtractor(rule, llm, min_entities_heuristic=1)
    out = te.extract("text")
    assert out == [sample_entity]
    assert rule.called
    assert not llm.called


def test_tiered_extractor_fallback(sample_entity):
    rule = DummyRuleExtractor([])
    llm_entity = ExtractedEntity(id="e3", label="LLM", entity_type="T", description="", confidence=0.9)
    llm = DummyLLMExtractor([llm_entity])
    te = TieredExtractor(rule, llm, min_entities_heuristic=1)
    out = te.extract("text")
    assert out == [llm_entity]
    assert rule.called
    assert llm.called


def test_tiered_relation_extractor_rules(sample_relation, sample_entity):
    rule = DummyRuleExtractor([sample_relation])
    llm = DummyLLMExtractor([])
    tre = TieredRelationExtractor(rule, llm, min_relations_heuristic=1)
    out = tre.extract("text", [sample_entity], [])
    assert out == [sample_relation]
    assert rule.called
    assert not llm.called


def test_tiered_relation_extractor_fallback(sample_relation, sample_entity):
    rule = DummyRuleExtractor([])
    llm = DummyLLMExtractor([sample_relation])
    tre = TieredRelationExtractor(rule, llm, min_relations_heuristic=1)
    out = tre.extract("text", [sample_entity], [])
    assert out == [sample_relation]
    assert rule.called
    assert llm.called


def test_ensemble_empty_text():
    e = EnsembleExtractor([DummyRuleExtractor([])])
    assert e.extract("   ", []) == []


def test_ensemble_no_extractors():
    with pytest.raises(ValueError):
        EnsembleExtractor([])


def test_ensemble_merging(sample_entity):
    # create two extractors returning same label/type with diff confidence
    ent1 = ExtractedEntity(
        id="e1", label="Foo", entity_type="T", description="", confidence=0.3
    )
    ent2 = ExtractedEntity(
        id="e2", label="foo", entity_type="T", description="", confidence=0.7
    )
    ex1 = DummyRuleExtractor([ent1])
    ex2 = DummyRuleExtractor([ent2])
    ensemble = EnsembleExtractor([ex1, ex2])
    out = ensemble.extract("text", ontology_classes=["T"])
    assert len(out) == 1
    merged = out[0]
    # confidence should be boosted above average
    assert merged.confidence > (0.3 + 0.7) / 2
    assert merged.properties["ensemble_votes"] == 2


def test_ensemble_handles_failures(sample_entity):
    good = DummyRuleExtractor([sample_entity])
    bad = FailingExtractor()
    ensemble = EnsembleExtractor([good, bad])
    out = ensemble.extract("text", ontology_classes=["T"])
    # should still return the results from good extractor
    assert out and out[0].label == "Foo"


def test_ensemble_no_results():
    # even if every extractor returns nothing, result should be empty list
    ensemble = EnsembleExtractor([DummyRuleExtractor([]), DummyRuleExtractor([])])
    assert ensemble.extract("text", ontology_classes=["T"]) == []


def test_tiered_extractor_partial_threshold():
    # rule produces one result but we require 2, so LLM should be called
    rule = DummyRuleExtractor([ExtractedEntity(id="e", label="L", entity_type="T", description="", confidence=0.1)])
    # LLM returns empty, so should fall back to rule output
    llm = DummyLLMExtractor([])
    te = TieredExtractor(rule, llm, min_entities_heuristic=2)
    out = te.extract("text")
    assert out == rule._results
    assert rule.called
    assert llm.called


def test_tiered_relation_extractor_below_threshold():
    # DummyRuleExtractor works because its signature accepts the extra
    # positional arguments passed by the tiered relation extractor.
    rel = ExtractedRelation(
        id="r",
        source_entity_id="a",
        target_entity_id="b",
        predicate="p",
    )
    rule = DummyRuleExtractor([rel])
    llm = DummyRuleExtractor([])
    tre = TieredRelationExtractor(rule, llm, min_relations_heuristic=2)
    res = tre.extract("t", [], [])
    # not enough rule results so llm called and its empty result is returned
    assert res == []
    assert rule.called
    assert llm.called
