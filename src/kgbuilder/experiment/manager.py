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

        try:
            logger.info(
                "config_run_starting",
                variant_name=variant.name,
                run_number=run_number,
                run_id=run_id,
            )

            # TODO: Integrate with actual KG builder
            # When integrating, pass run_id to KG builder for Neo4j namespace:
            #   kg_builder.build(params=variant.params, run_id=run_id)
            # The run_id should be used as a label or property on all nodes/edges
            kg_metrics = self._simulate_kg_build(variant)
            eval_metrics = self._simulate_evaluation(variant)

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
            
            # Save run metadata to file
            run.save_metadata(self.output_dir)

        return run

    @staticmethod
    def _simulate_kg_build(variant: ConfigVariant) -> dict[str, Any]:
        """Simulate KG building (placeholder).

        Args:
            variant: ConfigVariant being run

        Returns:
            Simulated KG metrics
        """
        # Placeholder: in real implementation, would call actual KG builder
        time.sleep(1)  # Simulate work

        nodes = 50 + (variant.params.max_iterations * 10)
        edges = 30 + (variant.params.max_iterations * 5)

        return {
            "nodes": nodes,
            "edges": edges,
            "build_time_seconds": 1.5,
            "model": variant.params.model,
            "max_iterations": variant.params.max_iterations,
        }

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
