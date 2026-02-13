"""Unit tests for KGQualityScorer (lightweight smoke tests)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from kgbuilder.validation.scorer import KGQualityScorer
from kgbuilder.validation.static_validator import StaticValidationResult


def test_scorer_handles_empty_store(tmp_path: Path) -> None:
    sv = MagicMock()
    # satisfiable shapes
    sv.check_satisfiability.return_value = StaticValidationResult(valid=True, mode="satisfiability")
    # validation of sampled actions returns valid
    sv.validate_entities_and_relations.return_value = StaticValidationResult(valid=True, mode="staticValidation")

    scorer = KGQualityScorer(static_validator=sv)
    fake_store = MagicMock()
    fake_store.to_dict.return_value = {"entities": [], "relations": []}

    report = scorer.score_store(fake_store, shapes_path=tmp_path / "shapes.ttl")
    assert 0.0 <= report.combined_score <= 1.0
    assert report.violations in (0, 1)
    assert "validation" in report.details
