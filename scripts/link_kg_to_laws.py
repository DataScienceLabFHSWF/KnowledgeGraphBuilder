#!/usr/bin/env python3
"""Cross-Domain KG Linking CLI.

Thin CLI wrapper around :class:`kgbuilder.linking.KGLawLinker`.

Usage:
    python scripts/link_kg_to_laws.py --dry-run                    # Preview links
    python scripts/link_kg_to_laws.py --create-links              # Create links
    python scripts/link_kg_to_laws.py --visualize                 # Generate viz query

Environment variables:
    NEO4J_PASSWORD - Neo4j password
    PYTHONPATH - must include src/
"""

from __future__ import annotations

import argparse
import json
import os

import structlog
from dotenv import load_dotenv

from kgbuilder.linking import KGLawLinker

# Load environment variables
load_dotenv()

logger = structlog.get_logger(__name__)


# KGLawLinker is now imported from kgbuilder.linking — see above.


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create cross-domain links between KG and law graph"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview links without creating them")
    parser.add_argument("--create-links", action="store_true",
                        help="Create the cross-domain links with prefixed relationship types")
    parser.add_argument("--visualize", action="store_true",
                        help="Generate visualization query")
    parser.add_argument("--stats", action="store_true",
                        help="Show existing link statistics")
    parser.add_argument("--database", default="neo4j",
                        help="Neo4j database to use")
    parser.add_argument("--link-prefix", default="LINKED_",
                        help="Prefix for linked relationship types")

    args = parser.parse_args()

    linker = KGLawLinker(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "changeme"),
        database=args.database,
        link_prefix=args.link_prefix,
    )

    if args.stats:
        stats = linker.get_link_statistics()
        print("Existing Cross-Domain Links:")
        print(json.dumps(stats, indent=2))
        return

    if args.visualize:
        query = linker.generate_visualization_query()
        print("Neo4j Browser Visualization Query:")
        print(query)
        return

    if args.dry_run or args.create_links:
        result = linker.create_links(dry_run=args.dry_run)

        print(f"Entities processed: {result['total_entities_processed']}")
        print(f"Links created: {result['total_links_created']}")
        print(f"Statistics: {json.dumps(result['stats'], indent=2)}")

        if result['links']:
            print("\nSample links:")
            for link in result['links'][:10]:
                target = link.get('target_paragraph', link.get('target_law', 'unknown'))
                print(f"  {link['source_entity']} -[{link['relationship']}]-> {target}")

        if args.dry_run:
            print("\nThis was a dry run. Use --create-links to actually create the relationships.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
