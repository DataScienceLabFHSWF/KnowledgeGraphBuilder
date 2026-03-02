# GraphQAAgent: Chat Interface & Demo Implementation Guide

> **Purpose**: Step-by-step guide for adding an interactive chat UI, streaming endpoints,
> and demo tooling to the GraphQAAgent repo. Copy this file into the GraphQAAgent
> repository and implement each section.
>
> **Date**: 2026-02-25  
> **Author**: Auto-generated from KnowledgeGraphBuilder ecosystem analysis  
> **Target repo**: `DataScienceLabFHSWF/GraphQAAgent`

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Architecture: What to Build](#2-architecture-what-to-build)
3. [Implementation Plan](#3-implementation-plan)
4. [Phase A: Streaming Chat API](#phase-a-streaming-chat-api)
5. [Phase B: Session & History Management](#phase-b-session--history-management)
6. [Phase C: KG/Ontology Explorer Endpoints](#phase-c-kgontology-explorer-endpoints)
7. [Phase D: Streamlit Chat Frontend](#phase-d-streamlit-chat-frontend)
8. [Phase E: Reasoning Visualization](#phase-e-reasoning-visualization)
9. [Phase F: Demo Script & Test Data](#phase-f-demo-script--test-data)
10. [Appendix: Full API Schema](#appendix-full-api-schema)
11. [Appendix: HITL Integration Points](#appendix-hitl-integration-points)

---

## 1. Current State Analysis

### What Exists

| Component | File | Status |
|-----------|------|--------|
| FastAPI server | `src/kgrag/api/server.py` | ✅ Working (uvicorn lifespan) |
| Health endpoint | `GET /api/v1/health` | ✅ Working |
| QA endpoint | `POST /api/v1/ask` | ✅ Working (returns JSON) |
| Request schema | `QuestionRequest(question, strategy, language)` | ✅ Working |
| Response schema | `AnswerResponse(answer, confidence, reasoning_chain, provenance, subgraph, latency_ms)` | ✅ Working |
| Orchestrator | Full SOTA pipeline (parse→expand→retrieve→CoT→generate→verify→explain) | ✅ Working |
| CLI | `src/kgrag/cli.py` | ❌ Stub (348B) |

### What's Missing

| Feature | Priority | Notes |
|---------|----------|-------|
| **Streaming /chat endpoint** | P0 | SSE for real-time token streaming |
| **Chat session management** | P0 | Multi-turn conversations with history |
| **Web frontend** | P0 | Streamlit or HTML for professor demo |
| **KG explorer endpoints** | P1 | Browse entities, relations, subgraphs |
| **Ontology explorer endpoints** | P1 | Browse TBox classes and hierarchy |
| **Reasoning visualization** | P1 | Interactive CoT + subgraph display |
| **Demo mode** | P1 | Pre-loaded questions, guided walkthrough |
| **HITL feedback endpoints** | P2 | Submit corrections, flag issues |
| **WebSocket support** | P2 | Real-time bi-directional communication |

---

## 2. Architecture: What to Build

```
src/kgrag/
├── api/
│   ├── server.py              (existing — add CORS, static files)
│   ├── routes.py              (existing — keep /ask)
│   ├── chat_routes.py         (NEW — streaming chat + sessions)
│   ├── explorer_routes.py     (NEW — KG/ontology browsing)
│   ├── schemas.py             (existing — extend with chat schemas)
│   └── chat_schemas.py        (NEW — chat-specific models)
├── chat/                      (NEW — chat session management)
│   ├── __init__.py
│   ├── session.py             (ChatSession with history + context)
│   ├── history.py             (Persist chat history to JSON/SQLite)
│   └── streaming.py           (SSE streaming helper)
├── frontend/                  (NEW — Streamlit chat UI)
│   ├── app.py                 (Main Streamlit app)
│   ├── pages/
│   │   ├── 1_Chat.py          (Chat interface)
│   │   ├── 2_KG_Explorer.py   (KG browser)
│   │   ├── 3_Ontology.py      (TBox browser)
│   │   └── 4_Reasoning.py     (Reasoning visualization)
│   └── components/
│       ├── chat_message.py    (Styled chat bubble)
│       ├── subgraph_viewer.py (vis.js or pyvis graph)
│       └── reasoning_dag.py   (CoT step visualization)
└── demo/                      (NEW — demo tooling)
    ├── __init__.py
    ├── demo_runner.py          (Guided demo with pre-loaded questions)
    ├── demo_data.py            (Sample questions, expected answers)
    └── demo_export.py          (Export demo session as PDF/HTML)
```

---

## 3. Implementation Plan

### Order of Implementation

```
Phase A: Streaming Chat API            (~4h)
  └── Phase B: Session Management      (~3h)
       └── Phase C: Explorer Endpoints (~3h)
            └── Phase D: Streamlit UI  (~6h)
                 └── Phase E: Reasoning Viz (~4h)
                      └── Phase F: Demo Script (~2h)
```

### Dependencies

- **No new heavy dependencies** — use what's already in the project
- Streamlit: `pip install streamlit` (already common in OntologyExtender)
- SSE: FastAPI's `StreamingResponse` + `asyncio` (built-in)
- Graph viz: `pyvis` or `streamlit-agraph` for Streamlit; `vis.js` CDN for HTML

---

## Phase A: Streaming Chat API

### A.1 Create `src/kgrag/api/chat_schemas.py`

```python
"""Chat-specific request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field
from kgrag.api.schemas import ProvenanceResponse


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    timestamp: str | None = None
    metadata: dict | None = None  # confidence, reasoning, provenance


class ChatRequest(BaseModel):
    """Request for the streaming chat endpoint."""
    session_id: str | None = None  # None = create new session
    message: str = Field(..., min_length=1)
    strategy: str = "hybrid_sota"
    language: str = "de"
    stream: bool = True  # False = return full JSON like /ask
    include_reasoning: bool = True
    include_subgraph: bool = True


class ChatResponse(BaseModel):
    """Full (non-streaming) chat response."""
    session_id: str
    message: ChatMessage
    confidence: float = 0.0
    reasoning_chain: list[str] = Field(default_factory=list)
    provenance: list[ProvenanceResponse] = Field(default_factory=list)
    subgraph: dict | None = None
    latency_ms: float = 0.0


class ChatStreamEvent(BaseModel):
    """Server-Sent Event payload for streaming."""
    event: str  # "token", "reasoning_step", "provenance", "subgraph", "done", "error"
    data: str   # JSON-encoded payload
```

### A.2 Create `src/kgrag/api/chat_routes.py`

```python
"""Chat API routes with SSE streaming support."""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from kgrag.api.chat_schemas import ChatRequest, ChatResponse, ChatStreamEvent
from kgrag.chat.session import ChatSessionManager

router = APIRouter(prefix="/chat", tags=["chat"])

# Injected by server.py
_session_manager: ChatSessionManager | None = None


def set_session_manager(mgr: ChatSessionManager) -> None:
    global _session_manager  # noqa: PLW0603
    _session_manager = mgr


@router.post("/send")
async def chat_send(request: ChatRequest):
    """Send a message. Returns SSE stream if stream=True, else JSON."""
    if _session_manager is None:
        raise HTTPException(503, "Chat not initialized")

    session_id = request.session_id or uuid.uuid4().hex[:12]

    if request.stream:
        return StreamingResponse(
            _stream_response(session_id, request),
            media_type="text/event-stream",
        )
    else:
        # Non-streaming: delegate to orchestrator and return full response
        result = await _session_manager.process_message(session_id, request)
        return result


async def _stream_response(
    session_id: str, request: ChatRequest
) -> AsyncGenerator[str, None]:
    """Generate SSE events for a streaming chat response.

    Event types:
    - "session": {"session_id": "..."}
    - "token": {"text": "..."}
    - "reasoning_step": {"step": 1, "text": "..."}
    - "provenance": [{"source": "...", "score": ...}]
    - "subgraph": {"nodes": [...], "edges": [...]}
    - "done": {"confidence": ..., "latency_ms": ...}
    - "error": {"message": "..."}
    """
    # Emit session ID first
    yield _sse("session", {"session_id": session_id})

    try:
        # TODO: Implement streaming orchestrator
        # The current Orchestrator.answer() is not streaming-capable.
        # Options:
        # 1. Run answer() in background, emit tokens from LLM callback
        # 2. Add a stream_answer() method to Orchestrator
        # 3. Use LangChain's streaming callbacks

        # For now: run full pipeline, emit result as chunks
        result = await _session_manager.process_message(session_id, request)

        # Emit reasoning steps
        if request.include_reasoning and result.reasoning_chain:
            for i, step in enumerate(result.reasoning_chain):
                yield _sse("reasoning_step", {"step": i + 1, "text": step})

        # Emit answer as token stream (simulated for now)
        words = result.message.content.split()
        for word in words:
            yield _sse("token", {"text": word + " "})

        # Emit provenance
        if result.provenance:
            yield _sse("provenance", [p.model_dump() for p in result.provenance])

        # Emit subgraph
        if request.include_subgraph and result.subgraph:
            yield _sse("subgraph", result.subgraph)

        # Done
        yield _sse("done", {
            "confidence": result.confidence,
            "latency_ms": result.latency_ms,
        })
    except Exception as e:
        yield _sse("error", {"message": str(e)})


def _sse(event: str, data: object) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/sessions/{session_id}/history")
async def get_history(session_id: str):
    """Get chat history for a session."""
    if _session_manager is None:
        raise HTTPException(503, "Chat not initialized")
    return _session_manager.get_history(session_id)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    if _session_manager is None:
        raise HTTPException(503, "Chat not initialized")
    _session_manager.delete_session(session_id)
    return {"status": "deleted"}
```

### A.3 Register in `server.py`

Add to `server.py` after the existing router:

```python
from kgrag.api.chat_routes import router as chat_router, set_session_manager
from kgrag.chat.session import ChatSessionManager

# In lifespan(), after set_orchestrator(orchestrator):
session_manager = ChatSessionManager(orchestrator)
set_session_manager(session_manager)

# In create_app(), after existing router:
app.include_router(chat_router, prefix="/api/v1")

# Add CORS for Streamlit frontend
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Phase B: Session & History Management

### B.1 Create `src/kgrag/chat/session.py`

```python
"""Chat session management with conversation history."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from kgrag.agents.orchestrator import Orchestrator
from kgrag.api.chat_schemas import ChatMessage, ChatRequest, ChatResponse, ProvenanceResponse


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""
    user_message: str
    assistant_message: str
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


class ChatSession:
    """Manages a single chat conversation."""

    def __init__(self, session_id: str, max_history: int = 20) -> None:
        self.session_id = session_id
        self.turns: list[ConversationTurn] = []
        self.max_history = max_history
        self.created_at = time.time()

    def add_turn(self, user_msg: str, assistant_msg: str, confidence: float = 0.0) -> None:
        self.turns.append(ConversationTurn(user_msg, assistant_msg, confidence))
        if len(self.turns) > self.max_history:
            self.turns = self.turns[-self.max_history:]

    def get_context_prompt(self) -> str:
        """Build conversation context for the LLM.

        Returns recent history formatted as a prompt prefix so the LLM
        can maintain conversational coherence.
        """
        if not self.turns:
            return ""

        lines = ["Previous conversation:"]
        for turn in self.turns[-5:]:  # Last 5 turns for context
            lines.append(f"User: {turn.user_message}")
            lines.append(f"Assistant: {turn.assistant_message}")
        lines.append("")
        return "\n".join(lines)


class ChatSessionManager:
    """Manage multiple chat sessions."""

    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orchestrator = orchestrator
        self._sessions: dict[str, ChatSession] = {}

    def get_or_create_session(self, session_id: str) -> ChatSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = ChatSession(session_id)
        return self._sessions[session_id]

    async def process_message(
        self, session_id: str, request: ChatRequest
    ) -> ChatResponse:
        """Process a chat message through the QA pipeline."""
        session = self.get_or_create_session(session_id)

        # Build contextual question with history
        context = session.get_context_prompt()
        full_question = f"{context}Current question: {request.message}" if context else request.message

        # Call the orchestrator
        answer = await self._orchestrator.answer(
            full_question, strategy=request.strategy
        )

        # Record the turn
        session.add_turn(request.message, answer.answer_text, answer.confidence)

        # Build response
        provenance = [
            ProvenanceResponse(
                source=ctx.source.value,
                score=ctx.score,
                doc_id=ctx.provenance.doc_id if ctx.provenance else None,
                source_id=ctx.provenance.source_id if ctx.provenance else None,
                entity_ids=ctx.provenance.entity_ids if ctx.provenance else [],
            )
            for ctx in answer.evidence
        ]

        return ChatResponse(
            session_id=session_id,
            message=ChatMessage(role="assistant", content=answer.answer_text),
            confidence=answer.confidence,
            reasoning_chain=answer.reasoning_chain,
            provenance=provenance,
            subgraph=answer.subgraph_json,
            latency_ms=answer.latency_ms,
        )

    def get_history(self, session_id: str) -> list[dict]:
        session = self._sessions.get(session_id)
        if not session:
            return []
        return [
            {"user": t.user_message, "assistant": t.assistant_message,
             "confidence": t.confidence, "timestamp": t.timestamp}
            for t in session.turns
        ]

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
```

---

## Phase C: KG/Ontology Explorer Endpoints

### C.1 Create `src/kgrag/api/explorer_routes.py`

These endpoints let the frontend browse the knowledge graph and ontology
interactively.

```python
"""Explorer API routes for browsing KG and ontology."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/explore", tags=["explorer"])

# Injected by server.py
_neo4j = None
_fuseki = None


def set_connectors(neo4j, fuseki) -> None:
    global _neo4j, _fuseki  # noqa: PLW0603
    _neo4j, _fuseki = neo4j, fuseki


# --- KG Browsing -----------------------------------------------------------

@router.get("/entities")
async def list_entities(
    entity_type: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
):
    """List entities in the KG, optionally filtered by type or search term.

    TODO: Implement with Neo4j Cypher:
        MATCH (n:Entity)
        WHERE ($type IS NULL OR n.entity_type = $type)
          AND ($search IS NULL OR n.label CONTAINS $search)
        RETURN n ORDER BY n.label SKIP $offset LIMIT $limit
    """
    raise HTTPException(501, "Not yet implemented")


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Get a single entity with its relations.

    TODO: Implement with Neo4j:
        MATCH (n:Entity {id: $id})
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN n, collect({type: type(r), target: m})
    """
    raise HTTPException(501, "Not yet implemented")


@router.get("/entities/{entity_id}/subgraph")
async def get_entity_subgraph(entity_id: str, depth: int = Query(default=2, le=4)):
    """Get the local subgraph around an entity (for visualization).

    TODO: Return nodes + edges in vis.js compatible format:
        {"nodes": [{"id": ..., "label": ..., "group": ...}],
         "edges": [{"from": ..., "to": ..., "label": ...}]}
    """
    raise HTTPException(501, "Not yet implemented")


@router.get("/relations")
async def list_relation_types():
    """List all relation types in the KG with counts.

    TODO: MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC
    """
    raise HTTPException(501, "Not yet implemented")


@router.get("/stats")
async def get_kg_stats():
    """Get KG statistics (node count, edge count, types).

    TODO: Aggregate query returning counts per label and relationship type.
    """
    raise HTTPException(501, "Not yet implemented")


# --- Law Graph Browsing ----------------------------------------------------

@router.get("/laws")
async def list_laws():
    """List all laws in the law graph.

    TODO: MATCH (g:Gesetz) RETURN g ORDER BY g.name
    """
    raise HTTPException(501, "Not yet implemented")


@router.get("/laws/{law_id}/structure")
async def get_law_structure(law_id: str):
    """Get the hierarchical structure of a law (Gesetz → Abschnitt → Paragraph → Absatz).

    TODO: Return tree structure for rendering.
    """
    raise HTTPException(501, "Not yet implemented")


@router.get("/laws/{law_id}/linked-entities")
async def get_law_linked_entities(law_id: str):
    """Get domain entities linked to a specific law.

    TODO: MATCH (p:Paragraph)-[:LINKED_TO]->(e:Entity) WHERE ...
    """
    raise HTTPException(501, "Not yet implemented")


# --- Ontology Browsing -----------------------------------------------------

@router.get("/ontology/classes")
async def list_ontology_classes():
    """List all ontology classes with hierarchy.

    TODO: SPARQL query to Fuseki:
        SELECT ?class ?label ?parent WHERE {
          ?class a owl:Class .
          OPTIONAL { ?class rdfs:label ?label }
          OPTIONAL { ?class rdfs:subClassOf ?parent }
        }
    """
    raise HTTPException(501, "Not yet implemented")


@router.get("/ontology/classes/{class_uri}/properties")
async def get_class_properties(class_uri: str):
    """Get properties (data + object) for an ontology class.

    TODO: SPARQL query for domain/range properties.
    """
    raise HTTPException(501, "Not yet implemented")


@router.get("/ontology/tree")
async def get_ontology_tree():
    """Get the full class hierarchy as a tree for visualization.

    TODO: Return in format suitable for D3.js/Cytoscape.js tree rendering.
    """
    raise HTTPException(501, "Not yet implemented")
```

Register in `server.py`:
```python
from kgrag.api.explorer_routes import router as explorer_router, set_connectors
# In lifespan: set_connectors(orchestrator.neo4j, orchestrator.fuseki)
# In create_app: app.include_router(explorer_router, prefix="/api/v1")
```

---

## Phase D: Streamlit Chat Frontend

### D.1 Create `src/kgrag/frontend/app.py`

```python
"""Streamlit main app — GraphQAAgent Interactive Demo."""
import streamlit as st

st.set_page_config(
    page_title="GraphQA Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔍 GraphQA Agent — Knowledge Graph Q&A")
st.markdown("""
Interactive demo for querying the ontology-driven Knowledge Graph.

**Features:**
- 💬 **Chat**: Ask questions about the knowledge graph
- 🕸️ **KG Explorer**: Browse entities and relations
- 📐 **Ontology**: Explore the TBox class hierarchy
- 🧠 **Reasoning**: Visualize Chain-of-Thought reasoning

Use the sidebar to navigate between pages.
""")

# Show system status in sidebar
with st.sidebar:
    st.header("System Status")
    # TODO: Check /api/v1/health
    # import httpx
    # try:
    #     r = httpx.get("http://localhost:8080/api/v1/health", timeout=5)
    #     data = r.json()
    #     st.success(f"API: {data['status']} (v{data['version']})")
    # except Exception:
    #     st.error("API: Unreachable")
    st.info("TODO: Implement health check")
```

### D.2 Create `src/kgrag/frontend/pages/1_Chat.py`

This is the main chat interface. Key features:
- Chat-style UI with `st.chat_message`
- Streaming support via SSE
- Expandable reasoning chain
- Provenance display
- Subgraph visualization

```python
"""Chat page — conversational QA over the Knowledge Graph."""
import json
import uuid

import httpx
import streamlit as st

API_URL = st.secrets.get("api_url", "http://localhost:8080/api/v1")

st.header("💬 Chat with the Knowledge Graph")

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:12]
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("confidence"):
            st.caption(f"Confidence: {msg['confidence']:.0%} | Latency: {msg.get('latency_ms', 0):.0f}ms")
        if msg.get("reasoning"):
            with st.expander("🧠 Reasoning Chain"):
                for i, step in enumerate(msg["reasoning"], 1):
                    st.markdown(f"**Step {i}:** {step}")
        if msg.get("provenance"):
            with st.expander(f"📚 Sources ({len(msg['provenance'])})"):
                for p in msg["provenance"]:
                    st.markdown(f"- [{p['source']}] score={p['score']:.3f}")

# Chat input
if prompt := st.chat_input("Ask a question about the Knowledge Graph..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Show assistant response
    with st.chat_message("assistant"):
        with st.spinner("Querying knowledge graph..."):
            # TODO: Implement actual API call
            # try:
            #     resp = httpx.post(f"{API_URL}/chat/send", json={
            #         "session_id": st.session_state.session_id,
            #         "message": prompt,
            #         "strategy": "hybrid_sota",
            #         "stream": False,
            #     }, timeout=120)
            #     data = resp.json()
            #     answer = data["message"]["content"]
            #     confidence = data.get("confidence", 0)
            #     reasoning = data.get("reasoning_chain", [])
            #     provenance = data.get("provenance", [])
            #     latency = data.get("latency_ms", 0)
            # except Exception as e:
            #     answer = f"Error: {e}"
            #     confidence = 0
            #     reasoning = []
            #     provenance = []
            #     latency = 0

            answer = "TODO: Connect to GraphQAAgent API"
            confidence = 0
            reasoning = []
            provenance = []
            latency = 0

        st.write(answer)
        if confidence:
            st.caption(f"Confidence: {confidence:.0%} | Latency: {latency:.0f}ms")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "confidence": confidence,
        "reasoning": reasoning,
        "provenance": provenance,
        "latency_ms": latency,
    })

# Sidebar controls
with st.sidebar:
    st.subheader("Chat Settings")
    strategy = st.selectbox("Retrieval Strategy", [
        "hybrid_sota", "hybrid", "graph_only", "vector_only"
    ])
    language = st.selectbox("Language", ["de", "en"])

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.session_state.session_id = uuid.uuid4().hex[:12]
        st.rerun()

    st.divider()

    # Pre-loaded demo questions
    st.subheader("Demo Questions")
    demo_qs = [
        "Welche Gesetze regeln den Rückbau von Kernkraftwerken?",
        "What entities are involved in decommissioning?",
        "Which paragraphs govern radiation protection?",
        "What is the relationship between AtG and StrlSchG?",
        "Which waste types are in the KrWG?",
    ]
    for q in demo_qs:
        if st.button(q[:50] + "...", key=f"demo_{hash(q)}"):
            st.session_state.messages.append({"role": "user", "content": q})
            st.rerun()
```

### D.3 Other Pages (Stubs)

Create stub pages for KG Explorer, Ontology, and Reasoning visualization.
Each should call the `/api/v1/explore/*` endpoints from Phase C.

**`pages/2_KG_Explorer.py`** — Entity search + subgraph visualization (pyvis/streamlit-agraph)  
**`pages/3_Ontology.py`** — Class hierarchy tree + property browser  
**`pages/4_Reasoning.py`** — Select a past QA answer and view its full reasoning DAG  

### D.4 Launch Configuration

Add to `pyproject.toml`:
```toml
[project.scripts]
kgrag-api = "uvicorn kgrag.api.server:app --host 0.0.0.0 --port 8080"
kgrag-ui = "streamlit run src/kgrag/frontend/app.py --server.port 8501"
```

Or `scripts/run_demo.sh`:
```bash
#!/bin/bash
# Start both API and Streamlit UI
echo "Starting GraphQA API on :8080..."
uvicorn kgrag.api.server:app --host 0.0.0.0 --port 8080 &
API_PID=$!

echo "Starting Streamlit UI on :8501..."
streamlit run src/kgrag/frontend/app.py --server.port 8501 &
UI_PID=$!

trap "kill $API_PID $UI_PID 2>/dev/null" EXIT
echo "Demo running: API=http://localhost:8080 UI=http://localhost:8501"
wait
```

---

## Phase E: Reasoning Visualization

### E.1 Subgraph Viewer Component

The orchestrator already returns `subgraph_json` with nodes and edges.
Create a Streamlit component that renders this with pyvis:

```python
# src/kgrag/frontend/components/subgraph_viewer.py
"""Interactive subgraph visualization using pyvis."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

def render_subgraph(subgraph: dict, height: int = 500) -> None:
    """Render a subgraph as an interactive network.

    Args:
        subgraph: Dict with 'nodes' and 'edges' keys.
                  Each node: {"id": str, "label": str, "type": str}
                  Each edge: {"source": str, "target": str, "label": str}
        height: Pixel height of the visualization.
    """
    # TODO: Implement with pyvis or vis.js
    # from pyvis.network import Network
    # net = Network(height=f"{height}px", width="100%", notebook=False)
    #
    # TYPE_COLORS = {
    #     "Facility": "#1565C0",
    #     "Organization": "#2E7D32",
    #     "LegalProvision": "#7B1FA2",
    #     "Process": "#EF6C00",
    # }
    #
    # for node in subgraph.get("nodes", []):
    #     color = TYPE_COLORS.get(node.get("type", ""), "#757575")
    #     net.add_node(node["id"], label=node["label"], color=color, title=node.get("type", ""))
    #
    # for edge in subgraph.get("edges", []):
    #     net.add_edge(edge["source"], edge["target"], label=edge.get("label", ""))
    #
    # html = net.generate_html()
    # components.html(html, height=height)

    st.info(f"TODO: Render subgraph with {len(subgraph.get('nodes', []))} nodes")
```

### E.2 Reasoning DAG Component

Visualize the Chain-of-Thought steps as a directed graph:

```python
# src/kgrag/frontend/components/reasoning_dag.py
"""Chain-of-Thought reasoning visualization."""
from __future__ import annotations

import streamlit as st


def render_reasoning_chain(
    reasoning_steps: list[dict],
    verification: dict | None = None,
) -> None:
    """Render reasoning steps as an interactive timeline.

    Each step shows:
    - Sub-question decomposition
    - Evidence text with entity highlights
    - Confidence score
    - Grounding entities (linked to KG)
    """
    # TODO: Implement as expandable cards with entity links
    for i, step in enumerate(reasoning_steps, 1):
        with st.expander(f"Step {i}: {step.get('sub_question', 'N/A')}", expanded=(i == 1)):
            st.markdown(f"**Evidence:** {step.get('evidence_text', 'N/A')}")
            st.markdown(f"**Answer fragment:** {step.get('answer_fragment', 'N/A')}")
            st.progress(step.get('confidence', 0))

            entities = step.get('grounding_entities', [])
            if entities:
                st.caption(f"Grounding: {', '.join(entities)}")

    if verification:
        st.divider()
        faithful = verification.get("is_faithful", True)
        score = verification.get("faithfulness_score", 1.0)
        st.metric("Faithfulness", f"{score:.0%}", delta="✓" if faithful else "⚠ Issues found")

        if verification.get("contradicted_claims"):
            st.warning("Contradicted claims:")
            for claim in verification["contradicted_claims"]:
                st.markdown(f"- {claim}")
```

---

## Phase F: Demo Script & Test Data

### F.1 Demo Data

```python
# src/kgrag/demo/demo_data.py
"""Pre-loaded demo questions and expected behavior."""

DEMO_SCENARIOS = [
    {
        "title": "Nuclear Decommissioning Legal Framework",
        "questions": [
            "Welche Gesetze regeln den Rückbau von Kernkraftwerken in Deutschland?",
            "Which paragraphs of the AtG cover decommissioning permits?",
            "What is the relationship between AtG and StrlSchG for decommissioning?",
        ],
        "expected_features": ["multi-hop reasoning", "law graph traversal", "cross-references"],
    },
    {
        "title": "Waste Management Chain",
        "questions": [
            "Which types of radioactive waste are distinguished in the StrlSchG?",
            "What processes are required for waste disposal according to KrWG?",
        ],
        "expected_features": ["entity enumeration", "process chain", "legal provisions"],
    },
    {
        "title": "Facility-Specific Queries",
        "questions": [
            "Which nuclear facilities are mentioned in the knowledge graph?",
            "What permits does a nuclear facility need for decommissioning?",
        ],
        "expected_features": ["entity lookup", "relation traversal", "type hierarchy"],
    },
]
```

### F.2 Guided Demo Runner

```python
# src/kgrag/demo/demo_runner.py
"""Guided demo that walks through scenarios with rich output."""
from __future__ import annotations

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kgrag.demo.demo_data import DEMO_SCENARIOS

API_URL = "http://localhost:8080/api/v1"
console = Console()


async def run_demo(scenario_idx: int = 0) -> None:
    """Run a guided demo scenario.

    TODO: Implement — call /chat/send for each question,
    display results with Rich formatting.
    """
    scenario = DEMO_SCENARIOS[scenario_idx]
    console.print(Panel(
        f"[bold]{scenario['title']}[/bold]\n"
        f"Questions: {len(scenario['questions'])}\n"
        f"Features: {', '.join(scenario['expected_features'])}",
        title="Demo Scenario",
    ))

    # TODO: Loop through questions, call API, display results
    for q in scenario["questions"]:
        console.print(f"\n[bold cyan]Q:[/bold cyan] {q}")
        # resp = await httpx.AsyncClient().post(...)
        console.print("[dim]TODO: Call API and display answer[/dim]")
```

---

## Appendix: Full API Schema

After all phases, the complete API surface will be:

```
GET  /api/v1/health                              → HealthResponse
POST /api/v1/ask                                 → AnswerResponse (existing)
POST /api/v1/chat/send                           → SSE stream or ChatResponse
GET  /api/v1/chat/sessions/{id}/history           → list[ConversationTurn]
DELETE /api/v1/chat/sessions/{id}                 → {"status": "deleted"}
GET  /api/v1/explore/entities                     → list[Entity] (paginated)
GET  /api/v1/explore/entities/{id}                → Entity + relations
GET  /api/v1/explore/entities/{id}/subgraph       → vis.js graph JSON
GET  /api/v1/explore/relations                    → list[RelationType + count]
GET  /api/v1/explore/stats                        → KG statistics
GET  /api/v1/explore/laws                         → list[Law]
GET  /api/v1/explore/laws/{id}/structure          → law hierarchy tree
GET  /api/v1/explore/laws/{id}/linked-entities    → list[Entity]
GET  /api/v1/explore/ontology/classes             → list[OntologyClass + parent]
GET  /api/v1/explore/ontology/classes/{uri}/props → list[Property]
GET  /api/v1/explore/ontology/tree                → hierarchy tree JSON
```

---

## Appendix: HITL Integration Points

When the HITL system is implemented (as a separate repo, see discussion below),
these GraphQAAgent endpoints should feed into it:

1. **Low-confidence answers** → trigger gap detection
   - After each `/ask` or `/chat/send`, if `confidence < 0.5`:
   - POST to HITL system: `{"trigger": "low_confidence_qa", "question": ..., "confidence": ...}`

2. **Unanswerable questions** → generate new CQs
   - If orchestrator returns empty/hedging answer:
   - POST to HITL: `{"trigger": "unanswerable", "question": ...}`

3. **Expert corrections** (future `/feedback` endpoint):
   - `POST /api/v1/feedback` → accept corrections on answers
   - Route to KGBuilder (ABox fix) or OntologyExtender (TBox gap)

4. **Subgraph export for review**:
   - `GET /api/v1/explore/entities/{id}/subgraph` data is exactly what
     the HITL HTML viewer needs for expert inspection.

---

## Implementation Priority

For the **professor demo on 2026-02-27**, the minimum viable set is:

1. **Phase A**: `/chat/send` with non-streaming mode (skip SSE for now)
2. **Phase B**: Basic session management (in-memory, no persistence)
3. **Phase D**: Streamlit Chat page only (skip explorer/reasoning pages)
4. **Phase F**: Demo data + guided walkthrough

This gives you a working chat UI that calls the existing `/ask` endpoint
with session context. Everything else can be iterated on later.
