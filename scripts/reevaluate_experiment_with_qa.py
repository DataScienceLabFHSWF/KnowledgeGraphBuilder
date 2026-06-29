#!/usr/bin/env python
"""Re-evaluate completed experiment runs with a QA dataset and regenerate reports.

This script is designed for post-hoc evaluation after long benchmark runs finish.
It reads existing run metadata, computes QA metrics per run (scored questions),
updates run metadata files, and regenerates markdown/json/html reports.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from kgbuilder.experiment import (
    ConfigRunner,
    ConfigVariant,
    ExperimentAnalyzer,
    ExperimentConfig,
    ExperimentManager,
    ExperimentReport,
    ExperimentReporter,
    ExperimentResults,
    ExperimentRun,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-evaluate existing experiment with QA benchmark")
    parser.add_argument("--metadata", type=Path, required=True, help="Path to experiment metadata JSON")
    parser.add_argument("--qa-dataset", type=Path, required=True, help="Path to QA dataset JSON")
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="Skip per-run QA querying and only regenerate analysis/report from existing metadata.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["markdown", "json", "html"],
        choices=["markdown", "json", "html"],
        help="Report formats to regenerate",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w") as f:
        json.dump(data, f, indent=2, default=str)


def _variant_lookup(config: ExperimentConfig) -> dict[str, ConfigVariant]:
    return {variant.name: variant for variant in config.variants}


def _collect_analysis(results: ExperimentResults) -> dict[str, Any]:
    analyzer = ExperimentAnalyzer(results)
    preferred_metrics = ["accuracy", "f1_score", "coverage", "entities_f1", "relations_f1"]

    metrics: set[str] = set()
    for run in results.runs:
        eval_metrics = run.eval_metrics or {}
        for metric in preferred_metrics:
            if isinstance(eval_metrics.get(metric), (int, float)):
                metrics.add(metric)

    convergence: dict[str, Any] = {}
    comparison: dict[str, Any] = {}
    for metric in sorted(metrics):
        convergence[metric] = analyzer.analyze_convergence(metric)
        comparison[metric] = analyzer.compare_variants(metric)

    return {
        "convergence": convergence,
        "comparison": comparison,
        "aggregate": analyzer.get_summary(),
    }


def main() -> int:
    args = parse_args()
    metadata = _load_json(args.metadata)

    output_dir = Path(metadata.get("config", {}).get("output_dir", args.metadata.parent))
    config = ExperimentConfig.from_dict(metadata.get("config", {}))
    config.output_dir = str(output_dir)
    config.evaluation.qa_dataset_path = str(args.qa_dataset)

    runner = ConfigRunner(output_dir, config=config)
    variants_by_name = _variant_lookup(config)

    updated_runs: list[ExperimentRun] = []
    updated_files = 0

    for run_id in metadata.get("run_ids", []):
        run_meta_path = output_dir / run_id / "run_metadata.json"
        if not run_meta_path.exists():
            continue

        run_data = _load_json(run_meta_path)
        variant_name = run_data.get("variant_name", "unknown")
        variant = variants_by_name.get(variant_name, ConfigVariant(name=variant_name, description=""))

        existing_eval = dict(run_data.get("eval_metrics", {}))
        if not args.skip_eval:
            qa_eval = runner._evaluate_with_qa_dataset(run_id)
            if qa_eval:
                existing_eval.update(qa_eval)
                run_data["eval_metrics"] = existing_eval
                run_data["accuracy"] = existing_eval.get("accuracy", 0.0)
                run_data["f1_score"] = existing_eval.get("f1_score", 0.0)
                run_data["coverage"] = existing_eval.get("coverage", 0.0)
                _save_json(run_meta_path, run_data)
                updated_files += 1

        run = ExperimentRun(
            run_id=run_data.get("run_id", run_id),
            variant=variant,
            variant_name=variant_name,
            run_number=int(run_data.get("run_number", 1)),
            status=run_data.get("status", "completed"),
            start_time=run_data.get("start_time"),
            end_time=run_data.get("end_time"),
            duration_seconds=float(run_data.get("duration_seconds", 0.0)),
            kg_metrics=run_data.get("kg_metrics", {}),
            eval_metrics=run_data.get("eval_metrics", {}),
            error=run_data.get("error"),
            metadata=run_data.get("metadata", {}),
        )

        run.accuracy = float(run.eval_metrics.get("accuracy", 0.0))
        run.f1_score = float(run.eval_metrics.get("f1_score", 0.0))
        run.coverage = float(run.eval_metrics.get("coverage", 0.0))
        run.kg_nodes = int(run.kg_metrics.get("nodes", 0))
        run.kg_edges = int(run.kg_metrics.get("edges", 0))

        updated_runs.append(run)

    results = ExperimentResults(config=config)
    results.runs = updated_runs
    results.start_time = datetime.fromisoformat(metadata["started_at"]) if metadata.get("started_at") else None
    results.end_time = datetime.now()
    results.completed_runs = sum(1 for run in updated_runs if run.status == "completed")
    results.failed_runs = sum(1 for run in updated_runs if run.status == "failed")
    results.aggregate_metrics = ExperimentManager._aggregate_metrics(updated_runs)

    analysis = _collect_analysis(results)

    report = ExperimentReport(
        experiment_name=config.name,
        timestamp=datetime.now().isoformat(),
        summary={
            "total_variants": len(config.variants),
            "total_runs": len(updated_runs),
            "completed_runs": results.completed_runs,
            "total_duration_hours": (metadata.get("total_duration_seconds", 0.0) / 3600.0),
            "avg_run_duration_min": (
                (metadata.get("total_duration_seconds", 0.0) / len(updated_runs) / 60.0)
                if updated_runs
                else 0.0
            ),
            "success_rate": (results.completed_runs / len(updated_runs)) if updated_runs else 0.0,
        },
        convergence=analysis.get("convergence", {}),
        comparison=analysis.get("comparison", {}),
        details=results.aggregate_metrics,
        visualizations={},
    )

    report_dir = output_dir / "reports"
    reporter = ExperimentReporter(output_dir=report_dir)
    report_paths = reporter.save_report(report, formats=args.formats)

    metadata["aggregate_metrics"] = results.aggregate_metrics
    metadata["completed_at"] = datetime.now().isoformat()
    _save_json(args.metadata, metadata)

    print(f"Updated run metadata files: {updated_files}")
    print(f"Reports regenerated in: {report_dir}")
    for fmt, path in report_paths.items():
        print(f"  {fmt}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
