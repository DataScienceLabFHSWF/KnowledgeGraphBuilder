#!/usr/bin/env python3
"""Phase B — Semantic extraction from law graph paragraphs.

After the structural Phase A (XML → Paragraf/Abschnitt/Gesetzbuch nodes),
this script runs LLM-based and rule-based extraction on paragraph texts to
extract semantic concepts: obligations, definitions, permissions, legal actors.

New semantic entities are linked to their source Paragraf via DEFINIERT_IN.
Cross-domain links are created when legal entities mention decommissioning
concepts (Facility, Activity, Component already in the KG).

Addresses Task 5 from NEXT_STEPS.md.

Usage:
    # Extract semantic entities from all AtG paragraphs:
    python scripts/run_legal_extraction.py --law AtG

    # Extract from all 5 loaded laws:
    python scripts/run_legal_extraction.py --all

    # Dry run — show what would be extracted without writing to Neo4j:
    python scripts/run_legal_extraction.py --law AtG --dry-run

    # With LLM ensemble (requires LegalLLMExtractor implementation):
    python scripts/run_legal_extraction.py --law AtG --use-llm

Environment variables:
    NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD
    OLLAMA_BASE_URL     http://localhost:18134
    OLLAMA_LLM_MODEL    qwen3:8b
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j driver required: pip install neo4j", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Neo4j connection
# ---------------------------------------------------------------------------

def get_neo4j_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "changeme")
    return GraphDatabase.driver(uri, auth=(user, password))


# ---------------------------------------------------------------------------
# Load paragraph texts from Neo4j
# ---------------------------------------------------------------------------

def load_paragraphs(driver, law_filter: str | None = None) -> list[dict]:
    """Load Paragraf nodes with their text content from Neo4j.

    Args:
        driver: Neo4j driver instance.
        law_filter: Optional law abbreviation to filter (e.g. "AtG").

    Returns:
        List of dicts with keys: id, titel, text, gesetz, abschnitt.
    """
    query = """
    MATCH (p:Paragraf)
    WHERE p.text IS NOT NULL AND p.text <> ''
    """
    params: dict = {}

    if law_filter:
        query += """
        AND EXISTS {
            MATCH (p)-[:teilVon*1..2]->(g:Gesetzbuch)
            WHERE g.name CONTAINS $law
        }
        """
        params["law"] = law_filter

    query += """
    OPTIONAL MATCH (p)-[:teilVon]->(a:Abschnitt)
    OPTIONAL MATCH (p)-[:teilVon*1..2]->(g:Gesetzbuch)
    RETURN id(p) AS neo4j_id,
           p.titel AS titel,
           p.text AS text,
           g.name AS gesetz,
           a.titel AS abschnitt
    ORDER BY gesetz, p.titel
    """

    with driver.session() as session:
        result = session.run(query, **params)
        return [dict(r) for r in result]


# ---------------------------------------------------------------------------
# Rule-based extraction
# ---------------------------------------------------------------------------

def run_rule_extraction(paragraphs: list[dict]) -> list[dict]:
    """Apply LegalRuleBasedExtractor to paragraphs.

    Returns list of extraction results with entities and relations.
    """
    # Import here to allow the script to show --help even without full deps
    from kgbuilder.extraction.legal_rules import LegalRuleBasedExtractor

    extractor = LegalRuleBasedExtractor()
    results = []

    for para in paragraphs:
        text = para["text"]
        law = para.get("gesetz", "")
        pid = para.get("titel", "")

        entities = extractor.extract_entities(text, law_abbr=law, paragraph_id=pid)
        relations = extractor.extract_relations(
            text, entities, law_abbr=law, paragraph_id=pid
        )

        results.append({
            "paragraph": para,
            "entities": entities,
            "relations": relations,
        })

    return results


# ---------------------------------------------------------------------------
# LLM extraction (optional, requires Task 2 complete)
# ---------------------------------------------------------------------------

def run_llm_extraction(paragraphs: list[dict]) -> list[dict]:
    """Apply LegalLLMExtractor to paragraphs.

    Returns list of extraction results. Falls back gracefully if the
    LegalLLMExtractor is not yet implemented.
    """
    try:
        from kgbuilder.extraction.legal_llm import LegalLLMExtractor
        from kgbuilder.embedding.ollama import OllamaProvider
        from kgbuilder.storage.ontology import OntologyService as OntSvc
    except ImportError as e:
        print(f"Cannot import LLM extraction modules: {e}", file=sys.stderr)
        return []

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:18134")
    model = os.getenv("OLLAMA_LLM_MODEL", "qwen3:8b")

    try:
        llm = OllamaProvider(model=model, base_url=base_url)
    except Exception as e:
        print(f"Cannot initialise OllamaProvider: {e}", file=sys.stderr)
        return []

    # Load ontology service (law ontology)
    ontology_path = Path("data/ontology/law/law-ontology-v1.0.owl")
    if not ontology_path.exists():
        print(f"Law ontology not found: {ontology_path}", file=sys.stderr)
        return []

    try:
        ont_svc = OntSvc(str(ontology_path))
        extractor = LegalLLMExtractor(llm=llm, ontology=ont_svc)
    except NotImplementedError:
        print("LegalLLMExtractor not yet implemented (Task 2). Skipping LLM pass.",
              file=sys.stderr)
        return []
    except Exception as e:
        print(f"Cannot initialise LegalLLMExtractor: {e}", file=sys.stderr)
        return []

    results = []
    for i, para in enumerate(paragraphs):
        text = para["text"]
        pid = para.get("titel", "")
        law = para.get("gesetz", "")

        print(f"  LLM extracting [{i + 1}/{len(paragraphs)}] {law} {pid}...")
        try:
            entities, relations = extractor.extract(
                text, paragraph_id=pid, law_abbr=law
            )
            results.append({
                "paragraph": para,
                "entities": entities,
                "relations": relations,
            })
        except NotImplementedError:
            print("  LegalLLMExtractor.extract() not implemented. Stopping LLM pass.")
            break
        except Exception as e:
            print(f"  LLM extraction failed for {pid}: {e}")
            results.append({"paragraph": para, "entities": [], "relations": []})

    return results


# ---------------------------------------------------------------------------
# Write results to Neo4j
# ---------------------------------------------------------------------------

def write_results_to_neo4j(
    driver,
    results: list[dict],
    dry_run: bool = False,
) -> dict:
    """Write extracted semantic entities and relations to Neo4j.

    Creates nodes for each extracted entity type (LegalReference, Obligation,
    Definition, Permission, Behoerde, etc.) and links them to their source
    Paragraf via DEFINIERT_IN.

    Returns summary statistics.
    """
    stats = {
        "entities_created": 0,
        "relations_created": 0,
        "paragraphs_processed": 0,
        "cross_domain_links": 0,
    }

    for r in results:
        para = r["paragraph"]
        neo4j_id = para["neo4j_id"]
        entities = r["entities"]
        relations = r["relations"]

        if not entities:
            continue

        stats["paragraphs_processed"] += 1

        if dry_run:
            print(f"  {para.get('gesetz', '?')} {para.get('titel', '?')}: "
                  f"{len(entities)} entities, {len(relations)} relations")
            for e in entities:
                print(f"    [{e.entity_type}] {e.label} (conf={e.confidence:.2f})")
            stats["entities_created"] += len(entities)
            stats["relations_created"] += len(relations)
            continue

        with driver.session() as session:
            for entity in entities:
                eid = f"legal_{uuid.uuid4().hex[:12]}"

                # Create entity node
                session.run(
                    f"CREATE (e:{entity.entity_type} {{id: $eid, label: $label, "
                    f"description: $desc, confidence: $conf, "
                    f"source: 'phase_b_extraction', "
                    f"entity_type: $etype}})",
                    eid=eid,
                    label=entity.label,
                    desc=entity.description,
                    conf=entity.confidence,
                    etype=entity.entity_type,
                )

                # Link to source Paragraf
                session.run(
                    "MATCH (p) WHERE id(p) = $pid "
                    f"MATCH (e:{entity.entity_type} {{id: $eid}}) "
                    "CREATE (e)-[:DEFINIERT_IN]->(p)",
                    pid=neo4j_id,
                    eid=eid,
                )
                stats["entities_created"] += 1

            # Create inter-entity relations
            for rel in relations:
                session.run(
                    "MATCH (a {id: $src}), (b {id: $tgt}) "
                    f"CREATE (a)-[:{rel.predicate} {{confidence: $conf, "
                    f"source: 'phase_b_extraction'}}]->(b)",
                    src=rel.source_entity_id,
                    tgt=rel.target_entity_id,
                    conf=rel.confidence,
                )
                stats["relations_created"] += 1

    return stats


# ---------------------------------------------------------------------------
# Cross-domain linking
# ---------------------------------------------------------------------------

def create_cross_domain_links(
    driver,
    dry_run: bool = False,
) -> int:
    """Link legal entities to decommissioning KG entities.

    Matches by label similarity: if a legal entity label appears as a
    substring of a decommissioning entity label (or vice versa), create a
    REFERENCES_LEGAL / LEGALLY_RELEVANT edge.
    """
    query = """
    // Find decommissioning entities that reference legal concepts
    MATCH (d)
    WHERE NOT any(l IN labels(d) WHERE l IN
        ['Paragraf', 'Abschnitt', 'Gesetzbuch',
         'LegalReference', 'Obligation', 'Permission',
         'Definition', 'Behoerde', 'Prohibition'])
    AND d.label IS NOT NULL
    WITH d, toLower(d.label) AS d_label

    // Find legal semantic entities
    MATCH (legal)
    WHERE any(l IN labels(legal) WHERE l IN
        ['LegalReference', 'Obligation', 'Permission',
         'Definition', 'Behoerde'])
    AND legal.label IS NOT NULL
    WITH d, d_label, legal, toLower(legal.label) AS l_label

    // Match by substring containment
    WHERE d_label CONTAINS l_label
       OR l_label CONTAINS d_label

    // Avoid self-links and duplicates
    AND id(d) <> id(legal)
    AND NOT (d)-[:LEGALLY_RELEVANT]->(legal)

    RETURN d.label AS decomm_label, legal.label AS legal_label,
           labels(d) AS d_labels, labels(legal) AS l_labels,
           id(d) AS d_id, id(legal) AS l_id
    LIMIT 200
    """

    links_created = 0

    with driver.session() as session:
        matches = session.run(query).data()

        for m in matches:
            if dry_run:
                print(f"  Would link: [{m['d_labels']}] {m['decomm_label']} "
                      f"↔ [{m['l_labels']}] {m['legal_label']}")
                links_created += 1
                continue

            session.run(
                "MATCH (d), (l) "
                "WHERE id(d) = $did AND id(l) = $lid "
                "CREATE (d)-[:LEGALLY_RELEVANT {source: 'cross_domain_linking'}]->(l)",
                did=m["d_id"],
                lid=m["l_id"],
            )
            links_created += 1

    return links_created


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase B: Semantic extraction from law graph paragraphs"
    )
    parser.add_argument("--law", default=None,
                        help="Filter by law abbreviation (e.g. AtG, StrlSchG)")
    parser.add_argument("--all", action="store_true",
                        help="Process all laws in the graph")
    parser.add_argument("--use-llm", action="store_true",
                        help="Also run LLM extraction (requires Task 2)")
    parser.add_argument("--cross-link", action="store_true",
                        help="Create cross-domain links after extraction")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without writing")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of paragraphs to process (0=all)")

    args = parser.parse_args()

    if not args.law and not args.all:
        print("Specify --law <abbreviation> or --all", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    law_filter = args.law if args.law else None

    driver = get_neo4j_driver()
    try:
        # Load paragraphs
        print(f"Loading paragraphs{f' for {law_filter}' if law_filter else ''}...")
        paragraphs = load_paragraphs(driver, law_filter)
        print(f"Loaded {len(paragraphs)} paragraphs with text content")

        if args.limit > 0:
            paragraphs = paragraphs[:args.limit]
            print(f"Limited to {args.limit} paragraphs")

        if not paragraphs:
            print("No paragraphs found. Is the law graph loaded?")
            sys.exit(1)

        # Rule-based extraction
        print("\n--- Rule-based extraction ---")
        rule_results = run_rule_extraction(paragraphs)
        rule_entities = sum(len(r["entities"]) for r in rule_results)
        rule_relations = sum(len(r["relations"]) for r in rule_results)
        print(f"Rule-based: {rule_entities} entities, {rule_relations} relations")

        # LLM extraction (optional)
        llm_results = []
        if args.use_llm:
            print("\n--- LLM extraction ---")
            llm_results = run_llm_extraction(paragraphs)
            llm_entities = sum(len(r["entities"]) for r in llm_results)
            llm_relations = sum(len(r["relations"]) for r in llm_results)
            print(f"LLM: {llm_entities} entities, {llm_relations} relations")

        # Merge results (if both available, prefer LLM where overlap)
        all_results = rule_results  # Use rule as base
        # TODO: When LegalEnsembleExtractor (Task 3) is done, use it here

        # Write to Neo4j
        print("\n--- Writing to Neo4j ---")
        stats = write_results_to_neo4j(driver, all_results, dry_run=args.dry_run)
        print(f"Created: {stats['entities_created']} entities, "
              f"{stats['relations_created']} relations "
              f"({stats['paragraphs_processed']} paragraphs)")

        # Cross-domain linking
        if args.cross_link:
            print("\n--- Cross-domain linking ---")
            links = create_cross_domain_links(driver, dry_run=args.dry_run)
            print(f"Cross-domain links: {links}")

        # Summary
        print("\n=== Phase B Summary ===")
        print(f"Paragraphs processed: {stats['paragraphs_processed']}")
        print(f"Entities created:     {stats['entities_created']}")
        print(f"Relations created:    {stats['relations_created']}")
        if args.dry_run:
            print("(DRY RUN — nothing written to Neo4j)")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
