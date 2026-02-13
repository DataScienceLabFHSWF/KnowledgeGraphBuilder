"""Tests for SHACL2FOL static validator wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kgbuilder.validation.static_validator import (
    StaticValidationResult,
    StaticValidator,
    StaticValidatorConfig,
)


@pytest.fixture
def config(tmp_path: Path) -> StaticValidatorConfig:
    """Create a test config pointing at tmp_path."""
    return StaticValidatorConfig(
        jar_path=tmp_path / "SHACL2FOL.jar",
        vampire_path=tmp_path / "vampire",
        work_dir=tmp_path,
    )


@pytest.fixture
def validator(config: StaticValidatorConfig) -> StaticValidator:
    return StaticValidator(config)


class TestStaticValidatorConfig:
    """Test StaticValidatorConfig defaults."""

    def test_default_jar_path(self) -> None:
        cfg = StaticValidatorConfig()
        assert cfg.jar_path == Path("lib/SHACL2FOL.jar")

    def test_default_tptp_prefix(self) -> None:
        cfg = StaticValidatorConfig()
        assert cfg.tptp_prefix == "fof"

    def test_default_timeout(self) -> None:
        cfg = StaticValidatorConfig()
        assert cfg.timeout_seconds == 120


class TestStaticValidationResult:
    """Test StaticValidationResult dataclass."""

    def test_default_is_invalid(self) -> None:
        result = StaticValidationResult()
        assert result.valid is False

    def test_to_dict_keys(self) -> None:
        result = StaticValidationResult(valid=True, mode="satisfiability")
        d = result.to_dict()
        assert "valid" in d
        assert "mode" in d
        assert "duration_ms" in d
        assert d["valid"] is True


class TestStaticValidator:
    """Test suite for StaticValidator."""

    def test_init_uses_default_config(self) -> None:
        v = StaticValidator()
        assert v._config.jar_path == Path("lib/SHACL2FOL.jar")

    def test_check_prerequisites_missing_tools(
        self, validator: StaticValidator
    ) -> None:
        checks = validator.check_prerequisites()
        # JAR and vampire don't exist in tmp_path
        assert checks["jar"] is False
        assert checks["vampire"] is False

    @pytest.mark.skip(reason="validate_static() not yet implemented")
    def test_validate_static_valid_actions(
        self, validator: StaticValidator, tmp_path: Path
    ) -> None:
        shapes = tmp_path / "shapes.ttl"
        shapes.write_text("# empty shapes")
        actions = tmp_path / "actions.json"
        actions.write_text("[]")
        result = validator.validate_static(shapes, actions)
        assert isinstance(result, StaticValidationResult)

    @pytest.mark.skip(reason="validate_static() not yet implemented")
    def test_validate_static_returns_counterexample_on_invalid(
        self, validator: StaticValidator, tmp_path: Path
    ) -> None:
        # When prover finds violation, counterexample should be populated
        pass

    def test_write_config_properties(
        self, validator: StaticValidator, tmp_path: Path
    ) -> None:
        path = validator._write_config_properties(tmp_path)
        assert path.exists()
        content = path.read_text()
        assert "proverPath=" in content
        assert "tptpPrefix=fof" in content
