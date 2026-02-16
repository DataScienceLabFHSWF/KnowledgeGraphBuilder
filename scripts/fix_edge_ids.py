#!/usr/bin/env python3
"""Fix duplicate edge IDs in Neo4j by adding unique suffixes.

Problem: Multiple extraction runs reused edge IDs like `rel_001`, `rel_002`
etc., so 1,223 domain edges share only ~20 unique IDs.

Solution: Rewrite each edge's `id` property to
    `{edge_type}_{source_id}_{target_id}_{counter}`
so every edge is uniquely identifiable.

Usage:
    python scripts/fix_edge_ids.py --dry-run    # Preview changes
    python scripts/fix_edge_ids.py --apply      # Apply changes
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import defaultdict

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def fix_edge_ids(
    *,
    dry_run: bool = True,
    neo4j_uri: str | None = None,
    neo4j_user: str | None = None,
    neo4j_password: str | None = None,
    database: str = "neo4j",
) -> dict[str, int]:
    """Assign unique edge IDs to all relationships in the graph.

    New ID format: ``{edge_type}_{hash12}`` where *hash12* is a 12-char
    hex digest of ``(edge_type, source_id, target_id, seq)``.

    Args:
        dry_run: If True, only report what would change.
        neo4j_uri: Bolt URI (default from env / localhost).
        neo4j_user: Neo4j user (default from env / neo4j).
        neo4j_password: Neo4j password (default from env / changeme).
        database: Neo4j database name.

    Returns:
        Summary dict with counts.
    """
    uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = neo4j_user or os.getenv("NEO4J_USER", "neo4j")
    pw = neo4j_password or os.environ.get("NEO4J_PASSWORD", "changeme")

    driver = GraphDatabase.driver(uri, auth=(user, pw))
    stats: dict[str, int] = {"total": 0, "updated": 0, "already_unique": 0, "null_fixed": 0}

    try:
        with driver.session(database=database) as session:
            # Fetch all edges with their Neo4j element IDs for safe updates
            result = session.run("""
                MATCH (s)-[r]->(t)
                RETURN elementId(r) AS eid, r.id AS old_id,
                       s.id AS src, t.id AS tgt,
                       type(r) AS rel_type
                ORDER BY type(r), s.id, t.id
            """)
            rows = [dict(rec) for rec in result]

        stats["total"] = len(rows)
        print(f"Total edges: {len(rows)}")

        # Count how many times each old_id appears
        id_counts: dict[str | None, int] = defaultdict(int)
        for row in rows:
            id_counts[row["old_id"]] += 1

        unique_old = sum(1 for c in id_counts.values() if c == 1)
        duplicate_old = sum(1 for c in id_counts.values() if c > 1)
        null_ids = id_counts.get(None, 0)
        print(f"Unique old IDs: {unique_old}, Duplicate patterns: {duplicate_old}, NULL IDs: {null_ids}")

        # Build new IDs: group by (rel_type, src, tgt) and assign counter
        pair_counters: dict[tuple[str, str, str], int] = defaultdict(int)
        updates: list[tuple[str, str, str]] = []  # (element_id, old_id, new_id)

        for row in rows:
            rel_type = row["rel_type"] or "UNKNOWN"
            src = row["src"] or "null"
            tgt = row["tgt"] or "null"
            key = (rel_type, src, tgt)

            seq = pair_counters[key]
            pair_counters[key] += 1

            # Deterministic hash of edge content for a fixed-length unique ID
            hash_input = f"{rel_type}:{src}:{tgt}:{seq}"
            digest = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
            new_id = f"{rel_type}_{digest}"

            old_id = row["old_id"]
            if old_id == new_id:
                stats["already_unique"] += 1
                continue
            if old_id is None:
                stats["null_fixed"] += 1

            updates.append((row["eid"], old_id or "NULL", new_id))

        print(f"Edges to update: {len(updates)}")
        if updates:
            print(f"Sample new IDs:")
            for eid, old, new in updates[:10]:
                print(f"  {old:>20} -> {new}")

        if dry_run:
            print("\n[DRY RUN] No changes applied. Use --apply to write.")
        else:
            # Apply in batches
            batch_size = 500
            with driver.session(database=database) as session:
                for i in range(0, len(updates), batch_size):
                    batch = updates[i : i + batch_size]
                    params = [{"eid": eid, "new_id": new_id} for eid, _, new_id in batch]
                    session.run(
                        """
                        UNWIND $batch AS item
                        MATCH ()-[r]->() WHERE elementId(r) = item.eid
                        SET r.id = item.new_id
                        """,
                        batch=params,
                    )
                    stats["updated"] += len(batch)
                    print(f"  Updated batch {i // batch_size + 1} "
                          f"({stats['updated']}/{len(updates)})")

            print(f"\nDone. Updated {stats['updated']} edge IDs.")

    finally:
        driver.close()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix duplicate edge IDs in Neo4j")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes only")
    group.add_argument("--apply", action="store_true", help="Apply ID changes")
    args = parser.parse_args()

    fix_edge_ids(dry_run=not args.apply)


if __name__ == "__main__":
    main()
