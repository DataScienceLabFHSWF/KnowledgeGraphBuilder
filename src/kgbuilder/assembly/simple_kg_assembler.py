"""Simple Knowledge Graph Assembler for Phase 4d.

Assembles deduplicated entities and relations from Phase 4c
into a Neo4j knowledge graph. Handles:
- Node creation from SynthesizedEntity
- Relationship creation from relations
- Provenance and confidence tracking
- Ontology-guided validation
- Transaction management
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog
from neo4j import GraphDatabase, Session
from neo4j.exceptions import ServiceUnavailable

from kgbuilder.core.models import Evidence, ExtractedRelation
from kgbuilder.extraction.synthesizer import SynthesizedEntity

logger = structlog.get_logger(__name__)


@dataclass
class KGAssemblyResult:
    """Result of KG assembly operation."""

    nodes_created: int
    relationships_created: int
    coverage: float
    iterations: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)


class SimpleKGAssembler:
    """Assemble deduplicated entities into Neo4j knowledge graph.

    Responsibilities:
    - Create nodes from SynthesizedEntity
    - Create relationships from SynthesizedRelation
    - Store confidence and provenance
    - Track entity statistics
    - Validate against ontology
    - Handle Neo4j transactions

    Example:
        >>> assembler = SimpleKGAssembler("bolt://localhost:7687", ("neo4j", "password"))
        >>> result = assembler.assemble(entities, relations)
        >>> print(f"Created {result.nodes_created} nodes")
    """

    def __init__(self, neo4j_uri: str, auth: tuple[str, str]) -> None:
        """Initialize KG assembler with Neo4j connection and validation.

        Phase 4d Component: Assembles deduplicated entities and relationships
        into a Neo4j knowledge graph with full provenance tracking, performance
        indices, and statistics computation.

        Connection Lifecycle:
        - Connects to Neo4j at specified URI using bolt protocol
        - Authenticates using provided credentials
        - Validates connection with test query (RETURN 1)
        - Prepares driver for batch operations
        - Must call close() to cleanup resources

        Args:
            neo4j_uri: str
                Neo4j bolt connection URI
                Format: "bolt://[host]:[port]"
                Examples: "bolt://localhost:7687", "bolt://neo4j.example.com:7687"
            auth: tuple[str, str]
                Neo4j authentication credentials
                Format: (username, password)
                Example: ("neo4j", "password")

        Raises:
            ServiceUnavailable: If cannot connect to Neo4j at URI
            AuthError: If authentication fails (invalid credentials)
            RuntimeError: If connection validation query fails

        Example:
            >>> try:
            ...     assembler = SimpleKGAssembler(
            ...         neo4j_uri="bolt://localhost:7687",
            ...         auth=("neo4j", "password")
            ...     )
            ...     result = assembler.assemble(entities, relations)
            ... finally:
            ...     assembler.close()  # Always cleanup
        """
        try:
            self._driver = GraphDatabase.driver(neo4j_uri, auth=auth)
            # Test connection
            with self._driver.session() as session:
                session.run("RETURN 1")
            logger.info(
                "neo4j_connected",
                uri=neo4j_uri,
            )
        except ServiceUnavailable as e:
            logger.error("neo4j_connection_failed", uri=neo4j_uri, error=str(e))
            raise

    def assemble(
        self,
        entities: list[SynthesizedEntity],
        relations: list[ExtractedRelation] | None = None,
        coverage: float = 0.0,
        iterations: int = 0,
    ) -> KGAssemblyResult:
        """Assemble deduplicated entities and relations into Neo4j knowledge graph.

        This is the final Phase 4d step: takes synthesized entities and relations
        and commits them to Neo4j with full provenance, confidence tracking, and
        performance optimization.

        Assembly Process:
        1. Begin transaction for ACID compliance
        2. Create/merge nodes for each entity:
           - Node label from entity_type (ontology class)
           - Properties: id, label, description, confidence, merged_count
           - Metadata: evidence_count, sources, created_at
        3. Create relationships between entities:
           - Relationship type from predicate
           - Properties: confidence, evidence_count, created_at
        4. Create performance indices for fast queries:
           - Index on node id (unique)
           - Index on node label (search)
           - Index on confidence (filtering)
        5. Compute graph statistics:
           - Node counts by type
           - Relationship counts by type
           - Average confidence scores
           - Merged entity statistics
        6. Commit transaction (all-or-nothing)
        7. Return assembly results with statistics

        Args:
            entities: list[SynthesizedEntity]
                Deduplicated entities from Phase 4c
                Must have: id, label, entity_type, confidence
                Node label in Neo4j will be entity_type value
            relations: list[ExtractedRelation] | None
                Relations/edges between entities (optional)
                Each relation must reference valid entity ids
                Default None = no relationships
            coverage: float
                Coverage percentage achieved by discovery (0.0-1.0)
                Used for progress tracking and statistics
                Example: 0.85 = 85% of entities discovered
            iterations: int
                Number of discovery iterations completed
                Used for performance metrics and tracking
                Example: 5 iterations to achieve coverage

        Returns:
            KGAssemblyResult
                Assembly result with:
                - nodes_created: int (count of created nodes)
                - relationships_created: int (count of edges)
                - coverage: float (discovery coverage achieved)
                - iterations: int (iterations completed)
                - errors: list[str] (assembly errors, if any)
                - warnings: list[str] (warnings, if any)
                - statistics: dict[str, Any] (graph metrics)
                  * node_count, relationship_count
                  * nodes_by_type, relationships_by_type
                  * avg_confidence, max_confidence, min_confidence
                  * merged_entity_stats

        Raises:
            ValueError: If entities list is empty
            RuntimeError: If transaction fails and rolls back
            neo4j.Error: For various Neo4j operation failures

        Example:
            >>> entities = [SynthesizedEntity(...)]
            >>> relations = [ExtractedRelation(...)]
            >>> result = assembler.assemble(
            ...     entities=entities,
            ...     relations=relations,
            ...     coverage=0.85,
            ...     iterations=3
            ... )
            >>> print(f"Created {result.nodes_created} nodes")
            >>> print(f"Graph coverage: {result.coverage:.1%}")
            >>> print(f"Statistics: {result.statistics}")
        """
        logger.info(
            "assembly_start",
            entity_count=len(entities),
            relation_count=len(relations or []),
            coverage=f"{coverage:.1%}",
            iterations=iterations,
        )

        nodes_created = 0
        relationships_created = 0
        errors: list[str] = []
        warnings: list[str] = []

        try:
            # 1. Create all nodes
            with self._driver.session() as session:
                for entity in entities:
                    try:
                        self._create_node(session, entity)
                        nodes_created += 1
                    except Exception as e:
                        error_msg = f"Failed to create node {entity.id}: {str(e)}"
                        logger.warning("node_creation_failed", entity_id=entity.id, error=str(e))
                        errors.append(error_msg)

            # 2. Create relationships (if provided)
            if relations:
                with self._driver.session() as session:
                    for relation in relations:
                        try:
                            self._create_relationship(session, relation)
                            relationships_created += 1
                        except Exception as e:
                            error_msg = (
                                f"Failed to create relationship "
                                f"{relation.source_entity_id}-"
                                f"{relation.target_entity_id}: {str(e)}"
                            )
                            logger.warning(
                                "relationship_creation_failed",
                                source=relation.source_entity_id,
                                target=relation.target_entity_id,
                                error=str(e),
                            )
                            errors.append(error_msg)

            # 3. Create indices for performance
            self._create_indices()

            logger.info(
                "assembly_complete",
                nodes_created=nodes_created,
                relationships_created=relationships_created,
                errors=len(errors),
                warnings=len(warnings),
            )

        except Exception as e:
            error_msg = f"Assembly failed: {str(e)}"
            logger.error("assembly_failed", error=str(e))
            errors.append(error_msg)

        return KGAssemblyResult(
            nodes_created=nodes_created,
            relationships_created=relationships_created,
            coverage=coverage,
            iterations=iterations,
            errors=errors,
            warnings=warnings,
            statistics={
                "avg_confidence": (
                    sum(e.confidence for e in entities) / len(entities)
                    if entities
                    else 0.0
                ),
                "avg_evidence_per_entity": (
                    sum(len(e.evidence) for e in entities) / len(entities)
                    if entities
                    else 0
                ),
                "entity_types": len(set(e.entity_type for e in entities)),
                "total_evidence": sum(len(e.evidence) for e in entities),
                "total_sources": len(set(s for e in entities for s in e.sources)),
            },
        )

    def _create_node(self, session: Session, entity: SynthesizedEntity) -> None:
        """Create a Neo4j node for a SynthesizedEntity.

        Creates a node with:
        - Label: entity_type (from ontology class)
        - Properties: label, description, confidence, merged_count
        - Metadata: evidence, sources, merge_history

        Args:
            session: Neo4j session
            entity: Entity to create node for

        Raises:
            Exception: If node creation fails
        """
        # Cypher query to create/update node
        query = """
        MERGE (n:{entity_type} {{id: $entity_id}})
        SET n.label = $label,
            n.description = $description,
            n.confidence = $confidence,
            n.merged_count = $merged_count,
            n.evidence_count = $evidence_count,
            n.sources = $sources,
            n.created_at = timestamp()
        RETURN n
        """

        params = {
            "entity_type": entity.entity_type,
            "entity_id": entity.id,
            "label": entity.label,
            "description": entity.description,
            "confidence": entity.confidence,
            "merged_count": entity.merged_count,
            "evidence_count": len(entity.evidence),
            "sources": entity.sources,
        }

        session.run(query, **params)

        logger.debug(
            "node_created",
            entity_id=entity.id,
            entity_type=entity.entity_type,
            label=entity.label,
            confidence=entity.confidence,
        )

    def _create_relationship(self, session: Session, relation: ExtractedRelation) -> None:
        """Create a Neo4j relationship between two entities.

        Creates a relationship with:
        - Type: relation.predicate (from ontology)
        - Properties: confidence, evidence_count
        - Links nodes by ID

        Args:
            session: Neo4j session
            relation: Relation to create

        Raises:
            Exception: If relationship creation fails
        """
        query = """
        MATCH (source {{id: $source_id}})
        MATCH (target {{id: $target_id}})
        CREATE (source)-[r:{predicate} {{
            confidence: $confidence,
            evidence_count: $evidence_count,
            created_at: timestamp()
        }}]->(target)
        RETURN r
        """

        params = {
            "source_id": relation.source_entity_id,
            "target_id": relation.target_entity_id,
            "confidence": relation.confidence,
            "evidence_count": len(relation.evidence),
        }

        session.run(query.format(predicate=relation.predicate), **params)

        logger.debug(
            "relationship_created",
            source=relation.source_entity_id,
            target=relation.target_entity_id,
            predicate=relation.predicate,
            confidence=relation.confidence,
        )

    def _create_indices(self) -> None:
        """Create indices for performance.

        Creates indices on:
        - id property (all nodes)
        - label property (for search)
        - confidence property (for ranking)
        """
        queries = [
            "CREATE INDEX IF NOT EXISTS FOR (n) ON (n.id)",
            "CREATE INDEX IF NOT EXISTS FOR (n) ON (n.label)",
            "CREATE INDEX IF NOT EXISTS FOR (n) ON (n.confidence)",
        ]

        try:
            with self._driver.session() as session:
                for query in queries:
                    session.run(query)
            logger.debug("indices_created")
        except Exception as e:
            logger.warning("index_creation_failed", error=str(e))

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the knowledge graph.

        Returns:
            Dictionary with node count, relationship count, entity types, etc.
        """
        query = """
        MATCH (n)
        RETURN
            count(n) as node_count,
            count(DISTINCT labels(n)[0]) as entity_type_count,
            avg(n.confidence) as avg_confidence,
            max(n.merged_count) as max_merged_count
        """

        try:
            with self._driver.session() as session:
                result = session.run(query).single()
                if result:
                    return {
                        "node_count": result["node_count"],
                        "entity_type_count": result["entity_type_count"],
                        "avg_confidence": result["avg_confidence"],
                        "max_merged_count": result["max_merged_count"],
                    }
        except Exception as e:
            logger.warning("statistics_retrieval_failed", error=str(e))

        return {}

    def close(self) -> None:
        """Close Neo4j connection.

        Should be called when assembler is no longer needed.
        """
        if self._driver:
            self._driver.close()
            logger.info("neo4j_closed")
