"""Tests for CQ->SPARQL functional testing (SEMANTiCS 2026 Phase B: CQ4OE/MASEO pattern)."""

from __future__ import annotations

from unittest.mock import MagicMock

from kgbuilder.evaluation.cq_sparql import (
    CompetencyQuestionTranslator,
    CQSparqlResult,
    CQSparqlRunner,
    CQSparqlTranslation,
    compute_cq_translation_coverage,
)


def _make_question(
    question_id: str = "q1",
    text: str = "Does a Facility exist?",
    entity_class: str | None = "Facility",
):
    return MagicMock(question_id=question_id, text=text, entity_class=entity_class)


class TestCompetencyQuestionTranslator:
    def test_translate_extracts_ask_query_from_fenced_response(self) -> None:
        llm = MagicMock()
        llm.generate.return_value = (
            "Here you go:\n```sparql\nASK { ?f a <http://ex.org/Facility> }\n```"
        )

        translator = CompetencyQuestionTranslator(llm=llm, ontology_service=None)
        translation = translator.translate(_make_question())

        assert translation.sparql == "ASK { ?f a <http://ex.org/Facility> }"
        assert translation.query_type == "ask"
        assert translation.translation_error is None

    def test_translate_extracts_select_query_and_detects_type(self) -> None:
        llm = MagicMock()
        llm.generate.return_value = (
            "```sparql\nSELECT ?f WHERE { ?f a <http://ex.org/Facility> }\n```"
        )

        translator = CompetencyQuestionTranslator(llm=llm, ontology_service=None)
        translation = translator.translate(_make_question(text="Which facilities exist?"))

        assert translation.query_type == "select"
        assert "SELECT" in translation.sparql

    def test_translate_returns_none_sparql_when_llm_response_has_no_query(self) -> None:
        llm = MagicMock()
        llm.generate.return_value = "I'm not sure how to answer that."

        translator = CompetencyQuestionTranslator(llm=llm, ontology_service=None)
        translation = translator.translate(_make_question())

        assert translation.sparql is None
        assert translation.translation_error is not None

    def test_translate_handles_llm_failure_gracefully(self) -> None:
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("boom")

        translator = CompetencyQuestionTranslator(llm=llm, ontology_service=None)
        translation = translator.translate(_make_question())

        assert translation.sparql is None
        assert "boom" in translation.translation_error

    def test_translate_uses_ontology_class_uri_hint_when_available(self) -> None:
        llm = MagicMock()
        llm.generate.return_value = "```sparql\nASK { ?f a <http://ex.org/Facility> }\n```"
        ontology = MagicMock()
        ontology._resolve_class_uri.return_value = "http://ex.org/Facility"

        translator = CompetencyQuestionTranslator(llm=llm, ontology_service=ontology)
        translator.translate(_make_question())

        prompt_used = llm.generate.call_args[0][0]
        assert "http://ex.org/Facility" in prompt_used


class TestCQSparqlRunner:
    def test_run_executes_ask_query_and_reports_pass(self) -> None:
        translation = CQSparqlTranslation(
            question_id="q1",
            question_text="t",
            sparql="ASK { ?f a <http://ex.org/Facility> }",
            query_type="ask",
        )
        store = MagicMock()
        store.query_sparql.return_value = {"boolean": True}

        result = CQSparqlRunner().run(translation, store)

        assert result.executed is True
        assert result.passed is True
        assert result.error is None
        store.query_sparql.assert_called_once_with(translation.sparql)

    def test_run_executes_select_query_and_reports_pass_when_bindings_present(self) -> None:
        translation = CQSparqlTranslation(
            question_id="q1",
            question_text="t",
            sparql="SELECT ?f WHERE { ?f a ?t }",
            query_type="select",
        )
        store = MagicMock()
        store.query_sparql.return_value = {"results": {"bindings": [{"f": {"value": "x"}}]}}

        result = CQSparqlRunner().run(translation, store)

        assert result.passed is True
        assert len(result.bindings) == 1

    def test_run_reports_fail_when_select_has_no_bindings(self) -> None:
        translation = CQSparqlTranslation(
            question_id="q1",
            question_text="t",
            sparql="SELECT ?f WHERE { ?f a ?t }",
            query_type="select",
        )
        store = MagicMock()
        store.query_sparql.return_value = {"results": {"bindings": []}}

        result = CQSparqlRunner().run(translation, store)

        assert result.passed is False

    def test_run_is_noop_when_translation_failed(self) -> None:
        translation = CQSparqlTranslation(
            question_id="q1", question_text="t", sparql=None, translation_error="nope",
        )
        store = MagicMock()

        result = CQSparqlRunner().run(translation, store)

        assert result.executed is False
        assert result.passed is None
        store.query_sparql.assert_not_called()

    def test_run_captures_store_execution_error(self) -> None:
        translation = CQSparqlTranslation(
            question_id="q1", question_text="t", sparql="ASK { ?a ?b ?c }",
        )
        store = MagicMock()
        store.query_sparql.side_effect = RuntimeError("store unreachable")

        result = CQSparqlRunner().run(translation, store)

        assert result.executed is True
        assert result.passed is None
        assert "store unreachable" in result.error

    def test_translate_and_run_convenience_method(self) -> None:
        llm = MagicMock()
        llm.generate.return_value = "```sparql\nASK { ?a ?b ?c }\n```"
        translator = CompetencyQuestionTranslator(llm=llm, ontology_service=None)
        store = MagicMock()
        store.query_sparql.return_value = {"boolean": False}

        result = CQSparqlRunner().translate_and_run(_make_question(), store, translator)

        assert isinstance(result, CQSparqlResult)
        assert result.passed is False


class TestComputeCqTranslationCoverage:
    def test_coverage_is_zero_for_empty_results(self) -> None:
        assert compute_cq_translation_coverage([]) == 0.0

    def test_coverage_counts_only_successful_translations(self) -> None:
        ok = CQSparqlResult(
            question_id="q1",
            translation=CQSparqlTranslation(question_id="q1", question_text="t", sparql="ASK {}"),
        )
        failed = CQSparqlResult(
            question_id="q2",
            translation=CQSparqlTranslation(
                question_id="q2", question_text="t", sparql=None, translation_error="x",
            ),
        )

        assert compute_cq_translation_coverage([ok, failed]) == 0.5
