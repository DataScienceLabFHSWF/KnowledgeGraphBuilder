"""Orchestrate the expert review workflow.

The review workflow connects gap detection → item creation →
expert review → feedback collection → feedback ingestion.

Cross-repo routing:
- TBox feedback → OntologyExtender (ontology class changes, hierarchy, SHACL)
- ABox feedback → KnowledgeGraphBuilder (entity/relation corrections, re-extraction)
- CQ feedback  → GraphQAAgent (new competency questions, query templates)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import structlog

from kgbuilder.hitl.config import HITLConfig
from kgbuilder.hitl.feedback_collector import FeedbackCollector
from kgbuilder.hitl.gap_detector import GapDetector
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

logger = structlog.get_logger(__name__)


class ReviewWorkflow:
    """Orchestrate end-to-end expert review sessions.

    Args:
        config: Full HITL configuration.
    """

    def __init__(self, config: HITLConfig) -> None:
        self._config = config
        self._gap_detector = GapDetector(config.gap_detection)
        self._feedback_collector = FeedbackCollector(config.feedback)
        self._sessions_dir = config.export.output_dir / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    @property
    def gap_detector(self) -> GapDetector:
        """Access the gap detector instance."""
        return self._gap_detector

    @property
    def feedback_collector(self) -> FeedbackCollector:
        """Access the feedback collector instance."""
        return self._feedback_collector

    def create_session(
        self,
        expert: ExpertProfile,
        trigger: TriggerSource,
        gap_report: GapReport | None = None,
    ) -> ReviewSession:
        """Create a new review session for an expert.

        If a gap_report is provided, review items are auto-generated
        from the gaps. Otherwise an empty session is created for
        manual item addition.

        Args:
            expert: The expert profile for this session.
            trigger: What triggered the session creation.
            gap_report: Optional gap report to generate review items from.

        Returns:
            A new ReviewSession with generated review items.
        """
        session_id = uuid.uuid4().hex[:12]
        session = ReviewSession(id=session_id, expert=expert)

        if gap_report:
            items = self._items_from_gap_report(gap_report, trigger)
            session.items.extend(items)
            logger.info(
                "session_created",
                session_id=session_id,
                expert=expert.name,
                item_count=len(items),
                trigger=trigger.value,
            )
        else:
            logger.info(
                "empty_session_created",
                session_id=session_id,
                expert=expert.name,
            )

        self._persist_session(session)
        return session

    def add_item(self, session: ReviewSession, item: ReviewItem) -> None:
        """Add a review item to an existing session.

        Args:
            session: The session to add the item to.
            item: The review item to add.
        """
        session.items.append(item)
        self._persist_session(session)

    def submit_feedback(
        self,
        session: ReviewSession,
        feedback: ExpertFeedback,
    ) -> None:
        """Submit expert feedback for a review item in this session.

        Args:
            session: The active review session.
            feedback: The expert's feedback.
        """
        self._feedback_collector.submit_feedback(feedback)
        session.feedback.append(feedback)

        # Update item status
        for item in session.items:
            if item.id == feedback.review_item_id:
                item.status = feedback.decision
                break

        self._persist_session(session)

    def complete_session(self, session: ReviewSession) -> dict[str, list[str]]:
        """Complete a review session and route feedback to repos.

        Returns a routing summary indicating which feedback goes where:
        - 'ontology_extender': TBox changes (classes, hierarchy, SHACL)
        - 'kg_builder': ABox changes (entities, relations)
        - 'qa_agent': New competency questions

        Args:
            session: The session to complete.

        Returns:
            Dict mapping repo name to list of feedback item IDs.
        """
        session.completed_at = datetime.now()
        self._persist_session(session)

        routing: dict[str, list[str]] = {
            "ontology_extender": [],
            "kg_builder": [],
            "qa_agent": [],
        }

        for fb in session.feedback:
            if fb.decision == ReviewStatus.REJECTED:
                continue

            item = next(
                (i for i in session.items if i.id == fb.review_item_id), None
            )
            if not item:
                continue

            if item.item_type.value.startswith("tbox_"):
                routing["ontology_extender"].append(fb.review_item_id)
            elif item.item_type.value.startswith("abox_"):
                routing["kg_builder"].append(fb.review_item_id)

            if fb.new_competency_questions:
                routing["qa_agent"].append(fb.review_item_id)

        logger.info(
            "session_completed",
            session_id=session.id,
            items_reviewed=len(session.feedback),
            routing={k: len(v) for k, v in routing.items()},
        )

        return routing

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _items_from_gap_report(
        self,
        report: GapReport,
        trigger: TriggerSource,
    ) -> list[ReviewItem]:
        """Convert gap report findings to review items."""
        items: list[ReviewItem] = []

        for cls in report.suggested_new_classes:
            items.append(ReviewItem(
                id=uuid.uuid4().hex[:10],
                item_type=FeedbackType.TBOX_NEW_CLASS,
                source=trigger,
                title=f"Proposed new class: {cls}",
                description=(
                    f"Entity type '{cls}' was frequently extracted but "
                    f"has no corresponding ontology class."
                ),
            ))

        for query in report.failed_queries:
            items.append(ReviewItem(
                id=uuid.uuid4().hex[:10],
                item_type=FeedbackType.NEW_COMPETENCY_QUESTION,
                source=trigger,
                title=f"Low-confidence query: {query[:60]}",
                description=(
                    f"This query returned low-confidence answers, "
                    f"suggesting missing knowledge in the graph."
                ),
                evidence=[query],
            ))

        return items

    def _persist_session(self, session: ReviewSession) -> Path:
        """Save session state to JSON."""
        data = asdict(session)
        # Serialize datetimes
        for key in ("started_at", "completed_at"):
            val = data.get(key)
            if isinstance(val, datetime):
                data[key] = val.isoformat()
            elif val is None:
                data[key] = None

        for item in data.get("items", []):
            if isinstance(item.get("created_at"), datetime):
                item["created_at"] = item["created_at"].isoformat()

        for fb in data.get("feedback", []):
            if isinstance(fb.get("timestamp"), datetime):
                fb["timestamp"] = fb["timestamp"].isoformat()

        out_path = self._sessions_dir / f"session_{session.id}.json"
        out_path.write_text(json.dumps(data, indent=2, default=str))
        return out_path
