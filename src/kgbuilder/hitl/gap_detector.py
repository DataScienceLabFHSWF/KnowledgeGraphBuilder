"""Detect ontology gaps from extraction results and QA feedback.

Gap detection runs after KG extraction or when QA confidence drops.
It identifies:
- Entities without ontology type assignments
- Failed SPARQL queries from competency questions
- Low-confidence QA answers from GraphQAAgent
- Relation types not in the ontology

Outputs a GapReport that can trigger OntologyExtender processing.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from kgbuilder.hitl.config import GapDetectionConfig
from kgbuilder.hitl.models import GapReport, TriggerSource

logger = structlog.get_logger(__name__)


class GapDetector:
    """Detect ontology gaps from extraction results and QA feedback.

    Args:
        config: Gap detection configuration.
    """

    def __init__(self, config: GapDetectionConfig) -> None:
        self._config = config

    def detect_from_extraction(
        self,
        entities: list[dict[str, str]],
        ontology_classes: list[str],
    ) -> GapReport:
        """Detect gaps by comparing extracted entities against ontology classes.

        Args:
            entities: Extracted entities with 'type' and 'label' fields.
            ontology_classes: List of ontology class URIs/labels.

        Returns:
            GapReport with untyped entities and suggested new classes.
        """
        ontology_set = {c.lower() for c in ontology_classes}
        untyped = []
        type_counts: dict[str, int] = {}

        for entity in entities:
            etype = entity.get("type", "").lower()
            if etype not in ontology_set and etype != "":
                untyped.append(entity.get("label", "unknown"))
                type_counts[etype] = type_counts.get(etype, 0) + 1

        # Suggest classes for types that appear frequently
        suggested = [
            t for t, count in sorted(type_counts.items(), key=lambda x: -x[1])
            if count >= 3
        ]

        ratio = len(untyped) / max(len(entities), 1)
        report = GapReport(
            untyped_entities=untyped,
            suggested_new_classes=suggested,
            coverage_score=1.0 - ratio,
        )

        if ratio > self._config.min_untyped_entity_ratio:
            logger.warning(
                "gap_detected",
                untyped_ratio=f"{ratio:.2%}",
                suggested_classes=suggested,
            )

        return report

    def detect_from_qa_feedback(
        self,
        qa_results: list[dict[str, str | float]],
    ) -> GapReport:
        """Detect gaps from low-confidence QA answers.

        When GraphQAAgent returns answers below the confidence threshold,
        this may indicate missing knowledge in the graph or ontology.

        Args:
            qa_results: List of QA result dicts with 'question', 'answer',
                'confidence' fields.

        Returns:
            GapReport with failed queries and potential new CQs.
        """
        low_confidence = [
            r for r in qa_results
            if float(r.get("confidence", 0)) < self._config.min_confidence_threshold
        ]

        failed_queries = [str(r.get("question", "")) for r in low_confidence]

        report = GapReport(
            failed_queries=failed_queries,
            low_confidence_answers=[
                {
                    "question": str(r.get("question", "")),
                    "answer": str(r.get("answer", "")),
                    "confidence": str(r.get("confidence", 0)),
                }
                for r in low_confidence
            ],
        )

        if low_confidence:
            logger.info(
                "qa_gaps_detected",
                low_confidence_count=len(low_confidence),
                total=len(qa_results),
            )

        return report

    def save_report(self, report: GapReport, name: str = "gap_report") -> Path:
        """Persist a gap report to disk as JSON.

        Args:
            report: The gap report to save.
            name: Base filename (without extension).

        Returns:
            Path to the saved report file.
        """
        import json
        from dataclasses import asdict

        out_dir = self._config.gap_report_output
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{name}_{report.timestamp:%Y%m%d_%H%M%S}.json"

        data = asdict(report)
        data["timestamp"] = report.timestamp.isoformat()
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        logger.info("gap_report_saved", path=str(out_path))
        return out_path
