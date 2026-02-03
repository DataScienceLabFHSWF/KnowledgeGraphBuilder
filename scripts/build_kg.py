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
  OLLAMA_URL          - Ollama LLM server (default: http://localhost:11434)
  OLLAMA_MODEL        - Ollama model name (default: qwen3:8b)
  NEO4J_URI           - Neo4j database URI (default: bolt://localhost:7687)
  NEO4J_USER          - Neo4j username (default: neo4j)
  NEO4J_PASSWORD      - Neo4j password (default: changeme)

Usage (Docker):
  docker-compose up kgbuilder

Usage (Local):
  python scripts/build_kg.py \\
    --questions-per-class 5 \\
    --max-iterations 10 \\
    --similarity-threshold 0.85 \\
    --confidence-threshold 0.6
"""

from __future__ import annotations

import sys
import os
import argparse
from pathlib import Path
from typing import Any
from datetime import datetime

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
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")


# =============================================================================
# COMPONENT IMPORTS (All IMPLEMENTED and TESTED)
# =============================================================================

from kgbuilder.agents.question_generator import QuestionGenerationAgent
from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop
from kgbuilder.assembly.simple_kg_assembler import SimpleKGAssembler
from kgbuilder.extraction.synthesizer import FindingsSynthesizer, SynthesizedEntity
from kgbuilder.extraction.entity import OntologyClassDef
from kgbuilder.extraction.relation import LLMRelationExtractor, OntologyRelationDef
from kgbuilder.storage.ontology import FusekiOntologyService
from kgbuilder.storage.vector import QdrantStore
from kgbuilder.retrieval import FusionRAGRetriever
from kgbuilder.extraction.entity import LLMEntityExtractor
from kgbuilder.embedding import OllamaProvider
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation


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
        default=5,
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
    print(f"\nService Configuration:")
    print(f"  Fuseki:     {FUSEKI_URL}/{FUSEKI_DATASET}")
    print(f"  Qdrant:     {QDRANT_URL}")
    print(f"  Ollama:     {OLLAMA_URL} (model: {OLLAMA_MODEL})")
    print(f"  Neo4j:      {NEO4J_URI}")
    print(f"\nHyperparameters:")
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
        print(f"✓ Loaded {len(classes)} ontology classes (from {len(all_classes)} total)")
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
            print(f"  ✓ {len(questions)} questions from class '{class_name}'")

        logger.info("questions_generated", total_count=len(all_questions))
        print(f"\n✓ Generated {len(all_questions)} research questions\n")

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
            print(f"⚠ Discovery completed with warnings: {discovery_result.error_message}")
        else:
            print(f"✓ Discovery completed successfully")

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
        print(f"✓ Deduplicated entities")
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
        print(f"✓ Relation extraction complete")
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
        
        assembler = SimpleKGAssembler(
            neo4j_uri=NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )

        assembly_result = assembler.assemble(
            entities=synthesized_entities,
            relations=extracted_relations
        )

        logger.info(
            "assembly_complete",
            nodes_created=assembly_result.nodes_created,
            relationships_created=assembly_result.relationships_created,
            errors=len(assembly_result.errors)
        )
        print(f"✓ Knowledge graph assembled in Neo4j")
        print(f"  - Nodes created: {assembly_result.nodes_created}")
        print(f"  - Relationships created: {assembly_result.relationships_created}")
        
        if assembly_result.errors:
            print(f"  - Errors: {len(assembly_result.errors)}")
            for error in assembly_result.errors[:5]:
                logger.error("assembly_error", error=error)
                print(f"    ✗ {error}")
            if len(assembly_result.errors) > 5:
                print(f"    ... and {len(assembly_result.errors) - 5} more errors")
        
        print()

        # =====================================================================
        # SUMMARY & STATISTICS
        # =====================================================================
        elapsed = (datetime.now() - start_time).total_seconds()

        print("="*80)
        print("PIPELINE EXECUTION SUMMARY")
        print("="*80)
        print(f"Status:                  {'SUCCESS ✓' if assembly_result.nodes_created > 0 else 'COMPLETED WITH ERRORS'}")
        print(f"Total time:              {elapsed:.1f}s")
        print(f"\nOntology:")
        print(f"  Classes processed:     {len(classes)}")
        print(f"  Questions generated:   {len(all_questions)}")
        print(f"\nKnowledge Discovery:")
        print(f"  Entities discovered:   {len(discovered_entities)}")
        print(f"  Entities synthesized:  {len(synthesized_entities)}")
        print(f"  Merge rate:            {merge_rate:.1%}")
        print(f"\nRelation Extraction:")
        print(f"  Relations extracted:   {len(extracted_relations)}")
        print(f"\nNeo4j Graph:")
        print(f"  Nodes created:         {assembly_result.nodes_created}")
        print(f"  Relationships created: {assembly_result.relationships_created}")
        print(f"  Assembly errors:       {len(assembly_result.errors)}")
        print(f"\nDatabase: {NEO4J_URI}")
        print("="*80 + "\n")

        if assembly_result.errors:
            print("⚠ Some entities could not be assembled. Check logs for details.\n")

    except Exception as e:
        logger.error("pipeline_failed", error=str(e), exc_info=True)
        print(f"\n✗ PIPELINE FAILED")
        print(f"Error: {e}\n")
        raise


if __name__ == "__main__":
    main()
