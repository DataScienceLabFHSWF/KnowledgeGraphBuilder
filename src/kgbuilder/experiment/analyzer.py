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

    Backwards-compatible: tests may instantiate with `values=` only. We
    therefore provide defaults for `variant_name` and `metric_name` and
    expose both per-step `improvement_rate` (list) and an `avg_improvement_rate`.
    """

    variant_name: str = "baseline"
    metric_name: str = "metric"
    values: list[float] = field(default_factory=list)
    mean: float = 0.0
    std_dev: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    improvement: float = 0.0
    improvement_rate: list[float] = field(default_factory=list)
    avg_improvement_rate: float = 0.0
    has_plateau: bool = False

    def __post_init__(self) -> None:
        """Compute derived statistics when `values` are provided.

        This keeps `ConvergenceAnalysis(values=...)` convenient for tests and
        for ad-hoc usage outside the ExperimentAnalyzer pipeline.
        """
        if self.values:
            n = len(self.values)
            self.mean = sum(self.values) / n
            self.min_val = min(self.values)
            self.max_val = max(self.values)
            if n > 1:
                variance = sum((v - self.mean) ** 2 for v in self.values) / n
                self.std_dev = variance ** 0.5
                self.improvement = self.values[-1] - self.values[0]
                self.improvement_rate = [
                    self.values[i + 1] - self.values[i] for i in range(n - 1)
                ]
                self.avg_improvement_rate = (
                    self.improvement / (n - 1) if n > 1 else 0.0
                )
                relative_diff = abs(self.values[-1] - self.values[-2]) / max(
                    self.values[-2], 1e-9
                )
                self.has_plateau = relative_diff < 0.01

    @property
    def final_value(self) -> float:
        """Return the final (last) metric value or 0.0 if empty."""
        return float(self.values[-1]) if self.values else 0.0

    @property
    def plateaued(self) -> bool:
        """Alias for `has_plateau` used by legacy tests."""
        return self.has_plateau

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
            "improvement_rate": [round(v, 4) for v in self.improvement_rate],
            "avg_improvement_rate": round(self.avg_improvement_rate, 4),
            "has_plateau": self.has_plateau,
        }


@dataclass
class ComparativeAnalysis:
    """Comparative analysis across variants.

    Backwards-compatible: tests may call `ComparativeAnalysis(metrics=...)`.
    We accept an optional `metrics` alias and expose `ranking` as a dict for
    easy consumption by tests.
    """

    metric_name: str = "metric"
    variant_metrics: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, float] | None = None
    best_variant: str = ""
    best_score: float = 0.0
    worst_variant: str = ""
    ranking: dict[str, float] = field(default_factory=dict)
    mean_diff: float = 0.0
    winner_margin: float = 0.0
    best_margin: float = 0.0
    margins: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Accept `metrics=` as alias for variant_metrics (test compatibility)
        if self.metrics:
            self.variant_metrics = dict(self.metrics)

        # Compute ranking and best/worst
        if self.variant_metrics:
            sorted_items = sorted(
                self.variant_metrics.items(), key=lambda kv: kv[1], reverse=True
            )
            self.ranking = {k: v for k, v in sorted_items}
            self.best_variant, self.best_score = sorted_items[0]
            self.worst_variant = sorted_items[-1][0]
            worst_score = sorted_items[-1][1]
            values = [v for _, v in sorted_items]
            self.mean_diff = (sum(values) / len(values)) if values else 0.0
            self.winner_margin = (
                values[0] - values[1] if len(values) > 1 else 0.0
            )
            # best_margin = best - worst
            self.best_margin = round(self.best_score - worst_score, 10)
            # margins = distance of each variant from the best
            self.margins = {k: round(self.best_score - v, 10) for k, v in self.variant_metrics.items()}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "variant_metrics": {
                k: round(v, 4) for k, v in self.variant_metrics.items()
            },
            "best_variant": self.best_variant,
            "best_score": round(self.best_score, 4),
            "worst_variant": self.worst_variant,
            "ranking": [(name, round(score, 4)) for name, score in self.ranking.items()],
            "mean_difference": round(self.mean_diff, 4),
            "winner_margin": round(self.winner_margin, 4),
        }


class ExperimentAnalyzer:
    """Analyze experiment results for convergence and performance.

    Backward-compatible: accepts either an ``ExperimentResults`` instance or
    a plain list of ``ExperimentRun`` objects.
    """

    def __init__(self, results: ExperimentResults | list[ExperimentRun]) -> None:
        """Initialize analyzer.

        Args:
            results: ExperimentResults or list of ExperimentRun to analyze.
        """
        if isinstance(results, list):
            self.runs: list[ExperimentRun] = results
            self.results = ExperimentResults(runs=results)
        else:
            self.results = results
            self.runs = results.runs
        logger.info(
            "analyzer_initialized",
            num_runs=len(self.runs),
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
        by_variant: dict[str, list[ExperimentRun]] = {}
        for run in self.results.runs:
            variant_name = run.variant.name if run.variant else (run.variant_name or "unknown")
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
            # per-step improvement series and average
            analysis.improvement_rate = [
                values[i + 1] - values[i] for i in range(len(values) - 1)
            ]
            analysis.avg_improvement_rate = analysis.improvement / (len(values) - 1)

        # Plateau detection (last 2 values within 1% of each other)
        if len(values) >= 2:
            relative_diff = abs(values[-1] - values[-2]) / max(values[-2], 1e-9)
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
        """Get comprehensive summary of experiment results."""
        config = self.results.config
        return {
            "experiment_name": config.name if config else "unknown",
            "num_variants": len(config.variants) if config else 0,
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
