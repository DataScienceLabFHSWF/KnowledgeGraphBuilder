"""Status, health, and statistics endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from kgbuilder.api.schemas import KGStatistics, OntologyInfo, ServiceHealth

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=ServiceHealth)
async def health_check() -> ServiceHealth:
    """Service health check — probes all backends."""
    neo4j_status = "unknown"
    qdrant_status = "unknown"
    fuseki_status = "unknown"
    ollama_status = "unknown"

    # Neo4j
    try:
        from kgbuilder.api.dependencies import get_neo4j_store

        store = get_neo4j_store()
        store.query("RETURN 1")
        neo4j_status = "ok"
    except Exception as e:
        neo4j_status = f"error: {e}"

    # Qdrant
    try:
        import httpx

        from kgbuilder.api.dependencies import _QDRANT_URL

        resp = httpx.get(f"{_QDRANT_URL}/healthz", timeout=3)
        qdrant_status = "ok" if resp.status_code == 200 else f"http {resp.status_code}"
    except Exception as e:
        qdrant_status = f"error: {e}"

    # Fuseki
    try:
        import httpx

        from kgbuilder.api.dependencies import _FUSEKI_URL

        resp = httpx.get(f"{_FUSEKI_URL}/$/ping", timeout=3)
        fuseki_status = "ok" if resp.status_code == 200 else f"http {resp.status_code}"
    except Exception as e:
        fuseki_status = f"error: {e}"

    # Ollama
    try:
        import httpx

        from kgbuilder.api.dependencies import _OLLAMA_URL

        resp = httpx.get(f"{_OLLAMA_URL}/api/tags", timeout=3)
        ollama_status = "ok" if resp.status_code == 200 else f"http {resp.status_code}"
    except Exception as e:
        ollama_status = f"error: {e}"

    overall = "ok" if neo4j_status == "ok" else "degraded"

    return ServiceHealth(
        status=overall,
        neo4j=neo4j_status,
        qdrant=qdrant_status,
        fuseki=fuseki_status,
        ollama=ollama_status,
    )


@router.get("/stats", response_model=KGStatistics)
async def get_kg_statistics() -> KGStatistics:
    """Get current knowledge graph statistics from Neo4j."""
    try:
        from kgbuilder.api.dependencies import get_neo4j_store

        store = get_neo4j_store()
        stats = store.get_statistics()

        return KGStatistics(
            node_count=stats.node_count if hasattr(stats, "node_count") else 0,
            edge_count=stats.edge_count if hasattr(stats, "edge_count") else 0,
            nodes_by_type=stats.nodes_by_type if hasattr(stats, "nodes_by_type") else {},
            edges_by_type=stats.edges_by_type if hasattr(stats, "edges_by_type") else {},
            avg_confidence=stats.avg_confidence if hasattr(stats, "avg_confidence") else 0.0,
        )

    except Exception:
        return KGStatistics()


@router.get("/ontology", response_model=OntologyInfo)
async def get_ontology_info() -> OntologyInfo:
    """Get ontology classes and relations from Fuseki."""
    try:
        from kgbuilder.api.dependencies import get_ontology_service

        svc = get_ontology_service()
        classes = svc.get_all_classes()
        relations = svc.get_all_relations()
        hierarchy = [
            {"child": c, "parent": p}
            for c, p in svc.get_class_hierarchy()
        ]

        return OntologyInfo(
            classes=classes,
            relations=relations,
            class_count=len(classes),
            relation_count=len(relations),
            hierarchy=hierarchy,
        )

    except Exception:
        return OntologyInfo(
            classes=[],
            relations=[],
            class_count=0,
            relation_count=0,
            hierarchy=[],
        )
