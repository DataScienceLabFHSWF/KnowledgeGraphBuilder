"""Database connectors for graph and vector storage.

Implementation of Issues #3.2 (VectorStore), #6.2 (GraphStore), #7.1 (RDFStore)

See Planning/ISSUES_BACKLOG.md Issues #3.2, #6.2, #7.1 for acceptance criteria.
"""

from .export import ExportConfig, KGExporter, export_kg
from .graph import GraphStore, Neo4jStore
from .neo4j_store import Neo4jGraphStore

# New protocol-based exports (Phase 6)
from .protocol import (
    Edge,
    GraphStatistics,
    InMemoryGraphStore,
    Node,
    QueryResult,
    create_graph_store,
)
from .protocol import (
    GraphStore as GraphStoreProtocol,
)
from .rdf import FusekiStore, RDFStore
from .rdf_store import RDFGraphStore
from .retrieval import SemanticRetriever
from .vector import QdrantStore, VectorStore

__all__ = [
    # Legacy exports
    "VectorStore",
    "QdrantStore",
    "GraphStore",
    "Neo4jStore",
    "RDFStore",
    "FusekiStore",
    "SemanticRetriever",
    # New protocol-based exports (Phase 6-7)
    "Node",
    "Edge",
    "QueryResult",
    "GraphStatistics",
    "GraphStoreProtocol",
    "InMemoryGraphStore",
    "Neo4jGraphStore",
    "RDFGraphStore",
    "create_graph_store",
    "KGExporter",
    "ExportConfig",
    "export_kg",
]
