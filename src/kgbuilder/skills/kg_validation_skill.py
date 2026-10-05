"""Post-assembly KG validation skill: SHACL + rules + consistency checking.

Mirrors the logic in `api.routes.validate`, expressed as a reusable skill so
`PipelineAgent`/`LangChainReactAgent` plans can invoke the same validation
stage the FastAPI route already exposes. Also composes the ontology-level
checks added in SEMANTiCS 2026 Phase C (OWL DL consistency via HermiT/Pellet,
OOPS! pitfall scanning) — see `Planning/SEMANTICS2026_IMPROVEMENT_PLAN.md`.
"""

from __future__ import annotations

from typing import Any

from kgbuilder.skills.base import AgentSkill
from kgbuilder.tools.kg_validation_tools import (
    ConsistencyCheckTool,
    OntologyConsistencyReasoningTool,
    OntologyPitfallScanTool,
    RulesEngineTool,
    SHACLValidationTool,
)


def _kg_validation_handler(
    store: Any,
    shacl_validator: Any | None = None,
    rules_engine: Any | None = None,
    consistency_checker: Any | None = None,
    consistency_reasoner: Any | None = None,
    pitfall_detector: Any | None = None,
    ontology_path: Any | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run whichever validation stages have a validator/checker configured.

    `consistency_reasoner` and `pitfall_detector` operate on the ontology
    *file* (`ontology_path`), not the KG instance data in `store` — pass
    `ontology_path` when either is supplied.

    Returns:
        dict with per-stage results under "shacl", "rules", "consistency",
        "ontology_consistency", "pitfalls" keys (only present for stages that
        were run), plus an aggregate "valid" flag. Pitfall findings are
        informational and do not affect "valid" — only hard consistency/
        conformance failures do.
    """
    results: dict[str, Any] = {}
    if (consistency_reasoner is not None or pitfall_detector is not None) and ontology_path is None:
        raise ValueError("ontology_path is required for configured ontology checks")

    if shacl_validator is not None:
        results["shacl"] = SHACLValidationTool.execute(
            shacl_validator=shacl_validator, store=store, run_id=run_id
        )

    if rules_engine is not None:
        results["rules"] = RulesEngineTool.execute(rules_engine=rules_engine, store=store)

    if consistency_checker is not None:
        results["consistency"] = ConsistencyCheckTool.execute(
            consistency_checker=consistency_checker, store=store
        )

    if consistency_reasoner is not None and ontology_path is not None:
        results["ontology_consistency"] = OntologyConsistencyReasoningTool.execute(
            consistency_reasoner=consistency_reasoner,
            ontology_path=ontology_path,
        )

    if pitfall_detector is not None and ontology_path is not None:
        results["pitfalls"] = OntologyPitfallScanTool.execute(
            pitfall_detector=pitfall_detector,
            ontology_path=ontology_path,
        )

    shacl_valid = getattr(results.get("shacl"), "valid", True)
    rules_valid = not getattr(results.get("rules"), "rule_violations", [])
    consistency_valid = getattr(results.get("consistency"), "conflict_count", 0) == 0
    ontology_consistency_result = results.get("ontology_consistency")
    ontology_consistent = (
        ontology_consistency_result.error is None and ontology_consistency_result.consistent
        if ontology_consistency_result is not None
        else True
    )

    results["valid"] = bool(
        shacl_valid and rules_valid and consistency_valid and ontology_consistent
    )
    return results


KGValidationSkill = AgentSkill(
    name="kg_validation",
    description=(
        "Run SHACL shape validation, semantic rules, and consistency checking against the "
        "assembled KG, returning per-stage results and an aggregate pass/fail flag."
    ),
    handler=_kg_validation_handler,
)
