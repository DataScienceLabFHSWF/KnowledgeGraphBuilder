#!/usr/bin/env python3
"""Short Demo: Real KG Construction Loop (limited to 1 iteration).

Connects to the actual infrastructure (Qdrant, Fuseki, Ollama)
and runs a single-iteration discovery loop to demonstrate the full
extraction pipeline end-to-end.

Prerequisites:
    docker-compose up -d   (Neo4j, Qdrant, Fuseki, Ollama)
    Data must be indexed in Qdrant already.

Usage:
    source .venv/bin/activate
    PYTHONPATH=src python examples/demo_short.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.embedding import OllamaProvider
from kgbuilder.storage.vector import QdrantStore
from kgbuilder.storage.ontology import FusekiOntologyService
from kgbuilder.retrieval import FusionRAGRetriever
from kgbuilder.extraction.entity import LLMEntityExtractor, OntologyClassDef
from kgbuilder.extraction.synthesizer import FindingsSynthesizer
from kgbuilder.agents.question_generator import QuestionGenerationAgent
from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop

# ---------------------------------------------------------------------------
# Configuration — sensible defaults, overridden by env vars
# ---------------------------------------------------------------------------
FUSEKI_URL = os.getenv("FUSEKI_URL", "http://localhost:3030")
FUSEKI_DATASET = os.getenv(
    "FUSEKI_DATASET", os.getenv("KGBUILDER_ONTOLOGY_DATASET", "kgbuilder")
)
QDRANT_URL = os.getenv(
    "QDRANT_URL", os.getenv("KGBUILDER_QDRANT_URL", "http://localhost:6333")
)
QDRANT_COLLECTION = os.getenv(
    "QDRANT_COLLECTION", os.getenv("KGBUILDER_QDRANT_COLLECTION", "kgbuilder")
)
OLLAMA_URL = os.getenv(
    "OLLAMA_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:18134")
)
OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL", os.getenv("OLLAMA_LLM_MODEL", "qwen3:8b")
)

# Demo limits  — keep it short for a live presentation
MAX_CLASSES = 3          # only use first N ontology classes
MAX_QUESTIONS = 3        # questions per class
MAX_ITERATIONS = 1       # single discovery iteration
TOP_K_DOCS = 5           # docs retrieved per question
CONFIDENCE = 0.5         # entity confidence threshold

SEPARATOR = "=" * 70


def _header(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def main() -> None:
    t0 = time.time()

    _header("KnowledgeGraphBuilder — Short Demo")
    print(f"  Fuseki:  {FUSEKI_URL}/{FUSEKI_DATASET}")
    print(f"  Qdrant:  {QDRANT_URL} / {QDRANT_COLLECTION}")
    print(f"  Ollama:  {OLLAMA_URL} ({OLLAMA_MODEL})")
    print(
        f"  Limits:  {MAX_CLASSES} classes, {MAX_QUESTIONS} questions, "
        f"{MAX_ITERATIONS} iteration(s)"
    )

    # ------------------------------------------------------------------
    # 1. Connect to services
    # ------------------------------------------------------------------
    _header("Phase 1 — Connect to Infrastructure")

    ontology = FusekiOntologyService(
        fuseki_url=FUSEKI_URL, dataset_name=FUSEKI_DATASET
    )
    qdrant = QdrantStore(url=QDRANT_URL, collection_name=QDRANT_COLLECTION)
    llm = OllamaProvider(model=OLLAMA_MODEL, base_url=OLLAMA_URL)

    doc_count = qdrant.get_points_count()
    all_classes = ontology.get_all_classes()
    print(f"  Qdrant documents indexed:  {doc_count}")
    print(f"  Ontology classes loaded:   {len(all_classes)}")

    # Limit to a few classes for demo speed
    demo_classes = all_classes[:MAX_CLASSES]
    print(f"  Using classes for demo:    {demo_classes}")

    # ------------------------------------------------------------------
    # 2. Generate research questions
    # ------------------------------------------------------------------
    _header("Phase 2 — Generate Research Questions")

    question_agent = QuestionGenerationAgent(ontology_service=ontology)
    all_questions = []
    for cls in demo_classes:
        qs = question_agent.generate_questions(max_questions=MAX_QUESTIONS)
        # Filter to this class
        class_qs = [q for q in qs if q.entity_class == cls][:MAX_QUESTIONS]
        if not class_qs:
            class_qs = qs[:MAX_QUESTIONS]
        all_questions.extend(class_qs)
        print(f"  [{cls}] {len(class_qs)} question(s)")

    print(f"\n  Total questions: {len(all_questions)}")
    for q in all_questions[:6]:
        print(f"    - {q.text[:90]}")
    if len(all_questions) > 6:
        print(f"    ... and {len(all_questions) - 6} more")

    # ------------------------------------------------------------------
    # 3. Run discovery loop (1 iteration)
    # ------------------------------------------------------------------
    _header("Phase 3 — Iterative Discovery (RAG + LLM Extraction)")

    ontology_class_defs = [
        OntologyClassDef(
            uri=f"http://example.org/ontology#{name}",
            label=name,
            description=f"Ontology class: {name}",
        )
        for name in demo_classes
    ]

    retriever = FusionRAGRetriever(
        qdrant_store=qdrant,
        llm_provider=llm,
        dense_weight=0.7,
        sparse_weight=0.3,
        top_k=TOP_K_DOCS,
    )

    extractor = LLMEntityExtractor(
        llm_provider=llm,
        confidence_threshold=CONFIDENCE,
        max_retries=2,
    )

    discovery = IterativeDiscoveryLoop(
        retriever=retriever,
        extractor=extractor,
        question_generator=question_agent,
        ontology_classes=ontology_class_defs,
    )

    print(f"  Running discovery (max {MAX_ITERATIONS} iteration(s))...")
    result = discovery.run_discovery(
        initial_questions=all_questions,
        max_iterations=MAX_ITERATIONS,
        coverage_target=0.8,
        top_k_docs=TOP_K_DOCS,
        ontology_classes=ontology_class_defs,
        extract_relations=False,       # skip relations for speed
        generate_follow_ups=False,     # skip follow-ups for speed
    )

    print(f"\n  Discovery result:")
    print(f"    Success:     {result.success}")
    print(f"    Iterations:  {result.total_iterations}")
    print(f"    Entities:    {len(result.entities)}")
    print(f"    Coverage:    {result.final_coverage:.0%}")
    print(f"    Time:        {result.total_time_sec:.1f}s")

    # ------------------------------------------------------------------
    # 4. Synthesize (deduplicate)
    # ------------------------------------------------------------------
    _header("Phase 4 — Synthesis (Deduplication)")

    synthesizer = FindingsSynthesizer(similarity_threshold=0.85)
    synthesized = synthesizer.synthesize(entities=result.entities)

    merge_rate = 1 - len(synthesized) / max(len(result.entities), 1)
    print(f"  Raw entities:         {len(result.entities)}")
    print(f"  After deduplication:  {len(synthesized)}")
    print(f"  Merge rate:           {merge_rate:.0%}")

    # ------------------------------------------------------------------
    # 5. Summary
    # ------------------------------------------------------------------
    elapsed = time.time() - t0

    _header("Demo Complete")
    print(f"  Total time:       {elapsed:.1f}s")
    print(f"  Entities found:   {len(synthesized)}")
    print(
        f"  LLM tokens used:  "
        f"~{llm.total_prompt_tokens + llm.total_completion_tokens:,}"
    )
    print()

    # Show a sample of discovered entities
    if synthesized:
        print("  Sample entities:")
        for ent in synthesized[:10]:
            desc = (ent.description or "")[:60]
            print(
                f"    - [{ent.entity_type}] {ent.label}  "
                f"(conf={ent.confidence:.2f})"
            )
            if desc:
                print(f"      {desc}")
        if len(synthesized) > 10:
            print(f"    ... and {len(synthesized) - 10} more")
    else:
        print("  No entities discovered (try more iterations or classes).")

    print(f"\n{SEPARATOR}")
    print("  To run the full pipeline with Neo4j assembly:")
    print("    python scripts/full_kg_pipeline.py --max-iterations 2")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
