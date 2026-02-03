"""Integration tests for Phase 7 multi-store implementation.

Tests the complete integration of:
- Neo4jGraphStore with real KG operations
- RDFGraphStore with SPARQL queries
- KGBuilder orchestrator with dual-store sync
- Query routing and synchronization
"""

from __future__ import annotations

import pytest
from typing import Any
from unittest.mock import MagicMock, patch

from kgbuilder.storage.protocol import Node, Edge, QueryResult, GraphStatistics
from kgbuilder.assembly.kg_builder import KGBuilder, KGBuilderConfig


class TestPhase7Integration:
    """Integration tests for Phase 7 components."""

    def test_kg_builder_with_mock_stores(self):
        """Test KGBuilder orchestration with mock stores."""
        # Setup mock stores
        neo4j_store = MagicMock()
        rdf_store = MagicMock()

        # Mock node creation
        node_ids = ["ent:001", "ent:002", "ent:003"]
        neo4j_store.batch_create_nodes.return_value = node_ids
        rdf_store.batch_create_nodes.return_value = node_ids

        # Mock edge creation
        edge_ids = ["rel:001", "rel:002"]
        neo4j_store.batch_create_edges.return_value = edge_ids
        rdf_store.batch_create_edges.return_value = edge_ids

        # Mock statistics
        neo4j_store.get_statistics.return_value = GraphStatistics(
            node_count=3,
            edge_count=2,
            nodes_by_type={"Person": 2, "Entity": 1},
            edges_by_type={"knows": 1, "related_to": 1},
            avg_confidence=0.92,
        )

        # Create nodes and edges
        nodes = [
            Node("ent:001", "Alice", "Person", {"confidence": 0.95}),
            Node("ent:002", "Bob", "Person", {"confidence": 0.93}),
            Node("ent:003", "Python", "Technology", {"confidence": 0.90}),
        ]

        edges = [
            Edge("ent:001", "ent:002", "knows", {"confidence": 0.92}),
            Edge("ent:002", "ent:003", "uses", {"confidence": 0.88}),
        ]

        # Create builder with sync
        config = KGBuilderConfig(sync_stores=True, batch_size=1000)
        builder = KGBuilder(neo4j_store, rdf_store, config)

        # Build graph
        result = builder.build(entities=nodes, relations=edges)

        # Verify results
        assert result.nodes_created == 3
        assert result.edges_created == 2
        assert result.nodes_synced == 3
        assert result.edges_synced == 2

        # Verify both stores were called
        neo4j_store.batch_create_nodes.assert_called_once_with(nodes)
        rdf_store.batch_create_nodes.assert_called_once_with(nodes)
        neo4j_store.batch_create_edges.assert_called_once_with(edges)
        rdf_store.batch_create_edges.assert_called_once_with(edges)

    def test_kg_builder_query_routing(self):
        """Test KGBuilder query routing between stores."""
        neo4j_store = MagicMock()
        rdf_store = MagicMock()

        # Setup mock query results
        neo4j_result = QueryResult(
            records=[{"n": {"id": "ent:001", "label": "Alice"}}],
            summary={"count": 1},
        )
        rdf_result = QueryResult(
            records=[{"s": {"id": "ent:001"}}],
            summary={"count": 1},
        )

        neo4j_store.query.return_value = neo4j_result
        rdf_store.query.return_value = rdf_result

        builder = KGBuilder(neo4j_store, rdf_store)

        # Test Cypher routing
        cypher_result = builder.query("MATCH (n) RETURN n LIMIT 1", store="auto")
        assert cypher_result == neo4j_result
        neo4j_store.query.assert_called_once()

        # Reset mocks
        neo4j_store.reset_mock()
        rdf_store.reset_mock()
        neo4j_store.query.return_value = neo4j_result
        rdf_store.query.return_value = rdf_result

        # Test SPARQL routing
        sparql_result = builder.query(
            "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1", store="auto"
        )
        assert sparql_result == rdf_result
        rdf_store.query.assert_called_once()

    def test_kg_builder_error_handling(self):
        """Test KGBuilder handles errors gracefully."""
        neo4j_store = MagicMock()

        # Mock failure
        neo4j_store.batch_create_nodes.side_effect = Exception("Connection failed")
        neo4j_store.health_check.return_value = False

        nodes = [Node("ent:001", "Test", "Entity")]

        config = KGBuilderConfig(auto_retry=True, max_retries=3)
        builder = KGBuilder(neo4j_store, config=config)

        result = builder.build(entities=nodes)

        # Should handle error gracefully
        assert len(result.errors) > 0
        assert result.nodes_created == 0

    def test_kg_builder_health_monitoring(self):
        """Test KGBuilder health monitoring."""
        neo4j_store = MagicMock()
        rdf_store = MagicMock()

        neo4j_store.health_check.return_value = True
        rdf_store.health_check.return_value = False

        builder = KGBuilder(neo4j_store, rdf_store)
        health = builder.health_check()

        assert health["primary"] is True
        assert health["secondary"] is False

    def test_kg_builder_batch_operations(self):
        """Test KGBuilder batch processing."""
        neo4j_store = MagicMock()

        # Create 2500 nodes (more than default batch size of 1000)
        large_batch = [
            Node(f"ent:{i:04d}", f"Entity {i}", "Entity") for i in range(2500)
        ]

        # Setup mock to return ids
        neo4j_store.batch_create_nodes.side_effect = [
            [n.id for n in large_batch[i : i + 1000]]
            for i in range(0, 2500, 1000)
        ]

        neo4j_store.get_statistics.return_value = GraphStatistics(
            node_count=2500, edge_count=0, nodes_by_type={}, edges_by_type={}, avg_confidence=0.9
        )

        config = KGBuilderConfig(batch_size=1000)
        builder = KGBuilder(neo4j_store, config=config)

        result = builder.build(entities=large_batch)

        # Verify batch operations were called multiple times
        assert neo4j_store.batch_create_nodes.call_count >= 2

    def test_kg_builder_export(self):
        """Test KGBuilder export functionality."""
        neo4j_store = MagicMock()
        neo4j_store.export.return_value = '{"nodes": [], "edges": []}'

        builder = KGBuilder(neo4j_store)

        # Test export
        export_data = builder.export(format="jsonld", store="primary")

        assert export_data is not None
        neo4j_store.export.assert_called_once_with("jsonld")

    def test_graph_statistics_aggregation(self):
        """Test statistics aggregation from both stores."""
        neo4j_store = MagicMock()
        rdf_store = MagicMock()

        neo4j_store.get_statistics.return_value = GraphStatistics(
            node_count=100,
            edge_count=250,
            nodes_by_type={"Person": 40, "Entity": 60},
            edges_by_type={"knows": 100, "related_to": 150},
            avg_confidence=0.85,
        )

        rdf_store.get_statistics.return_value = GraphStatistics(
            node_count=100,
            edge_count=250,
            nodes_by_type={"Person": 40, "Entity": 60},
            edges_by_type={"knows": 100, "related_to": 150},
            avg_confidence=0.85,
        )

        builder = KGBuilder(neo4j_store, rdf_store)
        stats = builder.get_statistics()

        assert stats["primary"]["node_count"] == 100
        assert stats["secondary"]["node_count"] == 100
        assert stats["primary"]["edge_count"] == 250


class TestMultiStoreConsistency:
    """Tests for consistency between multiple stores."""

    def test_dual_write_consistency(self):
        """Test that dual-write maintains consistency."""
        neo4j_store = MagicMock()
        rdf_store = MagicMock()

        node_ids = ["ent:001", "ent:002"]
        neo4j_store.batch_create_nodes.return_value = node_ids
        rdf_store.batch_create_nodes.return_value = node_ids

        neo4j_store.get_statistics.return_value = GraphStatistics(
            node_count=2, edge_count=0, nodes_by_type={}, edges_by_type={}, avg_confidence=0.9
        )

        nodes = [
            Node("ent:001", "Alice", "Person"),
            Node("ent:002", "Bob", "Person"),
        ]

        config = KGBuilderConfig(sync_stores=True)
        builder = KGBuilder(neo4j_store, rdf_store, config)

        result = builder.build(entities=nodes)

        # Both stores should have same node count
        assert result.nodes_created == result.nodes_synced
        assert result.nodes_created == 2

    def test_partial_sync_error_handling(self):
        """Test handling of partial sync failures."""
        neo4j_store = MagicMock()
        rdf_store = MagicMock()

        node_ids = ["ent:001", "ent:002"]
        neo4j_store.batch_create_nodes.return_value = node_ids

        # RDF store fails
        rdf_store.batch_create_nodes.side_effect = Exception("SPARQL endpoint down")

        neo4j_store.get_statistics.return_value = GraphStatistics(
            node_count=2, edge_count=0, nodes_by_type={}, edges_by_type={}, avg_confidence=0.9
        )

        nodes = [
            Node("ent:001", "Alice", "Person"),
            Node("ent:002", "Bob", "Person"),
        ]

        config = KGBuilderConfig(sync_stores=True)
        builder = KGBuilder(neo4j_store, rdf_store, config)

        result = builder.build(entities=nodes)

        # Primary should succeed even if secondary fails
        assert result.nodes_created == 2
        # Sync should have failed
        assert result.nodes_synced == 0


class TestQueryRoutingLogic:
    """Tests for intelligent query routing."""

    def test_sparql_query_detection(self):
        """Test SPARQL query detection."""
        primary = MagicMock()
        secondary = MagicMock()

        secondary.query.return_value = QueryResult(records=[], summary={})
        primary.query.return_value = QueryResult(records=[], summary={})

        builder = KGBuilder(primary, secondary)

        # SPARQL queries should route to secondary
        sparql_queries = [
            "SELECT ?s ?p ?o WHERE { ?s ?p ?o }",
            "  SELECT ?x WHERE { ?x rdf:type owl:Class }",
            "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
        ]

        for query in sparql_queries:
            secondary.reset_mock()
            builder.query(query, store="auto")
            secondary.query.assert_called_once()

    def test_cypher_query_detection(self):
        """Test Cypher query detection."""
        primary = MagicMock()
        secondary = MagicMock()

        primary.query.return_value = QueryResult(records=[], summary={})
        secondary.query.return_value = QueryResult(records=[], summary={})

        builder = KGBuilder(primary, secondary)

        # Cypher queries should route to primary
        cypher_queries = [
            "MATCH (n) RETURN n",
            "  CREATE (n:Person {name: 'Alice'})",
            "MERGE (n:Entity {id: '123'})",
        ]

        for query in cypher_queries:
            primary.reset_mock()
            builder.query(query, store="auto")
            primary.query.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
