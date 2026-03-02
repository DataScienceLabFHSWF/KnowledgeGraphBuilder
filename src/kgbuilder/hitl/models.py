"""Data models for the HITL review system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal


class ReviewStatus(Enum):
    """Status of a review item."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_DISCUSSION = "needs_discussion"
    MODIFIED = "modified"


class FeedbackType(Enum):
    """Type of expert feedback."""

    TBOX_NEW_CLASS = "tbox_new_class"
    TBOX_MODIFY_CLASS = "tbox_modify_class"
    TBOX_HIERARCHY_FIX = "tbox_hierarchy_fix"
    TBOX_PROPERTY_FIX = "tbox_property_fix"
    ABOX_WRONG_ENTITY = "abox_wrong_entity"
    ABOX_MISSING_LINK = "abox_missing_link"
    ABOX_WRONG_LINK = "abox_wrong_link"
    ABOX_DUPLICATE = "abox_duplicate"
    ABOX_CONFIDENCE_OVERRIDE = "abox_confidence_override"
    NEW_COMPETENCY_QUESTION = "new_competency_question"


class TriggerSource(Enum):
    """What triggered the HITL review."""

    LOW_CONFIDENCE_QA = "low_confidence_qa"
    EXPERT_INSPECTION = "expert_inspection"
    GAP_DETECTION = "gap_detection"
    NEW_DOCUMENT = "new_document"
    SHACL_VIOLATION = "shacl_violation"
    MANUAL = "manual"


@dataclass
class ExpertProfile:
    """A domain expert who can review artefacts."""

    id: str
    name: str
    domain: Literal["nuclear", "legal", "ontology", "general"]
    email: str = ""
    organization: str = ""


@dataclass
class ReviewItem:
    """A single item for expert review.

    Can be a TBox class, an ABox entity/relation, or a proposed change.
    """

    id: str
    item_type: FeedbackType
    source: TriggerSource
    title: str
    description: str
    evidence: list[str] = field(default_factory=list)
    context: dict[str, str] = field(default_factory=dict)
    status: ReviewStatus = ReviewStatus.PENDING
    assigned_to: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExpertFeedback:
    """Feedback from a domain expert on a review item."""

    review_item_id: str
    reviewer_id: str
    decision: ReviewStatus
    rationale: str
    suggested_changes: dict[str, str] = field(default_factory=dict)
    new_competency_questions: list[str] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GapReport:
    """Report of ontology gaps detected from extraction or QA."""

    untyped_entities: list[str] = field(default_factory=list)
    failed_queries: list[str] = field(default_factory=list)
    low_confidence_answers: list[dict[str, str]] = field(default_factory=list)
    suggested_new_classes: list[str] = field(default_factory=list)
    suggested_new_relations: list[str] = field(default_factory=list)
    coverage_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReviewSession:
    """A complete review session with an expert."""

    id: str
    expert: ExpertProfile
    items: list[ReviewItem] = field(default_factory=list)
    feedback: list[ExpertFeedback] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
