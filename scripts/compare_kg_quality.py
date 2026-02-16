#!/usr/bin/env python3
"""KG Quality Comparison Script — Baseline vs. Law-Augmented.

Connects to Neo4j and exports snapshot metrics for the current KG state,
then optionally compares two snapshots side-by-side.

Usage:
    # Snapshot current KG state:
    python scripts/compare_kg_quality.py snapshot --output output/comparison/baseline.json

    # Compare two snapshots:
    python scripts/compare_kg_quality.py compare \
        --baseline output/comparison/baseline.json \
        --augmented output/comparison/augmented.json \
        --report output/comparison/report.md

    # Full A/B run (reset KG, run without law, snapshot, run with law, snapshot, compare):
    python scripts/compare_kg_quality.py full-run \
        --ontology data/ontology/decommissioning-ontology.ttl \
        --questions data/evaluation/competency_questions.json \
        --output output/comparison

Environment variables:
    NEO4J_URI          bolt://localhost:7687
    NEO4J_USER         neo4j
    NEO4J_PASSWORD     changeme
    WANDB_ENABLED      true/false
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Neo4j connection
# ---------------------------------------------------------------------------

def get_neo4j_driver() -> GraphDatabase.driver:
    """Create a Neo4j driver from env vars."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "changeme")
    return GraphDatabase.driver(uri, auth=(user, password))


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

# Law-graph labels to exclude from decommissioning KG metrics.
LAW_GRAPH_LABELS = {"Paragraf", "Abschnitt", "Gesetzbuch"}


def snapshot_kg(driver: GraphDatabase.driver) -> dict:
    """Export current Neo4j KG state as a JSON-serialisable dict.

    Excludes law-graph nodes (Paragraf, Abschnitt, Gesetzbuch) so that only
    the *decommissioning* KG is measured.
    """
    with driver.session() as session:
        # --- Node metrics ---
        all_nodes = session.run(
            "MATCH (n) "
            "WHERE NOT any(l IN labels(n) WHERE l IN $skip) "
            "RETURN id(n) AS nid, labels(n) AS labels, "
            "       n.label AS label, n.entity_type AS etype, "
            "       n.confidence AS conf",
            skip=list(LAW_GRAPH_LABELS),
        ).data()

        # --- Edge metrics ---
        all_edges = session.run(
            "MATCH (a)-[r]->(b) "
            "WHERE NOT any(l IN labels(a) WHERE l IN $skip) "
            "  AND NOT any(l IN labels(b) WHERE l IN $skip) "
            "RETURN id(r) AS rid, type(r) AS rtype, "
            "       id(a) AS src, id(b) AS tgt",
            skip=list(LAW_GRAPH_LABELS),
        ).data()

    # Aggregate
    node_label_counts: Counter[str] = Counter()
    for n in all_nodes:
        for lbl in n["labels"]:
            node_label_counts[lbl] += 1

    edge_type_counts: Counter[str] = Counter()
    for e in all_edges:
        edge_type_counts[e["rtype"]] += 1

    confidences = [
        n["conf"] for n in all_nodes if n["conf"] is not None
    ]

    snapshot = {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_nodes": len(all_nodes),
        "total_edges": len(all_edges),
        "unique_node_labels": len(node_label_counts),
        "unique_edge_types": len(edge_type_counts),
        "node_label_distribution": dict(
            node_label_counts.most_common()
        ),
        "edge_type_distribution": dict(
            edge_type_counts.most_common()
        ),
        "confidence_stats": {
            "count": len(confidences),
            "mean": round(sum(confidences) / len(confidences), 4)
            if confidences
            else 0.0,
            "min": round(min(confidences), 4) if confidences else 0.0,
            "max": round(max(confidences), 4) if confidences else 0.0,
        },
        "entities": [
            {
                "label": n["label"],
                "type": n["etype"],
                "confidence": n["conf"],
            }
            for n in all_nodes
        ],
    }
    return snapshot


def save_snapshot(snapshot: dict, path: Path) -> None:
    """Persist snapshot to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"Snapshot saved: {path}  ({snapshot['total_nodes']} nodes, "
          f"{snapshot['total_edges']} edges)")


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

def compare_snapshots(baseline: dict, augmented: dict) -> str:
    """Produce a Markdown comparison report."""
    lines: list[str] = []
    lines.append("# KG Quality Comparison Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(UTC).isoformat()}")
    lines.append("")

    # --- Summary table ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Baseline | Law-Augmented | Delta | Change % |")
    lines.append("|--------|----------|---------------|-------|----------|")

    metrics = [
        ("Total Nodes", "total_nodes"),
        ("Total Edges", "total_edges"),
        ("Unique Node Labels", "unique_node_labels"),
        ("Unique Edge Types", "unique_edge_types"),
    ]

    for label, key in metrics:
        b = baseline[key]
        a = augmented[key]
        delta = a - b
        pct = f"{delta / b * 100:+.1f}%" if b > 0 else "N/A"
        lines.append(f"| {label} | {b} | {a} | {delta:+d} | {pct} |")

    # Confidence comparison
    b_conf = baseline.get("confidence_stats", {})
    a_conf = augmented.get("confidence_stats", {})
    if b_conf and a_conf:
        delta_mean = a_conf["mean"] - b_conf["mean"]
        lines.append(
            f"| Avg Confidence | {b_conf['mean']:.3f} | {a_conf['mean']:.3f} "
            f"| {delta_mean:+.3f} | — |"
        )

    lines.append("")

    # --- New node labels ---
    b_labels = set(baseline["node_label_distribution"].keys())
    a_labels = set(augmented["node_label_distribution"].keys())
    new_labels = a_labels - b_labels
    lost_labels = b_labels - a_labels

    if new_labels:
        lines.append("## New Node Labels (discovered with law context)")
        lines.append("")
        for lbl in sorted(new_labels):
            cnt = augmented["node_label_distribution"][lbl]
            lines.append(f"- **{lbl}**: {cnt} nodes")
        lines.append("")

    if lost_labels:
        lines.append("## Lost Node Labels (not in augmented run)")
        lines.append("")
        for lbl in sorted(lost_labels):
            cnt = baseline["node_label_distribution"][lbl]
            lines.append(f"- **{lbl}**: {cnt} nodes (was in baseline)")
        lines.append("")

    # --- New edge types ---
    b_etypes = set(baseline["edge_type_distribution"].keys())
    a_etypes = set(augmented["edge_type_distribution"].keys())
    new_etypes = a_etypes - b_etypes

    if new_etypes:
        lines.append("## New Edge Types")
        lines.append("")
        for et in sorted(new_etypes):
            cnt = augmented["edge_type_distribution"][et]
            lines.append(f"- **{et}**: {cnt} edges")
        lines.append("")

    # --- Per-label growth ---
    lines.append("## Per-Label Node Count Changes")
    lines.append("")
    lines.append("| Label | Baseline | Augmented | Delta |")
    lines.append("|-------|----------|-----------|-------|")

    all_labels = sorted(b_labels | a_labels)
    for lbl in all_labels:
        b_cnt = baseline["node_label_distribution"].get(lbl, 0)
        a_cnt = augmented["node_label_distribution"].get(lbl, 0)
        delta = a_cnt - b_cnt
        if delta != 0:
            lines.append(f"| {lbl} | {b_cnt} | {a_cnt} | {delta:+d} |")
    lines.append("")

    # --- Per edge-type growth ---
    lines.append("## Per-Type Edge Count Changes")
    lines.append("")
    lines.append("| Edge Type | Baseline | Augmented | Delta |")
    lines.append("|-----------|----------|-----------|-------|")

    all_etypes = sorted(b_etypes | a_etypes)
    for et in all_etypes:
        b_cnt = baseline["edge_type_distribution"].get(et, 0)
        a_cnt = augmented["edge_type_distribution"].get(et, 0)
        delta = a_cnt - b_cnt
        if delta != 0:
            lines.append(f"| {et} | {b_cnt} | {a_cnt} | {delta:+d} |")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_snapshot(args: argparse.Namespace) -> None:
    """Take a snapshot of the current KG."""
    driver = get_neo4j_driver()
    try:
        snap = snapshot_kg(driver)
        save_snapshot(snap, Path(args.output))
    finally:
        driver.close()


def cmd_compare(args: argparse.Namespace) -> None:
    """Compare two snapshot files."""
    baseline = json.loads(Path(args.baseline).read_text())
    augmented = json.loads(Path(args.augmented).read_text())

    report = compare_snapshots(baseline, augmented)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    print(f"Report saved: {report_path}")
    print()
    print(report)


def cmd_full_run(args: argparse.Namespace) -> None:
    """Run both pipeline variants and compare.

    This is the most comprehensive mode. It:
    1. Snapshots the current KG as baseline
    2. If --run-augmented is set, launches the pipeline with LAW_GRAPH_ENABLED
    3. Snapshots post-run state
    4. Generates comparison report
    """
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    driver = get_neo4j_driver()
    try:
        # Step 1 — baseline snapshot
        print("=== Step 1: Baseline Snapshot ===")
        baseline = snapshot_kg(driver)
        baseline_path = out / "baseline_snapshot.json"
        save_snapshot(baseline, baseline_path)

        if args.run_augmented:
            import subprocess

            # Step 2 — run pipeline with law graph enabled
            print("\n=== Step 2: Running Law-Augmented Pipeline ===")
            env = os.environ.copy()
            env["LAW_GRAPH_ENABLED"] = "true"
            if args.wandb:
                env["WANDB_ENABLED"] = "true"

            cmd = [
                sys.executable, "scripts/full_kg_pipeline.py",
                "--smoke-test",
                "--questions", args.questions,
                "--ontology-path", args.ontology,
                "--output", str(out / "with_law_context"),
            ]
            print(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, env=env, capture_output=False)

            if result.returncode != 0:
                print(f"Pipeline exited with code {result.returncode}")

            # Step 3 — post-run snapshot
            print("\n=== Step 3: Post-Run Snapshot ===")
            augmented = snapshot_kg(driver)
            augmented_path = out / "augmented_snapshot.json"
            save_snapshot(augmented, augmented_path)

            # Step 4 — compare
            print("\n=== Step 4: Comparison Report ===")
            report = compare_snapshots(baseline, augmented)
            report_path = out / "comparison_report.md"
            report_path.write_text(report)
            print(f"Report saved: {report_path}")
            print()
            print(report)
        else:
            print("\nSkipping pipeline run (use --run-augmented to actually run).")
            print("To compare with an existing augmented snapshot:")
            print(f"  python scripts/compare_kg_quality.py compare "
                  f"--baseline {baseline_path} --augmented <path>")
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KG Quality Comparison — Baseline vs. Law-Augmented"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # snapshot
    sp = subparsers.add_parser("snapshot", help="Snapshot current KG state")
    sp.add_argument(
        "--output", "-o", required=True, help="Output JSON path"
    )
    sp.set_defaults(func=cmd_snapshot)

    # compare
    cp = subparsers.add_parser("compare", help="Compare two snapshots")
    cp.add_argument("--baseline", "-b", required=True, help="Baseline JSON")
    cp.add_argument("--augmented", "-a", required=True, help="Augmented JSON")
    cp.add_argument(
        "--report", "-r",
        default="output/comparison/comparison_report.md",
        help="Output report path",
    )
    cp.set_defaults(func=cmd_compare)

    # full-run
    fp = subparsers.add_parser("full-run", help="Run full A/B comparison")
    fp.add_argument("--output", "-o", default="output/comparison")
    fp.add_argument("--ontology", default="data/ontology/decommissioning-ontology.ttl")
    fp.add_argument("--questions", default="data/evaluation/competency_questions.json")
    fp.add_argument("--run-augmented", action="store_true",
                    help="Actually run the pipeline (otherwise just snapshot)")
    fp.add_argument("--wandb", action="store_true", help="Enable W&B tracking")
    fp.set_defaults(func=cmd_full_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
