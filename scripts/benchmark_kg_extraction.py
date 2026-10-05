#!/usr/bin/env python3
"""Benchmark ontology-grounded KG extractors against a reviewed gold dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _gpu_snapshot() -> list[dict[str, Any]]:
    """Return a best-effort GPU memory snapshot without requiring NVML bindings."""
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    snapshots = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3:
            name, total, used = parts
            snapshots.append(
                {
                    "name": name,
                    "memory_total_mib": int(total),
                    "memory_used_mib": int(used),
                }
            )
    return snapshots


def _write_report_index(directory: Path) -> Path:
    """Refresh the comparison index for extraction benchmark JSON records."""
    report_paths = sorted(directory.glob("kg-extraction-*.json"))
    lines = [
        "# KG extraction benchmark reports",
        "",
        "Each Markdown report links to its raw JSON record, including per-item "
        "predictions and measurements.",
        "",
        "These are small development-pilot results, not independently reviewed "
        "or held-out scores. Do not use them to declare a production winner.",
        "",
        "| Report | Configuration | Entity F1 | Triple F1 | Attribute F1 | "
        "Median/item | Total tokens |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for report_path in report_paths:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        run = report["run"]
        aggregate = report["aggregate"]
        latency = aggregate["latency_seconds"]
        tokens = aggregate["tokens"]
        total_tokens = tokens["total"]
        total_text = f"{total_tokens:,}" if total_tokens is not None else "not reported"
        entity_extractor = run.get("entity_extractor", "unknown")
        relation_extractor = run.get("relation_extractor", "unknown")
        if run.get("decision_model"):
            model = run["decision_model"]
        elif entity_extractor in {"llm", "rules-first"} or relation_extractor in {
            "llm",
            "rules-first",
        }:
            model = run.get("llm_model", "unknown")
        else:
            model = "no generative LLM"
        configuration = f"`{entity_extractor} -> {relation_extractor}` ({model})"
        lines.append(
            f"| [{report_path.stem}]({report_path.with_suffix('.md').name}) | "
            f"{configuration} | "
            f"{aggregate['entity_metrics']['f1']:.3f} | "
            f"{aggregate['triple_metrics']['f1']:.3f} | "
            f"{aggregate['attribute_metrics']['f1']:.3f} | "
            f"{latency['median']:.2f} s | {total_text} |"
        )
    index_path = directory / "README.md"
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index_path


def _run_corpus_probe(
    dataset: Any,
    entity_extractor: Any,
    relation_extractor: Any,
    provider: Any,
    corpus_dir: Path | None,
    document_limit: int,
    paragraph_limit: int,
) -> dict[str, Any]:
    """Run unlabeled extraction on real project PDFs without claiming accuracy."""
    from kgbuilder.document.loaders import DocumentLoaderFactory

    if document_limit < 1 or paragraph_limit < 1:
        raise ValueError("Corpus document and paragraph limits must be positive")
    if corpus_dir is None:
        sources = list(
            dict.fromkeys(item.source_document for item in dataset.items if item.source_document)
        )
        source_paths = [Path(source) for source in sources][:document_limit]
    else:
        source_paths = sorted(corpus_dir.glob("*.pdf"))[:document_limit]
    if not source_paths:
        raise ValueError("No source PDFs found for the corpus probe")

    trial_results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    started_all = time.perf_counter()
    for source_path in source_paths:
        if not source_path.is_file():
            raise FileNotFoundError(f"Corpus PDF does not exist: {source_path}")
        try:
            document = DocumentLoaderFactory.load(source_path)
        except Exception as exc:
            errors.append({"source_document": str(source_path), "message": str(exc)})
            continue
        paragraphs = [
            (index, paragraph.strip())
            for index, paragraph in enumerate(document.content.split("\n\n"))
            if len(paragraph.strip()) >= 150
            and len(paragraph.strip()) <= 2400
            and sum(character.isalpha() for character in paragraph) >= 80
        ]
        if not paragraphs:
            errors.append(
                {
                    "source_document": str(source_path),
                    "message": "No eligible text passages were extracted from this PDF.",
                }
            )
            continue
        stride = max(1, len(paragraphs) // paragraph_limit)
        selected = paragraphs[::stride][:paragraph_limit]
        for paragraph_index, text in selected:
            usage_history = getattr(provider, "usage_history", [])
            usage_start = len(usage_history)
            relation_usage = getattr(relation_extractor, "usage_history", [])
            relation_usage_start = len(relation_usage)
            started = time.perf_counter()
            passage_errors: list[dict[str, str]] = []
            entities = []
            relations = []
            try:
                entities = entity_extractor.extract(text, dataset.classes)
            except Exception as exc:
                passage_errors.append({"stage": "entity_extraction", "message": str(exc)})
            if not passage_errors:
                try:
                    relations = relation_extractor.extract(
                        text,
                        entities,
                        dataset.relations,
                    )
                except Exception as exc:
                    passage_errors.append({"stage": "relation_extraction", "message": str(exc)})
            elapsed = time.perf_counter() - started
            usage = list(usage_history[usage_start:])
            usage.extend(relation_usage[relation_usage_start:])
            trial_results.append(
                {
                    "source_document": str(source_path),
                    "paragraph_index": paragraph_index,
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "text_characters": len(text),
                    "duration_seconds": elapsed,
                    "errors": passage_errors,
                    "predictions": {
                        "entities": [
                            {
                                "text": entity.label,
                                "type": entity.entity_type,
                                "confidence": entity.confidence,
                                "attributes": entity.properties,
                            }
                            for entity in entities
                        ],
                        "triples": [
                            {
                                "subject": next(
                                    (
                                        entity.label
                                        for entity in entities
                                        if entity.id == relation.source_entity_id
                                    ),
                                    relation.source_entity_id,
                                ),
                                "predicate": relation.predicate,
                                "object": next(
                                    (
                                        entity.label
                                        for entity in entities
                                        if entity.id == relation.target_entity_id
                                    ),
                                    relation.target_entity_id,
                                ),
                                "confidence": relation.confidence,
                                "evidence": [
                                    evidence.model_dump()
                                    if hasattr(evidence, "model_dump")
                                    else {
                                        "source_id": evidence.source_id,
                                        "text_span": evidence.text_span,
                                        "confidence": evidence.confidence,
                                    }
                                    for evidence in relation.evidence
                                ],
                            }
                            for relation in relations
                        ],
                    },
                    "usage": usage,
                }
            )
    durations = [item["duration_seconds"] for item in trial_results]
    return {
        "scoring": "unlabeled-exploratory-only",
        "documents_requested": document_limit,
        "passages_per_document_limit": paragraph_limit,
        "passages_processed": len(trial_results),
        "documents": [str(path) for path in source_paths],
        "elapsed_seconds": time.perf_counter() - started_all,
        "latency_seconds": {
            "median": statistics.median(durations) if durations else None,
            "p95": sorted(durations)[int(0.95 * (len(durations) - 1))] if durations else None,
        },
        "entities_predicted": sum(len(item["predictions"]["entities"]) for item in trial_results),
        "triples_predicted": sum(len(item["predictions"]["triples"]) for item in trial_results),
        "errors": errors
        + [
            {"source_document": item["source_document"], **error}
            for item in trial_results
            for error in item["errors"]
        ],
        "trials": trial_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/evaluation/kg_extraction_benchmark_current_domain_v1.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("ollama", "vllm"))
    parser.add_argument("--model", help="Override LLM_MODEL for this run")
    parser.add_argument("--model-revision", help="Record a model revision or image digest")
    parser.add_argument("--ollama-base-url", help="Ollama URL, including a non-default test port")
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--top-p", type=float)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--entity-extractor",
        choices=("llm", "gliner", "rules", "rules-first"),
        default="llm",
    )
    parser.add_argument(
        "--relation-extractor",
        choices=("llm", "decision", "rules", "rules-first"),
        default="llm",
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--decision-model", default=os.getenv("OLLAMA_DECISION_MODEL", "tev1:0.8b"))
    parser.add_argument("--decision-base-url", help="Decision-model Ollama API URL")
    parser.add_argument("--decision-model-revision", default="unspecified")
    parser.add_argument(
        "--decision-judge",
        action="store_true",
        help="Filter proposed LLM/rule relations through TEV source-support decisions.",
    )
    parser.add_argument(
        "--corpus-probe",
        action="store_true",
        help="Also run an explicitly unlabeled exploratory probe over source PDFs.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        help="PDF directory for the exploratory probe; defaults to dataset source documents.",
    )
    parser.add_argument("--corpus-documents", type=int, default=3)
    parser.add_argument("--corpus-paragraphs", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least one")
    if args.warmup < 0:
        parser.error("--warmup must not be negative")
    if args.decision_judge and args.relation_extractor == "decision":
        parser.error("--decision-judge would redundantly rescore the decision extractor")
    if args.backend:
        os.environ["LLM_BACKEND"] = args.backend
    if args.model:
        os.environ["LLM_MODEL"] = args.model
    if args.ollama_base_url:
        os.environ["OLLAMA_URL"] = args.ollama_base_url
    os.environ["LLM_CACHE_ENABLED"] = "false"
    os.environ["LLM_SEED"] = str(args.seed)
    backend = os.getenv("LLM_BACKEND", "ollama").strip().lower()
    model = os.getenv("LLM_MODEL") or (
        (os.getenv("OLLAMA_MODEL") or "gemma4:e2b")
        if backend == "ollama"
        else (os.getenv("VLLM_MODEL") or "Qwen/Qwen3-8B")
    )
    if args.temperature is not None:
        os.environ["LLM_TEMPERATURE"] = str(args.temperature)
    elif not os.getenv("LLM_TEMPERATURE"):
        os.environ["LLM_TEMPERATURE"] = (
            "1.0" if "kolibri" in model.casefold() else "0.2" if backend == "vllm" else "0.7"
        )
    if args.top_p is not None:
        os.environ["LLM_TOP_P"] = str(args.top_p)
    elif not os.getenv("LLM_TOP_P"):
        os.environ["LLM_TOP_P"] = "0.97" if "kolibri" in model.casefold() else "0.9"
    if "kolibri" in model.casefold():
        if (
            not os.getenv("LLM_CHAT_TEMPLATE_KWARGS")
            or os.getenv("LLM_CHAT_TEMPLATE_KWARGS") == "{}"
        ):
            os.environ["LLM_CHAT_TEMPLATE_KWARGS"] = '{"enable_thinking": false}'

    from kgbuilder.api.dependencies import get_llm_provider
    from kgbuilder.evaluation.kg_extraction_benchmark import (
        KGExtractionBenchmarkDataset,
        KGExtractionBenchmarkRunner,
        render_benchmark_markdown,
    )
    from kgbuilder.extraction.decision_model import (
        DecisionJudgedRelationExtractor,
        DecisionModelRelationExtractor,
        OllamaDecisionClient,
    )
    from kgbuilder.extraction.ensemble import TieredExtractor, TieredRelationExtractor
    from kgbuilder.extraction.entity import LLMEntityExtractor
    from kgbuilder.extraction.gliner import GLiNEREntityExtractor
    from kgbuilder.extraction.relation import LLMRelationExtractor
    from kgbuilder.extraction.rules import RuleBasedExtractor, RuleBasedRelationExtractor

    dataset, dataset_sha256 = KGExtractionBenchmarkDataset.load(args.dataset)
    provider = get_llm_provider()
    llm_entity_extractor = LLMEntityExtractor(llm_provider=provider)
    if args.entity_extractor == "llm":
        entity_extractor: Any = llm_entity_extractor
    elif args.entity_extractor == "gliner":
        entity_extractor = GLiNEREntityExtractor()
    elif args.entity_extractor == "rules":
        entity_extractor = RuleBasedExtractor()
    else:
        entity_extractor = TieredExtractor(
            rule_extractor=RuleBasedExtractor(),
            llm_extractor=llm_entity_extractor,
        )

    llm_relation_extractor = LLMRelationExtractor(llm_provider=provider)
    if args.relation_extractor == "llm":
        relation_extractor: Any = llm_relation_extractor
    else:
        if args.relation_extractor == "decision":
            decision_client = OllamaDecisionClient(
                model=args.decision_model,
                base_url=(
                    args.decision_base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
                ),
            )
            relation_extractor = DecisionModelRelationExtractor(decision_client)
        elif args.relation_extractor == "rules":
            relation_extractor = RuleBasedRelationExtractor()
        else:
            relation_extractor = TieredRelationExtractor(
                rule_extractor=RuleBasedRelationExtractor(),
                llm_extractor=llm_relation_extractor,
            )
    if args.decision_judge:
        judge = DecisionModelRelationExtractor(
            OllamaDecisionClient(
                model=args.decision_model,
                base_url=args.decision_base_url
                or os.getenv("OLLAMA_URL", "http://localhost:11434"),
            )
        )
        relation_extractor = DecisionJudgedRelationExtractor(relation_extractor, judge)

    runner = KGExtractionBenchmarkRunner(
        entity_extractor=entity_extractor,
        relation_extractor=relation_extractor,
        llm_provider=provider,
    )
    gpu_before = _gpu_snapshot()
    result = runner.run(
        dataset,
        repeats=args.repeats,
        warmup_count=args.warmup,
    )
    if args.corpus_probe:
        result["unlabeled_corpus_probe"] = _run_corpus_probe(
            dataset,
            entity_extractor,
            relation_extractor,
            provider,
            args.corpus_dir,
            args.corpus_documents,
            args.corpus_paragraphs,
        )
    result["run"] = {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_sha256": dataset_sha256,
        "llm_backend": os.getenv("LLM_BACKEND", "ollama"),
        "llm_model": provider.model_name,
        "model_revision": args.model_revision or os.getenv("MODEL_REVISION") or "unspecified",
        "entity_extractor": args.entity_extractor,
        "relation_extractor": args.relation_extractor,
        "temperature": getattr(provider, "temperature", None),
        "top_p": getattr(provider, "top_p", None),
        "seed": args.seed,
        "response_cache_enabled": False,
        "gpu_memory_snapshot_before": gpu_before,
        "gpu_memory_snapshot_after": _gpu_snapshot(),
        "decision_model": (
            args.decision_model
            if args.relation_extractor == "decision" or args.decision_judge
            else None
        ),
        "decision_judge": args.decision_model if args.decision_judge else None,
        "decision_model_revision": args.decision_model_revision,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(
        render_benchmark_markdown(result, args.output.name),
        encoding="utf-8",
    )
    index_path = _write_report_index(args.output.parent)
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))
    print(f"Saved benchmark record to {args.output}")
    print(f"Saved Markdown summary to {markdown_path}")
    print(f"Updated report index at {index_path}")


if __name__ == "__main__":
    main()
