import importlib
import pkgutil

import pytest

from kgbuilder import extraction, storage, enrichment, pipeline, analytics, document, validation, experiment

from kgbuilder.document.loaders.base import DocumentLoaderFactory
from kgbuilder.core.exceptions import UnsupportedFormatError
from pathlib import Path

from kgbuilder.pipeline.orchestrator import (
    BuildPipeline,
    BuildPipelineConfig,
    BuildPipelineResult,
    StoppingReason,
    KGBuildState,
)

from kgbuilder.analytics.pipeline import AnalyticsPipeline
from kgbuilder.storage.protocol import InMemoryGraphStore


# ---------------------------------------------------------------------------
# generic module import smoke test
# ---------------------------------------------------------------------------

def test_import_all_submodules():
    """Import every submodule under kgbuilder to execute top-level code.
    This catches syntax errors and drags many files into coverage.
    """
    import kgbuilder

    for finder, name, ispkg in pkgutil.walk_packages(kgbuilder.__path__, prefix=kgbuilder.__name__ + "."):
        # skip planning / scripts folders which are not packages but may appear
        if "Planning" in name or "scripts" in name:
            continue
        importlib.import_module(name)


# ---------------------------------------------------------------------------
# document loader factory
# ---------------------------------------------------------------------------

class DummyLoader:
    def __init__(self):
        self.supported_extensions = [".foo"]

    def load(self, path: Path):
        return "loaded"


def test_document_loader_factory_registration(monkeypatch):
    # register dummy loader and ensure lookup works
    DocumentLoaderFactory._loaders.clear()
    DocumentLoaderFactory.register(DummyLoader)
    loader = DocumentLoaderFactory.get_loader(Path("test.foo"))
    assert isinstance(loader, DummyLoader)
    assert loader.load(Path("test.foo")) == "loaded"
    with pytest.raises(UnsupportedFormatError):
        DocumentLoaderFactory.get_loader(Path("x.bar"))


# ---------------------------------------------------------------------------
# build pipeline basics
# ---------------------------------------------------------------------------

def test_build_pipeline_config_and_summary():
    cfg = BuildPipelineConfig()
    # should initialize with default stopping criteria that validates
    pipeline_obj = BuildPipeline(cfg)
    # run with no documents/qs should behave gracefully
    res: BuildPipelineResult = pipeline_obj.run(documents=[], competency_questions=[])
    assert isinstance(res, BuildPipelineResult)
    summary = res.get_summary_string()
    assert "Build Pipeline Result" in summary
    assert res.stopping_reason in list(StoppingReason)


# ---------------------------------------------------------------------------
# analytics pipeline
# ---------------------------------------------------------------------------

def test_analytics_pipeline_run():
    store = InMemoryGraphStore()
    pipeline = AnalyticsPipeline(store, ontology_service=None, enable_inference=False, enable_skos=False)
    result = pipeline.run()
    assert result.status == "success"
    assert result.metrics_before is not None
    assert result.metrics_after is not None


def test_build_pipeline_iteration_error():
    # subclass build pipeline to simulate extraction failure
    class FailingPipeline(BuildPipeline):
        def _extraction_step(self, documents, iteration, kg_state):
            raise RuntimeError("boom")
    cfg = BuildPipelineConfig(max_iterations=2)
    pip = FailingPipeline(cfg)
    res = pip.run(documents=["doc"])
    # should record at least one iteration with an error
    assert len(res.iterations) >= 1
    assert any(it.errors for it in res.iterations)


def test_build_pipeline_stopping_logic():
    # criteria set low to trigger immediate stop
    cfg = BuildPipelineConfig()
    # ensure stopping_criteria exists
    if cfg.stopping_criteria is None:
        from kgbuilder.pipeline.stopping_criterion import StoppingCriteria

        cfg.stopping_criteria = StoppingCriteria(min_entity_count=0, require_all=False)
    else:
        cfg.stopping_criteria.min_entity_count = 0
        cfg.stopping_criteria.require_all = False

    pip = BuildPipeline(cfg)
    res = pip.run(documents=[], competency_questions=[])
    # we can't easily predict stopping behavior with dummy data, but the
    # pipeline should execute at least one iteration and return a result.
    assert res.total_iterations >= 1


def test_analytics_pipeline_with_inference_and_skos(monkeypatch):
    store = InMemoryGraphStore()
    # supply dummy ontology service so both engines are created
    class DummyOntology:
        pass

    pipeline = AnalyticsPipeline(store, ontology_service=DummyOntology(), enable_inference=True, enable_skos=True)
    # replace inference engine with stub that returns predictable stats
    class StubEngine:
        def run_full_inference(self):
            return {"symmetric": 1, "inverse": 2}
    pipeline.inference_engine = StubEngine()
    # replace skos enricher with stub that logs
    class StubSkos:
        pass
    pipeline.skos_enricher = StubSkos()

    result = pipeline.run()
    assert result.status == "success"
    assert result.inference_enabled and result.inference_stats
    assert result.skos_enabled


def test_analytics_generate_report():
    store = InMemoryGraphStore()
    pipeline = AnalyticsPipeline(store, ontology_service=None, enable_inference=False, enable_skos=False)
    # status attribute normally set during run
    pipeline.status = "success"
    report = pipeline.generate_report()
    assert "Analytics Pipeline Report" in report


def test_skos_enricher_warning(monkeypatch, caplog):
    from kgbuilder.analytics.skos import SKOSEnricher

    enr = SKOSEnricher(ontology_service=None)
    caplog.set_level("WARNING")
    assert enr.enrich_entity("e", "label") is None
    assert "skos_enricher_no_ontology_service" in caplog.text


def test_skos_enricher_with_concepts(monkeypatch):
    from kgbuilder.analytics.skos import SKOSEnricher, SKOSMapping

    enr = SKOSEnricher(ontology_service=object())
    # stub query to return one concept
    monkeypatch.setattr(enr, "_query_skos_concepts", lambda label, t=None: [
        {"uri": "u", "prefLabel": label, "altLabels": [], "broader": [], "narrower": []}
    ])
    mapping = enr.enrich_entity("id", "Foo")
    assert isinstance(mapping, SKOSMapping)
    assert mapping.confidence >= 0.0
    # directly test confidence calculator returns float and >0
    conf = enr._compute_mapping_confidence("Foo", mapping.skos_concepts)
    assert isinstance(conf, float)
    assert conf >= 0.0

