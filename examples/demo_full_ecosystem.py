#!/usr/bin/env python3
"""Comprehensive Demo: Full KnowledgeGraphBuilder Ecosystem.

Demonstrates the complete pipeline for a professor presentation:
  1. KG Construction (KnowledgeGraphBuilder)
  2. Ontology-Guided Extraction + Enrichment
  3. Law Graph with cross-links
  4. GraphQAAgent chat session (Q&A over the KG)
  5. Reasoning display (CoT, provenance, subgraph)
  6. OntologyExtender gap detection + proposals
  7. HITL review session simulation

Prerequisites:
    docker-compose up -d   (Neo4j, Qdrant, Fuseki, Ollama)
    Data must be indexed in Qdrant and Neo4j already.
    GraphQAAgent must be running at :8080

Usage:
    source .venv/bin/activate
    PYTHONPATH=src python examples/demo_full_ecosystem.py

    # Quick mode (skip heavy operations):
    PYTHONPATH=src python examples/demo_full_ecosystem.py --quick

    # Run only specific phases:
    PYTHONPATH=src python examples/demo_full_ecosystem.py --phases 1,4,5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FUSEKI_URL = os.getenv("FUSEKI_URL", "http://localhost:3030")
FUSEKI_DATASET = os.getenv("FUSEKI_DATASET", "kgbuilder")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "kgbuilder")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:18134")
OLLAMA_MODEL = os.getenv("OLLAMA_LLM_MODEL", "qwen3:8b")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "kgbuilder")
GRAPHQA_URL = os.getenv("GRAPHQA_URL", "http://localhost:8080/api/v1")

# Demo limits
MAX_CLASSES = 3
MAX_QUESTIONS = 2
TOP_K_DOCS = 5
DEMO_OUTPUT = Path("output/demo_output")

# Presentation questions for the QA demo
DEMO_QUESTIONS = [
    "Welche Gesetze regeln den Rückbau von Kernkraftwerken in Deutschland?",
    "What entities are involved in the decommissioning of nuclear facilities?",
    "Which legal paragraphs govern radiation protection during decommissioning?",
    "What is the relationship between AtG and StrlSchG?",
    "Which types of waste are mentioned in the Kreislaufwirtschaftsgesetz?",
]

SEP = "═" * 72
SUBSEP = "─" * 72


def _header(num: int, title: str) -> None:
    """Print a phase header."""
    print(f"\n{SEP}")
    print(f"  Phase {num} — {title}")
    print(SEP)


def _subheader(title: str) -> None:
    """Print a sub-section header."""
    print(f"\n  {SUBSEP}")
    print(f"  {title}")
    print(f"  {SUBSEP}")


def _json_pretty(data: Any, indent: int = 4) -> str:
    """Pretty-print JSON with truncation."""
    text = json.dumps(data, indent=indent, ensure_ascii=False, default=str)
    lines = text.split("\n")
    if len(lines) > 30:
        return "\n".join(lines[:28]) + f"\n    ... ({len(lines) - 28} more lines)"
    return text


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: Infrastructure Health Check
# ═══════════════════════════════════════════════════════════════════════════════

def phase1_infrastructure() -> dict[str, bool]:
    """Check all infrastructure services are running.

    Returns:
        Dict mapping service name to health status.
    """
    _header(1, "Infrastructure Health Check")

    # TODO: Implement actual health checks
    # For each service, do a quick ping:
    # - Qdrant: GET /collections
    # - Fuseki: GET /$/ping
    # - Neo4j: bolt connection test
    # - Ollama: GET /api/tags
    # - GraphQAAgent: GET /api/v1/health

    services = {
        "Qdrant": _check_qdrant,
        "Fuseki": _check_fuseki,
        "Neo4j": _check_neo4j,
        "Ollama": _check_ollama,
        "GraphQAAgent": _check_graphqa,
    }

    results: dict[str, bool] = {}
    for name, checker in services.items():
        try:
            ok = checker()
            results[name] = ok
            status = "✓ OK" if ok else "✗ FAILED"
        except Exception as e:
            results[name] = False
            status = f"✗ ERROR: {e}"
        print(f"  {name:20s} {status}")

    all_ok = all(results.values())
    print(f"\n  {'All services healthy ✓' if all_ok else '⚠ Some services unavailable'}")
    return results


def _check_qdrant() -> bool:
    """Check Qdrant is reachable."""
    # TODO: Implement — import httpx, GET QDRANT_URL/collections
    raise NotImplementedError("Stub: implement Qdrant health check")


def _check_fuseki() -> bool:
    """Check Fuseki is reachable."""
    # TODO: Implement — GET FUSEKI_URL/$/ping
    raise NotImplementedError("Stub: implement Fuseki health check")


def _check_neo4j() -> bool:
    """Check Neo4j is reachable."""
    # TODO: Implement — neo4j driver verify_connectivity()
    raise NotImplementedError("Stub: implement Neo4j health check")


def _check_ollama() -> bool:
    """Check Ollama is reachable and model is loaded."""
    # TODO: Implement — GET OLLAMA_URL/api/tags, check OLLAMA_MODEL in list
    raise NotImplementedError("Stub: implement Ollama health check")


def _check_graphqa() -> bool:
    """Check GraphQAAgent API is reachable."""
    # TODO: Implement — GET GRAPHQA_URL/health
    raise NotImplementedError("Stub: implement GraphQA health check")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: Ontology & KG Overview
# ═══════════════════════════════════════════════════════════════════════════════

def phase2_ontology_overview() -> dict[str, Any]:
    """Display the current ontology structure and KG statistics.

    Shows:
    - Ontology classes (TBox) from Fuseki
    - KG node/edge counts (ABox) from Neo4j
    - Law graph statistics
    - Embedding coverage from Qdrant

    Returns:
        Dict with ontology stats.
    """
    _header(2, "Ontology & Knowledge Graph Overview")

    stats: dict[str, Any] = {}

    # --- 2a: Ontology (TBox) ---
    _subheader("2a. Ontology Structure (TBox — from Fuseki)")

    # TODO: Connect to FusekiOntologyService, list classes
    # from kgbuilder.storage.ontology import FusekiOntologyService
    # ontology = FusekiOntologyService(fuseki_url=FUSEKI_URL, dataset_name=FUSEKI_DATASET)
    # classes = ontology.get_all_classes()
    # for cls in classes:
    #     print(f"    • {cls}")
    # stats["ontology_classes"] = len(classes)
    print("  TODO: Load and display ontology classes from Fuseki")

    # --- 2b: Domain KG (ABox) ---
    _subheader("2b. Domain Knowledge Graph (ABox — from Neo4j)")

    # TODO: Connect to Neo4j, run MATCH (n) RETURN labels(n), count(*)
    # Also: MATCH ()-[r]->() RETURN type(r), count(*)
    # Display as table
    print("  TODO: Query Neo4j for node/edge counts by type")

    # --- 2c: Law Graph ---
    _subheader("2c. Law Graph Statistics")

    # TODO: Query Neo4j for law graph nodes
    # MATCH (n) WHERE n:Gesetz OR n:Paragraph OR n:Absatz RETURN labels(n), count(*)
    # Show: 5 laws processed, 858 nodes, 3684 edges
    print("  TODO: Query Neo4j for law graph statistics")

    # --- 2d: Embedding coverage ---
    _subheader("2d. Qdrant Embedding Coverage")

    # TODO: qdrant.get_points_count()
    print("  TODO: Query Qdrant for collection info")

    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: Live KG Extraction (short)
# ═══════════════════════════════════════════════════════════════════════════════

def phase3_extraction_demo() -> dict[str, Any]:
    """Run a short extraction demo to show the pipeline in action.

    Uses the existing demo_short.py logic but with richer output.

    Returns:
        Dict with extraction results.
    """
    _header(3, "Live KG Extraction Demo")

    # TODO: Reuse logic from examples/demo_short.py
    # Steps:
    # 1. Load ontology classes from Fuseki
    # 2. Generate questions for a subset of classes
    # 3. Run 1 iteration of discovery loop
    # 4. Show extracted entities with confidence scores
    # 5. Show enrichment results (aliases, relations)
    # 6. Show synthesis/deduplication stats

    # from kgbuilder.embedding import OllamaProvider
    # from kgbuilder.storage.vector import QdrantStore
    # from kgbuilder.storage.ontology import FusekiOntologyService
    # from kgbuilder.retrieval import FusionRAGRetriever
    # from kgbuilder.extraction.entity import LLMEntityExtractor
    # from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop

    print("  TODO: Run extraction pipeline (see demo_short.py)")
    print("  Will show:")
    print("    • Ontology class → Research questions")
    print("    • RAG retrieval → Document chunks")
    print("    • LLM extraction → Entities + Relations")
    print("    • Confidence scoring → Enrichment → Dedup")

    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4: GraphQAAgent Chat Session
# ═══════════════════════════════════════════════════════════════════════════════

def phase4_chat_session(questions: list[str] | None = None) -> list[dict[str, Any]]:
    """Interactive Q&A session using GraphQAAgent's /ask endpoint.

    Sends questions to the GraphQAAgent API and displays:
    - The question
    - The answer with confidence
    - Reasoning chain (CoT steps)
    - Provenance sources
    - Latency

    Args:
        questions: Override demo questions. Uses DEMO_QUESTIONS if None.

    Returns:
        List of QA results.
    """
    _header(4, "GraphQAAgent — Chat Session")

    qs = questions or DEMO_QUESTIONS
    results: list[dict[str, Any]] = []

    for i, question in enumerate(qs, 1):
        _subheader(f"Question {i}/{len(qs)}")
        print(f"  Q: {question}")
        print()

        # TODO: Implement actual API call to GraphQAAgent
        # import httpx
        # resp = httpx.post(f"{GRAPHQA_URL}/ask", json={
        #     "question": question,
        #     "strategy": "hybrid_sota",
        #     "language": "de",
        # }, timeout=120.0)
        # data = resp.json()
        #
        # print(f"  A: {data['answer']}")
        # print(f"  Confidence: {data['confidence']:.1%}")
        # print(f"  Latency: {data['latency_ms']:.0f}ms")
        # print(f"  Strategy: hybrid_sota")
        #
        # if data.get('reasoning_chain'):
        #     print(f"\n  Reasoning Chain:")
        #     for step in data['reasoning_chain']:
        #         print(f"    {step}")
        #
        # if data.get('provenance'):
        #     print(f"\n  Provenance ({len(data['provenance'])} sources):")
        #     for p in data['provenance'][:5]:
        #         print(f"    • [{p['source']}] score={p['score']:.3f} {p.get('doc_id', '')}")
        #
        # if data.get('subgraph'):
        #     print(f"\n  Subgraph: {len(data['subgraph'].get('nodes', []))} nodes, "
        #           f"{len(data['subgraph'].get('edges', []))} edges")

        print("  TODO: Call GraphQAAgent /ask endpoint")
        results.append({"question": question, "status": "stub"})

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 5: Reasoning & Provenance Display
# ═══════════════════════════════════════════════════════════════════════════════

def phase5_reasoning_display(qa_results: list[dict[str, Any]]) -> None:
    """Deep dive into reasoning for a selected answer.

    Shows:
    - Full Chain-of-Thought decomposition
    - Multi-hop path through the KG
    - Evidence alignment (which triples support each claim)
    - Subgraph visualization data (for HTML export)
    - Faithfulness verification result

    Args:
        qa_results: Results from phase4 to deep-dive into.
    """
    _header(5, "Reasoning & Provenance Deep Dive")

    # TODO: Pick the most interesting QA result (highest reasoning chain)
    # Resubmit with verbose=True or parse the existing result

    # Display sections:
    # 5a. Chain-of-Thought steps
    # 5b. KG traversal path (which entities/relations were followed)
    # 5c. Evidence alignment table (claim → supporting triple)
    # 5d. Faithfulness verification
    # 5e. Export subgraph as JSON for visualization

    print("  TODO: Display detailed reasoning for best QA answer")
    print("  Will show:")
    print("    • CoT decomposition (question → sub-questions → answers)")
    print("    • Multi-hop KG path (entity → relation → entity → ...)")
    print("    • Evidence table (claim ↔ KG triple)")
    print("    • Faithfulness score and contradicted claims")
    print("    • Subgraph JSON export for visualization")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 6: OntologyExtender — Gap Detection
# ═══════════════════════════════════════════════════════════════════════════════

def phase6_gap_detection() -> dict[str, Any]:
    """Run gap detection to show how the ontology extension loop works.

    Uses OntologyExtender's gap analyzer (if available) or simulates
    the output based on KGB extraction results.

    Returns:
        Dict with gap detection results.
    """
    _header(6, "OntologyExtender — Gap Detection Demo")

    # TODO: Either:
    # a) Call OntologyExtender's gap analyzer directly if installed
    # b) Simulate gap detection using KGBuilder's extraction results:
    #    - Load latest extraction checkpoint
    #    - Compare entity types against ontology classes
    #    - Show uncovered entities (= gaps)
    #    - Show proposed new classes

    # from kgbuilder.hitl.gap_detector import GapDetector
    # from kgbuilder.hitl.config import GapDetectionConfig
    #
    # detector = GapDetector(GapDetectionConfig())
    # report = detector.detect_from_extraction(
    #     entities=extracted_entities,
    #     ontology_classes=ontology_classes,
    # )
    # print(f"  Coverage: {report.coverage_score:.0%}")
    # print(f"  Untyped entities: {len(report.untyped_entities)}")
    # print(f"  Suggested new classes: {report.suggested_new_classes}")

    print("  TODO: Run gap detection (compare entities vs ontology)")
    print("  Will show:")
    print("    • Entity type coverage score")
    print("    • Untyped entities (not in ontology)")
    print("    • Suggested new ontology classes")
    print("    • Proposed class hierarchy placement")

    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 7: HITL Review Simulation
# ═══════════════════════════════════════════════════════════════════════════════

def phase7_hitl_simulation() -> None:
    """Simulate a HITL review session.

    Shows how expert feedback flows through the system:
    1. Gap report → Review items
    2. Expert reviews proposals (accept/reject/edit)
    3. Feedback routed to correct repo (TBox → OntExt, ABox → KGB)
    4. Changes applied and re-validated
    """
    _header(7, "HITL Review Session Simulation")

    # TODO: Use the HITL models to simulate a review session
    # from kgbuilder.hitl import (
    #     HITLConfig, ReviewWorkflow, ExpertProfile, TriggerSource
    # )
    #
    # config = HITLConfig()
    # workflow = ReviewWorkflow(config)
    #
    # expert = ExpertProfile(
    #     id="demo_expert",
    #     name="Prof. Demo",
    #     domain="nuclear",
    # )
    #
    # # Create session from gap report
    # session = workflow.create_session(
    #     expert=expert,
    #     trigger=TriggerSource.GAP_DETECTION,
    #     gap_report=gap_report,
    # )
    #
    # # Show review items
    # for item in session.items:
    #     print(f"  [{item.status.value}] {item.title}")
    #     print(f"    Type: {item.item_type.value}")
    #     print(f"    {item.description}")
    #
    # # Simulate expert decisions
    # ...
    #
    # # Complete and route
    # routing = workflow.complete_session(session)
    # print(f"  Routing: {routing}")

    print("  TODO: Simulate HITL review session")
    print("  Will show:")
    print("    • Gap report → Review items created")
    print("    • Expert reviews each proposal")
    print("    • Feedback routed: TBox → OntExtender, ABox → KGBuilder")
    print("    • Change request files generated")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 8: HTML Export (for professor to explore)
# ═══════════════════════════════════════════════════════════════════════════════

def phase8_html_export() -> list[Path]:
    """Generate interactive HTML visualizations for expert inspection.

    Creates:
    - Ontology tree viewer (TBox)
    - KG graph explorer (ABox)
    - Law graph navigator

    Returns:
        List of paths to generated HTML files.
    """
    _header(8, "Interactive HTML Export")

    # TODO: Use HTMLExporter to generate visualization files
    # from kgbuilder.hitl.export import HTMLExporter
    # from kgbuilder.hitl.config import ExportConfig
    #
    # config = ExportConfig(output_dir=DEMO_OUTPUT / "html")
    # exporter = HTMLExporter(config)
    #
    # ontology_data = ...  # Load from Fuseki
    # kg_data = ...        # Load from Neo4j
    # law_data = ...       # Load from Neo4j (law graph)
    #
    # files = []
    # files.append(exporter.export_ontology_tree(ontology_data))
    # files.append(exporter.export_kg_explorer(kg_data))
    # files.append(exporter.export_law_graph(law_data))
    #
    # for f in files:
    #     print(f"  Generated: {f}")

    print("  TODO: Generate HTML visualizations")
    print(f"  Output directory: {DEMO_OUTPUT / 'html'}")
    print("  Will generate:")
    print("    • ontology_tree.html  (Cytoscape.js class hierarchy)")
    print("    • kg_explorer.html    (interactive entity/relation graph)")
    print("    • law_graph.html      (law structure navigator)")

    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

ALL_PHASES = {
    1: ("Infrastructure Health Check", phase1_infrastructure),
    2: ("Ontology & KG Overview", phase2_ontology_overview),
    3: ("Live KG Extraction", phase3_extraction_demo),
    4: ("GraphQAAgent Chat", phase4_chat_session),
    5: ("Reasoning & Provenance", phase5_reasoning_display),
    6: ("Gap Detection", phase6_gap_detection),
    7: ("HITL Review Simulation", phase7_hitl_simulation),
    8: ("HTML Export", phase8_html_export),
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Full ecosystem demo for professor presentation",
    )
    parser.add_argument(
        "--phases",
        type=str,
        default=None,
        help="Comma-separated list of phases to run (e.g., '1,4,5'). Default: all",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: skip extraction (phase 3) and use cached results",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEMO_OUTPUT,
        help=f"Output directory for demo artifacts (default: {DEMO_OUTPUT})",
    )
    parser.add_argument(
        "--questions",
        nargs="+",
        default=None,
        help="Custom questions for the QA demo (phase 4)",
    )
    return parser.parse_args()


def main() -> None:
    """Run the full ecosystem demo."""
    args = parse_args()
    t0 = time.time()

    DEMO_OUTPUT.mkdir(parents=True, exist_ok=True)

    print(f"\n{SEP}")
    print("  KnowledgeGraphBuilder Ecosystem — Full Demo")
    print(f"  Date: {time.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Output: {args.output}")
    print(SEP)

    # Determine which phases to run
    if args.phases:
        phase_ids = [int(p.strip()) for p in args.phases.split(",")]
    elif args.quick:
        phase_ids = [1, 2, 4, 5, 6, 7]  # Skip extraction and HTML
    else:
        phase_ids = list(ALL_PHASES.keys())

    print(f"  Running phases: {phase_ids}")

    # Track results across phases
    results: dict[str, Any] = {}
    qa_results: list[dict[str, Any]] = []

    for pid in phase_ids:
        if pid not in ALL_PHASES:
            print(f"\n  ⚠ Unknown phase {pid}, skipping")
            continue

        name, func = ALL_PHASES[pid]

        try:
            if pid == 4:
                qa_results = func(questions=args.questions)  # type: ignore[call-arg]
                results[f"phase{pid}"] = qa_results
            elif pid == 5:
                func(qa_results)
            else:
                results[f"phase{pid}"] = func()
        except NotImplementedError as e:
            print(f"\n  ⚠ Phase {pid} ({name}): {e}")
            print("    (Stub not yet implemented — delegate to developer)")
        except Exception as e:
            print(f"\n  ✗ Phase {pid} ({name}) failed: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    elapsed = time.time() - t0
    print(f"\n{SEP}")
    print(f"  Demo Complete — {elapsed:.1f}s total")
    print(f"  Phases run: {len(phase_ids)}")
    print(SEP)

    # Save results
    results_file = args.output / "demo_results.json"
    results_file.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str)
    )
    print(f"  Results saved to: {results_file}")


if __name__ == "__main__":
    main()
