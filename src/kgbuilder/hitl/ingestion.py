"""Apply accepted expert feedback back into the KG and ontology.

This module is the feedback→action bridge:
- ABox changes are applied directly to Neo4j via the storage layer
- TBox changes produce change requests for OntologyExtender
- New competency questions are routed to GraphQAAgent

For safety, ingestion is NOT automatic by default; it requires
explicit confirmation (see FeedbackConfig.auto_apply_accepted).
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
    ReviewStatus,
)

logger = structlog.get_logger(__name__)

# TBox feedback types that should be routed to OntologyExtender
_TBOX_TYPES = {
    FeedbackType.TBOX_NEW_CLASS,
    FeedbackType.TBOX_MODIFY_CLASS,
    FeedbackType.TBOX_HIERARCHY_FIX,
    FeedbackType.TBOX_PROPERTY_FIX,
}

# ABox feedback types that should be applied to KG directly
_ABOX_TYPES = {
    FeedbackType.ABOX_WRONG_ENTITY,
    FeedbackType.ABOX_MISSING_LINK,
    FeedbackType.ABOX_WRONG_LINK,
    FeedbackType.ABOX_DUPLICATE,
    FeedbackType.ABOX_CONFIDENCE_OVERRIDE,
}


class FeedbackIngester:
    """Apply accepted feedback to the knowledge graph and ontology.

    This class produces change request files that downstream systems
    (OntologyExtender, KGBuilder pipeline, GraphQAAgent) can consume.
    It does NOT directly modify Neo4j or ontology files.

    Args:
        config: Feedback configuration.
    """

    def __init__(self, config: FeedbackConfig) -> None:
        self._config = config
        self._change_dir = config.feedback_store / "change_requests"
        self._change_dir.mkdir(parents=True, exist_ok=True)

    def ingest(
        self,
        feedback_items: list[ExpertFeedback],
        item_types: dict[str, FeedbackType],
    ) -> IngestResult:
        """Process a batch of accepted feedback and produce change requests.

        Args:
            feedback_items: Feedback entries to process (should be accepted).
            item_types: Mapping of review_item_id to its FeedbackType.

        Returns:
            IngestResult summarizing what was produced.
        """
        result = IngestResult()

        for fb in feedback_items:
            if fb.decision not in (ReviewStatus.ACCEPTED, ReviewStatus.MODIFIED):
                logger.debug(
                    "skipped_non_accepted",
                    item_id=fb.review_item_id,
                    decision=fb.decision.value,
                )
                continue

            ft = item_types.get(fb.review_item_id)
            if ft is None:
                logger.warning("unknown_item_type", item_id=fb.review_item_id)
                continue

            if ft in _TBOX_TYPES:
                path = self._write_tbox_change(fb, ft)
                result.tbox_changes.append(path)
            elif ft in _ABOX_TYPES:
                path = self._write_abox_change(fb, ft)
                result.abox_changes.append(path)

            if fb.new_competency_questions:
                path = self._write_cq_request(fb)
                result.cq_additions.append(path)

        logger.info(
            "ingestion_complete",
            tbox=len(result.tbox_changes),
            abox=len(result.abox_changes),
            cqs=len(result.cq_additions),
        )
        return result

    def _write_tbox_change(
        self, fb: ExpertFeedback, ft: FeedbackType
    ) -> Path:
        """Write a TBox change request for OntologyExtender."""
        data = {
            "target": "ontology_extender",
            "change_type": ft.value,
            "review_item_id": fb.review_item_id,
            "reviewer_id": fb.reviewer_id,
            "rationale": fb.rationale,
            "suggested_changes": fb.suggested_changes,
            "confidence": fb.confidence,
            "timestamp": fb.timestamp.isoformat(),
        }
        return self._write_change("tbox", fb.review_item_id, data)

    def _write_abox_change(
        self, fb: ExpertFeedback, ft: FeedbackType
    ) -> Path:
        """Write an ABox change request for KGBuilder."""
        data = {
            "target": "kg_builder",
            "change_type": ft.value,
            "review_item_id": fb.review_item_id,
            "reviewer_id": fb.reviewer_id,
            "rationale": fb.rationale,
            "suggested_changes": fb.suggested_changes,
            "confidence": fb.confidence,
            "timestamp": fb.timestamp.isoformat(),
        }
        return self._write_change("abox", fb.review_item_id, data)

    def _write_cq_request(self, fb: ExpertFeedback) -> Path:
        """Write a competency question request for GraphQAAgent."""
        data = {
            "target": "qa_agent",
            "new_competency_questions": fb.new_competency_questions,
            "reviewer_id": fb.reviewer_id,
            "review_item_id": fb.review_item_id,
            "rationale": fb.rationale,
            "timestamp": fb.timestamp.isoformat(),
        }
        return self._write_change("cq", fb.review_item_id, data)

    def _write_change(
        self, prefix: str, item_id: str, data: dict[str, object]
    ) -> Path:
        """Write a change request JSON file."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = self._change_dir / f"{prefix}_{item_id}_{ts}.json"
        out_path.write_text(json.dumps(data, indent=2, default=str))
        return out_path


class IngestResult:
    """Summary of a feedback ingestion run."""

    def __init__(self) -> None:
        self.tbox_changes: list[Path] = []
        self.abox_changes: list[Path] = []
        self.cq_additions: list[Path] = []

    @property
    def total(self) -> int:
        """Total number of change requests produced."""
        return len(self.tbox_changes) + len(self.abox_changes) + len(self.cq_additions)

    def summary(self) -> dict[str, int]:
        """Return a summary dict."""
        return {
            "tbox_changes": len(self.tbox_changes),
            "abox_changes": len(self.abox_changes),
            "cq_additions": len(self.cq_additions),
            "total": self.total,
        }
