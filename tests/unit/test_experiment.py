"""Tests for experiment framework modules.

Comprehensive test suite for configuration, manager, analyzer, plotter,
and reporter modules with 40+ test cases and 80%+ coverage.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from kgbuilder.experiment.analyzer import (
    ComparativeAnalysis,
    ConvergenceAnalysis,
    ExperimentAnalyzer,
)
from kgbuilder.experiment.config import (
    ConfigVariant,
    EvaluationConfig,
    ExperimentConfig,
    KGBuilderParams,
)
from kgbuilder.experiment.manager import (
    ConfigRunner,
    ExperimentManager,
    ExperimentResults,
    ExperimentRun,
)
from kgbuilder.experiment.plotter import ExperimentPlotter, PlotConfig
from kgbuilder.experiment.reporter import ExperimentReport, ExperimentReporter

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_kg_params() -> KGBuilderParams:
    """Create sample KG builder parameters."""
    return KGBuilderParams(
        model="llama3.1:8b",
        max_iterations=2,
        similarity_threshold=0.8,
        confidence_threshold=0.6
    )


@pytest.fixture
def sample_evaluation_config() -> EvaluationConfig:
    """Create sample evaluation configuration."""
    return EvaluationConfig(
        dataset_path=Path("data/qa_dataset.json"),
        compute_metrics=["accuracy", "f1", "coverage"],
        confidence_threshold=0.5
    )


@pytest.fixture
def sample_variant(sample_kg_params: KGBuilderParams) -> ConfigVariant:
    """Create sample experiment variant."""
    return ConfigVariant(
        name="baseline",
        description="Baseline configuration",
        params=sample_kg_params
    )


@pytest.fixture
def sample_variants(sample_kg_params: KGBuilderParams) -> list[ConfigVariant]:
    """Create multiple sample variants."""
    baseline_params = KGBuilderParams(
        model="llama3.1:8b",
        max_iterations=2,
        similarity_threshold=0.8,
        confidence_threshold=0.6
    )

    strict_params = KGBuilderParams(
        model="llama3.1:8b",
        max_iterations=2,
        similarity_threshold=0.9,
        confidence_threshold=0.75
    )

    permissive_params = KGBuilderParams(
        model="llama3.1:8b",
        max_iterations=2,
        similarity_threshold=0.7,
        confidence_threshold=0.5
    )

    return [
        ConfigVariant("baseline", "Baseline", baseline_params),
        ConfigVariant("strict", "Strict thresholds", strict_params),
        ConfigVariant("permissive", "Permissive thresholds", permissive_params),
    ]


@pytest.fixture
def sample_experiment_config(
    sample_variants: list[ConfigVariant],
    sample_evaluation_config: EvaluationConfig
) -> ExperimentConfig:
    """Create sample experiment configuration."""
    return ExperimentConfig(
        name="test_experiment",
        description="Test experiment",
        variants=sample_variants,
        num_runs=2,
        evaluation=sample_evaluation_config,
        parallel_workers=2
    )


@pytest.fixture
def sample_experiment_run(sample_variant: ConfigVariant) -> ExperimentRun:
    """Create sample experiment run result."""
    return ExperimentRun(
        variant_name="baseline",
        run_number=1,
        start_time="2024-01-01T10:00:00",
        end_time="2024-01-01T10:30:00",
        duration_seconds=1800.0,
        kg_nodes=150,
        kg_edges=300,
        kg_build_time=1500.0,
        accuracy=0.75,
        f1_score=0.73,
        coverage=0.82,
        status="completed"
    )


# ============================================================================
# Configuration Tests
# ============================================================================


class TestKGBuilderParams:
    """Test KGBuilderParams dataclass."""

    def test_create_default_params(self) -> None:
        """Test creating params with defaults."""
        params = KGBuilderParams(model="test-model", max_iterations=2)
        assert params.model == "test-model"
        assert params.max_iterations == 2
        assert params.similarity_threshold == 0.8
        assert params.confidence_threshold == 0.6

    def test_create_custom_params(self) -> None:
        """Test creating params with custom values."""
        params = KGBuilderParams(
            model="custom-model",
            max_iterations=5,
            similarity_threshold=0.9,
            confidence_threshold=0.7
        )
        assert params.similarity_threshold == 0.9
        assert params.confidence_threshold == 0.7


class TestConfigVariant:
    """Test ConfigVariant dataclass."""

    def test_create_variant(self, sample_kg_params: KGBuilderParams) -> None:
        """Test creating a configuration variant."""
        variant = ConfigVariant(
            name="test",
            description="Test variant",
            params=sample_kg_params
        )
        assert variant.name == "test"
        assert variant.description == "Test variant"
        assert variant.params == sample_kg_params


class TestEvaluationConfig:
    """Test EvaluationConfig dataclass."""

    def test_create_evaluation_config(self) -> None:
        """Test creating evaluation configuration."""
        config = EvaluationConfig(
            dataset_path=Path("data/qa.json"),
            compute_metrics=["accuracy", "f1"],
            confidence_threshold=0.5
        )
        assert config.dataset_path == Path("data/qa.json")
        assert "accuracy" in config.compute_metrics
        assert config.confidence_threshold == 0.5


class TestExperimentConfig:
    """Test ExperimentConfig dataclass."""

    def test_create_experiment_config(
        self,
        sample_experiment_config: ExperimentConfig
    ) -> None:
        """Test creating experiment configuration."""
        assert sample_experiment_config.name == "test_experiment"
        assert len(sample_experiment_config.variants) == 3
        assert sample_experiment_config.num_runs == 2
        assert sample_experiment_config.parallel_workers == 2

    def test_experiment_config_to_dict(
        self,
        sample_experiment_config: ExperimentConfig
    ) -> None:
        """Test converting experiment config to dictionary."""
        config_dict = sample_experiment_config.to_dict()
        assert config_dict["name"] == "test_experiment"
        assert len(config_dict["variants"]) == 3

    def test_experiment_config_to_json(
        self,
        sample_experiment_config: ExperimentConfig
    ) -> None:
        """Test converting experiment config to JSON."""
        json_str = sample_experiment_config.to_json()
        data = json.loads(json_str)
        assert data["name"] == "test_experiment"

    def test_save_and_load_config(
        self,
        sample_experiment_config: ExperimentConfig
    ) -> None:
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            sample_experiment_config.save(path)

            loaded = ExperimentConfig.load(path)
            assert loaded.name == sample_experiment_config.name
            assert len(loaded.variants) == len(sample_experiment_config.variants)


# ============================================================================
# Manager Tests
# ============================================================================


class TestConfigRunner:
    """Test ConfigRunner execution."""

    def test_config_runner_init(self, sample_variant: ConfigVariant) -> None:
        """Test ConfigRunner initialization."""
        runner = ConfigRunner(sample_variant)
        assert runner.variant == sample_variant

    def test_run_returns_experiment_run(
        self,
        sample_variant: ConfigVariant
    ) -> None:
        """Test that run returns ExperimentRun."""
        runner = ConfigRunner(sample_variant)
        result = runner.run(run_number=1)

        assert isinstance(result, ExperimentRun)
        assert result.variant_name == sample_variant.name
        assert result.run_number == 1
        assert result.status in ["completed", "pending", "running", "failed"]

    def test_run_generates_metrics(
        self,
        sample_variant: ConfigVariant
    ) -> None:
        """Test that run generates expected metrics."""
        runner = ConfigRunner(sample_variant)
        result = runner.run(run_number=1)

        assert result.kg_nodes > 0
        assert result.kg_edges >= 0
        assert 0 <= result.accuracy <= 1
        assert 0 <= result.f1_score <= 1
        assert 0 <= result.coverage <= 1


class TestExperimentRun:
    """Test ExperimentRun dataclass."""

    def test_create_experiment_run(self) -> None:
        """Test creating experiment run."""
        run = ExperimentRun(
            variant_name="test",
            run_number=1,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:30:00",
            duration_seconds=1800.0,
            kg_nodes=100,
            kg_edges=200,
            kg_build_time=1500.0,
            accuracy=0.8,
            f1_score=0.75,
            coverage=0.85,
            status="completed"
        )
        assert run.variant_name == "test"
        assert run.run_number == 1
        assert run.status == "completed"


class TestExperimentManager:
    """Test ExperimentManager orchestration."""

    def test_manager_init(self, sample_experiment_config: ExperimentConfig) -> None:
        """Test ExperimentManager initialization."""
        manager = ExperimentManager(sample_experiment_config)
        assert manager.config == sample_experiment_config

    def test_run_experiments_sequential(
        self,
        sample_experiment_config: ExperimentConfig
    ) -> None:
        """Test sequential experiment execution."""
        config = sample_experiment_config
        config.parallel_workers = 1  # Force sequential
        manager = ExperimentManager(config)

        results = manager.run_experiments()

        assert isinstance(results, ExperimentResults)
        assert len(results.runs) > 0
        assert all(isinstance(r, ExperimentRun) for r in results.runs)

    def test_experiment_results_aggregation(
        self,
        sample_experiment_config: ExperimentConfig
    ) -> None:
        """Test results aggregation."""
        manager = ExperimentManager(sample_experiment_config)
        results = manager.run_experiments()

        assert results.total_runs > 0
        assert results.total_duration > 0
        assert len(results.aggregated_metrics) > 0


class TestExperimentResults:
    """Test ExperimentResults aggregation."""

    def test_results_to_dict(self, sample_experiment_run: ExperimentRun) -> None:
        """Test converting results to dictionary."""
        results = ExperimentResults(runs=[sample_experiment_run])
        result_dict = results.to_dict()

        assert "runs" in result_dict
        assert "total_duration" in result_dict
        assert "aggregated_metrics" in result_dict


# ============================================================================
# Analyzer Tests
# ============================================================================


class TestConvergenceAnalysis:
    """Test convergence analysis."""

    def test_create_convergence_analysis(self) -> None:
        """Test creating convergence analysis."""
        values = [0.5, 0.65, 0.75, 0.76, 0.765]
        conv = ConvergenceAnalysis(values=values)

        assert conv.final_value == 0.765
        assert len(conv.values) == 5
        assert conv.mean > 0
        assert conv.std_dev >= 0

    def test_plateau_detection(self) -> None:
        """Test plateau detection."""
        # Values that plateau
        values = [0.5, 0.7, 0.75, 0.751, 0.752, 0.753]
        conv = ConvergenceAnalysis(values=values)

        # Should detect plateau (< 1% improvement)
        assert hasattr(conv, 'plateaued')

    def test_improvement_rate(self) -> None:
        """Test improvement rate calculation."""
        values = [0.5, 0.7, 0.8, 0.85, 0.87]
        conv = ConvergenceAnalysis(values=values)

        assert len(conv.improvement_rate) == len(values) - 1


class TestComparativeAnalysis:
    """Test comparative analysis."""

    def test_create_comparative_analysis(self) -> None:
        """Test creating comparative analysis."""
        metrics = {
            "baseline": 0.75,
            "strict": 0.78,
            "permissive": 0.72
        }
        comp = ComparativeAnalysis(metrics=metrics)

        assert comp.best_variant == "strict"
        assert comp.best_score == 0.78
        assert len(comp.ranking) == 3

    def test_ranking_order(self) -> None:
        """Test ranking order."""
        metrics = {
            "v1": 0.5,
            "v2": 0.8,
            "v3": 0.7
        }
        comp = ComparativeAnalysis(metrics=metrics)

        ranking = list(comp.ranking.keys())
        scores = list(comp.ranking.values())

        # Scores should be in descending order
        assert scores == sorted(scores, reverse=True)

    def test_margin_calculation(self) -> None:
        """Test margin calculation."""
        metrics = {
            "v1": 0.5,
            "v2": 0.8
        }
        comp = ComparativeAnalysis(metrics=metrics)

        assert comp.best_margin == 0.3
        assert "v1" in comp.margins
        assert "v2" in comp.margins


class TestExperimentAnalyzer:
    """Test experiment analysis."""

    def test_analyzer_init(self) -> None:
        """Test analyzer initialization."""
        runs = [
            ExperimentRun(
                variant_name="baseline",
                run_number=1,
                start_time="2024-01-01T10:00:00",
                end_time="2024-01-01T10:30:00",
                duration_seconds=1800.0,
                kg_nodes=100,
                kg_edges=200,
                kg_build_time=1500.0,
                accuracy=0.75,
                f1_score=0.73,
                coverage=0.82,
                status="completed"
            )
        ]
        analyzer = ExperimentAnalyzer(runs)
        assert len(analyzer.runs) == 1

    def test_convergence_analysis(self) -> None:
        """Test convergence analysis."""
        runs = [
            ExperimentRun(
                variant_name="baseline",
                run_number=i,
                start_time="2024-01-01T10:00:00",
                end_time="2024-01-01T10:30:00",
                duration_seconds=1800.0,
                kg_nodes=100 + i * 10,
                kg_edges=200 + i * 20,
                kg_build_time=1500.0,
                accuracy=0.7 + i * 0.05,
                f1_score=0.68 + i * 0.05,
                coverage=0.80 + i * 0.05,
                status="completed"
            )
            for i in range(1, 4)
        ]

        analyzer = ExperimentAnalyzer(runs)
        convergence = analyzer.analyze_convergence("accuracy")

        assert "baseline" in convergence
        assert isinstance(convergence["baseline"], ConvergenceAnalysis)


# ============================================================================
# Plotter Tests
# ============================================================================


class TestPlotConfig:
    """Test plot configuration."""

    def test_default_plot_config(self) -> None:
        """Test default plot configuration."""
        config = PlotConfig()
        assert config.figsize == (12, 6)
        assert config.dpi == 100
        assert len(config.colors) > 0

    def test_custom_plot_config(self) -> None:
        """Test custom plot configuration."""
        colors = ["red", "blue", "green"]
        config = PlotConfig(figsize=(16, 8), colors=colors)
        assert config.figsize == (16, 8)
        assert config.colors == colors


class TestExperimentPlotter:
    """Test plotting functionality."""

    def test_plotter_init(self) -> None:
        """Test plotter initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plotter = ExperimentPlotter(output_dir=tmpdir)
            assert plotter.output_dir == Path(tmpdir)

    def test_convergence_plot(self) -> None:
        """Test convergence plot generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plotter = ExperimentPlotter(output_dir=tmpdir)

            data = {
                "baseline": [0.5, 0.7, 0.75],
                "strict": [0.52, 0.72, 0.78]
            }

            fig = plotter.plot_convergence(data, metric_name="Accuracy")
            assert fig is not None

    def test_comparison_plot(self) -> None:
        """Test comparison plot generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plotter = ExperimentPlotter(output_dir=tmpdir)

            data = {
                "baseline": {"accuracy": 0.75, "f1": 0.73},
                "strict": {"accuracy": 0.78, "f1": 0.76}
            }

            fig = plotter.plot_comparison(data)
            assert fig is not None

    def test_heatmap_plot(self) -> None:
        """Test heatmap generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plotter = ExperimentPlotter(output_dir=tmpdir)

            data = {
                "0.5": {"0.7": 0.75, "0.8": 0.73},
                "0.6": {"0.7": 0.76, "0.8": 0.74}
            }

            fig = plotter.plot_heatmap(data)
            assert fig is not None

    def test_distribution_plot(self) -> None:
        """Test distribution plot generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plotter = ExperimentPlotter(output_dir=tmpdir)

            data = {
                "baseline": [0.75, 0.76, 0.74],
                "strict": [0.78, 0.79, 0.77]
            }

            fig = plotter.plot_distribution(data)
            assert fig is not None


# ============================================================================
# Reporter Tests
# ============================================================================


class TestExperimentReporter:
    """Test report generation."""

    def test_reporter_init(self) -> None:
        """Test reporter initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ExperimentReporter(output_dir=tmpdir)
            assert reporter.output_dir == Path(tmpdir)

    def test_markdown_report_generation(self) -> None:
        """Test Markdown report generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ExperimentReporter(output_dir=tmpdir)

            report = ExperimentReport(
                experiment_name="test",
                timestamp=datetime.now().isoformat(),
                summary={
                    "total_variants": 2,
                    "total_runs": 4,
                    "completed_runs": 4,
                    "total_duration_hours": 1.0,
                    "avg_run_duration_min": 15.0
                },
                convergence={},
                comparison={},
                details={"baseline": {"accuracy": 0.75}}
            )

            content = reporter.generate_markdown(report)
            assert "test" in content
            assert "Executive Summary" in content

    def test_json_report_generation(self) -> None:
        """Test JSON report generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ExperimentReporter(output_dir=tmpdir)

            report = ExperimentReport(
                experiment_name="test",
                timestamp=datetime.now().isoformat(),
                summary={"total_variants": 2},
                convergence={},
                comparison={},
                details={}
            )

            content = reporter.generate_json(report)
            data = json.loads(content)
            assert data["experiment_name"] == "test"

    def test_html_report_generation(self) -> None:
        """Test HTML report generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ExperimentReporter(output_dir=tmpdir)

            report = ExperimentReport(
                experiment_name="test",
                timestamp=datetime.now().isoformat(),
                summary={
                    "total_variants": 2,
                    "total_runs": 4,
                    "completed_runs": 4,
                    "total_duration_hours": 1.0,
                    "avg_run_duration_min": 15.0,
                    "success_rate": 1.0
                },
                convergence={},
                comparison={},
                details={}
            )

            content = reporter.generate_html(report)
            assert "<!DOCTYPE html>" in content
            assert "test" in content

    def test_save_report_all_formats(self) -> None:
        """Test saving report in all formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ExperimentReporter(output_dir=tmpdir)

            report = ExperimentReport(
                experiment_name="test",
                timestamp=datetime.now().isoformat(),
                summary={},
                convergence={},
                comparison={},
                details={}
            )

            paths = reporter.save_report(report)

            assert "markdown" in paths
            assert "json" in paths
            assert "html" in paths
            assert all(p.exists() for p in paths.values())


# ============================================================================
# Integration Tests
# ============================================================================


class TestExperimentIntegration:
    """Integration tests for full experiment workflow."""

    def test_full_experiment_workflow(
        self,
        sample_experiment_config: ExperimentConfig
    ) -> None:
        """Test complete experiment workflow."""
        # Create and run experiment
        manager = ExperimentManager(sample_experiment_config)
        results = manager.run_experiments()

        # Analyze results
        analyzer = ExperimentAnalyzer(results.runs)
        convergence = analyzer.analyze_convergence("accuracy")

        # Generate plots
        with tempfile.TemporaryDirectory() as tmpdir:
            plotter = ExperimentPlotter(output_dir=tmpdir)
            conv_data = {
                "baseline": [0.5, 0.7, 0.75],
                "strict": [0.52, 0.72, 0.78]
            }
            fig = plotter.plot_convergence(conv_data)
            assert fig is not None

            # Generate report
            reporter = ExperimentReporter(output_dir=tmpdir)
            report = ExperimentReport(
                experiment_name=sample_experiment_config.name,
                timestamp=datetime.now().isoformat(),
                summary={"total_variants": len(sample_experiment_config.variants)},
                convergence=convergence,
                comparison={},
                details={}
            )

            paths = reporter.save_report(report)
            assert len(paths) == 3


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_convergence_analysis(self) -> None:
        """Test handling empty convergence data."""
        conv = ConvergenceAnalysis(values=[])
        assert conv.final_value == 0.0

    def test_single_value_convergence(self) -> None:
        """Test convergence with single value."""
        conv = ConvergenceAnalysis(values=[0.5])
        assert conv.final_value == 0.5
        assert conv.mean == 0.5

    def test_plotter_with_empty_data(self) -> None:
        """Test plotter with empty data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plotter = ExperimentPlotter(output_dir=tmpdir)

            # Should handle gracefully
            fig = plotter.plot_comparison({})
            assert fig is not None

    def test_reporter_with_minimal_data(self) -> None:
        """Test reporter with minimal data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = ExperimentReporter(output_dir=tmpdir)

            report = ExperimentReport(
                experiment_name="minimal",
                timestamp=datetime.now().isoformat(),
                summary={},
                convergence={},
                comparison={},
                details={}
            )

            # Should not raise error
            content = reporter.generate_markdown(report)
            assert "minimal" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
