"""Graph database implementations using Neo4j.

Implementation of Issue #6.2: Property Graph Store

Key features:
- Neo4j graph database backend
- Entity and relation storage
- Graph query support
- Transaction management
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation


@runtime_checkable
class GraphStore(Protocol):
    """Protocol for property graph database implementations."""

    def add_node(
        self,
        node_id: str,
        label: str,
        properties: dict[str, Any],
    ) -> None:
        """Add or update a node.

        Args:
            node_id: Unique node identifier
            label: Node label/type
            properties: Node properties
        """
        ...

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: dict[str, Any],
    ) -> None:
        """Add or update an edge/relation.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            relation_type: Relation type
            properties: Relation properties
        """
        ...

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Execute a Cypher query.

        Args:
            cypher: Cypher query string
            params: Query parameters

        Returns:
            Query results
        """
        ...


class Neo4jStore:
    """Neo4j property graph store implementation.

    TODO (Implementation):
    - [ ] Implement __init__() with Neo4j connection
    - [ ] Implement add_node() with entity creation
    - [ ] Implement add_edge() with relation creation
    - [ ] Implement query() for Cypher execution
    - [ ] Implement batch operations for efficiency
    - [ ] Implement transaction management
    - [ ] Implement schema/index creation
    - [ ] Add error handling and retry logic
    - [ ] Add unit tests with Neo4j test container

    Dependencies: neo4j>=5.0.0

    See Planning/INTERFACES.md Section 6.2 for protocol definition.
    See Planning/ISSUES_BACKLOG.md Issue #6.2 for acceptance criteria.
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize Neo4j store.

        Args:
            uri: Neo4j connection URI
            username: Neo4j username (None for no auth)
            password: Neo4j password (None for no auth)
        """
        from neo4j import GraphDatabase

        self.uri = uri
        self.username = username
        self.password = password
        
        # Support both auth and no-auth scenarios
        if username and password:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
        else:
            self.driver = GraphDatabase.driver(uri)
        
        self._verify_connection()
        self._create_constraints()

    def _verify_connection(self) -> None:
        """Verify Neo4j connection is working."""
        with self.driver.session() as session:
            result = session.run("RETURN 1 as ping")
            result.consume()

    def _create_constraints(self) -> None:
        """Create uniqueness constraints for efficient lookups."""
        with self.driver.session() as session:
            # Create constraint on entity ID
            session.run(
                "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
            )
            # Create constraint on document ID
            session.run(
                "CREATE CONSTRAINT document_id_unique IF NOT EXISTS "
                "FOR (d:Document) REQUIRE d.id IS UNIQUE"
            )

    def add_node(
        self,
        node_id: str,
        label: str,
        properties: dict[str, Any],
    ) -> None:
        """Add or update a node in Neo4j.

        Args:
            node_id: Unique node identifier
            label: Node label/type
            properties: Node properties (including id)
        """
        with self.driver.session() as session:
            # Merge ensures idempotency
            cypher = f"""
            MERGE (n:{label} {{id: $node_id}})
            SET n += $properties
            """
            session.run(cypher, node_id=node_id, properties=properties)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: dict[str, Any],
    ) -> None:
        """Add or update an edge in Neo4j.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            relation_type: Relation type
            properties: Relation properties
        """
        with self.driver.session() as session:
            cypher = f"""
            MATCH (source {{id: $source_id}}), (target {{id: $target_id}})
            MERGE (source)-[r:{relation_type}]->(target)
            SET r += $properties
            """
            session.run(
                cypher,
                source_id=source_id,
                target_id=target_id,
                properties=properties,
            )

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Execute a Cypher query.

        Args:
            cypher: Cypher query string
            params: Query parameters

        Returns:
            Query results
        """
        params = params or {}
        with self.driver.session() as session:
            result = session.run(cypher, params)
            return [dict(record) for record in result]

    def add_entities(self, entities: list[ExtractedEntity]) -> None:
        """Batch add extracted entities.

        Args:
            entities: Extracted entities to persist
        """
        for entity in entities:
            properties = {
                "label": entity.label,
                "entity_type": entity.entity_type,
                "confidence": entity.confidence,
                "description": entity.description,
            }
            self.add_node(entity.id, "Entity", properties)

    def add_relations(self, relations: list[ExtractedRelation]) -> None:
        """Batch add extracted relations.

        Args:
            relations: Extracted relations to persist
        """
        for relation in relations:
            properties = {
                "predicate": relation.predicate,
                "confidence": relation.confidence,
            }
            self.add_edge(
                relation.source_entity_id,
                relation.target_entity_id,
                relation.predicate,
                properties,
            )

    def create_constraints(self) -> None:
        """Create Neo4j uniqueness constraints for KG IDs."""
        self._create_constraints()
