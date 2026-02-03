"""Unit tests for ConfidenceCalibrator (Task 5.4)."""

from __future__ import annotations

import pytest

from kgbuilder.confidence.calibrator import ConfidenceCalibrator
from kgbuilder.core.models import ExtractedEntity, Evidence


@pytest.fixture
def sample_entities() -> list[ExtractedEntity]:
    """Create sample entities for testing."""
    return [
        ExtractedEntity(
            id="e1",
            label="Apple Inc.",
            entity_type="Organization",
            description="Technology company",
            confidence=0.95,
            evidence=[Evidence(source_type="local_doc", source_id="doc1", text_span="Apple Inc.")],
        ),
        ExtractedEntity(
            id="e2",
            label="ML",
            entity_type="Concept",
            description="Field of study",
            confidence=0.85,
            evidence=[Evidence(source_type="local_doc", source_id="doc1", text_span="ML")],
        ),
        ExtractedEntity(
            id="e3",
            label="learning",
            entity_type="Concept",
            description="Subset of AI",
            confidence=0.75,
            evidence=[Evidence(source_type="local_doc", source_id="doc1", text_span="learning")],
        ),
        ExtractedEntity(
            id="e4",
            label="John Smith",
            entity_type="Person",
            description="Random person",
            confidence=0.55,
            evidence=[Evidence(source_type="local_doc", source_id="doc2", text_span="John Smith")],
        ),
        ExtractedEntity(
            id="e5",
            label="Google",
            entity_type="Organization",
            description="Tech company",
            confidence=0.92,
            evidence=[Evidence(source_type="local_doc", source_id="doc2", text_span="Google")],
        ),
    ]


@pytest.fixture
def calibrator() -> ConfidenceCalibrator:
    """Create calibrator instance."""
    return ConfidenceCalibrator()


class TestConfidenceCalibratorBasics:
    """Test basic calibrator initialization and properties."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        cal = ConfidenceCalibrator()
        assert cal is not None


class TestConfidenceCalibratorFitting:
    """Test fitting calibration models."""

    def test_fit_with_valid_data(
        self,
        calibrator: ConfidenceCalibrator,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test fitting with valid data."""
        correctness = [1, 1, 1, 0, 1]
        calibrator.fit(sample_entities, correctness)

    def test_fit_rejects_mismatched_lengths(
        self,
        calibrator: ConfidenceCalibrator,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test that fit rejects mismatched lengths."""
        correctness = [1, 1]
        with pytest.raises(ValueError):
            calibrator.fit(sample_entities, correctness)

    def test_fit_rejects_empty_data(
        self,
        calibrator: ConfidenceCalibrator,
    ) -> None:
        """Test that fit rejects empty data."""
        with pytest.raises(ValueError):
            calibrator.fit([], [])

    def test_fit_with_varied_correctness(
        self,
        calibrator: ConfidenceCalibrator,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test fit with varied correctness patterns."""
        correctness = [1, 1, 0, 0, 1]
        calibrator.fit(sample_entities, correctness)


class TestConfidenceCalibratorCalibration:
    """Test calibration of confidence scores."""

    def test_calibrate_after_fit(
        self,
        calibrator: ConfidenceCalibrator,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test calibration after fitting."""
        correctness = [1, 1, 1, 0, 1]
        calibrator.fit(sample_entities, correctness)
        results = calibrator.calibrate(sample_entities)

        assert len(results) == len(sample_entities)
        for result in results:
            assert hasattr(result, "entity_id")
            assert hasattr(result, "raw_confidence")
            assert hasattr(result, "calibrated_confidence")

    def test_calibrate_after_fit_multiple_types(
        self,
        calibrator: ConfidenceCalibrator,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test calibration after fitting preserves entity structure."""
        correctness = [1, 1, 1, 0, 1]
        calibrator.fit(sample_entities, correctness)
        updated = calibrator.calibrate_batch(sample_entities)

        # Verify structure is maintained
        for orig, upd in zip(sample_entities, updated):
            assert orig.id == upd.id
            assert orig.label == upd.label

    def test_calibrate_batch(
        self,
        calibrator: ConfidenceCalibrator,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test batch calibration with entity update."""
        correctness = [1, 1, 1, 0, 1]
        calibrator.fit(sample_entities, correctness)
        updated = calibrator.calibrate_batch(sample_entities)

        assert len(updated) == len(sample_entities)


class TestConfidenceCalibratorStatistics:
    """Test calibration statistics."""

    def test_get_stats_after_fit(
        self,
        calibrator: ConfidenceCalibrator,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test getting stats after fit."""
        correctness = [1, 1, 1, 0, 1]
        calibrator.fit(sample_entities, correctness)
        stats = calibrator.get_calibration_stats()

        assert isinstance(stats, dict)
        assert len(stats) > 0

    def test_get_stats_details(
        self,
        calibrator: ConfidenceCalibrator,
        sample_entities: list[ExtractedEntity],
    ) -> None:
        """Test detailed stats after fit."""
        correctness = [1, 1, 1, 0, 1]
        calibrator.fit(sample_entities, correctness)
        stats = calibrator.get_calibration_stats()

        # Stats should have entry per type
        assert isinstance(stats, dict)


class TestConfidenceCalibratorEdgeCases:
    """Test edge cases."""

    def test_multiple_entities(self, calibrator: ConfidenceCalibrator) -> None:
        """Test calibration with multiple entities."""
        entities = [
            ExtractedEntity(
                id="e1",
                label="Test",
                entity_type="Thing",
                description="Test",
                confidence=0.8,
                evidence=[Evidence(source_type="local_doc", source_id="d1", text_span="test")],
            ),
            ExtractedEntity(
                id="e2",
                label="Test2",
                entity_type="Thing",
                description="Test",
                confidence=0.6,
                evidence=[Evidence(source_type="local_doc", source_id="d2", text_span="test2")],
            ),
        ]
        calibrator.fit(entities, [1, 0])
        results = calibrator.calibrate(entities)
        assert len(results) == 2

    def test_all_same_type(self, calibrator: ConfidenceCalibrator) -> None:
        """Test with all entities of same type."""
        entities = [
            ExtractedEntity(
                id=f"e{i}",
                label=f"Entity {i}",
                entity_type="Concept",
                description="Test",
                confidence=0.5 + (i * 0.1),
                evidence=[Evidence(source_type="local_doc", source_id="d1", text_span=f"text{i}")],
            )
            for i in range(5)
        ]
        calibrator.fit(entities, [1, 1, 1, 0, 0])
        results = calibrator.calibrate(entities)
        assert len(results) == 5

    def test_perfect_predictions(self, calibrator: ConfidenceCalibrator) -> None:
        """Test with perfect predictions."""
        entities = [
            ExtractedEntity(
                id=f"e{i}",
                label=f"Entity {i}",
                entity_type="Concept",
                description="Test",
                confidence=0.5 + (i * 0.1),
                evidence=[Evidence(source_type="local_doc", source_id="d1", text_span=f"text{i}")],
            )
            for i in range(5)
        ]
        calibrator.fit(entities, [1, 1, 1, 1, 1])
        results = calibrator.calibrate(entities)
        assert len(results) == 5
