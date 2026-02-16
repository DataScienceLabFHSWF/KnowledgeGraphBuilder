#!/usr/bin/env python3
"""
Run a single KG builder experiment with wandb logging using ConfigRunner.
This script wraps your chosen parameters into a ConfigVariant and executes one run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from kgbuilder.experiment.config import ConfigVariant, ExperimentConfig, KGBuilderParams
from kgbuilder.experiment.manager import ExperimentManager


def main() -> None:
    """Run KG build experiment(s) using ExperimentManager."""
    if len(sys.argv) < 2:
        print("Usage: python run_single_experiment.py <experiment_config.json>")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    with config_path.open() as f:
        config = json.load(f)

    # Support both single and multiple variants in config
    if "variants" in config:
        # Full experiment config
        experiment_config = ExperimentConfig.from_dict(config)
    else:
        # Single variant config, wrap in ExperimentConfig
        params = KGBuilderParams(**config)
        variant = ConfigVariant(
            name="single_run",
            description="Single KG build run from config file",
            params=params,
        )
        experiment_config = ExperimentConfig(
            name="single_experiment",
            variants=[variant],
            num_runs=1,
            output_dir="experiment_output"
        )

    manager = ExperimentManager(experiment_config)
    try:
        results = manager.run_experiments()
        print("[OK] Experiment(s) run complete. Check wandb and output directory for logs and artifacts.")
        print(f"Completed runs: {results.completed_runs}, Failed runs: {results.failed_runs}")
    except Exception as e:
        print(f"Experiment run failed: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
