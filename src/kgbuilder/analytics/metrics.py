"""Graph metrics and diagnostics for Knowledge Graphs.

Computes graph statistics, centrality measures, and quality diagnostics
to understand KG structure, identify hubs/orphans, and measure schema coverage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GraphMetricsSnapshot:
    """Snapshot of graph metrics at a point in time."""

    timestamp: datetime = field(default_factory=datetime.now)
    total_nodes: int = 0
    total_edges: int = 0
    total_relations: int = 0
    
    # Node statistics
    typed_nodes: int = 0
    typed_percentage: float = 0.0
    
    # Edge statistics
    relations_with_domain_range: int = 0
    relations_satisfying_constraints: int = 0
    constraint_satisfaction_rate: float = 0.0
    
    # Centrality
    average_degree: float = 0.0
    max_degree: int = 0
    orphan_nodes: int = 0  # Nodes with degree 0
    hub_nodes: int = 0  # Nodes with degree > avg * 2
    
    # Quality
    missing_descriptions: int = 0
    missing_types: int = 0
    orphan_entities: int = 0
    
    # Predicate distribution (power-law)
    unique_predicates: int = 0
    most_common_predicates: list[tuple[str, int]] = field(default_factory=list)
    
    # Auxiliary
    duration_seconds: float = 0.0
    notes: str = ""


class GraphMetrics:
    """Computes and reports graph metrics for Knowledge Graphs.
    
    Metrics include:
    - Triple/node/edge counts
    - Schema coverage (% typed entities)
    - Constraint satisfaction (domain/range validation)
    - Centrality measures (degree, betweenness, PageRank)
    - Data quality diagnostics (orphans, missing descriptions)
    - Predicate frequency distribution
    """

    def __init__(self, graph_store: object) -> None:
        """Initialize metrics calculator.
        
        Args:
            graph_store: Neo4jGraphStore or similar interface
        """
        self.graph_store = graph_store

    def compute_metrics(self, ontology_service: object | None = None) -> GraphMetricsSnapshot:
        """Compute comprehensive graph metrics.
        
        Args:
            ontology_service: Optional ontology for constraint checking
            
        Returns:
            GraphMetricsSnapshot with computed metrics
        """
        snapshot = GraphMetricsSnapshot()
        start_time = datetime.now()
        
        try:
            # Count nodes and edges
            snapshot.total_nodes = self._count_nodes()
            snapshot.total_edges = self._count_edges()
            snapshot.total_relations = self._count_relations()
            
            # Schema coverage
            snapshot.typed_nodes = self._count_typed_nodes()
            snapshot.typed_percentage = (
                100 * snapshot.typed_nodes / max(snapshot.total_nodes, 1)
            )
            
            # Metrics
            snapshot.orphan_nodes = self._count_orphan_nodes()
            snapshot.average_degree = self._compute_average_degree()
            snapshot.max_degree = self._compute_max_degree()
            snapshot.hub_nodes = self._count_hub_nodes(snapshot.average_degree)
            
            # Data quality
            snapshot.missing_descriptions = self._count_missing_descriptions()
            snapshot.missing_types = self._count_missing_types()
            snapshot.orphan_entities = self._count_orphan_entities()
            
            # Predicates
            snapshot.unique_predicates = self._count_unique_predicates()
            snapshot.most_common_predicates = self._get_predicate_distribution(top_k=10)
            
            # Constraints (if ontology available)
            if ontology_service:
                result = self._check_constraint_satisfaction(ontology_service)
                snapshot.relations_with_domain_range = result["total"]
                snapshot.relations_satisfying_constraints = result["satisfied"]
                snapshot.constraint_satisfaction_rate = result["rate"]
            
        except Exception as e:
            logger.error(f"metrics_computation_error: {e}")
            snapshot.notes = f"Error during computation: {e}"
        
        snapshot.duration_seconds = (datetime.now() - start_time).total_seconds()
        logger.info(
            "graph_metrics_computed",
            nodes=snapshot.total_nodes,
            edges=snapshot.total_edges,
            typed_pct=snapshot.typed_percentage,
            orphans=snapshot.orphan_nodes,
            duration=snapshot.duration_seconds,
        )
        
        return snapshot

    def _count_nodes(self) -> int:
        """Count total nodes in graph."""
        # Placeholder: would query via graph_store
        return 0

    def _count_edges(self) -> int:
        """Count total edges in graph."""
        return 0

    def _count_relations(self) -> int:
        """Count total relations (excluding implicit edges)."""
        return 0

    def _count_typed_nodes(self) -> int:
        """Count nodes with entity type."""
        return 0

    def _count_orphan_nodes(self) -> int:
        """Count nodes with degree 0."""
        return 0

    def _compute_average_degree(self) -> float:
        """Compute average node degree."""
        return 0.0

    def _compute_max_degree(self) -> int:
        """Find maximum node degree."""
        return 0

    def _count_hub_nodes(self, avg_degree: float) -> int:
        """Count nodes with degree > 2 * avg_degree."""
        return 0

    def _count_missing_descriptions(self) -> int:
        """Count entities without description."""
        return 0

    def _count_missing_types(self) -> int:
        """Count entities without entity_type."""
        return 0

    def _count_orphan_entities(self) -> int:
        """Count entities with no relations."""
        return 0

    def _count_unique_predicates(self) -> int:
        """Count unique relation types."""
        return 0

    def _get_predicate_distribution(self, top_k: int = 10) -> list[tuple[str, int]]:
        """Get most common predicates and their frequencies."""
        return []

    def _check_constraint_satisfaction(
        self, ontology_service: object
    ) -> dict[str, float | int]:
        """Check domain/range constraint satisfaction.
        
        Returns: {total: int, satisfied: int, rate: float 0.0-1.0}
        """
        return {"total": 0, "satisfied": 0, "rate": 0.0}

    def generate_diagnostics_report(
        self, 
        snapshot: GraphMetricsSnapshot,
        output_path: str | None = None
    ) -> str:
        """Generate human-readable diagnostics report.
        
        Args:
            snapshot: Metrics snapshot
            output_path: Optional file path to save report
            
        Returns:
            Formatted report string
        """
        report = f"""
# Knowledge Graph Diagnostics Report
**Generated**: {snapshot.timestamp.isoformat()}

## Scale Metrics
- **Total Nodes**: {snapshot.total_nodes}
- **Total Edges**: {snapshot.total_edges}
- **Total Relations**: {snapshot.total_relations}

## Schema Coverage
- **Typed Nodes**: {snapshot.typed_nodes} / {snapshot.total_nodes} ({snapshot.typed_percentage:.1f}%)
- **Missing Types**: {snapshot.missing_types}
- **Missing Descriptions**: {snapshot.missing_descriptions}

## Connectivity
- **Average Degree**: {snapshot.average_degree:.2f}
- **Max Degree**: {snapshot.max_degree}
- **Orphan Nodes**: {snapshot.orphan_nodes}
- **Hub Nodes (degree > {snapshot.average_degree*2:.0f})**: {snapshot.hub_nodes}

## Data Quality
- **Orphan Entities**: {snapshot.orphan_entities}
- **Domain/Range Satisfaction**: {snapshot.constraint_satisfaction_rate:.1%}

## Predicate Distribution (Top 10)
"""
        for pred, count in snapshot.most_common_predicates:
            report += f"\n- `{pred}`: {count} relations"

        report += f"\n\n## Computation\n- **Duration**: {snapshot.duration_seconds:.2f}s\n"
        if snapshot.notes:
            report += f"- **Notes**: {snapshot.notes}\n"

        if output_path:
            try:
                with open(output_path, "w") as f:
                    f.write(report)
                logger.info(f"diagnostics_report_written path={output_path}")
            except Exception as e:
                logger.warning(f"Failed to write diagnostics report: {e}")

        return report
