"""Experiment execution management for comparative analysis.

Orchestrates running multiple KG construction configurations and
collecting metrics from each.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from kgbuilder.experiment.config import ConfigVariant, ExperimentConfig

logger = structlog.get_logger(__name__)


@dataclass
class ExperimentRun:
    """Results from running a single experiment variant.

    Attributes:
        variant: ConfigVariant that was run
        run_number: Run number (1-indexed)
        status: Status ("pending", "running", "completed", "failed")
        start_time: When run started
        end_time: When run completed
        duration_seconds: Total run time
        kg_metrics: KG construction metrics (nodes, edges, time)
        eval_metrics: Evaluation metrics (accuracy, F1, coverage, etc.)
        error: Error message if failed
        metadata: Additional metadata
    """

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
    ) -> ExperimentRun:
        """Run a single configuration variant.

        Args:
            variant: ConfigVariant to run
            run_number: Run number (1-indexed)

        Returns:
            ExperimentRun with results
        """
        run = ExperimentRun(variant=variant, run_number=run_number)
        run.status = "running"
        run.start_time = datetime.now()

        try:
            logger.info(
                "config_run_starting",
                variant_name=variant.name,
                run_number=run_number,
            )

            # TODO: Integrate with actual KG builder
            # For now, simulate the run
            kg_metrics = self._simulate_kg_build(variant)
            eval_metrics = self._simulate_evaluation(variant)

            run.kg_metrics = kg_metrics
            run.eval_metrics = eval_metrics
            run.status = "completed"

            logger.info(
                "config_run_completed",
                variant_name=variant.name,
                run_number=run_number,
                nodes=kg_metrics.get("nodes", 0),
                accuracy=eval_metrics.get("accuracy", 0),
            )

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            logger.error(
                "config_run_failed",
                variant_name=variant.name,
                run_number=run_number,
                error=str(e),
            )

        finally:
            run.end_time = datetime.now()
            if run.start_time:
                run.duration_seconds = (
                    run.end_time - run.start_time
                ).total_seconds()

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
    handling parallel execution and result aggregation.
    """

    def __init__(self, config: ExperimentConfig) -> None:
        """Initialize manager.

        Args:
            config: ExperimentConfig for this experiment
        """
        self.config = config
        self.runner = ConfigRunner(config.get_output_dir())
        logger.info(
            "experiment_manager_initialized",
            name=config.name,
            num_variants=len(config.variants),
        )

    def run_experiments(self) -> ExperimentResults:
        """Run all experiment variants.

        Executes all variants according to configuration, supporting
        parallel execution.

        Returns:
            ExperimentResults with all runs and metrics
        """
        self.config.validate()

        results = ExperimentResults(config=self.config)
        results.start_time = datetime.now()

        logger.info(
            "experiments_starting",
            name=self.config.name,
            num_variants=len(self.config.variants),
            num_runs=self.config.num_runs,
            parallel_jobs=self.config.parallel_jobs,
        )

        # Generate all runs
        all_runs = []
        for variant in self.config.variants:
            for run_num in range(1, self.config.num_runs + 1):
                all_runs.append((variant, run_num))

        # Execute runs (sequential or parallel)
        if self.config.parallel_jobs > 1:
            runs = self._run_parallel(all_runs)
        else:
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

        logger.info(
            "experiments_completed",
            name=self.config.name,
            completed_runs=results.completed_runs,
            failed_runs=results.failed_runs,
            total_duration_seconds=round(results.total_duration_seconds, 2),
        )

        return results

    def _run_sequential(
        self, all_runs: list[tuple[ConfigVariant, int]]
    ) -> list[ExperimentRun]:
        """Run all variants sequentially.

        Args:
            all_runs: List of (variant, run_number) tuples

        Returns:
            List of ExperimentRun results
        """
        runs = []
        for variant, run_num in all_runs:
            run = self.runner.run(variant, run_num)
            runs.append(run)
        return runs

    def _run_parallel(
        self, all_runs: list[tuple[ConfigVariant, int]]
    ) -> list[ExperimentRun]:
        """Run variants in parallel.

        Args:
            all_runs: List of (variant, run_number) tuples

        Returns:
            List of ExperimentRun results
        """
        # Use asyncio for parallel execution
        async def run_all():
            semaphore = asyncio.Semaphore(self.config.parallel_jobs)

            async def run_one(variant, run_num):
                async with semaphore:
                    # Run in executor to avoid blocking
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None, self.runner.run, variant, run_num
                    )

            tasks = [run_one(v, n) for v, n in all_runs]
            return await asyncio.gather(*tasks)

        # Run the async executor
        try:
            runs = asyncio.run(run_all())
        except RuntimeError:
            # Fallback if event loop already running
            runs = self._run_sequential(all_runs)

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
