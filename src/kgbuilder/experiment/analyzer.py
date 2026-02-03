"""Experiment analysis for convergence and comparative metrics.

Analyzes experiment results to extract convergence patterns,
comparative performance metrics, and statistical insights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from kgbuilder.experiment.manager import ExperimentResults, ExperimentRun

logger = structlog.get_logger(__name__)


@dataclass
class ConvergenceAnalysis:
    """Convergence analysis for a single variant.

    Attributes:
        variant_name: Name of the variant
        metric_name: Name of metric being analyzed (e.g., "accuracy")
        values: Metric values over iterations/runs
        mean: Mean metric value
        std_dev: Standard deviation
        min_val: Minimum value
        max_val: Maximum value
        improvement: Improvement from first to last value
        improvement_rate: Improvement rate per iteration
        has_plateau: Whether convergence has plateaued
    """

    variant_name: str
    metric_name: str
    values: list[float] = field(default_factory=list)
    mean: float = 0.0
    std_dev: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    improvement: float = 0.0
    improvement_rate: float = 0.0
    has_plateau: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "variant_name": self.variant_name,
            "metric_name": self.metric_name,
            "values": [round(v, 4) for v in self.values],
            "mean": round(self.mean, 4),
            "std_dev": round(self.std_dev, 4),
            "min": round(self.min_val, 4),
            "max": round(self.max_val, 4),
            "improvement": round(self.improvement, 4),
            "improvement_rate": round(self.improvement_rate, 4),
            "has_plateau": self.has_plateau,
        }


@dataclass
class ComparativeAnalysis:
    """Comparative analysis across variants.

    Attributes:
        metric_name: Metric being compared
        variant_metrics: Dict of variant_name -> metric value
        best_variant: Name of best performing variant
        worst_variant: Name of worst performing variant
        ranking: List of variants ranked by metric
        mean_diff: Mean difference across variants
        winner_margin: Margin between best and 2nd best
    """

    metric_name: str
    variant_metrics: dict[str, float] = field(default_factory=dict)
    best_variant: str = ""
    worst_variant: str = ""
    ranking: list[tuple[str, float]] = field(default_factory=list)
    mean_diff: float = 0.0
    winner_margin: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "variant_metrics": {
                k: round(v, 4) for k, v in self.variant_metrics.items()
            },
            "best_variant": self.best_variant,
            "worst_variant": self.worst_variant,
            "ranking": [
                (name, round(score, 4)) for name, score in self.ranking
            ],
            "mean_difference": round(self.mean_diff, 4),
            "winner_margin": round(self.winner_margin, 4),
        }


class ExperimentAnalyzer:
    """Analyze experiment results for convergence and performance.

    Provides comprehensive analysis of experiments including convergence
    tracking, comparative analysis, and statistical insights.
    """

    def __init__(self, results: ExperimentResults) -> None:
        """Initialize analyzer.

        Args:
            results: ExperimentResults to analyze
        """
        self.results = results
        logger.info(
            "analyzer_initialized",
            num_runs=len(results.runs),
            num_variants=len(results.config.variants),
        )

    def analyze_convergence(
        self, metric_name: str = "accuracy"
    ) -> dict[str, ConvergenceAnalysis]:
        """Analyze convergence for a metric across variants.

        Args:
            metric_name: Metric to analyze (default: "accuracy")

        Returns:
            Dict of variant_name -> ConvergenceAnalysis
        """
        convergence = {}

        # Group runs by variant
        by_variant = {}
        for run in self.results.runs:
            variant_name = run.variant.name
            if variant_name not in by_variant:
                by_variant[variant_name] = []
            by_variant[variant_name].append(run)

        # Analyze each variant
        for variant_name, runs in by_variant.items():
            analysis = self._analyze_variant_convergence(
                variant_name, runs, metric_name
            )
            convergence[variant_name] = analysis

        logger.info(
            "convergence_analysis_complete",
            metric_name=metric_name,
            num_variants=len(convergence),
        )

        return convergence

    @staticmethod
    def _analyze_variant_convergence(
        variant_name: str,
        runs: list[ExperimentRun],
        metric_name: str,
    ) -> ConvergenceAnalysis:
        """Analyze convergence for a single variant.

        Args:
            variant_name: Name of variant
            runs: List of runs for this variant
            metric_name: Metric to analyze

        Returns:
            ConvergenceAnalysis
        """
        analysis = ConvergenceAnalysis(
            variant_name=variant_name,
            metric_name=metric_name,
        )

        # Extract metric values from runs
        values = []
        for run in sorted(runs, key=lambda r: r.run_number):
            if run.eval_metrics and metric_name in run.eval_metrics:
                values.append(run.eval_metrics[metric_name])

        analysis.values = values

        if not values:
            return analysis

        # Compute statistics
        analysis.mean = sum(values) / len(values)
        analysis.min_val = min(values)
        analysis.max_val = max(values)

        # Std dev
        if len(values) > 1:
            variance = sum((v - analysis.mean) ** 2 for v in values) / len(values)
            analysis.std_dev = variance**0.5
        else:
            analysis.std_dev = 0.0

        # Improvement
        if len(values) > 1:
            analysis.improvement = values[-1] - values[0]
            analysis.improvement_rate = analysis.improvement / (len(values) - 1)

        # Plateau detection (last 2 values within 1% of each other)
        if len(values) >= 2:
            relative_diff = abs(values[-1] - values[-2]) / values[-2]
            analysis.has_plateau = relative_diff < 0.01

        return analysis

    def compare_variants(
        self, metric_name: str = "accuracy"
    ) -> ComparativeAnalysis:
        """Compare variants for a specific metric.

        Args:
            metric_name: Metric to compare (default: "accuracy")

        Returns:
            ComparativeAnalysis with rankings and comparisons
        """
        comparison = ComparativeAnalysis(metric_name=metric_name)

        # Get aggregated metrics per variant
        variant_metrics = self.results.aggregate_metrics

        # Extract metric for each variant
        for variant_name, metrics in variant_metrics.items():
            if metric_name in metrics:
                comparison.variant_metrics[variant_name] = metrics[metric_name]

        if not comparison.variant_metrics:
            logger.warning(
                "no_metrics_found_for_comparison",
                metric_name=metric_name,
            )
            return comparison

        # Ranking
        sorted_variants = sorted(
            comparison.variant_metrics.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        comparison.ranking = sorted_variants

        if sorted_variants:
            comparison.best_variant = sorted_variants[0][0]
            comparison.worst_variant = sorted_variants[-1][0]

            # Winner margin
            if len(sorted_variants) >= 2:
                comparison.winner_margin = (
                    sorted_variants[0][1] - sorted_variants[1][1]
                )

        # Mean difference
        values = list(comparison.variant_metrics.values())
        if values:
            mean_val = sum(values) / len(values)
            comparison.mean_diff = max(values) - min(values)

        logger.info(
            "comparison_analysis_complete",
            metric_name=metric_name,
            best_variant=comparison.best_variant,
            best_score=comparison.variant_metrics.get(
                comparison.best_variant, 0
            ),
        )

        return comparison

    def aggregate_statistics(self) -> dict[str, Any]:
        """Aggregate statistics across all runs.

        Returns:
            Dictionary with overall statistics
        """
        completed = [r for r in self.results.runs if r.status == "completed"]
        failed = [r for r in self.results.runs if r.status == "failed"]

        total_time = sum(r.duration_seconds for r in completed)
        avg_time = (
            total_time / len(completed) if completed else 0
        )

        return {
            "total_runs": len(self.results.runs),
            "completed_runs": len(completed),
            "failed_runs": len(failed),
            "total_time_seconds": round(total_time, 2),
            "average_time_per_run_seconds": round(avg_time, 2),
            "success_rate": round(
                len(completed) / len(self.results.runs)
                if self.results.runs
                else 0,
                4,
            ),
        }

    def get_summary(self) -> dict[str, Any]:
        """Get comprehensive summary of experiment results.

        Returns:
            Dictionary with summary statistics
        """
        return {
            "experiment_name": self.results.config.name,
            "num_variants": len(self.results.config.variants),
            "statistics": self.aggregate_statistics(),
            "aggregate_metrics": self.results.aggregate_metrics,
            "best_variant": self._get_best_variant(),
        }

    def _get_best_variant(self) -> str:
        """Get best performing variant by accuracy.

        Returns:
            Name of best variant
        """
        comparison = self.compare_variants("accuracy")
        return comparison.best_variant
