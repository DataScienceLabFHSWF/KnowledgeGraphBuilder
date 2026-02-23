"""Unit tests for KGQualityScorer (lightweight smoke tests)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from kgbuilder.validation.scorer import KGQualityReport, KGQualityScorer
from kgbuilder.validation.static_validator import StaticValidationResult


def _make_scorer(*, sv: MagicMock | None = None, sh: MagicMock | None = None) -> KGQualityScorer:
    """Helper to build a scorer with mocked validators."""
    if sv is None:
        sv = MagicMock()
        sv.check_satisfiability.return_value = StaticValidationResult(valid=True, mode="satisfiability")
        sv.validate_entities_and_relations.return_value = StaticValidationResult(valid=True, mode="staticValidation")
    if sh is None:
        sh = MagicMock()
        sh.validate.return_value = MagicMock(valid=True, violations=[])
    return KGQualityScorer(static_validator=sv, shacl_validator=sh)


def test_scorer_handles_empty_store(tmp_path: Path) -> None:
    scorer = _make_scorer()
    fake_store = MagicMock()
    fake_store.to_dict.return_value = {"entities": [], "relations": []}

    report = scorer.score_store(fake_store, shapes_path=tmp_path / "shapes.ttl")
    assert isinstance(report, KGQualityReport)
    assert 0.0 <= report.combined_score <= 1.0
    assert report.shacl_score >= 0.0
    assert "pyshacl" in report.details
    assert report.details["pyshacl"]["score"] >= 0.0


def test_scorer_report_includes_weights() -> None:
    scorer = _make_scorer()
    fake_store = MagicMock()
    fake_store.to_dict.return_value = {"entities": [], "relations": []}

    report = scorer.score_store(fake_store)
    assert "weights" in report.details
    total = sum(report.details["weights"].values())
    assert abs(total - 1.0) < 1e-6


def test_scorer_with_violations() -> None:
    sh = MagicMock()
    violation = MagicMock()
    violation.__dict__ = {"severity": "Violation", "message": "bad", "path": "x", "focus_node": "n1"}
    sh.validate.return_value = MagicMock(valid=False, violations=[violation] * 5)

    scorer = _make_scorer(sh=sh)
    fake_store = MagicMock()
    fake_store.to_dict.return_value = {"entities": [], "relations": []}

    report = scorer.score_store(fake_store)
    assert report.violations == 5
    assert report.shacl_score < 1.0
    assert report.shacl_report_path is not None
