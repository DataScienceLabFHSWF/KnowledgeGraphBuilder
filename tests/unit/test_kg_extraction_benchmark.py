from __future__ import annotations

from pathlib import Path
from typing import Any

from kgbuilder.core.models import Evidence, ExtractedEntity, ExtractedRelation
from kgbuilder.evaluation.kg_extraction_benchmark import (
    KGExtractionBenchmarkDataset,
    KGExtractionBenchmarkRunner,
    _local_name,
    render_benchmark_markdown,
)
from kgbuilder.extraction.entity import OntologyClassDef
from kgbuilder.extraction.relation import OntologyRelationDef

DATASET_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "evaluation"
    / "kg_extraction_benchmark_smoke.json"
)


def test_local_name_supports_urn_ontology_identifiers() -> None:
    assert _local_name("urn:kgb:NuclearFacility") == "NuclearFacility"


class FakeEntityExtractor:
    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        return [
            ExtractedEntity(
                id="person",
                label="Ada Lovelace",
                entity_type="Person",
                description="",
                confidence=0.9,
                properties={},
            ),
            ExtractedEntity(
                id="company",
                label="Analytical Engines Ltd.",
                entity_type="Company",
                description="",
                confidence=0.9,
                properties={"employment_start_year": "1843"},
            ),
        ]


class FakeRelationExtractor:
    def __init__(self, usage_history: list[dict[str, Any]]) -> None:
        self.usage_history = usage_history

    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> list[ExtractedRelation]:
        self.usage_history.append(
            {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
                "source": "server",
            }
        )
        return [
            ExtractedRelation(
                id="relationship",
                source_entity_id="person",
                target_entity_id="company",
                predicate="urn:kg:works_for",
                confidence=0.9,
                evidence=[
                    Evidence(
                        source_type="test",
                        source_id="passage",
                        text_span=text,
                        confidence=0.9,
                    )
                ],
            )
        ]


class FakeProvider:
    model_name = "fake"

    def __init__(self) -> None:
        self.usage_history: list[dict[str, Any]] = []


def test_smoke_dataset_has_version_and_stable_hash() -> None:
    dataset, digest = KGExtractionBenchmarkDataset.load(DATASET_PATH)

    assert dataset.split == "smoke"
    assert dataset.version == "0.1.0"
    assert len(dataset.items) == 2
    assert len(digest) == 64


def test_benchmark_reports_quality_richness_latency_and_server_tokens() -> None:
    dataset, _ = KGExtractionBenchmarkDataset.load(DATASET_PATH)
    item = dataset.model_copy(update={"items": [dataset.items[1]]})
    relation_usage: list[dict[str, Any]] = []

    result = KGExtractionBenchmarkRunner(
        entity_extractor=FakeEntityExtractor(),
        relation_extractor=FakeRelationExtractor(relation_usage),
        llm_provider=FakeProvider(),
    ).run(item)

    aggregate = result["aggregate"]
    assert aggregate["entity_metrics"]["f1"] == 1.0
    assert aggregate["triple_metrics"]["f1"] == 1.0
    assert aggregate["attribute_metrics"]["f1"] == 1.0
    assert aggregate["kg_richness"]["relation_evidence_entity_coverage"] == 1.0
    assert aggregate["kg_richness"]["ontology_domain_range_validity"] == 1.0
    assert aggregate["tokens"] == {
        "prompt": 10,
        "completion": 2,
        "total": 12,
        "source": "server",
        "calls": 1,
    }
    assert aggregate["latency_seconds"]["median"] is not None
    assert result["trials"][0]["predictions"]["entities"][0]["text"] == "Ada Lovelace"
    assert set(aggregate["quality_ci95"]["triple_f1"]) == {"lower", "upper"}


def test_benchmark_markdown_includes_metrics_usage_and_json_link() -> None:
    dataset, _ = KGExtractionBenchmarkDataset.load(DATASET_PATH)
    item = dataset.model_copy(update={"items": [dataset.items[1]]})
    result = KGExtractionBenchmarkRunner(
        entity_extractor=FakeEntityExtractor(),
        relation_extractor=FakeRelationExtractor([]),
        llm_provider=FakeProvider(),
    ).run(item)
    result["run"] = {
        "llm_model": "test-model",
        "llm_backend": "ollama",
        "entity_extractor": "gliner",
        "relation_extractor": "decision",
        "model_revision": "test-revision",
        "dataset_sha256": "abc123",
    }

    markdown = render_benchmark_markdown(result, "test-report.json")

    assert "# KG extraction benchmark: test-model" in markdown
    assert "| Entity | 1.000 | 1.000 | 1.000 |" in markdown
    assert "## Runtime and usage" in markdown
    assert "Raw per-item predictions and measurements: [test-report.json]" in markdown


def test_benchmark_warmup_is_not_counted_in_trials() -> None:
    dataset, _ = KGExtractionBenchmarkDataset.load(DATASET_PATH)
    item = dataset.model_copy(update={"items": [dataset.items[1]]})

    result = KGExtractionBenchmarkRunner(
        entity_extractor=FakeEntityExtractor(),
        relation_extractor=FakeRelationExtractor([]),
        llm_provider=FakeProvider(),
    ).run(item, warmup_count=1)

    assert len(result["warmup"]) == 1
    assert len(result["trials"]) == 1


def test_benchmark_records_extraction_errors_explicitly() -> None:
    dataset, _ = KGExtractionBenchmarkDataset.load(DATASET_PATH)
    item = dataset.model_copy(update={"items": [dataset.items[1]]})

    class FailingEntityExtractor(FakeEntityExtractor):
        def extract(self, text, ontology_classes, existing_entities=None):
            raise RuntimeError("mock entity failure")

    result = KGExtractionBenchmarkRunner(
        entity_extractor=FailingEntityExtractor(),
        relation_extractor=FakeRelationExtractor([]),
        llm_provider=FakeProvider(),
    ).run(item)

    assert result["trials"][0]["errors"] == [
        {"stage": "entity_extraction", "message": "mock entity failure"}
    ]
    assert result["aggregate"]["errors"] == 1


def test_benchmark_does_not_report_unknown_token_counts_as_zero() -> None:
    dataset, _ = KGExtractionBenchmarkDataset.load(DATASET_PATH)
    item = dataset.model_copy(update={"items": [dataset.items[1]]})

    class NoUsageRelationExtractor(FakeRelationExtractor):
        def extract(self, text, entities, ontology_relations):
            return []

    result = KGExtractionBenchmarkRunner(
        entity_extractor=FakeEntityExtractor(),
        relation_extractor=NoUsageRelationExtractor([]),
        llm_provider=FakeProvider(),
    ).run(item)

    assert result["aggregate"]["tokens"]["total"] is None
    assert result["aggregate"]["tokens"]["source"] == "unavailable"


def test_benchmark_reports_candidate_recall_separately_from_accepted_recall() -> None:
    from kgbuilder.extraction.decision_model import DecisionModelRelationExtractor

    class RejectAllClient:
        def decide(
            self, state: dict[str, Any], questions: dict[str, dict[str, Any]]
        ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
            return {name: {"noul": 0.01} for name in questions}, {}

    dataset, _ = KGExtractionBenchmarkDataset.load(DATASET_PATH)
    result = KGExtractionBenchmarkRunner(
        entity_extractor=FakeEntityExtractor(),
        relation_extractor=DecisionModelRelationExtractor(RejectAllClient()),
        llm_provider=FakeProvider(),
    ).run(dataset.model_copy(update={"items": [dataset.items[1]]}), repeats=2)
    assert result["aggregate"]["decision_candidates"]["recall"] == 1.0
    assert result["aggregate"]["decision_candidates"]["measured_trials"] == 2
    assert result["aggregate"]["triple_metrics"]["recall"] == 0.0
    assert "Candidate recall: 1.000" in render_benchmark_markdown(result, "result.json")
