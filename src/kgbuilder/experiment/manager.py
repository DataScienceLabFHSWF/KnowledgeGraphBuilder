"""Experiment execution management for comparative analysis.

Orchestrates running multiple KG construction configurations and
collecting metrics from each.

Key Design Decisions:
- All experiments share a SINGLE Ollama server (no multiple instances)
- LLM calls are serialized to avoid timeout issues from request queueing
- Each run gets a unique ID for tracking and Neo4j namespace isolation
- Run metadata is persisted to JSON for reproducibility and debugging
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from kgbuilder.experiment.checkpoint import CheckpointManager
from kgbuilder.experiment.config import ConfigVariant, ExperimentConfig

logger = structlog.get_logger(__name__)


def generate_run_id() -> str:
    """Generate unique run ID for experiment tracking.
    
    Format: exp_{timestamp}_{short_uuid}
    Example: exp_20260203_143022_a1b2c3d4
    
    This ID should be used as:
    - Neo4j node label prefix or property for namespace isolation
    - Directory name for run artifacts
    - Reference in logs and reports
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"exp_{timestamp}_{short_uuid}"


@dataclass
class ExperimentRun:
    """Results from running a single experiment variant.

    Attributes:
        run_id: Unique identifier for this run (for Neo4j namespace, logging)
        variant: ConfigVariant that was run
        run_number: Run number (1-indexed)
        status: Status ("pending", "running", "completed", "failed")
        start_time: When run started
        end_time: When run completed
        duration_seconds: Total run time
        kg_metrics: KG construction metrics (nodes, edges, time)
        eval_metrics: Evaluation metrics (accuracy, F1, coverage, etc.)
        error: Error message if failed
        metadata: Additional metadata (includes system info, git commit, etc.)
    """

    run_id: str
    variant: ConfigVariant
    run_number: int = 1
    status: str = "pending"
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    kg_metrics: dict[str, Any] = field(default_factory=dict)
    eval_metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "variant_name": self.variant.name,
            "run_number": self.run_number,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "kg_metrics": self.kg_metrics,
            "eval_metrics": self.eval_metrics,
            "error": self.error,
            "metadata": self.metadata,
        }
    
    def save_metadata(self, output_dir: Path) -> Path:
        """Save run metadata to JSON file.
        
        Args:
            output_dir: Directory to save metadata
            
        Returns:
            Path to saved metadata file
        """
        run_dir = output_dir / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_path = run_dir / "run_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        
        logger.debug("run_metadata_saved", path=str(metadata_path), run_id=self.run_id)
        return metadata_path


@dataclass
class ExperimentResults:
    """Results from running a complete experiment.

    Attributes:
        config: ExperimentConfig that was run
        runs: List of ExperimentRun results
        start_time: When experiment started
        end_time: When experiment completed
        total_duration_seconds: Total experiment runtime
        completed_runs: Number of successfully completed runs
        failed_runs: Number of failed runs
        aggregate_metrics: Aggregated metrics across all runs
    """

    config: ExperimentConfig
    runs: list[ExperimentRun] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    total_duration_seconds: float = 0.0
    completed_runs: int = 0
    failed_runs: int = 0
    aggregate_metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "config": self.config.to_dict(),
            "runs": [r.to_dict() for r in self.runs],
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "completed_runs": self.completed_runs,
            "failed_runs": self.failed_runs,
            "aggregate_metrics": self.aggregate_metrics,
        }


class ConfigRunner:
    """Executes a single KG construction configuration.

    Orchestrates building a KG for a specific ConfigVariant and collecting
    metrics about the process and results.
    
    IMPORTANT: This runner is designed for SEQUENTIAL execution of LLM calls.
    All experiments share a single Ollama server - running multiple LLM calls
    in parallel will cause request queueing and timeouts.
    
    Each run gets a unique run_id that should be used for:
    - Neo4j namespace isolation (as node label or property)
    - Output directory structure
    - Log correlation
    """

    def __init__(self, output_dir: Path) -> None:
        """Initialize runner.

        Args:
            output_dir: Directory to save results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("config_runner_initialized", output_dir=str(output_dir))

    def run(
        self,
        variant: ConfigVariant,
        run_number: int = 1,
        run_id: str | None = None,
    ) -> ExperimentRun:
        """Run a single configuration variant with wandb logging."""
        # Try to import wandb, else warn
        try:
            import wandb
        except ImportError:
            wandb = None
            logger.warning("wandb not installed, skipping experiment logging")
        """Run a single configuration variant.

        Args:
            variant: ConfigVariant to run
            run_number: Run number (1-indexed)
            run_id: Optional run ID (generated if not provided)

        Returns:
            ExperimentRun with results
        """
        # Generate unique run ID if not provided
        if run_id is None:
            run_id = generate_run_id()

        run = ExperimentRun(run_id=run_id, variant=variant, run_number=run_number)
        run.status = "running"
        run.start_time = datetime.now()

        # Add system metadata
        run.metadata["run_id"] = run_id
        run.metadata["variant_name"] = variant.name
        run.metadata["started_at"] = run.start_time.isoformat()
        run.metadata["params"] = variant.params.to_dict()

        # --- WANDB: Start a run for this variant ---
        wandb_run = None
        if wandb is not None:
            import os
            wandb_project = os.environ.get("WANDB_PROJECT", "kg-builder")
            wandb_api_key = os.environ.get("WANDB_API_KEY")
            if wandb_api_key:
                os.environ["WANDB_API_KEY"] = wandb_api_key
            wandb_run = wandb.init(
                project=wandb_project,
                name=f"{variant.name}_run{run_number}_{run_id}",
                config={
                    **variant.params.to_dict(),
                    "variant_name": variant.name,
                    "run_id": run_id,
                    "run_number": run_number,
                },
                reinit=True,
                tags=[variant.name],
                notes=variant.description,
            )

        try:
            logger.info(
                "config_run_starting",
                variant_name=variant.name,
                run_number=run_number,
                run_id=run_id,
            )

            # Run actual KG building pipeline
            kg_metrics = self._build_kg(variant, run_id, wandb_run=wandb_run)
            eval_metrics = self._simulate_evaluation(variant)

            # SHACL quality scoring (best-effort)
            shacl_metrics = self._run_shacl_scoring(run_id, wandb_run=wandb_run)
            if shacl_metrics:
                kg_metrics["shacl"] = shacl_metrics

            run.kg_metrics = kg_metrics
            run.eval_metrics = eval_metrics
            run.status = "completed"

            # Add completion metadata
            run.metadata["completed_at"] = datetime.now().isoformat()

            logger.info(
                "config_run_completed",
                variant_name=variant.name,
                run_number=run_number,
                run_id=run_id,
                nodes=kg_metrics.get("nodes", 0),
                accuracy=eval_metrics.get("accuracy", 0),
            )

            # --- WANDB: Log metrics and artifacts ---
            if wandb_run is not None:
                # Log all metrics
                wandb_run.log({**kg_metrics, **eval_metrics, "duration_seconds": run.duration_seconds})
                # Save run metadata as artifact
                run_metadata_path = run.save_metadata(self.output_dir)
                artifact = wandb.Artifact(
                    name=f"run_metadata_{run_id}",
                    type="run_metadata",
                    description=f"Run metadata for {variant.name} run {run_number}",
                )
                artifact.add_file(str(run_metadata_path))
                wandb_run.log_artifact(artifact)

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            run.metadata["error_at"] = datetime.now().isoformat()
            run.metadata["error_type"] = type(e).__name__
            logger.error(
                "config_run_failed",
                variant_name=variant.name,
                run_number=run_number,
                run_id=run_id,
                error=str(e),
            )

        finally:
            run.end_time = datetime.now()
            if run.start_time:
                run.duration_seconds = (
                    run.end_time - run.start_time
                ).total_seconds()
            # Save run metadata to file (again, in case of error)
            run.save_metadata(self.output_dir)
            # --- WANDB: Finish run ---
            if wandb_run is not None:
                wandb_run.finish()

        return run

    def _build_kg(self, variant: ConfigVariant, run_id: str, wandb_run: Any = None) -> dict[str, Any]:
        """Build KG using the actual pipeline.

        Args:
            variant: ConfigVariant with KG params
            run_id: Unique run ID for Neo4j namespace
            wandb_run: Optional wandb run for continuous logging

        Returns:
            KG metrics (nodes, edges, build_time, etc.)
        """
        import os
        from kgbuilder.agents.question_generator import QuestionGenerationAgent
        from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop
        from kgbuilder.storage.ontology import FusekiOntologyService
        from kgbuilder.storage.vector import QdrantStore
        from kgbuilder.storage.neo4j_store import Neo4jGraphStore
        from kgbuilder.retrieval import FusionRAGRetriever
        from kgbuilder.embedding import OllamaProvider
        from kgbuilder.assembly.kg_builder import KGBuilder, KGBuilderConfig
        from kgbuilder.storage.protocol import Node
        from kgbuilder.extraction.entity import LLMEntityExtractor, OntologyPropertyDef
        from kgbuilder.extraction.relation import LLMRelationExtractor, OntologyRelationDef

        build_start = time.time()

        try:
            # Get environment config
            fuseki_url = os.getenv("FUSEKI_URL", "http://localhost:3030")
            fuseki_dataset = os.getenv("FUSEKI_DATASET", "kgbuilder")
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            qdrant_collection = os.getenv("QDRANT_COLLECTION", "kgbuilder")
            ollama_url = os.getenv("OLLAMA_URL", "http://localhost:18134")
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "changeme")

            # Initialize services
            logger.info("kg_build_initializing_services", run_id=run_id)
            
            # Log initialization to wandb
            if wandb_run is not None:
                wandb_run.log({"status": "initializing_services"})
            
            # Ontology service
            ontology_service = FusekiOntologyService(
                fuseki_url=fuseki_url,
                dataset_name=fuseki_dataset
            )
            
            # Vector store
            vector_store = QdrantStore(
                url=qdrant_url,
                collection_name=qdrant_collection
            )
            
            # LLM & Embeddings
            llm = OllamaProvider(
                model=variant.params.model,
                base_url=ollama_url
            )
            
            # Retriever
            retriever = FusionRAGRetriever(
                qdrant_store=vector_store,
                llm_provider=llm,
                dense_weight=0.7,
                sparse_weight=0.3
            )
            
            # Build sparse index from Qdrant for hybrid retrieval
            logger.info("building_sparse_index_for_retrieval", run_id=run_id)
            retriever._build_sparse_index_from_qdrant()
            if retriever._index_built:
                logger.info(
                    "sparse_index_ready",
                    run_id=run_id,
                    document_count=len(retriever._documents)
                )
            
            # Question generation
            question_gen = QuestionGenerationAgent(
                ontology_service=ontology_service
            )
            
            # Entity extractor
            entity_extractor = LLMEntityExtractor(
                llm_provider=llm,
                confidence_threshold=variant.params.confidence_threshold
            )
            
            # Relation extractor (NEW - Phase 5)
            relation_extractor = LLMRelationExtractor(
                llm_provider=llm,
                confidence_threshold=variant.params.confidence_threshold
            )
            
            # Neo4j store
            neo4j_store = Neo4jGraphStore(
                uri=neo4j_uri,
                auth=(neo4j_user, neo4j_password)
            )
            
            # Get ontology classes with properties for extraction guidance (RICH SCHEMA)
            from kgbuilder.extraction.entity import OntologyClassDef
            class_labels = ontology_service.get_all_classes()
            ontology_classes = []
            
            for label in class_labels:
                # Load properties for each class from ontology (NEW)
                properties_tuples = ontology_service.get_class_properties(label)
                properties = [
                    OntologyPropertyDef(
                        name=prop_name,
                        data_type=prop_type,
                        description=prop_desc if prop_desc else None
                    )
                    for prop_name, prop_type, prop_desc in properties_tuples
                ]
                
                ontology_classes.append(
                    OntologyClassDef(
                        uri=f"http://ontology#/{label}",
                        label=label,
                        description=None,
                        properties=properties,  # NEW: Rich schema
                    )
                )
            
            logger.info("ontology_classes_loaded", count=len(ontology_classes), run_id=run_id)
            
            # Get ontology relations for extraction (NEW - Phase 5)
            ontology_relations = []
            try:
                # Query ontology for all object properties (relations)
                relation_uris = ontology_service.get_class_relations(None)  # Get all relations
                ontology_relations = [
                    OntologyRelationDef(
                        uri=f"http://ontology#/{rel}",
                        label=rel,
                        description=None,
                    )
                    for rel in relation_uris
                ]
            except Exception as e:
                logger.warning("ontology_relations_load_failed", error=str(e))
                ontology_relations = []
            
            logger.info("ontology_relations_loaded", count=len(ontology_relations), run_id=run_id)
            
            # Discovery loop
            discovery_loop = IterativeDiscoveryLoop(
                retriever=retriever,
                extractor=entity_extractor,
                question_generator=question_gen,
                ontology_classes=ontology_classes,
                relation_extractor=relation_extractor,  # NEW: Wire Phase 5
                ontology_relations=ontology_relations,  # NEW: Wire Phase 5
            )
            
            # Run discovery loop with continuous wandb logging
            logger.info("kg_build_starting_discovery", run_id=run_id)
            
            # Log initial state to wandb
            if wandb_run is not None:
                wandb_run.log({
                    "status": "discovery_started",
                    "ontology_classes": len(ontology_classes),
                    "max_iterations": variant.params.max_iterations,
                })
            
            discover_result = discovery_loop.run_discovery(
                max_iterations=variant.params.max_iterations,
                coverage_target=0.85,
                top_k_docs=5,  # Reduced from 10 to minimize context size for docker Ollama
                ontology_classes=ontology_classes,
                extract_relations=True,  # NEW: One-pass entity + relation extraction
            )
            
            # Get entities and relations from discovery result (dataclass, not dict)
            entities = discover_result.entities
            relations = getattr(discover_result, 'relations', [])  # NEW: Get extracted relations
            
            # Log discovery results to wandb continuously
            if wandb_run is not None:
                wandb_run.log({
                    "discovery_complete": 1,
                    "entities_discovered": len(entities),
                    "discovery_iterations": discover_result.total_iterations,
                    "discovery_coverage": discover_result.final_coverage,
                    "discovery_time_sec": discover_result.total_time_sec,
                })
            
            logger.info(
                "kg_build_discovery_complete",
                run_id=run_id,
                entities=len(entities),
                success=discover_result.success,
                coverage=discover_result.final_coverage,
            )
            
            # CHECKPOINT: Save extraction results before building KG
            # This enables semantic enrichment and skips re-extraction if needed
            logger.info("checkpointing_extraction_results", run_id=run_id)
            checkpoint_manager = CheckpointManager(
                checkpoint_dir=output_dir / "checkpoints"
            )
            checkpoint_path = checkpoint_manager.save_extraction(
                run_id=run_id,
                variant_name=variant.name,
                entities=entities,
                relations=relations,
                extraction_seconds=time.time() - build_start,
                questions_processed=discover_result.total_iterations,
            )
            logger.info(
                "extraction_checkpointed",
                run_id=run_id,
                checkpoint_path=str(checkpoint_path),
            )
            
            # Build KG with KGBuilder
            logger.info("kg_build_assembling", run_id=run_id)
            
            # Convert ExtractedEntity to Node format
            nodes = [
                Node(
                    id=e.id,
                    label=e.label,
                    node_type=e.entity_type,
                    properties={
                        "confidence": e.confidence,
                        "description": getattr(e, "description", ""),
                        "run_id": run_id
                    }
                )
                for e in entities
            ]
            
            # Build graph with BOTH entities and relations (NEW - Phase 5)
            builder = KGBuilder(
                primary_store=neo4j_store,
                config=KGBuilderConfig(
                    sync_stores=False,
                    batch_size=1000,
                )
            )
            
            # Log relation count if we extracted relations
            if relations:
                logger.info("kg_build_with_relations", relation_count=len(relations), run_id=run_id)
            
            # Build with relations (NOW includes Phase 5 output!)
            build_result = builder.build(entities=nodes, relations=relations if relations else None)
            
            build_time = time.time() - build_start
            
            # Log KG build results to wandb
            if wandb_run is not None:
                wandb_run.log({
                    "kg_build_complete": 1,
                    "nodes_created": build_result.nodes_created,
                    "edges_created": build_result.edges_created,
                    "build_time_seconds": round(build_time, 2),
                })
            
            logger.info(
                "kg_build_complete",
                run_id=run_id,
                nodes_created=build_result.nodes_created,
                edges_created=build_result.edges_created,
                build_time=build_time
            )
            
            return {
                "nodes": build_result.nodes_created,
                "edges": build_result.edges_created,
                "build_time_seconds": round(build_time, 2),
                "model": variant.params.model,
                "max_iterations": variant.params.max_iterations,
            }

        except Exception as e:
            logger.error("kg_build_failed", run_id=run_id, error=str(e))
            raise

    def _run_shacl_scoring(
        self, run_id: str, wandb_run: Any = None,
    ) -> dict[str, Any] | None:
        """Run KGQualityScorer and persist the SHACL report with run artifacts.

        Returns a dict with scorer metrics or ``None`` on failure.
        """
        import os, shutil
        try:
            from kgbuilder.validation.scorer import KGQualityScorer
            from kgbuilder.storage.neo4j_store import Neo4jGraphStore

            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "changeme")
            owl_path = Path(os.getenv(
                "ONTOLOGY_OWL_PATH",
                "./data/ontology/law/law-ontology-v1.0.owl",
            ))

            store = Neo4jGraphStore(neo4j_uri, (neo4j_user, neo4j_password))
            scorer = KGQualityScorer(ontology_owl_path=owl_path, sample_limit=500)
            report = scorer.score_neo4j_store(store)

            # Copy SHACL report JSON into the run directory
            run_dir = self.output_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            if report.shacl_report_path:
                dest = run_dir / "shacl_report.json"
                shutil.copy2(report.shacl_report_path, dest)
                logger.info("shacl_report_saved", dest=str(dest), run_id=run_id)

            metrics = {
                "combined_score": report.combined_score,
                "shacl_score": report.shacl_score,
                "consistency": report.consistency,
                "violations": report.violations,
                "class_coverage": report.class_coverage,
            }

            if wandb_run is not None:
                wandb_run.log({f"shacl_{k}": v for k, v in metrics.items()})

            return metrics

        except Exception as exc:
            logger.warning("shacl_scoring_failed", run_id=run_id, error=str(exc))
            return None

    @staticmethod
    def _simulate_evaluation(variant: ConfigVariant) -> dict[str, Any]:
        """Simulate QA evaluation (placeholder).

        Args:
            variant: ConfigVariant being run

        Returns:
            Simulated evaluation metrics
        """
        # Placeholder: in real implementation, would call actual evaluator
        base_accuracy = 0.65 + (variant.params.confidence_threshold * 0.1)
        accuracy = min(0.95, base_accuracy)

        return {
            "accuracy": accuracy,
            "f1_score": accuracy - 0.05,
            "coverage": 0.85,
            "completeness": 0.75,
            "total_questions": 54,
            "correct_answers": int(54 * accuracy),
        }


class ExperimentManager:
    """Orchestrates running multiple experiment variants.

    Manages execution of complete experiments with multiple variants,
    handling result aggregation and metadata tracking.
    
    IMPORTANT DESIGN DECISIONS:
    1. LLM calls are executed SEQUENTIALLY (not in parallel) to avoid
       Ollama request queueing and timeouts. All experiments share a
       single Ollama server instance.
    
    2. Each run gets a unique run_id for:
       - Neo4j namespace isolation (all nodes/edges tagged with run_id)
       - Output directory structure (results/{run_id}/)
       - Log correlation and debugging
    
    3. Run metadata is persisted to JSON files for reproducibility.
    
    4. The parallel_jobs setting controls OTHER parallelizable work
       (e.g., document loading, embedding), NOT LLM calls.
    """

    def __init__(self, config: ExperimentConfig) -> None:
        """Initialize manager.

        Args:
            config: ExperimentConfig for this experiment
        """
        self.config = config
        self.experiment_id = generate_run_id()  # Master experiment ID
        self.runner = ConfigRunner(config.get_output_dir())
        logger.info(
            "experiment_manager_initialized",
            name=config.name,
            experiment_id=self.experiment_id,
            num_variants=len(config.variants),
        )

    def run_experiments(self) -> ExperimentResults:
        """Run all experiment variants.

        Executes all variants SEQUENTIALLY to avoid Ollama timeouts.
        Each run gets a unique run_id for tracking.

        Returns:
            ExperimentResults with all runs and metrics
        """
        self.config.validate()

        results = ExperimentResults(config=self.config)
        results.start_time = datetime.now()

        logger.info(
            "experiments_starting",
            name=self.config.name,
            experiment_id=self.experiment_id,
            num_variants=len(self.config.variants),
            num_runs=self.config.num_runs,
            note="LLM calls are sequential to avoid Ollama timeouts",
        )

        # Generate all runs with unique IDs
        all_runs = []
        for variant in self.config.variants:
            for run_num in range(1, self.config.num_runs + 1):
                run_id = f"{self.experiment_id}_{variant.name}_{run_num}"
                all_runs.append((variant, run_num, run_id))

        # Execute runs SEQUENTIALLY (LLM calls cannot be parallelized safely)
        # The parallel_jobs setting is for other parallelizable work, not LLM
        runs = self._run_sequential(all_runs)

        results.runs = runs
        results.end_time = datetime.now()

        # Compute statistics
        results.completed_runs = sum(1 for r in runs if r.status == "completed")
        results.failed_runs = sum(1 for r in runs if r.status == "failed")

        if results.end_time and results.start_time:
            results.total_duration_seconds = (
                results.end_time - results.start_time
            ).total_seconds()

        # Aggregate metrics
        results.aggregate_metrics = self._aggregate_metrics(runs)
        
        # Save experiment-level metadata
        self._save_experiment_metadata(results)

        logger.info(
            "experiments_completed",
            name=self.config.name,
            experiment_id=self.experiment_id,
            completed_runs=results.completed_runs,
            failed_runs=results.failed_runs,
            total_duration_seconds=round(results.total_duration_seconds, 2),
        )

        return results
    
    def _save_experiment_metadata(self, results: ExperimentResults) -> Path:
        """Save experiment-level metadata to JSON.
        
        Args:
            results: Experiment results
            
        Returns:
            Path to saved metadata file
        """
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        metadata = {
            "experiment_id": self.experiment_id,
            "experiment_name": self.config.name,
            "started_at": results.start_time.isoformat() if results.start_time else None,
            "completed_at": results.end_time.isoformat() if results.end_time else None,
            "total_duration_seconds": results.total_duration_seconds,
            "completed_runs": results.completed_runs,
            "failed_runs": results.failed_runs,
            "config": self.config.to_dict(),
            "run_ids": [r.run_id for r in results.runs],
            "aggregate_metrics": results.aggregate_metrics,
        }
        
        metadata_path = output_dir / f"{self.experiment_id}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info("experiment_metadata_saved", path=str(metadata_path))
        return metadata_path

    def _run_sequential(
        self, all_runs: list[tuple[ConfigVariant, int, str]]
    ) -> list[ExperimentRun]:
        """Run all variants sequentially.
        
        This is the ONLY execution mode for LLM-based experiments.
        Parallel execution would cause Ollama request queueing and timeouts.

        Args:
            all_runs: List of (variant, run_number, run_id) tuples

        Returns:
            List of ExperimentRun results
        """
        runs = []
        total = len(all_runs)
        for idx, (variant, run_num, run_id) in enumerate(all_runs, 1):
            logger.info(
                "run_progress",
                current=idx,
                total=total,
                variant=variant.name,
                run_id=run_id,
            )
            run = self.runner.run(variant, run_num, run_id=run_id)
            runs.append(run)
        return runs

    @staticmethod
    def _aggregate_metrics(runs: list[ExperimentRun]) -> dict[str, Any]:
        """Aggregate metrics across all runs.

        Args:
            runs: List of ExperimentRun results

        Returns:
            Aggregated metrics
        """
        if not runs:
            return {}

        completed = [r for r in runs if r.status == "completed"]

        if not completed:
            return {"error": "No completed runs"}

        # Group by variant
        by_variant = {}
        for run in completed:
            variant_name = run.variant.name
            if variant_name not in by_variant:
                by_variant[variant_name] = []
            by_variant[variant_name].append(run)

        # Aggregate per variant
        aggregate = {}
        for variant_name, variant_runs in by_variant.items():
            # Get all eval metrics
            eval_metrics_list = [
                r.eval_metrics for r in variant_runs if r.eval_metrics
            ]

            if not eval_metrics_list:
                continue

            # Average metrics
            avg_metrics = {}
            for key in eval_metrics_list[0].keys():
                if isinstance(eval_metrics_list[0][key], (int, float)):
                    values = [m.get(key, 0) for m in eval_metrics_list]
                    avg_metrics[key] = round(sum(values) / len(values), 4)

            aggregate[variant_name] = avg_metrics

        return aggregate
