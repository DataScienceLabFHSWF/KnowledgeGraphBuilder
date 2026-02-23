import sys
import types
from pathlib import Path

# ensure package import works
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import pytest
from datetime import datetime, timedelta

from kgbuilder.analytics.metrics import GraphMetrics, GraphMetricsSnapshot


class DummyGraphStore:
    pass


class SampleMetrics(GraphMetrics):
    """GraphMetrics subclass that returns hard-coded values for easier testing."""

    def _count_nodes(self) -> int:
        return 100

    def _count_edges(self) -> int:
        return 200

    def _count_relations(self) -> int:
        return 50

    def _count_typed_nodes(self) -> int:
        return 80

    def _count_orphan_nodes(self) -> int:
        return 10

    def _compute_average_degree(self) -> float:
        return 4.0

    def _compute_max_degree(self) -> int:
        return 20

    def _count_hub_nodes(self, avg_degree: float) -> int:
        # expect avg_degree == 4.0
        return 5

    def _count_missing_descriptions(self) -> int:
        return 7

    def _count_missing_types(self) -> int:
        return 3

    def _count_orphan_entities(self) -> int:
        return 2

    def _count_unique_predicates(self) -> int:
        return 15

    def _get_predicate_distribution(self, top_k: int = 10) -> list[tuple[str, int]]:
        return [("relA", 20), ("relB", 10)]

    def _check_constraint_satisfaction(self, ontology_service: object) -> dict[str, float | int]:
        return {"total": 40, "satisfied": 30, "rate": 0.75}


def test_compute_metrics_basic() -> None:
    gm = SampleMetrics(graph_store=DummyGraphStore())
    snap = gm.compute_metrics()
    # derived values
    assert snap.total_nodes == 100
    assert snap.total_edges == 200
    assert snap.total_relations == 50
    assert snap.typed_nodes == 80
    assert snap.typed_percentage == pytest.approx(80.0)  # 80/100 * 100
    assert snap.orphan_nodes == 10
    assert snap.average_degree == 4.0
    assert snap.max_degree == 20
    assert snap.hub_nodes == 5
    assert snap.missing_descriptions == 7
    assert snap.missing_types == 3
    assert snap.orphan_entities == 2
    assert snap.unique_predicates == 15
    assert snap.most_common_predicates == [("relA", 20), ("relB", 10)]
    # constraint fields should be zero since no ontology_service passed
    assert snap.relations_with_domain_range == 0
    assert snap.relations_satisfying_constraints == 0
    assert snap.constraint_satisfaction_rate == 0.0
    assert isinstance(snap.duration_seconds, float)
    assert isinstance(snap.timestamp, datetime)


def test_compute_metrics_with_ontology() -> None:
    gm = SampleMetrics(graph_store=DummyGraphStore())
    ontology = object()
    snap = gm.compute_metrics(ontology_service=ontology)
    assert snap.relations_with_domain_range == 40
    assert snap.relations_satisfying_constraints == 30
    assert snap.constraint_satisfaction_rate == pytest.approx(0.75)


def test_snapshot_timestamp_updates() -> None:
    gm = SampleMetrics(graph_store=DummyGraphStore())
    before = datetime.now()
    snap = gm.compute_metrics()
    after = datetime.now() + timedelta(seconds=1)
    assert before <= snap.timestamp <= after
