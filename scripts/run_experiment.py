#!/usr/bin/env python
"""Run KG builder experiment framework.

Executes configured experiments, generates analysis, visualizations,
and reports comparing different KG builder configurations.

Usage:
    python run_experiment.py --config config.json --output results/
    python run_experiment.py --config config.yaml --workers 4
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Any

import structlog

from kgbuilder.experiment import (
    ExperimentAnalyzer,
    ExperimentConfig,
    ExperimentManager,
    ExperimentPlotter,
    ExperimentReporter,
    ExperimentReport,
    PlotConfig,
)

# Setup logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run KG builder experiment framework"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to experiment configuration file (JSON/YAML)"
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiment_results"),
        help="Output directory for results and reports"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers"
    )
    
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip visualization generation"
    )
    
    parser.add_argument(
        "--no-reports",
        action="store_true",
        help="Skip report generation"
    )
    
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["markdown", "json", "html"],
        choices=["markdown", "json", "html"],
        help="Report formats to generate"
    )
    
    return parser.parse_args()


def load_config(config_path: Path) -> ExperimentConfig:
    """Load experiment configuration from file.
    
    Args:
        config_path: Path to configuration file.
    
    Returns:
        Loaded experiment configuration.
    
    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config format is invalid.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    logger.info("loading_config", path=str(config_path))
    
    try:
        config = ExperimentConfig.load(config_path)
        logger.info("config_loaded", name=config.name, variants=len(config.variants))
        return config
    except Exception as e:
        logger.error("config_load_failed", error=str(e))
        raise


def run_experiments(
    config: ExperimentConfig,
    workers: int | None = None
) -> Any:
    """Run experiments with given configuration.
    
    Args:
        config: Experiment configuration.
        workers: Number of parallel workers. If None, uses config default.
    
    Returns:
        Experiment results.
    """
    if workers:
        config.parallel_workers = workers
    
    logger.info("starting_experiments", name=config.name, variants=len(config.variants))
    
    manager = ExperimentManager(config)
    results = manager.run_experiments()
    
    logger.info(
        "experiments_completed",
        total_runs=results.total_runs,
        duration_hours=results.total_duration / 3600.0
    )
    
    return results


def analyze_results(results: Any) -> dict[str, Any]:
    """Analyze experiment results.
    
    Args:
        results: Experiment results from manager.
    
    Returns:
        Analysis results including convergence and comparison.
    """
    logger.info("analyzing_results", runs=len(results.runs))
    
    analyzer = ExperimentAnalyzer(results.runs)
    
    # Extract metrics to analyze
    metrics = set()
    for run in results.runs:
        if run.accuracy is not None:
            metrics.add("accuracy")
        if run.f1_score is not None:
            metrics.add("f1_score")
        if run.coverage is not None:
            metrics.add("coverage")
    
    # Perform analysis
    convergence = {}
    comparison = {}
    
    for metric in metrics:
        logger.debug("analyzing_metric", metric=metric)
        convergence[metric] = analyzer.analyze_convergence(metric)
        comparison[metric] = analyzer.compare_variants(metric)
    
    logger.info("analysis_complete", metrics=list(metrics))
    
    return {
        "convergence": convergence,
        "comparison": comparison,
        "aggregate": analyzer.get_summary()
    }


def generate_visualizations(
    results: Any,
    analysis: dict[str, Any],
    output_dir: Path
) -> dict[str, Path]:
    """Generate visualization plots.
    
    Args:
        results: Experiment results.
        analysis: Analysis results.
        output_dir: Output directory for plots.
    
    Returns:
        Dictionary mapping plot names to file paths.
    """
    logger.info("generating_visualizations", output_dir=str(output_dir))
    
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    
    plotter = ExperimentPlotter(
        output_dir=plot_dir,
        config=PlotConfig(figsize=(12, 6), dpi=100)
    )
    
    viz_paths = {}
    
    # Generate convergence plots
    for metric, conv_data in analysis["convergence"].items():
        convergence_dict = {
            variant: conv.values
            for variant, conv in conv_data.items()
        }
        
        fig = plotter.plot_convergence(
            convergence_dict,
            metric_name=metric.replace("_", " ").title()
        )
        
        save_path = plot_dir / f"convergence_{metric}.png"
        fig.savefig(save_path, dpi=100, bbox_inches="tight")
        viz_paths[f"convergence_{metric}"] = str(save_path)
        logger.debug("convergence_plot_saved", metric=metric)
    
    # Generate comparison plots
    for metric, comp in analysis["comparison"].items():
        metrics_dict = {
            variant: {metric: score}
            for variant, score in comp.ranking.items()
        }
        
        fig = plotter.plot_comparison(metrics_dict)
        save_path = plot_dir / f"comparison_{metric}.png"
        fig.savefig(save_path, dpi=100, bbox_inches="tight")
        viz_paths[f"comparison_{metric}"] = str(save_path)
        logger.debug("comparison_plot_saved", metric=metric)
    
    logger.info("visualizations_complete", count=len(viz_paths))
    
    return viz_paths


def generate_reports(
    config: ExperimentConfig,
    results: Any,
    analysis: dict[str, Any],
    viz_paths: dict[str, Path],
    output_dir: Path,
    formats: list[str]
) -> dict[str, Path]:
    """Generate experiment reports.
    
    Args:
        config: Experiment configuration.
        results: Experiment results.
        analysis: Analysis results.
        viz_paths: Visualization file paths.
        output_dir: Output directory for reports.
        formats: Report formats to generate.
    
    Returns:
        Dictionary mapping format to report file path.
    """
    logger.info("generating_reports", formats=formats)
    
    report_dir = output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    reporter = ExperimentReporter(output_dir=report_dir)
    
    # Create report object
    report = ExperimentReport(
        experiment_name=config.name,
        timestamp=datetime.now().isoformat(),
        summary={
            "total_variants": len(config.variants),
            "total_runs": len(results.runs),
            "completed_runs": sum(1 for r in results.runs if r.status == "completed"),
            "total_duration_hours": results.total_duration / 3600.0,
            "avg_run_duration_min": results.total_duration / len(results.runs) / 60.0 if results.runs else 0,
            "success_rate": sum(1 for r in results.runs if r.status == "completed") / len(results.runs) if results.runs else 0,
        },
        convergence=analysis.get("convergence", {}),
        comparison=analysis.get("comparison", {}),
        details=results.aggregated_metrics,
        visualizations=viz_paths
    )
    
    # Save reports
    paths = reporter.save_report(report, formats=formats)
    
    logger.info("reports_saved", count=len(paths))
    
    return paths


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()
        
        # Create output directory
        args.output.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        config = load_config(args.config)
        
        # Run experiments
        results = run_experiments(config, workers=args.workers)
        
        # Analyze results
        analysis = analyze_results(results)
        
        # Generate visualizations
        viz_paths = {}
        if not args.no_plots:
            viz_paths = generate_visualizations(results, analysis, args.output)
        
        # Generate reports
        report_paths = {}
        if not args.no_reports:
            report_paths = generate_reports(
                config,
                results,
                analysis,
                viz_paths,
                args.output,
                args.formats
            )
        
        logger.info(
            "experiment_complete",
            output_dir=str(args.output),
            reports=len(report_paths),
            plots=len(viz_paths)
        )
        
        # Print summary
        print("\n" + "=" * 80)
        print("EXPERIMENT COMPLETE")
        print("=" * 80)
        print(f"Output Directory: {args.output}")
        print(f"Total Runs: {len(results.runs)}")
        print(f"Total Duration: {results.total_duration / 3600.0:.2f}h")
        
        if report_paths:
            print(f"\nReports Generated:")
            for fmt, path in report_paths.items():
                print(f"  - {fmt.upper()}: {path}")
        
        if viz_paths:
            print(f"\nVisualizations Generated: {len(viz_paths)}")
        
        print("=" * 80 + "\n")
        
        return 0
    
    except Exception as e:
        logger.error("experiment_failed", error=str(e), exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
