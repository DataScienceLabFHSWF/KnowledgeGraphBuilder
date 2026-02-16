"""Confidence score analysis and statistics."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from kgbuilder.core.models import ExtractedEntity

from . import ConfidenceReport, TypeConfidenceStats


class ConfidenceAnalyzer:
    """Analyze confidence score distribution and generate statistics."""

    def analyze(self, entities: Sequence[ExtractedEntity]) -> ConfidenceReport:
        """Generate statistical summary of confidences.

        Args:
            entities: List of extracted entities with confidence scores.

        Returns:
            ConfidenceReport with overall and per-type statistics.
        """
        if not entities:
            return ConfidenceReport(
                mean=0.0,
                std=0.0,
                min=0.0,
                max=0.0,
                percentiles={},
                per_type_stats={},
            )

        confidences = np.array([e.confidence for e in entities])

        # Overall statistics
        overall = ConfidenceReport(
            mean=float(confidences.mean()),
            std=float(confidences.std()),
            min=float(confidences.min()),
            max=float(confidences.max()),
            percentiles={
                10: float(np.percentile(confidences, 10)),
                25: float(np.percentile(confidences, 25)),
                50: float(np.percentile(confidences, 50)),
                75: float(np.percentile(confidences, 75)),
                90: float(np.percentile(confidences, 90)),
            },
            per_type_stats={},
        )

        # Per-type statistics
        by_type: dict[str, list[float]] = {}
        for entity in entities:
            if entity.entity_type not in by_type:
                by_type[entity.entity_type] = []
            by_type[entity.entity_type].append(entity.confidence)

        for entity_type, confs in by_type.items():
            confs_arr = np.array(confs)
            overall.per_type_stats[entity_type] = TypeConfidenceStats(
                entity_type=entity_type,
                count=len(confs),
                mean=float(confs_arr.mean()),
                std=float(confs_arr.std()),
                min=float(confs_arr.min()),
                max=float(confs_arr.max()),
                p90=float(np.percentile(confs_arr, 90)),
            )

        # Detect anomalies (outliers)
        q1 = float(np.percentile(confidences, 25))
        q3 = float(np.percentile(confidences, 75))
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        anomalies = []
        for entity in entities:
            if entity.confidence < lower_bound or entity.confidence > upper_bound:
                anomalies.append(
                    f"{entity.id} ({entity.label}): {entity.confidence}"
                )

        overall.anomalies = anomalies
        overall.recommended_threshold = float(np.percentile(confidences, 50))

        return overall

    def recommend_threshold(
        self, entities: Sequence[ExtractedEntity], target_precision: float = 0.8
    ) -> float:
        """Recommend filtering threshold based on target precision.

        Simple approach: use percentile that achieves target_precision.
        (In practice, would need gold standard labels to compute actual precision)

        Args:
            entities: List of extracted entities.
            target_precision: Target precision level (0.0-1.0).

        Returns:
            Recommended confidence threshold.
        """
        if not entities:
            return 0.5

        confidences = sorted([e.confidence for e in entities])

        # Heuristic: higher confidence → higher precision
        # Recommend threshold at (100 - target_precision * 100)th percentile
        target_percentile = (1 - target_precision) * 100
        idx = max(0, int(len(confidences) * target_percentile / 100))
        return float(confidences[idx])
