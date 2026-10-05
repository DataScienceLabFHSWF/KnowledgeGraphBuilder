"""OWL DL consistency reasoning via HermiT (SEMANTiCS 2026 Phase C, gap G2).

Checks whether an OWL ontology is logically consistent — i.e. whether any
class is *unsatisfiable* (provably has no possible instances) under OWL DL
semantics. This is a different, complementary check to
`validation.static_validator.StaticValidator` (which validates *SHACL
shapes* derived from the ontology, not the ontology's own DL consistency)
and to `validation.shacl_validator.SHACLValidator` (which checks instance
*data* against shapes).

Uses `owlready2`, which bundles the HermiT and Pellet reasoners as Java
JARs and invokes them via subprocess — no separate JAR download needed
(unlike SHACL2FOL/Vampire), but a Java runtime must be on PATH (already
required by `StaticValidator`).

Optional dependency: ``pip install -e ".[reasoning]"`` (owlready2).

Sources / attribution
----------------------
- **MASEO** (Multi-Agent System for Explainable Ontology Generation,
  OEG-UPM) — its Logical Consistency Agent uses HermiT to repair
  inconsistencies as one stage of a decompose -> generate -> validate ->
  repair cascade; this module provides the *check* half of that pattern.
  Repo: https://github.com/oeg-upm/maseo (Apache-2.0) · doi:10.5281/zenodo.19052003
- **HermiT** reasoner: http://www.hermit-reasoner.com/
- Presented at SEMANTiCS 2026 (Ghent, 15-17 Sep 2026), IOS Press
  *Studies on the Semantic Web* vol. 63, doi:10.3233/SSW63 (CC BY 4.0).
  See `Planning/SEMANTICS2026_IMPROVEMENT_PLAN.md` Phase C / gap G2.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ConsistencyCheckResult:
    """Result of an OWL DL consistency check.

    Attributes:
        consistent: Whether the ontology is logically consistent (no
            unsatisfiable classes). `False` if the check could not run at
            all (see `error`) — callers should treat that as "unknown",
            not "inconsistent"; check `error` before trusting `consistent`.
        unsatisfiable_classes: Names/IRIs of classes HermiT proved have no
            possible instances. Empty when `consistent` is `True`.
        reasoner: Which reasoner produced this result (`"hermit"` or `"pellet"`).
        duration_ms: Wall-clock reasoning time.
        error: Set if the check could not be completed (owlready2 missing,
            ontology failed to load, reasoner invocation failed). When set,
            `consistent`/`unsatisfiable_classes` are not meaningful.
    """

    consistent: bool
    unsatisfiable_classes: list[str] = field(default_factory=list)
    reasoner: str = "hermit"
    duration_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "consistent": self.consistent,
            "unsatisfiable_classes": self.unsatisfiable_classes,
            "reasoner": self.reasoner,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
        }


class ConsistencyReasoner:
    """Checks OWL DL consistency of an ontology file via HermiT or Pellet.

    Each call loads the ontology into a fresh, isolated `owlready2.World()`
    so concurrent/repeated checks (e.g. one per KG build) don't share state
    or leak memory across calls.
    """

    def __init__(self, reasoner: str = "hermit") -> None:
        """Initialize the reasoner wrapper.

        Args:
            reasoner: `"hermit"` (default) or `"pellet"` — both are bundled
                with owlready2.
        """
        if reasoner not in ("hermit", "pellet"):
            raise ValueError(f"Unsupported reasoner '{reasoner}'; use 'hermit' or 'pellet'")
        self._reasoner = reasoner

    def check_consistency(self, ontology_path: str | Path) -> ConsistencyCheckResult:
        """Check whether the OWL ontology at `ontology_path` is DL-consistent.

        Args:
            ontology_path: Path to an OWL/RDF ontology file (any format
                `owlready2`/rdflib can parse — RDF/XML, Turtle, ...).

        Returns:
            `ConsistencyCheckResult`. Never raises — failures are reported
            via `error` so callers can degrade gracefully (this check is
            optional/feature-flagged, matching `StaticValidator`).
        """
        try:
            import owlready2
        except ImportError as e:
            return ConsistencyCheckResult(
                consistent=False,
                reasoner=self._reasoner,
                error=(
                    "owlready2 is not installed. Install with "
                    "`pip install -e '.[reasoning]'` to enable HermiT/Pellet "
                    f"consistency checking. ({e})"
                ),
            )

        path = Path(ontology_path).resolve()
        if not path.exists():
            return ConsistencyCheckResult(
                consistent=False, reasoner=self._reasoner, error=f"Ontology file not found: {path}",
            )

        start = time.perf_counter()
        world = owlready2.World()
        try:
            onto = world.get_ontology(f"file://{path}").load()
        except Exception as e:
            return ConsistencyCheckResult(
                consistent=False,
                reasoner=self._reasoner,
                error=f"Failed to load ontology: {e}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        if self._reasoner == "pellet":
            sync_fn = owlready2.sync_reasoner_pellet
        else:
            sync_fn = owlready2.sync_reasoner_hermit
        try:
            with onto:
                sync_fn(world, infer_property_values=False, debug=0)
        except Exception as e:
            return ConsistencyCheckResult(
                consistent=False,
                reasoner=self._reasoner,
                error=f"Reasoner invocation failed: {e}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        unsatisfiable = [str(cls) for cls in world.inconsistent_classes()]
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "consistency_check_complete",
            reasoner=self._reasoner,
            consistent=len(unsatisfiable) == 0,
            unsatisfiable_count=len(unsatisfiable),
            duration_ms=round(duration_ms, 2),
        )

        return ConsistencyCheckResult(
            consistent=len(unsatisfiable) == 0,
            unsatisfiable_classes=unsatisfiable,
            reasoner=self._reasoner,
            duration_ms=duration_ms,
        )
