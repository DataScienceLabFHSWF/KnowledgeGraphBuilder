"""Build pipeline orchestrator with validation and stopping criteria.

Orchestrates the complete KG building pipeline with integrated validation:

1. Document Processing & Extraction
2. KG Assembly
3. Validation (SHACL, Rules, Consistency)
4. Competency Question Answering
5. Stopping Criterion Check
6. Iteration or Completion

This enables intelligent iteration: build → validate → check CQs →
stop if quality gates pass, else iterate.

Usage:
    >>> pipeline = BuildPipeline(config)
    >>> result = pipeline.run(
    ...     documents=docs,
    ...     competency_questions=cqs,
    ...     stopping_criteria=StoppingCriteria(min_cq_coverage=0.95)
    ... )
    >>> print(result.stopping_reason)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from kgbuilder.pipeline.stopping_criterion import (
    CompetencyQuestionResults,
    KGBuildState,
    StoppingCriteria,
    StoppingCriterionChecker,
    StoppingReason,
    ValidationResults,
)

logger = structlog.get_logger(__name__)


@dataclass
class BuildPipelineConfig:
    """Configuration for build pipeline.

    Attributes:
        max_iterations: Maximum extraction iterations
        enable_validation: Run SHACL/rules/consistency checking
        enable_cq_checking: Check competency question answerability
        validate_at_each_iteration: Validate after each extraction round
        stopping_criteria: Stopping criterion configuration
    """

    max_iterations: int = 10
    enable_validation: bool = True
    enable_cq_checking: bool = True
    validate_at_each_iteration: bool = True
    stopping_criteria: StoppingCriteria | None = None


@dataclass
class IterationResult:
    """Result of a single pipeline iteration.

    Attributes:
        iteration_num: Iteration number (1-indexed)
        entities_extracted: Entities added this iteration
        relations_extracted: Relations added this iteration
        validation_result: Validation results (if run)
        cq_results: CQ checking results (if run)
        stopping_check: Stopping criterion results
        duration_ms: Iteration duration in milliseconds
        errors: Any errors encountered
    """

    iteration_num: int
    entities_extracted: int = 0
    relations_extracted: int = 0
    validation_result: dict[str, Any] | None = None
    cq_results: CompetencyQuestionResults | None = None
    stopping_check: dict[str, Any] | None = None
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class BuildPipelineResult:
    """Final result of build pipeline execution.

    Attributes:
        success: Whether pipeline completed successfully
        stopping_reason: Reason pipeline stopped
        total_iterations: Number of extraction iterations performed
        final_kg_state: Final state of KG (entities, relations, confidence)
        iterations: Results from each iteration
        validation_summary: Overall validation summary
        cq_summary: Overall CQ answering summary
        total_duration_ms: Total pipeline duration
        errors: Any errors encountered during pipeline
    """

    success: bool
    stopping_reason: StoppingReason
    total_iterations: int
    final_kg_state: KGBuildState
    iterations: list[IterationResult] = field(default_factory=list)
    validation_summary: ValidationResults | None = None
    cq_summary: CompetencyQuestionResults | None = None
    total_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def get_summary_string(self) -> str:
        """Get human-readable summary."""
        summary_lines = [
            f"Build Pipeline Result: {'[OK] SUCCESS' if self.success else '[FAIL] FAILED'}",
            f"Stopping Reason: {self.stopping_reason.value}",
            f"Iterations: {self.total_iterations}",
            f"Final Entity Count: {self.final_kg_state.entity_count}",
            f"Final Edge Count: {self.final_kg_state.edge_count}",
            f"Average Confidence: {round(self.final_kg_state.avg_confidence, 3)}",
            f"Duration: {self.total_duration_ms:.0f}ms ({self.total_duration_ms/1000:.1f}s)",
        ]

        if self.cq_summary:
            summary_lines.append(
                f"CQ Coverage: {self.cq_summary.coverage_percentage:.1f}% "
                f"({self.cq_summary.answerable_questions}/{self.cq_summary.total_questions})"
            )

        if self.validation_summary:
            summary_lines.append(
                f"Validation Pass Rate: {self.validation_summary.pass_rate:.1f}% "
                f"({self.validation_summary.passed_checks}/{self.validation_summary.total_checks})"
            )

        if self.errors:
            summary_lines.append(f"Errors: {len(self.errors)}")
            for error in self.errors[:3]:  # Show first 3
                summary_lines.append(f"  - {error}")

        return "\n".join(summary_lines)


class BuildPipeline:
    """Orchestrates KG building with validation and stopping criteria.

    Architecture:
    ```
    Input: Documents + Ontology + CQs
         ↓
    ┌────────────────────────────────────┐
    │ Iteration Loop                     │
    │                                    │
    │ 1. Extract Entities/Relations      │
    │ 2. Assemble to KG                  │
    │ 3. Validate (SHACL + Rules)        │
    │ 4. Check CQ Answerability          │
    │ 5. Check Stopping Criteria         │
    │    - If Pass: Stop [OK]               │
    │    - If Fail: Continue Loop        │
    │                                    │
    └────────────────────────────────────┘
         ↓
    Output: Complete KG + Validation Report
    ```

    Usage:
        >>> config = BuildPipelineConfig(enable_validation=True)
        >>> pipeline = BuildPipeline(config)
        >>> result = pipeline.run(docs=documents, cqs=cqs)
    """

    def __init__(self, config: BuildPipelineConfig) -> None:
        """Initialize build pipeline.

        Args:
            config: Pipeline configuration
        """
        if config.stopping_criteria is None:
            config.stopping_criteria = StoppingCriteria()
        config.stopping_criteria.validate()

        self.config = config
        self.checker = StoppingCriterionChecker(config.stopping_criteria)

        logger.info("pipeline_initialized", config=config)

    def run(
        self,
        documents: list[Any],
        competency_questions: list[dict[str, str]] | None = None,
        initial_kg_state: KGBuildState | None = None,
    ) -> BuildPipelineResult:
        """Run the complete build pipeline.

        Executes iterative KG building with validation and stopping criteria:
        1. Start with initial KG (or empty)
        2. Extract new entities/relations
        3. Validate extracted data
        4. Check competency questions
        5. Evaluate stopping criteria
        6. Stop if criteria met, else iterate

        Args:
            documents: List of documents to process
            competency_questions: Competency questions to validate
            initial_kg_state: Starting KG state (default: empty)

        Returns:
            BuildPipelineResult with final KG and stopping reason
        """
        import time

        start_time = time.time()

        logger.info(
            "pipeline_run_started",
            doc_count=len(documents),
            cq_count=len(competency_questions) if competency_questions else 0,
            max_iterations=self.config.max_iterations,
        )

        # Initialize KG state
        if initial_kg_state is None:
            initial_kg_state = KGBuildState()
        kg_state = initial_kg_state

        iterations: list[IterationResult] = []
        final_reason = StoppingReason.NOT_STOPPED
        validation_summary: ValidationResults | None = None
        cq_summary: CompetencyQuestionResults | None = None

        # Main iteration loop
        for iteration_num in range(1, self.config.max_iterations + 1):
            iter_start = time.time()
            iteration_result = IterationResult(iteration_num=iteration_num)

            try:
                logger.info(
                    "pipeline_iteration_started",
                    iteration=iteration_num,
                    current_entities=kg_state.entity_count,
                )

                # Step 1: Extract entities and relations
                # (This is where the extraction pipeline would be called)
                # For now, placeholder for integration point
                extraction_result = self._extraction_step(documents, iteration_num, kg_state)
                iteration_result.entities_extracted = extraction_result.get(
                    "entities_added", 0
                )
                iteration_result.relations_extracted = extraction_result.get(
                    "relations_added", 0
                )
                kg_state.entity_count += iteration_result.entities_extracted
                kg_state.edge_count += iteration_result.relations_extracted
                kg_state.avg_confidence = extraction_result.get("avg_confidence", 0.75)

                # Step 2: Validate if enabled
                if self.config.enable_validation:
                    validation_result = self._validation_step(kg_state, iteration_num)
                    iteration_result.validation_result = validation_result
                    validation_summary = ValidationResults(
                        total_checks=validation_result.get("total_checks", 0),
                        passed_checks=validation_result.get("passed_checks", 0),
                        pass_rate=validation_result.get("pass_rate", 100.0),
                        violations=validation_result.get("violations", 0),
                        conflicts=validation_result.get("conflicts", 0),
                    )

                # Step 3: Check competency questions if provided
                if self.config.enable_cq_checking and competency_questions:
                    cq_result = self._cq_checking_step(
                        kg_state, competency_questions, iteration_num
                    )
                    iteration_result.cq_results = cq_result
                    cq_summary = cq_result

                # Step 4: Check stopping criteria
                should_stop, reason, details = self.checker.check(
                    kg_state, cq_summary, validation_summary
                )
                iteration_result.stopping_check = details
                kg_state.iteration_count = iteration_num

                if should_stop:
                    final_reason = reason
                    logger.info(
                        "pipeline_stopping_criteria_met",
                        reason=reason.value,
                        iteration=iteration_num,
                    )
                    break

            except Exception as e:
                error_msg = f"Iteration {iteration_num} failed: {str(e)}"
                logger.error("pipeline_iteration_failed", error=error_msg, iteration=iteration_num)
                iteration_result.errors.append(error_msg)

            finally:
                iteration_result.duration_ms = (time.time() - iter_start) * 1000
                iterations.append(iteration_result)

        # Finalize result
        total_duration = time.time() - start_time
        success = final_reason != StoppingReason.NOT_STOPPED and final_reason != StoppingReason.ERROR_STOPPING

        result = BuildPipelineResult(
            success=success,
            stopping_reason=final_reason,
            total_iterations=len(iterations),
            final_kg_state=kg_state,
            iterations=iterations,
            validation_summary=validation_summary,
            cq_summary=cq_summary,
            total_duration_ms=total_duration * 1000,
        )

        logger.info(
            "pipeline_completed",
            success=success,
            reason=final_reason.value,
            iterations=len(iterations),
            entities=kg_state.entity_count,
            duration_sec=round(total_duration, 1),
        )

        return result

    def _extraction_step(
        self, documents: list[Any], iteration: int, kg_state: KGBuildState
    ) -> dict[str, Any]:
        """Execute extraction step (placeholder for integration).

        This is where the entity/relation extraction pipeline would be called.
        For now, returns mock data for demonstration.

        Args:
            documents: Documents to process
            iteration: Current iteration number
            kg_state: Current KG state

        Returns:
            Dict with extraction results
        """
        # Placeholder: In real implementation, would call extraction pipeline
        logger.debug("extraction_step", iteration=iteration, doc_count=len(documents))

        # Mock extraction for demonstration
        entities_added = 10 if iteration == 1 else 5
        relations_added = 8 if iteration == 1 else 3

        return {
            "entities_added": entities_added,
            "relations_added": relations_added,
            "avg_confidence": 0.75 + (iteration * 0.02),  # Increasing confidence
        }

    def _validation_step(self, kg_state: KGBuildState, iteration: int) -> dict[str, Any]:
        """Execute validation step (placeholder for integration).

        Would call SHACL validator, rules engine, and consistency checker.

        Args:
            kg_state: Current KG state
            iteration: Current iteration number

        Returns:
            Dict with validation results
        """
        logger.debug("validation_step", iteration=iteration, entities=kg_state.entity_count)

        # Mock validation for demonstration
        total_checks = kg_state.entity_count * 3
        passed_checks = int(total_checks * (0.90 + iteration * 0.01))  # Improving pass rate

        return {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "pass_rate": (passed_checks / total_checks * 100) if total_checks > 0 else 100,
            "violations": max(0, total_checks - passed_checks),
            "conflicts": max(0, int((total_checks - passed_checks) * 0.3)),
        }

    def _cq_checking_step(
        self,
        kg_state: KGBuildState,
        competency_questions: list[dict[str, str]],
        iteration: int,
    ) -> CompetencyQuestionResults:
        """Execute competency question checking step.

        Would execute each CQ SPARQL query against the KG and check answerability.

        Args:
            kg_state: Current KG state
            competency_questions: CQs to check
            iteration: Current iteration number

        Returns:
            CompetencyQuestionResults with coverage info
        """
        logger.debug("cq_checking_step", iteration=iteration, cq_count=len(competency_questions))

        # Mock CQ checking for demonstration
        total_cqs = len(competency_questions)
        answerable = min(total_cqs, 2 + iteration * 2)  # Increasing coverage
        coverage = (answerable / total_cqs * 100) if total_cqs > 0 else 0

        return CompetencyQuestionResults(
            total_questions=total_cqs,
            answerable_questions=answerable,
            coverage_percentage=coverage,
            unanswerable=[f"CQ-{i}" for i in range(total_cqs - answerable)],
            details={f"CQ-{i}": {"answerable": i < answerable} for i in range(total_cqs)},
        )

    def get_checker_summary(self) -> str:
        """Get summary of stopping criteria checks.

        Returns:
            Human-readable summary from last check
        """
        return self.checker.get_summary()
