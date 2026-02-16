#!/usr/bin/env python3
"""
KG Version Management Utility.

Allows listing, diffing, and managing Knowledge Graph snapshots 
created during pipeline runs.

Usage:
    python scripts/manage_versions.py list
    python scripts/manage_versions.py diff <v1_id> <v2_id>
    python scripts/manage_versions.py delete <version_id>
"""

import argparse
import sys
from pathlib import Path

from tabulate import tabulate

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.storage.versioning import KGVersioningService


def list_versions(service: KGVersioningService):
    versions = service.list_versions()
    if not versions:
        print("No versions found.")
        return

    table_data = []
    for v in versions:
        table_data.append([
            v.version_id,
            v.timestamp,
            v.node_count,
            v.edge_count,
            v.description[:50] + "..." if len(v.description) > 50 else v.description
        ])

    print("\nKnowledge Graph Versions:")
    print(tabulate(table_data, headers=["ID", "Timestamp", "Nodes", "Edges", "Description"]))
    print()

def diff_versions(service: KGVersioningService, v1_id: str, v2_id: str):
    try:
        diff = service.diff(v1_id, v2_id)

        print(f"\nDiff: {v1_id} -> {v2_id}")
        print("-" * 50)
        print(f"Nodes Added:     {len(diff.nodes_added)}")
        print(f"Nodes Removed:   {len(diff.nodes_removed)}")
        print(f"Nodes Modified:  {len(diff.nodes_modified)}")
        print(f"Edges Added:     {len(diff.edges_added)}")
        print(f"Edges Removed:   {len(diff.edges_removed)}")
        print("-" * 50)
        print(f"Net Node Change: {diff.stats['net_node_change']}")
        print(f"Net Edge Change: {diff.stats['net_edge_change']}")
        print()

        if diff.nodes_added:
            print(f"Sample Nodes Added: {', '.join(diff.nodes_added[:5])}")
        if diff.nodes_modified:
            print(f"Sample Nodes Modified: {', '.join(diff.nodes_modified[:5])}")

    except Exception as e:
        print(f"Error computing diff: {e}")

def main():
    parser = argparse.ArgumentParser(description="Manage KG versions")
    parser.add_argument("command", choices=["list", "diff", "delete"], help="Command to run")
    parser.add_argument("args", nargs="*", help="Arguments for the command")
    parser.add_argument("--version-dir", type=Path, default=Path("output/versions"), help="Version storage directory")

    args = parser.parse_args()
    service = KGVersioningService(args.version_dir)

    if args.command == "list":
        list_versions(service)
    elif args.command == "diff":
        if len(args.args) < 2:
            print("Usage: diff <v1_id> <v2_id>")
            return
        diff_versions(service, args.args[0], args.args[1])
    elif args.command == "delete":
        if len(args.args) < 1:
            print("Usage: delete <version_id>")
            return
        if service.delete_version(args.args[0]):
            print(f"Version {args.args[0]} deleted.")
        else:
            print(f"Version {args.args[0]} not found.")

if __name__ == "__main__":
    main()
