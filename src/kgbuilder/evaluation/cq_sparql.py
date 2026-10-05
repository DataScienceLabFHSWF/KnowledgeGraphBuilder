"""Competency-question -> SPARQL functional testing (SEMANTiCS 2026 Phase B).

Translates a natural-language competency question (`ResearchQuestion`) into
an executable SPARQL ASK/SELECT query and runs it against the RDF store, so
"does the KG answer this CQ?" is checked by *executing a query*, not only by
an LLM judgment call. This is the functional-test pattern used throughout
the SEMANTiCS 2026 proceedings (CQ-to-SPARQL test generation, MASEO's
validation cascade) rather than string-similarity matching.

Sources / attribution
----------------------
- **CQ4OE benchmark** (OEG-UPM, Universidad Politécnica de Madrid) —
  ``CQCoverage`` (fraction of competency questions the ontology/KG can
  answer) is one of its six evaluation dimensions; the coverage metric name
  in this module is chosen to match theirs so results are comparable.
  Site: https://oeg-upm.github.io/cq4oe-benchmark/
  Leaderboard: https://oeg-upm.github.io/cq4oe-benchmark/leaderboard/
  HF dataset: `oeg/CQ4OE` · DOI: 10.5281/zenodo.20080309
- **MASEO** (Multi-Agent System for Explainable Ontology Generation,
  OEG-UPM) — CQ-to-SPARQL functional tests as one stage of its
  decompose -> generate -> validate -> repair cascade.
  Repo: https://github.com/oeg-upm/maseo (Apache-2.0)
  DOI: 10.5281/zenodo.19052003
- Both presented at SEMANTiCS 2026 (Ghent, 15-17 Sep 2026), IOS Press
  *Studies on the Semantic Web* vol. 63, doi:10.3233/SSW63 (CC BY 4.0).
  See `Planning/SEMANTICS2026_IMPROVEMENT_PLAN.md` Phase B / gap G5.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_SPARQL_FENCE_RE = re.compile(r"```(?:sparql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_TRANSLATION_PROMPT_TEMPLATE = """You are translating a competency question into \
a SPARQL query for an RDF knowledge graph.

Competency question: "{question_text}"
{class_hint}
Rules:
- If the question asks whether something exists or holds true, write a SPARQL ASK query.
- If the question asks "which/what/list ...", write a SPARQL SELECT query.
- Use only standard SPARQL 1.1 syntax. Do not invent prefixes that aren't declared.
- Return ONLY the SPARQL query, in a ```sparql ... ``` code fence. No explanation.
"""


@dataclass
class CQSparqlTranslation:
    """Result of translating one competency question into SPARQL.

    Attributes:
        question_id: `ResearchQuestion.question_id` this translation is for.
        question_text: The original natural-language question text.
        sparql: The translated SPARQL query string, or `None` if translation
            failed / the LLM declined to produce a usable query.
        query_type: `"ask"` or `"select"` (best-effort, sniffed from `sparql`).
        translation_error: Human-readable reason `sparql` is `None`, if so.
    """

    question_id: str
    question_text: str
    sparql: str | None
    query_type: str = "ask"
    translation_error: str | None = None


@dataclass
class CQSparqlResult:
    """Result of executing a translated CQ against the RDF store.

    Attributes:
        question_id: `ResearchQuestion.question_id` this result is for.
        translation: The `CQSparqlTranslation` that was executed (or attempted).
        executed: Whether a query was actually sent to the store (`False` if
            translation failed first).
        passed: `True`/`False` if the query executed successfully (ASK's
            boolean result, or "SELECT returned >= 1 binding" for SELECT);
            `None` if not executed or execution errored.
        bindings: Raw SPARQL result bindings (empty for ASK queries).
        execution_time_ms: Wall-clock query execution time.
        error: Execution error message, if any.
    """

    question_id: str
    translation: CQSparqlTranslation
    executed: bool = False
    passed: bool | None = None
    bindings: list[dict[str, Any]] = field(default_factory=list)
    execution_time_ms: float = 0.0
    error: str | None = None


class CompetencyQuestionTranslator:
    """Translates a `ResearchQuestion` into SPARQL, guided by the ontology.

    Uses `OntologyService` to resolve the question's `entity_class` to a
    full class URI (when available) as a hint in the translation prompt,
    the same ontology-grounding approach used elsewhere in this pipeline for
    extraction prompts.
    """

    def __init__(self, llm: Any, ontology_service: Any | None = None) -> None:
        """Initialize the translator.

        Args:
            llm: Any object exposing `generate(prompt, **kwargs) -> str`
                (see `core.protocols.LLMProvider`).
            ontology_service: Optional `OntologyService` used to resolve
                `entity_class` to a URI hint for the translation prompt.
        """
        self._llm = llm
        self._ontology = ontology_service

    def translate(self, question: Any) -> CQSparqlTranslation:
        """Translate one competency question into a SPARQL ASK/SELECT query.

        Args:
            question: A `ResearchQuestion` (or any object with `.question_id`,
                `.text`, and optionally `.entity_class`).

        Returns:
            `CQSparqlTranslation`. `sparql` is `None` (with `translation_error`
            set) if the LLM call fails or no SPARQL could be extracted from
            its response — callers should treat this as "not translatable"
            and fall back to another validation path, not as a hard error.
        """
        question_id = getattr(question, "question_id", "unknown")
        question_text = getattr(question, "text", str(question))
        entity_class = getattr(question, "entity_class", None)

        class_hint = ""
        if entity_class and self._ontology is not None:
            try:
                class_uri = self._resolve_class_uri(entity_class)
                if class_uri:
                    class_hint = f'The question concerns the ontology class <{class_uri}>.\n'
            except Exception as e:  # pragma: no cover - defensive, ontology lookups are best-effort
                logger.debug("cq_sparql_class_hint_failed", entity_class=entity_class, error=str(e))

        prompt = _TRANSLATION_PROMPT_TEMPLATE.format(
            question_text=question_text, class_hint=class_hint,
        )

        try:
            raw = self._llm.generate(prompt)
        except Exception as e:
            return CQSparqlTranslation(
                question_id=question_id,
                question_text=question_text,
                sparql=None,
                translation_error=f"LLM translation call failed: {e}",
            )

        sparql = self._extract_sparql(raw)
        if not sparql:
            return CQSparqlTranslation(
                question_id=question_id,
                question_text=question_text,
                sparql=None,
                translation_error="No SPARQL query found in LLM response",
            )

        query_type = "select" if re.search(r"\bSELECT\b", sparql, re.IGNORECASE) else "ask"
        return CQSparqlTranslation(
            question_id=question_id,
            question_text=question_text,
            sparql=sparql,
            query_type=query_type,
        )

    def _resolve_class_uri(self, entity_class: str) -> str | None:
        """Best-effort class URI lookup, tolerant of differing `OntologyService` implementations."""
        resolver = getattr(self._ontology, "_resolve_class_uri", None)
        if callable(resolver):
            return resolver(entity_class)
        return None

    @staticmethod
    def _extract_sparql(raw: str) -> str | None:
        """Pull the SPARQL query out of an LLM response (fenced or bare)."""
        if not raw:
            return None
        match = _SPARQL_FENCE_RE.search(raw)
        candidate = match.group(1).strip() if match else raw.strip()
        if not candidate or not re.search(r"\b(ASK|SELECT)\b", candidate, re.IGNORECASE):
            return None
        return candidate


class CQSparqlRunner:
    """Executes a translated CQ against an RDF store (`RDFStore.query_sparql`)."""

    def run(self, translation: CQSparqlTranslation, store: Any) -> CQSparqlResult:
        """Execute `translation.sparql` against `store`, if translation succeeded.

        Args:
            translation: Output of `CompetencyQuestionTranslator.translate`.
            store: Any object exposing `query_sparql(sparql) -> dict` (Fuseki
                response shape: `{"boolean": ...}` for ASK, `{"results":
                {"bindings": [...]}}` for SELECT — see `storage.rdf.RDFStore`).

        Returns:
            `CQSparqlResult`. `executed=False`/`passed=None` if `translation.sparql`
            is `None` (nothing to run — this is not an error, it means the
            question didn't translate cleanly and the caller should fall back
            to another validation path).
        """
        if translation.sparql is None:
            return CQSparqlResult(
                question_id=translation.question_id, translation=translation, executed=False,
            )

        start = time.perf_counter()
        try:
            raw_result = store.query_sparql(translation.sparql)
        except Exception as e:
            return CQSparqlResult(
                question_id=translation.question_id,
                translation=translation,
                executed=True,
                execution_time_ms=(time.perf_counter() - start) * 1000,
                error=str(e),
            )
        elapsed_ms = (time.perf_counter() - start) * 1000

        if translation.query_type == "ask":
            passed = bool(raw_result.get("boolean", False))
            bindings: list[dict[str, Any]] = []
        else:
            bindings = raw_result.get("results", {}).get("bindings", [])
            passed = len(bindings) > 0

        return CQSparqlResult(
            question_id=translation.question_id,
            translation=translation,
            executed=True,
            passed=passed,
            bindings=bindings,
            execution_time_ms=elapsed_ms,
        )

    def translate_and_run(
        self, question: Any, store: Any, translator: CompetencyQuestionTranslator,
    ) -> CQSparqlResult:
        """Convenience: translate then execute in one call."""
        return self.run(translator.translate(question), store)


def compute_cq_translation_coverage(results: list[CQSparqlResult]) -> float:
    """Fraction of results with a successful SPARQL translation.

    Named to match CQ4OE's **CQCoverage** dimension: the fraction of
    competency questions that could be translated/answered at all, as
    opposed to `passed`, which additionally requires the query to succeed
    against the current KG content.

    Args:
        results: `CQSparqlResult`s from one or more `CQSparqlRunner` runs.

    Returns:
        Fraction in [0.0, 1.0]; `0.0` for an empty `results` list.
    """
    if not results:
        return 0.0
    translated = sum(1 for r in results if r.translation.sparql is not None)
    return translated / len(results)
