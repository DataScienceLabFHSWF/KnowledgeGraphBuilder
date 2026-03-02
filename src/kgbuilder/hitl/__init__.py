"""Cross-repo Human-in-the-Loop (HITL) system for KG and ontology review.

This package provides:
- Interactive HTML export of ontologies (TBox) and knowledge graphs (ABox)
- Expert annotation collection (flag issues, suggest classes, propose links)
- Feedback ingestion back into KGBuilder / OntologyExtender
- Gap detection triggers from low-confidence QA answers

Architecture
------------
The HITL system spans all three repos:

    GraphQAAgent  ──(low confidence)──►  KGBuilder  ──(gaps)──►  OntologyExtender
         ▲                                   ▲                         │
         │                                   │                         │
         └── new CQs from users    expert corrections         updated OWL + SHACL

This module lives in KGBuilder and provides the coordination layer.
"""

from __future__ import annotations

__all__ = [
    # Config
    "ExportConfig",
    "HITLConfig",
    # Models
    "ExpertFeedback",
    "ExpertProfile",
    "GapReport",
    "ReviewItem",
    "ReviewSession",
    "ReviewStatus",
    "FeedbackType",
    "TriggerSource",
    # Components
    "FeedbackCollector",
    "FeedbackIngester",
    "GapDetector",
    "HTMLExporter",
    "ReviewWorkflow",
]

from kgbuilder.hitl.config import ExportConfig, HITLConfig
from kgbuilder.hitl.export import HTMLExporter
from kgbuilder.hitl.feedback_collector import FeedbackCollector
from kgbuilder.hitl.gap_detector import GapDetector
from kgbuilder.hitl.ingestion import FeedbackIngester
from kgbuilder.hitl.models import (
    ExpertFeedback,
    ExpertProfile,
    FeedbackType,
    GapReport,
    ReviewItem,
    ReviewSession,
    ReviewStatus,
    TriggerSource,
)
from kgbuilder.hitl.review_workflow import ReviewWorkflow
