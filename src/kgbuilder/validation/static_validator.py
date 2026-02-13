"""Static SHACL validation via SHACL2FOL theorem prover.

Wraps the SHACL2FOL Java tool (paolo7/SHACL2FOL) which translates SHACL
constraints into First-Order Logic and uses the Vampire theorem prover to
decide satisfiability, containment, and — critically — **static validation
under graph updates**.

Static validation answers: *"Will adding these nodes/edges ever violate
any SHACL constraint?"* **before** the update is applied.  This enables a
"pre-commit" validation gate in the KG construction pipeline.

Architecture:
    ┌──────────────────────────────────────────────┐
    │  Python  (StaticValidator)                   │
    │    ├─ convert entities/relations → actions    │
    │    ├─ write shapes.ttl + actions.json         │
    │    ├─ invoke SHACL2FOL JAR via subprocess     │
    │    └─ parse stdout → StaticValidationResult   │
    └──────────────────────────────────────────────┘

Modes supported by SHACL2FOL:
    1. ``satisfiability``  – Is the shape graph internally consistent?
    2. ``containment``     – Does shape A ⊆ shape B?
    3. ``validity``        – Does a concrete graph satisfy the shapes?
    4. ``staticValidation`` – Will a set of update *actions* preserve
       validity of a graph that currently satisfies the shapes?

We primarily use mode 4 (``staticValidation``).

Prerequisites:
    - Java 21+ runtime (``java`` on PATH)
    - Vampire theorem prover binary (Linux x86_64)
    - SHACL2FOL JAR (``SHACL2FOL.jar``)

References:
    - https://github.com/paolo7/SHACL2FOL
    - Ahmetaj et al. "SHACL Validation under Graph Updates" (arXiv:2508.00137, 2025)
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class StaticValidationResult:
    """Result of a static validation check.

    Attributes:
        valid: Whether the proposed updates preserve SHACL validity.
        mode: SHACL2FOL mode used (e.g. ``"staticValidation"``).
        raw_output: Full stdout from SHACL2FOL.
        duration_ms: Wall-clock time of the prover call.
        actions_checked: Number of update actions evaluated.
        counterexample: If invalid, textual description of a violation.
        error: Error message if the tool failed to run.
    """

    valid: bool = False
    mode: str = "staticValidation"
    raw_output: str = ""
    duration_ms: float = 0.0
    actions_checked: int = 0
    counterexample: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-friendly dict."""
        return {
            "valid": self.valid,
            "mode": self.mode,
            "duration_ms": round(self.duration_ms, 2),
            "actions_checked": self.actions_checked,
            "counterexample": self.counterexample,
            "error": self.error,
        }


@dataclass
class StaticValidatorConfig:
    """Configuration for the SHACL2FOL static validator.

    Attributes:
        jar_path: Path to ``SHACL2FOL.jar``.
        vampire_path: Path to the Vampire prover binary.
        java_bin: Java executable (must be ≥ 21).
        timeout_seconds: Max time for a single prover invocation.
        tptp_prefix: TPTP syntax prefix (``"fof"`` for Vampire).
        encode_una: Whether to encode the Unique Name Assumption.
        work_dir: Temporary directory for shapes/actions files.
    """

    jar_path: Path = Path("lib/SHACL2FOL.jar")
    vampire_path: Path = Path("lib/vampire")
    java_bin: str = "java"
    timeout_seconds: int = 120
    tptp_prefix: str = "fof"
    encode_una: bool = False
    work_dir: Path | None = None


# ---------------------------------------------------------------------------
# Static Validator
# ---------------------------------------------------------------------------

class StaticValidator:
    """Pre-commit SHACL validation using SHACL2FOL theorem prover.

    Given a set of SHACL shapes and a set of proposed graph updates
    (expressed as SHACL2FOL *actions*), determines whether the updates
    are guaranteed to preserve validity.

    The validator does **not** require materializing the full graph;
    it reasons over the shapes and actions symbolically.
    """

    def __init__(self, config: StaticValidatorConfig | None = None) -> None:
        """Initialize the static validator.

        Args:
            config: Validator configuration.  Uses defaults if ``None``.
        """
        self._config = config or StaticValidatorConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_satisfiability(self, shapes_path: Path) -> StaticValidationResult:
        """Check whether a SHACL shapes graph is internally satisfiable.

        Invokes SHACL2FOL in `satisfiability` mode and parses the result.
        """
        work_dir = Path(self._config.work_dir or Path.cwd())
        work_dir.mkdir(parents=True, exist_ok=True)
        self._write_config_properties(work_dir)

        proc = self._invoke_jar(shapes_path, None, mode="satisfiability", work_dir=work_dir)
        return self._parse_output(proc.stdout or "", mode="satisfiability")

    def check_containment(
        self,
        shapes_a_path: Path,
        shapes_b_path: Path,
    ) -> StaticValidationResult:
        """Check whether shape A is contained in shape B.

        Uses SHACL2FOL containment mode to decide whether A ⊆ B.
        """
        work_dir = Path(self._config.work_dir or Path.cwd())
        work_dir.mkdir(parents=True, exist_ok=True)
        self._write_config_properties(work_dir)

        # SHACL2FOL expects two shapes arguments for containment
        proc = self._invoke_jar(shapes_a_path, shapes_b_path, mode="containment", work_dir=work_dir)
        return self._parse_output(proc.stdout or "", mode="containment")

    def validate_static(
        self,
        shapes_path: Path,
        actions_path: Path,
    ) -> StaticValidationResult:
        """Static validation under graph updates (mode 'a').

        Invokes SHACL2FOL and parses the prover result.
        """
        work_dir = Path(self._config.work_dir or Path.cwd())
        work_dir.mkdir(parents=True, exist_ok=True)
        # Ensure config.properties present
        self._write_config_properties(work_dir)

        proc = self._invoke_jar(shapes_path, actions_path, mode="staticValidation", work_dir=work_dir)
        stdout = proc.stdout or ""
        result = self._parse_output(stdout, mode="staticValidation")
        return result

    def validate_entities_and_relations(
        self,
        shapes_path: Path,
        entities: list[Any],
        relations: list[Any],
        operation: str = "add",
        ontology_service: Any | None = None,
    ) -> StaticValidationResult:
        """Convert entities/relations to actions and run static validation.

        Args:
            shapes_path: Path to SHACL shapes file (Turtle).
            entities: List of extracted entities.
            relations: List of extracted relations.
            operation: Update operation to encode in actions ('add'|'remove'|'update').
            ontology_service: Optional ontology service passed through to the ActionConverter
                to enable inverse-action expansion and richer action generation.
        """
        if shapes_path is None:
            raise ValueError("shapes_path must be provided for static validation")

        from kgbuilder.validation.action_converter import ActionConverter

        converter = ActionConverter(ontology_service=ontology_service)
        actions = converter.from_entities_and_relations(entities or [], relations or [], operation=operation)

        # Write actions to temp file and invoke prover
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            actions_path = Path(td) / "actions.json"
            converter.write_json(actions, actions_path)
            return self.validate_static(shapes_path, actions_path)

    # ------------------------------------------------------------------
    # Health / setup checks
    # ------------------------------------------------------------------

    def check_prerequisites(self) -> dict[str, bool]:
        """Verify that Java, Vampire, and the JAR are available.

        Returns:
            Dict with keys ``java``, ``vampire``, ``jar`` mapping to
            availability booleans.
        """
        checks: dict[str, bool] = {}

        # Java 21+
        try:
            result = subprocess.run(
                [self._config.java_bin, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            checks["java"] = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            checks["java"] = False

        # Vampire binary
        checks["vampire"] = self._config.vampire_path.exists()

        # SHACL2FOL JAR
        checks["jar"] = self._config.jar_path.exists()

        logger.info("static_validator_prerequisites", **checks)
        return checks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _write_config_properties(self, work_dir: Path) -> Path:
        """Write a SHACL2FOL ``config.properties`` file.

        Args:
            work_dir: Directory to write the config file in.

        Returns:
            Path to the written config file.
        """
        config_path = work_dir / "config.properties"
        content = (
            f"proverPath={self._config.vampire_path.resolve()}\n"
            f"tptpPrefix={self._config.tptp_prefix}\n"
            f"encodeUNA={'true' if self._config.encode_una else 'false'}\n"
        )
        config_path.write_text(content)
        return config_path

    def _invoke_jar(
        self,
        shapes_path: Path,
        actions_path: Path | None,
        mode: str,
        work_dir: Path,
    ) -> subprocess.CompletedProcess[str]:
        """Invoke the SHACL2FOL JAR via subprocess and return CompletedProcess."""
        jar = self._config.jar_path
        if not jar.exists():
            raise FileNotFoundError(f"SHACL2FOL JAR not found at {jar}")

        cmd = [
            self._config.java_bin,
            "-jar",
            str(jar),
        ]
        # Map mode names to single-letter args expected by SHACL2FOL
        mode_map = {"satisfiability": "s", "containment": "c", "validity": "v", "staticValidation": "a"}
        arg0 = mode_map.get(mode, mode)
        cmd.append(arg0)
        cmd.append(str(shapes_path))
        if actions_path is not None:
            cmd.append(str(actions_path))

        env = None
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(work_dir),
                timeout=self._config.timeout_seconds,
                env=env,
            )
            return proc
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"SHACL2FOL invocation timed out: {e}") from e

    def _parse_output(self, stdout: str, mode: str) -> StaticValidationResult:
        """Parse SHACL2FOL stdout into a structured StaticValidationResult."""
        out = StaticValidationResult(mode=mode, raw_output=stdout)
        text = (stdout or "").lower()
        # Simple heuristics: look for VALID/INVALID or szs-style status
        if "valid" in text and "invalid" not in text:
            out.valid = True
        elif "invalid" in text:
            out.valid = False
        elif "szs status satisfiable" in text or "satisfiable" in text:
            out.valid = True
        elif "unsatisfiable" in text or "szs status unsatisfiable" in text:
            out.valid = False
        else:
            # Unknown — conservatively mark as invalid and include raw output
            out.valid = False
            out.error = "Could not parse prover output"

        # Attempt to capture a counterexample snippet
        if "counterexample" in text or "model" in text:
            out.counterexample = stdout.strip()[:200]

        return out
