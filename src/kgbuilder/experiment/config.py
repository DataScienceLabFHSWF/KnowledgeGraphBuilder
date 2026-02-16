"""Experiment configuration for comparative analysis.

Defines configuration structures for running multiple KG construction
experiments with different parameters and comparing results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class KGBuilderParams:
    """KG builder hyperparameters for a single experiment variant.

    Attributes:
        model: LLM model name (e.g., "qwen3:8b")
        max_iterations: Maximum iterations for discovery loop
        similarity_threshold: Entity deduplication threshold (0-1)
        confidence_threshold: Minimum extraction confidence (0-1)
        classes_limit: Limit classes to process (None = all)
        questions_per_class: Number of questions to generate per class
    """

    model: str = "qwen3:8b"
    max_iterations: int = 2
    similarity_threshold: float = 0.85
    confidence_threshold: float = 0.6
    classes_limit: int | None = None
    questions_per_class: int = 3

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model": self.model,
            "max_iterations": self.max_iterations,
            "similarity_threshold": self.similarity_threshold,
            "confidence_threshold": self.confidence_threshold,
            "classes_limit": self.classes_limit,
            "questions_per_class": self.questions_per_class,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> KGBuilderParams:
        """Create from dictionary."""
        return KGBuilderParams(
            model=data.get("model", "qwen3:8b"),
            max_iterations=data.get("max_iterations", 2),
            similarity_threshold=data.get("similarity_threshold", 0.85),
            confidence_threshold=data.get("confidence_threshold", 0.6),
            classes_limit=data.get("classes_limit"),
            questions_per_class=data.get("questions_per_class", 3),
        )


@dataclass
class ConfigVariant:
    """Single experiment variant with a configuration.

    Represents one KG construction configuration to run and evaluate.

    Attributes:
        name: Variant name (e.g., "baseline", "strict", "permissive")
        description: Human-readable description
        params: KG builder parameters for this variant
        metadata: Additional metadata
    """

    name: str
    description: str
    params: KGBuilderParams = field(default_factory=KGBuilderParams)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "params": self.params.to_dict(),
            "metadata": self.metadata,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ConfigVariant:
        """Create from dictionary."""
        params = KGBuilderParams.from_dict(data.get("params", {}))
        return ConfigVariant(
            name=data["name"],
            description=data.get("description", ""),
            params=params,
            metadata=data.get("metadata", {}),
        )


@dataclass
class EvaluationConfig:
    """QA evaluation configuration for experiments.

    Attributes:
        qa_dataset_path: Path to QA dataset JSON file
        metrics: Metrics to compute
        similarity_threshold: Answer similarity threshold for correctness
        max_results: Maximum results to evaluate per question
    """

    qa_dataset_path: str
    metrics: list[str] = field(
        default_factory=lambda: ["accuracy", "f1_score", "coverage", "completeness"]
    )
    similarity_threshold: float = 0.8
    max_results: int = 10

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "qa_dataset_path": self.qa_dataset_path,
            "metrics": self.metrics,
            "similarity_threshold": self.similarity_threshold,
            "max_results": self.max_results,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> EvaluationConfig:
        """Create from dictionary."""
        return EvaluationConfig(
            qa_dataset_path=data["qa_dataset_path"],
            metrics=data.get(
                "metrics",
                ["accuracy", "f1_score", "coverage", "completeness"],
            ),
            similarity_threshold=data.get("similarity_threshold", 0.8),
            max_results=data.get("max_results", 10),
        )


@dataclass
class ExperimentConfig:
    """Complete experiment configuration.

    Represents a full experiment specification with multiple variants
    and evaluation settings.

    Attributes:
        name: Experiment name
        description: Experiment description
        output_dir: Directory for experiment results
        variants: List of ConfigVariant to run
        evaluation: Evaluation configuration
        num_runs: Number of runs per variant
        parallel_jobs: Number of parallel jobs
        seed: Random seed for reproducibility
        metadata: Additional metadata
    """

    name: str
    description: str
    output_dir: str
    variants: list[ConfigVariant]
    evaluation: EvaluationConfig
    num_runs: int = 1
    parallel_jobs: int = 1
    seed: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "output_dir": self.output_dir,
            "num_runs": self.num_runs,
            "parallel_jobs": self.parallel_jobs,
            "seed": self.seed,
            "variants": [v.to_dict() for v in self.variants],
            "evaluation": self.evaluation.to_dict(),
            "metadata": self.metadata,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ExperimentConfig:
        """Create from dictionary."""
        variants = [
            ConfigVariant.from_dict(v) for v in data.get("variants", [])
        ]
        eval_config = EvaluationConfig.from_dict(
            data.get("evaluation", {"qa_dataset_path": ""})
        )

        return ExperimentConfig(
            name=data["name"],
            description=data.get("description", ""),
            output_dir=data["output_dir"],
            variants=variants,
            evaluation=eval_config,
            num_runs=data.get("num_runs", 1),
            parallel_jobs=data.get("parallel_jobs", 1),
            seed=data.get("seed"),
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def from_json(filepath: str | Path) -> ExperimentConfig:
        """Load from JSON file.

        Args:
            filepath: Path to JSON configuration file

        Returns:
            ExperimentConfig

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is invalid
        """
        filepath = Path(filepath)

        with open(filepath) as f:
            data = json.load(f)

        logger.info("experiment_config_loaded", filepath=str(filepath))
        return ExperimentConfig.from_dict(data)

    @staticmethod
    def from_yaml(filepath: str | Path) -> ExperimentConfig:
        """Load from YAML file.

        Args:
            filepath: Path to YAML configuration file

        Returns:
            ExperimentConfig

        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML is invalid
            ImportError: If PyYAML not installed
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required for YAML loading: pip install pyyaml")

        filepath = Path(filepath)

        with open(filepath) as f:
            data = yaml.safe_load(f)

        logger.info("experiment_config_loaded", filepath=str(filepath))
        return ExperimentConfig.from_dict(data)

    def save_json(self, filepath: str | Path) -> None:
        """Save to JSON file.

        Args:
            filepath: Path to save JSON configuration
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info("experiment_config_saved", filepath=str(filepath))

    def save_yaml(self, filepath: str | Path) -> None:
        """Save to YAML file.

        Args:
            filepath: Path to save YAML configuration

        Raises:
            ImportError: If PyYAML not installed
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required for YAML saving: pip install pyyaml")

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

        logger.info("experiment_config_saved", filepath=str(filepath))

    def get_output_dir(self) -> Path:
        """Get output directory, creating if needed.

        Returns:
            Path to output directory
        """
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path

    def get_variant_output_dir(self, variant_name: str) -> Path:
        """Get output directory for a specific variant.

        Args:
            variant_name: Name of variant

        Returns:
            Path to variant output directory
        """
        variant_dir = self.get_output_dir() / variant_name
        variant_dir.mkdir(parents=True, exist_ok=True)
        return variant_dir

    def validate(self) -> bool:
        """Validate configuration.

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.variants:
            raise ValueError("No variants defined")

        if self.num_runs < 1:
            raise ValueError("num_runs must be >= 1")

        if self.parallel_jobs < 1:
            raise ValueError("parallel_jobs must be >= 1")

        if not Path(self.evaluation.qa_dataset_path).exists():
            logger.warning(
                "qa_dataset_not_found",
                path=self.evaluation.qa_dataset_path,
            )

        logger.info(
            "experiment_config_validated",
            num_variants=len(self.variants),
            num_runs=self.num_runs,
        )

        return True
