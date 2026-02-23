import numpy as np
import pytest

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.enrichment import SemanticEnrichmentPipeline, EnrichedEntity, EnrichedRelation
# import full pipeline for end-to-end enrichment phases
from kgbuilder.enrichment.pipeline import SemanticEnrichmentPipeline as FullEnrichmentPipeline, EnrichmentMetrics


class DummyEmbeddingProvider:
    """A simple embedding provider for testing."""

    def __init__(self, fail: bool = False, return_array: bool = False):
        self.fail = fail
        self.return_array = return_array

    def embed_text(self, text: str):
        if self.fail or "fail" in text:
            raise ValueError("embedding failure")
        vec = [1.0, 2.0, 3.0]
        if self.return_array:
            return np.array(vec, dtype=np.float32)
        return vec


class DummyLLMProvider:
    """Placeholder LLM provider; not actually used by current pipeline."""

    def __init__(self):
        pass


@pytest.fixture
def entity_example() -> ExtractedEntity:
    return ExtractedEntity(
        id="e1",
        label="Sample",
        entity_type="TypeA",
        description="",
        confidence=0.8,
    )


@pytest.fixture
def relation_example() -> ExtractedRelation:
    return ExtractedRelation(
        id="r1",
        source_entity_id="e1",
        target_entity_id="e2",
        predicate="relatedTo",
    )


@pytest.fixture
def pipeline() -> SemanticEnrichmentPipeline:
    # simple providers, LLM unused
    return SemanticEnrichmentPipeline(DummyLLMProvider(), DummyEmbeddingProvider())


def test_generate_entity_description(entity_example, pipeline):
    desc = pipeline._generate_entity_description(entity_example)
    assert "Sample" in desc
    assert "TypeA" in desc
    assert "confidence" in desc


def test_generate_competency_questions(pipeline):
    questions = pipeline._generate_competency_questions("Foo", "Bar")
    assert isinstance(questions, list)
    assert len(questions) == 3
    assert any("What is Foo" in q for q in questions)


def test_generate_relation_description(pipeline):
    desc = pipeline._generate_relation_description("A", "B", "knows")
    assert "A" in desc and "B" in desc and "knows" in desc


def test_generate_embedding_success(pipeline):
    emb = pipeline._generate_embedding("some text")
    assert isinstance(emb, np.ndarray)
    assert emb.dtype == np.float32
    assert emb.shape == (3,)


def test_generate_embedding_failure():
    pipeline = SemanticEnrichmentPipeline(DummyLLMProvider(), DummyEmbeddingProvider(fail=True))
    emb = pipeline._generate_embedding("will fail")
    assert emb is None


def test_enrich_entities_basic(entity_example, pipeline):
    metadata = {"e1": {"questions": ["q1"], "confidence": 0.9, "evidence_count": 2}}
    enriched = pipeline.enrich_entities([entity_example], discovery_metadata=metadata)
    assert len(enriched) == 1
    ee = enriched[0]
    assert isinstance(ee, EnrichedEntity)
    assert ee.entity is entity_example
    assert ee.description
    assert ee.semantic_embedding is not None
    assert ee.competency_questions and len(ee.competency_questions) == 3
    # metadata should propagate
    assert ee.discovery_question_ids == ["q1"]
    assert ee.evidence_count == 2
    assert pytest.approx(ee.discovery_confidence) == 0.9


def test_enrich_entities_embedding_error(entity_example):
    pipeline = SemanticEnrichmentPipeline(DummyLLMProvider(), DummyEmbeddingProvider(fail=True))
    enriched = pipeline.enrich_entities([entity_example])
    assert len(enriched) == 1
    assert enriched[0].semantic_embedding is None


def test_enrich_entities_description_exception(entity_example, pipeline, monkeypatch):
    # force description generator to fail
    monkeypatch.setattr(pipeline, "_generate_entity_description", lambda e: (_ for _ in ()).throw(RuntimeError("boom")))
    enriched = pipeline.enrich_entities([entity_example])
    assert len(enriched) == 1
    assert enriched[0].description == ""
    assert enriched[0].entity is entity_example


def test_enrich_relations_basic(relation_example, entity_example):
    # create two entities for mapping
    entity2 = ExtractedEntity(id="e2", label="Target", entity_type="TypeB", description="", confidence=0.5)
    pipeline = SemanticEnrichmentPipeline(DummyLLMProvider(), DummyEmbeddingProvider())
    enriched = pipeline.enrich_relations([relation_example], entities={"e1": entity_example, "e2": entity2})
    assert len(enriched) == 1
    er = enriched[0]
    assert isinstance(er, EnrichedRelation)
    assert "relatedTo" in er.description
    assert er.semantic_embedding is not None


def test_enrich_relations_no_entities(relation_example):
    # should still work with missing entity map
    pipeline = SemanticEnrichmentPipeline(DummyLLMProvider(), DummyEmbeddingProvider())
    enriched = pipeline.enrich_relations([relation_example], entities=None)
    assert len(enriched) == 1
    assert enriched[0].description


def test_enrich_relations_embedding_fail(relation_example, entity_example):
    entity2 = ExtractedEntity(id="e2", label="Target", entity_type="TypeB", description="", confidence=0.5)
    pipeline = SemanticEnrichmentPipeline(DummyLLMProvider(), DummyEmbeddingProvider(fail=True))
    enriched = pipeline.enrich_relations([relation_example], entities={"e1": entity_example, "e2": entity2})
    assert len(enriched) == 1
    assert enriched[0].semantic_embedding is None


def test_pipeline_metrics_and_error_handling(monkeypatch):
    # create pipeline with dummy providers
    # use full pipeline implementation (not extraction variant)
    pip = FullEnrichmentPipeline(DummyLLMProvider(), DummyEmbeddingProvider())
    # replace enrichers with simple fakes that modify entities/relations
    class FakeEnricher:
        def __init__(self, name):
            self.name = name
        def enrich_entities(self, entities):
            # add marker to description
            for e in entities:
                setattr(e, self.name, True)
            return entities
        def enrich_relations(self, relations):
            for r in relations:
                setattr(r, self.name, True)
            return relations

    fake1 = FakeEnricher("phase1")
    fake2 = FakeEnricher("phase2")
    pip.enrichers = [("phase1", fake1), ("phase2", fake2)]

    # initial entities/relations
    ent = ExtractedEntity(id="e1", label="L", entity_type="T", description="", confidence=0.5)
    rel = ExtractedRelation(id="r1", source_entity_id="e1", target_entity_id="e1", predicate="p")
    ents, rels, metrics = pip.enrich([ent], [rel])

    assert isinstance(metrics, EnrichmentMetrics)
    assert ents[0].phase1 and ents[0].phase2
    assert rels[0].phase1 and rels[0].phase2
    assert metrics.total_entities == 1
    assert metrics.total_relations == 1
    assert metrics.duration_seconds >= 0

    # simulate one enricher raising error mid-pipeline
    class BadEnricher(FakeEnricher):
        def enrich_entities(self, entities):
            raise RuntimeError("oops")
    pip.enrichers = [("bad", BadEnricher("bad")), ("ok", FakeEnricher("ok"))]
    ents2, rels2, metrics2 = pip.enrich([ent], [])

    assert isinstance(metrics2, EnrichmentMetrics)
    # after error first phase should be skipped but second still runs
    assert hasattr(ents2[0], "ok")


# ---------------------------------------------------------------------------
# Additional tests for *enrichment* modules (not extraction)
# ---------------------------------------------------------------------------

from kgbuilder.enrichment.enrichers import (
    DescriptionEnricher,
    EmbeddingEnricher,
    CompetencyQuestionEnricher,
    TypeConstraintEnricher,
    AliasEnricher,
)
from kgbuilder.enrichment.pipeline import SemanticEnrichmentPipeline as EnrichPipeline
from kgbuilder.enrichment.protocols import EnrichedEntity as EE, EnrichedRelation as ER


# helpers for enrichment tests
class SimpleLLM:
    def __init__(self, resp: str = "resp", fail: bool = False):
        self.resp = resp
        self.fail = fail

    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        if self.fail:
            raise RuntimeError("bad")
        return self.resp


class SimpleEmbedding:
    def __init__(self, vec=None, fail: bool = False, array: bool = False):
        self.vec = vec or [0.1, 0.2]
        self.fail = fail
        self.array = array

    def embed_text(self, text: str):
        if self.fail:
            raise RuntimeError("err")
        return np.array(self.vec) if self.array else list(self.vec)


def make_e(label="L", etype="T"):
    return EE(entity_id="e", label=label, entity_type=etype, confidence=0.5)

def make_r(pred="p"):
    return ER(relation_id="r", source_id="s", target_id="t", predicate=pred, confidence=0.5)


def test_description_enricher():
    llm = SimpleLLM(resp="D")
    enr = DescriptionEnricher(llm)
    ent = make_e()
    out = enr.enrich_entities([ent])[0]
    assert out.description == "D"
    # preloaded description skipped
    ent2 = make_e()
    ent2.description = "X"
    assert enr.enrich_entities([ent2])[0].description == "X"


def test_description_error(caplog):
    llm = SimpleLLM(fail=True)
    enr = DescriptionEnricher(llm)
    ent = make_e()
    caplog.set_level("WARNING")
    out = enr.enrich_entities([ent])[0]
    assert out.description is None
    assert "Failed to generate description" in caplog.text


def test_embedding_enricher():
    prov = SimpleEmbedding(vec=[9, 9], array=True)
    enr = EmbeddingEnricher(prov)
    ent = make_e()
    ent.description = "desc"
    out = enr.enrich_entities([ent])[0]
    assert out.embedding == [9, 9]


def test_embedding_error(caplog):
    prov = SimpleEmbedding(fail=True)
    enr = EmbeddingEnricher(prov)
    ent = make_e()
    caplog.set_level("WARNING")
    out = enr.enrich_entities([ent])[0]
    assert out.embedding is None
    assert "Failed to generate embedding" in caplog.text


def test_competency_questions():
    llm = SimpleLLM(resp="a\nb")
    enr = CompetencyQuestionEnricher(llm)
    ent = make_e()
    out = enr.enrich_entities([ent])[0]
    assert out.competency_questions == ["a", "b"]


def test_alias_enricher():
    llm = SimpleLLM(resp="x,y,z")
    enr = AliasEnricher(llm)
    ent = make_e()
    out = enr.enrich_entities([ent])[0]
    assert out.aliases == ["x", "y", "z"]


def test_type_constraint():
    enr = TypeConstraintEnricher({"T": {}, "Other": {}})
    ent = make_e(etype="T")
    out = enr.enrich_entities([ent])[0]
    # "T" matches exactly; "Other" is considered related by simple substring logic
    assert out.type_scores["T"] == 1.0
    assert out.type_scores["Other"] == 0.5


def test_semantic_pipeline():
    llm = SimpleLLM(resp="d")
    emb = SimpleEmbedding(vec=[1, 2])
    pip = EnrichPipeline(llm, emb, ontology_classes={"T": {}})
    ent = make_e()
    ents, rels, mets = pip.enrich([ent], [])
    assert mets.total_entities == 1
    assert mets.descriptions_added >= 0
    assert isinstance(ents[0].description, str)

