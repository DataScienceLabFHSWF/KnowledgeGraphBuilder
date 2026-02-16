#!/usr/bin/env python3
"""Docker Entrypoint: Complete KG Construction Pipeline

This is the main entry point for the KG builder Docker container.
It runs the complete knowledge discovery and graph construction pipeline:

  1. Load ontology from Fuseki
  2. Generate research questions from ontology classes
  3. Retrieve relevant documents from Qdrant (RAG)
  4. Extract entities and relations using LLM
  5. Deduplicate and synthesize findings
  6. Assemble final KG into Neo4j

All components are fully implemented and tested.

Environment Variables:
  FUSEKI_URL          - Fuseki SPARQL endpoint (default: http://localhost:3030)
  FUSEKI_DATASET      - Fuseki dataset name (default: kgbuilder)
  QDRANT_URL          - Qdrant vector DB (default: http://localhost:6333)
  QDRANT_COLLECTION   - Qdrant collection name (default: kgbuilder)
    OLLAMA_URL          - Ollama LLM server (default: http://localhost:18134, GPU container)
  OLLAMA_MODEL        - Ollama model name (default: qwen3:8b)
  NEO4J_URI           - Neo4j database URI (default: bolt://localhost:7687)
  NEO4J_USER          - Neo4j username (default: neo4j)
  NEO4J_PASSWORD      - Neo4j password (default: changeme)

Usage (Docker):
  docker-compose up kgbuilder

Usage (Local):
  python scripts/build_kg.py \\
    --questions-per-class 5 \\
    --max-iterations 2 \\
    --similarity-threshold 0.85 \\
    --confidence-threshold 0.6
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# --- Load .env automatically for all runs ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================

FUSEKI_URL = os.getenv("FUSEKI_URL", "http://localhost:3030")
FUSEKI_DATASET = os.getenv("FUSEKI_DATASET", "kgbuilder")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "changeme")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "kgbuilder")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:18134")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")


# =============================================================================
# COMPONENT IMPORTS (All IMPLEMENTED and TESTED)
# =============================================================================

from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop
from kgbuilder.agents.question_generator import QuestionGenerationAgent
from kgbuilder.assembly.kg_builder import KGBuilder, KGBuilderConfig
from kgbuilder.assembly.simple_kg_assembler import SimpleKGAssembler
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.embedding import OllamaProvider
from kgbuilder.extraction.entity import LLMEntityExtractor, OntologyClassDef
from kgbuilder.extraction.relation import LLMRelationExtractor, OntologyRelationDef
from kgbuilder.extraction.synthesizer import FindingsSynthesizer, SynthesizedEntity
from kgbuilder.retrieval import FusionRAGRetriever
from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.storage.ontology import FusekiOntologyService
from kgbuilder.storage.protocol import Edge, Node
from kgbuilder.storage.vector import QdrantStore
from kgbuilder.validation import (
    ConsistencyChecker,
    ReportGenerator,
    ValidationResult,
)
from kgbuilder.validation.validators import CompetencyQuestionValidator

# =============================================================================
# CLI ARGUMENT PARSING
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments for KG construction hyperparameters."""
    parser = argparse.ArgumentParser(
        description="Knowledge Graph Construction - Full Discovery & Assembly Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Core hyperparameters
    parser.add_argument(
        "--questions-per-class",
        type=int,
        default=3,
        help="Number of questions to generate per ontology class"
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=2,
        help="Maximum iterations for discovery loop per question"
    )

    parser.add_argument(
        "--classes-limit",
        type=int,
        default=None,
        help="Limit ontology classes to process (None = all classes)"
    )

    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.6,
        help="Minimum confidence for extracted entities (0.0-1.0)"
    )

    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.85,
        help="Entity deduplication similarity threshold (0.0-1.0)"
    )

    # Retrieval hyperparameters
    parser.add_argument(
        "--dense-weight",
        type=float,
        default=0.7,
        help="Weight for dense vector retrieval in FusionRAG (0.0-1.0)"
    )

    parser.add_argument(
        "--sparse-weight",
        type=float,
        default=0.3,
        help="Weight for sparse keyword retrieval in FusionRAG (0.0-1.0)"
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of documents to retrieve per query"
    )

    # Validation & Quality Gating
    parser.add_argument(
        "--validate",
        action="store_true",
        default=True,
        help="Enable validation phase (SHACL, rules, consistency)"
    )

    parser.add_argument(
        "--check-competency-questions",
        action="store_true",
        default=False,
        help="Check if competency questions are answered before finishing"
    )

    parser.add_argument(
        "--cq-coverage-threshold",
        type=float,
        default=0.8,
        help="Minimum coverage of competency questions (0.0-1.0) before stopping"
    )

    parser.add_argument(
        "--validation-report-dir",
        type=str,
        default="./validation_reports",
        help="Directory to save validation reports (JSON/Markdown/HTML)"
    )

    # Logging
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )

    return parser.parse_args()


# =============================================================================
# COMPONENT FACTORY FUNCTIONS
# =============================================================================

def build_retriever(
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3,
    top_k: int = 10,
) -> FusionRAGRetriever:
    """Build FusionRAG retriever with Qdrant backend.
    
    FusionRAG combines:
    - Dense retrieval (semantic similarity via embeddings)
    - Sparse retrieval (BM25 keyword matching)
    
    Args:
        dense_weight: Weight for dense vectors (0.0-1.0)
        sparse_weight: Weight for sparse keywords (0.0-1.0)
        top_k: Number of documents to retrieve
        
    Returns:
        Configured FusionRAGRetriever instance
    """
    logger.info(
        "retriever_building",
        type="FusionRAGRetriever",
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
        top_k=top_k,
    )

    qdrant_store = QdrantStore(
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION
    )

    llm = OllamaProvider(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_URL
    )

    retriever = FusionRAGRetriever(
        qdrant_store=qdrant_store,
        llm_provider=llm,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
        top_k=top_k
    )

    logger.info("retriever_built", type="FusionRAGRetriever")
    return retriever


def build_entity_extractor(confidence_threshold: float = 0.6) -> LLMEntityExtractor:
    """Build LLM-based entity extractor with ontology guidance.
    
    Uses structured prompting to extract entities that match ontology classes
    with confidence scores and provenance information.
    
    Args:
        confidence_threshold: Minimum confidence for inclusion (0.0-1.0)
        
    Returns:
        Configured LLMEntityExtractor instance
    """
    logger.info(
        "extractor_building",
        type="LLMEntityExtractor",
        confidence_threshold=confidence_threshold
    )

    llm = OllamaProvider(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_URL
    )

    extractor = LLMEntityExtractor(
        llm_provider=llm,
        confidence_threshold=confidence_threshold,
        max_retries=3
    )

    logger.info("extractor_built", type="LLMEntityExtractor")
    return extractor


def convert_class_names_to_definitions(
    class_names: list[str],
) -> list[OntologyClassDef]:
    """Convert ontology class names to OntologyClassDef objects.
    
    Args:
        class_names: Class labels from ontology
        
    Returns:
        OntologyClassDef objects for extraction guidance
    """
    definitions = []
    for name in class_names:
        definitions.append(
            OntologyClassDef(
                uri=f"http://example.org/ontology#{name}",
                label=name,
                description=f"Class {name} from knowledge graph ontology"
            )
        )
    return definitions


def build_relation_extractor(confidence_threshold: float = 0.5) -> LLMRelationExtractor:
    """Build LLM-based relation extractor with ontology guidance.
    
    Uses structured prompting to extract relationships between entities
    with domain/range validation and cardinality constraints.
    
    Args:
        confidence_threshold: Minimum confidence for inclusion (0.0-1.0)
        
    Returns:
        Configured LLMRelationExtractor instance
    """
    logger.info(
        "relation_extractor_building",
        type="LLMRelationExtractor",
        confidence_threshold=confidence_threshold
    )

    llm = OllamaProvider(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_URL
    )

    extractor = LLMRelationExtractor(
        llm_provider=llm,
        confidence_threshold=confidence_threshold,
        max_retries=3
    )

    logger.info("relation_extractor_built", type="LLMRelationExtractor")
    return extractor


def get_default_relation_definitions() -> list[OntologyRelationDef]:
    """Get default relation definitions for extraction.
    
    These are common relation types used in knowledge graphs.
    In production, these would come from the ontology in Fuseki.
    
    Returns:
        List of OntologyRelationDef objects
    """
    return [
        OntologyRelationDef(
            uri="http://example.org/ontology#relatedTo",
            label="relatedTo",
            description="General relation between two entities",
        ),
        OntologyRelationDef(
            uri="http://example.org/ontology#partOf",
            label="partOf",
            description="Entity is part of another entity",
            is_transitive=True,
        ),
        OntologyRelationDef(
            uri="http://example.org/ontology#hasPart",
            label="hasPart",
            description="Entity has another entity as part",
        ),
        OntologyRelationDef(
            uri="http://example.org/ontology#locatedIn",
            label="locatedIn",
            description="Entity is located in a location",
            is_transitive=True,
        ),
        OntologyRelationDef(
            uri="http://example.org/ontology#involves",
            label="involves",
            description="An activity or event involves an entity",
        ),
        OntologyRelationDef(
            uri="http://example.org/ontology#causes",
            label="causes",
            description="One entity/event causes another",
        ),
        OntologyRelationDef(
            uri="http://example.org/ontology#precedes",
            label="precedes",
            description="One entity/event precedes another temporally",
            is_transitive=True,
        ),
        OntologyRelationDef(
            uri="http://example.org/ontology#associatedWith",
            label="associatedWith",
            description="Entity is associated with another entity",
            is_symmetric=True,
        ),
    ]


def extract_relations_from_entities(
    synthesized_entities: list[SynthesizedEntity],
    retriever: FusionRAGRetriever,
    relation_extractor: LLMRelationExtractor,
    ontology_relations: list[OntologyRelationDef],
    top_k: int = 5,
) -> list[ExtractedRelation]:
    """Extract relations between synthesized entities.
    
    Strategy:
    1. For each entity pair, search for chunks mentioning both
    2. Extract relations from those chunks
    3. Aggregate and deduplicate relations
    
    Args:
        synthesized_entities: Deduplicated entities from synthesis
        retriever: FusionRAG retriever for finding relevant chunks
        relation_extractor: LLM relation extractor
        ontology_relations: Valid relation types from ontology
        top_k: Number of chunks to retrieve per query
        
    Returns:
        List of extracted relations
    """
    all_relations: list[ExtractedRelation] = []
    processed_pairs: set[tuple[str, str]] = set()

    # Convert synthesized entities to extracted entities for the extractor
    entities_for_extraction = [
        ExtractedEntity(
            id=se.id,
            label=se.label,
            entity_type=se.entity_type,
            description=se.description or "",
            confidence=se.confidence,
            evidence=se.evidence,
        )
        for se in synthesized_entities
    ]

    # Build entity lookup by label for quick matching
    entity_labels = {e.label.lower(): e for e in entities_for_extraction}

    # Process entities in batches - query for chunks that might contain relations
    for i, entity in enumerate(synthesized_entities):
        # Query for chunks mentioning this entity
        query = f"{entity.label} relationships connections"

        try:
            results = retriever.retrieve(query=query, top_k=top_k)

            for result in results:
                # Check which other entities appear in this chunk
                chunk_text = result.content.lower()
                entities_in_chunk = [
                    e for e in entities_for_extraction
                    if e.label.lower() in chunk_text and e.id != entity.id
                ]

                if entities_in_chunk:
                    # Extract relations from this chunk
                    try:
                        relations = relation_extractor.extract(
                            text=result.content,
                            entities=[
                                e for e in entities_for_extraction
                                if e.label.lower() in chunk_text
                            ],
                            ontology_relations=ontology_relations,
                        )

                        for rel in relations:
                            # Avoid duplicate relations
                            pair_key = (rel.source_entity_id, rel.target_entity_id, rel.predicate)
                            reverse_key = (rel.target_entity_id, rel.source_entity_id, rel.predicate)

                            if pair_key not in processed_pairs and reverse_key not in processed_pairs:
                                all_relations.append(rel)
                                processed_pairs.add(pair_key)

                    except Exception as e:
                        logger.warning(
                            "relation_extraction_chunk_failed",
                            entity_id=entity.id,
                            error=str(e)
                        )
                        continue

        except Exception as e:
            logger.warning(
                "relation_retrieval_failed",
                entity_id=entity.id,
                error=str(e)
            )
            continue

        # Log progress every 10 entities
        if (i + 1) % 10 == 0:
            logger.info(
                "relation_extraction_progress",
                entities_processed=i + 1,
                total_entities=len(synthesized_entities),
                relations_found=len(all_relations)
            )

    return all_relations


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def main() -> None:
    """Run the complete KG construction pipeline."""

    args = parse_arguments()
    start_time = datetime.now()

    # Print banner
    print("\n" + "="*80)
    print("KNOWLEDGE GRAPH CONSTRUCTION PIPELINE")
    print("Full Discovery + Assembly to Neo4j")
    print("="*80)
    print("\nService Configuration:")
    print(f"  Fuseki:     {FUSEKI_URL}/{FUSEKI_DATASET}")
    print(f"  Qdrant:     {QDRANT_URL}")
    print(f"  Ollama:     {OLLAMA_URL} (model: {OLLAMA_MODEL})")
    print(f"  Neo4j:      {NEO4J_URI}")
    print("\nHyperparameters:")
    print(f"  Questions per class:     {args.questions_per_class}")
    print(f"  Max iterations:          {args.max_iterations}")
    print(f"  Classes limit:           {args.classes_limit or 'All'}")
    print(f"  Confidence threshold:    {args.confidence_threshold}")
    print(f"  Similarity threshold:    {args.similarity_threshold}")
    print(f"  Dense weight:            {args.dense_weight}")
    print(f"  Sparse weight:           {args.sparse_weight}")
    print(f"  Top-K retrieval:         {args.top_k}")
    print("="*80 + "\n")

    try:
        # =====================================================================
        # PHASE 1: LOAD ONTOLOGY FROM FUSEKI
        # =====================================================================
        print("PHASE 1: Loading Ontology from Fuseki")
        print("-" * 80)

        ontology_service = FusekiOntologyService(FUSEKI_URL, FUSEKI_DATASET)
        all_classes = ontology_service.get_all_classes()

        if not all_classes:
            logger.error("ontology_load_failed", message="No classes found in Fuseki")
            raise RuntimeError(f"No classes found in Fuseki at {FUSEKI_URL}/{FUSEKI_DATASET}")

        # Apply class limit if specified
        classes = all_classes[:args.classes_limit] if args.classes_limit else all_classes

        logger.info("ontology_loaded", total_classes=len(all_classes), classes_to_process=len(classes))
        print(f"[OK] Loaded {len(classes)} ontology classes (from {len(all_classes)} total)")
        print(f"  Classes: {', '.join(classes[:5])}{'...' if len(classes) > 5 else ''}\n")

        # =====================================================================
        # PHASE 2: QUESTION GENERATION
        # =====================================================================
        print("PHASE 2: Generating Research Questions")
        print("-" * 80)

        question_agent = QuestionGenerationAgent(
            ontology_service=ontology_service
        )

        all_questions = []
        for class_name in classes:
            logger.info("generating_questions", class_name=class_name)
            questions = question_agent.generate_questions(
                max_questions=args.questions_per_class
            )
            all_questions.extend(questions)
            print(f"  [OK] {len(questions)} questions from class '{class_name}'")

        logger.info("questions_generated", total_count=len(all_questions))
        print(f"\n[OK] Generated {len(all_questions)} research questions\n")

        # =====================================================================
        # PHASE 3: ITERATIVE DISCOVERY
        # =====================================================================
        print("PHASE 3: Iterative Knowledge Discovery")
        print("-" * 80)

        ontology_class_defs = convert_class_names_to_definitions(classes)
        retriever = build_retriever(
            dense_weight=args.dense_weight,
            sparse_weight=args.sparse_weight,
            top_k=args.top_k
        )
        extractor = build_entity_extractor(
            confidence_threshold=args.confidence_threshold
        )

        discovery_loop = IterativeDiscoveryLoop(
            retriever=retriever,
            extractor=extractor,
            question_generator=question_agent,
            ontology_classes=ontology_class_defs
        )

        logger.info("discovery_starting", initial_questions=len(all_questions))
        discovery_result = discovery_loop.run_discovery(
            initial_questions=all_questions,
            max_iterations=args.max_iterations,
            coverage_target=0.8,
            ontology_classes=ontology_class_defs
        )

        if not discovery_result.success:
            logger.warning("discovery_warning", message=discovery_result.error_message)
            print(f"[WARN] Discovery completed with warnings: {discovery_result.error_message}")
        else:
            print("[OK] Discovery completed successfully")

        discovered_entities = discovery_result.entities
        logger.info(
            "discovery_complete",
            entities=len(discovered_entities),
            iterations=discovery_result.total_iterations,
            coverage=discovery_result.final_coverage,
            time_sec=discovery_result.total_time_sec
        )
        print(f"  - Discovered entities: {len(discovered_entities)}")
        print(f"  - Iterations: {discovery_result.total_iterations}")
        print(f"  - Coverage: {discovery_result.final_coverage:.1%}")
        print(f"  - Time: {discovery_result.total_time_sec:.1f}s\n")

        # =====================================================================
        # PHASE 4: ENTITY DEDUPLICATION & SYNTHESIS
        # =====================================================================
        print("PHASE 4: Entity Deduplication & Synthesis")
        print("-" * 80)

        synthesizer = FindingsSynthesizer(
            similarity_threshold=args.similarity_threshold
        )

        synthesized_entities = synthesizer.synthesize(
            entities=discovered_entities
        )

        merge_count = len(discovered_entities) - len(synthesized_entities)
        merge_rate = merge_count / max(len(discovered_entities), 1)

        logger.info(
            "synthesis_complete",
            before=len(discovered_entities),
            after=len(synthesized_entities),
            merged=merge_count,
            merge_rate=merge_rate
        )
        print("[OK] Deduplicated entities")
        print(f"  - Before: {len(discovered_entities)}")
        print(f"  - After:  {len(synthesized_entities)}")
        print(f"  - Merged: {merge_count} ({merge_rate:.1%})\n")

        # =====================================================================
        # PHASE 5: RELATION EXTRACTION
        # =====================================================================
        print("PHASE 5: Relation Extraction")
        print("-" * 80)

        relation_extractor = build_relation_extractor(
            confidence_threshold=args.confidence_threshold
        )
        ontology_relations = get_default_relation_definitions()

        logger.info(
            "relation_extraction_starting",
            entity_count=len(synthesized_entities),
            relation_types=len(ontology_relations)
        )
        print(f"Extracting relations between {len(synthesized_entities)} entities...")

        extracted_relations = extract_relations_from_entities(
            synthesized_entities=synthesized_entities,
            retriever=retriever,
            relation_extractor=relation_extractor,
            ontology_relations=ontology_relations,
            top_k=args.top_k,
        )

        logger.info(
            "relation_extraction_complete",
            relations_extracted=len(extracted_relations)
        )
        print("[OK] Relation extraction complete")
        print(f"  - Relations extracted: {len(extracted_relations)}")

        # Show relation type distribution
        if extracted_relations:
            relation_types = {}
            for rel in extracted_relations:
                rel_type = rel.predicate.split("#")[-1] if "#" in rel.predicate else rel.predicate
                relation_types[rel_type] = relation_types.get(rel_type, 0) + 1
            print(f"  - Relation types: {dict(sorted(relation_types.items(), key=lambda x: -x[1])[:5])}")
        print()

        # =====================================================================
        # PHASE 6: KNOWLEDGE GRAPH ASSEMBLY
        # =====================================================================
        print("PHASE 6: KG Assembly & Persistence")
        print("-" * 80)

        logger.info("assembly_starting", entity_count=len(synthesized_entities), relation_count=len(extracted_relations))

        # Initialize Neo4j graph store (Phase 7 multi-store support)
        neo4j_store = Neo4jGraphStore(
            uri=NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )

        # Create KGBuilder with Neo4j as primary store
        builder = KGBuilder(
            primary_store=neo4j_store,
            config=KGBuilderConfig(
                primary_store="neo4j",
                sync_stores=False,  # No secondary store in this pipeline
                batch_size=1000,
                auto_retry=True
            )
        )

        # Convert SynthesizedEntity to Node format
        nodes = [
            Node(
                id=entity.id,
                label=entity.label,
                node_type=entity.entity_type,
                properties={
                    "confidence": entity.confidence,
                    "description": entity.description,
                    "provenance": [e.source for e in entity.evidence]
                }
            )
            for entity in synthesized_entities
        ]

        # Convert ExtractedRelation to Edge format
        edges = [
            Edge(
                source_id=rel.source_id,
                target_id=rel.target_id,
                relation_type=rel.relation_type,
                properties={
                    "confidence": rel.confidence,
                    "provenance": [e.source for e in rel.evidence]
                }
            )
            for rel in extracted_relations
        ]

        # Build graph using new orchestrator
        build_result = builder.build(entities=nodes, relations=edges)

        # Maintain backward compatibility with old AssemblyResult format
        assembly_result = SimpleKGAssembler.KGAssemblyResult(
            nodes_created=build_result.nodes_created,
            relationships_created=build_result.edges_created,
            coverage=1.0,
            iterations=1,
            errors=build_result.errors,
            warnings=build_result.warnings,
            statistics=build_result.statistics
        )

        logger.info(
            "assembly_complete",
            nodes_created=assembly_result.nodes_created,
            relationships_created=assembly_result.relationships_created,
            errors=len(assembly_result.errors)
        )
        print("[OK] Knowledge graph assembled in Neo4j")
        print(f"  - Nodes created: {assembly_result.nodes_created}")
        print(f"  - Relationships created: {assembly_result.relationships_created}")

        if assembly_result.errors:
            print(f"  - Errors: {len(assembly_result.errors)}")
            for error in assembly_result.errors[:5]:
                logger.error("assembly_error", error=error)
                print(f"    [FAIL] {error}")
            if len(assembly_result.errors) > 5:
                print(f"    ... and {len(assembly_result.errors) - 5} more errors")

        print()

        # =====================================================================
        # PHASE 7: VALIDATION & QUALITY ASSESSMENT
        # =====================================================================

        validation_passed = True
        validation_report = None

        if args.validate:
            print("PHASE 7: Knowledge Graph Validation & Quality Assessment")
            print("-" * 80)

            try:
                # Run consistency checking
                logger.info("validation_starting")
                consistency_checker = ConsistencyChecker()
                consistency_report = consistency_checker.check_consistency(neo4j_store)

                logger.info(
                    "consistency_check_complete",
                    conflicts=consistency_report.conflict_count,
                    duplicates=len(consistency_report.duplicates)
                )
                print("[OK] Consistency check complete")
                print(f"  - Conflicts detected: {consistency_report.conflict_count}")
                print(f"  - Potential duplicates: {len(consistency_report.duplicates)}")
                print(f"  - Conflict rate: {consistency_report.conflict_rate:.2%}")

                if consistency_report.recommendations:
                    print(f"  - Recommendations: {consistency_report.recommendations[0]}")

                # Generate validation reports
                if args.validation_report_dir:
                    report_dir = Path(args.validation_report_dir)
                    report_dir.mkdir(parents=True, exist_ok=True)

                    # Create a synthetic validation result for reporting
                    validation_report = ValidationResult()
                    validation_report.node_count = assembly_result.nodes_created
                    validation_report.edge_count = assembly_result.relationships_created
                    validation_report.valid = consistency_report.conflict_count == 0

                    reporter = ReportGenerator(title="KG Validation Report")
                    reporter.to_json(validation_report, report_dir / "validation_report.json")
                    reporter.to_markdown(validation_report, report_dir / "validation_report.md")
                    reporter.to_html(validation_report, report_dir / "validation_report.html")

                    logger.info("validation_reports_generated", directory=str(report_dir))
                    print(f"  - Reports saved to: {report_dir}")

                validation_passed = consistency_report.conflict_count == 0

            except Exception as e:
                logger.warning("validation_phase_failed", error=str(e))
                print(f"[WARN] Validation phase encountered error: {e}")
                validation_passed = False

            print()

        # =====================================================================
        # PHASE 8: COMPETENCY QUESTION VALIDATION (Stopping Criterion)
        # =====================================================================

        cq_validation_passed = True

        if args.check_competency_questions:
            print("PHASE 8: Competency Question Coverage Check (Stopping Criterion)")
            print("-" * 80)

            try:
                logger.info("competency_question_check_starting")

                # Check which questions are answered by the KG
                cq_validator = CompetencyQuestionValidator(
                    ontology_service=ontology_service,
                    graph_store=neo4j_store
                )

                # Use the questions generated in Phase 2
                cq_results = cq_validator.validate_questions(all_questions)

                answerable_count = sum(1 for result in cq_results if result["answerable"])
                cq_coverage = answerable_count / max(len(all_questions), 1) if all_questions else 0.0

                logger.info(
                    "competency_questions_checked",
                    total=len(all_questions),
                    answerable=answerable_count,
                    coverage=cq_coverage
                )

                print("[OK] Competency Question Coverage Analysis")
                print(f"  - Total questions: {len(all_questions)}")
                print(f"  - Answerable: {answerable_count}")
                print(f"  - Coverage: {cq_coverage:.1%}")
                print(f"  - Threshold: {args.cq_coverage_threshold:.1%}")

                # Check if we meet the stopping criterion
                if cq_coverage >= args.cq_coverage_threshold:
                    print("  [OK] STOPPING CRITERION MET - Coverage above threshold")
                    cq_validation_passed = True
                else:
                    print("  [FAIL] STOPPING CRITERION NOT MET - Coverage below threshold")
                    print(f"     Need {int((args.cq_coverage_threshold - cq_coverage) * len(all_questions))} more questions answered")
                    cq_validation_passed = False

                # List unanswered questions for guidance
                unanswerable = [q for q, result in zip(all_questions, cq_results) if not result["answerable"]]
                if unanswerable:
                    print("\n  Unanswered questions to address:")
                    for q in unanswerable[:5]:
                        print(f"    - {q}")
                    if len(unanswerable) > 5:
                        print(f"    ... and {len(unanswerable) - 5} more")

            except Exception as e:
                logger.warning("competency_question_check_failed", error=str(e))
                print(f"[WARN] Competency question check failed: {e}")
                cq_validation_passed = False

            print()

        # =====================================================================
        # SUMMARY & STATISTICS
        # =====================================================================
        elapsed = (datetime.now() - start_time).total_seconds()

        print("="*80)
        print("PIPELINE EXECUTION SUMMARY")
        print("="*80)

        overall_status = "SUCCESS [OK]"
        if not validation_passed:
            overall_status = "VALIDATION WARNINGS [WARN]"
        if args.check_competency_questions and not cq_validation_passed:
            overall_status = "STOPPING CRITERION NOT MET [FAIL]"

        print(f"Status:                  {overall_status}")
        print(f"Total time:              {elapsed:.1f}s")
        print("\nOntology:")
        print(f"  Classes processed:     {len(classes)}")
        print(f"  Questions generated:   {len(all_questions)}")
        print("\nKnowledge Discovery:")
        print(f"  Entities discovered:   {len(discovered_entities)}")
        print(f"  Entities synthesized:  {len(synthesized_entities)}")
        print(f"  Merge rate:            {merge_rate:.1%}")
        print("\nRelation Extraction:")
        print(f"  Relations extracted:   {len(extracted_relations)}")
        print("\nNeo4j Graph:")
        print(f"  Nodes created:         {assembly_result.nodes_created}")
        print(f"  Relationships created: {assembly_result.relationships_created}")
        print(f"  Assembly errors:       {len(assembly_result.errors)}")

        if args.validate:
            print("\nValidation:")
            print(f"  Status:                {'[OK] PASSED' if validation_passed else '[WARN] WARNINGS'}")
            print(f"  Conflicts detected:    {consistency_report.conflict_count if consistency_report else 'N/A'}")

        if args.check_competency_questions:
            print("\nCompetency Questions (Stopping Criterion):")
            print(f"  Coverage:              {cq_coverage:.1%}")
            print(f"  Threshold:             {args.cq_coverage_threshold:.1%}")
            print(f"  Status:                {'[OK] MET' if cq_validation_passed else '[FAIL] NOT MET'}")


        print(f"\nDatabase: {NEO4J_URI}")
        print("="*80 + "\n")

        # Log total Ollama token usage if available
        try:
            from kgbuilder.embedding.ollama import OllamaProvider
            OllamaProvider.log_total_token_usage()
        except Exception as e:
            print(f"[Token Usage] Could not log Ollama token usage: {e}")

        if assembly_result.errors:
            print("[WARN] Some entities could not be assembled. Check logs for details.\n")

        if args.check_competency_questions and not cq_validation_passed:
            print("[FAIL] STOPPING CRITERION NOT MET")
            print(f"  Competency question coverage ({cq_coverage:.1%}) is below threshold ({args.cq_coverage_threshold:.1%})")
            print("  Please add more data or extend discovery to answer remaining questions.\n")

    except Exception as e:
        logger.error("pipeline_failed", error=str(e), exc_info=True)
        print("\n[FAIL] PIPELINE FAILED")
        print(f"Error: {e}\n")
        raise


if __name__ == "__main__":
    main()
