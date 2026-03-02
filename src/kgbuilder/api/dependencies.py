"""Dependency injection and service singletons for the API layer.

Provides lazily-initialized connections to Neo4j, Qdrant, Fuseki,
and Ollama so route handlers can declare ``Depends(get_neo4j_store)``
instead of managing connections themselves.
"""

from __future__ import annotations

import os
from functools import lru_cache

import structlog

logger = structlog.get_logger(__name__)

# ------------------------------------------------------------------
# Environment helpers
# ------------------------------------------------------------------

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "changeme")
_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "kgbuilder")
_FUSEKI_URL = os.getenv("FUSEKI_URL", "http://localhost:3030")
_FUSEKI_DATASET = os.getenv("FUSEKI_DATASET", "kgbuilder")
_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")

# Cross-service URLs
_GRAPHQA_API_URL = os.getenv("GRAPHQA_API_URL", "http://graphqa-api:8002")
_ONTOLOGY_API_URL = os.getenv("ONTOLOGY_API_URL", "http://ontology-api:8003")


# ------------------------------------------------------------------
# Lazy singletons
# ------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_neo4j_store():
    """Get or create Neo4j graph store singleton."""
    from kgbuilder.storage.neo4j_store import Neo4jGraphStore

    return Neo4jGraphStore(
        uri=_NEO4J_URI,
        auth=(_NEO4J_USER, _NEO4J_PASSWORD),
    )


@lru_cache(maxsize=1)
def get_qdrant_store():
    """Get or create Qdrant vector store singleton."""
    from kgbuilder.storage.vector import QdrantStore

    return QdrantStore(url=_QDRANT_URL, collection_name=_QDRANT_COLLECTION)


@lru_cache(maxsize=1)
def get_ontology_service():
    """Get or create Fuseki ontology service singleton."""
    from kgbuilder.storage.ontology import FusekiOntologyService

    return FusekiOntologyService(
        fuseki_url=_FUSEKI_URL,
        dataset_name=_FUSEKI_DATASET,
    )


@lru_cache(maxsize=1)
def get_llm_provider():
    """Get or create Ollama LLM provider singleton."""
    from kgbuilder.embedding import OllamaProvider

    return OllamaProvider(model=_OLLAMA_MODEL, base_url=_OLLAMA_URL)


def get_env_config() -> dict[str, str]:
    """Return current configuration as a dict (for debugging)."""
    return {
        "neo4j_uri": _NEO4J_URI,
        "qdrant_url": _QDRANT_URL,
        "fuseki_url": _FUSEKI_URL,
        "ollama_url": _OLLAMA_URL,
        "ollama_model": _OLLAMA_MODEL,
        "graphqa_api_url": _GRAPHQA_API_URL,
        "ontology_api_url": _ONTOLOGY_API_URL,
    }
