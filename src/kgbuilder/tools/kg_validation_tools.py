"""KG validation tools: SHACL shapes, semantic rules, and consistency checking."""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _shacl_validation_handler(shacl_validator: Any, store: Any, run_id: str | None = None) -> Any:
    """Validate the KG against SHACL shapes."""
    return shacl_validator.validate(store, run_id=run_id)


def _rules_engine_handler(rules_engine: Any, store: Any) -> Any:
    """Execute semantic rules (transitive/symmetric/functional/inverse) against the KG."""
    return rules_engine.execute_rules(store)


def _consistency_check_handler(consistency_checker: Any, store: Any) -> Any:
    """Detect conflicts and duplicates in the KG."""
    return consistency_checker.check_consistency(store)


SHACLValidationTool = AgentTool(
    name="shacl_validation",
    description="Validate the knowledge graph against SHACL shape constraints.",
    parameters={
        "type": "object",
        "properties": {"run_id": {"type": "string"}},
    },
    handler=_shacl_validation_handler,
)

RulesEngineTool = AgentTool(
    name="rules_engine_validation",
    description="Execute semantic rules (transitive/symmetric/functional/inverse properties) against the KG.",
    parameters={"type": "object", "properties": {}},
    handler=_rules_engine_handler,
)

ConsistencyCheckTool = AgentTool(
    name="consistency_check",
    description="Detect type/value conflicts and duplicate entities in the KG.",
    parameters={"type": "object", "properties": {}},
    handler=_consistency_check_handler,
)
