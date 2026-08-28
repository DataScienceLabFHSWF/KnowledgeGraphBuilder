"""Static (pre-commit) SHACL2FOL validation tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kgbuilder.tools.base import AgentTool


def _static_validation_handler(
    static_validator: Any,
    shapes_path: str | Path,
    entities: list[Any],
    relations: list[Any] | None = None,
    ontology_service: Any | None = None,
) -> Any:
    """Check whether adding entities/relations would preserve SHACL validity."""
    return static_validator.validate_entities_and_relations(
        Path(shapes_path), entities, relations or [], ontology_service=ontology_service
    )


StaticValidationTool = AgentTool(
    name="static_validation",
    description=(
        "Pre-commit check via SHACL2FOL: does adding this batch of entities/relations "
        "preserve SHACL validity before it is written to the KG?"
    ),
    parameters={
        "type": "object",
        "properties": {
            "shapes_path": {"type": "string"},
            "entities": {"type": "array"},
            "relations": {"type": "array"},
        },
        "required": ["shapes_path", "entities"],
    },
    handler=_static_validation_handler,
)
