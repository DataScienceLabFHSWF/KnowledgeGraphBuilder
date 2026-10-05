"""Regression tests for safe publication of benchmark aggregates."""

from __future__ import annotations

from scripts.publish_extraction_reports import public_summary


def test_public_summary_omits_source_predictions_errors_and_connection_details() -> None:
    report = {
        "run": {
            "llm_model": "test",
            "dataset_sha256": "123",
            "api_key": "private-key",
            "base_url": "http://private-host",
        },
        "dataset": {"name": "development", "description": "private source text"},
        "aggregate": {"errors": 2, "triple_metrics": {"f1": 0.5}},
        "trials": [{"predictions": {"evidence": "private quote"}}],
        "unlabeled_corpus_probe": {
            "documents": ["/private/source.pdf"],
            "errors": [{"message": "private quote in error"}],
            "passages_processed": 1,
            "trials": [
                {
                    "predictions": {"triples": ["private quote"]},
                    "usage": [{"total_tokens": 7}],
                }
            ],
        },
    }
    summary = public_summary(report)
    assert "private" not in str(summary)
    assert summary["aggregate"]["errors"] == 2
    assert summary["unlabeled_corpus_probe"]["tokens"] == 7
    assert summary["unlabeled_corpus_probe"]["error_count"] == 1
    assert "trials" not in summary


def test_public_summary_preserves_unknown_corpus_token_usage() -> None:
    summary = public_summary(
        {
            "run": {},
            "dataset": {},
            "aggregate": {},
            "unlabeled_corpus_probe": {"trials": [{"usage": []}]},
        }
    )
    assert summary["unlabeled_corpus_probe"]["tokens"] is None
