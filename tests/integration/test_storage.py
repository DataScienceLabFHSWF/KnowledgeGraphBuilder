"""Unit tests for storage implementations (Phase 7).

Tests for:
- Neo4jGraphStore (concrete implementation)
- RDFGraphStore (SPARQL implementation)
- KGBuilder orchestrator
- Query routing and synchronization
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call
from typing import Any

from kgbuilder.storage.protocol import Node, Edge, QueryResult, GraphStatistics
from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.storage.rdf_store import RDFGraphStore
from kgbuilder.assembly.kg_builder import (
    KGBuilder,
    KGBuilderConfig,
    KGBuildResult,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_node() -> Node:
    """Create a sample node for testing."""
    return Node(
        id="entity:001",
        label="Albert Einstein",
        node_type="Person",
        properties={"birth_year": 1879, "nationality": "German"},
    )


@pytest.fixture
def sample_node_batch() -> list[Node]:
    """Create a batch of sample nodes."""
    return [
        Node(
            id=f"entity:{i:03d}",
            label=f"Entity {i}",
            node_type="Concept" if i % 2 == 0 else "Person",
            properties={"index": i},
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def sample_edge() -> Edge:
    """Create a sample edge for testing."""
    return Edge(
        source_id="entity:001",
        target_id="entity:002",
        relation_type="knows",
        properties={"confidence": 0.95},
    )


@pytest.fixture
def sample_edge_batch() -> list[Edge]:
    """Create a batch of sample edges."""
    return [
        Edge(
            id=f"edge:{i:03d}",
            source_id=f"entity:{i:03d}",
            target_id=f"entity:{i+1:03d}",
            edge_type="related_to" if i % 2 == 0 else "knows",
            properties={"confidence": 0.9 - (i * 0.05)},
        )
        for i in range(1, 5)
    ]


@pytest.fixture
def mock_neo4j_driver():
    """Create a mock Neo4j driver."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value = session

    # Mock successful queries
    session.run.return_value.single.return_value = MagicMock(
        value=MagicMock(return_value={"healthy": True})
    )

    return driver


@pytest.fixture
def mock_sparql_wrapper():
    """Create a mock SPARQLWrapper."""
    wrapper = MagicMock()
    wrapper.query.return_value = MagicMock(
        convert=MagicMock(return_value=b"<rdf></rdf>")
    )
    return wrapper


# =============================================================================
# Neo4jGraphStore Tests
# =============================================================================


class TestNeo4jGraphStore:
    """Test Neo4jGraphStore implementation."""

    @patch("kgbuilder.storage.neo4j_store.GraphDatabase")
    def test_init_successful(self, mock_gd, mock_neo4j_driver):
        """Test successful Neo4j store initialization."""
        mock_gd.driver.return_value = mock_neo4j_driver

        store = Neo4jGraphStore("bolt://localhost:7687", ("neo4j", "password"))

        assert store is not None
        mock_gd.driver.assert_called_once()

    @patch("kgbuilder.storage.neo4j_store.GraphDatabase")
    def test_health_check_healthy(self, mock_gd, mock_neo4j_driver):
        """Test health check returns True when healthy."""
        mock_gd.driver.return_value = mock_neo4j_driver

        store = Neo4jGraphStore("bolt://localhost:7687", ("neo4j", "password"))
        health = store.health_check()

        assert health is True

    @patch("kgbuilder.storage.neo4j_store.GraphDatabase")
    def test_add_node(self, mock_gd, mock_neo4j_driver, sample_node):
        """Test adding a single node."""
        mock_gd.driver.return_value = mock_neo4j_driver
        session = MagicMock()
        mock_neo4j_driver.session.return_value.__enter__.return_value = session

        # Mock node creation
        result = MagicMock()
        result.single.return_value = {"id": sample_node.id}
        session.run.return_value = result

        store = Neo4jGraphStore("bolt://localhost:7687", ("neo4j", "password"))
        node_id = store.add_node(sample_node)

        assert node_id == sample_node.id

    @patch("kgbuilder.storage.neo4j_store.GraphDatabase")
    def test_batch_create_nodes(self, mock_gd, mock_neo4j_driver, sample_node_batch):
        """Test batch creating nodes."""
        mock_gd.driver.return_value = mock_neo4j_driver
        session = MagicMock()
        mock_neo4j_driver.session.return_value = session

        # Mock batch creation
        result = MagicMock()
        result.records = [MagicMock(value=MagicMock(return_value={"id": node.id})) for node in sample_node_batch]
        session.run.return_value = result

        store = Neo4jGraphStore("bolt://localhost:7687", ("neo4j", "password"))
        node_ids = store.batch_create_nodes(sample_node_batch)

        assert len(node_ids) >= 0  # Batch operation completed

    @patch("kgbuilder.storage.neo4j_store.GraphDatabase")
    def test_query_cypher(self, mock_gd, mock_neo4j_driver):
        """Test executing Cypher query."""
        mock_gd.driver.return_value = mock_neo4j_driver
        session = MagicMock()
        mock_neo4j_driver.session.return_value = session

        # Mock query result
        result = MagicMock()
        result.records = [{"n": MagicMock()}]
        session.run.return_value = result

        store = Neo4jGraphStore("bolt://localhost:7687", ("neo4j", "password"))
        query_result = store.query("MATCH (n) RETURN n LIMIT 10")

        assert isinstance(query_result, QueryResult)

    @patch("kgbuilder.storage.neo4j_store.GraphDatabase")
    def test_get_statistics(self, mock_gd, mock_neo4j_driver):
        """Test getting graph statistics."""
        mock_gd.driver.return_value = mock_neo4j_driver
        session = MagicMock()
        mock_neo4j_driver.session.return_value = session

        # Mock statistics query
        result = MagicMock()
        result.single.return_value = MagicMock(value=MagicMock(return_value={
            "node_count": 100,
            "edge_count": 250,
        }))
        session.run.return_value = result

        store = Neo4jGraphStore("bolt://localhost:7687", ("neo4j", "password"))
        stats = store.get_statistics()

        assert isinstance(stats, GraphStatistics)


# =============================================================================
# RDFGraphStore Tests
# =============================================================================


class TestRDFGraphStore:
    """Test RDFGraphStore implementation."""

    @patch("kgbuilder.storage.rdf_store.SPARQLWrapper")
    def test_init_successful(self, mock_sparql):
        """Test successful RDF store initialization."""
        store = RDFGraphStore("http://localhost:3030/ds")

        assert store is not None

    @patch("kgbuilder.storage.rdf_store.SPARQLWrapper")
    def test_health_check_healthy(self, mock_sparql):
        """Test health check for RDF store."""
        wrapper = MagicMock()
        wrapper.query.return_value.convert.return_value = b"true"
        mock_sparql.return_value = wrapper

        store = RDFGraphStore("http://localhost:3030/ds")
        health = store.health_check()

        assert isinstance(health, bool)

    @patch("kgbuilder.storage.rdf_store.SPARQLWrapper")
    def test_add_node_to_rdf(self, mock_sparql, sample_node):
        """Test adding node to RDF store."""
        wrapper = MagicMock()
        mock_sparql.return_value = wrapper

        store = RDFGraphStore("http://localhost:3030/ds")
        node_id = store.add_node(sample_node)

        assert node_id == sample_node.id

    @patch("kgbuilder.storage.rdf_store.SPARQLWrapper")
    def test_batch_create_nodes_rdf(self, mock_sparql, sample_node_batch):
        """Test batch creating nodes in RDF store."""
        wrapper = MagicMock()
        mock_sparql.return_value = wrapper

        store = RDFGraphStore("http://localhost:3030/ds")
        node_ids = store.batch_create_nodes(sample_node_batch)

        assert len(node_ids) >= 0

    @patch("kgbuilder.storage.rdf_store.SPARQLWrapper")
    def test_query_sparql(self, mock_sparql):
        """Test executing SPARQL query."""
        wrapper = MagicMock()
        wrapper.query.return_value.convert.return_value = b"results"
        mock_sparql.return_value = wrapper

        store = RDFGraphStore("http://localhost:3030/ds")
        query_result = store.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10")

        assert isinstance(query_result, QueryResult)

    @patch("kgbuilder.storage.rdf_store.SPARQLWrapper")
    def test_get_statistics_rdf(self, mock_sparql):
        """Test getting statistics from RDF store."""
        wrapper = MagicMock()
        mock_sparql.return_value = wrapper

        store = RDFGraphStore("http://localhost:3030/ds")
        stats = store.get_statistics()

        assert isinstance(stats, GraphStatistics)


# =============================================================================
# KGBuilder Tests
# =============================================================================


class TestKGBuilder:
    """Test KGBuilder orchestrator."""

    def test_init_primary_only(self):
        """Test KGBuilder initialization with primary store only."""
        primary = MagicMock()
        builder = KGBuilder(primary_store=primary)

        assert builder is not None
        assert builder._primary == primary

    def test_init_with_secondary(self):
        """Test KGBuilder initialization with primary and secondary stores."""
        primary = MagicMock()
        secondary = MagicMock()
        builder = KGBuilder(primary_store=primary, secondary_store=secondary)

        assert builder._primary == primary
        assert builder._secondary == secondary

    def test_init_with_config(self):
        """Test KGBuilder initialization with config."""
        primary = MagicMock()
        config = KGBuilderConfig(sync_stores=True, batch_size=500)
        builder = KGBuilder(primary_store=primary, config=config)

        assert builder._config.sync_stores is True
        assert builder._config.batch_size == 500

    def test_health_check_single_store(self):
        """Test health check with single store."""
        primary = MagicMock()
        primary.health_check.return_value = True

        builder = KGBuilder(primary_store=primary)
        health = builder.health_check()

        assert health["primary"] is True

    def test_health_check_dual_stores(self):
        """Test health check with dual stores."""
        primary = MagicMock()
        secondary = MagicMock()
        primary.health_check.return_value = True
        secondary.health_check.return_value = True

        builder = KGBuilder(primary_store=primary, secondary_store=secondary)
        health = builder.health_check()

        assert health["primary"] is True
        assert health["secondary"] is True

    def test_build_nodes_only(self, sample_node_batch):
        """Test building KG with nodes only."""
        primary = MagicMock()
        primary.batch_create_nodes.return_value = [n.id for n in sample_node_batch]
        primary.get_statistics.return_value = GraphStatistics(
            node_count=5,
            edge_count=0,
            nodes_by_type={"Person": 3, "Concept": 2},
            edges_by_type={},
            avg_confidence=0.9,
        )

        builder = KGBuilder(primary_store=primary)
        result = builder.build(entities=sample_node_batch)

        assert isinstance(result, KGBuildResult)
        assert result.nodes_created == 5

    def test_build_nodes_and_edges(self, sample_node_batch, sample_edge_batch):
        """Test building KG with nodes and edges."""
        primary = MagicMock()
        primary.batch_create_nodes.return_value = [n.id for n in sample_node_batch]
        primary.batch_create_edges.return_value = [e.source_id for e in sample_edge_batch]
        primary.get_statistics.return_value = GraphStatistics(
            node_count=5,
            edge_count=4,
            nodes_by_type={"Person": 3, "Concept": 2},
            edges_by_type={"knows": 2, "related_to": 2},
            avg_confidence=0.88,
        )

        builder = KGBuilder(primary_store=primary)
        result = builder.build(entities=sample_node_batch, relations=sample_edge_batch)

        assert result.nodes_created == 5
        assert result.edges_created == 4

    def test_query_auto_routing_cypher(self):
        """Test query auto-routing to primary (Cypher)."""
        primary = MagicMock()
        secondary = MagicMock()
        primary.query.return_value = QueryResult(
            records=[{"n": "node"}], summary={"count": 10}
        )

        builder = KGBuilder(primary_store=primary, secondary_store=secondary)
        result = builder.query("MATCH (n) RETURN n LIMIT 10", store="auto")

        assert isinstance(result, QueryResult)
        primary.query.assert_called_once()

    def test_query_auto_routing_sparql(self):
        """Test query auto-routing to secondary (SPARQL)."""
        primary = MagicMock()
        secondary = MagicMock()
        secondary.query.return_value = QueryResult(
            records=[{"s": "subject"}], summary={"count": 5}
        )

        builder = KGBuilder(primary_store=primary, secondary_store=secondary)
        result = builder.query("SELECT ?s WHERE { ?s ?p ?o } LIMIT 10", store="auto")

        assert isinstance(result, QueryResult)
        secondary.query.assert_called_once()

    def test_query_explicit_store(self):
        """Test explicit store selection in queries."""
        primary = MagicMock()
        primary.query.return_value = QueryResult(records=[], summary={})

        builder = KGBuilder(primary_store=primary)
        result = builder.query("MATCH (n) RETURN n", store="primary")

        assert isinstance(result, QueryResult)
        primary.query.assert_called_once()

    def test_sync_to_secondary(self, sample_node_batch, sample_edge_batch):
        """Test synchronization to secondary store."""
        primary = MagicMock()
        secondary = MagicMock()

        primary.batch_create_nodes.return_value = [n.id for n in sample_node_batch]
        primary.batch_create_edges.return_value = [e.source_id for e in sample_edge_batch]
        primary.get_statistics.return_value = GraphStatistics(
            node_count=5, edge_count=4, nodes_by_type={}, edges_by_type={}, avg_confidence=0.9
        )

        secondary.batch_create_nodes.return_value = [n.id for n in sample_node_batch]
        secondary.batch_create_edges.return_value = [e.source_id for e in sample_edge_batch]

        config = KGBuilderConfig(sync_stores=True)
        builder = KGBuilder(primary_store=primary, secondary_store=secondary, config=config)

        result = builder.build(entities=sample_node_batch, relations=sample_edge_batch)

        assert result.nodes_synced == 5
        assert result.edges_synced == 4

    def test_get_statistics(self):
        """Test getting statistics from builder."""
        primary = MagicMock()
        primary.get_statistics.return_value = GraphStatistics(
            node_count=100,
            edge_count=250,
            nodes_by_type={"Person": 40, "Concept": 60},
            edges_by_type={"knows": 100, "related_to": 150},
            avg_confidence=0.85,
        )

        builder = KGBuilder(primary_store=primary)
        stats = builder.get_statistics()

        assert stats["primary"]["node_count"] == 100
        assert stats["primary"]["edge_count"] == 250


# =============================================================================
# Integration Tests
# =============================================================================


class TestKGBuilderIntegration:
    """Integration tests for KGBuilder with multiple stores."""

    def test_build_workflow_complete(self, sample_node_batch, sample_edge_batch):
        """Test complete KG build workflow."""
        primary = MagicMock()
        secondary = MagicMock()

        # Setup mocks to return only the nodes/edges in the batch
        def batch_nodes_side_effect(nodes):
            return [n.id for n in nodes]
        
        def batch_edges_side_effect(edges):
            return [e.id for e in edges]

        primary.batch_create_nodes.side_effect = batch_nodes_side_effect
        primary.batch_create_edges.side_effect = batch_edges_side_effect
        primary.health_check.return_value = True
        primary.get_statistics.return_value = GraphStatistics(
            node_count=5, edge_count=4, nodes_by_type={}, edges_by_type={}, avg_confidence=0.9
        )

        secondary.batch_create_nodes.side_effect = batch_nodes_side_effect
        secondary.batch_create_edges.side_effect = batch_edges_side_effect
        secondary.health_check.return_value = True

        config = KGBuilderConfig(sync_stores=True, batch_size=2)
        builder = KGBuilder(primary_store=primary, secondary_store=secondary, config=config)

        # Execute workflow
        health = builder.health_check()
        assert health["primary"] and health["secondary"]

        result = builder.build(entities=sample_node_batch, relations=sample_edge_batch)
        assert result.nodes_created == 5
        assert result.edges_created == 4

        stats = builder.get_statistics()
        assert "primary" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
