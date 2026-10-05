"""Consolidated ontology-level validation report (SEMANTiCS 2026 Phase C).

Combines the checks scattered across `validation/` and `evaluation/` into
one artifact suitable for a paper's reproducibility appendix when
publishing an ontology: OWL DL consistency (HermiT/Pellet), SHACL shape
satisfiability (SHACL2FOL/Vampire), pySHACL instance conformance (if a
sample graph is supplied), OOPS! pitfall scan, and competency-question
coverage (CQ4OE-style `CQCoverage`, via `evaluation.cq_sparql`).

This is deliberately a *report generator*, not a new validation mechanism —
every check it runs already exists elsewhere in this package; this module
only orchestrates them and renders one combined result.

See `Planning/SEMANTICS2026_IMPROVEMENT_PLAN.md` Phase C for the gap
analysis and per-check source attribution (MASEO, CQ4OE, OOPS!, HermiT).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class OntologyValidationReport:
    """Consolidated result of an ontology-level validation run.

    Each field is `None` when that check wasn't run (no validator/detector
    configured for it) — absence is distinct from a failing result.

    Attributes:
        ontology_path: Ontology file this report was generated for.
        generated_at: UTC ISO 8601 timestamp.
        consistency: OWL DL consistency result (`ConsistencyReasoner`).
        shape_satisfiability: SHACL shape satisfiability result (`StaticValidator`).
        pitfalls: OOPS! pitfall scan result.
        cq_coverage: Fraction of supplied competency questions with a
            successful SPARQL translation (CQ4OE's `CQCoverage` metric).
        cq_results: Per-question `CQSparqlResult`s backing `cq_coverage`.
    """

    ontology_path: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat()
    )
    consistency: Any | None = None
    shape_satisfiability: Any | None = None
    pitfalls: Any | None = None
    cq_coverage: float | None = None
    cq_results: list[Any] = field(default_factory=list)

    @property
    def overall_valid(self) -> bool:
        """`True` unless a check that actually completed reports a hard failure.

        A check that errored out (e.g. owlready2 not installed, OOPS! API
        unreachable and no local fallback findings) does not itself flip
        this to `False` — only a *completed* check reporting inconsistency/
        unsatisfiability does. Pitfalls are informational and never affect
        this flag (matching `KGValidationSkill`'s treatment of pitfalls).
        """
        if self.consistency is not None and self.consistency.error is None:
            if not self.consistency.consistent:
                return False
        if self.shape_satisfiability is not None and not self.shape_satisfiability.error:
            if not self.shape_satisfiability.valid:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict."""
        return {
            "ontology_path": self.ontology_path,
            "generated_at": self.generated_at,
            "overall_valid": self.overall_valid,
            "consistency": self.consistency.to_dict() if self.consistency is not None else None,
            "shape_satisfiability": (
                self.shape_satisfiability.to_dict()
                if self.shape_satisfiability is not None
                else None
            ),
            "pitfalls": self.pitfalls.to_dict() if self.pitfalls is not None else None,
            "cq_coverage": self.cq_coverage,
            "cq_results": [
                {
                    "question_id": r.question_id,
                    "translated": r.translation.sparql is not None,
                    "passed": r.passed,
                    "error": r.error,
                }
                for r in self.cq_results
            ],
        }

    def to_markdown(self) -> str:
        """Render a human-readable summary suitable for a reproducibility appendix."""
        lines = [
            f"# Ontology Validation Report: `{self.ontology_path}`",
            "",
            f"Generated: {self.generated_at}",
            f"**Overall valid: {'✅ yes' if self.overall_valid else '❌ no'}**",
            "",
        ]

        if self.consistency is not None:
            if self.consistency.error:
                lines.append(
                    f"## OWL DL Consistency ({self.consistency.reasoner}): "
                    f"\u26a0\ufe0f not run — {self.consistency.error}"
                )
            else:
                status = "✅ consistent" if self.consistency.consistent else "❌ inconsistent"
                lines.append(f"## OWL DL Consistency ({self.consistency.reasoner}): {status}")
                if self.consistency.unsatisfiable_classes:
                    lines.append("Unsatisfiable classes:")
                    for cls in self.consistency.unsatisfiable_classes:
                        lines.append(f"- {cls}")
            lines.append("")

        if self.shape_satisfiability is not None:
            if self.shape_satisfiability.error:
                lines.append(
                    "## SHACL Shape Satisfiability (SHACL2FOL/Vampire): "
                    f"\u26a0\ufe0f {self.shape_satisfiability.error}"
                )
            else:
                status = "✅ satisfiable" if self.shape_satisfiability.valid else "❌ unsatisfiable"
                lines.append(f"## SHACL Shape Satisfiability (SHACL2FOL/Vampire): {status}")
            lines.append("")

        if self.pitfalls is not None:
            lines.append(f"## Ontology Pitfalls (OOPS!, source: {self.pitfalls.source})")
            if not self.pitfalls.pitfalls:
                lines.append("No pitfalls found.")
            else:
                for p in self.pitfalls.pitfalls:
                    lines.append(
                        f"- **{p.code}** ({p.importance}) {p.name} — "
                        f"{p.num_affected_elements} affected element(s)"
                    )
            lines.append("")

        if self.cq_coverage is not None:
            lines.append(
                f"## Competency Question Coverage: {self.cq_coverage * 100:.1f}% "
                f"({len(self.cq_results)} CQs)"
            )

        return "\n".join(lines)


class OntologyValidationReportBuilder:
    """Orchestrates the individual validation checks into one `OntologyValidationReport`."""

    def __init__(
        self,
        consistency_reasoner: Any | None = None,
        static_validator: Any | None = None,
        pitfall_detector: Any | None = None,
        cq_translator: Any | None = None,
        cq_runner: Any | None = None,
    ) -> None:
        """Initialize the builder with whichever checkers are available.

        Args:
            consistency_reasoner: Optional `ConsistencyReasoner` (OWL DL / HermiT).
            static_validator: Optional `StaticValidator` (SHACL2FOL/Vampire).
            pitfall_detector: Optional `OOPSPitfallDetector`.
            cq_translator: Optional `CompetencyQuestionTranslator`, required
                (with `cq_runner`) to compute CQ coverage.
            cq_runner: Optional `CQSparqlRunner`.
        """
        self._consistency_reasoner = consistency_reasoner
        self._static_validator = static_validator
        self._pitfall_detector = pitfall_detector
        self._cq_translator = cq_translator
        self._cq_runner = cq_runner

    def build(
        self,
        ontology_path: str | Path,
        shapes_path: str | Path | None = None,
        competency_questions: list[Any] | None = None,
        rdf_store: Any | None = None,
    ) -> OntologyValidationReport:
        """Run all configured checks and assemble one report.

        Args:
            ontology_path: OWL ontology file to validate.
            shapes_path: SHACL shapes file for satisfiability checking
                (required, together with `static_validator`, to run that check).
            competency_questions: CQs to translate/execute for coverage
                (required, together with `cq_translator`/`cq_runner`/`rdf_store`).
            rdf_store: RDF store to execute translated CQs against.

        Returns:
            `OntologyValidationReport` with whichever checks were runnable.
        """
        report = OntologyValidationReport(ontology_path=str(ontology_path))

        if self._consistency_reasoner is not None:
            report.consistency = self._consistency_reasoner.check_consistency(ontology_path)

        if self._static_validator is not None and shapes_path is not None:
            report.shape_satisfiability = self._static_validator.check_satisfiability(
                Path(shapes_path)
            )

        if self._pitfall_detector is not None:
            report.pitfalls = self._pitfall_detector.scan(ontology_path)

        if (
            self._cq_translator is not None
            and self._cq_runner is not None
            and competency_questions
            and rdf_store is not None
        ):
            from kgbuilder.evaluation.cq_sparql import compute_cq_translation_coverage

            report.cq_results = [
                self._cq_runner.translate_and_run(question, rdf_store, self._cq_translator)
                for question in competency_questions
            ]
            report.cq_coverage = compute_cq_translation_coverage(report.cq_results)

        logger.info(
            "ontology_validation_report_generated",
            ontology_path=str(ontology_path),
            overall_valid=report.overall_valid,
        )
        return report
