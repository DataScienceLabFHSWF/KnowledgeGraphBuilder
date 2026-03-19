#!/usr/bin/env python3
"""Convergence plot for the KG benchmark paper.

Reads ``iteration_metrics.json`` files from experiment run directories,
aggregates per-variant across multiple runs, and produces:

1. ``convergence_entities.png``  — cumulative entities discovered per iteration
2. ``convergence_coverage.png``  — ontology coverage per iteration
3. ``convergence_combined.png``  — both panels side-by-side (paper figure)

Usage
-----
    python scripts/plot_convergence.py \\
        --results experiment_results/benchmark_paper \\
        --output  output/figures

The ``--results`` directory is expected to have the structure written by
ExperimentManager:

    <results_dir>/
      <variant_name>/
        run1_<run_id>/
          iteration_metrics.json
        run2_<run_id>/
          iteration_metrics.json
        ...

``iteration_metrics.json`` schema (list of objects):
    {
      "iteration": 1,
      "entities_discovered_this_iter": 12,
      "total_entities_cumulative": 12,
      "ontology_coverage": 0.33,
      "questions_processed": 18,
      "new_entity_types": ["Action", "Plan"],
      "processing_time_sec": 47.3
    }
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


VARIANT_STYLES: dict[str, dict] = {
    "A_single_pass":   {"color": "#E07B54", "label": "A: Single-pass (qwen3:8b)", "ls": "--"},
    "B_multipass":     {"color": "#5B919B", "label": "B: Multi-pass (qwen3:8b)", "ls": "-"},
    "C_multipass_law": {"color": "#3E6B48", "label": "C: Multi-pass + Law Graph (qwen3:8b)", "ls": "-"},
    "D_nemotron_4b":   {"color": "#9B6B9B", "label": "D: Multi-pass (nemotron-3-nano:4b)", "ls": "-."},
    "E_nemotron_30b":  {"color": "#B59B3E", "label": "E: Multi-pass (nemotron-3-nano:30b)", "ls": ":"},
}


def load_variant_runs(results_dir: Path, variant_name: str) -> list[list[dict]]:
    """Load all iteration_metrics.json files for one variant.

    Returns a list of run-data (each run-data is a list of iteration dicts).
    """
    variant_dir = results_dir / variant_name
    runs: list[list[dict]] = []
    if not variant_dir.exists():
        return runs
    for run_dir in sorted(variant_dir.iterdir()):
        metrics_file = run_dir / "iteration_metrics.json"
        if metrics_file.exists():
            data = json.loads(metrics_file.read_text())
            if data:
                runs.append(data)
    return runs


def aggregate_runs(
    runs: list[list[dict]],
    metric: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (iterations, mean, std) arrays across runs for a metric.

    For single-pass variants (all runs have 1 iteration), each run already
    has just one data point — the mean/std are still computed correctly.
    """
    max_iters = max(len(run) for run in runs)
    values = np.full((len(runs), max_iters), np.nan)
    for r_idx, run in enumerate(runs):
        for it in run:
            i = it["iteration"] - 1  # 0-indexed
            values[r_idx, i] = it[metric]

    # Forward-fill NaN (for runs that converged early)
    for r_idx in range(len(runs)):
        last = np.nan
        for i in range(max_iters):
            if not np.isnan(values[r_idx, i]):
                last = values[r_idx, i]
            elif not np.isnan(last):
                values[r_idx, i] = last

    iterations = np.arange(1, max_iters + 1)
    mean = np.nanmean(values, axis=0)
    std = np.nanstd(values, axis=0)
    return iterations, mean, std


def plot_metric(
    ax,
    results_dir: Path,
    metric: str,
    ylabel: str,
    title: str,
    max_iter_cap: int = 10,
) -> None:
    """Plot mean ± std for all variants on one axes."""
    import matplotlib.pyplot as plt  # noqa: F401  (unused but ensures backend loaded)

    for variant_name, style in VARIANT_STYLES.items():
        runs = load_variant_runs(results_dir, variant_name)
        if not runs:
            continue

        iters, mean, std = aggregate_runs(runs, metric)
        iters = iters[:max_iter_cap]
        mean = mean[:max_iter_cap]
        std = std[:max_iter_cap]
        n_runs = len(runs)

        ax.plot(
            iters, mean,
            color=style["color"],
            linestyle=style["ls"],
            linewidth=2,
            marker="o",
            markersize=5,
            label=f"{style['label']} (n={n_runs})",
        )
        ax.fill_between(
            iters,
            mean - std,
            mean + std,
            color=style["color"],
            alpha=0.15,
        )

    ax.set_xlabel("Iteration", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xticks(range(1, max_iter_cap + 1))
    ax.legend(fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.5)


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Plot KG benchmark convergence curves")
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("experiment_results/benchmark_paper"),
        help="Root directory of experiment results (default: experiment_results/benchmark_paper)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/figures"),
        help="Output directory for figures (default: output/figures)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Cap x-axis at this iteration count (default: 10)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Figure DPI (default: 300)",
    )
    args = parser.parse_args()

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("ERROR: matplotlib is required.  pip install matplotlib")
        raise SystemExit(1)

    args.output.mkdir(parents=True, exist_ok=True)

    # --- Figure 1: combined (paper figure) ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(
        "KG Construction Convergence — Nuclear Decommissioning Domain",
        fontsize=13,
        fontweight="bold",
    )

    plot_metric(
        ax1,
        args.results,
        metric="total_entities_cumulative",
        ylabel="Cumulative entities discovered",
        title="Entity growth by iteration",
        max_iter_cap=args.max_iterations,
    )
    plot_metric(
        ax2,
        args.results,
        metric="ontology_coverage",
        ylabel="Ontology class coverage",
        title="Coverage convergence",
        max_iter_cap=args.max_iterations,
    )

    plt.tight_layout()
    combined_path = args.output / "convergence_combined.png"
    fig.savefig(combined_path, dpi=args.dpi, bbox_inches="tight")
    print(f"Saved: {combined_path}")

    # --- Individual figures ---
    for metric, fname, ylabel, title in [
        (
            "total_entities_cumulative",
            "convergence_entities.png",
            "Cumulative entities discovered",
            "Entity growth by iteration",
        ),
        (
            "ontology_coverage",
            "convergence_coverage.png",
            "Ontology class coverage",
            "Coverage convergence by iteration",
        ),
    ]:
        fig_single, ax = plt.subplots(figsize=(7, 5))
        plot_metric(ax, args.results, metric, ylabel, title, args.max_iterations)
        plt.tight_layout()
        out_path = args.output / fname
        fig_single.savefig(out_path, dpi=args.dpi, bbox_inches="tight")
        print(f"Saved: {out_path}")
        plt.close(fig_single)

    plt.close(fig)


if __name__ == "__main__":
    main()
