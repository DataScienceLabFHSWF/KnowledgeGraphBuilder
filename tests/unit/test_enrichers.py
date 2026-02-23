from __future__ import annotations

import pytest
import numpy as np

from kgbuilder.enrichment.enrichers import (
    DescriptionEnricher,
    EmbeddingEnricher,
    CompetencyQuestionEnricher,
    TypeConstraintEnricher,
    AliasEnricher,
)
from kgbuilder.enrichment.protocols import EnrichedEntity, EnrichedRelation
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation


class DummyLLM:
    def __init__(self, reply: str | None = None, fail: bool = False):
        self.reply = reply or ""
        self.fail = fail

    def generate(self, prompt: str, temperature: float = 0.5):
        if self.fail:
            raise RuntimeError("llm error")
        return self.reply


class DummyEmbed:
    def __init__(self, vec=(1, 2, 3), fail=False):
        self.vec = vec
        self.fail = fail

    def embed_text(self, text: str):
        if self.fail:
            raise ValueError("embed fail")
        return np.array(self.vec, dtype=np.float32)


def make_enriched_entity(label="L", etype="T") -> EnrichedEntity:
    # use the protocols dataclass fields
    return EnrichedEntity(
        entity_id="e",
        label=label,
        entity_type=etype,
        confidence=0.5,
    )


def make_enriched_relation(pred="p") -> EnrichedRelation:
    return EnrichedRelation(
        relation_id="r",
        source_id="a",
        target_id="b",
        predicate=pred,
        confidence=0.5,
    )


def test_description_enricher_basic():
    llm = DummyLLM(reply="a good description")
    enr = DescriptionEnricher(llm)
    ent = make_enriched_entity()
    rel = make_enriched_relation()
    out = enr.enrich_entities([ent])
    assert out[0].description == "a good description"
    out2 = enr.enrich_relations([rel])
    assert out2[0].description == "a good description"


def test_description_enricher_skips_and_errors():
    llm = DummyLLM(reply="desc")
    enr = DescriptionEnricher(llm)
    ent = make_enriched_entity()
    ent.description = "already"
    out = enr.enrich_entities([ent])
    assert out[0].description == "already"
    # error
    bad = DescriptionEnricher(DummyLLM(fail=True))
    e2 = make_enriched_entity()
    out2 = bad.enrich_entities([e2])
    # failure should leave description unset (None)
    assert out2[0].description in (None, "")


def test_embedding_enricher_success_and_failure():
    emb = DummyEmbed()
    enr = EmbeddingEnricher(emb)
    ent = make_enriched_entity()
    out = enr.enrich_entities([ent])
    assert isinstance(out[0].embedding, list)
    rel = make_enriched_relation()
    out2 = enr.enrich_relations([rel])
    assert isinstance(out2[0].embedding, list)
    # failure
    bad = EmbeddingEnricher(DummyEmbed(fail=True))
    e = make_enriched_entity()
    bad.enrich_entities([e])  # should not raise


def test_competency_question_enricher():
    llm = DummyLLM(reply="Q1\nQ2\nQ3")
    enr = CompetencyQuestionEnricher(llm)
    ent = make_enriched_entity()
    res = enr.enrich_entities([ent])
    assert len(res[0].competency_questions) == 3
    # skip when already present
    ent2 = make_enriched_entity()
    ent2.competency_questions = ["x"]
    assert enr.enrich_entities([ent2])[0].competency_questions == ["x"]
    # error
    bad = CompetencyQuestionEnricher(DummyLLM(fail=True))
    e3 = make_enriched_entity()
    bad.enrich_entities([e3])


def test_type_constraint_enricher_scores():
    ontos = {"A": object(), "B": object()}
    enr = TypeConstraintEnricher(ontos)
    ent = make_enriched_entity(label="X", etype="A")
    res = enr.enrich_entities([ent])
    assert res[0].type_scores
    assert res[0].type_scores.get("A") == 1.0
    # related heuristic
    ent2 = make_enriched_entity(label="Y", etype="Ax")
    res2 = enr.enrich_entities([ent2])
    assert res2[0].type_scores.get("A") == 0.5


def test_alias_enricher():
    llm = DummyLLM(reply="foo, bar")
    enr = AliasEnricher(llm)
    ent = make_enriched_entity()
    res = enr.enrich_entities([ent])
    assert res[0].aliases == ["foo", "bar"]
    # skip existing
    ent2 = make_enriched_entity()
    ent2.aliases = ["x"]
    assert enr.enrich_entities([ent2])[0].aliases == ["x"]
    # error
    bad = AliasEnricher(DummyLLM(fail=True))
    e = make_enriched_entity()
    bad.enrich_entities([e])
