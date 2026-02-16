#!/usr/bin/env python3
"""Quick-start script for building a Knowledge Graph from your own data.

This is the recommended entry point for new users and new domains.
It wraps the three pipeline stages (ingest, extract, persist) behind a
single CLI so you can go from raw documents + ontology to a populated
Neo4j graph with one command.

Inputs required:
    1. An OWL ontology file        (--ontology)
    2. A directory of documents    (--documents)
    3. Competency questions (opt.) (--cqs)

Example:
    python scripts/quickstart.py \\
        --ontology data/ontology/my-domain.owl \\
        --documents data/my-docs/ \\
        --cqs data/my-cqs.txt \\
        --max-iterations 2

The script will:
    1. Upload the ontology to Fuseki
    2. Ingest & embed documents into Qdrant
    3. Run the iterative discovery extraction loop
    4. Assemble the KG in Neo4j
    5. Validate with auto-generated SHACL shapes
    6. Export results to output/<domain>/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# --- Load .env automatically ---
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse quickstart CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "KnowledgeGraphBuilder -- build a KG from your own documents and ontology."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Minimal run
  python scripts/quickstart.py \\
      --ontology data/ontology/my-domain.owl \\
      --documents data/my-docs/

  # With competency questions and custom output
  python scripts/quickstart.py \\
      --ontology data/ontology/my-domain.owl \\
      --documents data/my-docs/ \\
      --cqs data/my-cqs.txt \\
      --output output/my-domain/ \\
      --max-iterations 3

  # Dry run (parse + extract, no DB writes)
  python scripts/quickstart.py \\
      --ontology data/ontology/my-domain.owl \\
      --documents data/my-docs/ \\
      --dry-run
""",
    )

    # Required inputs
    parser.add_argument(
        "--ontology",
        type=str,
        required=True,
        help="Path to OWL ontology file (.owl, .rdf, .ttl)",
    )
    parser.add_argument(
        "--documents",
        type=str,
        required=True,
        help="Directory containing source documents (PDF, DOCX, PPTX, TXT, XML)",
    )

    # Optional inputs
    parser.add_argument(
        "--cqs",
        type=str,
        default=None,
        help="Path to competency questions file (one question per line)",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Path to JSON profile with pipeline config overrides",
    )

    # Pipeline parameters
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Fuseki dataset name (default: derived from ontology filename)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Qdrant collection name (default: derived from ontology filename)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: output/<domain>/)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=2,
        help="Maximum discovery loop iterations (default: 2)",
    )
    parser.add_argument(
        "--questions-per-class",
        type=int,
        default=3,
        help="Research questions to generate per ontology class (default: 3)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Minimum entity confidence for inclusion (default: 0.5)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of chunks to retrieve per query (default: 10)",
    )
    parser.add_argument(
        "--extensions",
        type=str,
        nargs="+",
        default=[".pdf", ".docx", ".pptx", ".txt", ".md"],
        help="Document file extensions to process (default: .pdf .docx .pptx .txt .md)",
    )

    # Flags
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and extract without writing to databases",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip document ingestion (use if documents are already in Qdrant)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip SHACL validation phase",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def derive_domain_name(ontology_path: Path) -> str:
    """Derive a short domain name from the ontology filename.

    Args:
        ontology_path: Path to the ontology file.

    Returns:
        A slug-like domain name (e.g. ``my-domain`` from ``my-domain.owl``).
    """
    stem = ontology_path.stem
    # Strip common suffixes like -v1.0, -ontology, _ontology
    for suffix in ("-ontology", "_ontology", "-v1", "-v2", "-v1.0", "-v2.0"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem.lower().replace("_", "-")


def load_competency_questions(cq_path: Path) -> list[str]:
    """Load competency questions from a text file (one per line).

    Args:
        cq_path: Path to the CQ file.

    Returns:
        List of non-empty question strings.
    """
    lines = cq_path.read_text(encoding="utf-8").strip().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def count_documents(doc_dir: Path, extensions: list[str]) -> int:
    """Count matching documents in a directory.

    Args:
        doc_dir: Document directory.
        extensions: File extensions to count.

    Returns:
        Number of matching files.
    """
    count = 0
    for ext in extensions:
        count += len(list(doc_dir.rglob(f"*{ext}")))
    return count


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def step_upload_ontology(
    ontology_path: Path,
    dataset: str,
) -> None:
    """Upload ontology to Fuseki.

    Args:
        ontology_path: Path to the OWL ontology file.
        dataset: Fuseki dataset name.
    """
    from kgbuilder.storage.rdf import FusekiStore

    fuseki_url = os.getenv("FUSEKI_URL", "http://localhost:3030")
    fuseki_user = os.getenv("FUSEKI_USER", "admin")
    fuseki_password = os.getenv("FUSEKI_PASSWORD", "")

    content = ontology_path.read_text(encoding="utf-8")

    store = FusekiStore(
        url=fuseki_url,
        dataset_name=dataset,
        username=fuseki_user,
        password=fuseki_password,
    )
    store.load_ontology(content)
    logger.info("ontology_uploaded", dataset=dataset, size_kb=len(content) / 1024)


def step_ingest_documents(
    doc_dir: Path,
    extensions: list[str],
    collection: str,
) -> int:
    """Ingest and embed documents into Qdrant.

    Args:
        doc_dir: Directory containing source documents.
        extensions: File extensions to process.
        collection: Qdrant collection name.

    Returns:
        Number of successfully ingested documents.
    """
    import numpy as np

    from kgbuilder.core.config import ProcessingConfig
    from kgbuilder.document.advanced_processor import AdvancedDocumentProcessor
    from kgbuilder.storage.vector import QdrantStore

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:18134")

    config = ProcessingConfig()
    processor = AdvancedDocumentProcessor(config)
    qdrant = QdrantStore(url=qdrant_url, collection_name=collection)

    # Gather files
    files: list[Path] = []
    for ext in extensions:
        files.extend(doc_dir.rglob(f"*{ext}"))
    files.sort()

    if not files:
        logger.warning("no_documents_found", directory=str(doc_dir), extensions=extensions)
        return 0

    success_count = 0
    try:
        import ollama as ollama_client
    except ImportError:
        logger.error("ollama_package_missing", hint="pip install ollama")
        raise

    for idx, fpath in enumerate(files, 1):
        try:
            doc_result = processor.process_document(fpath)
            for chunk_id, chunk_text in enumerate(doc_result.chunks):
                response = ollama_client.embed(
                    model=os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding"),
                    input=chunk_text,
                )
                embedding = np.array(response.embeddings[0], dtype=np.float32)
                meta = doc_result.metadatas[chunk_id].copy() if doc_result.metadatas else {}
                meta["content"] = chunk_text
                qdrant.store(
                    ids=[f"{fpath.stem}_chunk_{chunk_id}"],
                    embeddings=[embedding],
                    metadata=[meta],
                )
            success_count += 1
            logger.info(
                "document_ingested",
                file=fpath.name,
                chunks=len(doc_result.chunks),
                progress=f"{idx}/{len(files)}",
            )
        except Exception as exc:
            logger.warning("document_ingest_failed", file=fpath.name, error=str(exc))

    return success_count


def step_run_extraction(
    dataset: str,
    collection: str,
    output_dir: Path,
    max_iterations: int,
    questions_per_class: int,
    confidence_threshold: float,
    top_k: int,
    cqs: list[str] | None,
    dry_run: bool,
) -> dict:
    """Run iterative discovery extraction loop.

    Args:
        dataset: Fuseki dataset name.
        collection: Qdrant collection name.
        output_dir: Directory for checkpoints and exports.
        max_iterations: Discovery loop iterations.
        questions_per_class: Questions per ontology class.
        confidence_threshold: Minimum entity confidence.
        top_k: Chunks to retrieve per query.
        cqs: Competency questions (optional).
        dry_run: If True, skip database writes.

    Returns:
        Summary dict with entity/relation counts.
    """
    from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop
    from kgbuilder.agents.question_generator import QuestionGenerationAgent
    from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
    from kgbuilder.embedding import OllamaProvider
    from kgbuilder.extraction.entity import LLMEntityExtractor, OntologyClassDef
    from kgbuilder.extraction.relation import LLMRelationExtractor
    from kgbuilder.extraction.synthesizer import FindingsSynthesizer
    from kgbuilder.retrieval import FusionRAGRetriever
    from kgbuilder.storage.neo4j_store import Neo4jGraphStore
    from kgbuilder.storage.ontology import FusekiOntologyService
    from kgbuilder.storage.protocol import Edge, Node
    from kgbuilder.storage.vector import QdrantStore

    fuseki_url = os.getenv("FUSEKI_URL", "http://localhost:3030")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:18134")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "changeme")

    # --- Ontology ---
    ontology_service = FusekiOntologyService(fuseki_url, dataset)
    all_classes = ontology_service.get_all_classes()
    if not all_classes:
        raise RuntimeError(f"No classes found in Fuseki dataset '{dataset}'")

    print(f"  Ontology classes: {len(all_classes)}")
    print(f"  Classes: {', '.join(all_classes[:8])}{'...' if len(all_classes) > 8 else ''}")

    # --- Components ---
    llm = OllamaProvider(model=ollama_model, base_url=ollama_url)
    qdrant = QdrantStore(url=qdrant_url, collection_name=collection)

    retriever = FusionRAGRetriever(
        qdrant_store=qdrant,
        llm_provider=llm,
        top_k=top_k,
    )
    entity_extractor = LLMEntityExtractor(
        llm_provider=llm,
        confidence_threshold=confidence_threshold,
        max_retries=3,
    )

    # --- Question generation ---
    question_agent = QuestionGenerationAgent(ontology_service=ontology_service)
    all_questions: list[str] = []
    for class_name in all_classes:
        questions = question_agent.generate_questions(max_questions=questions_per_class)
        all_questions.extend(questions)

    # Add user-provided CQs
    if cqs:
        all_questions.extend(cqs)
        print(f"  Added {len(cqs)} competency questions")

    print(f"  Research questions: {len(all_questions)}")

    # --- Discovery loop ---
    class_defs = [
        OntologyClassDef(
            uri=f"http://example.org/ontology#{name}",
            label=name,
            description=f"Class {name} from the domain ontology",
        )
        for name in all_classes
    ]

    discovery_loop = IterativeDiscoveryLoop(
        retriever=retriever,
        entity_extractor=entity_extractor,
        ontology_classes=class_defs,
        max_iterations=max_iterations,
    )

    print(f"\n  Running discovery ({max_iterations} iterations)...")
    discovery_result = discovery_loop.run(questions=all_questions)
    raw_entities = discovery_result.entities if discovery_result.entities else []
    print(f"  Raw entities: {len(raw_entities)}")

    # --- Synthesis ---
    synthesizer = FindingsSynthesizer()
    synthesized = synthesizer.synthesize(raw_entities)
    print(f"  Deduplicated entities: {len(synthesized)}")

    # --- Relation extraction ---
    relation_extractor = LLMRelationExtractor(
        llm_provider=llm,
        confidence_threshold=confidence_threshold,
        max_retries=3,
    )

    entities_for_rel = [
        ExtractedEntity(
            id=se.id,
            label=se.label,
            entity_type=se.entity_type,
            description=se.description or "",
            confidence=se.confidence,
            evidence=se.evidence,
        )
        for se in synthesized
    ]

    ontology_relations = ontology_service.get_relations()
    all_relations: list[ExtractedRelation] = []
    for entity in synthesized[:50]:  # limit to avoid excessive LLM calls
        query = f"{entity.label} relationships"
        try:
            results = retriever.retrieve(query=query, top_k=5)
            for result in results:
                chunk_lower = result.content.lower()
                in_chunk = [
                    e
                    for e in entities_for_rel
                    if e.label.lower() in chunk_lower and e.id != entity.id
                ]
                if in_chunk:
                    rels = relation_extractor.extract(
                        text=result.content,
                        entities=[e for e in entities_for_rel if e.label.lower() in chunk_lower],
                        ontology_relations=ontology_relations,
                    )
                    all_relations.extend(rels)
        except Exception:
            continue

    print(f"  Relations: {len(all_relations)}")

    # --- Checkpoint ---
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "timestamp": datetime.now().isoformat(),
        "domain": dataset,
        "entities": [
            {"id": e.id, "label": e.label, "type": e.entity_type, "confidence": e.confidence}
            for e in synthesized
        ],
        "relations": [
            {
                "source": r.source_entity_id,
                "predicate": r.predicate,
                "target": r.target_entity_id,
                "confidence": r.confidence,
            }
            for r in all_relations
        ],
    }
    ckpt_path = output_dir / "checkpoint.json"
    ckpt_path.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False))
    print(f"  Checkpoint saved: {ckpt_path}")

    # --- Persist ---
    if not dry_run:
        try:
            neo4j_store = Neo4jGraphStore(
                uri=neo4j_uri, user=neo4j_user, password=neo4j_password
            )
            for se in synthesized:
                neo4j_store.upsert_node(
                    Node(
                        id=se.id,
                        label=se.entity_type,
                        properties={
                            "name": se.label,
                            "description": se.description or "",
                            "confidence": se.confidence,
                            "graph_type": dataset,
                        },
                    )
                )
            for rel in all_relations:
                neo4j_store.upsert_edge(
                    Edge(
                        source_id=rel.source_entity_id,
                        target_id=rel.target_entity_id,
                        label=rel.predicate,
                        properties={"confidence": rel.confidence, "graph_type": dataset},
                    )
                )
            neo4j_store.close()
            print(f"  Neo4j: {len(synthesized)} nodes, {len(all_relations)} edges written")
        except Exception as exc:
            logger.warning("neo4j_write_failed", error=str(exc))
            print(f"  [WARN] Neo4j write failed: {exc}")

    return {
        "entities": len(synthesized),
        "relations": len(all_relations),
        "classes": len(all_classes),
        "questions": len(all_questions),
    }


def step_validate(
    ontology_path: Path,
    output_dir: Path,
) -> None:
    """Run SHACL validation and quality scoring.

    Args:
        ontology_path: Path to the OWL ontology file.
        output_dir: Directory for validation reports.
    """
    from kgbuilder.storage.neo4j_store import Neo4jGraphStore
    from kgbuilder.validation.scorer import KGQualityScorer

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "changeme")

    try:
        scorer = KGQualityScorer(ontology_owl_path=ontology_path)
        neo4j_store = Neo4jGraphStore(
            uri=neo4j_uri, user=neo4j_user, password=neo4j_password
        )
        report = scorer.score_neo4j_store(neo4j_store)
        neo4j_store.close()

        report_path = output_dir / "quality_report.json"
        report_path.write_text(json.dumps(report.__dict__, indent=2, default=str))
        print(f"  Quality score: {report.combined_score:.2f}")
        print(f"  Report saved: {report_path}")
    except Exception as exc:
        logger.warning("validation_failed", error=str(exc))
        print(f"  [WARN] Validation skipped: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the quickstart pipeline."""
    args = parse_args()

    ontology_path = Path(args.ontology)
    doc_dir = Path(args.documents)

    # Validate inputs
    if not ontology_path.exists():
        print(f"[ERROR] Ontology file not found: {ontology_path}")
        sys.exit(1)
    if not doc_dir.is_dir():
        print(f"[ERROR] Document directory not found: {doc_dir}")
        sys.exit(1)

    domain = derive_domain_name(ontology_path)
    dataset = args.dataset or domain
    collection = args.collection or domain
    output_dir = Path(args.output) if args.output else Path("output") / domain

    cqs: list[str] | None = None
    if args.cqs:
        cq_path = Path(args.cqs)
        if cq_path.exists():
            cqs = load_competency_questions(cq_path)
        else:
            print(f"[WARN] CQ file not found: {cq_path}, continuing without CQs")

    doc_count = count_documents(doc_dir, args.extensions)

    # Banner
    print("\n" + "=" * 70)
    print("KnowledgeGraphBuilder -- Quick Start")
    print("=" * 70)
    print(f"  Domain:          {domain}")
    print(f"  Ontology:        {ontology_path}")
    print(f"  Documents:       {doc_dir}  ({doc_count} files)")
    print(f"  CQs:             {len(cqs) if cqs else 'none'}")
    print(f"  Fuseki dataset:  {dataset}")
    print(f"  Qdrant coll.:    {collection}")
    print(f"  Output:          {output_dir}")
    print(f"  Max iterations:  {args.max_iterations}")
    print(f"  Dry run:         {args.dry_run}")
    print("=" * 70)

    start = time.time()

    # Step 1: Upload ontology
    print("\n[1/4] Uploading ontology to Fuseki...")
    try:
        step_upload_ontology(ontology_path, dataset)
        print("  Done.")
    except Exception as exc:
        print(f"  [ERROR] Failed: {exc}")
        print("  Make sure Fuseki is running (docker-compose up -d fuseki)")
        sys.exit(1)

    # Step 2: Ingest documents
    if not args.skip_ingest:
        print(f"\n[2/4] Ingesting {doc_count} documents into Qdrant...")
        try:
            ingested = step_ingest_documents(doc_dir, args.extensions, collection)
            print(f"  Done. {ingested}/{doc_count} documents ingested.")
        except Exception as exc:
            print(f"  [ERROR] Ingestion failed: {exc}")
            sys.exit(1)
    else:
        print("\n[2/4] Skipping ingestion (--skip-ingest)")

    # Step 3: Extract & assemble
    print("\n[3/4] Running extraction pipeline...")
    try:
        summary = step_run_extraction(
            dataset=dataset,
            collection=collection,
            output_dir=output_dir,
            max_iterations=args.max_iterations,
            questions_per_class=args.questions_per_class,
            confidence_threshold=args.confidence_threshold,
            top_k=args.top_k,
            cqs=cqs,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"  [ERROR] Extraction failed: {exc}")
        logger.error("extraction_failed", error=str(exc), exc_info=True)
        sys.exit(1)

    # Step 4: Validate
    if not args.skip_validation and not args.dry_run:
        print("\n[4/4] Validating KG...")
        step_validate(ontology_path, output_dir)
    else:
        print("\n[4/4] Validation skipped")

    elapsed = time.time() - start

    # Summary
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    print(f"  Entities:   {summary['entities']}")
    print(f"  Relations:  {summary['relations']}")
    print(f"  Classes:    {summary['classes']}")
    print(f"  Questions:  {summary['questions']}")
    print(f"  Time:       {elapsed / 60:.1f} min")
    print(f"  Output:     {output_dir}")
    if not args.dry_run:
        print(f"  Neo4j:      http://localhost:7474  (graph_type: '{dataset}')")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
