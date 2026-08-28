"""Coverage snapshot tool."""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _coverage_snapshot_handler(agent: Any, **kwargs: Any) -> dict[str, Any]:
    """Return a snapshot of current ontology coverage."""
    max_questions = kwargs.get("max_questions", 50)
    all_classes = agent._ontology.get_all_classes()
    coverage = agent._calculate_coverage(all_classes)
    return {
        "total_classes": len(all_classes),
        "covered_classes": sum(1 for count in coverage.values() if count >= 1),
        "under_covered": [cls for cls, count in coverage.items() if count < 1][:max_questions],
        "coverage": coverage,
    }


CoverageSnapshotTool = AgentTool(
    name="coverage_snapshot",
    description="Return the current ontology coverage snapshot and under-covered classes.",
    parameters={
        "type": "object",
        "properties": {"max_questions": {"type": "integer", "minimum": 1}},
        "additionalProperties": True,
    },
    handler=_coverage_snapshot_handler,
)
