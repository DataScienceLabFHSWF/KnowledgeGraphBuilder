"""Post-assembly KG validation skill: SHACL + rules + consistency checking.

Mirrors the logic in `api.routes.validate`, expressed as a reusable skill so
`PipelineAgent`/`LangChainReactAgent` plans can invoke the same validation
stage the FastAPI route already exposes.
"""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.kg_validation_tools import (
    ConsistencyCheckTool,
    RulesEngineTool,
    SHACLValidationTool,
)


def _kg_validation_handler(
    store: Any,
    shacl_validator: Any | None = None,
    rules_engine: Any | None = None,
    consistency_checker: Any | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run whichever validation stages have a validator/checker configured.

    Returns:
        dict with per-stage results under "shacl", "rules", "consistency" keys
        (only present for stages that were run), plus an aggregate "valid" flag.
    """
    results: dict[str, Any] = {}

    if shacl_validator is not None:
        results["shacl"] = SHACLValidationTool.handler(shacl_validator, store=store, run_id=run_id)

    if rules_engine is not None:
        results["rules"] = RulesEngineTool.handler(rules_engine, store=store)

    if consistency_checker is not None:
        results["consistency"] = ConsistencyCheckTool.handler(consistency_checker, store=store)

    shacl_valid = getattr(results.get("shacl"), "valid", True)
    rules_valid = not getattr(results.get("rules"), "rule_violations", [])
    consistency_valid = getattr(results.get("consistency"), "conflict_count", 0) == 0

    results["valid"] = bool(shacl_valid and rules_valid and consistency_valid)
    return results


KGValidationSkill = AgentSkill(
    name="kg_validation",
    description=(
        "Run SHACL shape validation, semantic rules, and consistency checking against the "
        "assembled KG, returning per-stage results and an aggregate pass/fail flag."
    ),
    handler=_kg_validation_handler,
)
