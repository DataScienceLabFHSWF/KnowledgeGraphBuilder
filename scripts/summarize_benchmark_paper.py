#!/usr/bin/env python3
"""Summarize benchmark-paper experiment results from run metadata.

This script is intended for post-hoc paper analysis after a long benchmark
finishes. It reads the per-run ``run_metadata.json`` artifacts, aggregates the
KG-side metrics that the generic report pipeline currently underuses, and writes
compact JSON/CSV outputs for downstream reporting.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from typing import Any


DEFAULT_EXPERIMENT_ID = "exp_20260422_134930_4b044a48"
DEFAULT_RESULTS_DIR = Path("experiment_results/benchmark_paper")
DEFAULT_OUTPUT_PREFIX = "paper_summary"


@dataclass
class RunRecord:
    """Normalized per-run record extracted from run metadata."""

    run_id: str
    variant_name: str
    run_number: int
    status: str
    error: str | None
    nodes: int
    edges: int
    build_time_seconds: float
    final_coverage: float
    total_iterations: int
    total_entities: int
    total_relations: int
    shacl_score: float | None
    combined_score: float | None
    entity_f1: float | None
    relation_f1: float | None
    overall_f1: float | None
    discovery_iterations: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize benchmark-paper run metadata")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory containing run folders and experiment metadata",
    )
    parser.add_argument(
        "--experiment-id",
        default=DEFAULT_EXPERIMENT_ID,
        help="Experiment ID prefix to summarize",
    )
    parser.add_argument(
        "--output-prefix",
        default=DEFAULT_OUTPUT_PREFIX,
        help="Output filename prefix inside the reports directory",
    )
    return parser.parse_args()


def _safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def _safe_std(values: list[float]) -> float:
    return stdev(values) if len(values) > 1 else 0.0


def _load_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return json.load(handle)


def _discover_run_files(results_dir: Path, experiment_id: str) -> list[Path]:
    return sorted(results_dir.glob(f"{experiment_id}_*/run_metadata.json"))


def _load_runs(results_dir: Path, experiment_id: str) -> list[RunRecord]:
    run_files = _discover_run_files(results_dir, experiment_id)
    if not run_files:
        raise FileNotFoundError(
            f"No run_metadata.json files found for experiment '{experiment_id}' in {results_dir}"
        )

    runs: list[RunRecord] = []
    for run_file in run_files:
        payload = _load_json(run_file)
        kg_metrics = payload.get("kg_metrics", {})
        eval_metrics = payload.get("eval_metrics", {})
        shacl_metrics = kg_metrics.get("shacl", {})
        runs.append(
            RunRecord(
                run_id=payload["run_id"],
                variant_name=payload["variant_name"],
                run_number=int(payload.get("run_number", 0)),
                status=payload.get("status", "unknown"),
                error=payload.get("error"),
                nodes=int(kg_metrics.get("nodes", 0)),
                edges=int(kg_metrics.get("edges", 0)),
                build_time_seconds=float(kg_metrics.get("build_time_seconds", 0.0)),
                final_coverage=float(kg_metrics.get("final_coverage", 0.0)),
                total_iterations=int(kg_metrics.get("total_discovery_iterations", 0)),
                total_entities=int(kg_metrics.get("total_entities_discovered", 0)),
                total_relations=int(kg_metrics.get("total_relations_extracted", 0)),
                shacl_score=(
                    float(shacl_metrics["shacl_score"])
                    if shacl_metrics.get("shacl_score") is not None
                    else None
                ),
                combined_score=(
                    float(shacl_metrics["combined_score"])
                    if shacl_metrics.get("combined_score") is not None
                    else None
                ),
                entity_f1=(
                    float(eval_metrics["entities_f1"])
                    if eval_metrics.get("entities_f1") is not None
                    else None
                ),
                relation_f1=(
                    float(eval_metrics["relations_f1"])
                    if eval_metrics.get("relations_f1") is not None
                    else None
                ),
                overall_f1=(
                    float(eval_metrics["f1_score"])
                    if eval_metrics.get("f1_score") is not None
                    else None
                ),
                discovery_iterations=list(kg_metrics.get("discovery_iterations", [])),
            )
        )
    return runs


def _aggregate_variant(rows: list[RunRecord]) -> dict[str, Any]:
    numeric_fields = {
        "nodes": [float(row.nodes) for row in rows],
        "edges": [float(row.edges) for row in rows],
        "build_time_seconds": [row.build_time_seconds for row in rows],
        "final_coverage": [row.final_coverage for row in rows],
        "total_entities": [float(row.total_entities) for row in rows],
        "total_relations": [float(row.total_relations) for row in rows],
        "total_iterations": [float(row.total_iterations) for row in rows],
        "shacl_score": [row.shacl_score for row in rows if row.shacl_score is not None],
        "overall_f1": [row.overall_f1 for row in rows if row.overall_f1 is not None],
        "entity_f1": [row.entity_f1 for row in rows if row.entity_f1 is not None],
        "relation_f1": [row.relation_f1 for row in rows if row.relation_f1 is not None],
    }

    metrics: dict[str, Any] = {
        "runs": len(rows),
        "clean_runs": sum(1 for row in rows if row.status == "completed" and not row.error),
    }
    for field_name, values in numeric_fields.items():
        metrics[field_name] = {
            "mean": round(_safe_mean(values), 4),
            "std": round(_safe_std(values), 4),
            "values": [round(v, 4) for v in values],
        }

    iteration_summary: dict[str, dict[str, float]] = {}
    max_iteration = max((len(row.discovery_iterations) for row in rows), default=0)
    for iteration_index in range(max_iteration):
        coverage_values: list[float] = []
        cumulative_entity_values: list[float] = []
        new_entity_values: list[float] = []
        for row in rows:
            if iteration_index >= len(row.discovery_iterations):
                continue
            iteration = row.discovery_iterations[iteration_index]
            coverage_values.append(float(iteration.get("coverage", 0.0)))
            cumulative_entity_values.append(float(iteration.get("entities_cumulative", 0.0)))
            new_entity_values.append(float(iteration.get("entities_new", 0.0)))
        iteration_summary[str(iteration_index + 1)] = {
            "coverage_mean": round(_safe_mean(coverage_values), 4),
            "entities_cumulative_mean": round(_safe_mean(cumulative_entity_values), 4),
            "entities_new_mean": round(_safe_mean(new_entity_values), 4),
        }

    metrics["iteration_summary"] = iteration_summary
    return metrics


def _compute_deltas(summary: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    deltas: dict[str, dict[str, float]] = {}
    baseline = summary.get("A_single_pass")
    if baseline is None:
        return deltas

    baseline_nodes = baseline["nodes"]["mean"]
    baseline_coverage = baseline["final_coverage"]["mean"]
    baseline_time = baseline["build_time_seconds"]["mean"]

    for variant_name, metrics in summary.items():
        deltas[variant_name] = {
            "vs_A_nodes_abs": round(metrics["nodes"]["mean"] - baseline_nodes, 4),
            "vs_A_nodes_pct": round(
                100.0 * (metrics["nodes"]["mean"] - baseline_nodes) / baseline_nodes,
                2,
            ) if baseline_nodes else 0.0,
            "vs_A_coverage_abs": round(
                metrics["final_coverage"]["mean"] - baseline_coverage,
                4,
            ),
            "vs_A_time_ratio": round(
                metrics["build_time_seconds"]["mean"] / baseline_time,
                4,
            ) if baseline_time else 0.0,
        }
    return deltas


def _write_csv(path: Path, summary: dict[str, dict[str, Any]], deltas: dict[str, dict[str, float]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "variant",
                "runs",
                "nodes_mean",
                "nodes_std",
                "coverage_mean",
                "coverage_std",
                "time_mean_sec",
                "time_std_sec",
                "relations_mean",
                "edges_mean",
                "shacl_mean",
                "vs_A_nodes_pct",
                "vs_A_coverage_abs",
                "vs_A_time_ratio",
            ]
        )
        for variant_name in sorted(summary):
            metrics = summary[variant_name]
            delta = deltas.get(variant_name, {})
            writer.writerow(
                [
                    variant_name,
                    metrics["runs"],
                    metrics["nodes"]["mean"],
                    metrics["nodes"]["std"],
                    metrics["final_coverage"]["mean"],
                    metrics["final_coverage"]["std"],
                    metrics["build_time_seconds"]["mean"],
                    metrics["build_time_seconds"]["std"],
                    metrics["total_relations"]["mean"],
                    metrics["edges"]["mean"],
                    metrics["shacl_score"]["mean"],
                    delta.get("vs_A_nodes_pct", 0.0),
                    delta.get("vs_A_coverage_abs", 0.0),
                    delta.get("vs_A_time_ratio", 0.0),
                ]
            )


def main() -> int:
    args = parse_args()
    runs = _load_runs(args.results_dir, args.experiment_id)
    clean_runs = [run for run in runs if run.status == "completed" and not run.error]
    if not clean_runs:
        raise RuntimeError("No clean completed runs found to summarize")

    grouped: dict[str, list[RunRecord]] = {}
    for run in clean_runs:
        grouped.setdefault(run.variant_name, []).append(run)

    summary = {
        variant_name: _aggregate_variant(rows)
        for variant_name, rows in sorted(grouped.items())
    }
    deltas = _compute_deltas(summary)

    output_dir = args.results_dir / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{args.output_prefix}.json"
    csv_path = output_dir / f"{args.output_prefix}.csv"

    output_payload = {
        "experiment_id": args.experiment_id,
        "results_dir": str(args.results_dir),
        "total_runs": len(runs),
        "clean_runs": len(clean_runs),
        "variants": summary,
        "deltas_vs_A_single_pass": deltas,
        "caveats": [
            "Edges and extracted relations are zero in the run metadata for all variants.",
            "Gold-standard F1 metrics are zero across all runs, so conclusions should rely on KG construction metrics rather than extraction accuracy.",
            "SHACL scores are uniformly 1.0 and do not differentiate variants in this benchmark run.",
        ],
    }

    json_path.write_text(json.dumps(output_payload, indent=2))
    _write_csv(csv_path, summary, deltas)

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())