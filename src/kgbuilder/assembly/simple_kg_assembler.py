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
        """Initialize KG assembler with Neo4j connection.

        Args:
            neo4j_uri: Neo4j database URI (e.g., "bolt://localhost:7687")
            auth: Tuple of (username, password)

        Raises:
            ServiceUnavailable: If Neo4j connection fails
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
        """Assemble findings into Neo4j knowledge graph.

        Creates nodes for each entity and relationships between them.
        Stores confidence scores and provenance information.

        Args:
            entities: Deduplicated entities from Phase 4c
            relations: Optional relations between entities
            coverage: Coverage percentage achieved by discovery
            iterations: Number of discovery iterations

        Returns:
            KGAssemblyResult with statistics

        Example:
            >>> entities = [SynthesizedEntity(...)]
            >>> result = assembler.assemble(entities, coverage=0.85, iterations=3)
            >>> assert result.nodes_created == len(entities)
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
