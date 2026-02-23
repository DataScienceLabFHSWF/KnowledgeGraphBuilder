import sys
from pathlib import Path

# ensure package import works
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from kgbuilder.assembly.core import GraphStatistics, AssemblyResult


def test_graph_statistics_defaults() -> None:
    gs = GraphStatistics()
    assert gs.num_nodes == 0
    assert gs.node_type_distribution is None
    assert gs.avg_degree == 0.0
    assert "num_edges" in gs.__dict__


def test_assembly_result_repr_and_values() -> None:
    stats = GraphStatistics(num_nodes=5, num_edges=3)
    ar = AssemblyResult(
        document_id="doc1",
        entities_extracted=2,
        relations_extracted=1,
        entities_stored=2,
        relations_stored=1,
        duplicates_removed=0,
        processing_time_ms=123.4,
        stats=stats,
    )
    assert "doc1" in repr(ar)
    d = ar.__dict__
    assert d["entities_extracted"] == 2
    assert d["stats"].num_nodes == 5
