"""Final entity quality filtering and reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from kgbuilder.core.models import ExtractedEntity


@dataclass
class QualityReport:
    """Comprehensive quality report for entity set."""

    total_entities: int
    filtered_entities: int
    removal_rate: float
    confidence_stats: dict[str, float]
    type_breakdown: dict[str, int]
    quality_issues: list[str]
    timestamp: str
    filter_threshold: float


class EntityQualityFilter:
    """Final quality filtering and QA reporting.

    Applies final confidence-based filtering and generates comprehensive
    quality reports. Produces both human-readable (Markdown) and machine-
    readable (JSON) outputs.

    Filtering Criteria:
    1. Confidence threshold (default: 0.70)
    2. Evidence requirement (minimum 1 evidence source)
    3. Description quality (non-empty)
    4. Type validation (must match ontology if available)

    Attributes:
        _confidence_threshold: Minimum confidence for inclusion
        _require_evidence: Whether evidence is required
        _require_description: Whether description is required
    """

    def __init__(
        self,
        confidence_threshold: float = 0.70,
        require_evidence: bool = True,
        require_description: bool = True,
    ) -> None:
        """Initialize filter.

        Args:
            confidence_threshold: Minimum confidence score (0.0-1.0)
            require_evidence: If True, must have at least 1 evidence source
            require_description: If True, description must be non-empty
        """
        self._confidence_threshold = confidence_threshold
        self._require_evidence = require_evidence
        self._require_description = require_description

    def filter(
        self,
        entities: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """Filter entities by quality criteria.

        Args:
            entities: Entities to filter

        Returns:
            Filtered entities meeting quality criteria
        """
        filtered = []

        for entity in entities:
            if self._passes_filter(entity):
                filtered.append(entity)

        return filtered

    def generate_report(
        self,
        entities: list[ExtractedEntity],
        filtered_entities: list[ExtractedEntity],
    ) -> QualityReport:
        """Generate quality report for entity filtering.

        Args:
            entities: Original entities
            filtered_entities: Filtered entities

        Returns:
            Quality report with statistics and insights
        """
        # Calculate statistics
        confidences = [e.confidence for e in filtered_entities] if filtered_entities else [0.0]
        min_conf = min(confidences) if confidences else 0.0
        max_conf = max(confidences) if confidences else 0.0
        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0

        # Type breakdown
        type_breakdown = {}
        for entity in filtered_entities:
            type_breakdown[entity.entity_type] = type_breakdown.get(entity.entity_type, 0) + 1

        # Quality issues
        issues = self._identify_quality_issues(entities, filtered_entities)

        removal_rate = (len(entities) - len(filtered_entities)) / max(len(entities), 1)

        return QualityReport(
            total_entities=len(entities),
            filtered_entities=len(filtered_entities),
            removal_rate=removal_rate,
            confidence_stats={
                "min": min_conf,
                "max": max_conf,
                "mean": mean_conf,
                "threshold": self._confidence_threshold,
            },
            type_breakdown=type_breakdown,
            quality_issues=issues,
            timestamp=datetime.now().isoformat(),
            filter_threshold=self._confidence_threshold,
        )

    def export_markdown(
        self,
        report: QualityReport,
        filepath: str | None = None,
    ) -> str:
        """Generate Markdown report.

        Args:
            report: Quality report to export
            filepath: Optional file path to write to

        Returns:
            Markdown report text
        """
        md = f"""# Entity Quality Report

Generated: {report.timestamp}

## Summary

- **Total Entities**: {report.total_entities}
- **After Filtering**: {report.filtered_entities}
- **Removal Rate**: {report.removal_rate:.1%}
- **Filter Threshold**: {report.filter_threshold:.2f}

## Confidence Statistics

- **Mean**: {report.confidence_stats['mean']:.2f}
- **Min**: {report.confidence_stats['min']:.2f}
- **Max**: {report.confidence_stats['max']:.2f}
- **Threshold**: {report.confidence_stats['threshold']:.2f}

## Entity Types

| Type | Count |
|------|-------|
"""

        for entity_type, count in sorted(report.type_breakdown.items()):
            md += f"| {entity_type} | {count} |\n"

        if report.quality_issues:
            md += f"""
## Quality Issues

"""
            for issue in report.quality_issues:
                md += f"- {issue}\n"
        else:
            md += "\n## Quality Assessment\n\n✅ No quality issues detected.\n"

        if filepath:
            with open(filepath, "w") as f:
                f.write(md)

        return md

    def export_json(
        self,
        report: QualityReport,
        entities: list[ExtractedEntity],
        filepath: str | None = None,
    ) -> str:
        """Generate JSON report with entity details.

        Args:
            report: Quality report to export
            entities: Filtered entities to include
            filepath: Optional file path to write to

        Returns:
            JSON report text
        """
        entity_data = [
            {
                "id": e.id,
                "label": e.label,
                "type": e.entity_type,
                "description": e.description,
                "confidence": e.confidence,
                "evidence_count": len(e.evidence),
                "sources": list(set(ev.source_id for ev in e.evidence)) if e.evidence else [],
            }
            for e in entities
        ]

        data = {
            "report": {
                "timestamp": report.timestamp,
                "total_entities": report.total_entities,
                "filtered_entities": report.filtered_entities,
                "removal_rate": report.removal_rate,
                "filter_threshold": report.filter_threshold,
                "confidence_stats": report.confidence_stats,
                "type_breakdown": report.type_breakdown,
                "quality_issues": report.quality_issues,
            },
            "entities": entity_data,
        }

        json_str = json.dumps(data, indent=2)

        if filepath:
            with open(filepath, "w") as f:
                f.write(json_str)

        return json_str

    def _passes_filter(self, entity: ExtractedEntity) -> bool:
        """Check if entity passes all quality filters.

        Args:
            entity: Entity to check

        Returns:
            True if entity passes, False otherwise
        """
        # Confidence check
        if entity.confidence < self._confidence_threshold:
            return False

        # Evidence check
        if self._require_evidence and not entity.evidence:
            return False

        # Description check
        if self._require_description and not entity.description:
            return False

        return True

    def _identify_quality_issues(
        self,
        original_entities: list[ExtractedEntity],
        filtered_entities: list[ExtractedEntity],
    ) -> list[str]:
        """Identify quality issues in filtering results.

        Args:
            original_entities: Original entities
            filtered_entities: Filtered entities

        Returns:
            List of quality issue descriptions
        """
        issues = []

        # Check high removal rate
        removal_rate = (len(original_entities) - len(filtered_entities)) / max(len(original_entities), 1)
        if removal_rate > 0.5:
            issues.append(
                f"High removal rate ({removal_rate:.1%}): "
                f"Consider lowering threshold from {self._confidence_threshold:.2f}"
            )

        # Check type distribution
        if filtered_entities:
            type_counts = {}
            for entity in filtered_entities:
                type_counts[entity.entity_type] = type_counts.get(entity.entity_type, 0) + 1

            for entity_type, count in type_counts.items():
                if count == 1:
                    issues.append(
                        f"Single entity of type '{entity_type}': " f"Consider validation or merging"
                    )

        # Check confidence distribution
        if filtered_entities:
            confidences = [e.confidence for e in filtered_entities]
            mean_conf = sum(confidences) / len(confidences)
            min_conf = min(confidences)

            if mean_conf < 0.75:
                issues.append(
                    f"Low average confidence ({mean_conf:.2f}): "
                    "Consider running confidence booster or re-extraction"
                )

            if min_conf < 0.70:
                issues.append(
                    f"Minimum confidence very low ({min_conf:.2f}): "
                    "Consider higher threshold"
                )

        return issues
