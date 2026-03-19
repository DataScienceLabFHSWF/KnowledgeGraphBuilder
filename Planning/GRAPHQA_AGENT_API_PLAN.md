# GraphQAAgent — FastAPI Implementation Plan

> Copy this file into the GraphQAAgent repository and follow it step-by-step.
> It mirrors the plans created for
> [KGBuilder](https://github.com/DataScienceLabFHSWF/KnowledgeGraphBuilder/tree/fast-api)
> and [OntologyExtender](Planning/ONTOLOGY_EXTENDER_API_PLAN.md).

---

## Table of Contents

1. [Overview](#1-overview)
2. [What Already Exists](#2-what-already-exists)
3. [What's Missing](#3-whats-missing)
4. [Port & Service Configuration](#4-port--service-configuration)
5. [Directory Structure](#5-directory-structure)
6. [pyproject.toml Changes](#6-pyprojecttoml-changes)
7. [New Pydantic Schemas](#7-new-pydantic-schemas)
   - 7.1 [Chat Schemas (`api/chat_schemas.py`)](#71-chat-schemas)
   - 7.2 [Explorer Schemas (`api/explorer_schemas.py`)](#72-explorer-schemas)
   - 7.3 [HITL Schemas (`api/hitl_schemas.py`)](#73-hitl-schemas)
8. [Dependencies & Singletons (`api/dependencies.py`)](#8-dependencies--singletons)
9. [Server Updates (`api/server.py`)](#9-server-updates)
10. [New Route Modules](#10-new-route-modules)
    - 10.1 [Chat (`routes/chat.py`)](#101-chat)
    - 10.2 [Explorer (`routes/explorer.py`)](#102-explorer)
    - 10.3 [HITL Feedback (`routes/hitl.py`)](#103-hitl-feedback)
11. [Chat Session Management](#11-chat-session-management)
12. [SSE Streaming](#12-sse-streaming)
13. [Docker Setup](#13-docker-setup)
    - 13.1 [Dockerfile.api](#131-dockerfileapi)
    - 13.2 [docker-compose.yml (standalone)](#132-docker-composeyml-standalone)
14. [Cross-Service Integration](#14-cross-service-integration)
15. [Streamlit Frontend Pages](#15-streamlit-frontend-pages)
16. [Testing Strategy](#16-testing-strategy)
17. [Implementation Phases](#17-implementation-phases)
18. [Implementation Checklist](#18-implementation-checklist)

---

## 1. Overview

The GraphQAAgent API is the **user-facing** service of the KGPlatform.
It provides:

- **Question answering** over the Knowledge Graph (existing `/ask`, new
  streaming `/chat/send`)
- **KG exploration** — entity search, subgraph visualization, law structure,
  ontology browsing
- **HITL feedback** — low-confidence answers are forwarded to KGBuilder
  for gap detection, which may trigger ontology extension

### Feedback Loop

```
User question
     │
     ▼
GraphQAAgent ──(confidence < 0.5)──► KGBuilder ──(TBox gaps)──► OntologyExtender
     │                                    │                            │
     ▲                                    ▲                            │
     │                                    │                            │
  answers                          re-build trigger          updated OWL + SHACL
```

### Services That Talk to GraphQA

| Caller             | Endpoint                   | When                               |
| ------------------ | -------------------------- | ---------------------------------- |
| **Streamlit UI**   | `POST /chat/send`          | User asks a question               |
| **Streamlit UI**   | `GET /explore/*`           | User browses KG entities           |
| **KGBuilder**      | `POST /chat`               | CQ test after ontology update      |
| **KGBuilder HITL** | Routes feedback with `target: qa_agent` | New CQs from expert review |

---

## 2. What Already Exists

The repo already has a working FastAPI server:

| File                      | Content                                  |
| ------------------------- | ---------------------------------------- |
| `src/kgrag/api/server.py` | FastAPI app with CORS, lifespan           |
| `src/kgrag/api/routes.py` | `POST /api/v1/ask` — full QA pipeline    |
| `src/kgrag/api/schemas.py`| `QuestionRequest`, `AnswerResponse`      |

**Existing schemas:**

```python
class QuestionRequest(BaseModel):
    question: str
    strategy: str = "hybrid_sota"
    language: str = "de"

class AnswerResponse(BaseModel):
    answer: str
    confidence: float
    reasoning_chain: list[str]
    provenance: list[ProvenanceResponse]
    subgraph: dict | None
    latency_ms: float
```

**Existing orchestrator:** Full SOTA pipeline —
parse → expand → retrieve → CoT → generate → verify → explain.

---

## 3. What's Missing

| Priority | Feature                    | Endpoints                                              |
| -------- | -------------------------- | ------------------------------------------------------ |
| **P0**   | Streaming chat             | `POST /chat/send`, `GET /chat/sessions/{id}/history`   |
| **P0**   | Session management         | `DELETE /chat/sessions/{id}`                            |
| **P1**   | KG Explorer                | `GET /explore/entities`, `/entities/{id}`, `/entities/{id}/subgraph` |
| **P1**   | Relation & stats browsing  | `GET /explore/relations`, `/explore/stats`              |
| **P1**   | Law structure              | `GET /explore/laws`, `/laws/{id}/structure`, `/laws/{id}/linked-entities` |
| **P1**   | Ontology browsing          | `GET /explore/ontology/classes`, `/ontology/tree`       |
| **P2**   | HITL low-confidence report | `POST /hitl/report-low-confidence`                      |
| **P2**   | Expert feedback            | `POST /feedback`                                        |
| **P2**   | Dependencies module        | Lazy singletons for Neo4j, Qdrant, Fuseki, Ollama       |

---

## 4. Port & Service Configuration

| Item                | Value                                 |
| ------------------- | ------------------------------------- |
| **API port**        | `8002` (host & container)             |
| **Ollama instance** | `ollama-graphqa` → host `11436`       |
| **Neo4j**           | shared `neo4j:7687` (bolt)            |
| **Qdrant**          | shared `qdrant:6333`                  |
| **Fuseki**          | shared `fuseki:3030`                  |
| **Service name**    | `graphqa-api`                         |

### Environment Variables

```bash
# Core
SERVICE_NAME=graphqa
UVICORN_PORT=8002

# LLM
OLLAMA_URL=http://ollama-graphqa:11434
OLLAMA_MODEL=qwen3:8b

# Graph stores
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
QDRANT_URL=http://qdrant:6333
FUSEKI_URL=http://fuseki:3030

# Cross-service
KGBUILDER_API_URL=http://kgbuilder-api:8001

# Chat
CONFIDENCE_THRESHOLD=0.5      # below this → trigger HITL
MAX_SESSION_AGE_HOURS=24
MAX_SESSIONS=1000
```

---

## 5. Directory Structure

Add new files alongside the existing `api/` package:

```
src/kgrag/
├── api/                              # EXISTS
│   ├── server.py                     # UPDATE — mount new routers, add dependencies
│   ├── routes.py                     # EXISTS — keep /ask as-is
│   ├── schemas.py                    # EXISTS — keep QuestionRequest, AnswerResponse
│   ├── chat_schemas.py              # ← NEW
│   ├── explorer_schemas.py          # ← NEW
│   ├── hitl_schemas.py             # ← NEW
│   ├── dependencies.py             # ← NEW — lazy singletons
│   └── routes/                      # ← NEW directory
│       ├── __init__.py
│       ├── chat.py                  # POST /chat/send, session management
│       ├── explorer.py             # GET /explore/* endpoints
│       └── hitl.py                 # POST /hitl/report-low-confidence, /feedback
├── chat/                            # ← NEW — session management
│   ├── __init__.py
│   ├── session.py                   # ChatSession + ChatSessionManager
│   └── streaming.py                # SSE event helpers
├── frontend/                        # ← NEW (optional) — Streamlit UI
│   ├── app.py
│   └── pages/
│       ├── 1_Chat.py
│       ├── 2_KG_Explorer.py
│       ├── 3_Ontology.py
│       └── 4_Reasoning.py
└── ...existing modules...
```

---

## 6. pyproject.toml Changes

```toml
[project.optional-dependencies]
api = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "httpx>=0.25",
    "sse-starlette>=2.0",        # for SSE streaming
]
frontend = [
    "streamlit>=1.30",
    "pyvis>=0.3",
]

[project.scripts]
graphqa-api = "uvicorn:main"   # convenience; real launch below
```

---

## 7. New Pydantic Schemas

### 7.1 Chat Schemas

`src/kgrag/api/chat_schemas.py`

```python
"""Chat-specific request/response models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: ChatRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict | None = None


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    session_id: str | None = Field(
        default=None,
        description="Existing session ID, or None to create a new session",
    )
    message: str = Field(..., min_length=1)
    strategy: str = Field(default="hybrid_sota")
    language: str = Field(default="de")
    stream: bool = Field(
        default=True,
        description="If True, response is SSE stream; if False, blocking JSON",
    )
    include_reasoning: bool = True
    include_subgraph: bool = True


class ProvenanceItem(BaseModel):
    """Source provenance for an answer."""

    source: str
    chunk_id: str = ""
    relevance: float = 0.0
    text_snippet: str = ""


class ChatResponse(BaseModel):
    """Full (non-streaming) chat response."""

    session_id: str
    message: ChatMessage
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_chain: list[str] = Field(default_factory=list)
    provenance: list[ProvenanceItem] = Field(default_factory=list)
    subgraph: dict | None = None
    latency_ms: float = 0.0


class ChatStreamEvent(BaseModel):
    """A single SSE event payload.

    Event types: session, token, reasoning_step, provenance, subgraph, done, error
    """

    event: str
    data: dict | str


class SessionInfo(BaseModel):
    """Summary of a chat session."""

    session_id: str
    created_at: datetime
    turn_count: int
    last_message: str = ""


class ConversationTurn(BaseModel):
    """A user question + assistant answer pair."""

    user_message: ChatMessage
    assistant_message: ChatMessage
    confidence: float = 0.0
    latency_ms: float = 0.0
```

### 7.2 Explorer Schemas

`src/kgrag/api/explorer_schemas.py`

```python
"""KG exploration request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityInfo(BaseModel):
    """A Knowledge Graph entity."""

    id: str
    label: str
    entity_type: str = ""
    confidence: float = 0.0
    description: str = ""
    properties: dict[str, str] = Field(default_factory=dict)


class EntityDetail(EntityInfo):
    """Entity with its direct neighbors."""

    neighbors: list[RelationEdge] = Field(default_factory=list)


class RelationEdge(BaseModel):
    """A single relation between two entities."""

    source_id: str
    source_label: str = ""
    target_id: str
    target_label: str = ""
    predicate: str
    confidence: float = 0.0


class SubgraphResponse(BaseModel):
    """vis.js-compatible subgraph for visualization."""

    nodes: list[dict] = Field(
        default_factory=list,
        description="List of {id, label, group, ...} for vis.js",
    )
    edges: list[dict] = Field(
        default_factory=list,
        description="List of {from, to, label, ...} for vis.js",
    )


class RelationType(BaseModel):
    """A relation type with count."""

    predicate: str
    label: str = ""
    count: int = 0


class KGStats(BaseModel):
    """Knowledge Graph statistics."""

    entity_count: int = 0
    relation_count: int = 0
    entity_types: dict[str, int] = Field(default_factory=dict)
    relation_types: dict[str, int] = Field(default_factory=dict)
    law_count: int = 0


class LawInfo(BaseModel):
    """A law or regulation in the KG."""

    id: str
    title: str
    abbreviation: str = ""
    section_count: int = 0


class LawStructure(BaseModel):
    """Hierarchical structure of a law."""

    id: str
    title: str
    children: list[LawStructure] = Field(default_factory=list)


class OntologyClassInfo(BaseModel):
    """An OWL class from the ontology."""

    uri: str
    label: str
    description: str = ""
    parent_uri: str | None = None
    instance_count: int = 0


class OntologyTree(BaseModel):
    """Hierarchical ontology tree node."""

    uri: str
    label: str
    children: list[OntologyTree] = Field(default_factory=list)
    instance_count: int = 0


# Fix forward reference
EntityDetail.model_rebuild()
LawStructure.model_rebuild()
OntologyTree.model_rebuild()
```

### 7.3 HITL Schemas

`src/kgrag/api/hitl_schemas.py`

```python
"""HITL feedback schemas for cross-service communication."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QAResult(BaseModel):
    """A single QA result to report."""

    question: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    session_id: str = ""
    entity_types_mentioned: list[str] = Field(default_factory=list)


class LowConfidenceReport(BaseModel):
    """Batch of low-confidence QA results to send to KGBuilder."""

    qa_results: list[QAResult]
    threshold: float = Field(
        default=0.5,
        description="Confidence threshold used for filtering",
    )


class ReportResponse(BaseModel):
    """Response from KGBuilder after receiving low-confidence report."""

    status: str  # "received" | "gaps_detected" | "error"
    gaps_detected: int = 0
    suggested_classes: list[str] = Field(default_factory=list)
    message: str = ""


class FeedbackRequest(BaseModel):
    """Expert correction on an answer."""

    session_id: str
    turn_index: int
    correction: str
    feedback_type: str = "correction"  # "correction" | "approval" | "rejection"
    reviewer_id: str = "anonymous"


class FeedbackResponse(BaseModel):
    """Acknowledgment of feedback."""

    status: str  # "accepted" | "error"
    feedback_id: str = ""
```

---

## 8. Dependencies & Singletons

`src/kgrag/api/dependencies.py`

```python
"""Dependency injection — lazy singletons for backend connections."""

from __future__ import annotations

import os
from functools import lru_cache

import httpx
import structlog

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_settings() -> dict[str, str]:
    """Gather all env-based settings."""
    return {
        "neo4j_uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "neo4j_user": os.getenv("NEO4J_USER", "neo4j"),
        "neo4j_password": os.getenv("NEO4J_PASSWORD", "password"),
        "qdrant_url": os.getenv("QDRANT_URL", "http://localhost:6333"),
        "fuseki_url": os.getenv("FUSEKI_URL", "http://localhost:3030"),
        "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        "kgbuilder_api_url": os.getenv("KGBUILDER_API_URL", "http://localhost:8001"),
        "confidence_threshold": os.getenv("CONFIDENCE_THRESHOLD", "0.5"),
        "max_session_age_hours": os.getenv("MAX_SESSION_AGE_HOURS", "24"),
        "max_sessions": os.getenv("MAX_SESSIONS", "1000"),
    }


# ── Neo4j ────────────────────────────────────────────────────────────────

_neo4j_driver = None


def get_neo4j_driver():
    """Lazy-init Neo4j driver."""
    global _neo4j_driver
    if _neo4j_driver is None:
        try:
            from neo4j import GraphDatabase
            settings = get_settings()
            _neo4j_driver = GraphDatabase.driver(
                settings["neo4j_uri"],
                auth=(settings["neo4j_user"], settings["neo4j_password"]),
            )
            logger.info("neo4j_connected", uri=settings["neo4j_uri"])
        except Exception as e:
            logger.error("neo4j_connection_failed", error=str(e))
            raise
    return _neo4j_driver


def neo4j_query(cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a Cypher query and return records as dicts."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(cypher, params or {})
        return [dict(record) for record in result]


# ── Qdrant ───────────────────────────────────────────────────────────────

_qdrant_client = None


def get_qdrant_client():
    """Lazy-init Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        try:
            from qdrant_client import QdrantClient
            settings = get_settings()
            _qdrant_client = QdrantClient(url=settings["qdrant_url"])
            logger.info("qdrant_connected", url=settings["qdrant_url"])
        except Exception as e:
            logger.error("qdrant_connection_failed", error=str(e))
            raise
    return _qdrant_client


# ── Fuseki ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_fuseki_client() -> httpx.Client:
    """HTTP client for Fuseki SPARQL."""
    settings = get_settings()
    return httpx.Client(base_url=settings["fuseki_url"], timeout=30.0)


def sparql_query(query: str, dataset: str = "kgbuilder") -> list[dict]:
    """Execute SPARQL SELECT on Fuseki."""
    client = get_fuseki_client()
    resp = client.post(
        f"/{dataset}/sparql",
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
    )
    resp.raise_for_status()
    return [
        {k: v["value"] for k, v in row.items()}
        for row in resp.json().get("results", {}).get("bindings", [])
    ]


# ── Cross-service helpers ────────────────────────────────────────────────

def forward_to_kgbuilder(qa_results: list[dict]) -> dict:
    """POST low-confidence results to KGBuilder's HITL gap detector.

    Calls: POST {KGBUILDER_API_URL}/api/v1/hitl/gaps/detect
    """
    settings = get_settings()
    url = f"{settings['kgbuilder_api_url']}/api/v1/hitl/gaps/detect"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json={"qa_results": qa_results})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("kgbuilder_forward_failed", url=url, error=str(e))
        return {"status": "error", "message": str(e)}
```

---

## 9. Server Updates

Update existing `src/kgrag/api/server.py` to mount new routers:

```python
"""GraphQAAgent FastAPI application."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Existing router
from kgrag.api.routes import router as ask_router

# New routers
from kgrag.api.routes.chat import router as chat_router
from kgrag.api.routes.explorer import router as explorer_router
from kgrag.api.routes.hitl import router as hitl_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("graphqa_api_starting", port=os.getenv("UVICORN_PORT", "8002"))
    yield
    logger.info("graphqa_api_stopping")


app = FastAPI(
    title="GraphQA Agent API",
    version="0.1.0",
    description="Question answering, KG exploration, and HITL feedback over a Knowledge Graph.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing /api/v1/ask endpoint
app.include_router(ask_router, prefix="/api/v1", tags=["qa"])

# New routers
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(explorer_router, prefix="/api/v1/explore", tags=["explorer"])
app.include_router(hitl_router, prefix="/api/v1", tags=["hitl"])


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "graphqa-agent", "docs": "/docs"}


@app.get("/api/v1/health")
async def health() -> dict:
    """Health check — probe Neo4j, Qdrant, Ollama."""
    from kgrag.api.dependencies import get_settings

    checks: dict[str, str] = {}
    settings = get_settings()

    # Neo4j
    try:
        from kgrag.api.dependencies import get_neo4j_driver
        driver = get_neo4j_driver()
        driver.verify_connectivity()
        checks["neo4j"] = "ok"
    except Exception:
        checks["neo4j"] = "error"

    # Qdrant
    try:
        from kgrag.api.dependencies import get_qdrant_client
        client = get_qdrant_client()
        client.get_collections()
        checks["qdrant"] = "ok"
    except Exception:
        checks["qdrant"] = "error"

    # Ollama
    try:
        import httpx
        resp = httpx.get(f"{settings['ollama_url']}/api/tags", timeout=5.0)
        checks["ollama"] = "ok" if resp.status_code == 200 else "error"
    except Exception:
        checks["ollama"] = "error"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "service": "graphqa-agent", **checks}
```

> **Note:** Keep the existing `routes.py` with `POST /api/v1/ask` as-is.
> The new routers are mounted alongside it.

---

## 10. New Route Modules

### 10.1 Chat

`src/kgrag/api/routes/chat.py`

This is the **main user-facing endpoint** — streaming chat with
session management.

```python
"""Chat endpoints — streaming and blocking QA with session management."""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from kgrag.api.chat_schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    ConversationTurn,
    SessionInfo,
)
from kgrag.chat.session import get_session_manager

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/send")
async def chat_send(request: ChatRequest):
    """Send a message and get a response.

    If `stream=True` (default), returns an SSE stream with events:
    - `session` — `{"session_id": "..."}`
    - `token` — `{"token": "..."}`
    - `reasoning_step` — `{"step": "...", "index": N}`
    - `provenance` — `{"sources": [...]}`
    - `subgraph` — `{"nodes": [...], "edges": [...]}`
    - `done` — `{"confidence": 0.85, "latency_ms": 1234.5}`
    - `error` — `{"message": "..."}`

    If `stream=False`, returns a full `ChatResponse` JSON.
    """
    manager = get_session_manager()

    # Get or create session
    session_id = request.session_id or str(uuid.uuid4())
    session = manager.get_or_create(session_id)

    if request.stream:
        return StreamingResponse(
            _stream_answer(session_id, session, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        return await _blocking_answer(session_id, session, request)


async def _blocking_answer(
    session_id: str, session, request: ChatRequest
) -> ChatResponse:
    """Non-streaming: run the full QA pipeline and return a single JSON response."""
    start = time.perf_counter()

    # Add user message to session
    user_msg = ChatMessage(role=ChatRole.USER, content=request.message)
    session.add_message(user_msg)

    # Run the existing QA orchestrator
    # TODO: Wire to your existing orchestrator (the one behind /api/v1/ask)
    # For now, placeholder:
    try:
        from kgrag.api.routes import _run_qa_pipeline  # adapt import

        result = _run_qa_pipeline(
            question=request.message,
            strategy=request.strategy,
            language=request.language,
        )
    except Exception as e:
        logger.error("qa_pipeline_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    latency = (time.perf_counter() - start) * 1000

    # Build response
    assistant_msg = ChatMessage(
        role=ChatRole.ASSISTANT,
        content=result.get("answer", ""),
        metadata={"confidence": result.get("confidence", 0.0)},
    )
    session.add_message(assistant_msg)

    # Auto-report low confidence
    confidence = result.get("confidence", 0.0)
    if confidence < float(_get_threshold()):
        _auto_report_low_confidence(request.message, result)

    return ChatResponse(
        session_id=session_id,
        message=assistant_msg,
        confidence=confidence,
        reasoning_chain=result.get("reasoning_chain", []),
        provenance=[],  # map from result
        subgraph=result.get("subgraph") if request.include_subgraph else None,
        latency_ms=latency,
    )


async def _stream_answer(session_id: str, session, request: ChatRequest):
    """SSE generator — yields events as the pipeline progresses."""
    import json

    start = time.perf_counter()

    # 1. Session event
    yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"

    user_msg = ChatMessage(role=ChatRole.USER, content=request.message)
    session.add_message(user_msg)

    try:
        # 2. Run pipeline (adapt to your orchestrator)
        # TODO: If your orchestrator supports callbacks/streaming, wire them here.
        # For now, run blocking and emit tokens from the final answer.
        from kgrag.api.routes import _run_qa_pipeline

        result = _run_qa_pipeline(
            question=request.message,
            strategy=request.strategy,
            language=request.language,
        )

        # 3. Reasoning steps
        if request.include_reasoning:
            for i, step in enumerate(result.get("reasoning_chain", [])):
                yield f"event: reasoning_step\ndata: {json.dumps({'step': step, 'index': i})}\n\n"

        # 4. Tokens (simulate streaming from final answer)
        answer = result.get("answer", "")
        words = answer.split()
        for word in words:
            yield f"event: token\ndata: {json.dumps({'token': word + ' '})}\n\n"

        # 5. Provenance
        if result.get("provenance"):
            yield f"event: provenance\ndata: {json.dumps({'sources': result['provenance']})}\n\n"

        # 6. Subgraph
        if request.include_subgraph and result.get("subgraph"):
            yield f"event: subgraph\ndata: {json.dumps(result['subgraph'])}\n\n"

        # 7. Done
        latency = (time.perf_counter() - start) * 1000
        confidence = result.get("confidence", 0.0)
        yield f"event: done\ndata: {json.dumps({'confidence': confidence, 'latency_ms': latency})}\n\n"

        # Save to session
        assistant_msg = ChatMessage(role=ChatRole.ASSISTANT, content=answer)
        session.add_message(assistant_msg)

        # Auto-report low confidence
        if confidence < float(_get_threshold()):
            _auto_report_low_confidence(request.message, result)

    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions() -> list[SessionInfo]:
    """List active chat sessions."""
    manager = get_session_manager()
    return [
        SessionInfo(
            session_id=sid,
            created_at=s.created_at,
            turn_count=len(s.messages) // 2,
            last_message=s.messages[-1].content if s.messages else "",
        )
        for sid, s in manager.sessions.items()
    ]


@router.get("/sessions/{session_id}/history", response_model=list[ConversationTurn])
async def get_history(session_id: str) -> list[ConversationTurn]:
    """Get conversation history for a session."""
    manager = get_session_manager()
    session = manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    turns: list[ConversationTurn] = []
    messages = session.messages
    for i in range(0, len(messages) - 1, 2):
        if messages[i].role == ChatRole.USER and messages[i + 1].role == ChatRole.ASSISTANT:
            turns.append(ConversationTurn(
                user_message=messages[i],
                assistant_message=messages[i + 1],
                confidence=messages[i + 1].metadata.get("confidence", 0.0)
                if messages[i + 1].metadata else 0.0,
            ))
    return turns


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete a chat session."""
    manager = get_session_manager()
    if manager.delete(session_id):
        return {"status": "deleted", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


# ── Helpers ──────────────────────────────────────────────────────────────

def _get_threshold() -> str:
    from kgrag.api.dependencies import get_settings
    return get_settings().get("confidence_threshold", "0.5")


def _auto_report_low_confidence(question: str, result: dict) -> None:
    """Best-effort forward to KGBuilder when confidence is low."""
    try:
        from kgrag.api.dependencies import forward_to_kgbuilder
        forward_to_kgbuilder([{
            "question": question,
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence", 0.0),
        }])
    except Exception:
        logger.warning("auto_report_failed", question=question[:50])
```

### 10.2 Explorer

`src/kgrag/api/routes/explorer.py`

```python
"""KG exploration endpoints — entity search, subgraph, laws, ontology."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query

from kgrag.api.explorer_schemas import (
    EntityDetail,
    EntityInfo,
    KGStats,
    LawInfo,
    LawStructure,
    OntologyClassInfo,
    OntologyTree,
    RelationEdge,
    RelationType,
    SubgraphResponse,
)
from kgrag.api.dependencies import neo4j_query, sparql_query

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Entities ─────────────────────────────────────────────────────────────

@router.get("/entities", response_model=list[EntityInfo])
async def list_entities(
    search: str = Query(default="", description="Text search filter"),
    entity_type: str = Query(default="", description="Filter by entity type"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[EntityInfo]:
    """List KG entities with optional search and type filter."""
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if search:
        conditions.append("toLower(n.label) CONTAINS toLower($search)")
        params["search"] = search
    if entity_type:
        conditions.append("any(l IN labels(n) WHERE l = $etype)")
        params["etype"] = entity_type

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cypher = f"""
        MATCH (n)
        {where}
        RETURN elementId(n) AS id, n.label AS label,
               labels(n) AS types, n.confidence AS confidence,
               n.description AS description
        ORDER BY n.label
        SKIP $offset LIMIT $limit
    """
    rows = neo4j_query(cypher, params)
    return [
        EntityInfo(
            id=str(r["id"]),
            label=r.get("label", ""),
            entity_type=r["types"][0] if r.get("types") else "",
            confidence=r.get("confidence") or 0.0,
            description=r.get("description") or "",
        )
        for r in rows
    ]


@router.get("/entities/{entity_id}", response_model=EntityDetail)
async def get_entity(entity_id: str) -> EntityDetail:
    """Get entity details with its direct neighbors."""
    # Get entity
    rows = neo4j_query(
        "MATCH (n) WHERE elementId(n) = $id RETURN n, labels(n) AS types",
        {"id": entity_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Entity not found")

    node = rows[0]["n"]
    types = rows[0]["types"]

    # Get neighbors
    rel_rows = neo4j_query(
        """
        MATCH (n)-[r]-(m)
        WHERE elementId(n) = $id
        RETURN elementId(n) AS src_id, n.label AS src_label,
               elementId(m) AS tgt_id, m.label AS tgt_label,
               type(r) AS predicate, r.confidence AS confidence,
               startNode(r) = n AS outgoing
        LIMIT 100
        """,
        {"id": entity_id},
    )

    neighbors = [
        RelationEdge(
            source_id=str(r["src_id"]) if r["outgoing"] else str(r["tgt_id"]),
            source_label=r.get("src_label", "") if r["outgoing"] else r.get("tgt_label", ""),
            target_id=str(r["tgt_id"]) if r["outgoing"] else str(r["src_id"]),
            target_label=r.get("tgt_label", "") if r["outgoing"] else r.get("src_label", ""),
            predicate=r["predicate"],
            confidence=r.get("confidence") or 0.0,
        )
        for r in rel_rows
    ]

    return EntityDetail(
        id=entity_id,
        label=node.get("label", ""),
        entity_type=types[0] if types else "",
        confidence=node.get("confidence") or 0.0,
        description=node.get("description") or "",
        properties={k: str(v) for k, v in node.items() if k not in ("label", "confidence", "description")},
        neighbors=neighbors,
    )


@router.get("/entities/{entity_id}/subgraph", response_model=SubgraphResponse)
async def get_entity_subgraph(
    entity_id: str,
    depth: int = Query(default=2, ge=1, le=5),
) -> SubgraphResponse:
    """Get vis.js-compatible subgraph centered on an entity."""
    rows = neo4j_query(
        f"""
        MATCH path = (n)-[*1..{depth}]-(m)
        WHERE elementId(n) = $id
        UNWIND nodes(path) AS node
        UNWIND relationships(path) AS rel
        WITH COLLECT(DISTINCT node) AS nodes, COLLECT(DISTINCT rel) AS rels
        RETURN nodes, rels
        """,
        {"id": entity_id},
    )

    if not rows:
        return SubgraphResponse(nodes=[], edges=[])

    vis_nodes = []
    vis_edges = []
    seen_nodes = set()
    seen_edges = set()

    for row in rows:
        for node in row.get("nodes", []):
            nid = str(node.element_id) if hasattr(node, "element_id") else str(id(node))
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                vis_nodes.append({
                    "id": nid,
                    "label": node.get("label", nid),
                    "group": list(node.labels)[0] if hasattr(node, "labels") and node.labels else "Unknown",
                })
        for rel in row.get("rels", []):
            eid = str(rel.element_id) if hasattr(rel, "element_id") else str(id(rel))
            if eid not in seen_edges:
                seen_edges.add(eid)
                vis_edges.append({
                    "from": str(rel.start_node.element_id) if hasattr(rel, "start_node") else "",
                    "to": str(rel.end_node.element_id) if hasattr(rel, "end_node") else "",
                    "label": rel.type if hasattr(rel, "type") else "",
                })

    return SubgraphResponse(nodes=vis_nodes, edges=vis_edges)


# ── Relations ────────────────────────────────────────────────────────────

@router.get("/relations", response_model=list[RelationType])
async def list_relation_types() -> list[RelationType]:
    """List all relation types with counts."""
    rows = neo4j_query("""
        MATCH ()-[r]->()
        RETURN type(r) AS predicate, count(r) AS count
        ORDER BY count DESC
    """)
    return [
        RelationType(predicate=r["predicate"], label=r["predicate"], count=r["count"])
        for r in rows
    ]


# ── Stats ────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=KGStats)
async def get_stats() -> KGStats:
    """KG-level statistics."""
    entity_count = neo4j_query("MATCH (n) RETURN count(n) AS c")[0]["c"]
    relation_count = neo4j_query("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]

    type_rows = neo4j_query("""
        MATCH (n) UNWIND labels(n) AS lbl
        RETURN lbl, count(n) AS c ORDER BY c DESC
    """)
    entity_types = {r["lbl"]: r["c"] for r in type_rows}

    rel_rows = neo4j_query("""
        MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY c DESC
    """)
    relation_types = {r["t"]: r["c"] for r in rel_rows}

    law_count_rows = neo4j_query("MATCH (n:Law) RETURN count(n) AS c")
    law_count = law_count_rows[0]["c"] if law_count_rows else 0

    return KGStats(
        entity_count=entity_count,
        relation_count=relation_count,
        entity_types=entity_types,
        relation_types=relation_types,
        law_count=law_count,
    )


# ── Laws ─────────────────────────────────────────────────────────────────

@router.get("/laws", response_model=list[LawInfo])
async def list_laws(
    limit: int = Query(default=50, ge=1, le=500),
) -> list[LawInfo]:
    """List laws/regulations in the KG."""
    rows = neo4j_query("""
        MATCH (l:Law)
        OPTIONAL MATCH (l)-[:HAS_SECTION]->(s)
        RETURN elementId(l) AS id, l.title AS title,
               l.abbreviation AS abbreviation, count(s) AS section_count
        ORDER BY l.title
        LIMIT $limit
    """, {"limit": limit})
    return [
        LawInfo(
            id=str(r["id"]),
            title=r.get("title", ""),
            abbreviation=r.get("abbreviation") or "",
            section_count=r.get("section_count", 0),
        )
        for r in rows
    ]


@router.get("/laws/{law_id}/structure", response_model=LawStructure)
async def get_law_structure(law_id: str) -> LawStructure:
    """Get hierarchical structure of a law (sections, subsections)."""
    rows = neo4j_query("""
        MATCH (l) WHERE elementId(l) = $id
        OPTIONAL MATCH (l)-[:HAS_SECTION]->(s)
        OPTIONAL MATCH (s)-[:HAS_SUBSECTION]->(ss)
        RETURN l.title AS title,
               collect(DISTINCT {id: elementId(s), title: s.title,
                       subs: collect(DISTINCT {id: elementId(ss), title: ss.title})}) AS sections
    """, {"id": law_id})

    if not rows:
        raise HTTPException(status_code=404, detail="Law not found")

    r = rows[0]
    children = [
        LawStructure(
            id=str(sec["id"]),
            title=sec.get("title", ""),
            children=[
                LawStructure(id=str(sub["id"]), title=sub.get("title", ""))
                for sub in sec.get("subs", []) if sub.get("id")
            ],
        )
        for sec in r.get("sections", []) if sec.get("id")
    ]

    return LawStructure(id=law_id, title=r.get("title", ""), children=children)


@router.get("/laws/{law_id}/linked-entities", response_model=list[EntityInfo])
async def get_law_linked_entities(law_id: str) -> list[EntityInfo]:
    """Get domain entities linked to a specific law."""
    rows = neo4j_query("""
        MATCH (l)-[:REFERENCES|APPLIES_TO|REGULATES]-(e)
        WHERE elementId(l) = $id AND NOT e:Law
        RETURN elementId(e) AS id, e.label AS label,
               labels(e) AS types, e.confidence AS confidence
        ORDER BY e.label
    """, {"id": law_id})
    return [
        EntityInfo(
            id=str(r["id"]),
            label=r.get("label", ""),
            entity_type=r["types"][0] if r.get("types") else "",
            confidence=r.get("confidence") or 0.0,
        )
        for r in rows
    ]


# ── Ontology ─────────────────────────────────────────────────────────────

@router.get("/ontology/classes", response_model=list[OntologyClassInfo])
async def list_ontology_classes() -> list[OntologyClassInfo]:
    """List ontology classes with instance counts."""
    # Get classes from Fuseki
    classes = sparql_query("""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?uri ?label ?description ?parent WHERE {
            ?uri a owl:Class .
            OPTIONAL { ?uri rdfs:label ?label }
            OPTIONAL { ?uri rdfs:comment ?description }
            OPTIONAL { ?uri rdfs:subClassOf ?parent . ?parent a owl:Class }
            FILTER(!isBlank(?uri))
        }
        ORDER BY ?label
    """)

    # Deduplicate
    seen: dict[str, OntologyClassInfo] = {}
    for row in classes:
        uri = row["uri"]
        if uri not in seen:
            label = row.get("label", uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1])
            seen[uri] = OntologyClassInfo(
                uri=uri,
                label=label,
                description=row.get("description", ""),
                parent_uri=row.get("parent"),
            )

    # TODO: Enrich with instance counts from Neo4j (match label to Neo4j label)

    return list(seen.values())


@router.get("/ontology/tree", response_model=list[OntologyTree])
async def get_ontology_tree() -> list[OntologyTree]:
    """Get full ontology hierarchy as a tree."""
    classes = await list_ontology_classes()

    # Build tree from flat list
    by_uri: dict[str, OntologyTree] = {
        c.uri: OntologyTree(uri=c.uri, label=c.label, instance_count=c.instance_count)
        for c in classes
    }
    roots: list[OntologyTree] = []

    for c in classes:
        node = by_uri[c.uri]
        if c.parent_uri and c.parent_uri in by_uri:
            by_uri[c.parent_uri].children.append(node)
        else:
            roots.append(node)

    return roots
```

### 10.3 HITL Feedback

`src/kgrag/api/routes/hitl.py`

```python
"""HITL feedback endpoints — report low-confidence answers to KGBuilder."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from kgrag.api.hitl_schemas import (
    FeedbackRequest,
    FeedbackResponse,
    LowConfidenceReport,
    ReportResponse,
)
from kgrag.api.dependencies import forward_to_kgbuilder, get_settings

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/hitl/report-low-confidence", response_model=ReportResponse)
async def report_low_confidence(report: LowConfidenceReport) -> ReportResponse:
    """Report low-confidence QA results to KGBuilder for gap detection.

    This is the main cross-service trigger: when GraphQA can't answer
    a question confidently, it sends the results here, which forwards
    them to KGBuilder's `POST /api/v1/hitl/gaps/detect`.

    Flow: GraphQA → KGBuilder (gap detection) → OntologyExtender (if TBox gaps)
    """
    settings = get_settings()
    threshold = float(settings.get("confidence_threshold", "0.5"))

    # Filter to truly low-confidence results
    low_conf = [
        r.model_dump()
        for r in report.qa_results
        if r.confidence < threshold
    ]

    if not low_conf:
        return ReportResponse(
            status="received",
            message=f"No results below threshold {threshold}",
        )

    logger.info(
        "reporting_low_confidence",
        count=len(low_conf),
        threshold=threshold,
    )

    # Forward to KGBuilder
    result = forward_to_kgbuilder(low_conf)

    return ReportResponse(
        status=result.get("status", "error"),
        gaps_detected=result.get("gaps_detected", 0),
        suggested_classes=result.get("suggested_new_classes", []),
        message=result.get("message", "Forwarded to KGBuilder"),
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Submit expert feedback on an answer (correction, approval, rejection).

    For now, stores locally. In future, can forward corrections to KGBuilder
    for ABox updates.
    """
    import uuid

    logger.info(
        "feedback_received",
        session_id=request.session_id,
        feedback_type=request.feedback_type,
    )

    # TODO: Persist feedback (file, DB, or forward to KGBuilder)
    feedback_id = f"fb_{uuid.uuid4().hex[:12]}"

    return FeedbackResponse(
        status="accepted",
        feedback_id=feedback_id,
    )
```

---

## 11. Chat Session Management

`src/kgrag/chat/session.py`

```python
"""In-memory chat session management."""

from __future__ import annotations

from datetime import datetime, timedelta
from dataclasses import dataclass, field
from threading import Lock

from kgrag.api.chat_schemas import ChatMessage


@dataclass
class ChatSession:
    """A single chat session."""

    session_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    messages: list[ChatMessage] = field(default_factory=list)

    def add_message(self, msg: ChatMessage) -> None:
        self.messages.append(msg)


class ChatSessionManager:
    """Thread-safe in-memory session store."""

    def __init__(self, max_sessions: int = 1000, max_age_hours: int = 24) -> None:
        self._lock = Lock()
        self.sessions: dict[str, ChatSession] = {}
        self._max_sessions = max_sessions
        self._max_age = timedelta(hours=max_age_hours)

    def get_or_create(self, session_id: str) -> ChatSession:
        with self._lock:
            self._evict_expired()
            if session_id not in self.sessions:
                if len(self.sessions) >= self._max_sessions:
                    # Evict oldest
                    oldest = min(self.sessions, key=lambda k: self.sessions[k].created_at)
                    del self.sessions[oldest]
                self.sessions[session_id] = ChatSession(session_id=session_id)
            return self.sessions[session_id]

    def get(self, session_id: str) -> ChatSession | None:
        with self._lock:
            return self.sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self.sessions.pop(session_id, None) is not None

    def _evict_expired(self) -> None:
        now = datetime.utcnow()
        expired = [
            sid for sid, s in self.sessions.items()
            if now - s.created_at > self._max_age
        ]
        for sid in expired:
            del self.sessions[sid]


# Module-level singleton
_manager: ChatSessionManager | None = None


def get_session_manager() -> ChatSessionManager:
    global _manager
    if _manager is None:
        _manager = ChatSessionManager()
    return _manager
```

---

## 12. SSE Streaming

`src/kgrag/chat/streaming.py`

```python
"""SSE stream event helpers."""

from __future__ import annotations

import json


def sse_event(event: str, data: dict | str) -> str:
    """Format a single SSE event string."""
    payload = json.dumps(data) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"


def sse_token(token: str) -> str:
    return sse_event("token", {"token": token})


def sse_reasoning_step(step: str, index: int) -> str:
    return sse_event("reasoning_step", {"step": step, "index": index})


def sse_provenance(sources: list[dict]) -> str:
    return sse_event("provenance", {"sources": sources})


def sse_subgraph(nodes: list, edges: list) -> str:
    return sse_event("subgraph", {"nodes": nodes, "edges": edges})


def sse_done(confidence: float, latency_ms: float) -> str:
    return sse_event("done", {"confidence": confidence, "latency_ms": latency_ms})


def sse_error(message: str) -> str:
    return sse_event("error", {"message": message})
```

---

## 13. Docker Setup

### 13.1 Dockerfile.api

`docker/Dockerfile.api`

```dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi "uvicorn[standard]" httpx sse-starlette

COPY . .
RUN pip install --no-cache-dir -e .

EXPOSE 8002

CMD ["uvicorn", "kgrag.api.server:app", "--host", "0.0.0.0", "--port", "8002"]
```

### 13.2 docker-compose.yml (standalone)

Root of the GraphQAAgent repo:

```yaml
services:
  # ── GraphQA API ────────────────────────────────────────────────────────
  graphqa-api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports:
      - "8002:8002"
    environment:
      SERVICE_NAME: graphqa
      UVICORN_PORT: "8002"
      OLLAMA_URL: http://ollama-graphqa:11434
      OLLAMA_MODEL: qwen3:8b
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: password
      QDRANT_URL: http://qdrant:6333
      FUSEKI_URL: http://fuseki:3030
      KGBUILDER_API_URL: http://localhost:8001  # cross-service (optional standalone)
      CONFIDENCE_THRESHOLD: "0.5"
    depends_on:
      neo4j:
        condition: service_healthy
      qdrant:
        condition: service_started
      ollama-graphqa:
        condition: service_started
    networks:
      - graphqa-net

  # ── Neo4j ──────────────────────────────────────────────────────────────
  neo4j:
    image: neo4j:5.26.0
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc", "n10s"]'
      NEO4J_apoc_export_file_enabled: "true"
      NEO4J_apoc_import_file_enabled: "true"
      NEO4J_apoc_import_file_use__neo4j__config: "true"
    volumes:
      - neo4j-data:/data
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      retries: 5
    networks:
      - graphqa-net

  # ── Qdrant ─────────────────────────────────────────────────────────────
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant-data:/qdrant/storage
    networks:
      - graphqa-net

  # ── Fuseki ─────────────────────────────────────────────────────────────
  fuseki:
    image: stain/jena-fuseki
    ports:
      - "3030:3030"
    environment:
      ADMIN_PASSWORD: admin
      FUSEKI_DATASET_1: kgbuilder
    volumes:
      - fuseki-data:/fuseki
    networks:
      - graphqa-net

  # ── Ollama (dedicated for GraphQA) ─────────────────────────────────────
  ollama-graphqa:
    image: ollama/ollama:0.14.3
    ports:
      - "11436:11434"
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    networks:
      - graphqa-net

volumes:
  neo4j-data:
  qdrant-data:
  fuseki-data:
  ollama-data:

networks:
  graphqa-net:
    driver: bridge
```

---

## 14. Cross-Service Integration

### 14.1 GraphQA → KGBuilder (low confidence)

When a QA answer has `confidence < 0.5`:

```
POST http://kgbuilder-api:8001/api/v1/hitl/gaps/detect
Content-Type: application/json

{
  "qa_results": [
    {
      "question": "What decommissioning obligations apply to offshore wind farms?",
      "answer": "Unable to find specific regulations...",
      "confidence": 0.32
    }
  ]
}
```

This happens automatically in `chat.py` via `_auto_report_low_confidence()`.

### 14.2 KGBuilder → GraphQA (CQ testing)

After ontology update + rebuild, KGBuilder can test competency questions:

```
POST http://graphqa-api:8002/api/v1/chat/send
Content-Type: application/json

{
  "message": "What are the requirements for decommissioning fund sufficiency?",
  "stream": false,
  "strategy": "hybrid_sota"
}
```

### 14.3 Full cycle

```
1. User asks question → GraphQA /chat/send
2. Low confidence (< 0.5) → GraphQA /hitl/report-low-confidence
3. Forwarded to → KGBuilder /hitl/gaps/detect
4. TBox gaps found → KGBuilder forwards to OntologyExtender /extend
5. OntologyExtender applies changes → notifies KGBuilder /build
6. KGBuilder rebuilds KG → tests CQs via GraphQA /chat/send
7. User asks same question → better answer
```

### 14.4 Platform docker-compose env vars

```yaml
graphqa-api:
  environment:
    KGBUILDER_API_URL: http://kgbuilder-api:8001

kgbuilder-api:
  environment:
    GRAPHQA_API_URL: http://graphqa-api:8002
    ONTOLOGY_API_URL: http://ontology-api:8003

ontology-api:
  environment:
    KGBUILDER_API_URL: http://kgbuilder-api:8001
```

---

## 15. Streamlit Frontend Pages

The GraphQA repo can include its own Streamlit frontend
(`src/kgrag/frontend/`). This is **optional** — the KGPlatform meta-repo
has a unified frontend that talks to all three APIs.

### Page Outline

| Page              | API calls                                               |
| ----------------- | ------------------------------------------------------- |
| `1_Chat.py`       | `POST /chat/send` (SSE), `GET /chat/sessions/*/history` |
| `2_KG_Explorer.py`| `GET /explore/entities`, `GET /explore/entities/*/subgraph` |
| `3_Ontology.py`   | `GET /explore/ontology/classes`, `GET /explore/ontology/tree` |
| `4_Reasoning.py`  | Select past answer → visualize CoT DAG + subgraph       |

### Chat page snippet

```python
# src/kgrag/frontend/pages/1_Chat.py
import streamlit as st
import httpx
import json

GRAPHQA_URL = "http://localhost:8002"

st.title("Knowledge Graph QA")

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.session_id = None

# Display history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Input
if prompt := st.chat_input("Ask a question about the knowledge graph..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        answer_tokens = []

        # Non-streaming for simplicity
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{GRAPHQA_URL}/api/v1/chat/send", json={
                "session_id": st.session_state.session_id,
                "message": prompt,
                "stream": False,
            })
            data = resp.json()
            st.session_state.session_id = data["session_id"]
            answer = data["message"]["content"]
            confidence = data["confidence"]

            placeholder.write(answer)
            if confidence < 0.5:
                st.warning(f"Low confidence: {confidence:.0%}")
            else:
                st.caption(f"Confidence: {confidence:.0%}")

            # Show reasoning
            if data.get("reasoning_chain"):
                with st.expander("Reasoning chain"):
                    for i, step in enumerate(data["reasoning_chain"]):
                        st.markdown(f"**Step {i+1}:** {step}")

    st.session_state.messages.append({"role": "assistant", "content": answer})
```

---

## 16. Testing Strategy

### Unit Tests

```
tests/api/
├── conftest.py              # TestClient, mock Neo4j/Qdrant/Fuseki
├── test_chat.py             # Streaming + blocking chat, sessions
├── test_explorer.py         # Entity search, subgraph, laws, ontology
├── test_hitl.py             # Low-confidence reporting, feedback
└── test_schemas.py          # Schema validation
```

**Key test fixtures:**

```python
@pytest.fixture
def client():
    from kgrag.api.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)

@pytest.fixture
def mock_neo4j():
    with patch("kgrag.api.dependencies.neo4j_query") as m:
        m.return_value = [
            {"id": "1", "label": "TestEntity", "types": ["Entity"],
             "confidence": 0.9, "description": "A test entity"}
        ]
        yield m

@pytest.fixture
def mock_kgbuilder():
    with patch("kgrag.api.dependencies.forward_to_kgbuilder") as m:
        m.return_value = {"status": "received", "gaps_detected": 0}
        yield m
```

**Key test cases:**

```python
def test_chat_blocking(client, mock_qa_pipeline):
    resp = client.post("/api/v1/chat/send", json={
        "message": "What is a decommissioning plan?",
        "stream": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["message"]["role"] == "assistant"

def test_chat_streaming(client, mock_qa_pipeline):
    resp = client.post("/api/v1/chat/send", json={
        "message": "Test question",
        "stream": True,
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

def test_explorer_entities(client, mock_neo4j):
    resp = client.get("/api/v1/explore/entities?search=test&limit=10")
    assert resp.status_code == 200
    assert len(resp.json()) > 0

def test_hitl_low_confidence(client, mock_kgbuilder):
    resp = client.post("/api/v1/hitl/report-low-confidence", json={
        "qa_results": [{"question": "test", "answer": "idk", "confidence": 0.3}],
    })
    assert resp.status_code == 200
```

---

## 17. Implementation Phases

| Phase | What                                | Effort | Priority |
| ----- | ----------------------------------- | ------ | -------- |
| **A** | Dependencies + schemas + server update | ~2h  | P0       |
| **B** | Chat endpoint (blocking mode first)   | ~3h  | P0       |
| **C** | Chat SSE streaming                    | ~2h  | P0       |
| **D** | Session management                    | ~2h  | P0       |
| **E** | HITL low-confidence reporting         | ~1h  | P0       |
| **F** | Explorer: entities + subgraph         | ~3h  | P1       |
| **G** | Explorer: laws + ontology             | ~2h  | P1       |
| **H** | Expert feedback endpoint              | ~1h  | P2       |
| **I** | Streamlit frontend                    | ~6h  | P2       |
| **J** | Docker setup + integration test       | ~2h  | P0       |

**MVP** (for demo): A + B + D + E + J ≈ 10h

---

## 18. Implementation Checklist

- [ ] Create `src/kgrag/api/chat_schemas.py` (§7.1)
- [ ] Create `src/kgrag/api/explorer_schemas.py` (§7.2)
- [ ] Create `src/kgrag/api/hitl_schemas.py` (§7.3)
- [ ] Create `src/kgrag/api/dependencies.py` (§8)
- [ ] Update `src/kgrag/api/server.py` (§9)
- [ ] Create `src/kgrag/api/routes/__init__.py`
- [ ] Create `src/kgrag/api/routes/chat.py` (§10.1)
- [ ] Create `src/kgrag/api/routes/explorer.py` (§10.2)
- [ ] Create `src/kgrag/api/routes/hitl.py` (§10.3)
- [ ] Create `src/kgrag/chat/__init__.py`
- [ ] Create `src/kgrag/chat/session.py` (§11)
- [ ] Create `src/kgrag/chat/streaming.py` (§12)
- [ ] Create `docker/Dockerfile.api` (§13.1)
- [ ] Create/update `docker-compose.yml` (§13.2)
- [ ] Add `[project.optional-dependencies] api = [...]` to `pyproject.toml`
- [ ] Install: `.venv/bin/pip install -e ".[api]"`
- [ ] Verify: `.venv/bin/python -c "from kgrag.api.server import app; print(app.title)"`
- [ ] Run: `.venv/bin/uvicorn kgrag.api.server:app --port 8002 --reload`
- [ ] Open http://localhost:8002/docs
- [ ] Create `tests/api/` test suite
- [ ] Run: `.venv/bin/pytest tests/api/ -v`
- [ ] Commit on `fast-api` branch

---

## Appendix: Full Endpoint Summary

| Method   | Path                                     | Description                           |
| -------- | ---------------------------------------- | ------------------------------------- |
| `GET`    | `/`                                      | Root → docs redirect                  |
| `GET`    | `/api/v1/health`                         | Health check (Neo4j + Qdrant + Ollama)|
| `POST`   | `/api/v1/ask`                            | **Existing** — blocking QA            |
| `POST`   | `/api/v1/chat/send`                      | Chat (SSE or blocking)                |
| `GET`    | `/api/v1/chat/sessions`                  | List sessions                         |
| `GET`    | `/api/v1/chat/sessions/{id}/history`     | Session conversation history          |
| `DELETE` | `/api/v1/chat/sessions/{id}`             | Delete session                        |
| `GET`    | `/api/v1/explore/entities`               | Search entities (paginated)           |
| `GET`    | `/api/v1/explore/entities/{id}`          | Entity details + neighbors            |
| `GET`    | `/api/v1/explore/entities/{id}/subgraph` | vis.js subgraph                       |
| `GET`    | `/api/v1/explore/relations`              | Relation types + counts               |
| `GET`    | `/api/v1/explore/stats`                  | KG statistics                         |
| `GET`    | `/api/v1/explore/laws`                   | List laws                             |
| `GET`    | `/api/v1/explore/laws/{id}/structure`    | Law hierarchy                         |
| `GET`    | `/api/v1/explore/laws/{id}/linked-entities` | Entities linked to law             |
| `GET`    | `/api/v1/explore/ontology/classes`       | Ontology classes                      |
| `GET`    | `/api/v1/explore/ontology/tree`          | Ontology hierarchy tree               |
| `POST`   | `/api/v1/hitl/report-low-confidence`     | Report low-confidence → KGBuilder     |
| `POST`   | `/api/v1/feedback`                       | Expert feedback on answers            |
