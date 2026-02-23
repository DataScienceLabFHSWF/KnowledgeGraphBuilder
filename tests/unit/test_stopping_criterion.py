"""Tests for pipeline stopping criteria logic."""

from __future__ import annotations

import pytest

from kgbuilder.pipeline.stopping_criterion import (
    StoppingCriteria,
    KGBuildState,
    CompetencyQuestionResults,
    ValidationResults,
    StoppingCriterionChecker,
    StoppingReason,
)


def test_criteria_validation_errors():
    with pytest.raises(ValueError):
        StoppingCriteria(min_cq_coverage=1.5).validate()
    with pytest.raises(ValueError):
        StoppingCriteria(min_validation_pass_rate=-0.1).validate()
    with pytest.raises(ValueError):
        StoppingCriteria(min_avg_confidence=2.0).validate()
    with pytest.raises(ValueError):
        StoppingCriteria(min_entity_count=-1).validate()
    with pytest.raises(ValueError):
        StoppingCriteria(max_iterations=0).validate()


def make_state(count=0, avg=0.0, iter_count=0):
    return KGBuildState(entity_count=count, avg_confidence=avg, iteration_count=iter_count)


def make_cq(total=0, answerable=0):
    return CompetencyQuestionResults(
        total_questions=total,
        answerable_questions=answerable,
        coverage_percentage=(answerable / total * 100 if total else 0),
    )


def make_val(total=0, passed=0):
    return ValidationResults(
        total_checks=total,
        passed_checks=passed,
        pass_rate=(passed / total * 100 if total else 100),
    )


def test_check_entity_count_trigger():
    # entity count alone does not trigger stop because other checks are
    # evaluated and must all pass.
    crit = StoppingCriteria(min_entity_count=5)
    chk = StoppingCriterionChecker(crit)
    state = make_state(count=6)
    stop, reason, details = chk.check(state, None, None)
    assert not stop
    assert reason == StoppingReason.NOT_STOPPED
    assert details["checks"]["entity_count"]["passed"]


def test_check_confidence_trigger():
    crit = StoppingCriteria(min_avg_confidence=0.7, require_all=False)
    chk = StoppingCriterionChecker(crit)
    state = make_state(count=0, avg=0.8)
    stop, reason, details = chk.check(state)
    # confidence alone doesn't stop pipeline (other checks still false)
    assert not stop
    assert reason == StoppingReason.NOT_STOPPED


def test_cq_and_validation_logic():
    # with default entity/confidence thresholds, leaving them unmet prevents stop
    crit = StoppingCriteria(min_cq_coverage=0.5, min_validation_pass_rate=0.5, require_all=True)
    chk = StoppingCriterionChecker(crit)
    state = make_state()
    cq = make_cq(total=4, answerable=2)
    val = make_val(total=10, passed=6)
    stop, reason, _ = chk.check(state, cq, val)
    assert not stop
    assert reason == StoppingReason.NOT_STOPPED


def test_cq_validation_with_relaxed_other_thresholds():
    # lower other thresholds to zero so only cq/validation matter
    crit = StoppingCriteria(
        min_cq_coverage=0.5,
        min_validation_pass_rate=0.5,
        min_avg_confidence=0.0,
        min_entity_count=0,
        require_all=True,
    )
    chk = StoppingCriterionChecker(crit)
    state = make_state()
    cq = make_cq(total=4, answerable=2)
    val = make_val(total=10, passed=6)
    stop, reason, _ = chk.check(state, cq, val)
    assert stop
    # reason should be either cq or validation
    assert reason in (StoppingReason.CQ_COVERAGE_MET, StoppingReason.VALIDATION_PASS_RATE_MET)


def test_null_results_do_not_crash():
    crit = StoppingCriteria(min_cq_coverage=0.1, min_validation_pass_rate=0.1)
    chk = StoppingCriterionChecker(crit)
    state = make_state()
    stop, reason, d = chk.check(state, None, None)
    # no coverage or validation -> should not stop but record failures
    assert not stop
    assert reason == StoppingReason.NOT_STOPPED
    assert "cq_coverage" in d["checks"]
    assert "validation_pass_rate" in d["checks"]


def test_max_iterations_precedence():
    crit = StoppingCriteria(max_iterations=3)
    chk = StoppingCriterionChecker(crit)
    state = make_state(iter_count=3)
    stop, reason, _ = chk.check(state)
    assert stop
    assert reason == StoppingReason.MAX_ITERATIONS_REACHED


def test_subscription_logic_any_vs_all():
    # behaviour is identical since logic currently requires all checks
    crit = StoppingCriteria(min_entity_count=1, require_all=False)
    chk = StoppingCriterionChecker(crit)
    state = make_state(count=1)
    stop, reason, _ = chk.check(state)
    assert not stop  # other default criteria still prevent stopping
    crit2 = StoppingCriteria(min_entity_count=1, require_all=True)
    chk2 = StoppingCriterionChecker(crit2)
    state2 = make_state(count=0)
    stop2, reason2, _ = chk2.check(state2)
    assert not stop2
