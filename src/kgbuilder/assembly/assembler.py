"""Knowledge Graph Assembler - converts entities/relations to graph.

This module provides the KGAssembler class that takes synthesized entities
and relations from the extraction pipeline and assembles them into a
knowledge graph using any GraphStore backend.

The assembler is backend-agnostic: it works with InMemoryGraphStore for
testing/export, Neo4jGraphStore for production, or RDFGraphStore for
semantic web applications.

Pipeline Position:
    Documents → Chunks → Embeddings → RAG → Extraction → Synthesis → [ASSEMBLER] → KG

Usage:
    from kgbuilder.assembly import KGAssembler
    from kgbuilder.storage.protocol import create_graph_store
    
    # Use in-memory for testing or JSON export
    store = create_graph_store("memory")
    assembler = KGAssembler(store)
    
    # Assemble from synthesized entities
    result = assembler.assemble(entities, relations)
    
    # Export to JSON
    if hasattr(store, "to_json"):
        json_output = store.to_json()
        
    # Or use Neo4j for production
    store = create_graph_store("neo4j", uri="bolt://localhost:7687", auth=("neo4j", "pass"))
    assembler = KGAssembler(store)
    result = assembler.assemble(entities, relations)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from kgbuilder.core.models import ExtractedRelation
from kgbuilder.extraction.synthesizer import SynthesizedEntity
from kgbuilder.storage.protocol import Edge, GraphStatistics, GraphStore, Node

logger = structlog.get_logger(__name__)


# =============================================================================
# RESULT DATA CLASS
# =============================================================================


@dataclass
class KGAssemblyResult:
    """Result of KG assembly operation.
    
    Attributes:
        nodes_created: Number of nodes created in the graph
        edges_created: Number of edges/relationships created
        nodes_updated: Number of existing nodes updated (merged)
        edges_skipped: Number of edges skipped (missing nodes)
        errors: List of error messages encountered
        warnings: List of warning messages
        statistics: Graph statistics after assembly
        assembly_time_sec: Time taken for assembly
    """

    nodes_created: int = 0
    edges_created: int = 0
    nodes_updated: int = 0
    edges_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    statistics: GraphStatistics | None = None
    assembly_time_sec: float = 0.0

    @property
    def success(self) -> bool:
        """True if assembly completed without errors."""
        return len(self.errors) == 0


# =============================================================================
# KG ASSEMBLER
# =============================================================================


class KGAssembler:
    """Assemble synthesized entities and relations into a knowledge graph.
    
    This class converts the output of the extraction/synthesis pipeline
    into a proper knowledge graph stored in any GraphStore backend.
    
    The assembler:
    1. Converts SynthesizedEntity → Node
    2. Converts ExtractedRelation → Edge
    3. Stores evidence and confidence as properties
    4. Tracks provenance (merge history, sources)
    5. Computes assembly statistics
    
    Backend Agnostic:
        Works with any GraphStore implementation (InMemory, Neo4j, RDF).
        Use InMemoryGraphStore for testing or to export JSON before
        loading into a database.
    
    Example:
        >>> from kgbuilder.storage.protocol import InMemoryGraphStore
        >>> store = InMemoryGraphStore()
        >>> assembler = KGAssembler(store)
        >>> result = assembler.assemble(entities, relations)
        >>> print(f"Created {result.nodes_created} nodes")
        >>> print(store.to_json())  # Export to JSON
    """

    def __init__(
        self,
        graph_store: GraphStore,
        *,
        include_evidence: bool = True,
        include_provenance: bool = True,
    ) -> None:
        """Initialize the assembler with a graph store.
        
        Args:
            graph_store: The GraphStore backend to use
            include_evidence: Include evidence text in node properties
            include_provenance: Include merge history in node metadata
        """
        self._store = graph_store
        self._include_evidence = include_evidence
        self._include_provenance = include_provenance
        logger.info(
            "kg_assembler_initialized",
            store_type=type(graph_store).__name__,
            include_evidence=include_evidence,
            include_provenance=include_provenance,
        )

    def assemble(
        self,
        entities: list[SynthesizedEntity],
        relations: list[ExtractedRelation] | None = None,
    ) -> KGAssemblyResult:
        """Assemble entities and relations into the knowledge graph.
        
        This is the main entry point for KG construction. It converts
        synthesized entities to nodes and extracted relations to edges.
        
        Args:
            entities: List of synthesized (deduplicated) entities
            relations: Optional list of relations between entities
            
        Returns:
            KGAssemblyResult with counts, errors, and statistics
            
        Example:
            >>> result = assembler.assemble(entities, relations)
            >>> if result.success:
            ...     print(f"KG built: {result.nodes_created} nodes, {result.edges_created} edges")
            ... else:
            ...     print(f"Errors: {result.errors}")
        """
        start_time = datetime.now(tz=timezone.utc)
        result = KGAssemblyResult()

        logger.info(
            "assembly_start",
            entity_count=len(entities),
            relation_count=len(relations) if relations else 0,
        )

        # Track entity ID mapping (for relation resolution)
        entity_ids: set[str] = set()

        # -----------------------------------------------------------------
        # Step 1: Create nodes from entities
        # -----------------------------------------------------------------
        for entity in entities:
            try:
                node = self._entity_to_node(entity)
                self._store.add_node(node)
                entity_ids.add(entity.id)
                result.nodes_created += 1
            except Exception as e:
                error_msg = f"Failed to create node for entity {entity.id}: {e}"
                result.errors.append(error_msg)
                logger.error("node_creation_failed", entity_id=entity.id, error=str(e))

        logger.info("nodes_created", count=result.nodes_created)

        # -----------------------------------------------------------------
        # Step 2: Create edges from relations
        # -----------------------------------------------------------------
        if relations:
            for relation in relations:
                # Check that both nodes exist
                if relation.source_entity_id not in entity_ids:
                    result.edges_skipped += 1
                    result.warnings.append(
                        f"Skipped relation {relation.id}: source {relation.source_entity_id} not found"
                    )
                    continue
                if relation.target_entity_id not in entity_ids:
                    result.edges_skipped += 1
                    result.warnings.append(
                        f"Skipped relation {relation.id}: target {relation.target_entity_id} not found"
                    )
                    continue

                try:
                    edge = self._relation_to_edge(relation)
                    self._store.add_edge(edge)
                    result.edges_created += 1
                except Exception as e:
                    error_msg = f"Failed to create edge for relation {relation.id}: {e}"
                    result.errors.append(error_msg)
                    logger.error("edge_creation_failed", relation_id=relation.id, error=str(e))

        logger.info("edges_created", count=result.edges_created, skipped=result.edges_skipped)

        # -----------------------------------------------------------------
        # Step 3: Compute statistics
        # -----------------------------------------------------------------
        result.statistics = self._store.get_statistics()

        # Calculate assembly time
        end_time = datetime.now(tz=timezone.utc)
        result.assembly_time_sec = (end_time - start_time).total_seconds()

        logger.info(
            "assembly_complete",
            nodes=result.nodes_created,
            edges=result.edges_created,
            errors=len(result.errors),
            warnings=len(result.warnings),
            time_sec=result.assembly_time_sec,
        )

        return result

    def _entity_to_node(self, entity: SynthesizedEntity) -> Node:
        """Convert a SynthesizedEntity to a Node.
        
        Args:
            entity: The synthesized entity
            
        Returns:
            Node ready for storage
        """
        # Build properties dict
        properties: dict[str, Any] = {
            "confidence": entity.confidence,
            "description": entity.description,
            "merge_count": entity.merge_count,
        }

        # Add aliases if present
        if hasattr(entity, "aliases") and entity.aliases:
            properties["aliases"] = entity.aliases

        # Add evidence summaries
        if self._include_evidence and entity.evidence:
            properties["evidence_count"] = len(entity.evidence)
            properties["evidence_sources"] = list(set(
                e.source_id for e in entity.evidence if e.source_id
            ))[:10]  # Limit to 10 sources
            # Include first evidence text span as sample
            if entity.evidence[0].text_span:
                properties["evidence_sample"] = entity.evidence[0].text_span[:200]

        # Build metadata dict
        metadata: dict[str, Any] = {
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        # Add provenance (merge history)
        if self._include_provenance and hasattr(entity, "merged_from"):
            metadata["merged_from"] = entity.merged_from

        return Node(
            id=entity.id,
            label=entity.label,
            node_type=entity.entity_type,
            properties=properties,
            metadata=metadata,
        )

    def _relation_to_edge(self, relation: ExtractedRelation) -> Edge:
        """Convert an ExtractedRelation to an Edge.
        
        Args:
            relation: The extracted relation
            
        Returns:
            Edge ready for storage
        """
        properties: dict[str, Any] = {
            "confidence": relation.confidence,
        }

        # Add evidence if available
        if self._include_evidence and relation.evidence:
            properties["evidence_count"] = len(relation.evidence)
            if relation.evidence[0].text_span:
                properties["evidence_sample"] = relation.evidence[0].text_span[:200]

        return Edge(
            id=relation.id,
            source_id=relation.source_entity_id,
            target_id=relation.target_entity_id,
            edge_type=relation.predicate,
            properties=properties,
            metadata={"created_at": datetime.now(tz=timezone.utc).isoformat()},
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def assemble_to_json(
    entities: list[SynthesizedEntity],
    relations: list[ExtractedRelation] | None = None,
) -> str:
    """Convenience function: assemble entities/relations and export to JSON.
    
    This is the simplest way to get a KG output without any database.
    
    Args:
        entities: Synthesized entities from the pipeline
        relations: Optional relations between entities
        
    Returns:
        JSON string of the knowledge graph
        
    Example:
        >>> json_kg = assemble_to_json(entities, relations)
        >>> with open("output/kg.json", "w") as f:
        ...     f.write(json_kg)
    """
    from kgbuilder.storage.protocol import InMemoryGraphStore

    store = InMemoryGraphStore()
    assembler = KGAssembler(store)
    assembler.assemble(entities, relations)
    return store.to_json()


def assemble_to_dict(
    entities: list[SynthesizedEntity],
    relations: list[ExtractedRelation] | None = None,
) -> dict[str, Any]:
    """Convenience function: assemble entities/relations and export to dict.
    
    Args:
        entities: Synthesized entities from the pipeline
        relations: Optional relations between entities
        
    Returns:
        Dictionary with nodes, edges, and metadata
    """
    from kgbuilder.storage.protocol import InMemoryGraphStore

    store = InMemoryGraphStore()
    assembler = KGAssembler(store)
    assembler.assemble(entities, relations)
    return store.to_dict()
