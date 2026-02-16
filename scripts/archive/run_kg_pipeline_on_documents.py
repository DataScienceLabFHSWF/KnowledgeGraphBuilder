#!/usr/bin/env python3
"""End-to-end KG construction pipeline on all indexed documents.

Runs the complete Phase 4 pipeline using REAL components:
- Phase 4a: QuestionGenerationAgent (REAL Fuseki ontology)
- Phase 4b: IterativeDiscoveryLoop (REAL FusionRAGRetriever + LLMEntityExtractor)
- Phase 4c: FindingsSynthesizer (Entity deduplication)
- Phase 4d: SimpleKGAssembler (Neo4j graph assembly)

This script processes all 3004 indexed documents from Qdrant.

Hyperparameters (for ablation studies):
    --questions-per-class: Number of questions generated per ontology class
    --max-iterations: Maximum iterations for discovery loop
    --similarity-threshold: Entity deduplication similarity threshold
    --confidence-threshold: Minimum confidence for extracted entities

Usage:
    python scripts/run_kg_pipeline_on_documents.py \\
        --questions-per-class 5 \\
        --max-iterations 10 \\
        --similarity-threshold 0.85 \\
        --confidence-threshold 0.6
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# REAL COMPONENT IMPORTS
# =============================================================================

from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop
from kgbuilder.agents.question_generator import QuestionGenerationAgent
from kgbuilder.assembly.simple_kg_assembler import SimpleKGAssembler
from kgbuilder.embedding import OllamaProvider
from kgbuilder.extraction.entity import LLMEntityExtractor, OntologyClassDef
from kgbuilder.extraction.synthesizer import FindingsSynthesizer
from kgbuilder.retrieval import FusionRAGRetriever
from kgbuilder.storage.ontology import FusekiOntologyService
from kgbuilder.storage.vector import QdrantStore

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
# CLI ARGUMENT PARSING (Hyperparameters for ablation studies)
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments for pipeline hyperparameters.
    
    Enables experiment control for ablation studies and comparisons.
    All defaults align with standard configuration for baseline experiments.
    """
    parser = argparse.ArgumentParser(
        description="End-to-end KG construction pipeline with hyperparameter tuning",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Hyperparameters for ablation studies
    parser.add_argument(
        "--questions-per-class",
        type=int,
        default=3,
        help="Number of questions to generate per ontology class"
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum iterations for the discovery loop"
    )

    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.85,
        help="Entity deduplication similarity threshold (0.0-1.0)"
    )

    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.6,
        help="Minimum confidence for extracted entities (0.0-1.0)"
    )

    parser.add_argument(
        "--classes-limit",
        type=int,
        default=3,
        help="Limit ontology classes to process (for testing)"
    )

    parser.add_argument(
        "--dense-weight",
        type=float,
        default=0.7,
        help="Weight for dense retrieval in FusionRAG (0.0-1.0)"
    )

    parser.add_argument(
        "--sparse-weight",
        type=float,
        default=0.3,
        help="Weight for sparse retrieval in FusionRAG (0.0-1.0)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser.parse_args()


# =============================================================================
# COMPONENT FACTORY FUNCTIONS
# =============================================================================

def build_retriever(
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3
) -> FusionRAGRetriever:
    """Build FusionRAG retriever with Qdrant backend.
    
    Args:
        dense_weight: Weight for dense vector similarity (0.0-1.0)
        sparse_weight: Weight for sparse keyword matching (0.0-1.0)
        
    Returns:
        Configured FusionRAGRetriever instance
    """
    logger.info(
        "building_retriever",
        type="FusionRAGRetriever",
        dense_weight=dense_weight,
        sparse_weight=sparse_weight
    )

    # Initialize Qdrant store
    qdrant_store = QdrantStore(
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION
    )

    # Initialize LLM for semantic understanding
    llm = OllamaProvider(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_URL
    )

    # Create retriever with configured fusion weights
    retriever = FusionRAGRetriever(
        qdrant_store=qdrant_store,
        llm_provider=llm,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
        top_k=10
    )

    logger.info("retriever_built", type="FusionRAGRetriever")
    return retriever


def build_entity_extractor(confidence_threshold: float = 0.6) -> LLMEntityExtractor:
    """Build LLM-based entity extractor with ontology guidance.
    
    Args:
        confidence_threshold: Minimum confidence for extracted entities (0.0-1.0)
        
    Returns:
        Configured LLMEntityExtractor instance
    """
    logger.info(
        "building_extractor",
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
    """Convert class name strings to OntologyClassDef objects.
    
    Args:
        class_names: List of class label strings from ontology
        
    Returns:
        List of OntologyClassDef objects for extraction guidance
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

# =============================================================================
# MAIN PIPELINE
# =============================================================================

def main() -> None:
    """Run the complete end-to-end KG construction pipeline."""

    # Parse CLI arguments for hyperparameter control
    args = parse_arguments()

    print("\n" + "="*80)
    print("KNOWLEDGE GRAPH CONSTRUCTION PIPELINE")
    print("="*80)
    print(f"Fuseki URL: {FUSEKI_URL}/{FUSEKI_DATASET}")
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"Neo4j URI: {NEO4J_URI}")
    print(f"Ollama URL: {OLLAMA_URL} (model: {OLLAMA_MODEL})")
    print("\nHyperparameters:")
    print(f"  Questions per class:     {args.questions_per_class}")
    print(f"  Max iterations:          {args.max_iterations}")
    print(f"  Similarity threshold:    {args.similarity_threshold}")
    print(f"  Confidence threshold:    {args.confidence_threshold}")
    print(f"  Dense weight:            {args.dense_weight}")
    print(f"  Sparse weight:           {args.sparse_weight}")
    print("="*80 + "\n")

    try:
        # =====================================================================
        # PHASE 4A: QUESTION GENERATION (Real Fuseki ontology)
        # =====================================================================
        print("PHASE 4A: Question Generation (Real Fuseki Ontology)")
        print("-" * 80)

        ontology_service = FusekiOntologyService(FUSEKI_URL, FUSEKI_DATASET)
        classes = ontology_service.get_all_classes()

        if not classes:
            logger.error("no_classes_found_in_ontology")
            raise RuntimeError("No classes found in Fuseki ontology")

        logger.info("ontology_classes", count=len(classes))

        # Create question generation agent with ontology service
        question_agent = QuestionGenerationAgent(
            ontology_service=ontology_service
        )

        # Generate questions from real ontology
        all_questions = []
        classes_to_process = classes[:args.classes_limit]
        for class_name in classes_to_process:
            logger.info("generating_questions_for_class", class_label=class_name)
            questions = question_agent.generate_questions(
                max_questions=args.questions_per_class
            )
            all_questions.extend(questions)
            print(f"  ✓ Generated {len(questions)} questions for {class_name}")

        print(f"\n✓ Phase 4A: Generated {len(all_questions)} research questions from ontology\n")

        # =====================================================================
        # PHASE 4B: ITERATIVE DISCOVERY (Real Retriever + Extractor)
        # =====================================================================
        print("PHASE 4B: Iterative Discovery (Real Retriever + Extractor)")
        print("-" * 80)

        # Convert class names to OntologyClassDef objects for extraction guidance
        ontology_class_defs = convert_class_names_to_definitions(classes)
        retriever = build_retriever(
            dense_weight=args.dense_weight,
            sparse_weight=args.sparse_weight
        )
        extractor = build_entity_extractor(
            confidence_threshold=args.confidence_threshold
        )

        # Create discovery loop with ontology classes for extraction guidance
        discovery_loop = IterativeDiscoveryLoop(
            retriever=retriever,
            extractor=extractor,
            question_generator=question_agent,
            ontology_classes=ontology_class_defs
        )

        # Run discovery on the questions with ontology classes
        discovery_result = discovery_loop.run_discovery(
            initial_questions=all_questions,
            max_iterations=args.max_iterations,
            coverage_target=0.8,
            ontology_classes=ontology_class_defs
        )

        if not discovery_result.success:
            logger.warning("discovery_loop_warning", message=discovery_result.error_message)
        else:
            print(f"✓ Phase 4B: Discovered {len(discovery_result.entities)} entities")
            print(f"  - Iterations: {discovery_result.total_iterations}")
            print(f"  - Coverage: {discovery_result.final_coverage:.2%}")
            print(f"  - Time: {discovery_result.total_time_sec:.1f}s\n")

        discovered_entities = discovery_result.entities

        # =====================================================================
        # PHASE 4C: FINDINGS SYNTHESIS (Deduplication)
        # =====================================================================
        print("PHASE 4C: Findings Synthesis")
        print("-" * 80)

        synthesizer = FindingsSynthesizer(
            similarity_threshold=args.similarity_threshold
        )

        synthesized_entities = synthesizer.synthesize(
            entities=discovered_entities
        )

        # Calculate merge rate
        merge_rate = (len(discovered_entities) - len(synthesized_entities)) / max(len(discovered_entities), 1)
        print(f"✓ Phase 4C: Synthesized {len(discovered_entities)} → {len(synthesized_entities)} entities")
        print(f"  - Merged: {len(discovered_entities) - len(synthesized_entities)} ({merge_rate:.1%})\n")

        # =====================================================================
        # PHASE 4D: KG ASSEMBLY (Neo4j)
        # =====================================================================
        print("PHASE 4D: KG Assembly (Neo4j)")
        print("-" * 80)

        assembler = SimpleKGAssembler(
            neo4j_uri=NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )

        # Assemble into Neo4j
        assembly_result = assembler.assemble(entities=synthesized_entities)

        print("✓ Phase 4D: Created KG in Neo4j")
        print(f"  - Nodes created: {assembly_result.nodes_created}")
        print(f"  - Relationships created: {assembly_result.relationships_created}")
        print(f"  - Errors: {len(assembly_result.errors)}\n")

        if assembly_result.errors:
            for error in assembly_result.errors:
                logger.error("assembly_error", error=error)

        # =====================================================================
        # SUMMARY
        # =====================================================================
        print("="*80)
        print("PIPELINE EXECUTION COMPLETE")
        print("="*80)
        print(f"Ontology Classes:        {len(classes)}")
        print(f"Questions Generated:     {len(all_questions)}")
        print(f"Entities Discovered:     {len(discovered_entities)}")
        print(f"Entities Synthesized:    {len(synthesized_entities)}")
        print(f"Neo4j Nodes Created:     {assembly_result.nodes_created}")
        print(f"Neo4j Relationships:     {assembly_result.relationships_created}")
        print(f"Total Time:              {discovery_result.total_time_sec:.1f}s")
        print("="*80 + "\n")

    except Exception as e:
        logger.error("pipeline_failed", error=str(e), exc_info=True)
        print(f"\n✗ Pipeline failed: {e}\n")
        raise


if __name__ == "__main__":
    main()
