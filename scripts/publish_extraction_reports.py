#!/usr/bin/env python3
"""Export aggregate benchmark records without source text, predictions, or credentials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from kgbuilder.evaluation.kg_extraction_benchmark import render_benchmark_markdown


def public_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Return allowlisted numeric metrics and reproducibility metadata."""
    run_fields = (
        "created_at",
        "dataset_sha256",
        "llm_backend",
        "llm_model",
        "model_revision",
        "entity_extractor",
        "relation_extractor",
        "temperature",
        "top_p",
        "seed",
        "response_cache_enabled",
        "decision_model",
        "decision_judge",
        "decision_model_revision",
        "gpu_memory_snapshot_before",
        "gpu_memory_snapshot_after",
    )
    dataset_fields = (
        "name",
        "version",
        "split",
        "item_count",
        "languages",
        "repeats",
        "trial_count",
    )
    summary: dict[str, Any] = {
        "publication": "aggregate-only; source text and raw predictions intentionally excluded",
        "run": {key: report["run"][key] for key in run_fields if key in report["run"]},
        "dataset": {
            key: report["dataset"][key] for key in dataset_fields if key in report["dataset"]
        },
        "aggregate": report["aggregate"],
    }
    probe = report.get("unlabeled_corpus_probe")
    if probe:
        fields = (
            "scoring",
            "documents_requested",
            "passages_per_document_limit",
            "passages_processed",
            "elapsed_seconds",
            "latency_seconds",
            "entities_predicted",
            "triples_predicted",
        )
        summary["unlabeled_corpus_probe"] = {
            **{key: probe[key] for key in fields if key in probe},
            "documents_processed": len(probe.get("documents", [])),
            "error_count": len(probe.get("errors", [])),
            "tokens": sum(
                record.get("total_tokens") or 0
                for trial in probe.get("trials", [])
                for record in trial.get("usage", [])
            )
            if any(
                record.get("total_tokens") is not None
                for trial in probe.get("trials", [])
                for record in trial.get("usage", [])
            )
            else None,
        }
    return summary


def main() -> None:
    """Publish JSON/Markdown aggregates and a comparison index."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("Planning/benchmarks"))
    args = parser.parse_args()
    paths = sorted(args.input_dir.glob("kg-extraction-*.json"))
    if not paths:
        parser.error("No kg-extraction-*.json reports found in --input-dir")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Published extraction benchmark measurements",
        "",
        "Aggregate-only exports. Raw source passages and predictions remain local.",
        "These development examples are not independently reviewed or held out.",
        "",
        "| Report | Entity F1 | Triple F1 | Tokens | Median/item | Errors |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for path in paths:
        summary = public_summary(json.loads(path.read_text(encoding="utf-8")))
        output = args.output_dir / path.name
        output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        output.with_suffix(".md").write_text(
            render_benchmark_markdown(summary, output.name, aggregate_only=True), encoding="utf-8"
        )
        aggregate = summary["aggregate"]
        tokens = aggregate["tokens"]["total"]
        lines.append(
            f"| [{path.stem}]({path.stem}.md) | "
            f"{aggregate['entity_metrics']['f1']:.3f} | {aggregate['triple_metrics']['f1']:.3f} | "
            f"{tokens if tokens is not None else 'not reported'} | "
            f"{aggregate['latency_seconds']['median']:.2f} s | {aggregate['errors']} |"
        )
    (args.output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
