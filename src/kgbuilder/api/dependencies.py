"""Dependency injection and service singletons for the API layer.

Provides lazily-initialized connections to Neo4j, Qdrant, Fuseki,
and Ollama so route handlers can declare ``Depends(get_neo4j_store)``
instead of managing connections themselves.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

import structlog

from kgbuilder.core.protocols import LLMProvider

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
_LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama").strip().lower()
_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b")
_VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen3-8B")
_LLM_MODEL = os.getenv("LLM_MODEL") or (
    _OLLAMA_MODEL if _LLM_BACKEND == "ollama" else _VLLM_MODEL
)
_VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
_VLLM_EMBEDDING_BASE_URL = os.getenv("VLLM_EMBEDDING_BASE_URL", _VLLM_BASE_URL)
_VLLM_EMBEDDING_MODEL = os.getenv(
    "VLLM_EMBEDDING_MODEL",
    "Qwen/Qwen3-Embedding-0.6B",
)
_LLM_TEMPERATURE = float(
    os.getenv("LLM_TEMPERATURE") or ("0.7" if _LLM_BACKEND == "ollama" else "0.2")
)
_LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.9"))
_LLM_SEED = int(os.environ["LLM_SEED"]) if os.getenv("LLM_SEED") else None
_LLM_CHAT_TEMPLATE_KWARGS = json.loads(os.getenv("LLM_CHAT_TEMPLATE_KWARGS") or "{}")
_LLM_CACHE_ENABLED = os.getenv("LLM_CACHE_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}

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
def get_llm_provider() -> LLMProvider:
    """Get or create the configured Ollama or vLLM provider singleton."""
    from kgbuilder.embedding import OllamaProvider, VLLMProvider

    if _LLM_BACKEND == "ollama":
        return OllamaProvider(
            model=_LLM_MODEL,
            base_url=_OLLAMA_URL,
            temperature=_LLM_TEMPERATURE,
            top_p=_LLM_TOP_P,
            seed=_LLM_SEED,
            cache_enabled=_LLM_CACHE_ENABLED,
        )
    if _LLM_BACKEND == "vllm":
        return VLLMProvider(
            model=_LLM_MODEL,
            base_url=_VLLM_BASE_URL,
            embeddings_model=_VLLM_EMBEDDING_MODEL,
            embeddings_base_url=_VLLM_EMBEDDING_BASE_URL,
            api_key=os.getenv("VLLM_API_KEY"),
            temperature=_LLM_TEMPERATURE,
            top_p=_LLM_TOP_P,
            seed=_LLM_SEED,
            chat_template_kwargs=_LLM_CHAT_TEMPLATE_KWARGS,
        )
    raise ValueError(
        f"Unsupported LLM_BACKEND '{_LLM_BACKEND}'. Supported values: ollama, vllm."
    )


def get_env_config() -> dict[str, str]:
    """Return current configuration as a dict (for debugging)."""
    return {
        "neo4j_uri": _NEO4J_URI,
        "qdrant_url": _QDRANT_URL,
        "fuseki_url": _FUSEKI_URL,
        "llm_backend": _LLM_BACKEND,
        "llm_model": _LLM_MODEL,
        "llm_temperature": str(_LLM_TEMPERATURE),
        "llm_top_p": str(_LLM_TOP_P),
        "llm_seed": str(_LLM_SEED),
        "llm_chat_template_kwargs": json.dumps(_LLM_CHAT_TEMPLATE_KWARGS),
        "llm_cache_enabled": str(_LLM_CACHE_ENABLED),
        "ollama_url": _OLLAMA_URL,
        "ollama_model": _OLLAMA_MODEL,
        "vllm_base_url": _VLLM_BASE_URL,
        "vllm_embedding_base_url": _VLLM_EMBEDDING_BASE_URL,
        "vllm_embedding_model": _VLLM_EMBEDDING_MODEL,
        "graphqa_api_url": _GRAPHQA_API_URL,
        "ontology_api_url": _ONTOLOGY_API_URL,
    }
