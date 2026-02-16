"""Knowledge Graph Inference Engine.

Implements OWL-RL inspired reasoning for Neo4j Knowledge Graphs.
Materializes inferred relations (symmetry, inversion, transitivity)
directly in the graph to improve query performance and discoverability.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.storage.ontology import FusekiOntologyService

logger = structlog.get_logger(__name__)


class Neo4jInferenceEngine:
    """Runs semantic inference on Neo4j using ontology metadata."""

    def __init__(
        self,
        graph_store: Neo4jGraphStore,
        ontology_service: FusekiOntologyService
    ) -> None:
        """Initialize inference engine.

        Args:
            graph_store: Target Neo4j graph store
            ontology_service: Source ontology service
        """
        self.graph_store = graph_store
        self.ontology_service = ontology_service

    def run_full_inference(self) -> dict[str, int]:
        """Run all enabled inference rules.

        Returns:
            Dict mapping rule name to number of edges created/updated
        """
        logger.info("Starting full KG inference run")
        start_time = datetime.now()

        # Load metadata
        characteristics = self.ontology_service.get_special_properties()

        stats = {}

        # 1. Symmetry
        stats["symmetric"] = self.materialize_symmetry(characteristics.get("symmetric", []))

        # 2. Inversion
        stats["inverse"] = self.materialize_inversions(characteristics.get("inverse", []))

        # 3. Class Hierarchy (subClassOf)
        hierarchy = self.ontology_service.get_class_hierarchy()
        stats["subclass"] = self.materialize_class_hierarchy(hierarchy)

        # 4. Transitivity
        stats["transitive"] = self.materialize_transitivity(characteristics.get("transitive", []))

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            "KG inference completed",
            duration_seconds=duration,
            stats=stats
        )
        return stats

    def materialize_symmetry(self, properties: list[str]) -> int:
        """Create bidirectional edges for symmetric properties.
        
        Args:
            properties: List of property labels defined as symmetric
            
        Returns:
            Number of edges created
        """
        if not properties:
            return 0

        total_created = 0
        for prop in properties:
            logger.debug(f"Applying symmetry rule for property: {prop}")

            # Cypher to find missing symmetric edges
            # MATCH (a)-[r:PROP]->(b)
            # WHERE NOT (b)-[:PROP]->(a)
            # MERGE (b)-[new:PROP]->(a)
            query = f"""
            MATCH (a)-[r:{prop}]->(b)
            WHERE NOT (b)-[:{prop}]->(a)
            MERGE (b)-[new:{prop}]->(a)
            SET new.inferred = true,
                new.inferred_at = datetime(),
                new.inference_rule = 'symmetry'
            RETURN count(new) as count
            """

            try:
                with self.graph_store._driver.session(database=self.graph_store.database) as session:
                    res = session.run(query)
                    count = res.single()["count"]
                    total_created += count
                    if count > 0:
                        logger.info(f"Materialized {count} symmetric edges for {prop}")
            except Exception as e:
                logger.error(f"Failed to materialize symmetry for {prop}: {e}")

        return total_created

    def materialize_inversions(self, pairs: list[tuple[str, str]]) -> int:
        """Create inverse edges for properties defined as inverses.
        
        Args:
            pairs: List of (prop1, prop2) tuples where prop1 is inverse of prop2
            
        Returns:
            Number of edges created
        """
        if not pairs:
            return 0

        total_created = 0
        # Deduplicate and ensure we handle both directions (A inv B means B inv A)
        unique_pairs = []
        seen = set()
        for p1, p2 in pairs:
            if (p1, p2) not in seen:
                unique_pairs.append((p1, p2))
                seen.add((p1, p2))
                seen.add((p2, p1))

        for p1, p2 in unique_pairs:
            logger.debug(f"Applying inversion rule for {p1} <-> {p2}")

            # Rule 1: a ->[p1]-> b  implies  b ->[p2]-> a
            # Rule 2: a ->[p2]-> b  implies  b ->[p1]-> a

            for src_prop, inv_prop in [(p1, p2), (p2, p1)]:
                query = f"""
                MATCH (a)-[r:{src_prop}]->(b)
                WHERE NOT (b)-[:{inv_prop}]->(a)
                MERGE (b)-[new:{inv_prop}]->(a)
                SET new.inferred = true,
                    new.inferred_at = datetime(),
                    new.inference_rule = 'inversion',
                    new.source_property = '{src_prop}'
                RETURN count(new) as count
                """

                try:
                    with self.graph_store._driver.session(database=self.graph_store.database) as session:
                        res = session.run(query)
                        count = res.single()["count"]
                        total_created += count
                        if count > 0:
                            logger.info(f"Materialized {count} inverse edges ({src_prop} -> {inv_prop})")
                except Exception as e:
                    logger.error(f"Failed to materialize inversion {src_prop}->{inv_prop}: {e}")

        return total_created

    def materialize_class_hierarchy(self, hierarchy: list[tuple[str, str]]) -> int:
        """Materialize rdfs:subClassOf by adding parent labels to child nodes.
        
        Args:
            hierarchy: List of (child_label, parent_label) tuples
            
        Returns:
            Number of nodes updated
        """
        if not hierarchy:
            return 0

        total_updated = 0
        for child, parent in hierarchy:
            # Cypher to add parent label to nodes that have the child label
            # We skip nodes that already have the parent label
            query = f"""
            MATCH (n:{child})
            WHERE NOT n:{parent}
            SET n:{parent}
            RETURN count(n) as count
            """

            try:
                with self.graph_store._driver.session(database=self.graph_store.database) as session:
                    res = session.run(query)
                    count = res.single()["count"]
                    total_updated += count
                    if count > 0:
                        logger.info(f"Materialized hierarchy: {child} is a {parent} ({count} updates)")
            except Exception as e:
                # This can happen if labels contain special characters not handled by formatting
                logger.error(f"Failed to materialize hierarchy {child}->{parent}: {e}")

        return total_updated

    def materialize_transitivity(self, properties: list[str]) -> int:
        """Materialize transitive closure for specific properties.
        
        Args:
            properties: List of property labels defined as transitive
            
        Returns:
            Number of edges created
        """
        if not properties:
            return 0

        total_created = 0
        for prop in properties:
            # Basic transitive rule: (a)-[p]->(b) AND (b)-[p]->(c) => (a)-[p]->(c)
            # We run this once per property. In a fully logical system,
            # we would repeat until no new edges are added.
            query = f"""
            MATCH (a)-[:{prop}]->(b)-[:{prop}]->(c)
            WHERE NOT (a)-[:{prop}]->(c) AND a <> c
            MERGE (a)-[new:{prop}]->(c)
            SET new.inferred = true,
                new.inferred_at = datetime(),
                new.inference_rule = 'transitivity'
            RETURN count(new) as count
            """

            try:
                with self.graph_store._driver.session(database=self.graph_store.database) as session:
                    res = session.run(query)
                    count = res.single()["count"]
                    total_created += count
                    if count > 0:
                        logger.info(f"Materialized {count} transitive edges for {prop}")
            except Exception as e:
                logger.error(f"Failed to materialize transitivity for {prop}: {e}")

        return total_created
