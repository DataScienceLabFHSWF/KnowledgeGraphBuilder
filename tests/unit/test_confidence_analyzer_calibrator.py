"""Tests covering confidence analyzer and calibrator components."""

from __future__ import annotations

import pytest

import numpy as np

from kgbuilder.confidence.analyzer import ConfidenceAnalyzer
from kgbuilder.confidence.calibrator import ConfidenceCalibrator, CalibrationResult
from kgbuilder.core.models import ExtractedEntity, Evidence


def make_entity(eid: str, etype: str, conf: float) -> ExtractedEntity:
    return ExtractedEntity(
        id=eid,
        label="lbl",
        entity_type=etype,
        description="",
        confidence=conf,
        evidence=[Evidence(source_type="doc", source_id="x")] if conf >= 0 else [],
    )


def test_analyzer_empty_and_basic():
    analyzer = ConfidenceAnalyzer()
    # empty should return zeroed report
    empty_report = analyzer.analyze([])
    assert empty_report.mean == 0.0
    assert empty_report.per_type_stats == {}

    # simple dataset
    # include an extreme value to trigger anomaly detection
    ents = [
        make_entity("1", "A", 0.5),
        make_entity("2", "A", 0.8),
        make_entity("3", "B", 0.2),
        make_entity("4", "B", 0.99),
    ]
    rep = analyzer.analyze(ents)
    assert pytest.approx(rep.mean, rel=1e-6) == np.mean([0.5, 0.8, 0.2, 0.99])
    # check per-type stats key
    assert "A" in rep.per_type_stats
    # rep.anomalies is always a list (may be empty if IQR bounds include all values)
    assert isinstance(rep.anomalies, list)

    # recommend threshold edge cases
    assert analyzer.recommend_threshold([]) == 0.5
    # for list sorted, threshold should return appropriate percentile
    thr = analyzer.recommend_threshold([make_entity("x", "A", c) for c in [0.1, 0.9]], target_precision=0.5)
    assert thr in (0.1, 0.9)


def test_calibrator_fit_and_calibrate():
    calib = ConfidenceCalibrator()
    # mismatched lengths should error
    with pytest.raises(ValueError):
        calib.fit([], [0.1])
    with pytest.raises(ValueError):
        calib.fit([make_entity("1", "A", 0.5)], [0.1])
    # need at least 2 entities
    with pytest.raises(ValueError):
        calib.fit([make_entity("1", "A", 0.5)], [0.0])

    # prepare some training data for two types
    ents = [make_entity("1", "A", 0.2), make_entity("2", "A", 0.8), make_entity("3", "B", 0.5), make_entity("4", "B", 0.6)]
    correct = [0.0, 1.0, 0.4, 0.5]
    calib.fit(ents, correct)
    # models should be stored for each type
    stats = calib.get_calibration_stats()
    assert "A" in stats and "B" in stats
    # calibrate some new entities
    new_ents = [make_entity("5", "A", 0.3), make_entity("6", "C", 0.7)]
    results = calib.calibrate(new_ents)
    assert isinstance(results[0], CalibrationResult)
    # second entity type C has no model so calibrated confidence equals raw
    assert results[1].calibrated_confidence == 0.7
    # uncertainty for unknown type should be high (0.9)
    assert results[1].uncertainty == 0.9

    # calibrate_batch should return updated entities
    updated = calib.calibrate_batch(new_ents)
    assert all(isinstance(e, ExtractedEntity) for e in updated)
    assert updated[1].confidence == 0.7
