"""Tests for the post-assembly validation tools/skill (SHACL, rules, consistency, static)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from kgbuilder.skills.kg_validation_skill import KGValidationSkill
from kgbuilder.tools.kg_validation_tools import (
    ConsistencyCheckTool,
    RulesEngineTool,
    SHACLValidationTool,
)
from kgbuilder.tools.relation_extraction_tool import RelationExtractionTool
from kgbuilder.tools.static_validation_tool import StaticValidationTool


def test_relation_extraction_tool_delegates_to_extractor() -> None:
    extractor = MagicMock()
    extractor.extract.return_value = ["rel1"]

    result = RelationExtractionTool.handler(
        extractor, text="text", entities=["e1"], ontology_relations=["r1"]
    )

    assert result == ["rel1"]
    extractor.extract.assert_called_once_with(text="text", entities=["e1"], ontology_relations=["r1"])


def test_static_validation_tool_delegates_to_static_validator() -> None:
    validator = MagicMock()
    validator.validate_entities_and_relations.return_value = "sv-result"

    result = StaticValidationTool.handler(
        validator, shapes_path="shapes.ttl", entities=["e1"], relations=["r1"], ontology_service="onto"
    )

    assert result == "sv-result"
    validator.validate_entities_and_relations.assert_called_once_with(
        Path("shapes.ttl"), ["e1"], ["r1"], ontology_service="onto"
    )


def test_shacl_rules_consistency_tools_delegate() -> None:
    shacl_validator = MagicMock()
    shacl_validator.validate.return_value = "shacl-result"
    rules_engine = MagicMock()
    rules_engine.execute_rules.return_value = "rules-result"
    consistency_checker = MagicMock()
    consistency_checker.check_consistency.return_value = "consistency-result"
    store = MagicMock()

    assert SHACLValidationTool.handler(shacl_validator, store=store, run_id="run-1") == "shacl-result"
    shacl_validator.validate.assert_called_once_with(store, run_id="run-1")

    assert RulesEngineTool.handler(rules_engine, store=store) == "rules-result"
    rules_engine.execute_rules.assert_called_once_with(store)

    assert ConsistencyCheckTool.handler(consistency_checker, store=store) == "consistency-result"
    consistency_checker.check_consistency.assert_called_once_with(store)


def test_kg_validation_skill_aggregates_valid_when_all_pass() -> None:
    store = MagicMock()

    shacl_validator = MagicMock()
    shacl_validator.validate.return_value = MagicMock(valid=True)

    rules_engine = MagicMock()
    rules_engine.execute_rules.return_value = MagicMock(rule_violations=[])

    consistency_checker = MagicMock()
    consistency_checker.check_consistency.return_value = MagicMock(conflict_count=0)

    result = KGValidationSkill.handler(
        store=store,
        shacl_validator=shacl_validator,
        rules_engine=rules_engine,
        consistency_checker=consistency_checker,
    )

    assert result["valid"] is True
    assert set(result.keys()) == {"shacl", "rules", "consistency", "valid"}


def test_kg_validation_skill_fails_when_consistency_has_conflicts() -> None:
    store = MagicMock()

    consistency_checker = MagicMock()
    consistency_checker.check_consistency.return_value = MagicMock(conflict_count=3)

    result = KGValidationSkill.handler(store=store, consistency_checker=consistency_checker)

    assert result["valid"] is False
    assert "shacl" not in result
    assert "rules" not in result
