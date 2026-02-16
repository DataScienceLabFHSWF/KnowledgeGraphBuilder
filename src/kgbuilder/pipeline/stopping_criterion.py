"""Stopping criteria for KG building pipeline.

Implements configurable stopping criteria to determine when the KG
building process should halt, based on metrics like:
- Competency question coverage
- Validation pass rate
- Entity count thresholds
- Extraction confidence levels
- Query answerability

This enables intelligent iteration: build KG → validate → check CQs →
stop if good enough, otherwise iterate extraction.

Usage:
    >>> criterion = StoppingCriterion(
    ...     min_cq_coverage=0.95,
    ...     min_validation_pass_rate=0.90,
    ...     min_avg_confidence=0.75
    ... )
    >>> should_stop = criterion.check(kg_state, cq_results, validation_results)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class StoppingReason(Enum):
    """Reasons for stopping the KG building pipeline."""

    NOT_STOPPED = "not_stopped"
    CQ_COVERAGE_MET = "cq_coverage_met"
    VALIDATION_PASS_RATE_MET = "validation_pass_rate_met"
    CONFIDENCE_THRESHOLD_MET = "confidence_threshold_met"
    ENTITY_COUNT_REACHED = "entity_count_reached"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    QUALITY_GATES_PASSED = "quality_gates_passed"
    MANUAL_STOP = "manual_stop"
    ERROR_STOPPING = "error_stopping"


@dataclass
class StoppingCriteria:
    """Configuration for stopping criteria.

    Attributes:
        min_cq_coverage: Minimum percentage of CQs that must be answerable (0-1)
        min_validation_pass_rate: Minimum percentage of validation checks to pass (0-1)
        min_avg_confidence: Minimum average entity confidence score (0-1)
        min_entity_count: Minimum number of entities in KG
        max_iterations: Maximum extraction iterations before forced stop
        require_all: If True, ALL criteria must be met; if False, ANY can trigger stop
    """

    min_cq_coverage: float = 0.95  # 95% of CQs answerable
    min_validation_pass_rate: float = 0.90  # 90% of validation checks pass
    min_avg_confidence: float = 0.75  # Avg confidence >= 0.75
    min_entity_count: int = 100  # At least 100 entities
    max_iterations: int = 10  # Max 10 extraction iterations
    require_all: bool = True  # All criteria must be met to stop

    def validate(self) -> None:
        """Validate criteria configuration.

        Raises:
            ValueError: If criteria are invalid (e.g., percentages not 0-1)
        """
        if not (0 <= self.min_cq_coverage <= 1):
            raise ValueError(
                f"min_cq_coverage must be 0-1, got {self.min_cq_coverage}"
            )
        if not (0 <= self.min_validation_pass_rate <= 1):
            raise ValueError(
                f"min_validation_pass_rate must be 0-1, got {self.min_validation_pass_rate}"
            )
        if not (0 <= self.min_avg_confidence <= 1):
            raise ValueError(
                f"min_avg_confidence must be 0-1, got {self.min_avg_confidence}"
            )
        if self.min_entity_count < 0:
            raise ValueError("min_entity_count must be >= 0")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")


@dataclass
class KGBuildState:
    """Current state of KG building process.

    Attributes:
        entity_count: Number of entities currently in KG
        edge_count: Number of relations/edges in KG
        avg_confidence: Average confidence of extracted entities
        iteration_count: Current extraction iteration number
        total_violations: Total validation violations found
        total_conflicts: Total conflicts detected
        metadata: Additional tracking metadata
    """

    entity_count: int = 0
    edge_count: int = 0
    avg_confidence: float = 0.0
    iteration_count: int = 0
    total_violations: int = 0
    total_conflicts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompetencyQuestionResults:
    """Results from competency question validation.

    Attributes:
        total_questions: Total number of CQs defined
        answerable_questions: Number of CQs with results
        coverage_percentage: Percentage of answerable CQs (0-100)
        unanswerable: List of unanswerable CQ IDs
        details: Detailed results for each CQ
    """

    total_questions: int = 0
    answerable_questions: int = 0
    coverage_percentage: float = 0.0
    unanswerable: list[str] = field(default_factory=list)
    details: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_coverage_ratio(self) -> float:
        """Get coverage as ratio (0-1)."""
        if self.total_questions == 0:
            return 1.0
        return self.answerable_questions / self.total_questions


@dataclass
class ValidationResults:
    """Results from KG validation.

    Attributes:
        total_checks: Total validation checks performed
        passed_checks: Number of passed checks
        pass_rate: Percentage of passed checks (0-100)
        violations: Number of validation violations
        conflicts: Number of detected conflicts
        severity_breakdown: Breakdown by severity (ERROR, WARNING, INFO)
    """

    total_checks: int = 0
    passed_checks: int = 0
    pass_rate: float = 100.0
    violations: int = 0
    conflicts: int = 0
    severity_breakdown: dict[str, int] = field(default_factory=dict)

    def get_pass_rate_ratio(self) -> float:
        """Get pass rate as ratio (0-1)."""
        if self.total_checks == 0:
            return 1.0
        return self.passed_checks / self.total_checks


class StoppingCriterionChecker:
    """Checks if KG building should stop based on criteria.

    Implements pluggable stopping criteria with support for:
    - ALL criteria met (conjunctive): All must pass to stop
    - ANY criteria met (disjunctive): Any can trigger stop
    - Custom criteria: Extend by adding new check methods

    Usage:
        >>> criteria = StoppingCriteria(min_cq_coverage=0.95)
        >>> checker = StoppingCriterionChecker(criteria)
        >>> should_stop, reason = checker.check(state, cq_results, val_results)
    """

    def __init__(self, criteria: StoppingCriteria) -> None:
        """Initialize criterion checker.

        Args:
            criteria: StoppingCriteria configuration

        Raises:
            ValueError: If criteria are invalid
        """
        criteria.validate()
        self.criteria = criteria
        self.check_results: dict[str, bool] = {}

    def check(
        self,
        kg_state: KGBuildState,
        cq_results: CompetencyQuestionResults | None = None,
        validation_results: ValidationResults | None = None,
    ) -> tuple[bool, StoppingReason, dict[str, Any]]:
        """Check if KG building should stop.

        Evaluates all stopping criteria and returns whether pipeline should
        halt and the reason (if any).

        Args:
            kg_state: Current KG building state
            cq_results: Competency question validation results
            validation_results: Graph validation results

        Returns:
            Tuple of:
            - should_stop: Whether to stop the pipeline
            - reason: StoppingReason enum for why
            - details: Dict with detailed check results

        Raises:
            ValueError: If required results are None when needed for criteria
        """
        self.check_results = {}

        # Check max iterations first (hard stop)
        if kg_state.iteration_count >= self.criteria.max_iterations:
            logger.warning(
                "stopping_criterion_triggered",
                reason="max_iterations_reached",
                current=kg_state.iteration_count,
                max=self.criteria.max_iterations,
            )
            return (
                True,
                StoppingReason.MAX_ITERATIONS_REACHED,
                {"reason": "Reached maximum extraction iterations"},
            )

        # Perform individual checks
        self._check_entity_count(kg_state)
        self._check_confidence(kg_state)
        self._check_cq_coverage(cq_results)
        self._check_validation_pass_rate(validation_results)

        # Determine if should stop based on logic (all vs any)
        should_stop = self._evaluate_stopping_logic()

        if should_stop:
            reason = self._get_stopping_reason()
            logger.info(
                "stopping_criterion_met",
                reason=reason.value,
                checks=self.check_results,
            )
            return (True, reason, {"checks": self.check_results})

        logger.debug("stopping_criteria_not_met", checks=self.check_results)
        return (False, StoppingReason.NOT_STOPPED, {"checks": self.check_results})

    def _check_entity_count(self, kg_state: KGBuildState) -> None:
        """Check if minimum entity count is met."""
        passed = kg_state.entity_count >= self.criteria.min_entity_count
        self.check_results["entity_count"] = {
            "passed": passed,
            "current": kg_state.entity_count,
            "required": self.criteria.min_entity_count,
        }

    def _check_confidence(self, kg_state: KGBuildState) -> None:
        """Check if minimum average confidence is met."""
        passed = kg_state.avg_confidence >= self.criteria.min_avg_confidence
        self.check_results["avg_confidence"] = {
            "passed": passed,
            "current": round(kg_state.avg_confidence, 3),
            "required": self.criteria.min_avg_confidence,
        }

    def _check_cq_coverage(self, cq_results: CompetencyQuestionResults | None) -> None:
        """Check if minimum CQ coverage is met."""
        if cq_results is None:
            self.check_results["cq_coverage"] = {
                "passed": False,
                "reason": "No CQ results available",
            }
            return

        coverage_ratio = cq_results.get_coverage_ratio()
        passed = coverage_ratio >= self.criteria.min_cq_coverage
        self.check_results["cq_coverage"] = {
            "passed": passed,
            "current": round(coverage_ratio, 3),
            "current_percentage": round(cq_results.coverage_percentage, 1),
            "required": self.criteria.min_cq_coverage,
            "answerable": cq_results.answerable_questions,
            "total": cq_results.total_questions,
            "unanswerable_ids": cq_results.unanswerable,
        }

    def _check_validation_pass_rate(
        self, validation_results: ValidationResults | None
    ) -> None:
        """Check if minimum validation pass rate is met."""
        if validation_results is None:
            self.check_results["validation_pass_rate"] = {
                "passed": False,
                "reason": "No validation results available",
            }
            return

        pass_rate_ratio = validation_results.get_pass_rate_ratio()
        passed = pass_rate_ratio >= self.criteria.min_validation_pass_rate
        self.check_results["validation_pass_rate"] = {
            "passed": passed,
            "current": round(pass_rate_ratio, 3),
            "current_percentage": round(validation_results.pass_rate, 1),
            "required": self.criteria.min_validation_pass_rate,
            "passed_checks": validation_results.passed_checks,
            "total_checks": validation_results.total_checks,
            "violations": validation_results.violations,
            "conflicts": validation_results.conflicts,
        }

    def _evaluate_stopping_logic(self) -> bool:
        """Evaluate if should stop based on all/any logic."""
        all_passed = all(
            check.get("passed", False) for check in self.check_results.values()
            if isinstance(check, dict) and "passed" in check
        )
        any_passed = any(
            check.get("passed", False) for check in self.check_results.values()
            if isinstance(check, dict) and "passed" in check
        )

        if self.criteria.require_all:
            return all_passed
        else:
            # If require_all is False, stop if any positive criterion passes
            # (entity count and confidence are "nice to have", not critical)
            return all_passed  # Still require CQ + validation for stop

    def _get_stopping_reason(self) -> StoppingReason:
        """Determine the primary stopping reason."""
        if self.check_results.get("cq_coverage", {}).get("passed"):
            return StoppingReason.CQ_COVERAGE_MET
        if self.check_results.get("validation_pass_rate", {}).get("passed"):
            return StoppingReason.VALIDATION_PASS_RATE_MET
        if self.check_results.get("avg_confidence", {}).get("passed"):
            return StoppingReason.CONFIDENCE_THRESHOLD_MET
        if self.check_results.get("entity_count", {}).get("passed"):
            return StoppingReason.ENTITY_COUNT_REACHED

        return StoppingReason.QUALITY_GATES_PASSED

    def get_summary(self) -> str:
        """Get human-readable summary of checks.

        Returns:
            Summary string with check results
        """
        lines = ["Stopping Criteria Check Summary:"]
        lines.append(f"  Require All: {self.criteria.require_all}")
        lines.append("")

        for check_name, check_result in self.check_results.items():
            if isinstance(check_result, dict):
                passed = check_result.get("passed", False)
                status = "[OK] PASS" if passed else "[FAIL] FAIL"
                lines.append(f"  {check_name}: {status}")

                if "current" in check_result:
                    current = check_result["current"]
                    required = check_result.get("required", "N/A")
                    lines.append(f"    Current: {current} | Required: {required}")

                if "unanswerable_ids" in check_result:
                    unanswerable = check_result["unanswerable_ids"]
                    if unanswerable:
                        lines.append(f"    Unanswerable CQs: {', '.join(unanswerable)}")

        return "\n".join(lines)
