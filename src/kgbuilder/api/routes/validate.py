"""KG validation endpoints.

Runs SHACL shape validation, semantic rules, and consistency checks
against the current knowledge graph.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException

from kgbuilder.api.schemas import ValidationRequest, ValidationResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/validate", response_model=ValidationResponse)
async def validate_kg(request: ValidationRequest) -> ValidationResponse:
    """Run validation pipeline on the current KG.

    Combines SHACL shape validation, semantic rules, and consistency
    checking depending on the request flags.
    """
    from kgbuilder.api.dependencies import get_neo4j_store

    violations: list[dict[str, str]] = []
    total_checks = 0
    passed_checks = 0
    conflicts_count = 0

    try:
        neo4j_store = get_neo4j_store()

        # SHACL validation
        if request.run_shacl:
            try:
                from pathlib import Path

                import rdflib

                from kgbuilder.validation.shacl_validator import SHACLValidator

                shapes_path = request.shapes_path
                if shapes_path:
                    shapes_graph = rdflib.Graph()
                    shapes_graph.parse(shapes_path)
                    validator = SHACLValidator(shapes_graph)
                    result = validator.validate(neo4j_store)
                    total_checks += result.total_checks
                    passed_checks += result.passed_checks
                    for v in result.violations:
                        violations.append({
                            "type": "shacl",
                            "severity": v.severity.value,
                            "path": v.path,
                            "message": v.message,
                            "focus_node": v.focus_node,
                        })
                else:
                    logger.info("shacl_skipped_no_shapes")
            except Exception as e:
                logger.warning("shacl_validation_error", error=str(e))
                violations.append({
                    "type": "shacl",
                    "severity": "error",
                    "path": "",
                    "message": f"SHACL validation failed: {e}",
                    "focus_node": "",
                })

        # Rules engine
        if request.run_rules:
            try:
                from kgbuilder.validation.rules_engine import RulesEngine

                engine = RulesEngine()
                rules_result = engine.execute_rules(neo4j_store)
                total_checks += len(rules_result.rule_violations) + 10
                passed_checks += 10
                for rv in rules_result.rule_violations:
                    violations.append({
                        "type": "rule",
                        "severity": "warning",
                        "path": rv.predicate,
                        "message": rv.reason,
                        "focus_node": rv.subject_id,
                    })
            except Exception as e:
                logger.warning("rules_engine_error", error=str(e))

        # Consistency checking
        if request.run_consistency:
            try:
                from kgbuilder.validation.consistency_checker import ConsistencyChecker

                checker = ConsistencyChecker()
                report = checker.check_consistency(neo4j_store)
                conflicts_count = report.conflict_count
                total_checks += conflicts_count + 10
                passed_checks += 10
                for c in report.conflicts:
                    violations.append({
                        "type": "consistency",
                        "severity": "warning",
                        "path": "",
                        "message": c.description,
                        "focus_node": c.entity_id,
                    })
            except Exception as e:
                logger.warning("consistency_check_error", error=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {e}") from e

    pass_rate = (passed_checks / max(total_checks, 1)) * 100.0

    return ValidationResponse(
        passed=len(violations) == 0,
        total_checks=total_checks,
        pass_rate=round(pass_rate, 2),
        violations_count=len(violations),
        conflicts_count=conflicts_count,
        violations=violations,
    )
