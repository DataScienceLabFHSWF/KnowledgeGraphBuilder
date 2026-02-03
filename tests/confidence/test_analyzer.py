"""Tests for ConfidenceAnalyzer."""

from __future__ import annotations

import pytest

from kgbuilder.core.models import ExtractedEntity
from kgbuilder.confidence.analyzer import ConfidenceAnalyzer


@pytest.fixture
def analyzer() -> ConfidenceAnalyzer:
    """Create a ConfidenceAnalyzer instance."""
    return ConfidenceAnalyzer()


@pytest.fixture
def sample_entities() -> list[ExtractedEntity]:
    """Create sample entities with varying confidence."""
    return [
        ExtractedEntity(
            id=f"e{i}",
            label=f"Entity {i}",
            entity_type="Action",
            description=f"Entity {i}",
            confidence=0.5 + i * 0.05,  # 0.5, 0.55, 0.6, ..., 0.95
        )
        for i in range(10)
    ]


def test_analyze_empty_list(analyzer: ConfidenceAnalyzer) -> None:
    """Test analysis on empty entity list."""
    report = analyzer.analyze([])
    assert report.mean == 0.0
    assert report.per_type_stats == {}


def test_analyze_single_entity(analyzer: ConfidenceAnalyzer) -> None:
    """Test analysis on single entity."""
    entities = [
        ExtractedEntity(
            id="e1", label="Test", entity_type="Action", description="Test", confidence=0.75
        )
    ]
    report = analyzer.analyze(entities)
    assert report.mean == 0.75
    assert report.min == 0.75
    assert report.max == 0.75


def test_analyze_returns_statistics(
    analyzer: ConfidenceAnalyzer, sample_entities: list[ExtractedEntity]
) -> None:
    """Test that analysis returns correct statistics."""
    report = analyzer.analyze(sample_entities)
    assert 0.72 < report.mean < 0.74  # ~0.725
    assert report.min == 0.5
    assert report.max == 0.95
    assert "Action" in report.per_type_stats


def test_percentiles_calculated(
    analyzer: ConfidenceAnalyzer, sample_entities: list[ExtractedEntity]
) -> None:
    """Test that percentiles are calculated."""
    report = analyzer.analyze(sample_entities)
    assert 10 in report.percentiles
    assert 25 in report.percentiles
    assert 50 in report.percentiles
    assert 75 in report.percentiles
    assert 90 in report.percentiles


def test_per_type_statistics(analyzer: ConfidenceAnalyzer) -> None:
    """Test per-type confidence statistics."""
    entities = [
        ExtractedEntity(
            id="e1",
            label="Action 1",
            entity_type="Action",
            description="Action 1",
            confidence=0.8,
        ),
        ExtractedEntity(
            id="e2",
            label="Action 2",
            entity_type="Action",
            description="Action 2",
            confidence=0.9,
        ),
        ExtractedEntity(
            id="e3",
            label="Param 1",
            entity_type="Parameter",
            description="Param 1",
            confidence=0.6,
        ),
        ExtractedEntity(
            id="e4",
            label="Param 2",
            entity_type="Parameter",
            description="Param 2",
            confidence=0.7,
        ),
    ]
    report = analyzer.analyze(entities)
    assert len(report.per_type_stats) == 2
    assert report.per_type_stats["Action"].count == 2
    assert report.per_type_stats["Parameter"].count == 2
    assert 0.84 < report.per_type_stats["Action"].mean < 0.86
    assert 0.64 < report.per_type_stats["Parameter"].mean < 0.66


def test_anomaly_detection(analyzer: ConfidenceAnalyzer) -> None:
    """Test outlier/anomaly detection."""
    entities = [
        ExtractedEntity(
            id=f"e{i}",
            label=f"Entity {i}",
            entity_type="Action",
            description=f"Entity {i}",
            confidence=0.5,
        )
        for i in range(9)
    ]
    # Add outlier
    entities.append(
        ExtractedEntity(
            id="outlier",
            label="Outlier",
            entity_type="Action",
            description="Outlier",
            confidence=0.99,
        )
    )
    report = analyzer.analyze(entities)
    assert len(report.anomalies) > 0


def test_recommend_threshold(
    analyzer: ConfidenceAnalyzer, sample_entities: list[ExtractedEntity]
) -> None:
    """Test threshold recommendation."""
    threshold = analyzer.recommend_threshold(sample_entities, target_precision=0.8)
    assert 0.5 <= threshold <= 0.9


def test_recommend_threshold_empty_list(analyzer: ConfidenceAnalyzer) -> None:
    """Test threshold recommendation on empty list."""
    threshold = analyzer.recommend_threshold([], target_precision=0.8)
    assert threshold == 0.5
