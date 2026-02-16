"""Pipeline orchestration and control.

Provides high-level pipeline orchestration for the KG building process,
including validation integration and intelligent stopping criteria based on
quality metrics and competency question answering.

Phase 8.5 Feature: Build Pipeline Controller with Stopping Criteria
See Planning/PHASE_8_PLAN.md Task 8.5 for specifications.

Public API:
    - BuildPipeline: Main pipeline orchestrator
    - BuildPipelineConfig: Pipeline configuration
    - BuildPipelineResult: Pipeline execution results
    - StoppingCriteria: Stopping criterion configuration
    - StoppingCriterionChecker: Criterion evaluation
    - KGBuildState: Current KG state tracking
    - CompetencyQuestionResults: CQ validation results
    - ValidationResults: Graph validation results
"""

from kgbuilder.pipeline.orchestrator import (
    BuildPipeline,
    BuildPipelineConfig,
    BuildPipelineResult,
    IterationResult,
)
from kgbuilder.pipeline.stopping_criterion import (
    CompetencyQuestionResults,
    KGBuildState,
    StoppingCriteria,
    StoppingCriterionChecker,
    StoppingReason,
    ValidationResults,
)

__all__ = [
    "BuildPipeline",
    "BuildPipelineConfig",
    "BuildPipelineResult",
    "IterationResult",
    "StoppingCriteria",
    "StoppingCriterionChecker",
    "StoppingReason",
    "KGBuildState",
    "CompetencyQuestionResults",
    "ValidationResults",
]
