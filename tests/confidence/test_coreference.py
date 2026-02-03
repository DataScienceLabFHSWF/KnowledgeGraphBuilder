"""Tests for CoreferenceResolver."""

from __future__ import annotations

import pytest

from kgbuilder.core.models import ExtractedEntity, Evidence
from kgbuilder.confidence.coreference import CoreferenceResolver
from kgbuilder.confidence import EntityCluster


@pytest.fixture
def resolver() -> CoreferenceResolver:
    """Create a CoreferenceResolver instance."""
    return CoreferenceResolver()


def test_find_clusters_empty_list(resolver: CoreferenceResolver) -> None:
    """Test clustering on empty list."""
    clusters = resolver.find_clusters([])
    assert len(clusters) == 0


def test_find_clusters_single_entity(resolver: CoreferenceResolver) -> None:
    """Test clustering on single entity."""
    entities = [
        ExtractedEntity(
            id="e1",
            label="Entity",
            entity_type="Organization",
            description="Entity",
            confidence=0.8,
        )
    ]
    clusters = resolver.find_clusters(entities)
    assert len(clusters) == 0  # Single entity, no clusters


def test_find_exact_match_cluster(resolver: CoreferenceResolver) -> None:
    """Test clustering on exact match."""
    entities = [
        ExtractedEntity(
            id="e1",
            label="E.ON",
            entity_type="Organization",
            description="E.ON",
            confidence=0.8,
        ),
        ExtractedEntity(
            id="e2",
            label="E.ON",
            entity_type="Organization",
            description="E.ON",
            confidence=0.7,
        ),
    ]
    # Exact match (ratio=1.0) with threshold 0.9 should find cluster
    clusters = resolver.find_clusters(entities, similarity_threshold=0.9)
    assert len(clusters) == 1
    assert set(clusters[0].entities) == {"e1", "e2"}


def test_find_fuzzy_match_cluster(resolver: CoreferenceResolver) -> None:
    """Test clustering on fuzzy match."""
    entities = [
        ExtractedEntity(
            id="e1",
            label="E.ON",
            entity_type="Organization",
            description="E.ON",
            confidence=0.85,
        ),
        ExtractedEntity(
            id="e2",
            label="EON",
            entity_type="Organization",
            description="EON",
            confidence=0.65,
        ),
    ]
    # Fuzzy match with threshold 0.8 should find similarity ~0.8 (E.ON vs EON)
    clusters = resolver.find_clusters(entities, similarity_threshold=0.8)
    # E.ON vs EON is 4/5 = 0.8 exactly, so should match at 0.8
    assert len(clusters) == 1


def test_no_cross_type_clustering(resolver: CoreferenceResolver) -> None:
    """Test that different types are not clustered together."""
    entities = [
        ExtractedEntity(
            id="e1",
            label="Test",
            entity_type="Organization",
            description="Test",
            confidence=0.8,
        ),
        ExtractedEntity(
            id="e2",
            label="Test",
            entity_type="Parameter",
            description="Test",
            confidence=0.8,
        ),
    ]
    clusters = resolver.find_clusters(entities, similarity_threshold=0.5)
    # Same label but different type → entities processed in separate type groups
    # Each type group has only 1 entity, so no clusters formed
    assert len(clusters) == 0


def test_merge_cluster_combines_evidence(resolver: CoreferenceResolver) -> None:
    """Test that merging combines evidence from all entities."""
    entities = [
        ExtractedEntity(
            id="e1",
            label="E.ON",
            entity_type="Organization",
            description="E.ON",
            confidence=0.85,
            evidence=[Evidence(source_type="local_doc", source_id="doc1", text_span="E.ON operates...")],
        ),
        ExtractedEntity(
            id="e2",
            label="EON",
            entity_type="Organization",
            description="EON",
            confidence=0.65,
            evidence=[Evidence(source_type="local_doc", source_id="doc2", text_span="EON announced...")],
        ),
    ]
    entities_dict = {e.id: e for e in entities}

    cluster = EntityCluster(
        representative_id="e1",
        entities=["e1", "e2"],
        similarity_scores={},
    )

    merged = resolver.merge_cluster(cluster, entities_dict)

    assert len(merged.evidence) == 2
    assert merged.entity_type == "Organization"


def test_merge_cluster_keeps_longest_label(
    resolver: CoreferenceResolver,
) -> None:
    """Test that merge keeps longest label."""
    entities = [
        ExtractedEntity(
            id="e1",
            label="E.ON",
            entity_type="Organization",
            description="E.ON",
            confidence=0.85,
        ),
        ExtractedEntity(
            id="e2",
            label="E.ON GmbH",
            entity_type="Organization",
            description="E.ON GmbH",
            confidence=0.75,
        ),
    ]
    entities_dict = {e.id: e for e in entities}

    cluster = EntityCluster(
        representative_id="e1",
        entities=["e1", "e2"],
        similarity_scores={},
    )

    merged = resolver.merge_cluster(cluster, entities_dict)
    assert merged.label == "E.ON GmbH"


def test_merge_cluster_averages_confidence(
    resolver: CoreferenceResolver,
) -> None:
    """Test that merge averages confidence."""
    entities = [
        ExtractedEntity(
            id="e1",
            label="Org",
            entity_type="Organization",
            description="Org",
            confidence=0.80,
        ),
        ExtractedEntity(
            id="e2",
            label="Org",
            entity_type="Organization",
            description="Org",
            confidence=0.60,
        ),
    ]
    entities_dict = {e.id: e for e in entities}

    cluster = EntityCluster(
        representative_id="e1",
        entities=["e1", "e2"],
        similarity_scores={},
    )

    merged = resolver.merge_cluster(cluster, entities_dict)
    # Average is 0.7, plus 0.05 boost = 0.75
    assert 0.74 < merged.confidence < 0.76
