"""Tests for the consolidated ontology validation report (SEMANTiCS 2026 Phase C)."""

from __future__ import annotations

from unittest.mock import MagicMock

from kgbuilder.validation.ontology_report import (
    OntologyValidationReport,
    OntologyValidationReportBuilder,
)


def _consistency_result(consistent=True, error=None, unsatisfiable=None):
    return MagicMock(
        consistent=consistent,
        error=error,
        reasoner="hermit",
        unsatisfiable_classes=unsatisfiable or [],
        to_dict=lambda: {"consistent": consistent},
    )


def _satisfiability_result(valid=True, error=""):
    return MagicMock(valid=valid, error=error, to_dict=lambda: {"valid": valid})


def _pitfall_result(pitfalls=None, source="oops_api"):
    return MagicMock(
        pitfalls=pitfalls or [], source=source, to_dict=lambda: {"pitfalls": pitfalls or []},
    )


class TestOntologyValidationReportBuilder:
    def test_build_runs_only_configured_checks(self) -> None:
        consistency_reasoner = MagicMock()
        consistency_reasoner.check_consistency.return_value = _consistency_result()

        builder = OntologyValidationReportBuilder(consistency_reasoner=consistency_reasoner)
        report = builder.build("onto.owl")

        assert report.consistency is not None
        assert report.shape_satisfiability is None
        assert report.pitfalls is None
        assert report.cq_coverage is None
        consistency_reasoner.check_consistency.assert_called_once_with("onto.owl")

    def test_build_runs_shape_satisfiability_only_when_shapes_path_given(self) -> None:
        static_validator = MagicMock()
        static_validator.check_satisfiability.return_value = _satisfiability_result()

        builder = OntologyValidationReportBuilder(static_validator=static_validator)

        report_without_shapes = builder.build("onto.owl")
        assert report_without_shapes.shape_satisfiability is None
        static_validator.check_satisfiability.assert_not_called()

        report_with_shapes = builder.build("onto.owl", shapes_path="shapes.ttl")
        assert report_with_shapes.shape_satisfiability is not None
        static_validator.check_satisfiability.assert_called_once()

    def test_build_runs_pitfall_scan(self) -> None:
        pitfall_detector = MagicMock()
        pitfall_detector.scan.return_value = _pitfall_result()

        report = OntologyValidationReportBuilder(pitfall_detector=pitfall_detector).build(
            "onto.owl"
        )

        assert report.pitfalls is not None
        pitfall_detector.scan.assert_called_once_with("onto.owl")

    def test_build_computes_cq_coverage_when_all_cq_resources_present(self) -> None:
        translator = MagicMock()
        runner = MagicMock()
        cq_result_ok = MagicMock(
            question_id="q1", translation=MagicMock(sparql="ASK {}"), passed=True, error=None,
        )
        cq_result_fail = MagicMock(
            question_id="q2", translation=MagicMock(sparql=None), passed=None,
            error="no translation",
        )
        runner.translate_and_run.side_effect = [cq_result_ok, cq_result_fail]
        questions = [MagicMock(question_id="q1"), MagicMock(question_id="q2")]

        builder = OntologyValidationReportBuilder(cq_translator=translator, cq_runner=runner)
        report = builder.build("onto.owl", competency_questions=questions, rdf_store=MagicMock())

        assert report.cq_coverage == 0.5
        assert len(report.cq_results) == 2

    def test_build_skips_cq_coverage_when_rdf_store_missing(self) -> None:
        translator = MagicMock()
        runner = MagicMock()

        builder = OntologyValidationReportBuilder(cq_translator=translator, cq_runner=runner)
        report = builder.build("onto.owl", competency_questions=[MagicMock()])

        assert report.cq_coverage is None
        runner.translate_and_run.assert_not_called()


class TestOntologyValidationReportOverallValid:
    def test_overall_valid_true_when_no_checks_configured(self) -> None:
        report = OntologyValidationReport(ontology_path="onto.owl")
        assert report.overall_valid is True

    def test_overall_valid_false_when_ontology_inconsistent(self) -> None:
        report = OntologyValidationReport(
            ontology_path="onto.owl", consistency=_consistency_result(consistent=False, error=None),
        )
        assert report.overall_valid is False

    def test_overall_valid_true_when_consistency_check_errored(self) -> None:
        report = OntologyValidationReport(
            ontology_path="onto.owl",
            consistency=_consistency_result(consistent=False, error="owlready2 not installed"),
        )
        assert report.overall_valid is True

    def test_overall_valid_false_when_shapes_unsatisfiable(self) -> None:
        report = OntologyValidationReport(
            ontology_path="onto.owl",
            shape_satisfiability=_satisfiability_result(valid=False, error=""),
        )
        assert report.overall_valid is False

    def test_overall_valid_ignores_pitfalls(self) -> None:
        report = OntologyValidationReport(
            ontology_path="onto.owl", pitfalls=_pitfall_result(pitfalls=[MagicMock()]),
        )
        assert report.overall_valid is True


class TestOntologyValidationReportRendering:
    def test_to_dict_includes_all_sections(self) -> None:
        report = OntologyValidationReport(
            ontology_path="onto.owl",
            consistency=_consistency_result(),
            shape_satisfiability=_satisfiability_result(),
            pitfalls=_pitfall_result(),
            cq_coverage=0.75,
        )

        as_dict = report.to_dict()

        assert as_dict["ontology_path"] == "onto.owl"
        assert as_dict["overall_valid"] is True
        assert as_dict["consistency"] == {"consistent": True}
        assert as_dict["cq_coverage"] == 0.75

    def test_to_markdown_renders_readable_summary(self) -> None:
        report = OntologyValidationReport(
            ontology_path="onto.owl",
            consistency=_consistency_result(consistent=True),
            pitfalls=_pitfall_result(pitfalls=[]),
            cq_coverage=1.0,
        )

        markdown = report.to_markdown()

        assert "onto.owl" in markdown
        assert "OWL DL Consistency" in markdown
        assert "Competency Question Coverage: 100.0%" in markdown
