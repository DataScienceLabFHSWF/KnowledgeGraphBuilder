"""Entity confidence tuning and refinement module.

Phase 5 of the Knowledge Graph Builder pipeline.
Refines raw extracted entities by optimizing confidence scores,
resolving coreferences, and generating quality reports.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ConfidenceReport:
    """Statistical summary of confidence distribution."""

    mean: float
    std: float
    min: float
    max: float
    percentiles: dict[int, float]  # p10, p25, p50, p75, p90
    per_type_stats: dict[str, "TypeConfidenceStats"]
    anomalies: list[str] = field(default_factory=list)
    recommended_threshold: float = 0.70


@dataclass
class TypeConfidenceStats:
    """Per-entity-type confidence statistics."""

    entity_type: str
    count: int
    mean: float
    std: float
    min: float
    max: float
    p90: float


@dataclass
class EntityCluster:
    """Group of coreferent entities."""

    representative_id: str
    entities: list[str]  # entity IDs
    similarity_scores: dict[tuple[str, str], float]
    reason: str = "coreference"


@dataclass
class ConsensusResult:
    """Result of consensus voting."""

    entity_id: str
    original_confidence: float
    consensus_confidence: float
    vote_count: int
    agree_count: int
    disagree_count: int
    explanations: list[str] = field(default_factory=list)
    recommendation: Literal["accept", "review", "reject"] = "review"


@dataclass
class EntityReviewFlag:
    """Flag an entity for manual review."""

    entity_id: str
    entity_label: str
    reason: str
    severity: Literal["low", "medium", "high"]
    confidence: float
    suggested_action: str


@dataclass
class TypeQualityMetrics:
    """Quality metrics for a specific entity type."""

    entity_type: str
    total_count: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    mean_confidence: float
    calibration_error: float = 0.0


@dataclass
class QualityReport:
    """Final quality report."""

    total_entities: int
    entities_retained: int
    entities_filtered: int
    confidence_distribution: dict[str, int]  # "high", "medium", "low"
    per_type_metrics: dict[str, TypeQualityMetrics]
    flagged_entities: list[EntityReviewFlag]
    recommended_threshold: float
    report_date: str


from kgbuilder.confidence.analyzer import ConfidenceAnalyzer
from kgbuilder.confidence.booster import ConfidenceBooster
from kgbuilder.confidence.calibrator import ConfidenceCalibrator, CalibrationResult
from kgbuilder.confidence.coreference import CoreferenceResolver
from kgbuilder.confidence.filter import EntityQualityFilter
from kgbuilder.confidence.voter import ConsensusVoter, VotingResult

__all__ = [
    # Data models
    "ConfidenceReport",
    "TypeConfidenceStats",
    "EntityCluster",
    "ConsensusResult",
    "EntityReviewFlag",
    "TypeQualityMetrics",
    "QualityReport",
    "CalibrationResult",
    "VotingResult",
    # Components
    "ConfidenceAnalyzer",
    "ConfidenceBooster",
    "ConfidenceCalibrator",
    "CoreferenceResolver",
    "EntityQualityFilter",
    "ConsensusVoter",
]
