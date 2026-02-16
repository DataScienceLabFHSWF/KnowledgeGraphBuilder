"""Graph storage protocol and data models.

This module defines the unified interface for all graph storage backends
(Neo4j, RDF/SPARQL, in-memory) and the core data structures for nodes and edges.

The GraphStore protocol allows the pipeline to work with any backend:
- InMemoryGraphStore: Fast, no dependencies, good for testing and export
- Neo4jGraphStore: Production graph database with Cypher queries
- RDFGraphStore: Semantic web backend with SPARQL (future)

Usage:
    # Use in-memory store for testing or JSON export
    store = InMemoryGraphStore()
    assembler = KGAssembler(store)
    result = assembler.assemble(entities, relations)
    
    # Export to JSON
    kg_data = store.to_dict()
    
    # Or use Neo4j for production
    store = Neo4jGraphStore("bolt://localhost:7687", ("neo4j", "pass"))
    assembler = KGAssembler(store)
    result = assembler.assemble(entities, relations)
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Node:
    """A node in the knowledge graph.
    
    Represents an entity with a unique ID, type (label), and properties.
    Maps to: Neo4j Node, RDF Subject, JSON-LD @id.
    
    Attributes:
        id: Unique identifier (UUID or URI)
        label: Human-readable name
        node_type: Ontology class / node label
        properties: Key-value properties (confidence, description, etc.)
        metadata: System metadata (created_at, source, etc.)
    
    Example:
        >>> node = Node(
        ...     id="entity-123",
        ...     label="Fuel Rod Assembly",
        ...     node_type="Component",
        ...     properties={"confidence": 0.85, "description": "..."}
        ... )
    """

    id: str
    node_type: str
    label: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set default metadata if not provided."""
        if "created_at" not in self.metadata:
            self.metadata["created_at"] = datetime.now(tz=timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "label": self.label,
            "type": self.node_type,
            "properties": self.properties,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        """Create Node from dictionary."""
        return cls(
            id=data["id"],
            label=data["label"],
            node_type=data.get("type", data.get("node_type", "Entity")),
            properties=data.get("properties", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Edge:
    """An edge (relationship) in the knowledge graph.
    
    Represents a directed relationship between two nodes.
    Maps to: Neo4j Relationship, RDF Triple, JSON-LD reference.
    
    Attributes:
        id: Unique identifier
        source_id: ID of source node
        target_id: ID of target node
        edge_type: Relationship type (predicate)
        properties: Key-value properties (confidence, evidence, etc.)
        metadata: System metadata
    
    Example:
        >>> edge = Edge(
        ...     id="rel-456",
        ...     source_id="entity-123",
        ...     target_id="entity-789",
        ...     edge_type="HAS_COMPONENT",
        ...     properties={"confidence": 0.9}
        ... )
    """

    id: str
    source_id: str
    target_id: str
    edge_type: str
    # backward-compatible optional fields used by tests/fixtures
    source_node_type: str | None = None
    target_node_type: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Set default metadata if not provided."""
        if "created_at" not in self.metadata:
            self.metadata["created_at"] = datetime.now(tz=timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.edge_type,
            "source_node_type": self.source_node_type,
            "target_node_type": self.target_node_type,
            "properties": self.properties,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Edge:
        """Create Edge from dictionary."""
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            edge_type=data.get("type", data.get("edge_type", "RELATED_TO")),
            source_node_type=data.get("source_node_type") or data.get("source_node_type"),
            target_node_type=data.get("target_node_type") or data.get("target_node_type"),
            properties=data.get("properties", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class QueryResult:
    """Result of a graph query.
    
    Attributes:
        records: List of result records (dict per row)
        columns: Column names in result
        summary: Query execution summary (timing, counts, etc.)
    """

    records: list[dict[str, Any]]
    columns: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphStatistics:
    """Statistics about the knowledge graph.
    
    Attributes:
        node_count: Total number of nodes
        edge_count: Total number of edges
        nodes_by_type: Count of nodes per type
        edges_by_type: Count of edges per type
        avg_confidence: Average confidence across all nodes
        density: Graph density (edges / possible edges)
    """

    node_count: int = 0
    edge_count: int = 0
    nodes_by_type: dict[str, int] = field(default_factory=dict)
    edges_by_type: dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    min_confidence: float = 0.0
    max_confidence: float = 0.0
    density: float = 0.0


# =============================================================================
# GRAPH STORE PROTOCOL
# =============================================================================


@runtime_checkable
class GraphStore(Protocol):
    """Protocol defining the interface for all graph storage backends.
    
    Any class implementing this protocol can be used as a KG backend.
    The pipeline is agnostic to the specific implementation.
    
    Implementations:
        - InMemoryGraphStore: In-memory storage, JSON export
        - Neo4jGraphStore: Neo4j graph database
        - RDFGraphStore: RDF triplestore (Fuseki/SPARQL)
    
    Example:
        >>> def process_kg(store: GraphStore, entities: list) -> None:
        ...     for entity in entities:
        ...         node = Node(id=entity.id, label=entity.label, ...)
        ...         store.add_node(node)
        ...     stats = store.get_statistics()
        ...     print(f"Created {stats.node_count} nodes")
    """

    # -------------------------------------------------------------------------
    # Node Operations
    # -------------------------------------------------------------------------

    def add_node(self, node: Node) -> str:
        """Add a node to the graph.
        
        If a node with the same ID exists, it will be updated (merge).
        
        Args:
            node: The node to add
            
        Returns:
            The node ID (for chaining)
        """
        ...

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID.
        
        Args:
            node_id: The unique node identifier
            
        Returns:
            The node if found, None otherwise
        """
        ...

    def get_nodes_by_type(self, node_type: str) -> list[Node]:
        """Get all nodes of a specific type.
        
        Args:
            node_type: The node type/label to filter by
            
        Returns:
            List of matching nodes
        """
        ...

    def update_node(self, node_id: str, properties: dict[str, Any]) -> bool:
        """Update node properties.
        
        Args:
            node_id: ID of node to update
            properties: Properties to merge/update
            
        Returns:
            True if node was found and updated
        """
        ...

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its connected edges.
        
        Args:
            node_id: ID of node to delete
            
        Returns:
            True if node was found and deleted
        """
        ...

    # -------------------------------------------------------------------------
    # Edge Operations
    # -------------------------------------------------------------------------

    def add_edge(self, edge: Edge) -> str:
        """Add an edge to the graph.
        
        Both source and target nodes must exist.
        
        Args:
            edge: The edge to add
            
        Returns:
            The edge ID
            
        Raises:
            ValueError: If source or target node doesn't exist
        """
        ...

    def get_edge(self, edge_id: str) -> Edge | None:
        """Get an edge by ID.
        
        Args:
            edge_id: The unique edge identifier
            
        Returns:
            The edge if found, None otherwise
        """
        ...

    def get_edges_for_node(self, node_id: str, direction: str = "both") -> list[Edge]:
        """Get all edges connected to a node.
        
        Args:
            node_id: The node ID
            direction: "outgoing", "incoming", or "both"
            
        Returns:
            List of connected edges
        """
        ...

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def query(self, query_str: str, params: dict[str, Any] | None = None) -> QueryResult:
        """Execute a query (Cypher, SPARQL, or simple filter).
        
        The query language depends on the backend:
        - Neo4j: Cypher
        - RDF: SPARQL
        - InMemory: Simple dict filter
        
        Args:
            query_str: The query string
            params: Query parameters
            
        Returns:
            Query results
        """
        ...

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def add_nodes_batch(self, nodes: list[Node]) -> int:
        """Add multiple nodes in a batch.
        
        More efficient than calling add_node() repeatedly.
        
        Args:
            nodes: List of nodes to add
            
        Returns:
            Number of nodes added
        """
        ...

    def add_edges_batch(self, edges: list[Edge]) -> int:
        """Add multiple edges in a batch.
        
        Args:
            edges: List of edges to add
            
        Returns:
            Number of edges added
        """
        ...

    # -------------------------------------------------------------------------
    # Statistics & Export
    # -------------------------------------------------------------------------

    def get_statistics(self) -> GraphStatistics:
        """Get statistics about the graph.
        
        Returns:
            GraphStatistics with counts and metrics
        """
        ...

    def get_all_nodes(self) -> Iterator[Node]:
        """Iterate over all nodes.
        
        Yields:
            All nodes in the graph
        """
        ...

    def get_all_edges(self) -> Iterator[Edge]:
        """Iterate over all edges.
        
        Yields:
            All edges in the graph
        """
        ...

    def clear(self) -> None:
        """Remove all nodes and edges from the graph."""
        ...


# =============================================================================
# IN-MEMORY IMPLEMENTATION
# =============================================================================


class InMemoryGraphStore:
    """In-memory graph store for testing and JSON export.
    
    This implementation stores the graph in Python dictionaries.
    It's useful for:
    - Unit testing without database dependencies
    - Small graphs that fit in memory
    - Export to JSON/other formats before database load
    - Development and prototyping
    
    NOT suitable for:
    - Large graphs (>100k nodes)
    - Concurrent access
    - Persistence across restarts
    
    Example:
        >>> store = InMemoryGraphStore()
        >>> store.add_node(Node(id="1", label="Test", node_type="Entity"))
        >>> store.add_node(Node(id="2", label="Other", node_type="Entity"))
        >>> store.add_edge(Edge(id="e1", source_id="1", target_id="2", edge_type="RELATED"))
        >>> print(store.get_statistics().node_count)  # 2
        >>> kg_dict = store.to_dict()  # Export to JSON-serializable dict
    """

    def __init__(self) -> None:
        """Initialize empty in-memory graph."""
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}
        logger.info("in_memory_graph_store_initialized")

    # -------------------------------------------------------------------------
    # Node Operations
    # -------------------------------------------------------------------------

    def add_node(self, node: Node) -> str:
        """Add or update a node."""
        self._nodes[node.id] = node
        logger.debug("node_added", node_id=node.id, node_type=node.node_type)
        return node.id

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: str) -> list[Node]:
        """Get all nodes of a specific type."""
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def update_node(self, node_id: str, properties: dict[str, Any]) -> bool:
        """Update node properties."""
        node = self._nodes.get(node_id)
        if node is None:
            return False
        node.properties.update(properties)
        return True

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its connected edges."""
        if node_id not in self._nodes:
            return False

        # Delete connected edges
        edges_to_delete = [
            eid for eid, e in self._edges.items()
            if e.source_id == node_id or e.target_id == node_id
        ]
        for eid in edges_to_delete:
            del self._edges[eid]

        del self._nodes[node_id]
        return True

    # -------------------------------------------------------------------------
    # Edge Operations
    # -------------------------------------------------------------------------

    def add_edge(self, edge: Edge) -> str:
        """Add an edge to the graph."""
        if edge.source_id not in self._nodes:
            raise ValueError(f"Source node {edge.source_id} not found")
        if edge.target_id not in self._nodes:
            raise ValueError(f"Target node {edge.target_id} not found")

        self._edges[edge.id] = edge
        logger.debug("edge_added", edge_id=edge.id, edge_type=edge.edge_type)
        return edge.id

    def get_edge(self, edge_id: str) -> Edge | None:
        """Get an edge by ID."""
        return self._edges.get(edge_id)

    def get_edges_for_node(self, node_id: str, direction: str = "both") -> list[Edge]:
        """Get all edges connected to a node."""
        edges = []
        for edge in self._edges.values():
            if direction in ("outgoing", "both") and edge.source_id == node_id:
                edges.append(edge)
            elif direction in ("incoming", "both") and edge.target_id == node_id:
                edges.append(edge)
        return edges

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def query(self, query_str: str, params: dict[str, Any] | None = None) -> QueryResult:
        """Execute a simple filter query.
        
        For in-memory store, query_str is interpreted as a node type filter.
        Use get_nodes_by_type() for type-based queries instead.
        
        Args:
            query_str: Node type to filter by, or "*" for all
            params: Not used in in-memory implementation
            
        Returns:
            QueryResult with matching nodes as records
        """
        if query_str == "*":
            records = [n.to_dict() for n in self._nodes.values()]
        else:
            records = [n.to_dict() for n in self.get_nodes_by_type(query_str)]

        return QueryResult(
            records=records,
            columns=["id", "label", "type", "properties"],
            summary={"count": len(records)}
        )

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def add_nodes_batch(self, nodes: list[Node]) -> int:
        """Add multiple nodes in a batch."""
        for node in nodes:
            self._nodes[node.id] = node
        logger.info("nodes_batch_added", count=len(nodes))
        return len(nodes)

    def add_edges_batch(self, edges: list[Edge]) -> int:
        """Add multiple edges in a batch."""
        added = 0
        for edge in edges:
            try:
                self.add_edge(edge)
                added += 1
            except ValueError as e:
                logger.warning("edge_skipped", edge_id=edge.id, reason=str(e))
        logger.info("edges_batch_added", count=added)
        return added

    # -------------------------------------------------------------------------
    # Statistics & Export
    # -------------------------------------------------------------------------

    def get_statistics(self) -> GraphStatistics:
        """Compute graph statistics."""
        nodes_by_type: dict[str, int] = {}
        edges_by_type: dict[str, int] = {}
        confidences: list[float] = []

        for node in self._nodes.values():
            nodes_by_type[node.node_type] = nodes_by_type.get(node.node_type, 0) + 1
            if "confidence" in node.properties:
                confidences.append(float(node.properties["confidence"]))

        for edge in self._edges.values():
            edges_by_type[edge.edge_type] = edges_by_type.get(edge.edge_type, 0) + 1

        n = len(self._nodes)
        e = len(self._edges)
        density = e / (n * (n - 1)) if n > 1 else 0.0

        return GraphStatistics(
            node_count=n,
            edge_count=e,
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
            avg_confidence=sum(confidences) / len(confidences) if confidences else 0.0,
            min_confidence=min(confidences) if confidences else 0.0,
            max_confidence=max(confidences) if confidences else 0.0,
            density=density,
        )

    def get_all_nodes(self) -> Iterator[Node]:
        """Iterate over all nodes."""
        yield from self._nodes.values()

    def get_all_edges(self) -> Iterator[Edge]:
        """Iterate over all edges."""
        yield from self._edges.values()

    def clear(self) -> None:
        """Remove all nodes and edges."""
        self._nodes.clear()
        self._edges.clear()
        logger.info("graph_cleared")

    # -------------------------------------------------------------------------
    # Export Methods (In-Memory specific)
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Export graph to a JSON-serializable dictionary.
        
        Returns:
            Dictionary with nodes, edges, and metadata
        
        Example:
            >>> store = InMemoryGraphStore()
            >>> # ... add nodes and edges ...
            >>> data = store.to_dict()
            >>> with open("kg.json", "w") as f:
            ...     json.dump(data, f, indent=2)
        """
        return {
            "metadata": {
                "exported_at": datetime.now(tz=timezone.utc).isoformat(),
                "node_count": len(self._nodes),
                "edge_count": len(self._edges),
            },
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InMemoryGraphStore:
        """Import graph from a dictionary.
        
        Args:
            data: Dictionary with nodes and edges
            
        Returns:
            New InMemoryGraphStore with loaded data
        """
        store = cls()
        for node_data in data.get("nodes", []):
            store.add_node(Node.from_dict(node_data))
        for edge_data in data.get("edges", []):
            store.add_edge(Edge.from_dict(edge_data))
        return store

    def to_json(self, indent: int = 2) -> str:
        """Export graph to JSON string.
        
        Args:
            indent: JSON indentation (default 2)
            
        Returns:
            JSON string representation of the graph
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_graph_store(
    backend: str = "memory",
    **kwargs: Any
) -> GraphStore:
    """Factory function to create a graph store.
    
    Args:
        backend: "memory", "neo4j", or "rdf"
        **kwargs: Backend-specific arguments
        
    Returns:
        GraphStore implementation
        
    Example:
        >>> store = create_graph_store("memory")
        >>> store = create_graph_store("neo4j", uri="bolt://localhost:7687", auth=("neo4j", "pass"))
    """
    if backend == "memory":
        return InMemoryGraphStore()
    elif backend == "neo4j":
        # Import here to avoid dependency if not using Neo4j
        from kgbuilder.storage.neo4j_store import Neo4jGraphStore
        return Neo4jGraphStore(**kwargs)
    elif backend == "rdf":
        # Import here to avoid dependency if not using RDF
        from kgbuilder.storage.rdf_store import RDFGraphStore
        return RDFGraphStore(**kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'memory', 'neo4j', or 'rdf'")
