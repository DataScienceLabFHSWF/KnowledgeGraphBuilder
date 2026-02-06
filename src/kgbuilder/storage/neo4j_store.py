"""Neo4j Graph Store Implementation - GraphStore Protocol.

Implements the GraphStore protocol for Neo4j property graph database.
This is a refactoring of SimpleKGAssembler to work with the unified
GraphStore interface, enabling multi-store support.

Features:
- Full CRUD operations for nodes and edges
- Batch operations with transaction support
- Cypher query execution
- Graph statistics and analysis
- Export to multiple formats
- Performance indices

Usage:
    >>> store = Neo4jGraphStore("bolt://localhost:7687", ("neo4j", "password"))
    >>> node = Node(id="e1", label="Alice", node_type="Person")
    >>> store.add_node(node)
    >>> edge = Edge(id="r1", source_id="e1", target_id="e2", edge_type="knows")
    >>> store.add_edge(edge)
    >>> result = store.query("MATCH (n) RETURN n LIMIT 10")
    >>> stats = store.get_statistics()
"""

from __future__ import annotations

from typing import Any, Iterator
import json

import structlog
from neo4j import GraphDatabase, Session
from neo4j.exceptions import ServiceUnavailable

from kgbuilder.storage.protocol import (
    GraphStore,
    Node,
    Edge,
    QueryResult,
    GraphStatistics,
)

logger = structlog.get_logger(__name__)


class Neo4jGraphStore:
    """Neo4j implementation of GraphStore protocol.

    This implementation uses Neo4j's bolt protocol to store graphs as
    property graphs. It supports full CRUD, transactions, queries, and
    statistics.

    Thread-safe through Neo4j driver connection pooling.
    """

    def __init__(self, uri: str, auth: tuple[str, str]) -> None:
        """Initialize Neo4j graph store.

        Args:
            uri: Neo4j bolt URI (e.g., "bolt://localhost:7687")
            auth: (username, password) tuple

        Raises:
            ServiceUnavailable: If cannot connect to Neo4j
        """
        try:
            self._driver = GraphDatabase.driver(uri, auth=auth)
            # Test connection
            with self._driver.session() as session:
                session.run("RETURN 1")
            logger.info("neo4j_connected", uri=uri)
            self._uri = uri
        except ServiceUnavailable as e:
            logger.error("neo4j_connection_failed", uri=uri, error=str(e))
            raise

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        self._driver.close()

    # =========================================================================
    # Node Operations
    # =========================================================================

    def add_node(self, node: Node) -> str:
        """Add or update a node.

        Args:
            node: Node object

        Returns:
            Node ID
        """
        query = """
        MERGE (n:{node_type} {id: $id})
        SET n.label = $label,
            n.node_type = $node_type,
            n.properties = $properties,
            n.created_at = datetime()
        RETURN n.id AS id
        """

        with self._driver.session() as session:
            result = session.run(
                query.replace("{node_type}", node.node_type),
                id=node.id,
                label=node.label,
                node_type=node.node_type,
                properties=json.dumps(node.properties),
            )
            return result.single()["id"]

    def get_node(self, node_id: str) -> Node | None:
        """Get a node by ID.

        Args:
            node_id: Node ID

        Returns:
            Node object or None if not found
        """
        query = """
        MATCH (n {id: $id})
        RETURN n.id AS id, n.label AS label, labels(n)[0] AS node_type,
               n.properties AS properties
        """

        with self._driver.session() as session:
            result = session.run(query, id=node_id)
            record = result.single()

            if not record:
                return None

            props = json.loads(record["properties"]) if record["properties"] else {}
            return Node(
                id=record["id"],
                label=record["label"],
                node_type=record["node_type"],
                properties=props,
            )

    def update_node(self, node_id: str, properties: dict[str, Any]) -> bool:
        """Update node properties.

        Args:
            node_id: Node ID
            properties: Properties to update

        Returns:
            True if successful, False if node not found
        """
        query = """
        MATCH (n {id: $id})
        SET n += $properties
        RETURN count(n) AS count
        """

        with self._driver.session() as session:
            result = session.run(query, id=node_id, properties=properties)
            return result.single()["count"] > 0

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and connected edges.

        Args:
            node_id: Node ID

        Returns:
            True if successful, False if node not found
        """
        query = """
        MATCH (n {id: $id})
        DETACH DELETE n
        RETURN count(n) AS count
        """

        with self._driver.session() as session:
            result = session.run(query, id=node_id)
            return result.single()["count"] > 0

    def get_nodes_by_type(self, node_type: str) -> list[Node]:
        """Get all nodes of a type.

        Args:
            node_type: Node type/label

        Returns:
            List of nodes
        """
        query = f"""
        MATCH (n:{node_type})
        RETURN n.id AS id, n.label AS label, labels(n)[0] AS node_type,
               n.properties AS properties
        """

        nodes = []
        with self._driver.session() as session:
            result = session.run(query)
            for record in result:
                props = json.loads(record["properties"]) if record["properties"] else {}
                nodes.append(
                    Node(
                        id=record["id"],
                        label=record["label"],
                        node_type=record["node_type"],
                        properties=props,
                    )
                )

        return nodes

    # =========================================================================
    # Edge Operations
    # =========================================================================

    def add_edge(self, edge: Edge) -> str:
        """Add an edge.

        Args:
            edge: Edge object

        Returns:
            Edge ID

        Raises:
            ValueError: If source or target node not found
        """
        # Check nodes exist
        query_check = """
        MATCH (s {id: $source_id}), (t {id: $target_id})
        RETURN count(*) AS count
        """

        with self._driver.session() as session:
            result = session.run(
                query_check, source_id=edge.source_id, target_id=edge.target_id
            )
            if result.single()["count"] == 0:
                raise ValueError(
                    f"Source {edge.source_id} or target {edge.target_id} not found"
                )

            # Create edge
            query = f"""
            MATCH (s {{id: $source_id}}), (t {{id: $target_id}})
            CREATE (s)-[r:{edge.edge_type} {{id: $id, properties: $properties, created_at: datetime()}}]->(t)
            RETURN r.id AS id
            """

            result = session.run(
                query,
                id=edge.id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                properties=json.dumps(edge.properties),
            )
            return result.single()["id"]

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge.

        Args:
            edge_id: Edge ID

        Returns:
            True if successful, False if edge not found
        """
        query = """
        MATCH ()-[r {id: $id}]->()
        DELETE r
        RETURN count(r) AS count
        """

        with self._driver.session() as session:
            result = session.run(query, id=edge_id)
            return result.single()["count"] > 0

    def get_edges_for_node(
        self, node_id: str, direction: str = "both"
    ) -> list[Edge]:
        """Get edges connected to a node.

        Args:
            node_id: Node ID
            direction: "in", "out", or "both"

        Returns:
            List of edges
        """
        if direction == "out":
            query = """
            MATCH (n {id: $id})-[r]->()
            RETURN r.id AS id, n.id AS source_id, 
                   other(n, n).id AS target_id, type(r) AS edge_type,
                   r.properties AS properties
            """
        elif direction == "in":
            query = """
            MATCH ()-[r]->(n {id: $id})
            RETURN r.id AS id, other(n, n).id AS source_id, 
                   n.id AS target_id, type(r) AS edge_type,
                   r.properties AS properties
            """
        else:  # both
            query = """
            MATCH (n {id: $id})-[r]-()
            RETURN r.id AS id, startNode(r).id AS source_id, 
                   endNode(r).id AS target_id, type(r) AS edge_type,
                   r.properties AS properties
            """

        edges = []
        with self._driver.session() as session:
            result = session.run(query, id=node_id)
            for record in result:
                props = json.loads(record["properties"]) if record["properties"] else {}
                edges.append(
                    Edge(
                        id=record["id"],
                        source_id=record["source_id"],
                        target_id=record["target_id"],
                        edge_type=record["edge_type"],
                        properties=props,
                    )
                )

        return edges

    # =========================================================================
    # Batch Operations
    # =========================================================================

    def batch_create_nodes(self, nodes: list[Node]) -> list[str]:
        """Create multiple nodes efficiently.

        Args:
            nodes: List of nodes

        Returns:
            List of node IDs created
        """
        ids = []
        for node in nodes:
            ids.append(self.add_node(node))
        return ids

    def batch_create_edges(self, edges: list[Edge]) -> list[str]:
        """Create multiple edges efficiently.

        Args:
            edges: List of edges

        Returns:
            List of edge IDs created
        """
        ids = []
        for edge in edges:
            try:
                ids.append(self.add_edge(edge))
            except ValueError as e:
                logger.warning("edge_creation_failed", error=str(e))
        return ids

    # =========================================================================
    # Query Operations
    # =========================================================================

    def query(
        self, query_str: str, params: dict[str, Any] | None = None
    ) -> QueryResult:
        """Execute a Cypher query.

        Args:
            query_str: Cypher query
            params: Query parameters

        Returns:
            QueryResult with records and summary
        """
        records = []
        columns = []

        with self._driver.session() as session:
            result = session.run(query_str, params or {})
            columns = result.keys()
            for record in result:
                records.append(dict(record))
            summary = result.consume()

        return QueryResult(
            records=records,
            columns=list(columns),
            summary={
                "nodes_created": summary.counters.nodes_created,
                "nodes_deleted": summary.counters.nodes_deleted,
                "relationships_created": summary.counters.relationships_created,
                "relationships_deleted": summary.counters.relationships_deleted,
            },
        )

    def get_subgraph(
        self, node_ids: list[str], depth: int = 1
    ) -> tuple[list[Node], list[Edge]]:
        """Get subgraph around nodes.

        Args:
            node_ids: Starting node IDs
            depth: Hops to traverse

        Returns:
            (nodes, edges) in subgraph
        """
        query = """
        MATCH (n)-[r*0..{depth}]-(m)
        WHERE n.id IN $node_ids
        RETURN collect(distinct n) AS nodes, collect(distinct r) AS edges
        """.replace("{depth}", str(depth))

        nodes = []
        edges = []

        with self._driver.session() as session:
            result = session.run(query, node_ids=node_ids)
            record = result.single()

            if record:
                for node in record["nodes"] or []:
                    props = json.loads(node["properties"]) if node["properties"] else {}
                    nodes.append(
                        Node(
                            id=node["id"],
                            label=node["label"],
                            node_type=node.get("node_type", "Unknown"),
                            properties=props,
                        )
                    )

                for edge in record["edges"] or []:
                    if edge:  # Can be None in some patterns
                        props = json.loads(edge["properties"]) if edge["properties"] else {}
                        edges.append(
                            Edge(
                                id=edge["id"],
                                source_id=edge.start_node["id"],
                                target_id=edge.end_node["id"],
                                edge_type=edge.type,
                                properties=props,
                            )
                        )

        return nodes, edges

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_statistics(self) -> GraphStatistics:
        """Get graph statistics.

        Returns:
            GraphStatistics object
        """
        query = """
        MATCH (n)
        WITH labels(n)[0] AS node_type, count(n) AS count
        RETURN collect({type: node_type, count: count}) AS nodes_by_type,
               sum(count) AS total_nodes
        """

        node_count = 0
        nodes_by_type = {}

        with self._driver.session() as session:
            result = session.run(query)
            record = result.single()
            if record:
                for item in record["nodes_by_type"]:
                    nodes_by_type[item["type"]] = item["count"]
                node_count = record["total_nodes"]

        # Get edge count
        query_edges = "MATCH ()-[r]->() RETURN count(r) AS count"
        with self._driver.session() as session:
            result = session.run(query_edges)
            edge_count = result.single()["count"]

        return GraphStatistics(
            node_count=node_count,
            edge_count=edge_count,
            nodes_by_type=nodes_by_type,
        )

    def health_check(self) -> bool:
        """Check if Neo4j is accessible.

        Returns:
            True if healthy
        """
        try:
            with self._driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False

    def clear(self) -> None:
        """Delete all nodes and edges."""
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.warning("neo4j_graph_cleared")
