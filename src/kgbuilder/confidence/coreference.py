"""Coreference resolution for entity deduplication."""

from __future__ import annotations

from difflib import SequenceMatcher

from kgbuilder.core.models import ExtractedEntity

from . import EntityCluster


class CoreferenceResolver:
    """Resolve coreferent entities (duplicates) and merge them."""

    def find_clusters(
        self,
        entities: list[ExtractedEntity],
        similarity_threshold: float = 0.85,
    ) -> list[EntityCluster]:
        """Find clusters of coreferent entities.

        Uses fuzzy string matching to identify entities that likely refer to
        the same real-world object.

        Args:
            entities: List of extracted entities.
            similarity_threshold: Similarity threshold for clustering (0.0-1.0).

        Returns:
            List of entity clusters where size > 1.
        """
        if len(entities) < 2:
            return []

        clusters = []

        # Group entities by type first (no cross-type clustering)
        entities_by_type: dict[str, list[tuple[int, ExtractedEntity]]] = {}
        for idx, entity in enumerate(entities):
            if entity.entity_type not in entities_by_type:
                entities_by_type[entity.entity_type] = []
            entities_by_type[entity.entity_type].append((idx, entity))

        # Cluster within each type using simple greedy approach
        for entity_type, typed_entities in entities_by_type.items():
            if len(typed_entities) < 2:
                continue

            type_entities = [e for _, e in typed_entities]
            n = len(type_entities)

            # Track which entities have been clustered
            clustered = set()

            # For each unclustered entity, find all similar ones
            for i in range(n):
                if i in clustered:
                    continue

                # Find all entities similar to this one
                cluster_members = [i]
                for j in range(i + 1, n):
                    if j in clustered:
                        continue

                    ratio = SequenceMatcher(
                        None, type_entities[i].label, type_entities[j].label
                    ).ratio()

                    if ratio >= similarity_threshold:
                        cluster_members.append(j)
                        clustered.add(j)

                # Only create cluster if > 1 member
                if len(cluster_members) > 1:
                    clustered.add(i)
                    cluster_entities = [type_entities[idx].id for idx in cluster_members]
                    clusters.append(
                        EntityCluster(
                            representative_id=cluster_entities[0],
                            entities=cluster_entities,
                            similarity_scores={},
                            reason="fuzzy_match",
                        )
                    )

        return clusters

    def merge_cluster(
        self,
        cluster: EntityCluster,
        entities_dict: dict[str, ExtractedEntity],
    ) -> ExtractedEntity:
        """Merge coreferent entities in a cluster.

        Combines evidence from all entities in the cluster, choosing the
        highest-confidence entity as the representative and merging metadata.

        Args:
            cluster: Cluster of coreferent entities.
            entities_dict: Dictionary mapping entity IDs to entities.

        Returns:
            Merged entity with combined evidence.
        """
        entities = [entities_dict[eid] for eid in cluster.entities]

        # Choose representative (highest confidence)
        representative = max(entities, key=lambda e: e.confidence)

        # Merge evidence
        all_evidence = []
        for e in entities:
            all_evidence.extend(e.evidence)

        # Merge labels (keep longest)
        best_label = max([e.label for e in entities], key=len)

        # Average confidence
        avg_confidence = sum(e.confidence for e in entities) / len(entities)

        # Return merged entity
        return ExtractedEntity(
            id=representative.id,
            label=best_label,
            entity_type=representative.entity_type,
            description=representative.description,
            confidence=min(0.99, avg_confidence + 0.05),  # +5% for multi-source
            evidence=all_evidence,
        )
