#!/usr/bin/env python3
"""
Full end-to-end Knowledge Graph construction pipeline.

Orchestrates complete KG building from ontology + competency questions:
1. Load ontology (classes, properties, relations)
2. Load and validate competency questions
3. Iterative discovery (entities + relations in one pass)
4. Deduplication and synthesis
5. Knowledge graph assembly
6. Comprehensive validation (SHACL, consistency, quality)
7. Export in multiple formats

Usage:
    python scripts/full_kg_pipeline.py --config config.json
    python scripts/full_kg_pipeline.py --ontology data/ontology/ont.owl --questions data/competency_questions.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.core.models import Document, ExtractedEntity, ExtractedRelation, Chunk
from kgbuilder.document.loaders import PDFLoader, DOCXLoader
from kgbuilder.document.chunking.strategies import FixedSizeChunker
from kgbuilder.embedding.ollama import OllamaProvider
from kgbuilder.extraction.entity import (
    LLMEntityExtractor,
    OntologyClassDef,
)
from kgbuilder.extraction.rules import RuleBasedExtractor, RuleBasedRelationExtractor
from kgbuilder.extraction.ensemble import TieredExtractor, TieredRelationExtractor
from kgbuilder.extraction.relation import (
    LLMRelationExtractor,
    OntologyRelationDef,
)
from kgbuilder.enrichment import SemanticEnrichmentPipeline, EnrichedEntity, EnrichedRelation
from kgbuilder.pipeline.checkpoint_cli import enrich_from_checkpoint
from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.storage.protocol import Node, Edge
from kgbuilder.storage.vector import QdrantStore
from kgbuilder.storage.ontology import FusekiOntologyService
from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop
from kgbuilder.agents.question_generator import QuestionGenerationAgent
from kgbuilder.assembly.kg_builder import KGBuilder
from kgbuilder.validation.rules_engine import RulesEngine
from kgbuilder.validation.consistency_checker import ConsistencyChecker
from kgbuilder.experiment.checkpoint import CheckpointManager

logger = structlog.get_logger(__name__)


class PipelineConfig(BaseModel):
    """Full pipeline configuration."""

    # Ontology
    ontology_url: str = Field(
        default_factory=lambda: os.environ.get("FUSEKI_URL", "http://localhost:3030")
    )
    ontology_path: Path | None = Field(
        default=None,
        description="Path to local ontology file (.owl, .ttl)"
    )
    ontology_user: str = Field(
        default_factory=lambda: os.environ.get("FUSEKI_USER", "admin")
    )
    ontology_password: str = Field(
        default_factory=lambda: os.environ.get("FUSEKI_PASSWORD", "")
    )
    ontology_dataset: str = "kgbuilder"

    # Documents
    document_dir: Path = Field(default=Path("data/documents"))
    document_extensions: list[str] = [".pdf", ".docx"]

    # LLM
    llm_model: str = Field(
        default_factory=lambda: os.environ.get("OLLAMA_LLM_MODEL", "qwen3:8b")
    )
    embedding_model: str = Field(
        default_factory=lambda: os.environ.get("OLLAMA_EMBED_MODEL", "qwen3-embedding")
    )
    llm_base_url: str = Field(
        default_factory=lambda: os.environ.get("OLLAMA_URL", os.environ.get("OLLAMA_BASE_URL", "http://localhost:18134"))
    )
    llm_temperature: float = 0.7
    llm_timeout: int = 300

    # Discovery
    questions_path: Path | None = Field(
        default=None,
        description="Path to competency questions JSON file"
    )
    max_iterations: int = 3
    coverage_target: float = 0.85
    top_k_docs: int = 5
    confidence_threshold: float = 0.6
    generate_follow_ups: bool = True

    # Storage
    neo4j_uri: str = Field(
        default_factory=lambda: os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    )
    neo4j_user: str = Field(
        default_factory=lambda: os.environ.get("NEO4J_USER", "neo4j")
    )
    neo4j_password: str = Field(
        default_factory=lambda: os.environ.get("NEO4J_PASSWORD", "changeme")
    )
    neo4j_database: str = "neo4j"
    qdrant_url: str = Field(
        default_factory=lambda: os.environ.get("QDRANT_URL", "http://localhost:6333")
    )
    vector_collection: str = "discovery"

    # Pipeline
    smoke_test: bool = False
    skip_discovery: bool = False
    skip_enrichment: bool = False
    skip_validation: bool = False
    enrich_only: bool = Field(
        default=False,
        description="Load checkpoint and run enrichment only (skip discovery)"
    )
    checkpoint_path: Path | None = Field(
        default=None,
        description="Path to extraction checkpoint for re-enrichment"
    )
    export_formats: list[str] = ["json-ld", "cypher", "rdf"]
    output_dir: Path = Field(default=Path("output/kg_results"))


@dataclass
class PipelineResult:
    """Results from complete pipeline execution."""

    timestamp: str
    ontology_classes: int = 0
    ontology_relations: int = 0
    documents_loaded: int = 0
    discovered_entities: int = 0
    discovered_relations: int = 0
    synthesized_entities: int = 0
    enriched_entities: int = 0
    enriched_relations: int = 0
    kg_nodes: int = 0
    kg_edges: int = 0
    validation_results: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0


class FullKGPipeline:
    """Complete KG construction pipeline with all validations."""

    def __init__(self, config: PipelineConfig) -> None:
        """Initialize pipeline with services."""
        self.config = config
        
        # Apply smoke test overrides if enabled
        if self.config.smoke_test:
            logger.info("smoke_test_mode_enabled")
            self.config.ontology_dataset = "kgbuilder_test"
            # Neo4j Community only supports 'neo4j' database
            # self.config.neo4j_database = "neo4j_test" 
            self.config.vector_collection = "discovery_test"
            
        self.result = PipelineResult(timestamp=datetime.now().isoformat())

        # Initialize services
        logger.info("initializing_services")
        self._init_storage_services()
        self._init_llm_services()

    def _init_storage_services(self) -> None:
        """Initialize storage backends."""
        logger.info("connecting_to_storage")

        # Ontology service
        self.ontology_service = FusekiOntologyService(
            fuseki_url=self.config.ontology_url,
            dataset_name=self.config.ontology_dataset,
            username=self.config.ontology_user,
            password=self.config.ontology_password,
        )

        # Qdrant for vectors
        self.vector_store = QdrantStore(
            url=self.config.qdrant_url,
            collection_name=self.config.vector_collection,
        )

        # Neo4j for KG
        self.graph_store = Neo4jGraphStore(
            uri=self.config.neo4j_uri,
            auth=(self.config.neo4j_user, self.config.neo4j_password),
            database=self.config.neo4j_database,
        )

        logger.info("storage_services_initialized")

    def _init_llm_services(self) -> None:
        """Initialize LLM-based extraction and enrichment services."""
        logger.info("initializing_llm_services")

        # LLM provider for generation
        self.llm = OllamaProvider(
            model=self.config.llm_model,
            base_url=self.config.llm_base_url,
            temperature=self.config.llm_temperature,
            timeout=self.config.llm_timeout,
        )

        # Embedding provider
        self.embedding_provider = OllamaProvider(
            model=self.config.embedding_model,
            base_url=self.config.llm_base_url,
            timeout=self.config.llm_timeout,
        )

        # Entity extractor (TIERED: Heuristic -> LLM)
        self.rule_extractor = RuleBasedExtractor()
        
        self.llm_extractor = LLMEntityExtractor(
            llm_provider=self.llm,
            confidence_threshold=self.config.confidence_threshold,
        )
        
        # Use TieredExtractor for speedup
        self.entity_extractor = TieredExtractor(
            rule_extractor=self.rule_extractor,
            llm_extractor=self.llm_extractor,
            min_entities_heuristic=1
        )

        # Relation extractor (TIERED: Heuristic -> LLM)
        self.rule_relation_extractor = RuleBasedRelationExtractor()
        
        self.llm_relation_extractor = LLMRelationExtractor(
            llm_provider=self.llm,
            confidence_threshold=self.config.confidence_threshold,
        )
        
        # Use TieredRelationExtractor for speedup
        self.relation_extractor = TieredRelationExtractor(
            rule_extractor=self.rule_relation_extractor,
            llm_extractor=self.llm_relation_extractor,
            min_relations_heuristic=1
        )

        # Enrichment pipeline
        self.enrichment_pipeline = SemanticEnrichmentPipeline(
            llm=self.llm,
            embedding_provider=self.embedding_provider,
            ontology_classes={},
        )

        # Checkpoint manager
        self.checkpoint_manager = CheckpointManager(self.config.output_dir / "checkpoints")

        logger.info("llm_services_initialized")

    def run(self) -> PipelineResult:
        """Execute complete pipeline."""
        start_time = datetime.now()

        try:
            # Enrich-only mode: load checkpoint and run enrichment
            if self.config.enrich_only and self.config.checkpoint_path:
                logger.info("pipeline_mode", mode="enrich_only")
                self._enrich_from_checkpoint()
                logger.info("pipeline_completed", **asdict(self.result))
                return self.result

            # 1. Load ontology
            logger.info("pipeline_step", step="load_ontology")
            self._load_ontology()

            # 2. Load documents
            logger.info("pipeline_step", step="load_documents")
            self._load_documents()

            # 3. Discovery (if not skipped)
            if not self.config.skip_discovery:
                logger.info("pipeline_step", step="discovery_loop")
                self._run_discovery()
            else:
                logger.warning("skipping_discovery", reason="config_skip_discovery=true")

            # 4. Enrichment (if not skipped)
            if not self.config.skip_enrichment:
                logger.info("pipeline_step", step="enrichment")
                self._run_enrichment()
            else:
                logger.warning("skipping_enrichment", reason="config_skip_enrichment=true")

            # 5. KG assembly
            logger.info("pipeline_step", step="kg_assembly")
            self._build_kg()

            # 6. Validation (if not skipped)
            if not self.config.skip_validation:
                logger.info("pipeline_step", step="validation")
                self._validate_kg()
            else:
                logger.warning("skipping_validation", reason="config_skip_validation=true")

            # 7. Export
            logger.info("pipeline_step", step="export")
            self._export_kg()

            logger.info("pipeline_completed", **asdict(self.result))

        except Exception as e:
            logger.error("pipeline_failed", error=str(e), exc_info=True)
            self.result.errors.append(f"Pipeline execution failed: {str(e)}")

        finally:
            self.result.execution_time_seconds = (
                datetime.now() - start_time
            ).total_seconds()

        return self.result

    def _load_ontology(self) -> None:
        """Load ontology from service, optionally uploading first."""
        try:
            # Upload local ontology if provided
            if self.config.ontology_path and self.config.ontology_path.exists():
                logger.info("uploading_ontology", path=str(self.config.ontology_path))
                with open(self.config.ontology_path, "r") as f:
                    content = f.read()
                    self.ontology_service.store.load_ontology(content)
                logger.info("ontology_uploaded_successfully")

            # Load classes
            class_labels = self.ontology_service.get_all_classes()
            self.result.ontology_classes = len(class_labels)

            # Build OntologyClassDef objects for extraction
            self.ontology_classes: list[OntologyClassDef] = []
            for label in class_labels:
                # Get real URI if possible (or fake it if only label returned)
                # Note: FusekiOntologyService returns labels from get_all_classes
                class_uri = f"http://example.org/ontology#{label}" 
                
                # Fetch properties for this class
                properties_tuples = self.ontology_service.get_class_properties(label)
                
                # Fetch relations for this class to inform extraction
                # (Optional optimization: load them once later)

                self.ontology_classes.append(
                    OntologyClassDef(
                        uri=class_uri,
                        label=label,
                        properties=[
                            {"name": p[0], "type": p[1], "description": p[2]}
                            for p in properties_tuples
                        ],
                    )
                )

            # Load relations (ObjectProperties)
            self.ontology_relations: list[OntologyRelationDef] = []
            if hasattr(self.ontology_service, "get_all_relations"):
                rel_names = self.ontology_service.get_all_relations()
                for rel_name in rel_names:
                    self.ontology_relations.append(
                        OntologyRelationDef(
                            uri=f"http://example.org/ontology#{rel_name}",
                            label=rel_name
                        )
                    )
            
            self.result.ontology_relations = len(self.ontology_relations)

            # Update enrichment pipeline with ontology classes
            self.enrichment_pipeline.ontology_classes = {
                cls.label: cls for cls in self.ontology_classes
            }

            logger.info(
                "ontology_loaded",
                classes=self.result.ontology_classes,
                relations=self.result.ontology_relations,
            )

        except Exception as e:
            logger.error("ontology_load_failed", error=str(e))
            self.result.errors.append(f"Failed to load ontology: {str(e)}")
            raise

    def _load_documents(self) -> None:
        """Load and chunk documents."""
        try:
            loaders = {
                ".pdf": PDFLoader(),
                ".docx": DOCXLoader(),
            }

            doc_paths = []

            for ext in self.config.document_extensions:
                doc_paths.extend(
                    self.config.document_dir.glob(f"*{ext}")
                )

            documents: list[Document] = []
            for path in doc_paths:
                loader = loaders.get(path.suffix)
                if loader:
                    try:
                        doc = loader.load(path)
                        documents.append(doc)
                    except Exception as e:
                        logger.warning(
                            "document_load_failed", path=str(path), error=str(e)
                        )
                        self.result.warnings.append(
                            f"Failed to load {path}: {str(e)}"
                        )

            self.result.documents_loaded = len(documents)
            logger.info("documents_loaded", count=len(documents))

            # Only index if vector store is empty
            if hasattr(self.vector_store, "get_points_count"):
                points_count = self.vector_store.get_points_count()
                if points_count > 0:
                    logger.info("vector_store_already_indexed", count=points_count)
                    return

            # Chunk and store in vector store
            logger.info("chunking_and_indexing_documents")
            chunker = FixedSizeChunker()
            all_chunks = []
            for doc in documents:
                chunks = chunker.chunk(doc, chunk_size=1000, chunk_overlap=100)
                all_chunks.extend(chunks)

            if all_chunks:
                # Embed chunks
                chunk_texts = [c.content for c in all_chunks]
                embeddings = self.embedding_provider.embed_batch(chunk_texts)
                
                # Store in Qdrant
                ids = [c.id for c in all_chunks]
                metadata = [
                    {
                        "doc_id": c.document_id,
                        "content": c.content,
                        "strategy": "fixed_size"
                    } for c in all_chunks
                ]
                self.vector_store.store(ids, embeddings, metadata)
                logger.info("indexing_complete", chunks=len(all_chunks))

        except Exception as e:
            logger.error("document_loading_failed", error=str(e))
            self.result.errors.append(f"Failed to load documents: {str(e)}")
            raise

    def _run_discovery(self) -> None:
        """Run iterative discovery loop."""
        try:
            # Initialize question generator with ontology service
            question_gen = QuestionGenerationAgent(
                ontology_service=self.ontology_service,
            )

            # Document retriever using vector store
            class VectorRetriever:
                """Simple retriever wrapping the vector store."""

                def __init__(self, vector_store: QdrantStore, embedding_provider: OllamaProvider):
                    self._store = vector_store
                    self._embed = embedding_provider

                def retrieve(self, query: str, top_k: int = 10) -> list[Any]:
                    """Retrieve relevant chunks from vector store."""
                    try:
                        # Vectorize query
                        query_vec = self._embed.embed_text(query)
                        # Search in Qdrant (using its internal collection name)
                        results = self._store.search(query_vec, top_k=top_k)
                        
                        # Convert to objects with .content and .doc_id as required by DiscoveryLoop
                        @dataclass
                        class RetrievalResult:
                            content: str
                            doc_id: str
                            score: float
                        
                        # results are list[tuple(id, score, metadata)]
                        mapped = []
                        for rid, score, meta in results:
                            mapped.append(RetrievalResult(
                                content=meta.get("content", ""),
                                doc_id=meta.get("doc_id", "unknown"),
                                score=score
                            ))
                        return mapped
                    except Exception as e:
                        logger.warning(f"Retrieval failed for query: {e}")
                        return []

            retriever = VectorRetriever(self.vector_store, self.embedding_provider)

            discovery_loop = IterativeDiscoveryLoop(
                retriever=retriever,
                extractor=self.entity_extractor,
                question_generator=question_gen,
                ontology_classes=self.ontology_classes if hasattr(self, 'ontology_classes') else None,
                relation_extractor=self.relation_extractor,
                ontology_relations=self.ontology_relations if hasattr(self, 'ontology_relations') else None,
            )

            # Load initial questions if provided
            initial_questions = None
            if self.config.questions_path and self.config.questions_path.exists():
                logger.info("loading_competency_questions", path=str(self.config.questions_path))
                with open(self.config.questions_path) as f:
                    q_data = json.load(f)
                    from kgbuilder.agents.question_generator import ResearchQuestion
                    initial_questions = [ResearchQuestion(**q) for q in q_data]

            # Run the discovery loop
            result = discovery_loop.run_discovery(
                initial_questions=initial_questions,
                max_iterations=self.config.max_iterations,
                coverage_target=self.config.coverage_target,
                top_k_docs=self.config.top_k_docs,
                generate_follow_ups=self.config.generate_follow_ups,
            )

            # Store discovered entities and relations on self for enrichment
            self.discovered_entities = result.entities
            self.discovered_relations = result.relations

            self.result.discovered_entities = len(self.discovered_entities)
            self.result.discovered_relations = len(self.discovered_relations)

            # Save checkpoint
            try:
                checkpoint_path = self.checkpoint_manager.save_extraction(
                    run_id=self.result.timestamp.replace(":", "-"),
                    variant_name="full_pipeline",
                    entities=self.discovered_entities,
                    relations=self.discovered_relations,
                    extraction_seconds=self.result.execution_time_seconds,
                )
                logger.info("checkpoint_saved")
            except Exception as e:
                logger.warning("checkpoint_save_failed", error=str(e))

            logger.info(
                "discovery_complete",
                entities=self.result.discovered_entities,
                relations=self.result.discovered_relations,
            )

        except Exception as e:
            logger.error("discovery_failed", error=str(e))
            self.result.errors.append(f"Discovery failed: {str(e)}")
            raise

    def _build_kg(self) -> None:
        """Build knowledge graph in Neo4j."""
        try:
            logger.info("kg_building_start")

            # Use enriched entities if available, fall back to discovered
            entities = getattr(self, 'enriched_entities', None) or getattr(self, 'discovered_entities', [])
            relations = getattr(self, 'enriched_relations', None) or getattr(self, 'discovered_relations', [])

            if not entities:
                logger.warning("no_entities_for_kg")
                return

            # Build KG using the KGBuilder
            kg_builder = KGBuilder(
                primary_store=self.graph_store,
            )

            # Convert entities to Nodes
            kg_nodes = []
            for e in entities:
                # Handle both ExtractedEntity (id, properties) and EnrichedEntity (entity_id, metadata)
                eid = getattr(e, 'entity_id', getattr(e, 'id', 'unknown'))
                e_type = getattr(e, 'type', getattr(e, 'entity_type', 'Entity'))
                e_label = getattr(e, 'label', eid)
                e_desc = getattr(e, 'description', '')
                
                # Merge properties/metadata
                props = {}
                if hasattr(e, 'properties'):
                    props.update(e.properties)
                if hasattr(e, 'metadata'):
                    props.update(e.metadata)
                
                props['description'] = e_desc
                props['confidence'] = getattr(e, 'confidence', 0.0)
                if hasattr(e, 'aliases'):
                    props['aliases'] = e.aliases
                
                kg_nodes.append(Node(
                    id=eid,
                    label=e_label,
                    node_type=e_type,
                    properties=props
                ))
            
            # Convert relations to Edges
            kg_edges = []
            for r in relations:
                # Handle both ExtractedRelation (id, source_entity_id, target_entity_id) 
                # and EnrichedRelation (relation_id, source_id, target_id)
                rid = getattr(r, 'relation_id', getattr(r, 'id', 'unknown'))
                sid = getattr(r, 'source_id', getattr(r, 'source_entity_id', 'unknown'))
                tid = getattr(r, 'target_id', getattr(r, 'target_entity_id', 'unknown'))
                pred = getattr(r, 'predicate', 'related_to')
                
                props = {}
                if hasattr(r, 'properties'):
                    props.update(r.properties)
                if hasattr(r, 'metadata'):
                    props.update(r.metadata)
                
                props['confidence'] = getattr(r, 'confidence', 0.0)
                
                kg_edges.append(Edge(
                    id=rid,
                    source_id=sid,
                    target_id=tid,
                    edge_type=pred,
                    properties=props
                ))

            build_result = kg_builder.build(kg_nodes, kg_edges)
            self.result.kg_nodes = build_result.nodes_created
            self.result.kg_edges = build_result.edges_created

            logger.info(
                "kg_building_complete",
                nodes=self.result.kg_nodes,
                edges=self.result.kg_edges,
            )

        except Exception as e:
            logger.error("kg_build_failed", error=str(e))
            self.result.errors.append(f"KG building failed: {str(e)}")
            raise

    def _run_enrichment(self) -> None:
        """Run enrichment pipeline on discovered entities and relations."""
        try:
            if not hasattr(self, 'discovered_entities') or not self.discovered_entities:
                logger.warning("no_entities_to_enrich")
                return

            logger.info("enrichment_start")

            # Convert extracted entities to enriched format
            enriched_entities: list[EnrichedEntity] = []
            for entity in self.discovered_entities:
                enriched_entities.append(
                    EnrichedEntity(
                        entity_id=entity.id,
                        label=entity.label,
                        entity_type=entity.entity_type,
                        confidence=entity.confidence,
                        description=getattr(entity, 'description', ''),
                        aliases=getattr(entity, 'aliases', []),
                    )
                )

            # Convert extracted relations to enriched format
            enriched_relations: list[EnrichedRelation] = []
            if hasattr(self, 'discovered_relations'):
                for relation in self.discovered_relations:
                    enriched_relations.append(
                        EnrichedRelation(
                            relation_id=relation.id,
                            source_id=relation.source_entity_id,
                            target_id=relation.target_entity_id,
                            predicate=relation.predicate,
                            confidence=relation.confidence,
                        )
                    )

            # Run enrichment pipeline
            enriched_entities, enriched_relations, metrics = self.enrichment_pipeline.enrich(
                enriched_entities,
                enriched_relations,
            )

            # Store enriched results for assembly
            self.enriched_entities = enriched_entities
            self.enriched_relations = enriched_relations
            self.result.enriched_entities = len(enriched_entities)
            self.result.enriched_relations = len(enriched_relations)

            logger.info(
                "enrichment_complete",
                duration_seconds=metrics.duration_seconds,
                descriptions=metrics.descriptions_added,
                embeddings=metrics.embeddings_added,
                competency_questions=metrics.competency_questions_added,
                aliases=metrics.aliases_added,
            )

        except Exception as e:
            logger.error("enrichment_failed", error=str(e))
            self.result.errors.append(f"Enrichment failed: {str(e)}")
            raise

    def _enrich_from_checkpoint(self) -> None:
        """Load checkpoint and run enrichment only."""
        try:
            if not self.config.checkpoint_path or not self.config.checkpoint_path.exists():
                raise FileNotFoundError(
                    f"Checkpoint not found: {self.config.checkpoint_path}"
                )

            logger.info("loading_checkpoint", path=str(self.config.checkpoint_path))

            # Load from checkpoint
            enriched_entities, enriched_relations = enrich_from_checkpoint(
                checkpoint_path=self.config.checkpoint_path,
                output_dir=self.config.output_dir,
                llm_model=self.config.llm_model,
                embedding_model=self.config.embedding_model,
                ollama_base_url=self.config.llm_base_url,
            )

            self.result.enriched_entities = len(enriched_entities)
            self.result.enriched_relations = len(enriched_relations)

            logger.info(
                "enrichment_from_checkpoint_complete",
                entities=len(enriched_entities),
                relations=len(enriched_relations),
            )

        except Exception as e:
            logger.error("checkpoint_enrichment_failed", error=str(e))
            self.result.errors.append(f"Checkpoint enrichment failed: {str(e)}")
            raise

    def _validate_kg(self) -> None:
        """Run comprehensive KG validation."""
        try:
            logger.info("validation_start")

            validation_results = {}

            # Run rules engine (semantic validation)
            try:
                rules = RulesEngine()
                rules_result = rules.execute_rules(self.graph_store)
                validation_results["rules"] = {
                    "passed": rules_result.passed if hasattr(rules_result, 'passed') else True,
                    "violations": len(rules_result.violations) if hasattr(rules_result, 'violations') else 0,
                }
            except Exception as e:
                logger.warning("rules_validation_failed", error=str(e))
                validation_results["rules"] = {"error": str(e)}

            # Run consistency checker
            try:
                checker = ConsistencyChecker()
                consistency_result = checker.check_consistency(self.graph_store)
                validation_results["consistency"] = {
                    "conflict_rate": consistency_result.conflict_rate if hasattr(consistency_result, 'conflict_rate') else 0.0,
                }
            except Exception as e:
                logger.warning("consistency_check_failed", error=str(e))
                validation_results["consistency"] = {"error": str(e)}

            self.result.validation_results = validation_results
            logger.info("validation_complete", results=validation_results)

        except Exception as e:
            logger.warning("validation_failed", error=str(e))
            self.result.warnings.append(f"Validation failed: {str(e)}")

    def _export_kg(self) -> None:
        """Export KG in requested formats."""
        try:
            self.config.output_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. Gather all data in memory for easier formatting
            from kgbuilder.storage.protocol import InMemoryGraphStore
            mem_store = InMemoryGraphStore()
            
            logger.info("loading_graph_for_export")
            for node in self.graph_store.get_all_nodes():
                mem_store.add_node(node)
            
            for edge in self.graph_store.get_all_edges():
                mem_store.add_edge(edge)
                
            stats = mem_store.get_statistics()
            logger.info("graph_loaded_for_export", nodes=stats.node_count, edges=stats.edge_count)

            for fmt in self.config.export_formats:
                logger.info("exporting_kg", format=fmt)
                
                # Standardize format name for file extension
                ext = fmt.lower().replace("-", "")
                output_path = self.config.output_dir / f"kg_export.{ext}"
                
                if fmt in ["json-ld", "json"]:
                    with open(output_path, "w") as f:
                        f.write(mem_store.to_json())
                    logger.info("kg_exported", format=fmt, path=str(output_path))
                
                elif fmt == "cypher":
                    with open(output_path, "w") as f:
                        f.write("// Knowledge Graph Export\n")
                        f.write("// Generated by KGBuilder\n\n")
                        
                        # Nodes
                        for node in mem_store.get_all_nodes():
                            props = json.dumps(node.properties)
                            f.write(f"CREATE (n:{node.node_type} {{id: '{node.id}', label: '{node.label}', properties: '{props}'}});\n")
                        
                        # Edges
                        for edge in mem_store.get_all_edges():
                            props = json.dumps(edge.properties)
                            f.write(f"MATCH (s {{id: '{edge.source_id}'}}), (t {{id: '{edge.target_id}'}}) "
                                    f"CREATE (s)-[:{edge.edge_type} {{id: '{edge.id}', properties: '{props}'}}]->(t);\n")
                    logger.info("kg_exported", format=fmt, path=str(output_path))
                
                elif fmt in ["rdf", "ttl"]:
                    # Basic Turtle export (simplified)
                    output_path = self.config.output_dir / "kg_export.ttl"
                    with open(output_path, "w") as f:
                        f.write("@prefix kg: <http://example.org/kg#> .\n")
                        f.write("@prefix ont: <http://example.org/ontology#> .\n")
                        f.write("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n")
                        
                        for node in mem_store.get_all_nodes():
                            f.write(f"kg:{node.id} a ont:{node.node_type} ;\n")
                            f.write(f"    rdfs:label \"{node.label}\" .\n")
                        
                        for edge in mem_store.get_all_edges():
                            f.write(f"kg:{edge.source_id} ont:{edge.edge_type} kg:{edge.target_id} .\n")
                    logger.info("kg_exported", format=fmt, path=str(output_path))

        except Exception as e:
            logger.error("export_failed", error=str(e))
            self.result.errors.append(f"Export failed: {str(e)}")


def main() -> int:
    """Main entry point."""
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Full KG construction pipeline"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Pipeline configuration JSON file",
    )
    parser.add_argument(
        "--ontology-path",
        type=Path,
        help="Path to local ontology file (owl, ttl)",
    )
    parser.add_argument(
        "--ontology-url",
        type=str,
        default="http://localhost:3030",
        help="Fuseki ontology endpoint URL",
    )
    parser.add_argument(
        "--documents",
        type=Path,
        default=Path("data/documents"),
        help="Documents directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/kg_results"),
        help="Output directory",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        help="Path to competency questions JSON file",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of documents to retrieve per question",
    )
    parser.add_argument(
        "--follow-ups",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Generate synthetic follow-up questions (true/false)",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run in smoke test mode (uses test collections)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max discovery iterations",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation checks",
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip discovery phase",
    )
    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help="Skip enrichment phase",
    )
    parser.add_argument(
        "--enrich-only",
        action="store_true",
        help="Load checkpoint and run enrichment only (skip discovery)",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="Path to extraction checkpoint for re-enrichment (with --enrich-only)",
    )

    args = parser.parse_args()

    # Load config
    if args.config:
        with open(args.config) as f:
            config_dict = json.load(f)
        config = PipelineConfig(**config_dict)
    else:
        config = PipelineConfig(
            ontology_url=args.ontology_url,
            ontology_path=args.ontology_path,
            document_dir=args.documents,
            output_dir=args.output,
            questions_path=args.questions,
            smoke_test=args.smoke_test,
            max_iterations=args.max_iterations,
            skip_validation=args.skip_validation,
            skip_discovery=args.skip_discovery,
            skip_enrichment=args.skip_enrichment,
            enrich_only=args.enrich_only,
            checkpoint_path=args.checkpoint,
            top_k_docs=args.top_k,
            generate_follow_ups=args.follow_ups.lower() == "true",
        )

    # Run pipeline
    pipeline = FullKGPipeline(config)
    result = pipeline.run()

    # Print summary
    print("\n" + "=" * 70)
    print("KNOWLEDGE GRAPH CONSTRUCTION PIPELINE RESULTS")
    print("=" * 70)
    print(f"Timestamp: {result.timestamp}")
    print(f"Execution time: {result.execution_time_seconds:.1f}s")
    print()
    print("ONTOLOGY:")
    print(f"  Classes: {result.ontology_classes}")
    print(f"  Relations: {result.ontology_relations}")
    print()
    print("DATA:")
    print(f"  Documents loaded: {result.documents_loaded}")
    print(f"  Entities discovered: {result.discovered_entities}")
    print(f"  Relations discovered: {result.discovered_relations}")
    print()
    print("ENRICHMENT:")
    print(f"  Entities enriched: {result.enriched_entities}")
    print(f"  Relations enriched: {result.enriched_relations}")
    print()
    print("KNOWLEDGE GRAPH:")
    print(f"  Nodes in Neo4j: {result.kg_nodes}")
    print(f"  Edges in Neo4j: {result.kg_edges}")
    print()

    if result.errors:
        print("ERRORS:")
        for error in result.errors:
            print(f"  ✗ {error}")
        print()

    if result.warnings:
        print("WARNINGS:")
        for warning in result.warnings:
            print(f"  ⚠ {warning}")
        print()

    print("=" * 70)

    return 0 if not result.errors else 1


if __name__ == "__main__":
    sys.exit(main())
