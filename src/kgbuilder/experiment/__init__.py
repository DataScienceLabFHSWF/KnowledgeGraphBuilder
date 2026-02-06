"""Experiment framework for reproducible comparative analysis.

Enables running multiple KG configurations in parallel and comparing results.
Supports metrics collection, convergence analysis, and report generation.

Key Components:
- ExperimentConfig: Configuration definition with variants
- ConfigRunner: Single configuration execution
- ExperimentManager: Orchestrates multiple runs
- CheckpointManager: Saves/loads extraction results for reproducibility
- Analyzer: Metrics analysis and convergence tracking
- Reporter: Multi-format report generation
"""

from kgbuilder.experiment.analyzer import (
    ComparativeAnalysis,
    ConvergenceAnalysis,
    ExperimentAnalyzer,
)
from kgbuilder.experiment.checkpoint import (
    CheckpointManager,
    CheckpointMetadata,
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
    generate_run_id,
)
from kgbuilder.experiment.plotter import (
    ExperimentPlotter,
    PlotConfig,
)
from kgbuilder.experiment.reporter import (
    ExperimentReport,
    ExperimentReporter,
)

__all__ = [
    "KGBuilderParams",
    "ConfigVariant",
    "EvaluationConfig",
    "ExperimentConfig",
    "ExperimentRun",
    "ExperimentResults",
    "ConfigRunner",
    "ExperimentManager",
    "CheckpointManager",
    "CheckpointMetadata",
    "ConvergenceAnalysis",
    "ComparativeAnalysis",
    "ExperimentAnalyzer",
    "PlotConfig",
    "ExperimentPlotter",
    "ExperimentReport",
    "ExperimentReporter",
]

