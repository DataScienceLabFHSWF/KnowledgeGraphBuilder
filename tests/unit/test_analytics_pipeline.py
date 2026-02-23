import pytest
from types import SimpleNamespace

from kgbuilder.analytics.pipeline import (
    AnalyticsPipeline,
    AnalyticsPipelineResult,
)


class DummyMetrics:
    def __init__(self):
        self.calls = []

    def compute_metrics(self, ontology_service):
        self.calls.append(ontology_service)
        # return a simple snapshot-like object with required attributes
        return SimpleNamespace(
            total_nodes=10,
            total_edges=5,
            typed_percentage=0.5,
        )


class DummyInference:
    def __init__(self, graph_store, ontology_service):
        pass

    def run_full_inference(self):
        return {"inferred": 3}


def test_result_dataclass_defaults():
    res = AnalyticsPipelineResult()
    assert res.status == "pending"
    assert res.total_duration_seconds == 0.0


def test_pipeline_basic(monkeypatch):
    # don't use real graph store or ontology
    gp = object()
    ont = object()

    monkeypatch.setattr(
        "kgbuilder.analytics.pipeline.GraphMetrics",
        lambda gs: DummyMetrics(),
    )
    # disable inference/skos by not providing ontology_service
    pipeline = AnalyticsPipeline(graph_store=gp, ontology_service=None, enable_inference=False, enable_skos=False)
    result = pipeline.run()
    assert result.status == "success"
    assert result.metrics_before is not None
    assert result.metrics_after is not None
    assert result.inference_enabled is False
    assert result.skos_enabled is False


def test_pipeline_with_inference_and_skos(monkeypatch):
    gp = object()
    ont = object()
    monkeypatch.setattr(
        "kgbuilder.analytics.pipeline.GraphMetrics",
        lambda gs: DummyMetrics(),
    )
    monkeypatch.setattr(
        "kgbuilder.analytics.pipeline.Neo4jInferenceEngine",
        DummyInference,
    )
    # use dummy skos enricher that just logs calls
    class DummySKOS:
        def __init__(self, ont):
            pass
    monkeypatch.setattr("kgbuilder.analytics.pipeline.SKOSEnricher", DummySKOS)

    pipeline = AnalyticsPipeline(graph_store=gp, ontology_service=ont, enable_inference=True, enable_skos=True)
    result = pipeline.run()
    assert result.status == "success"
    assert result.inference_enabled
    assert result.inference_stats == {"inferred": 3}
    assert result.skos_enabled
    # ensure summary logging doesn't error


def test_pipeline_handles_metric_failure(monkeypatch):
    gp = object()
    ont = object()

    class BadMetrics(DummyMetrics):
        def compute_metrics(self, ontology_service):
            raise RuntimeError("fail")

    monkeypatch.setattr(
        "kgbuilder.analytics.pipeline.GraphMetrics",
        lambda gs: BadMetrics(),
    )

    pipeline = AnalyticsPipeline(graph_store=gp, ontology_service=ont, enable_inference=False, enable_skos=False)
    result = pipeline.run()
    assert result.status == "failed"
    assert "fail" in result.error_message
