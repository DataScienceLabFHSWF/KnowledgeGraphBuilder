"""Database connectors for graph and vector storage.

Implementation of Issues #3.2 (VectorStore), #6.2 (GraphStore), #7.1 (RDFStore)

TODO (VectorStore - Qdrant/ChromaDB/Milvus):
- [ ] Define VectorStore protocol with full CRUD operations
- [ ] Implement QdrantStore (production)
  - Collection management
  - Dense & sparse search (hybrid)
  - Metadata filtering
  - Batch operations
- [ ] Implement ChromaDBStore (development)
- [ ] Implement MilvusStore (alternative for scale)
- [ ] Add connection pooling and error recovery
- [ ] Add integration tests with docker containers

TODO (GraphStore - Neo4j):
- [ ] Define GraphStore protocol (create_node, add_relation, query, export)
- [ ] Implement Neo4jGraphStore
  - Transaction management
  - Batch updates
  - SPARQL/Cypher support
  - Export to multiple formats
- [ ] Add connection pooling
- [ ] Add integration tests

TODO (RDFStore - Fuseki/alternatives):
- [ ] Define RDFStore protocol
- [ ] Implement FusekiStore for SPARQL queries
- [ ] Add OWL reasoning support
- [ ] Add integration tests

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
