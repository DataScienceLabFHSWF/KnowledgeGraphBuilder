"""CLI: run an internal, non-destructive entity-resolution pass and
write merge candidates to JSON.

Usage:
    python scripts/entity_resolution_pass.py --out candidates.json --min-cluster-size 2

This script does not merge nodes; it only suggests clusters for review.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kgbuilder.analytics.er_runner import find_merge_candidates
from kgbuilder.storage.neo4j_store import Neo4jGraphStore


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bolt-uri", default=None)
    p.add_argument("--user", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--node-type", action="append", help="Restrict to node types (can repeat)")
    p.add_argument("--min-cluster-size", type=int, default=2)
    p.add_argument("--threshold", type=float, default=0.85)
    p.add_argument("--edit-weight", type=float, default=0.3)
    p.add_argument("--out", default="experiment_output/er_candidates.json")
    args = p.parse_args(argv)

    bolt = args.bolt_uri or None
    user = args.user or None
    pw = args.password or None

    # Use environment/defaults inside Neo4jGraphStore if None
    store = Neo4jGraphStore(bolt or "bolt://localhost:7687", auth=(user or "neo4j", pw or "changeme"))

    candidates = find_merge_candidates(
        store,
        node_types=args.node_type,
        min_cluster_size=args.min_cluster_size,
        edit_weight=args.edit_weight,
        sim_threshold=args.threshold,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    serial = [
        {"ids": sorted(list(c.ids)), "size": c.size, "score": c.score}
        for c in candidates
    ]
    out_path.write_text(json.dumps(serial, indent=2, ensure_ascii=False), encoding="utf8")
    print(f"Wrote {len(serial)} candidate clusters to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())