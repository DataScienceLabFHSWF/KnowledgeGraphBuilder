"""Ontology query tool."""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _ontology_query_handler(ontology: Any, class_name: str, query_type: str = "hierarchy") -> Any:
    """Inspect ontology metadata for a specific class."""
    if query_type == "hierarchy":
        return ontology.get_class_hierarchy(class_name)
    if query_type == "relations":
        return ontology.get_class_relations(class_name)
    if query_type == "description":
        return ontology.get_class_description(class_name)
    raise ValueError(f"Unsupported ontology query type: {query_type}")


OntologyQueryTool = AgentTool(
    name="ontology_query",
    description="Inspect ontology metadata for a class, including hierarchy, relations, and description.",
    parameters={
        "type": "object",
        "properties": {
            "class_name": {"type": "string"},
            "query_type": {"type": "string", "enum": ["hierarchy", "relations", "description"]},
        },
        "required": ["class_name", "query_type"],
    },
    handler=_ontology_query_handler,
)
