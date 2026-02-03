"""Confidence calibration for reliable confidence scores."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.isotonic import IsotonicRegression

from kgbuilder.core.models import ExtractedEntity


@dataclass
class CalibrationResult:
    """Result from confidence calibration."""

    entity_id: str
    raw_confidence: float
    calibrated_confidence: float
    calibration_method: str  # "isotonic", "platt", etc.
    uncertainty: float  # Higher = less certain about calibration


class ConfidenceCalibrator:
    """Calibrate confidence scores to match actual precision.

    Learns per-type calibration curves using isotonic regression to map
    raw confidence scores to reliable probability estimates. This corrects
    for model overconfidence or underconfidence.

    Algorithm:
    1. For each entity type, collect (confidence, correctness) pairs
    2. Fit isotonic regression model (isotonic functions are monotonic)
    3. Apply model to map raw confidence → calibrated confidence
    4. Result: confidence scores that match actual precision
       (e.g., 0.8 calibrated confidence = ~80% correct)

    Attributes:
        _models: Dict mapping entity type → fitted IsotonicRegression model
        _entity_counts: Track how many entities per type for uncertainty
    """

    def __init__(self) -> None:
        """Initialize calibrator with empty models."""
        self._models: dict[str, IsotonicRegression] = {}
        self._entity_counts: dict[str, int] = {}

    def fit(
        self,
        entities: list[ExtractedEntity],
        correctness_scores: list[float],
    ) -> None:
        """Fit calibration models using labeled data.

        Args:
            entities: Entities to calibrate
            correctness_scores: Ground truth correctness (0.0-1.0) for each entity
                Should correlate with confidence but may not match exactly

        Raises:
            ValueError: If mismatched lengths or insufficient data
        """
        if len(entities) != len(correctness_scores):
            raise ValueError(
                f"Mismatched lengths: {len(entities)} entities, "
                f"{len(correctness_scores)} scores"
            )

        if len(entities) < 2:
            raise ValueError("Need at least 2 entities to fit calibration")

        # Group by entity type
        by_type: dict[str, list[tuple[float, float]]] = {}
        for entity, correct in zip(entities, correctness_scores):
            if entity.entity_type not in by_type:
                by_type[entity.entity_type] = []
            by_type[entity.entity_type].append((entity.confidence, correct))

        # Fit isotonic regression per type
        for entity_type, pairs in by_type.items():
            if len(pairs) < 2:
                # Skip types with insufficient data
                continue

            confidences = np.array([c for c, _ in pairs])
            correctnesses = np.array([x for _, x in pairs])

            # Isotonic regression: y_pred = f(y_true) where f is monotonic
            model = IsotonicRegression(increasing=True, out_of_bounds="clip")
            model.fit(confidences, correctnesses)

            self._models[entity_type] = model
            self._entity_counts[entity_type] = len(pairs)

    def calibrate(
        self,
        entities: list[ExtractedEntity],
    ) -> list[CalibrationResult]:
        """Calibrate confidence scores using fitted models.

        Args:
            entities: Entities to calibrate

        Returns:
            Calibration results with calibrated confidence scores
        """
        results = []

        for entity in entities:
            # Get or create model for this type
            if entity.entity_type in self._models:
                model = self._models[entity.entity_type]
                calibrated = float(model.predict([entity.confidence])[0])
                count = self._entity_counts.get(entity.entity_type, 0)
                # Uncertainty: higher when fewer entities in training set
                uncertainty = 1.0 / max(count, 1)
            else:
                # No model for this type: return raw confidence with high uncertainty
                calibrated = entity.confidence
                uncertainty = 0.9  # Very uncertain

            result = CalibrationResult(
                entity_id=entity.id,
                raw_confidence=entity.confidence,
                calibrated_confidence=calibrated,
                calibration_method="isotonic",
                uncertainty=uncertainty,
            )
            results.append(result)

        return results

    def calibrate_batch(
        self,
        entities: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """Calibrate and return updated entities.

        Args:
            entities: Entities to calibrate

        Returns:
            Entities with calibrated confidence scores
        """
        results = self.calibrate(entities)

        # Create updated entities with calibrated confidence
        calibrated_entities = []
        for entity, calib_result in zip(entities, results):
            # Use dataclass replace to update confidence
            from dataclasses import replace

            updated = replace(entity, confidence=calib_result.calibrated_confidence)
            calibrated_entities.append(updated)

        return calibrated_entities

    def get_calibration_stats(self) -> dict[str, dict[str, float]]:
        """Get statistics about fitted calibration models.

        Returns:
            Dict mapping entity type → stats about calibration
        """
        stats = {}

        for entity_type, model in self._models.items():
            count = self._entity_counts.get(entity_type, 0)

            # Get X and y from model
            if hasattr(model, 'X_thresholds_') and hasattr(model, 'y_thresholds_'):
                # Isotonic model stores thresholds
                min_conf = float(np.min(model.X_thresholds_))
                max_conf = float(np.max(model.X_thresholds_))
                min_calib = float(np.min(model.y_thresholds_))
                max_calib = float(np.max(model.y_thresholds_))
            else:
                min_conf = max_conf = min_calib = max_calib = 0.0

            stats[entity_type] = {
                "entity_count": count,
                "raw_confidence_range": (min_conf, max_conf),
                "calibrated_range": (min_calib, max_calib),
            }

        return stats
