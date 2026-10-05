"""Gold-set evaluation for ontology-grounded entity and triple extraction."""

from __future__ import annotations

import hashlib
import random
import re
import statistics
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol, TypedDict

from pydantic import BaseModel, Field

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.entity import OntologyClassDef
from kgbuilder.extraction.relation import OntologyRelationDef


class GoldEntity(BaseModel):
    """Reviewed gold entity mention and optional attributes."""

    text: str
    entity_type: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class GoldTriple(BaseModel):
    """Reviewed gold subject-predicate-object triple."""

    subject: str
    predicate: str
    object: str
    evidence: str


class KGExtractionBenchmarkItem(BaseModel):
    """One source passage with its local ontology subset and gold KG."""

    id: str
    language: str
    text: str
    source_document: str | None = None
    source_reference: str | None = None
    text_origin: str = "source"
    variant_of: str | None = None
    classes: list[OntologyClassDef] = Field(default_factory=list)
    relations: list[OntologyRelationDef] = Field(default_factory=list)
    gold_entities: list[GoldEntity]
    gold_triples: list[GoldTriple]


class KGExtractionBenchmarkDataset(BaseModel):
    """Versioned, document-split benchmark dataset."""

    name: str
    version: str
    split: str
    description: str = ""
    classes: list[OntologyClassDef] = Field(default_factory=list)
    relations: list[OntologyRelationDef] = Field(default_factory=list)
    items: list[KGExtractionBenchmarkItem] = Field(min_length=1)

    @classmethod
    def load(cls, path: Path) -> tuple[KGExtractionBenchmarkDataset, str]:
        """Load a dataset and return its content hash for run provenance."""
        content = path.read_bytes()
        dataset = cls.model_validate_json(content)
        return dataset, hashlib.sha256(content).hexdigest()


class EntityExtractor(Protocol):
    """Minimal interface required by the benchmark runner."""

    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]: ...


class RelationExtractor(Protocol):
    """Minimal interface required by the benchmark runner."""

    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
        ontology_relations: list[OntologyRelationDef],
    ) -> list[ExtractedRelation]: ...


class _BenchmarkAggregate(TypedDict):
    entity_tp: int
    entity_predicted: int
    entity_gold: int
    triple_tp: int
    triple_predicted: int
    triple_gold: int
    attribute_tp: int
    attribute_predicted: int
    attribute_gold: int
    relation_evidence_entity_covered: int
    relation_evidence_count: int
    predicted_entities: int
    predicted_triples: int
    gold_entities: int
    gold_triples: int
    ontology_class_types: set[str]
    ontology_relation_types: set[str]
    all_ontology_class_types: set[str]
    all_ontology_relation_types: set[str]
    predicted_attribute_count: int
    gold_attribute_count: int
    valid_relations: int
    predicted_relation_count: int
    duration_seconds: list[float]
    prompt_tokens: int
    completion_tokens: int
    token_records: int
    prompt_token_measurements: int
    completion_token_measurements: int
    token_sources: set[str]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _local_name(value: str) -> str:
    if value.casefold().startswith("urn:"):
        return value.rsplit(":", maxsplit=1)[-1]
    return value.rstrip("/#").rsplit("/", maxsplit=1)[-1].rsplit("#", maxsplit=1)[-1]


def _canonical_type_name(value: str) -> str:
    return "".join(character.casefold() for character in _local_name(value) if character.isalnum())


def _prf(true_positive: int, predicted: int, gold: int) -> dict[str, float]:
    precision = true_positive / predicted if predicted else float(gold == 0)
    recall = true_positive / gold if gold else float(predicted == 0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _triple_key(subject: str, predicate: str, object_: str) -> tuple[str, str, str]:
    return (_normalize(subject), _normalize(_local_name(predicate)), _normalize(object_))


class KGExtractionBenchmarkRunner:
    """Measure extraction quality, provider tokens, and passage latency."""

    def __init__(
        self,
        entity_extractor: EntityExtractor,
        relation_extractor: RelationExtractor,
        llm_provider: Any,
    ) -> None:
        self.entity_extractor = entity_extractor
        self.relation_extractor = relation_extractor
        self.llm_provider = llm_provider

    def run(
        self,
        dataset: KGExtractionBenchmarkDataset,
        repeats: int = 1,
        warmup_count: int = 0,
    ) -> dict[str, Any]:
        """Run every item and report quality, runtime, usage, and raw predictions."""
        if repeats < 1:
            raise ValueError("repeats must be at least one")
        if warmup_count < 0:
            raise ValueError("warmup_count must not be negative")
        dataset_items = [
            item.model_copy(
                update={
                    "classes": item.classes or dataset.classes,
                    "relations": item.relations or dataset.relations,
                }
            )
            for item in dataset.items
        ]
        warmup_results = []
        for item in dataset_items[:warmup_count]:
            warmup_started = time.perf_counter()
            entities = self.entity_extractor.extract(item.text, item.classes)
            relations = self.relation_extractor.extract(item.text, entities, item.relations)
            warmup_results.append(
                {
                    "item_id": item.id,
                    "duration_seconds": time.perf_counter() - warmup_started,
                    "entities": len(entities),
                    "relations": len(relations),
                }
            )
        item_results: list[dict[str, Any]] = []
        aggregate: _BenchmarkAggregate = {
            "entity_tp": 0,
            "entity_predicted": 0,
            "entity_gold": 0,
            "triple_tp": 0,
            "triple_predicted": 0,
            "triple_gold": 0,
            "attribute_tp": 0,
            "attribute_predicted": 0,
            "attribute_gold": 0,
            "relation_evidence_entity_covered": 0,
            "relation_evidence_count": 0,
            "predicted_entities": 0,
            "predicted_triples": 0,
            "gold_entities": 0,
            "gold_triples": 0,
            "ontology_class_types": set(),
            "ontology_relation_types": set(),
            "all_ontology_class_types": set(),
            "all_ontology_relation_types": set(),
            "predicted_attribute_count": 0,
            "gold_attribute_count": 0,
            "valid_relations": 0,
            "predicted_relation_count": 0,
            "duration_seconds": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "token_records": 0,
            "prompt_token_measurements": 0,
            "completion_token_measurements": 0,
            "token_sources": set(),
        }

        for repeat in range(1, repeats + 1):
            for item in dataset_items:
                result = self._run_item(item, repeat)
                item_results.append(result)
                aggregate["entity_tp"] += result["entity_tp"]
                aggregate["entity_predicted"] += result["entity_predicted"]
                aggregate["entity_gold"] += result["entity_gold"]
                aggregate["triple_tp"] += result["triple_tp"]
                aggregate["triple_predicted"] += result["triple_predicted"]
                aggregate["triple_gold"] += result["triple_gold"]
                aggregate["attribute_tp"] += result["attribute_tp"]
                aggregate["attribute_predicted"] += result["attribute_predicted"]
                aggregate["attribute_gold"] += result["attribute_gold"]
                aggregate["relation_evidence_entity_covered"] += result[
                    "relation_evidence_entity_covered"
                ]
                aggregate["relation_evidence_count"] += result["relation_evidence_count"]
                aggregate["predicted_entities"] += result["predicted_entities"]
                aggregate["predicted_triples"] += result["predicted_triples"]
                aggregate["gold_entities"] += result["gold_entities"]
                aggregate["gold_triples"] += result["gold_triples"]
                aggregate["predicted_attribute_count"] += result["predicted_attribute_count"]
                aggregate["gold_attribute_count"] += result["gold_attribute_count"]
                aggregate["valid_relations"] += result["valid_relations"]
                aggregate["predicted_relation_count"] += result["predicted_relation_count"]
                aggregate["prompt_tokens"] += result["prompt_tokens"]
                aggregate["completion_tokens"] += result["completion_tokens"]
                aggregate["token_records"] += result["token_records"]
                aggregate["prompt_token_measurements"] += result["prompt_token_measurements"]
                aggregate["completion_token_measurements"] += result[
                    "completion_token_measurements"
                ]
                aggregate["duration_seconds"].append(result["duration_seconds"])
                aggregate["ontology_class_types"].update(result["predicted_class_types"])
                aggregate["ontology_relation_types"].update(result["predicted_relation_types"])
                aggregate["all_ontology_class_types"].update(result["ontology_class_types"])
                aggregate["all_ontology_relation_types"].update(result["ontology_relation_types"])
                aggregate["token_sources"].update(result["token_sources"])

        entity_metrics = _prf(
            aggregate["entity_tp"],
            aggregate["entity_predicted"],
            aggregate["entity_gold"],
        )
        triple_metrics = _prf(
            aggregate["triple_tp"],
            aggregate["triple_predicted"],
            aggregate["triple_gold"],
        )
        attribute_metrics = _prf(
            aggregate["attribute_tp"],
            aggregate["attribute_predicted"],
            aggregate["attribute_gold"],
        )
        durations = sorted(aggregate["duration_seconds"])
        total_tokens = aggregate["prompt_tokens"] + aggregate["completion_tokens"]
        tokens_measured = (
            aggregate["prompt_token_measurements"] > 0
            and aggregate["completion_token_measurements"] > 0
        )
        return {
            "dataset": {
                "name": dataset.name,
                "version": dataset.version,
                "split": dataset.split,
                "item_count": len(dataset_items),
                "repeats": repeats,
                "trial_count": len(item_results),
                "languages": sorted({item.language for item in dataset_items}),
                "source_documents": sorted(
                    {item.source_document for item in dataset_items if item.source_document}
                ),
            },
            "warmup": warmup_results,
            "trials": item_results,
            "aggregate": {
                "entity_metrics": entity_metrics,
                "triple_metrics": triple_metrics,
                "attribute_metrics": attribute_metrics,
                "entity_counts": {
                    "predicted": aggregate["predicted_entities"],
                    "gold": aggregate["gold_entities"],
                },
                "triple_counts": {
                    "predicted": aggregate["predicted_triples"],
                    "gold": aggregate["gold_triples"],
                },
                "kg_richness": {
                    "predicted_entity_class_types": len(aggregate["ontology_class_types"]),
                    "predicted_relation_types": len(aggregate["ontology_relation_types"]),
                    "ontology_class_coverage": (
                        len(
                            aggregate["ontology_class_types"]
                            & aggregate["all_ontology_class_types"]
                        )
                        / len(aggregate["all_ontology_class_types"])
                        if aggregate["all_ontology_class_types"]
                        else 0.0
                    ),
                    "ontology_relation_coverage": (
                        len(
                            aggregate["ontology_relation_types"]
                            & aggregate["all_ontology_relation_types"]
                        )
                        / len(aggregate["all_ontology_relation_types"])
                        if aggregate["all_ontology_relation_types"]
                        else 0.0
                    ),
                    "predicted_attributes": aggregate["predicted_attribute_count"],
                    "gold_attributes": aggregate["gold_attribute_count"],
                    "relation_evidence_entity_coverage": (
                        aggregate["relation_evidence_entity_covered"]
                        / aggregate["relation_evidence_count"]
                        if aggregate["relation_evidence_count"]
                        else 1.0
                    ),
                    "ontology_domain_range_validity": (
                        aggregate["valid_relations"] / aggregate["predicted_relation_count"]
                        if aggregate["predicted_relation_count"]
                        else 1.0
                    ),
                },
                "latency_seconds": {
                    "median": self._percentile(durations, 0.5),
                    "p95": self._percentile(durations, 0.95),
                    "mean": statistics.mean(durations) if durations else 0.0,
                },
                "quality_ci95": {
                    "entity_f1": self._bootstrap_f1(item_results, "entity_tp"),
                    "triple_f1": self._bootstrap_f1(item_results, "triple_tp"),
                },
                "errors": sum(bool(result["errors"]) for result in item_results),
                "decision_candidates": self._candidate_metrics(item_results),
                "tokens": {
                    "prompt": (
                        aggregate["prompt_tokens"]
                        if aggregate["prompt_token_measurements"]
                        else None
                    ),
                    "completion": (
                        aggregate["completion_tokens"]
                        if aggregate["completion_token_measurements"]
                        else None
                    ),
                    "total": total_tokens if tokens_measured else None,
                    "source": (
                        "mixed"
                        if len(aggregate["token_sources"]) > 1
                        else next(iter(aggregate["token_sources"]), "unavailable")
                    ),
                    "calls": aggregate["token_records"],
                },
            },
        }

    def _run_item(self, item: KGExtractionBenchmarkItem, repeat: int) -> dict[str, Any]:
        provider_usage = getattr(self.llm_provider, "usage_history", [])
        provider_usage_start = len(provider_usage)
        relation_usage = getattr(self.relation_extractor, "usage_history", [])
        relation_usage_start = len(relation_usage)
        started = time.perf_counter()
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []
        errors: list[dict[str, str]] = []
        try:
            entities = self.entity_extractor.extract(item.text, item.classes)
        except Exception as exc:
            errors.append({"stage": "entity_extraction", "message": str(exc)})
        if not errors:
            try:
                relations = self.relation_extractor.extract(item.text, entities, item.relations)
            except Exception as exc:
                errors.append({"stage": "relation_extraction", "message": str(exc)})
        elapsed = time.perf_counter() - started

        entity_gold = {
            (_normalize(entity.text), _normalize(_local_name(entity.entity_type)))
            for entity in item.gold_entities
        }
        entity_predictions = {
            (_normalize(entity.label), _normalize(_local_name(entity.entity_type)))
            for entity in entities
        }
        entity_tp = len(entity_gold & entity_predictions)
        predicted_labels = {entity.id: entity.label for entity in entities}
        triple_gold = {
            _triple_key(triple.subject, triple.predicate, triple.object)
            for triple in item.gold_triples
        }
        predicted_triples = {
            _triple_key(
                predicted_labels.get(relation.source_entity_id, relation.source_entity_id),
                relation.predicate,
                predicted_labels.get(relation.target_entity_id, relation.target_entity_id),
            )
            for relation in relations
        }
        candidates = getattr(self.relation_extractor, "last_candidate_triples", None)
        candidate_keys = (
            {_triple_key(*candidate) for candidate in candidates}
            if candidates is not None and not errors
            else None
        )
        attribute_gold = {
            (_normalize(entity.text), _normalize(name), _normalize(str(value)))
            for entity in item.gold_entities
            for name, value in entity.attributes.items()
        }
        attribute_predictions = {
            (_normalize(entity.label), _normalize(name), _normalize(str(value)))
            for entity in entities
            for name, value in entity.properties.items()
        }
        evidence_covered = 0
        evidence_count = 0
        for relation in relations:
            for evidence in relation.evidence:
                evidence_count += 1
                quote = evidence.text_span or ""
                source_matches = bool(quote) and quote in item.text
                subject_label = predicted_labels.get(relation.source_entity_id, "")
                object_label = predicted_labels.get(relation.target_entity_id, "")
                endpoint_matches = (
                    bool(subject_label and object_label)
                    and subject_label.casefold() in quote.casefold()
                    and object_label.casefold() in quote.casefold()
                )
                evidence_covered += int(source_matches and endpoint_matches)

        class_aliases = {
            alias: _normalize(_local_name(definition.uri))
            for definition in item.classes
            for alias in (
                _normalize(_local_name(definition.uri)),
                _normalize(definition.label),
            )
        }
        class_types = set(class_aliases.values())
        relation_type_aliases = {
            alias: _normalize(_local_name(definition.uri))
            for definition in item.relations
            for alias in (
                _normalize(_local_name(definition.uri)),
                _normalize(definition.label),
            )
        }
        relation_aliases: dict[str, OntologyRelationDef] = {}
        for definition in item.relations:
            relation_aliases[_normalize(_local_name(definition.uri))] = definition
            relation_aliases[_normalize(definition.label)] = definition
        entity_types = {
            entity.id: _normalize(_local_name(entity.entity_type)) for entity in entities
        }
        valid_relations = 0
        for relation in relations:
            relation_definition = relation_aliases.get(
                _normalize(_local_name(relation.predicate))
            ) or relation_aliases.get(_normalize(relation.predicate))
            if relation_definition is None:
                continue
            source_type = entity_types.get(relation.source_entity_id)
            target_type = entity_types.get(relation.target_entity_id)
            domain = {_canonical_type_name(value) for value in relation_definition.domain}
            range_ = {_canonical_type_name(value) for value in relation_definition.range}
            if (
                source_type
                and target_type
                and (not domain or _canonical_type_name(source_type) in domain)
                and (not range_ or _canonical_type_name(target_type) in range_)
            ):
                valid_relations += 1

        usage_records = list(provider_usage[provider_usage_start:])
        usage_records.extend(relation_usage[relation_usage_start:])
        prompt_tokens = sum(record.get("prompt_tokens") or 0 for record in usage_records)
        completion_tokens = sum(record.get("completion_tokens") or 0 for record in usage_records)
        prompt_measurements = sum(
            record.get("prompt_tokens") is not None for record in usage_records
        )
        completion_measurements = sum(
            record.get("completion_tokens") is not None for record in usage_records
        )
        token_sources = sorted(
            {
                record.get("source", "unavailable")
                for record in usage_records
                if record.get("source") != "unavailable"
            }
        )

        return {
            "item_id": item.id,
            "source_document": item.source_document,
            "source_reference": item.source_reference,
            "text_origin": item.text_origin,
            "variant_of": item.variant_of,
            "repeat": repeat,
            "duration_seconds": elapsed,
            "errors": errors,
            "entity_tp": entity_tp,
            "entity_predicted": len(entity_predictions),
            "entity_gold": len(entity_gold),
            "triple_tp": len(triple_gold & predicted_triples),
            "triple_predicted": len(predicted_triples),
            "triple_gold": len(triple_gold),
            "decision_candidates": (
                {
                    "count": len(candidate_keys),
                    "gold_covered": len(triple_gold & candidate_keys),
                    "gold": len(triple_gold),
                }
                if candidate_keys is not None
                else None
            ),
            "attribute_tp": len(attribute_gold & attribute_predictions),
            "attribute_predicted": len(attribute_predictions),
            "attribute_gold": len(attribute_gold),
            "predicted_entities": len(entities),
            "predicted_triples": len(relations),
            "gold_entities": len(item.gold_entities),
            "gold_triples": len(item.gold_triples),
            "predicted_class_types": sorted(
                {
                    class_aliases.get(
                        _normalize(_local_name(entity.entity_type)),
                        _normalize(_local_name(entity.entity_type)),
                    )
                    for entity in entities
                }
            ),
            "predicted_relation_types": sorted(
                {
                    relation_type_aliases.get(
                        _normalize(_local_name(relation.predicate)),
                        _normalize(_local_name(relation.predicate)),
                    )
                    for relation in relations
                }
            ),
            "ontology_class_types": sorted(class_types),
            "ontology_relation_types": sorted(
                {
                    alias
                    for definition in item.relations
                    for alias in (
                        _normalize(_local_name(definition.uri)),
                        _normalize(definition.label),
                    )
                }
            ),
            "predicted_attribute_count": len(attribute_predictions),
            "gold_attribute_count": len(attribute_gold),
            "valid_relations": valid_relations,
            "predicted_relation_count": len(relations),
            "relation_evidence_entity_covered": evidence_covered,
            "relation_evidence_count": evidence_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "token_records": max(prompt_measurements, completion_measurements),
            "prompt_token_measurements": prompt_measurements,
            "completion_token_measurements": completion_measurements,
            "token_sources": token_sources,
            "predictions": {
                "entities": [
                    {
                        "id": entity.id,
                        "text": entity.label,
                        "type": entity.entity_type,
                        "confidence": entity.confidence,
                        "attributes": entity.properties,
                    }
                    for entity in entities
                ],
                "triples": [
                    {
                        "subject": predicted_labels.get(
                            relation.source_entity_id, relation.source_entity_id
                        ),
                        "predicate": relation.predicate,
                        "object": predicted_labels.get(
                            relation.target_entity_id, relation.target_entity_id
                        ),
                        "confidence": relation.confidence,
                        "evidence": [asdict(evidence) for evidence in relation.evidence],
                    }
                    for relation in relations
                ],
            },
        }

    @staticmethod
    def _candidate_metrics(results: list[dict[str, Any]]) -> dict[str, Any] | None:
        measured = [
            result["decision_candidates"]
            for result in results
            if result.get("decision_candidates") is not None
        ]
        if not measured:
            return None
        gold = sum(item["gold"] for item in measured)
        covered = sum(item["gold_covered"] for item in measured)
        return {
            "count": sum(item["count"] for item in measured),
            "gold_covered": covered,
            "gold": gold,
            "recall": covered / gold if gold else None,
            "measured_trials": len(measured),
        }

    @staticmethod
    def _bootstrap_f1(
        results: list[dict[str, Any]],
        true_positive_field: str,
        iterations: int = 2000,
    ) -> dict[str, float]:
        """Calculate a deterministic item-bootstrap 95% interval for micro F1."""
        if not results:
            return {"lower": 0.0, "upper": 0.0}
        groups: dict[str, list[dict[str, Any]]] = {}
        for result in results:
            group = str(result.get("variant_of") or result["item_id"])
            groups.setdefault(group, []).append(result)
        group_values = list(groups.values())
        generator = random.Random(0)
        scores = []
        predicted_field = (
            "entity_predicted" if true_positive_field == "entity_tp" else "triple_predicted"
        )
        gold_field = "entity_gold" if true_positive_field == "entity_tp" else "triple_gold"
        for _ in range(iterations):
            sampled_groups = [generator.choice(group_values) for _ in group_values]
            sample = [result for group in sampled_groups for result in group]
            true_positive = sum(result[true_positive_field] for result in sample)
            predicted = sum(result[predicted_field] for result in sample)
            gold = sum(result[gold_field] for result in sample)
            precision = true_positive / predicted if predicted else float(gold == 0)
            recall = true_positive / gold if gold else float(predicted == 0)
            scores.append(
                2 * precision * recall / (precision + recall) if precision + recall else 0.0
            )
        scores.sort()
        return {
            "lower": scores[int(0.025 * (len(scores) - 1))],
            "upper": scores[int(0.975 * (len(scores) - 1))],
        }

    @staticmethod
    def _percentile(values: list[float], quantile: float) -> float | None:
        if not values:
            return None
        index = min(len(values) - 1, max(0, int(round((len(values) - 1) * quantile))))
        return values[index]


def render_benchmark_markdown(
    result: dict[str, Any], json_filename: str, *, aggregate_only: bool = False
) -> str:
    """Render a concise, human-readable summary beside a benchmark JSON record."""
    run = result.get("run", {})
    dataset = result.get("dataset", {})
    aggregate = result.get("aggregate", {})
    latency = aggregate.get("latency_seconds", {})
    tokens = aggregate.get("tokens", {})
    richness = aggregate.get("kg_richness", {})
    entity_extractor = run.get("entity_extractor", "unknown")
    relation_extractor = run.get("relation_extractor", "unknown")
    generative_path = entity_extractor in {"llm", "rules-first"} or relation_extractor in {
        "llm",
        "rules-first",
    }
    if "rules-first" in {entity_extractor, relation_extractor}:
        generation_usage = "conditional fallback; may be skipped per item"
    elif generative_path:
        generation_usage = "used"
    else:
        generation_usage = "not invoked by this path"

    def interval(name: str) -> str:
        bounds = aggregate.get("quality_ci95", {}).get(name)
        if not bounds:
            return "-"
        return f"[{bounds['lower']:.3f}, {bounds['upper']:.3f}]"

    def metric_line(name: str, confidence_interval: str) -> str:
        metric = aggregate.get(f"{name}_metrics", {})
        return (
            f"| {name.title()} | {metric.get('precision', 0):.3f} | "
            f"{metric.get('recall', 0):.3f} | {metric.get('f1', 0):.3f} | "
            f"{confidence_interval} |"
        )

    def token_count(value: int | None) -> str:
        return f"{value:,}" if value is not None else "not reported"

    lines = [
        f"# KG extraction benchmark: {run.get('llm_model', 'unknown model')}",
        "",
        f"- **Run:** {run.get('created_at', 'unknown')}",
        f"- **Dataset:** {dataset.get('name', 'unknown')} "
        f"({dataset.get('version', 'unknown')}, {dataset.get('split', 'unknown')}; "
        f"{dataset.get('item_count', 0)} items; "
        f"{', '.join(dataset.get('languages', [])) or 'languages unknown'}; "
        f"repeats {dataset.get('repeats', 'not recorded')})",
        f"- **Configured backend/model:** {run.get('llm_backend', 'unknown')} / "
        f"{run.get('llm_model', 'unknown')}",
        f"- **Extractors:** entities `{entity_extractor}`, relations `{relation_extractor}`",
        f"- **Generative LLM stage:** {generation_usage}",
        f"- **Decision evidence judge:** {run.get('decision_judge') or 'disabled'}",
        f"- **Model revision:** {run.get('model_revision', 'unspecified')}",
        f"- **Dataset SHA-256:** `{run.get('dataset_sha256', 'unknown')}`",
        "",
        "## Quality",
        "",
        "| Metric | Precision | Recall | F1 | Bootstrap 95% CI |",
        "|---|---:|---:|---:|---:|",
        metric_line("entity", interval("entity_f1")),
        metric_line("triple", interval("triple_f1")),
        metric_line("attribute", "-"),
        "",
        "## Runtime and usage",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| Median latency/item | {latency.get('median', 0):.2f} s |",
        f"| P95 latency/item | {latency.get('p95', 0):.2f} s |",
        f"| Mean latency/item | {latency.get('mean', 0):.2f} s |",
        f"| Prompt tokens | {token_count(tokens.get('prompt'))} |",
        f"| Completion tokens | {token_count(tokens.get('completion'))} |",
        f"| Total tokens | {token_count(tokens.get('total'))} |",
        f"| Token source | {tokens.get('source', 'unavailable')} "
        f"({tokens.get('calls', 0)} calls) |",
        f"| Errors | {aggregate.get('errors', 0)} |",
        "",
        "## Knowledge-graph coverage",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| Predicted entities / gold | "
        f"{aggregate.get('entity_counts', {}).get('predicted', 0)} / "
        f"{aggregate.get('entity_counts', {}).get('gold', 0)} |",
        f"| Predicted triples / gold | "
        f"{aggregate.get('triple_counts', {}).get('predicted', 0)} / "
        f"{aggregate.get('triple_counts', {}).get('gold', 0)} |",
        f"| Ontology class coverage | {richness.get('ontology_class_coverage', 0):.1%} |",
        f"| Ontology relation coverage | {richness.get('ontology_relation_coverage', 0):.1%} |",
        f"| Domain/range-valid relations | "
        f"{richness.get('ontology_domain_range_validity', 0):.1%} |",
        f"| Predicted / gold attributes | "
        f"{richness.get('predicted_attributes', 0)} / "
        f"{richness.get('gold_attributes', 0)} |",
        "",
    ]
    candidates = aggregate.get("decision_candidates")
    if candidates:
        recall = candidates["recall"]
        lines.extend(
            [
                "",
                "## Decision candidate coverage",
                "",
                f"- Candidates: {candidates['count']}; gold covered: "
                f"{candidates['gold_covered']}/{candidates['gold']}.",
                f"- Candidate recall: {recall:.3f}."
                if recall is not None
                else "- Candidate recall: undefined (no gold triples).",
                "- This bounds decision-stage recall; missing proposals cannot be "
                "recovered by judging.",
            ]
        )

    if run.get("decision_model"):
        lines.extend([f"- **Decision model:** {run['decision_model']}", ""])

    probe = result.get("unlabeled_corpus_probe")
    if probe:
        probe_entities = probe.get("entities_predicted", "not reported")
        probe_relations = probe.get("triples_predicted", "not reported")
        lines.extend(
            [
                "## Unlabeled source-document probe",
                "",
                "This is an exploratory extraction count, not an accuracy score; "
                "the passages do not have exhaustive gold annotations.",
                "",
                f"- Entities: {probe_entities}",
                f"- Triples: {probe_relations}",
                f"- Elapsed: {probe.get('elapsed_seconds', 0):.2f} s",
                "",
            ]
        )

    lines.extend(
        [
            "## Interpretation",
            "",
            "This is a development-pilot result, not a held-out or independently "
            "expert-reviewed model ranking. Read quality alongside richness, "
            "latency, and token usage; do not select a production winner from this "
            "run alone.",
            "",
            (
                f"Aggregate-only measurements: [{json_filename}]({json_filename}). "
                "Source passages, predictions, and error messages are retained locally, "
                "not published."
                if aggregate_only
                else "Raw per-item predictions and measurements: "
                f"[{json_filename}]({json_filename})"
            ),
            "",
        ]
    )
    return "\n".join(lines)
