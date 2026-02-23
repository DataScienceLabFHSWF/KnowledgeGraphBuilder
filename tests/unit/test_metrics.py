import pytest

import numpy as np

from kgbuilder.analytics.metrics import GraphMetrics, GraphMetricsSnapshot
from kgbuilder.analytics.pipeline import AnalyticsPipelineResult


class DummyStore:
    pass


def test_graphmetrics_methods_return_zero():
    gm = GraphMetrics(DummyStore())
    # private counters should all exist and return 0
    assert gm._count_nodes() == 0
    assert gm._count_edges() == 0
    assert gm._count_relations() == 0
    assert gm._count_typed_nodes() == 0
    assert gm._count_orphan_nodes() == 0
    assert gm._compute_average_degree() == 0.0
    assert gm._compute_max_degree() == 0
    assert gm._count_hub_nodes(1.5) == 0
    assert gm._count_missing_descriptions() == 0
    assert gm._count_missing_types() == 0
    assert gm._count_orphan_entities() == 0
    assert gm._count_unique_predicates() == 0
    assert gm._get_predicate_distribution() == []
    assert gm._check_constraint_satisfaction(object()) == {"total": 0, "satisfied": 0, "rate": 0.0}

    snap = gm.compute_metrics(None)
    # snapshot fields should equal zeros and duration present
    assert isinstance(snap, GraphMetricsSnapshot)
    assert snap.total_nodes == 0
    assert snap.duration_seconds >= 0


def test_graphmetrics_compute_with_custom_counts(monkeypatch):
    class CustomMetrics(GraphMetrics):
        def _count_nodes(self):
            return 5
        def _count_edges(self):
            return 3
        def _count_relations(self):
            return 2
        def _count_typed_nodes(self):
            return 4
        def _count_orphan_nodes(self):
            return 1
        def _compute_average_degree(self):
            return 1.2
        def _compute_max_degree(self):
            return 3
        def _count_hub_nodes(self, avg):
            return 0
        def _count_missing_descriptions(self):
            return 0
        def _count_missing_types(self):
            return 0
        def _count_orphan_entities(self):
            return 0
        def _count_unique_predicates(self):
            return 2
        def _get_predicate_distribution(self, top_k=10):
            return [("p", 2)]

    gm = CustomMetrics(DummyStore())
    snap = gm.compute_metrics(None)
    assert snap.total_nodes == 5
    assert snap.total_edges == 3
    assert snap.typed_percentage == pytest.approx(100 * 4 / 5)
    assert snap.unique_predicates == 2


def test_graphmetrics_exception_handling(monkeypatch):
    class BadMetrics(GraphMetrics):
        def _count_nodes(self):
            raise RuntimeError("boom")
    gm = BadMetrics(DummyStore())
    snap = gm.compute_metrics(None)
    assert "Error during computation" in snap.notes
