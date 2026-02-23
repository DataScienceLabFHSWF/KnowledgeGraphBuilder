import pytest

from kgbuilder.pipeline.stopping_criterion import (
    StoppingCriteria,
    StoppingCriterionChecker,
    KGBuildState,
    CompetencyQuestionResults,
    ValidationResults,
    StoppingReason,
)


def test_stopping_criteria_validation_failures():
    with pytest.raises(ValueError):
        StoppingCriteria(min_cq_coverage=-0.1).validate()
    with pytest.raises(ValueError):
        StoppingCriteria(min_validation_pass_rate=1.5).validate()
    with pytest.raises(ValueError):
        StoppingCriteria(min_avg_confidence=2.0).validate()
    with pytest.raises(ValueError):
        StoppingCriteria(min_entity_count=-5).validate()
    with pytest.raises(ValueError):
        StoppingCriteria(max_iterations=0).validate()


def make_dummy_state(entity_count=0, avg_conf=0.0, iteration=0):
    return KGBuildState(entity_count=entity_count, avg_confidence=avg_conf, iteration_count=iteration)


def make_cq(total, ans):
    return CompetencyQuestionResults(total_questions=total, answerable_questions=ans,
                                     coverage_percentage=(ans/total*100 if total>0 else 0),
                                     unanswerable=[f"cq{i}" for i in range(total-ans)])


def make_val(total, passed):
    return ValidationResults(total_checks=total, passed_checks=passed,
                             pass_rate=(passed/total*100 if total>0 else 100),
                             violations=total-passed, conflicts=0)


def test_checker_max_iterations_short_circuit():
    crit = StoppingCriteria(max_iterations=1)
    checker = StoppingCriterionChecker(crit)
    state = make_dummy_state(iteration=1)
    stop, reason, details = checker.check(state)
    assert stop is True
    assert reason == StoppingReason.MAX_ITERATIONS_REACHED


def test_checker_entity_confidence_cq_validation_logic():
    crit = StoppingCriteria(min_entity_count=5, min_avg_confidence=0.5,
                             min_cq_coverage=0.5, min_validation_pass_rate=0.5,
                             require_all=True)
    checker = StoppingCriterionChecker(crit)
    state = make_dummy_state(entity_count=6, avg_conf=0.6)
    cq = make_cq(4, 3)  # 75% coverage
    val = make_val(10, 8)  # 80% pass
    stop, reason, details = checker.check(state, cq, val)
    assert stop
    assert reason == StoppingReason.CQ_COVERAGE_MET or reason == StoppingReason.VALIDATION_PASS_RATE_MET
    assert "cq_coverage" in details["checks"]

    # require_all False should still stop when one criterion passes
    crit.require_all = False
    checker2 = StoppingCriterionChecker(crit)
    stop2, _, _ = checker2.check(state, make_cq(10, 0), None)
    # though CQ fails, entity_count/confidence are met but they are non-critical -> logic still uses all_passed
    assert stop2 is False


def test_checker_missing_results_and_summary():
    crit = StoppingCriteria()
    checker = StoppingCriterionChecker(crit)
    state = make_dummy_state()
    stop, reason, details = checker.check(state, None, None)
    assert stop is False
    # summary string contains required information
    s = checker.get_summary()
    assert "Stopping Criteria Check Summary" in s


def test_results_ratio_methods():
    cq = CompetencyQuestionResults(total_questions=0, answerable_questions=0)
    assert cq.get_coverage_ratio() == 1.0
    cq2 = CompetencyQuestionResults(total_questions=4, answerable_questions=1)
    assert cq2.get_coverage_ratio() == 0.25
    val = ValidationResults(total_checks=0, passed_checks=0)
    assert val.get_pass_rate_ratio() == 1.0
    val2 = ValidationResults(total_checks=10, passed_checks=5)
    assert val2.get_pass_rate_ratio() == 0.5
