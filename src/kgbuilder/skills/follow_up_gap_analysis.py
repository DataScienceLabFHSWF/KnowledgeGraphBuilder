"""Follow-up discovery skill."""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill


def _follow_up_gap_analysis_handler(agent: Any, **kwargs: Any) -> Any:
    """Generate follow-up questions for newly discovered entity types."""
    return agent.generate_follow_up_questions(**kwargs)


FollowUpGapAnalysisSkill = AgentSkill(
    name="follow_up_gap_analysis",
    description="Generate follow-up questions once a discovery pass finds new entity types.",
    handler=_follow_up_gap_analysis_handler,
)
