"""RDF Graph Store Implementation - GraphStore Protocol.

Implements the GraphStore protocol for RDF/SPARQL backends (Apache Fuseki).
This enables semantic web integration with the unified GraphStore interface.

Features:
- SPARQL query execution (SELECT, CONSTRUCT, INSERT, DELETE)
- Node/Edge to RDF triple conversion
- Ontology integration
- Multiple RDF formats (Turtle, JSON-LD, N-Triples)
- Graph statistics via SPARQL queries

Usage:
    >>> store = RDFGraphStore("http://localhost:3030/ds")
    >>> node = Node(id="e1", label="Alice", node_type="Person")
    >>> store.add_node(node)
    >>> result = store.query("SELECT ?n WHERE { ?n a ?type }")
    >>> stats = store.get_statistics()
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import structlog
from SPARQLWrapper import JSON, POST, TURTLE, SPARQLWrapper

from kgbuilder.storage.protocol import (
    Edge,
    GraphStatistics,
    Node,
    QueryResult,
)

logger = structlog.get_logger(__name__)

# RDF/OWL namespaces
KGBUILDER_NS = "http://kgbuilder.io/ontology#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"


class RDFGraphStore:
    """RDF/SPARQL implementation of GraphStore protocol.

    This implementation uses Apache Fuseki (or compatible SPARQL endpoint)
    to store knowledge graphs as RDF triples. It integrates with OWL ontologies
    and supports semantic web standards.

    Features:
    - Semantic web integration via RDF/OWL
    - SPARQL query interface
    - Multiple RDF formats
    - Ontology reasoning (when enabled)
    """

    def __init__(self, endpoint: str) -> None:
        """Initialize RDF graph store.

        Args:
            endpoint: SPARQL endpoint URL (e.g., "http://localhost:3030/ds")

        Raises:
            Exception: If endpoint is unreachable
        """
        self._endpoint = endpoint
        self._query_endpoint = SPARQLWrapper(urljoin(endpoint, "query"))
        self._update_endpoint = SPARQLWrapper(urljoin(endpoint, "update"))
        self._graph_endpoint = urljoin(endpoint, "data")

        # Test connection
        try:
            self._query_endpoint.setQuery("ASK { ?s ?p ?o }")
            self._query_endpoint.setReturnFormat(JSON)
            self._query_endpoint.query()
            logger.info("rdf_store_connected", endpoint=endpoint)
        except Exception as e:
            logger.error("rdf_store_connection_failed", endpoint=endpoint, error=str(e))
            raise

    # =========================================================================
    # Node Operations
    # =========================================================================

    def add_node(self, node: Node) -> str:
        """Add a node as RDF triples.

        Creates:
        - Instance triple: <kg:nodeId> rdf:type <kg:NodeType>
        - Label triple: <kg:nodeId> rdfs:label "label"
        - Property triples: <kg:nodeId> <kg:property> "value"

        Args:
            node: Node object

        Returns:
            Node ID
        """
        triples = self._node_to_triples(node)
        self._insert_triples(triples)
        logger.debug("rdf_node_added", node_id=node.id, node_type=node.node_type)
        return node.id

    def get_node(self, node_id: str) -> Node | None:
        """Retrieve a node from RDF.

        Uses SPARQL to reconstruct node from triples.

        Args:
            node_id: Node ID

        Returns:
            Node object or None if not found
        """
        query = f"""
        PREFIX kg: <{KGBUILDER_NS}>
        PREFIX rdfs: <{RDFS_NS}>
        
        CONSTRUCT {{
            kg:{node_id} ?p ?o .
        }}
        WHERE {{
            kg:{node_id} ?p ?o .
        }}
        """

        result_graph = self._construct_query(query)
        if not result_graph:
            return None

        # Extract properties from RDF graph
        node_uri = f"{KGBUILDER_NS}{node_id}"
        label = None
        node_type = None
        properties = {}

        for s, p, o in result_graph:
            if str(p) == f"{RDFS_NS}label":
                label = str(o)
            elif str(p) == f"{RDF_NS}type":
                node_type = str(o).split("#")[-1]
            elif str(p).startswith(KGBUILDER_NS):
                prop_name = str(p).split("#")[-1]
                properties[prop_name] = str(o)

        if not label or not node_type:
            return None

        return Node(
            id=node_id, label=label, node_type=node_type, properties=properties
        )

    def update_node(self, node_id: str, properties: dict[str, Any]) -> bool:
        """Update node properties.

        Args:
            node_id: Node ID
            properties: Properties to add/update

        Returns:
            True if successful
        """
        triples = []
        for key, value in properties.items():
            triples.append(
                f'kg:{node_id} kg:{key} "{value}" .'
            )

        if triples:
            self._insert_triples(triples)
            return True
        return False

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and connected edges.

        Args:
            node_id: Node ID

        Returns:
            True if successful
        """
        # Delete edges
        delete_edges = f"""
        PREFIX kg: <{KGBUILDER_NS}>
        DELETE {{ ?s ?p kg:{node_id} . kg:{node_id} ?q ?o . }}
        WHERE {{ {{ ?s ?p kg:{node_id} }} UNION {{ kg:{node_id} ?q ?o }} }}
        """
        self._update_query(delete_edges)

        # Delete node
        delete_node = f"""
        PREFIX kg: <{KGBUILDER_NS}>
        DELETE {{ kg:{node_id} ?p ?o . }}
        WHERE {{ kg:{node_id} ?p ?o . }}
        """
        self._update_query(delete_node)
        return True

    def get_nodes_by_type(self, node_type: str) -> list[Node]:
        """Get all nodes of a type.

        Args:
            node_type: Node type

        Returns:
            List of nodes
        """
        query = f"""
        PREFIX kg: <{KGBUILDER_NS}>
        PREFIX rdfs: <{RDFS_NS}>
        SELECT ?id ?label
        WHERE {{
            ?node a kg:{node_type} ;
                  rdfs:label ?label .
            BIND(STRAFTER(STR(?node), "#") AS ?id)
        }}
        """

        results = self._select_query(query)
        nodes = []
        for record in results:
            node_id = record.get("id", {}).get("value")
            label = record.get("label", {}).get("value")
            if node_id and label:
                nodes.append(
                    Node(
                        id=node_id,
                        label=label,
                        node_type=node_type,
                        properties={},
                    )
                )
        return nodes

    # =========================================================================
    # Edge Operations
    # =========================================================================

    def add_edge(self, edge: Edge) -> str:
        """Add an edge as RDF triple.

        Creates:
        - Predicate triple: <kg:sourceId> <kg:predicateName> <kg:targetId>

        Args:
            edge: Edge object

        Returns:
            Edge ID
        """
        triple = f'kg:{edge.source_id} kg:{edge.edge_type} kg:{edge.target_id} .'
        self._insert_triples([triple])
        logger.debug(
            "rdf_edge_added",
            edge_id=edge.id,
            source=edge.source_id,
            target=edge.target_id,
        )
        return edge.id

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge.

        Args:
            edge_id: Edge ID (for compatibility, actual deletion uses source/target)

        Returns:
            True if successful
        """
        # Note: RDF edges are identified by subject+predicate+object
        # This is a no-op for individual edge IDs
        logger.warning("rdf_edge_delete_by_id_not_supported", edge_id=edge_id)
        return False

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
            query = f"""
            PREFIX kg: <{KGBUILDER_NS}>
            SELECT ?source ?predicate ?target
            WHERE {{ kg:{node_id} ?predicate ?target . }}
            """
        elif direction == "in":
            query = f"""
            PREFIX kg: <{KGBUILDER_NS}>
            SELECT ?source ?predicate ?target
            WHERE {{ ?source ?predicate kg:{node_id} . }}
            """
        else:  # both
            query = f"""
            PREFIX kg: <{KGBUILDER_NS}>
            SELECT ?source ?predicate ?target
            WHERE {{ {{ kg:{node_id} ?predicate ?target }} UNION {{ ?source ?predicate kg:{node_id} }} }}
            """

        results = self._select_query(query)
        edges = []
        for i, record in enumerate(results):
            source = record.get("source", {}).get("value", "").split("#")[-1]
            target = record.get("target", {}).get("value", "").split("#")[-1]
            predicate = record.get("predicate", {}).get("value", "").split("#")[-1]

            edges.append(
                Edge(
                    id=f"edge-{i}",
                    source_id=source,
                    target_id=target,
                    edge_type=predicate,
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
            List of node IDs
        """
        all_triples = []
        for node in nodes:
            all_triples.extend(self._node_to_triples(node))

        if all_triples:
            self._insert_triples(all_triples)

        return [n.id for n in nodes]

    def batch_create_edges(self, edges: list[Edge]) -> list[str]:
        """Create multiple edges efficiently.

        Args:
            edges: List of edges

        Returns:
            List of edge IDs
        """
        triples = []
        for edge in edges:
            triples.append(
                f'kg:{edge.source_id} kg:{edge.edge_type} kg:{edge.target_id} .'
            )

        if triples:
            self._insert_triples(triples)

        return [e.id for e in edges]

    # =========================================================================
    # Query Operations
    # =========================================================================

    def query(
        self, query_str: str, params: dict[str, Any] | None = None
    ) -> QueryResult:
        """Execute SPARQL query.

        Args:
            query_str: SPARQL query string
            params: Query parameters (not supported in SPARQL)

        Returns:
            QueryResult with records
        """
        try:
            records = self._select_query(query_str)
            return QueryResult(records=records, summary={"type": "sparql"})
        except Exception as e:
            logger.error("sparql_query_failed", error=str(e))
            return QueryResult(records=[], summary={"error": str(e)})

    def get_subgraph(
        self, node_ids: list[str], depth: int = 1
    ) -> tuple[list[Node], list[Edge]]:
        """Get subgraph around nodes using property paths.

        Args:
            node_ids: Starting node IDs
            depth: Hops to traverse

        Returns:
            (nodes, edges) in subgraph
        """
        # Use SPARQL property paths for reachability
        nodes_str = " ".join(f'kg:{nid}' for nid in node_ids)

        query = f"""
        PREFIX kg: <{KGBUILDER_NS}>
        CONSTRUCT {{ ?s ?p ?o . }}
        WHERE {{
            VALUES ?start {{ {nodes_str} }}
            ?s (^kg:|kg:){{,{depth}}} ?start .
            ?s ?p ?o .
        }}
        """

        result_graph = self._construct_query(query)
        nodes = []
        edges = []

        # Extract nodes from graph
        seen_nodes = set()
        for s, p, o in result_graph:
            node_uri = str(s)
            if node_uri.startswith(KGBUILDER_NS) and node_uri not in seen_nodes:
                seen_nodes.add(node_uri)
                node_id = node_uri.split("#")[-1]
                # Create node (simplified - would need full query to get all properties)
                nodes.append(Node(id=node_id, label=node_id, node_type="Unknown"))

            # Extract edges
            if str(p).startswith(KGBUILDER_NS) and str(o).startswith(KGBUILDER_NS):
                source_id = str(s).split("#")[-1]
                target_id = str(o).split("#")[-1]
                predicate = str(p).split("#")[-1]
                edges.append(
                    Edge(
                        id=f"{source_id}-{predicate}-{target_id}",
                        source_id=source_id,
                        target_id=target_id,
                        edge_type=predicate,
                    )
                )

        return nodes, edges

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_statistics(self) -> GraphStatistics:
        """Get RDF graph statistics.

        Returns:
            GraphStatistics object
        """
        # Count nodes
        query_nodes = f"""
        PREFIX kg: <{KGBUILDER_NS}>
        SELECT (COUNT(DISTINCT ?n) AS ?count)
        WHERE {{ ?n a ?type . }}
        """

        # Count edges
        query_edges = f"""
        PREFIX kg: <{KGBUILDER_NS}>
        SELECT (COUNT(DISTINCT ?s) AS ?count)
        WHERE {{ ?s ?p ?o . FILTER(?p != rdf:type && ?p != rdfs:label) }}
        """

        node_count = 0
        edge_count = 0

        try:
            results = self._select_query(query_nodes)
            if results:
                node_count = int(results[0].get("count", {}).get("value", 0))

            results = self._select_query(query_edges)
            if results:
                edge_count = int(results[0].get("count", {}).get("value", 0))
        except Exception as e:
            logger.warning("statistics_query_failed", error=str(e))

        return GraphStatistics(node_count=node_count, edge_count=edge_count)

    def health_check(self) -> bool:
        """Check if SPARQL endpoint is accessible.

        Returns:
            True if healthy
        """
        try:
            self._query_endpoint.setQuery("ASK { ?s ?p ?o }")
            self._query_endpoint.setReturnFormat(JSON)
            self._query_endpoint.query()
            return True
        except Exception:
            return False

    def clear(self) -> None:
        """Delete all triples from the graph."""
        query = "DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }"
        self._update_query(query)
        logger.warning("rdf_graph_cleared")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _node_to_triples(self, node: Node) -> list[str]:
        """Convert node to RDF triples."""
        triples = [
            f'kg:{node.id} a kg:{node.node_type} .',
            f'kg:{node.id} rdfs:label "{node.label}" .',
        ]

        for key, value in node.properties.items():
            # Escape quotes in values
            value_str = str(value).replace('"', '\\"')
            triples.append(f'kg:{node.id} kg:{key} "{value_str}" .')

        return triples

    def _insert_triples(self, triples: list[str]) -> None:
        """Insert triples into RDF store."""
        if not triples:
            return

        triples_str = "\n".join(triples)
        query = f"""
        PREFIX kg: <{KGBUILDER_NS}>
        PREFIX rdfs: <{RDFS_NS}>
        INSERT DATA {{
            {triples_str}
        }}
        """
        self._update_query(query)

    def _select_query(self, sparql: str) -> list[dict[str, Any]]:
        """Execute SPARQL SELECT query."""
        self._query_endpoint.setQuery(sparql)
        self._query_endpoint.setReturnFormat(JSON)
        results = self._query_endpoint.query().convert()
        return results.get("results", {}).get("bindings", [])

    def _construct_query(self, sparql: str):
        """Execute SPARQL CONSTRUCT query and return RDF graph."""
        self._query_endpoint.setQuery(sparql)
        self._query_endpoint.setReturnFormat(TURTLE)
        result_str = self._query_endpoint.query().convert()

        # Parse Turtle to RDF graph
        try:
            from rdflib import Graph
            g = Graph()
            g.parse(data=result_str, format="turtle")
            return g
        except Exception as e:
            logger.error("rdf_parse_failed", error=str(e))
            return []

    def _update_query(self, sparql: str) -> None:
        """Execute SPARQL UPDATE query."""
        self._update_endpoint.setQuery(sparql)
        self._update_endpoint.method = POST
        self._update_endpoint.query()
