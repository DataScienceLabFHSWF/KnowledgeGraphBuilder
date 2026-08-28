"""Ontology gap analysis skill."""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill


def _ontology_gap_analysis_handler(agent: Any, **kwargs: Any) -> Any:
    """Generate research questions from ontology coverage gaps."""
    return agent.generate_questions(**kwargs)


OntologyGapAnalysisSkill = AgentSkill(
    name="ontology_gap_analysis",
    description="Identify under-covered ontology classes and return priority-ranked research questions.",
    handler=_ontology_gap_analysis_handler,
)
