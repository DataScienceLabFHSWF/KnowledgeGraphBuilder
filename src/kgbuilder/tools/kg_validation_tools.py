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


def _ontology_consistency_reasoning_handler(consistency_reasoner: Any, ontology_path: Any) -> Any:
    """Check OWL DL consistency of the ontology file (HermiT/Pellet, not KG instance data)."""
    return consistency_reasoner.check_consistency(ontology_path)


def _ontology_pitfall_scan_handler(pitfall_detector: Any, ontology_path: Any) -> Any:
    """Scan the ontology file for common modeling pitfalls (OOPS!)."""
    return pitfall_detector.scan(ontology_path)


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
    description=(
        "Execute semantic rules (transitive/symmetric/functional/inverse properties) "
        "against the KG."
    ),
    parameters={"type": "object", "properties": {}},
    handler=_rules_engine_handler,
)

ConsistencyCheckTool = AgentTool(
    name="consistency_check",
    description="Detect type/value conflicts and duplicate entities in the KG.",
    parameters={"type": "object", "properties": {}},
    handler=_consistency_check_handler,
)

OntologyConsistencyReasoningTool = AgentTool(
    name="ontology_consistency_reasoning",
    description=(
        "Check OWL DL consistency of the ontology file itself via HermiT/Pellet "
        "(unsatisfiable-class detection) — distinct from `consistency_check`, which "
        "checks KG instance data, not the ontology's own logical consistency."
    ),
    parameters={
        "type": "object",
        "properties": {"ontology_path": {"type": "string"}},
        "required": ["ontology_path"],
    },
    handler=_ontology_consistency_reasoning_handler,
)

OntologyPitfallScanTool = AgentTool(
    name="ontology_pitfall_scan",
    description=(
        "Scan the ontology file for common modeling pitfalls via OOPS! "
        "(naming, disjointness, annotations, ...)."
    ),
    parameters={
        "type": "object",
        "properties": {"ontology_path": {"type": "string"}},
        "required": ["ontology_path"],
    },
    handler=_ontology_pitfall_scan_handler,
)
