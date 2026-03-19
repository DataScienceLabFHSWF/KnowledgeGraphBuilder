"""HITL (Human-in-the-Loop) feedback and gap detection endpoints.

These endpoints are the API surface for the cross-repo HITL feedback loop:

  GraphQAAgent ──POST /api/v1/hitl/gaps/detect──► KGBuilder
  KGBuilder    ──POST (ontology-api)/extend────► OntologyExtender
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import structlog
from fastapi import APIRouter, HTTPException

from kgbuilder.api.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    GapDetectRequest,
    GapReportResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

_ONTOLOGY_API_URL = os.getenv("ONTOLOGY_API_URL", "http://ontology-api:8003")


# ------------------------------------------------------------------
# Gap detection
# ------------------------------------------------------------------


@router.get("/gaps", response_model=GapReportResponse)
async def get_latest_gap_report() -> GapReportResponse:
    """Return the latest persisted gap report, or an empty one."""
    import json

    gap_dir = Path("output/hitl_export/gap_reports")
    if gap_dir.exists():
        reports = sorted(gap_dir.glob("gap_report_*.json"), reverse=True)
        if reports:
            data = json.loads(reports[0].read_text())
            return GapReportResponse(
                untyped_entities=data.get("untyped_entities", []),
                failed_queries=data.get("failed_queries", []),
                suggested_new_classes=data.get("suggested_new_classes", []),
                suggested_new_relations=data.get("suggested_new_relations", []),
                coverage_score=data.get("coverage_score", 0.0),
                low_confidence_answers=data.get("low_confidence_answers", []),
                timestamp=data.get("timestamp"),
            )

    return GapReportResponse(
        untyped_entities=[],
        failed_queries=[],
        suggested_new_classes=[],
        suggested_new_relations=[],
        coverage_score=1.0,
        low_confidence_answers=[],
    )


@router.post("/gaps/detect", response_model=GapReportResponse)
async def detect_gaps(request: GapDetectRequest) -> GapReportResponse:
    """Run gap detection from QA results.

    This is the primary entry point for GraphQAAgent to report
    low-confidence answers back to KGBuilder.
    """
    from kgbuilder.hitl.config import GapDetectionConfig
    from kgbuilder.hitl.gap_detector import GapDetector

    detector = GapDetector(GapDetectionConfig())
    report = detector.detect_from_qa_feedback(request.qa_results)

    # Persist report
    try:
        detector.save_report(report, name="gap_report")
    except Exception as e:
        logger.warning("gap_report_save_failed", error=str(e))

    # If there are TBox gaps, forward to OntologyExtender
    if report.suggested_new_classes:
        await _forward_tbox_gaps_to_ontology_api(report)

    return GapReportResponse(
        untyped_entities=report.untyped_entities,
        failed_queries=report.failed_queries,
        suggested_new_classes=report.suggested_new_classes,
        suggested_new_relations=report.suggested_new_relations,
        coverage_score=report.coverage_score,
        low_confidence_answers=report.low_confidence_answers,
        timestamp=report.timestamp.isoformat(),
    )


@router.post("/gaps/detect-from-extraction", response_model=GapReportResponse)
async def detect_gaps_from_extraction(
    entities: list[dict[str, str]],
    ontology_classes: list[str],
) -> GapReportResponse:
    """Run gap detection by comparing extracted entities against ontology."""
    from kgbuilder.hitl.config import GapDetectionConfig
    from kgbuilder.hitl.gap_detector import GapDetector

    detector = GapDetector(GapDetectionConfig())
    report = detector.detect_from_extraction(entities, ontology_classes)

    try:
        detector.save_report(report, name="extraction_gap_report")
    except Exception as e:
        logger.warning("gap_report_save_failed", error=str(e))

    return GapReportResponse(
        untyped_entities=report.untyped_entities,
        failed_queries=report.failed_queries,
        suggested_new_classes=report.suggested_new_classes,
        suggested_new_relations=report.suggested_new_relations,
        coverage_score=report.coverage_score,
        low_confidence_answers=report.low_confidence_answers,
        timestamp=report.timestamp.isoformat(),
    )


# ------------------------------------------------------------------
# Feedback ingestion
# ------------------------------------------------------------------


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Submit expert feedback — routes to OntologyExtender or KGBuilder.

    Wraps ``kgbuilder.hitl.ingestion.FeedbackIngester``.
    """
    from datetime import datetime

    from kgbuilder.hitl.config import FeedbackConfig
    from kgbuilder.hitl.ingestion import FeedbackIngester
    from kgbuilder.hitl.models import ExpertFeedback, FeedbackType, ReviewStatus

    try:
        decision_map = {
            "accepted": ReviewStatus.ACCEPTED,
            "rejected": ReviewStatus.REJECTED,
            "modified": ReviewStatus.MODIFIED,
            "needs_discussion": ReviewStatus.NEEDS_DISCUSSION,
        }
        decision = decision_map.get(request.decision, ReviewStatus.PENDING)

        feedback = ExpertFeedback(
            review_item_id=request.review_item_id,
            reviewer_id=request.reviewer_id,
            decision=decision,
            rationale=request.rationale,
            suggested_changes=request.suggested_changes,
            new_competency_questions=request.new_competency_questions,
            confidence=request.confidence,
            timestamp=datetime.now(),
        )

        ingester = FeedbackIngester(FeedbackConfig())

        # Determine feedback type from item_id prefix or context
        # For now, default to ABOX
        item_types = {request.review_item_id: FeedbackType.ABOX_WRONG_ENTITY}
        result = ingester.ingest([feedback], item_types)

        routed_to = []
        if result.tbox_changes:
            routed_to.append("ontology_extender")
        if result.abox_changes:
            routed_to.append("kg_builder")
        if result.cq_additions:
            routed_to.append("qa_agent")

        change_paths = [
            str(p) for p in result.tbox_changes + result.abox_changes + result.cq_additions
        ]

        return FeedbackResponse(
            status="processed",
            routed_to=routed_to,
            change_request_paths=change_paths,
        )

    except Exception as e:
        logger.error("feedback_processing_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Feedback processing failed: {e}") from e


# ------------------------------------------------------------------
# Cross-service forwarding
# ------------------------------------------------------------------


async def _forward_tbox_gaps_to_ontology_api(report) -> None:
    """Forward TBox gap suggestions to OntologyExtender API.

    Non-blocking best-effort: if ontology-api is unavailable, we log
    and continue (the gap report is already persisted locally).
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        for cls in report.suggested_new_classes:
            try:
                await client.post(
                    f"{_ONTOLOGY_API_URL}/api/v1/extend",
                    json={
                        "change_type": "tbox_new_class",
                        "review_item_id": f"gap_{cls}",
                        "reviewer_id": "kgbuilder_gap_detector",
                        "rationale": f"Entity type '{cls}' frequently extracted but has no ontology class",
                        "suggested_changes": {"class_label": cls},
                        "confidence": 0.8,
                    },
                )
            except httpx.HTTPError as e:
                logger.debug(
                    "ontology_api_unreachable",
                    class_name=cls,
                    error=str(e),
                )
