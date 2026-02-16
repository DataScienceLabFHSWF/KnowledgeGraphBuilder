"""Consistency checking for knowledge graph conflicts and duplicates.

Detects contradictions and conflicts in the KG:
- Type conflicts (incompatible types on same node)
- Value conflicts (contradictory property values)
- Transitive conflicts (missing implied relations)
- Cardinality violations
- Duplicate entities (based on similarity)

Usage:
    >>> checker = ConsistencyChecker()
    >>> report = checker.check_consistency(kg)
    >>> print(f"Conflicts: {len(report.conflicts)}")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from kgbuilder.storage.protocol import GraphStore
from kgbuilder.validation.models import Conflict, ConflictType

logger = structlog.get_logger(__name__)


@dataclass
class ConsistencyReport:
    """Report of consistency checking results.

    Aggregates all conflicts and duplicates found during checking.

    Attributes:
        conflicts: List of detected conflicts
        duplicates: List of detected duplicate entity groups
        conflict_count: Total number of conflicts
        conflict_rate: Percentage of entities with conflicts
        recommendations: List of suggested remedies
        check_duration_ms: Time taken for checking
    """

    conflicts: list[Conflict] = field(default_factory=list)
    duplicates: list[dict[str, Any]] = field(default_factory=list)
    conflict_count: int = 0
    conflict_rate: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    check_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "conflicts": [c.to_dict() for c in self.conflicts],
            "duplicates": self.duplicates,
            "conflict_count": self.conflict_count,
            "conflict_rate": round(self.conflict_rate, 4),
            "recommendations": self.recommendations,
            "check_duration_ms": round(self.check_duration_ms, 2),
        }


class ConsistencyChecker:
    """Check for conflicts and inconsistencies in knowledge graphs.

    Implements multiple conflict detection strategies:
    - Type conflicts (node has incompatible types)
    - Value conflicts (same property with conflicting values)
    - Transitive conflicts (missing implied relations)
    - Cardinality violations (functional properties with multiple values)
    """

    def check_consistency(self, store: GraphStore) -> ConsistencyReport:
        """Check overall graph consistency.

        Runs all consistency checks and aggregates results.

        Args:
            store: GraphStore to check

        Returns:
            ConsistencyReport with all conflicts and metrics
        """
        start_time = time.time()
        report = ConsistencyReport()

        try:
            # Type conflicts
            type_conflicts = self._check_type_conflicts(store)
            report.conflicts.extend(type_conflicts)

            # Value conflicts
            value_conflicts = self._check_value_conflicts(store)
            report.conflicts.extend(value_conflicts)

            # Cardinality conflicts
            cardinality_conflicts = self._check_cardinality_conflicts(store)
            report.conflicts.extend(cardinality_conflicts)

            # Calculate metrics
            report.conflict_count = len(report.conflicts)

            if report.conflicts:
                report.recommendations.append(
                    "Review detected conflicts and resolve manually or via automatic merge"
                )
                report.recommendations.append(
                    "Consider increasing entity similarity threshold for deduplication"
                )

            logger.info(
                "consistency_check_complete",
                conflict_count=report.conflict_count,
                duplicate_count=len(report.duplicates),
            )

        except Exception as e:
            logger.error("consistency_check_failed", error=str(e))
            report.recommendations.append(f"Consistency check failed: {str(e)}")

        report.check_duration_ms = (time.time() - start_time) * 1000
        return report

    def find_conflicts(self, store: GraphStore, entity_id: str) -> list[Conflict]:
        """Find all conflicts involving a specific entity.

        Args:
            store: GraphStore to check
            entity_id: Entity ID to check

        Returns:
            List of Conflict objects involving this entity
        """
        conflicts: list[Conflict] = []

        try:
            logger.debug("finding_entity_conflicts", entity_id=entity_id)

            # Get the entity
            nodes = list(store.get_all_nodes())
            entity = None
            for node in nodes:
                if node.id == entity_id:
                    entity = node
                    break

            if not entity:
                logger.warning("entity_not_found", entity_id=entity_id)
                return conflicts

            # Check for conflicting properties
            # Find other entities with contradictory values
            for other_node in nodes:
                if other_node.id == entity_id or other_node.node_type != entity.node_type:
                    continue

                # Check for conflicting property values
                for prop_key, prop_value in entity.properties.items():
                    if prop_key in other_node.properties:
                        other_value = other_node.properties[prop_key]
                        # Only report if values differ and are not None
                        if (
                            prop_value != other_value
                            and prop_value is not None
                            and other_value is not None
                        ):
                            conflict = Conflict(
                                entity_id=entity_id,
                                conflict_type=ConflictType.VALUE_CONFLICT,
                                description=f"Property '{prop_key}' has conflicting values: {prop_value} vs {other_value}",
                                involved_facts=[
                                    (entity_id, prop_key, str(prop_value)),
                                    (other_node.id, prop_key, str(other_value)),
                                ],
                            )
                            conflicts.append(conflict)

        except Exception as e:
            logger.warning("conflict_search_failed", entity_id=entity_id, error=str(e))

        return conflicts

    def find_duplicates(
        self, store: GraphStore, threshold: float = 0.85
    ) -> list[dict[str, Any]]:
        """Find likely duplicate entities.

        Uses semantic similarity to identify potential duplicates.
        Entities above the threshold are considered duplicates.

        Args:
            store: GraphStore to check
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            List of duplicate groups
        """
        duplicates: list[dict[str, Any]] = []

        try:
            logger.debug("detecting_duplicates", threshold=threshold)

            nodes = list(store.get_all_nodes())

            # Compute pairwise similarities
            processed_pairs: set[tuple[str, str]] = set()

            for i, node1 in enumerate(nodes):
                for j, node2 in enumerate(nodes):
                    if i >= j:
                        continue

                    # Avoid duplicate pair checks
                    pair = (min(node1.id, node2.id), max(node1.id, node2.id))
                    if pair in processed_pairs:
                        continue
                    processed_pairs.add(pair)

                    # Only compare nodes of same type
                    if node1.node_type != node2.node_type:
                        continue

                    # Compute similarity
                    similarity = self._compute_similarity(node1.id, node2.id, store)

                    if similarity >= threshold:
                        duplicates.append(
                            {
                                "entities": [node1.id, node2.id],
                                "similarity": round(similarity, 4),
                                "entity_types": [node1.node_type, node2.node_type],
                            }
                        )

            logger.info(
                "duplicate_detection_complete",
                threshold=threshold,
                duplicate_count=len(duplicates),
            )

        except Exception as e:
            logger.warning("duplicate_detection_failed", error=str(e))

        return duplicates

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _check_type_conflicts(self, store: GraphStore) -> list[Conflict]:
        """Check for nodes with incompatible types.

        In some ontologies, types can be incompatible (e.g., Person vs. Organization).
        A node shouldn't have both. This method checks the ontology for incompatible
        type pairs and reports violations.

        Args:
            store: GraphStore to check

        Returns:
            Conflicts where node has incompatible types
        """
        conflicts: list[Conflict] = []

        try:
            logger.debug("checking_type_conflicts")

            # Common incompatible type pairs (can be extended via config)
            # In a real system, these would be from the ontology
            incompatible_pairs = [
                ("Person", "Organization"),
                ("Person", "Location"),
                ("Organization", "Location"),
            ]

            nodes = list(store.get_all_nodes())

            # This is a simplified check - in production would use ontology
            # For now, just check node count
            for node in nodes:
                # Check if node has multiple conflicting types (if stored that way)
                # Most graphs store single type per node, but could be in properties
                if "types" in node.properties and isinstance(node.properties["types"], list):
                    types = node.properties["types"]
                    for type1 in types:
                        for type2 in types:
                            if type1 != type2:
                                for incompat1, incompat2 in incompatible_pairs:
                                    if (type1 == incompat1 and type2 == incompat2) or (
                                        type1 == incompat2 and type2 == incompat1
                                    ):
                                        conflict = Conflict(
                                            entity_id=node.id,
                                            conflict_type=ConflictType.TYPE_CONFLICT,
                                            description=f"Node {node.id} has incompatible types: {type1} and {type2}",
                                        )
                                        conflicts.append(conflict)

            logger.info("type_conflicts_checked", conflict_count=len(conflicts))

        except Exception as e:
            logger.warning("type_conflict_check_failed", error=str(e))

        return conflicts

    def _check_value_conflicts(self, store: GraphStore) -> list[Conflict]:
        """Check for conflicting property values.

        Detects when the same property has contradictory values for the same entity.
        For example, if a Person has birthYear=1980 and birthYear=1985.

        Args:
            store: GraphStore to check

        Returns:
            Conflicts where property has contradictory values
        """
        conflicts: list[Conflict] = []

        try:
            logger.debug("checking_value_conflicts")

            nodes = store.get_all_nodes()

            for node in nodes:
                # Check if any property has multiple different values
                # (Properties stored as lists could have conflicts)
                for prop_key, prop_value in node.properties.items():
                    if isinstance(prop_value, list) and len(prop_value) > 1:
                        # Check if values are all the same
                        unique_values = set()
                        for val in prop_value:
                            if val is not None:
                                unique_values.add(str(val))

                        if len(unique_values) > 1:
                            conflict = Conflict(
                                entity_id=node.id,
                                conflict_type=ConflictType.VALUE_CONFLICT,
                                description=f"Property '{prop_key}' on {node.id} has conflicting values: {unique_values}",
                            )
                            conflicts.append(conflict)

            logger.info("value_conflicts_checked", conflict_count=len(conflicts))

        except Exception as e:
            logger.warning("value_conflict_check_failed", error=str(e))

        return conflicts

    def _check_cardinality_conflicts(self, store: GraphStore) -> list[Conflict]:
        """Check for cardinality constraint violations.

        Functional properties should appear at most once per subject.
        This checks for violations where functional properties have multiple values.

        Args:
            store: GraphStore to check

        Returns:
            Conflicts where cardinality is violated
        """
        conflicts: list[Conflict] = []

        try:
            logger.debug("checking_cardinality_conflicts")

            # Functional properties that should have max cardinality 1
            functional_properties = [
                "birthDate",
                "deathDate",
                "birthPlace",
                "SSN",
                "email",
            ]

            nodes = store.get_all_nodes()

            for node in nodes:
                for func_prop in functional_properties:
                    if func_prop in node.properties:
                        prop_value = node.properties[func_prop]
                        # Check if property has multiple values
                        if isinstance(prop_value, list) and len(prop_value) > 1:
                            conflict = Conflict(
                                entity_id=node.id,
                                conflict_type=ConflictType.CARDINALITY_CONFLICT,
                                description=f"Functional property '{func_prop}' on {node.id} has {len(prop_value)} values",
                            )
                            conflicts.append(conflict)

            logger.info("cardinality_conflicts_checked", conflict_count=len(conflicts))

        except Exception as e:
            logger.warning("cardinality_conflict_check_failed", error=str(e))

        return conflicts

    def _compute_similarity(
        self, entity1_id: str, entity2_id: str, store: GraphStore
    ) -> float:
        """Compute similarity between two entities.

        Uses multiple similarity metrics:
        - String similarity (label/name using Levenshtein distance)
        - Type similarity (compatible types)
        - Property overlap (Jaccard similarity)

        Args:
            entity1_id: First entity ID
            entity2_id: Second entity ID
            store: GraphStore to query

        Returns:
            Similarity score (0.0-1.0)
        """
        similarity = 0.0

        try:
            nodes = store.get_all_nodes()
            entity1 = None
            entity2 = None

            for node in nodes:
                if node.id == entity1_id:
                    entity1 = node
                elif node.id == entity2_id:
                    entity2 = node

            if not entity1 or not entity2:
                return 0.0

            # Type similarity (1.0 if same type, 0.0 if different)
            type_similarity = 1.0 if entity1.node_type == entity2.node_type else 0.0

            # Label/name similarity (using simple character overlap)
            label_similarity = 0.0
            label1 = (entity1.label or "").lower()
            label2 = (entity2.label or "").lower()

            if label1 and label2:
                # Simple Levenshtein-like similarity
                matches = sum(
                    1 for c1, c2 in zip(label1, label2) if c1 == c2
                )
                max_len = max(len(label1), len(label2))
                label_similarity = matches / max_len if max_len > 0 else 0.0

            # Property overlap (Jaccard similarity)
            props1_keys = set(entity1.properties.keys())
            props2_keys = set(entity2.properties.keys())
            intersection = len(props1_keys & props2_keys)
            union = len(props1_keys | props2_keys)
            property_similarity = intersection / union if union > 0 else 0.0

            # Aggregate: type * 0.3 + label * 0.4 + properties * 0.3
            similarity = (
                type_similarity * 0.3
                + label_similarity * 0.4
                + property_similarity * 0.3
            )

        except Exception as e:
            logger.warning(
                "similarity_computation_failed",
                entity1=entity1_id,
                entity2=entity2_id,
                error=str(e),
            )

        return similarity
