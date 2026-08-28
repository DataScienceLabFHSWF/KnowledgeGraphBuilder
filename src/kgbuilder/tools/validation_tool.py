"""Validation tool wrapping a VCQ-style KG content validator."""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _validation_handler(
    validator: Any,
    question: Any,
    evidence: list[Any] | None = None,
) -> Any:
    """Check whether the KG content answering `question` is correct/complete."""
    return validator.validate_question(question, evidence or [])


ValidationTool = AgentTool(
    name="kg_content_validation",
    description="Validate that existing KG content correctly/completely answers a VCQ research question.",
    parameters={
        "type": "object",
        "properties": {
            "question": {"type": "object"},
            "evidence": {"type": "array"},
        },
        "required": ["question"],
    },
    handler=_validation_handler,
)
