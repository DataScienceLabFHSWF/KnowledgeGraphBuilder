"""KG Builder: Multi-Store Orchestrator for Phase 7.

Provides high-level orchestration for knowledge graph building with
support for multiple backends (Neo4j, RDF/SPARQL) with features like
query routing, store synchronization, and health monitoring.

Usage:
    >>> builder = KGBuilder(
    ...     primary_store=Neo4jGraphStore(...),
    ...     secondary_store=RDFGraphStore(...),
    ...     config=KGBuilderConfig(sync=True)
    ... )
    >>> result = builder.build(entities, relations)
    >>> entities = builder.query("MATCH (n) RETURN n LIMIT 10")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from kgbuilder.storage.protocol import (
    GraphStore,
    Node,
    Edge,
    QueryResult,
    GraphStatistics,
)

logger = structlog.get_logger(__name__)


@dataclass
class KGBuilderConfig:
    """Configuration for KGBuilder."""

    primary_store: str = "neo4j"  # "neo4j" or "rdf"
    sync_stores: bool = False  # Sync to secondary store
    query_timeout: int = 30  # Query timeout in seconds
    batch_size: int = 1000  # Batch operation size
    auto_retry: bool = True  # Retry failed operations
    max_retries: int = 3
    # Static validation
    enable_static_validation: bool = False
    static_shapes_path: str | None = None


@dataclass
class KGBuildResult:
    """Result of KG building operation."""

    nodes_created: int = 0
    edges_created: int = 0
    nodes_synced: int = 0
    edges_synced: int = 0
    primary_store: str = ""
    secondary_store: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)


class KGBuilder:
    """Multi-store KG builder with query routing and synchronization.

    Features:
    - Primary/secondary store support
    - Automatic query routing (SPARQL vs Cypher)
    - Store synchronization (dual-write)
    - Health monitoring
    - Batch operations
    - Error recovery

    Example:
        >>> neo4j = Neo4jGraphStore("bolt://localhost:7687", ("neo4j", "pass"))
        >>> rdf = RDFGraphStore("http://localhost:3030/ds")
        >>> builder = KGBuilder(neo4j, rdf, KGBuilderConfig(sync_stores=True))
        >>> result = builder.build(entities, relations)
    """

    def __init__(
        self,
        primary_store: GraphStore,
        secondary_store: GraphStore | None = None,
        config: KGBuilderConfig | None = None,
        static_validator: object | None = None,
        ontology_service: Any | None = None,
    ) -> None:
        """Initialize KG builder.

        Args:
            primary_store: Primary graph store (Neo4j or RDF)
            secondary_store: Optional secondary store for sync
            config: Builder configuration
            ontology_service: Optional ontology backend to use for validation helpers
        """
        self._primary = primary_store
        self._secondary = secondary_store
        self._config = config or KGBuilderConfig()
        self._static_validator = static_validator
        self._ontology_service = ontology_service

        logger.info(
            "kg_builder_initialized",
            primary_store=type(primary_store).__name__,
            secondary_store=type(secondary_store).__name__ if secondary_store else None,
            sync=self._config.sync_stores,
            static_validation_enabled=self._config.enable_static_validation,
        )

    def build(
        self, entities: list[Node], relations: list[Edge] | None = None
    ) -> KGBuildResult:
        """Build KG from entities and relations.

        Args:
            entities: List of nodes
            relations: List of edges

        Returns:
            KGBuildResult with statistics
        """
        result = KGBuildResult(
            primary_store=type(self._primary).__name__,
            secondary_store=type(self._secondary).__name__
            if self._secondary
            else None,
        )

        try:
            # Optional: static validation (pre-commit)
            if self._config.enable_static_validation and self._static_validator:
                try:
                    shapes_path_str = self._config.static_shapes_path
                    if not shapes_path_str:
                        raise ValueError("static_shapes_path must be configured when static validation is enabled")
                    from pathlib import Path

                    shapes_path = Path(shapes_path_str)
                    sv_result = self._static_validator.validate_entities_and_relations(
                        shapes_path, entities, relations or [], ontology_service=self._ontology_service
                    )
                    logger.info("static_validation_result", valid=sv_result.valid)
                    if not sv_result.valid:
                        msg = f"Static validation failed: {sv_result.counterexample or sv_result.error}"
                        logger.warning("static_validation_rejected", reason=msg)
                        result.warnings.append(msg)
                        return result
                except Exception as e:
                    logger.warning("static_validation_error", error=str(e))

            # 1. Create nodes in primary store (in batches)
            logger.info("build_nodes_starting", count=len(entities))
            node_ids = self._batch_operation(
                self._primary.batch_create_nodes, entities, self._config.batch_size
            )
            result.nodes_created = len(node_ids)

            # 2. Create edges in primary store
            if relations:
                logger.info("build_edges_starting", count=len(relations))
                edge_ids = self._batch_operation(
                    self._primary.batch_create_edges,
                    relations,
                    self._config.batch_size,
                )
                result.edges_created = len(edge_ids)

            # 3. Sync to secondary store if enabled
            if self._config.sync_stores and self._secondary:
                logger.info("sync_stores_starting")
                sync_result = self._sync_to_secondary(entities, relations)
                result.nodes_synced = sync_result["nodes"]
                result.edges_synced = sync_result["edges"]

            # 4. Collect statistics
            result.statistics = self._get_statistics()

            logger.info(
                "build_complete",
                nodes_created=result.nodes_created,
                edges_created=result.edges_created,
                nodes_synced=result.nodes_synced,
                edges_synced=result.edges_synced,
            )

        except Exception as e:
            logger.error("build_failed", error=str(e))
            result.errors.append(str(e))

        return result

    def query(
        self,
        query_str: str,
        store: str = "auto",
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute query with automatic routing.

        Auto-detects store:
        - SPARQL queries (SELECT, CONSTRUCT) → secondary (RDF)
        - Cypher queries (MATCH, CREATE) → primary (Neo4j)

        Args:
            query_str: Query string
            store: "auto", "primary", or "secondary"
            params: Query parameters

        Returns:
            QueryResult
        """
        try:
            if store == "auto":
                # Detect query type
                query_upper = query_str.strip().upper()
                if query_upper.startswith("SELECT") or query_upper.startswith(
                    "CONSTRUCT"
                ):
                    # SPARQL query
                    if self._secondary:
                        logger.debug("routing_query_to_secondary", type="SPARQL")
                        return self._secondary.query(query_str, params)
                    else:
                        logger.warning("sparql_requested_but_no_secondary_store")
                else:
                    # Cypher query
                    logger.debug("routing_query_to_primary", type="Cypher")
                    return self._primary.query(query_str, params)
            elif store == "primary":
                return self._primary.query(query_str, params)
            elif store == "secondary":
                if self._secondary:
                    return self._secondary.query(query_str, params)
                else:
                    logger.error("secondary_store_not_available")
                    return QueryResult(records=[], summary={"error": "No secondary store"})

            return QueryResult(records=[], summary={"error": "Invalid store"})

        except Exception as e:
            logger.error("query_failed", store=store, error=str(e))
            return QueryResult(records=[], summary={"error": str(e)})

    def health_check(self) -> dict[str, bool]:
        """Check health of all stores.

        Returns:
            Dict with store names and health status
        """
        status = {
            "primary": False,
            "secondary": False,
        }

        try:
            status["primary"] = self._primary.health_check()
        except Exception as e:
            logger.warning("primary_store_health_check_failed", error=str(e))

        if self._secondary:
            try:
                status["secondary"] = self._secondary.health_check()
            except Exception as e:
                logger.warning("secondary_store_health_check_failed", error=str(e))

        return status

    def get_statistics(self) -> dict[str, Any]:
        """Get combined statistics from all stores.

        Returns:
            Dict with stats for each store
        """
        return {
            "primary": self._get_store_stats(self._primary, "primary"),
            "secondary": (
                self._get_store_stats(self._secondary, "secondary")
                if self._secondary
                else None
            ),
        }

    def export(self, format: str, store: str = "primary") -> str | dict:
        """Export graph to format.

        Supported formats: jsonld, turtle, cypher, graphml

        Args:
            format: Export format
            store: Which store to export from

        Returns:
            Exported data
        """
        try:
            if store == "primary":
                return self._primary.export(format)
            elif store == "secondary" and self._secondary:
                return self._secondary.export(format)
        except Exception as e:
            logger.error("export_failed", format=format, error=str(e))

        return ""

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _batch_operation(
        self,
        operation,
        items: list,
        batch_size: int,
    ) -> list:
        """Execute operation on items in batches.

        Args:
            operation: Function to call (e.g., batch_create_nodes)
            items: Items to process
            batch_size: Size of each batch

        Returns:
            Combined results from all batches
        """
        results = []
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            try:
                batch_results = operation(batch)
                results.extend(batch_results)
            except Exception as e:
                logger.warning("batch_operation_failed", error=str(e))
                if self._config.auto_retry:
                    # Retry individual items
                    for item in batch:
                        try:
                            result = operation([item])
                            results.extend(result)
                        except Exception as retry_err:
                            logger.error(
                                "batch_item_failed", error=str(retry_err)
                            )

        return results

    def _sync_to_secondary(
        self, entities: list[Node], relations: list[Edge] | None = None
    ) -> dict[str, int]:
        """Synchronize data to secondary store.

        Args:
            entities: Nodes to sync
            relations: Edges to sync

        Returns:
            Dict with sync counts
        """
        result = {"nodes": 0, "edges": 0}

        if not self._secondary:
            return result

        try:
            # Sync nodes
            node_ids = self._secondary.batch_create_nodes(entities)
            result["nodes"] = len(node_ids)

            # Sync edges
            if relations:
                edge_ids = self._secondary.batch_create_edges(relations)
                result["edges"] = len(edge_ids)

            logger.info("sync_complete", nodes=result["nodes"], edges=result["edges"])

        except Exception as e:
            logger.error("sync_failed", error=str(e))

        return result

    def _get_statistics(self) -> dict[str, Any]:
        """Get statistics from primary store.

        Returns:
            Statistics dict
        """
        try:
            stats = self._primary.get_statistics()
            return {
                "node_count": stats.node_count,
                "edge_count": stats.edge_count,
                "nodes_by_type": stats.nodes_by_type,
                "edges_by_type": stats.edges_by_type,
                "avg_confidence": stats.avg_confidence,
            }
        except Exception as e:
            logger.warning("statistics_collection_failed", error=str(e))
            return {}

    def _get_store_stats(self, store: GraphStore, store_name: str) -> dict[str, Any]:
        """Get statistics for a specific store.

        Args:
            store: Graph store
            store_name: Store name for logging

        Returns:
            Statistics dict
        """
        try:
            stats = store.get_statistics()
            return {
                "name": store_name,
                "node_count": stats.node_count,
                "edge_count": stats.edge_count,
                "healthy": store.health_check(),
            }
        except Exception as e:
            logger.warning(
                f"{store_name}_stats_failed", error=str(e)
            )
            return {"name": store_name, "error": str(e)}
