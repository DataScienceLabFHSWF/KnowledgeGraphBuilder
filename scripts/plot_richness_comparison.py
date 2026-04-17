"""Cross-condition graph richness comparison plots.

Reads run_metadata.json files produced by the benchmark pipeline and generates:
- Grouped bar charts comparing key richness metrics across conditions A–E
- Radar (spider) chart comparing conditions A–E on a normalised composite view

Usage:
    python scripts/plot_richness_comparison.py \
        --results experiment_results/benchmark_paper \
        --output output/figures
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

# Maps human-readable label → (json_path, higher_is_better)
# json_path uses dot notation to traverse nested dicts:
#   "kg_metrics.graph_richness.orphan_rate"
METRICS: dict[str, tuple[str, bool]] = {
    "Class coverage (%)":         ("kg_metrics.graph_richness.ontology_class_coverage_pct", True),
    "Relation coverage (%)":      ("kg_metrics.graph_richness.ontology_relation_coverage_pct", True),
    "Entity type entropy":        ("kg_metrics.graph_richness.entity_type_entropy", True),
    "Unique relation types":      ("kg_metrics.graph_richness.unique_relation_types", True),
    "Relation density":           ("kg_metrics.graph_richness.relation_density", True),
    "Avg. degree":                ("kg_metrics.graph_richness.avg_degree", True),
    "Orphan rate":                ("kg_metrics.graph_richness.orphan_rate", False),
    "Final coverage":             ("kg_metrics.final_coverage", True),
    "SHACL score":                ("kg_metrics.shacl.combined_score", True),
}

# Radar chart uses a subset that are all "higher = better" after inversion
RADAR_METRICS: list[str] = [
    "Class coverage (%)",
    "Relation coverage (%)",
    "Entity type entropy",
    "Unique relation types",
    "Relation density",
    "Avg. degree",
    "Final coverage",
]

VARIANT_STYLES: dict[str, dict[str, str]] = {
    "A": {"label": "A: Single-pass (qwen3:8b)",        "color": "#4878CF"},
    "B": {"label": "B: Multi-pass (qwen3:8b)",         "color": "#6ACC65"},
    "C": {"label": "C: Multi-pass + Law (qwen3:8b)",   "color": "#D65F5F"},
    "D": {"label": "D: Multi-pass (nemotron:4b)",      "color": "#B47CC7"},
    "E": {"label": "E: Multi-pass (nemotron:30b)",     "color": "#C4AD66"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_nested(obj: dict[str, Any], dotpath: str) -> float | None:
    """Traverse a nested dict using dot-separated keys."""
    parts = dotpath.split(".")
    cur: Any = obj
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if cur is None:
        return None
    try:
        return float(cur)
    except (TypeError, ValueError):
        return None


def _load_results(results_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Load all run_metadata.json files grouped by variant name."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for meta_path in results_dir.rglob("run_metadata.json"):
        try:
            with meta_path.open() as f:
                data = json.load(f)
            variant = data.get("variant_name", "unknown")
            grouped[variant].append(data)
        except Exception as e:
            print(f"  ⚠  Skipping {meta_path}: {e}")
    return dict(grouped)


def _aggregate(runs: list[dict[str, Any]], dotpath: str) -> tuple[float, float]:
    """Return (mean, std) for a metric across runs, ignoring None."""
    vals = [v for r in runs if (v := _get_nested(r, dotpath)) is not None]
    if not vals:
        return (0.0, 0.0)
    arr = np.array(vals, dtype=float)
    return (float(np.mean(arr)), float(np.std(arr)))


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_bar_charts(
    grouped: dict[str, list[dict[str, Any]]],
    output_dir: Path,
) -> None:
    """Grouped bar chart: one subplot per metric, bars per variant."""
    import matplotlib.pyplot as plt

    variants = [v for v in VARIANT_STYLES if v in grouped]
    n_metrics = len(METRICS)
    cols = 3
    rows = math.ceil(n_metrics / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows))
    axes_flat = axes.flatten()

    for idx, (metric_label, (dotpath, higher_better)) in enumerate(METRICS.items()):
        ax = axes_flat[idx]
        means, stds, colors, labels = [], [], [], []
        for var in variants:
            mean, std = _aggregate(grouped[var], dotpath)
            means.append(mean)
            stds.append(std)
            colors.append(VARIANT_STYLES[var]["color"])
            labels.append(var)

        x = np.arange(len(variants))
        bars = ax.bar(x, means, yerr=stds, capsize=4, color=colors, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_title(metric_label, fontsize=10, fontweight="bold")
        ax.set_ylabel("mean ± std", fontsize=8)
        direction = "↑ better" if higher_better else "↓ better"
        ax.annotate(direction, xy=(0.98, 0.96), xycoords="axes fraction",
                    ha="right", va="top", fontsize=7, color="grey")

    # Hide unused subplots
    for idx in range(n_metrics, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle("Graph Richness: Cross-Condition Comparison", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    out_path = output_dir / "richness_bar_comparison.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓  Saved {out_path}")


def plot_radar_chart(
    grouped: dict[str, list[dict[str, Any]]],
    output_dir: Path,
) -> None:
    """Radar/spider chart comparing conditions on normalised metrics."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    variants = [v for v in VARIANT_STYLES if v in grouped]

    # Collect raw means per variant per radar metric
    raw: dict[str, list[float]] = {m: [] for m in RADAR_METRICS}
    for metric_label in RADAR_METRICS:
        dotpath, _ = METRICS[metric_label]
        for var in variants:
            mean, _ = _aggregate(grouped[var], dotpath)
            raw[metric_label].append(mean)

    # Normalise each metric to [0, 1] across variants
    normed: dict[str, list[float]] = {}
    for metric_label, vals in raw.items():
        mn, mx = min(vals), max(vals)
        if mx == mn:
            normed[metric_label] = [0.5] * len(vals)
        else:
            normed[metric_label] = [(v - mn) / (mx - mn) for v in vals]

    N = len(RADAR_METRICS)
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles += angles[:1]  # close loop

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(RADAR_METRICS, size=9)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], size=7, color="grey")

    for i, var in enumerate(variants):
        values = [normed[m][i] for m in RADAR_METRICS]
        values += values[:1]
        style = VARIANT_STYLES[var]
        ax.plot(angles, values, linewidth=2, color=style["color"], label=style["label"])
        ax.fill(angles, values, alpha=0.07, color=style["color"])

    ax.legend(
        loc="upper right",
        bbox_to_anchor=(1.35, 1.15),
        fontsize=9,
        framealpha=0.8,
    )
    ax.set_title("Graph Quality Radar\n(normalised per metric)", size=13, fontweight="bold", pad=20)

    out_path = output_dir / "richness_radar_comparison.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓  Saved {out_path}")


def print_summary_table(grouped: dict[str, list[dict[str, Any]]]) -> None:
    """Print a compact ASCII summary table to stdout."""
    variants = [v for v in VARIANT_STYLES if v in grouped]
    col_w = 28

    header = f"{'Metric':<{col_w}}" + "".join(f"{'  ' + v:>12}" for v in variants)
    print("\n" + "=" * len(header))
    print(header)
    print("=" * len(header))
    for metric_label, (dotpath, higher_better) in METRICS.items():
        row = f"{metric_label:<{col_w}}"
        for var in variants:
            mean, std = _aggregate(grouped[var], dotpath)
            cell = f"{mean:.2f}±{std:.2f}"
            row += f"{cell:>12}"
        row += "  " + ("↑" if higher_better else "↓")
        print(row)
    print("=" * len(header) + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Plot cross-condition graph richness comparison.")
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("experiment_results/benchmark_paper"),
        help="Root directory containing per-variant run subdirectories.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/figures"),
        help="Directory to write output PNG files.",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    print(f"Loading results from {args.results} ...")
    grouped = _load_results(args.results)
    if not grouped:
        print("No run_metadata.json files found. Run the benchmark first.")
        return

    found_variants = sorted(grouped.keys())
    print(f"Found variants: {found_variants}")
    for var, runs in grouped.items():
        print(f"  {var}: {len(runs)} run(s)")

    print_summary_table(grouped)

    try:
        import matplotlib
        matplotlib.use("Agg")
    except ImportError:
        print("matplotlib not installed — skipping plots.")
        return

    print("Generating bar charts ...")
    plot_bar_charts(grouped, args.output)

    print("Generating radar chart ...")
    plot_radar_chart(grouped, args.output)

    print(f"\nAll figures saved to {args.output}/")


if __name__ == "__main__":
    main()
