"""Collect, store, and process expert feedback.

Provides persistence for feedback data (JSON files) and helpers
to query, filter, and aggregate feedback across review sessions.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import structlog

from kgbuilder.hitl.config import FeedbackConfig
from kgbuilder.hitl.models import (
    ExpertFeedback,
    FeedbackType,
    ReviewItem,
    ReviewStatus,
)

logger = structlog.get_logger(__name__)


class FeedbackCollector:
    """Collect and persist expert feedback.

    Feedback is stored as individual JSON files in the configured
    feedback store directory, one per review item.

    Args:
        config: Feedback configuration.
    """

    def __init__(self, config: FeedbackConfig) -> None:
        self._config = config
        self._store = config.feedback_store
        self._store.mkdir(parents=True, exist_ok=True)

    def submit_feedback(self, feedback: ExpertFeedback) -> Path:
        """Persist a single expert feedback entry.

        Args:
            feedback: The feedback to store.

        Returns:
            Path to the saved feedback file.

        Raises:
            ValueError: If rationale is required but empty.
        """
        if self._config.require_rationale and not feedback.rationale.strip():
            raise ValueError("Rationale is required for feedback submissions.")

        data = asdict(feedback)
        data["timestamp"] = feedback.timestamp.isoformat()

        filename = (
            f"feedback_{feedback.review_item_id}"
            f"_{feedback.reviewer_id}"
            f"_{feedback.timestamp:%Y%m%d_%H%M%S}.json"
        )
        out_path = self._store / filename
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        logger.info(
            "feedback_submitted",
            item_id=feedback.review_item_id,
            reviewer=feedback.reviewer_id,
            decision=feedback.decision.value,
        )
        return out_path

    def load_feedback_for_item(self, review_item_id: str) -> list[ExpertFeedback]:
        """Load all feedback entries for a specific review item.

        Args:
            review_item_id: The ID of the review item.

        Returns:
            List of ExpertFeedback objects, chronologically ordered.
        """
        results: list[ExpertFeedback] = []

        for path in sorted(self._store.glob(f"feedback_{review_item_id}_*.json")):
            data = json.loads(path.read_text())
            data["decision"] = ReviewStatus(data["decision"])
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            results.append(ExpertFeedback(**data))

        return results

    def get_consensus(self, review_item_id: str) -> ReviewStatus | None:
        """Determine consensus status for a review item.

        Returns the majority decision if min_reviewers have responded.
        Returns None if not enough reviewers have provided feedback.

        Args:
            review_item_id: The review item to check.

        Returns:
            Consensus ReviewStatus or None if insufficient responses.
        """
        feedback = self.load_feedback_for_item(review_item_id)

        if len(feedback) < self._config.min_reviewers_per_item:
            return None

        counts: dict[ReviewStatus, int] = {}
        for f in feedback:
            counts[f.decision] = counts.get(f.decision, 0) + 1

        return max(counts, key=lambda s: counts[s])

    def summarize(self) -> dict[str, int]:
        """Summarize all stored feedback by decision type.

        Returns:
            Dict mapping decision name to count.
        """
        summary: dict[str, int] = {}
        for path in self._store.glob("feedback_*.json"):
            data = json.loads(path.read_text())
            decision = data.get("decision", "unknown")
            summary[decision] = summary.get(decision, 0) + 1
        return summary

    def get_tbox_feedback(self) -> list[ExpertFeedback]:
        """Get all TBox-related feedback (ontology changes).

        Returns:
            List of feedback entries for TBox items.
        """
        tbox_prefixes = {"tbox_"}
        results: list[ExpertFeedback] = []

        for path in sorted(self._store.glob("feedback_*.json")):
            data = json.loads(path.read_text())
            item_type = data.get("suggested_changes", {}).get("item_type", "")
            if any(item_type.startswith(p) for p in tbox_prefixes):
                data["decision"] = ReviewStatus(data["decision"])
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                results.append(ExpertFeedback(**data))

        return results

    def get_abox_feedback(self) -> list[ExpertFeedback]:
        """Get all ABox-related feedback (KG instance changes).

        Returns:
            List of feedback entries for ABox items.
        """
        abox_prefixes = {"abox_"}
        results: list[ExpertFeedback] = []

        for path in sorted(self._store.glob("feedback_*.json")):
            data = json.loads(path.read_text())
            item_type = data.get("suggested_changes", {}).get("item_type", "")
            if any(item_type.startswith(p) for p in abox_prefixes):
                data["decision"] = ReviewStatus(data["decision"])
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                results.append(ExpertFeedback(**data))

        return results
