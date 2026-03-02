# KGPlatform — Orchestration Plan

> **Purpose**: Blueprint for creating a meta-repository that wires together  
> KnowledgeGraphBuilder, GraphQAAgent, and OntologyExtender into a single  
> Docker Compose deployment with FastAPI service layers.
>
> **Date**: 2026-03-02  
> **Target repo**: `DataScienceLabFHSWF/KGPlatform`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Repository Structure](#2-repository-structure)
3. [Service Architecture](#3-service-architecture)
4. [Port Allocation](#4-port-allocation)
5. [Docker Compose](#5-docker-compose)
6. [FastAPI Service: KGBuilder](#6-fastapi-service-kgbuilder)
7. [FastAPI Service: OntologyExtender](#7-fastapi-service-ontologyextender)
8. [FastAPI Service: GraphQAAgent](#8-fastapi-service-graphqaagent)
9. [Inter-Service Communication](#9-inter-service-communication)
10. [Shared Schemas](#10-shared-schemas)
11. [Frontend (Streamlit)](#11-frontend-streamlit)
12. [Setup & Bootstrap Script](#12-setup--bootstrap-script)
13. [Environment Variables](#13-environment-variables)
14. [Implementation Order](#14-implementation-order)
15. [Standalone Compose Files](#15-standalone-compose-files)

---

## 1. Overview

Three repositories form the KG research ecosystem:

| Repository | GitHub | Purpose |
|-----------|--------|---------|
| **KnowledgeGraphBuilder** | `DataScienceLabFHSWF/KnowledgeGraphBuilder` | KG construction, validation, export |
| **GraphQAAgent** | `DataScienceLabFHSWF/GraphQAAgent` | Ontology-informed GraphRAG QA |
| **OntologyExtender** | `DataScienceLabFHSWF/OntologyExtender` | Human-in-the-loop ontology extension |

Each repo:
- **Keeps working standalone** with its own `docker-compose.yml` and Ollama instance
- **Gets a FastAPI service layer** for programmatic access
- **Connects to shared infrastructure** (Neo4j, Qdrant, Fuseki) when run together

The HITL feedback loop drives inter-service communication:

```
GraphQAAgent ──(low confidence)──► KGBuilder ──(gaps)──► OntologyExtender
     ▲                                 ▲                        │
     │                                 │                        │
     └── new CQs from users    expert corrections      updated OWL + SHACL
```

---

## 2. Repository Structure

```
KGPlatform/
├── docker-compose.yml              # Full orchestrated deployment
├── docker-compose.override.yml     # Local dev overrides (optional)
├── .env.example                    # All env vars documented
├── .gitmodules                     # Submodule definitions
├── README.md
├── Makefile                        # Convenience targets
│
├── repos/                          # Git submodules (the 3 repos)
│   ├── KnowledgeGraphBuilder/      # submodule → DataScienceLabFHSWF/KnowledgeGraphBuilder
│   ├── GraphQAAgent/               # submodule → DataScienceLabFHSWF/GraphQAAgent
│   └── OntologyExtender/           # submodule → DataScienceLabFHSWF/OntologyExtender
│
├── services/                       # Thin FastAPI wrappers (one per repo)
│   ├── kgbuilder_api/
│   │   ├── Dockerfile
│   │   ├── main.py                 # FastAPI app
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── build.py            # KG build endpoints
│   │   │   ├── validate.py         # Validation endpoints
│   │   │   ├── export.py           # Export endpoints
│   │   │   └── hitl.py             # HITL feedback endpoints
│   │   └── requirements.txt
│   │
│   ├── ontology_api/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── extend.py           # Ontology extension endpoints
│   │   │   ├── browse.py           # Ontology browsing
│   │   │   └── validate.py         # SHACL shape validation
│   │   └── requirements.txt
│   │
│   ├── graphqa_api/
│   │   ├── Dockerfile
│   │   ├── main.py                 # Wraps existing FastAPI server.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py             # Streaming chat (SSE)
│   │   │   ├── explorer.py         # KG/ontology explorer
│   │   │   └── hitl.py             # Feedback submission
│   │   └── requirements.txt
│   │
│   └── shared/                     # Shared Pydantic schemas
│       ├── __init__.py
│       ├── schemas.py              # Cross-service request/response models
│       └── client.py               # HTTP client helpers for inter-service calls
│
├── frontend/                       # Streamlit UI (optional)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   └── pages/
│       ├── 1_Build_KG.py
│       ├── 2_QA_Chat.py
│       ├── 3_Ontology.py
│       └── 4_Review.py
│
├── data/                           # Shared persistent data
│   ├── neo4j/
│   ├── qdrant/
│   ├── fuseki/
│   ├── ontology/
│   └── shared/                     # Inter-service exchange (fallback)
│       └── change_requests/
│
└── scripts/
    ├── bootstrap.sh                # Clone submodules, create .env, pull images
    ├── seed_ontology.sh            # Load initial ontology into Fuseki
    └── health_check.sh             # Verify all services are up
```

---

## 3. Service Architecture

```
                    ┌───────────────────────────────────────────┐
                    │            KGPlatform Network              │
                    │                                           │
  ┌─────────────┐  │  ┌──────────────┐  ┌──────────────────┐  │
  │  Streamlit   │──┼─►│ kgbuilder-api│  │  graphqa-api     │  │
  │  Frontend    │  │  │  :8001       │  │  :8002           │  │
  │  :8501       │──┼─►│              │  │  (existing FastAPI│  │
  │              │──┼─►│              │  │   + new routes)  │  │
  └─────────────┘  │  └──────┬───────┘  └────────┬─────────┘  │
                    │         │                    │            │
                    │         │  ┌─────────────────┘            │
                    │         │  │                              │
                    │         ▼  ▼                              │
                    │  ┌──────────────┐                         │
                    │  │ ontology-api │                         │
                    │  │  :8003       │                         │
                    │  └──────┬───────┘                         │
                    │         │                                 │
                    │  ═══════╪═════════════════════════════    │
                    │  Infrastructure (shared)                  │
                    │         │                                 │
                    │  ┌──────┴───────┐  ┌──────────────────┐  │
                    │  │   Neo4j      │  │     Qdrant       │  │
                    │  │  :7474/:7687 │  │     :6333        │  │
                    │  └──────────────┘  └──────────────────┘  │
                    │                                           │
                    │  ┌──────────────┐  ┌──────────────────┐  │
                    │  │   Fuseki     │  │     Ollama       │  │
                    │  │   :3030      │  │ :11434 (shared)  │  │
                    │  └──────────────┘  │ :11435 (kgb)     │  │
                    │                    │ :11436 (qa)       │  │
                    │                    │ :11437 (onto)     │  │
                    │                    └──────────────────┘  │
                    └───────────────────────────────────────────┘
```

---

## 4. Port Allocation

### Application Services

| Service | Internal Port | External Port | Description |
|---------|--------------|---------------|-------------|
| `kgbuilder-api` | 8001 | 8001 | KG construction API |
| `graphqa-api` | 8002 | 8002 | QA / chat API |
| `ontology-api` | 8003 | 8003 | Ontology extension API |
| `frontend` | 8501 | 8501 | Streamlit UI |

### Infrastructure (shared)

| Service | Internal Port | External Port | Description |
|---------|--------------|---------------|-------------|
| `neo4j` (HTTP) | 7474 | 7474 | Neo4j browser |
| `neo4j` (Bolt) | 7687 | 7687 | Neo4j driver |
| `qdrant` | 6333 | 6333 | Vector store |
| `fuseki` | 3030 | 3030 | SPARQL endpoint |

### Ollama Instances (one per repo — each can load different models)

| Service | Internal Port | External Port | For |
|---------|--------------|---------------|-----|
| `ollama-shared` | 11434 | 11434 | Shared / default |
| `ollama-kgbuilder` | 11434 | 11435 | KGBuilder (extraction models) |
| `ollama-graphqa` | 11434 | 11436 | GraphQA (reasoning models) |
| `ollama-ontology` | 11434 | 11437 | OntologyExtender |

> Each Ollama container listens on `11434` internally. The different external 
> ports (`11435–11437`) are only relevant for host access / debugging.  
> Services connect internally via container name: `http://ollama-kgbuilder:11434`.

### Standalone mode ports (when repos run independently)

Each repo's own `docker-compose.yml` keeps its Ollama on its designated port:

| Repo | Standalone Ollama External Port |
|------|-------------------------------|
| KnowledgeGraphBuilder | 11435 |
| GraphQAAgent | 11436 |
| OntologyExtender | 11437 |

---

## 5. Docker Compose

### `docker-compose.yml` (full platform)

```yaml
version: "3.8"

services:
  # ============================================================
  # APPLICATION SERVICES
  # ============================================================

  kgbuilder-api:
    build:
      context: .
      dockerfile: services/kgbuilder_api/Dockerfile
    container_name: kgbuilder-api
    restart: unless-stopped
    ports:
      - "8001:8001"
    volumes:
      - ./repos/KnowledgeGraphBuilder:/app/repo
      - ./data:/app/data
      - ./data/shared:/app/shared
    env_file: .env
    environment:
      - SERVICE_NAME=kgbuilder
      - UVICORN_PORT=8001
      - OLLAMA_URL=http://ollama-kgbuilder:11434
      - NEO4J_URI=bolt://neo4j:7687
      - QDRANT_URL=http://qdrant:6333
      - FUSEKI_URL=http://fuseki:3030
      - GRAPHQA_API_URL=http://graphqa-api:8002
      - ONTOLOGY_API_URL=http://ontology-api:8003
    depends_on:
      - neo4j
      - qdrant
      - fuseki
      - ollama-kgbuilder
    networks:
      - kgplatform

  graphqa-api:
    build:
      context: .
      dockerfile: services/graphqa_api/Dockerfile
    container_name: graphqa-api
    restart: unless-stopped
    ports:
      - "8002:8002"
    volumes:
      - ./repos/GraphQAAgent:/app/repo
      - ./data:/app/data
    env_file: .env
    environment:
      - SERVICE_NAME=graphqa
      - UVICORN_PORT=8002
      - OLLAMA_URL=http://ollama-graphqa:11434
      - NEO4J_URI=bolt://neo4j:7687
      - QDRANT_URL=http://qdrant:6333
      - FUSEKI_URL=http://fuseki:3030
      - KGBUILDER_API_URL=http://kgbuilder-api:8001
    depends_on:
      - neo4j
      - qdrant
      - fuseki
      - ollama-graphqa
    networks:
      - kgplatform

  ontology-api:
    build:
      context: .
      dockerfile: services/ontology_api/Dockerfile
    container_name: ontology-api
    restart: unless-stopped
    ports:
      - "8003:8003"
    volumes:
      - ./repos/OntologyExtender:/app/repo
      - ./data:/app/data
    env_file: .env
    environment:
      - SERVICE_NAME=ontology
      - UVICORN_PORT=8003
      - OLLAMA_URL=http://ollama-ontology:11434
      - FUSEKI_URL=http://fuseki:3030
      - KGBUILDER_API_URL=http://kgbuilder-api:8001
    depends_on:
      - fuseki
      - ollama-ontology
    networks:
      - kgplatform

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: kgplatform-frontend
    restart: unless-stopped
    ports:
      - "8501:8501"
    environment:
      - KGBUILDER_API_URL=http://kgbuilder-api:8001
      - GRAPHQA_API_URL=http://graphqa-api:8002
      - ONTOLOGY_API_URL=http://ontology-api:8003
    depends_on:
      - kgbuilder-api
      - graphqa-api
      - ontology-api
    networks:
      - kgplatform

  # ============================================================
  # INFRASTRUCTURE — shared across all services
  # ============================================================

  neo4j:
    image: neo4j:5.26.0
    container_name: kgplatform-neo4j
    restart: unless-stopped
    environment:
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
      - NEO4J_AUTH=${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:-changeme}
      - NEO4J_PLUGINS=["apoc", "n10s"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,n10s.*
      - NEO4J_dbms_security_procedures_allowlist=apoc.*,n10s.*
    volumes:
      - ./data/neo4j:/data
      - neo4j-plugins:/plugins
    ports:
      - "7474:7474"
      - "7687:7687"
    networks:
      - kgplatform

  qdrant:
    image: qdrant/qdrant:latest
    container_name: kgplatform-qdrant
    restart: unless-stopped
    volumes:
      - ./data/qdrant:/qdrant/storage
    ports:
      - "6333:6333"
    networks:
      - kgplatform

  fuseki:
    image: stain/jena-fuseki:latest
    container_name: kgplatform-fuseki
    restart: unless-stopped
    ports:
      - "3030:3030"
    volumes:
      - ./data/fuseki:/fuseki
    environment:
      - ADMIN_PASSWORD=${FUSEKI_ADMIN_PASSWORD:-admin}
    networks:
      - kgplatform

  # ============================================================
  # OLLAMA — one instance per repo (different models / configs)
  # ============================================================

  ollama-kgbuilder:
    image: ollama/ollama:0.14.3
    container_name: ollama-kgbuilder
    restart: unless-stopped
    ports:
      - "11435:11434"
    volumes:
      - ollama-kgbuilder-data:/root/.ollama
    environment:
      - OLLAMA_ALLOW_DOWNLOADS=true
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    networks:
      - kgplatform

  ollama-graphqa:
    image: ollama/ollama:0.14.3
    container_name: ollama-graphqa
    restart: unless-stopped
    ports:
      - "11436:11434"
    volumes:
      - ollama-graphqa-data:/root/.ollama
    environment:
      - OLLAMA_ALLOW_DOWNLOADS=true
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    networks:
      - kgplatform

  ollama-ontology:
    image: ollama/ollama:0.14.3
    container_name: ollama-ontology
    restart: unless-stopped
    ports:
      - "11437:11434"
    volumes:
      - ollama-ontology-data:/root/.ollama
    environment:
      - OLLAMA_ALLOW_DOWNLOADS=true
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    networks:
      - kgplatform

volumes:
  neo4j-plugins:
  ollama-kgbuilder-data:
  ollama-graphqa-data:
  ollama-ontology-data:

networks:
  kgplatform:
    driver: bridge
```

---

## 6. FastAPI Service: KGBuilder

### `services/kgbuilder_api/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install the repo's own dependencies
COPY repos/KnowledgeGraphBuilder/requirements.txt /tmp/repo-requirements.txt
RUN pip install --no-cache-dir -r /tmp/repo-requirements.txt

# Install FastAPI wrapper dependencies
COPY services/kgbuilder_api/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

# Install kgbuilder package
COPY repos/KnowledgeGraphBuilder/ /app/repo/
RUN pip install --no-cache-dir -e /app/repo

# Copy service code
COPY services/kgbuilder_api/ /app/service/
COPY services/shared/ /app/service/shared/

WORKDIR /app/service

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### `services/kgbuilder_api/requirements.txt`

```
fastapi>=0.115
uvicorn[standard]>=0.34
httpx>=0.25
```

### `services/kgbuilder_api/main.py`

```python
"""KGBuilder FastAPI service — wraps the KG construction pipeline."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.build import router as build_router
from routes.validate import router as validate_router
from routes.export import router as export_router
from routes.hitl import router as hitl_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: verify connections to Neo4j, Qdrant, Fuseki
    # (lazy init — services may still be starting)
    yield
    # Shutdown: cleanup


app = FastAPI(
    title="KGBuilder API",
    description="Ontology-driven Knowledge Graph construction service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build_router, prefix="/api/v1", tags=["build"])
app.include_router(validate_router, prefix="/api/v1", tags=["validate"])
app.include_router(export_router, prefix="/api/v1", tags=["export"])
app.include_router(hitl_router, prefix="/api/v1/hitl", tags=["hitl"])


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "kgbuilder"}
```

### `services/kgbuilder_api/routes/build.py`

```python
"""KG build pipeline endpoints."""

from __future__ import annotations

import uuid
from enum import Enum

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# In-memory job tracker (replace with Redis/DB for production)
_jobs: dict[str, dict] = {}


class BuildStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BuildRequest(BaseModel):
    """Request to trigger a KG build pipeline run."""

    ontology_path: str = Field(
        default="data/ontology/plan-ontology-v1.0.owl",
        description="Path to OWL ontology file",
    )
    document_dir: str = Field(
        default="data/documents",
        description="Directory containing input documents",
    )
    max_iterations: int = Field(default=5, ge=1, le=50)
    questions_per_class: int = Field(default=3, ge=1, le=20)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    model: str = Field(default="qwen3:8b")


class BuildResponse(BaseModel):
    job_id: str
    status: BuildStatus
    message: str


class JobStatus(BaseModel):
    job_id: str
    status: BuildStatus
    progress: float = 0.0
    entities_count: int = 0
    relations_count: int = 0
    current_iteration: int = 0
    error: str | None = None


@router.post("/build", response_model=BuildResponse)
async def start_build(
    request: BuildRequest,
    background_tasks: BackgroundTasks,
) -> BuildResponse:
    """Start a KG build pipeline run (async background job)."""
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "status": BuildStatus.PENDING,
        "progress": 0.0,
        "entities_count": 0,
        "relations_count": 0,
        "current_iteration": 0,
        "error": None,
    }

    background_tasks.add_task(_run_build_pipeline, job_id, request)

    return BuildResponse(
        job_id=job_id,
        status=BuildStatus.PENDING,
        message="Build pipeline started",
    )


@router.get("/build/{job_id}", response_model=JobStatus)
async def get_build_status(job_id: str) -> JobStatus:
    """Check status of a build job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobStatus(job_id=job_id, **_jobs[job_id])


async def _run_build_pipeline(job_id: str, request: BuildRequest) -> None:
    """Execute the build pipeline in the background.

    This imports and calls the actual kgbuilder pipeline code.
    """
    _jobs[job_id]["status"] = BuildStatus.RUNNING
    try:
        # Import here to avoid startup-time dependency issues
        from kgbuilder.pipeline.orchestrator import Orchestrator

        # TODO: wire up actual orchestrator with request params
        # orchestrator = Orchestrator(config=...)
        # result = orchestrator.run()

        _jobs[job_id]["status"] = BuildStatus.COMPLETED
        _jobs[job_id]["progress"] = 1.0
    except Exception as e:
        _jobs[job_id]["status"] = BuildStatus.FAILED
        _jobs[job_id]["error"] = str(e)
```

### `services/kgbuilder_api/routes/validate.py`

```python
"""Validation endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ValidationRequest(BaseModel):
    checkpoint_path: str | None = None
    run_shacl: bool = True
    run_rules: bool = True
    run_consistency: bool = True


class ValidationResponse(BaseModel):
    passed: bool
    total_checks: int
    pass_rate: float
    violations: list[dict]


@router.post("/validate", response_model=ValidationResponse)
async def validate_kg(request: ValidationRequest) -> ValidationResponse:
    """Run SHACL + semantic rule validation on the current KG."""
    # TODO: import and run kgbuilder.validation pipeline
    return ValidationResponse(
        passed=True,
        total_checks=0,
        pass_rate=1.0,
        violations=[],
    )
```

### `services/kgbuilder_api/routes/export.py`

```python
"""KG export endpoints."""

from __future__ import annotations

from enum import Enum

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter()


class ExportFormat(str, Enum):
    JSON_LD = "json-ld"
    TURTLE = "turtle"
    CYPHER = "cypher"
    GRAPHML = "graphml"
    KGBUILDER_JSON = "kgbuilder-json"


class ExportRequest(BaseModel):
    format: ExportFormat = ExportFormat.KGBUILDER_JSON
    include_metadata: bool = True
    min_confidence: float = 0.0


@router.post("/export")
async def export_kg(request: ExportRequest) -> Response:
    """Export the KG in the requested format."""
    # TODO: import and run kgbuilder.storage.export
    return Response(
        content="{}",
        media_type="application/json",
    )
```

### `services/kgbuilder_api/routes/hitl.py`

```python
"""HITL (Human-in-the-Loop) feedback endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class GapReportResponse(BaseModel):
    untyped_entities: list[str]
    failed_queries: list[str]
    suggested_new_classes: list[str]
    suggested_new_relations: list[str]
    coverage_score: float
    low_confidence_answers: list[dict[str, str]]


class FeedbackRequest(BaseModel):
    """Feedback from an expert or from GraphQAAgent."""

    review_item_id: str
    reviewer_id: str
    decision: str = Field(description="accepted | rejected | modified | needs_discussion")
    rationale: str
    suggested_changes: dict[str, str] = Field(default_factory=dict)
    new_competency_questions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FeedbackResponse(BaseModel):
    status: str
    routed_to: list[str]


class GapDetectRequest(BaseModel):
    """Trigger gap detection from QA feedback."""

    qa_results: list[dict[str, str | float]]


@router.get("/gaps", response_model=GapReportResponse)
async def get_gaps() -> GapReportResponse:
    """Get the latest gap report."""
    # TODO: import GapDetector, run against current KG
    return GapReportResponse(
        untyped_entities=[],
        failed_queries=[],
        suggested_new_classes=[],
        suggested_new_relations=[],
        coverage_score=1.0,
        low_confidence_answers=[],
    )


@router.post("/gaps/detect", response_model=GapReportResponse)
async def detect_gaps(request: GapDetectRequest) -> GapReportResponse:
    """Run gap detection from QA results (called by GraphQAAgent)."""
    from kgbuilder.hitl.config import GapDetectionConfig
    from kgbuilder.hitl.gap_detector import GapDetector

    detector = GapDetector(GapDetectionConfig())
    report = detector.detect_from_qa_feedback(request.qa_results)

    return GapReportResponse(
        untyped_entities=report.untyped_entities,
        failed_queries=report.failed_queries,
        suggested_new_classes=report.suggested_new_classes,
        suggested_new_relations=report.suggested_new_relations,
        coverage_score=report.coverage_score,
        low_confidence_answers=report.low_confidence_answers,
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Submit expert feedback — routes to OntologyExtender or KGBuilder."""
    # TODO: import FeedbackIngester, process and route
    return FeedbackResponse(
        status="accepted",
        routed_to=["kg_builder"],
    )
```

---

## 7. FastAPI Service: OntologyExtender

### `services/ontology_api/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git \
    && rm -rf /var/lib/apt/lists/*

# Install OntologyExtender dependencies
COPY repos/OntologyExtender/requirements.txt /tmp/repo-requirements.txt
RUN pip install --no-cache-dir -r /tmp/repo-requirements.txt || true

# Install FastAPI wrapper
COPY services/ontology_api/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

# Install OntologyExtender
COPY repos/OntologyExtender/ /app/repo/
RUN pip install --no-cache-dir -e /app/repo || true

COPY services/ontology_api/ /app/service/
COPY services/shared/ /app/service/shared/

WORKDIR /app/service

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
```

### `services/ontology_api/requirements.txt`

```
fastapi>=0.115
uvicorn[standard]>=0.34
httpx>=0.25
rdflib>=7.0
pyshacl>=0.25.0
```

### `services/ontology_api/main.py`

```python
"""OntologyExtender FastAPI service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.extend import router as extend_router
from routes.browse import router as browse_router
from routes.validate import router as validate_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="OntologyExtender API",
    description="Human-in-the-loop ontology extension service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extend_router, prefix="/api/v1", tags=["extend"])
app.include_router(browse_router, prefix="/api/v1/ontology", tags=["browse"])
app.include_router(validate_router, prefix="/api/v1", tags=["validate"])


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ontology-extender"}
```

### `services/ontology_api/routes/extend.py`

```python
"""Ontology extension endpoints — process TBox change requests."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class TBoxChangeRequest(BaseModel):
    """Request from KGBuilder's HITL module to extend the ontology."""

    change_type: str = Field(
        description="tbox_new_class | tbox_modify_class | tbox_hierarchy_fix | tbox_property_fix"
    )
    review_item_id: str
    reviewer_id: str
    rationale: str
    suggested_changes: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class TBoxChangeResponse(BaseModel):
    status: str
    change_id: str
    changes_applied: list[str]
    new_ontology_version: str | None = None


@router.post("/extend", response_model=TBoxChangeResponse)
async def extend_ontology(request: TBoxChangeRequest) -> TBoxChangeResponse:
    """Apply a TBox change (new class, hierarchy fix, etc.)."""
    # TODO: import OntologyExtender logic
    return TBoxChangeResponse(
        status="accepted",
        change_id=request.review_item_id,
        changes_applied=[request.change_type],
    )


class BulkExtendRequest(BaseModel):
    changes: list[TBoxChangeRequest]


@router.post("/extend/bulk", response_model=list[TBoxChangeResponse])
async def extend_ontology_bulk(request: BulkExtendRequest) -> list[TBoxChangeResponse]:
    """Apply multiple TBox changes in batch."""
    results = []
    for change in request.changes:
        results.append(TBoxChangeResponse(
            status="accepted",
            change_id=change.review_item_id,
            changes_applied=[change.change_type],
        ))
    return results
```

### `services/ontology_api/routes/browse.py`

```python
"""Ontology browsing endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class OntologyClass(BaseModel):
    uri: str
    label: str
    description: str
    parent_uri: str | None = None
    properties: list[dict[str, str]]
    examples: list[str] = []


class OntologyRelation(BaseModel):
    uri: str
    label: str
    description: str
    domain: list[str]
    range: list[str]


class OntologySummary(BaseModel):
    classes: list[OntologyClass]
    relations: list[OntologyRelation]
    hierarchy: list[dict[str, str]]
    class_count: int
    relation_count: int


@router.get("/summary", response_model=OntologySummary)
async def get_ontology_summary() -> OntologySummary:
    """Get full ontology summary (classes, relations, hierarchy)."""
    # TODO: query Fuseki or parse OWL file
    return OntologySummary(
        classes=[],
        relations=[],
        hierarchy=[],
        class_count=0,
        relation_count=0,
    )


@router.get("/classes", response_model=list[OntologyClass])
async def get_classes() -> list[OntologyClass]:
    """List all ontology classes."""
    return []


@router.get("/relations", response_model=list[OntologyRelation])
async def get_relations() -> list[OntologyRelation]:
    """List all ontology relations."""
    return []
```

### `services/ontology_api/routes/validate.py`

```python
"""SHACL validation endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SHACLValidationRequest(BaseModel):
    shapes_path: str | None = None
    data_graph_path: str | None = None


class SHACLViolation(BaseModel):
    focus_node: str
    path: str
    message: str
    severity: str


class SHACLValidationResponse(BaseModel):
    conforms: bool
    violations: list[SHACLViolation]
    total_shapes: int


@router.post("/validate/shacl", response_model=SHACLValidationResponse)
async def validate_shacl(request: SHACLValidationRequest) -> SHACLValidationResponse:
    """Validate an RDF graph against SHACL shapes."""
    # TODO: use pyshacl
    return SHACLValidationResponse(
        conforms=True,
        violations=[],
        total_shapes=0,
    )
```

---

## 8. FastAPI Service: GraphQAAgent

GraphQAAgent already has a working FastAPI server at `src/kgrag/api/server.py`. 
The wrapper adds new endpoints and delegates to the existing server.

### `services/graphqa_api/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git \
    && rm -rf /var/lib/apt/lists/*

# Install GraphQAAgent dependencies
COPY repos/GraphQAAgent/requirements.txt /tmp/repo-requirements.txt
RUN pip install --no-cache-dir -r /tmp/repo-requirements.txt

# Install FastAPI wrapper extras
COPY services/graphqa_api/requirements.txt /tmp/svc-requirements.txt
RUN pip install --no-cache-dir -r /tmp/svc-requirements.txt

# Install GraphQAAgent
COPY repos/GraphQAAgent/ /app/repo/
RUN pip install --no-cache-dir -e /app/repo

COPY services/graphqa_api/ /app/service/
COPY services/shared/ /app/service/shared/

WORKDIR /app/service

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
```

### `services/graphqa_api/requirements.txt`

```
fastapi>=0.115
uvicorn[standard]>=0.34
httpx>=0.25
sse-starlette>=2.0
```

### `services/graphqa_api/main.py`

```python
"""GraphQAAgent FastAPI service — extends existing server with new routes."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the existing GraphQAAgent routes
# from kgrag.api.routes import router as existing_router

from routes.chat import router as chat_router
from routes.explorer import router as explorer_router
from routes.hitl import router as hitl_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: initialize KGRAG orchestrator
    yield


app = FastAPI(
    title="GraphQAAgent API",
    description="Ontology-informed GraphRAG QA with streaming chat",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount existing routes (from the GraphQAAgent repo)
# app.include_router(existing_router, prefix="/api/v1", tags=["qa"])

# New routes
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(explorer_router, prefix="/api/v1", tags=["explorer"])
app.include_router(hitl_router, prefix="/api/v1/hitl", tags=["hitl"])


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "graphqa"}
```

### `services/graphqa_api/routes/chat.py`

```python
"""Streaming chat endpoint (SSE)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()

# Simple in-memory session store
_sessions: dict[str, list[dict]] = {}


class ChatMessage(BaseModel):
    role: str = Field(description="user | assistant | system")
    content: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    strategy: str = "auto"
    language: str = "de"
    stream: bool = True


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    confidence: float
    reasoning_chain: list[str]
    provenance: list[dict]


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse | ChatResponse:
    """Send a message and get a response (streaming or blocking)."""
    session_id = request.session_id or uuid.uuid4().hex[:12]

    if session_id not in _sessions:
        _sessions[session_id] = []

    _sessions[session_id].append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat(),
    })

    if request.stream:
        return StreamingResponse(
            _stream_response(session_id, request.message),
            media_type="text/event-stream",
        )

    # Non-streaming: call orchestrator directly
    # TODO: import and call KGRAG orchestrator
    answer = f"[Placeholder] Answer to: {request.message}"

    _sessions[session_id].append({
        "role": "assistant",
        "content": answer,
        "timestamp": datetime.now().isoformat(),
    })

    return ChatResponse(
        session_id=session_id,
        answer=answer,
        confidence=0.0,
        reasoning_chain=[],
        provenance=[],
    )


async def _stream_response(session_id: str, question: str):
    """SSE stream generator."""
    # TODO: wire to actual KGRAG orchestrator streaming
    tokens = f"[Placeholder] Streaming answer to: {question}".split()
    for token in tokens:
        data = json.dumps({"token": token + " ", "done": False})
        yield f"data: {data}\n\n"
        await asyncio.sleep(0.05)

    yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"


@router.get("/chat/{session_id}/history")
async def get_history(session_id: str) -> list[dict]:
    """Get chat history for a session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return _sessions[session_id]
```

### `services/graphqa_api/routes/explorer.py`

```python
"""KG and ontology explorer endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class EntityInfo(BaseModel):
    id: str
    label: str
    entity_type: str
    confidence: float
    description: str
    neighbors: list[dict]


class SubgraphResponse(BaseModel):
    nodes: list[dict]
    edges: list[dict]


@router.get("/kg/entity/{entity_id}", response_model=EntityInfo)
async def get_entity(entity_id: str) -> EntityInfo:
    """Get entity details with neighbors."""
    # TODO: query Neo4j
    return EntityInfo(
        id=entity_id,
        label="",
        entity_type="",
        confidence=0.0,
        description="",
        neighbors=[],
    )


@router.get("/kg/subgraph", response_model=SubgraphResponse)
async def get_subgraph(
    center_id: str,
    depth: int = 1,
) -> SubgraphResponse:
    """Get subgraph around an entity."""
    # TODO: query Neo4j
    return SubgraphResponse(nodes=[], edges=[])


@router.get("/kg/search")
async def search_entities(query: str, limit: int = 10) -> list[dict]:
    """Search entities by label (fuzzy)."""
    # TODO: query Qdrant or Neo4j full-text index
    return []
```

### `services/graphqa_api/routes/hitl.py`

```python
"""HITL integration — report low-confidence answers to KGBuilder."""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

KGBUILDER_API_URL = os.getenv("KGBUILDER_API_URL", "http://kgbuilder-api:8001")


class LowConfidenceReport(BaseModel):
    """Batch of QA results to report for gap detection."""

    qa_results: list[dict[str, str | float]]


class ReportResponse(BaseModel):
    status: str
    gaps_detected: int
    suggested_classes: list[str]


@router.post("/report-low-confidence", response_model=ReportResponse)
async def report_low_confidence(request: LowConfidenceReport) -> ReportResponse:
    """Report low-confidence QA answers to KGBuilder for gap detection.

    This triggers the HITL feedback loop:
    GraphQAAgent → KGBuilder (gap detection) → OntologyExtender (if needed)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{KGBUILDER_API_URL}/api/v1/hitl/gaps/detect",
                json={"qa_results": request.qa_results},
            )
            resp.raise_for_status()
            data = resp.json()
            return ReportResponse(
                status="reported",
                gaps_detected=len(data.get("suggested_new_classes", [])),
                suggested_classes=data.get("suggested_new_classes", []),
            )
        except httpx.HTTPError:
            return ReportResponse(
                status="kgbuilder_unreachable",
                gaps_detected=0,
                suggested_classes=[],
            )
```

---

## 9. Inter-Service Communication

### Communication Patterns

| From → To | Method | Trigger |
|-----------|--------|---------|
| GraphQA → KGBuilder | `POST /api/v1/hitl/gaps/detect` | Low-confidence QA answer |
| KGBuilder → OntologyExtender | `POST /api/v1/extend` | Gap report with TBox changes |
| KGBuilder → GraphQA | `POST /api/v1/chat` (CQ test) | New competency question |
| OntologyExtender → KGBuilder | `POST /api/v1/build` (re-extract) | Ontology updated |
| Frontend → All | Various `GET`/`POST` | User interaction |

### Shared HTTP Client

```python
# services/shared/client.py
"""HTTP client helpers for inter-service communication."""

from __future__ import annotations

import os

import httpx


def get_service_url(service: str) -> str:
    """Resolve service URL from environment."""
    urls = {
        "kgbuilder": os.getenv("KGBUILDER_API_URL", "http://kgbuilder-api:8001"),
        "graphqa": os.getenv("GRAPHQA_API_URL", "http://graphqa-api:8002"),
        "ontology": os.getenv("ONTOLOGY_API_URL", "http://ontology-api:8003"),
    }
    return urls.get(service, "")


async def call_service(
    service: str,
    method: str,
    path: str,
    json: dict | None = None,
    timeout: float = 30.0,
) -> dict:
    """Make an HTTP call to a sibling service."""
    base_url = get_service_url(service)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(method, f"{base_url}{path}", json=json)
        resp.raise_for_status()
        return resp.json()
```

---

## 10. Shared Schemas

```python
# services/shared/schemas.py
"""Cross-service Pydantic models — canonical data formats."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Competency Question (shared format per INTERFACE_CONTRACT)
# ------------------------------------------------------------------

class QAQuestion(BaseModel):
    id: str
    question: str
    expected_answers: list[str] = Field(default_factory=list)
    query_type: str = "entity"
    difficulty: int = Field(default=3, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ------------------------------------------------------------------
# Gap Report (KGBuilder → OntologyExtender)
# ------------------------------------------------------------------

class GapReport(BaseModel):
    untyped_entities: list[str] = Field(default_factory=list)
    failed_queries: list[str] = Field(default_factory=list)
    low_confidence_answers: list[dict[str, str]] = Field(default_factory=list)
    suggested_new_classes: list[str] = Field(default_factory=list)
    suggested_new_relations: list[str] = Field(default_factory=list)
    coverage_score: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)


# ------------------------------------------------------------------
# TBox Change Request (KGBuilder → OntologyExtender)
# ------------------------------------------------------------------

class TBoxChangeType(str, Enum):
    NEW_CLASS = "tbox_new_class"
    MODIFY_CLASS = "tbox_modify_class"
    HIERARCHY_FIX = "tbox_hierarchy_fix"
    PROPERTY_FIX = "tbox_property_fix"


class TBoxChangeRequest(BaseModel):
    change_type: TBoxChangeType
    review_item_id: str
    reviewer_id: str
    rationale: str
    suggested_changes: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# ------------------------------------------------------------------
# Entity / Relation (shared view for explorer)
# ------------------------------------------------------------------

class EntitySummary(BaseModel):
    id: str
    label: str
    entity_type: str
    confidence: float
    description: str = ""


class RelationSummary(BaseModel):
    source_id: str
    target_id: str
    predicate: str
    confidence: float
```

---

## 11. Frontend (Streamlit)

### `frontend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### `frontend/requirements.txt`

```
streamlit>=1.41
httpx>=0.25
pyvis>=0.3
```

### `frontend/app.py`

```python
"""KGPlatform — unified frontend."""

import streamlit as st

st.set_page_config(
    page_title="KGPlatform",
    page_icon="🔗",
    layout="wide",
)

st.title("KGPlatform")
st.markdown("""
Unified interface for the Knowledge Graph research ecosystem:
- **Build KG** — Trigger and monitor KG construction
- **QA Chat** — Ask questions against the knowledge graph
- **Ontology** — Browse and extend the ontology
- **Review** — HITL expert review workflow
""")

# Health check all services
import httpx

services = {
    "KGBuilder": "http://kgbuilder-api:8001/api/v1/health",
    "GraphQA": "http://graphqa-api:8002/api/v1/health",
    "Ontology": "http://ontology-api:8003/api/v1/health",
}

cols = st.columns(len(services))
for col, (name, url) in zip(cols, services.items()):
    try:
        r = httpx.get(url, timeout=3)
        col.metric(name, "✅ Online")
    except Exception:
        col.metric(name, "❌ Offline")
```

---

## 12. Setup & Bootstrap Script

### `scripts/bootstrap.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== KGPlatform Bootstrap ==="

# 1. Initialize and clone submodules
echo "[1/5] Initializing git submodules..."
git submodule update --init --recursive

# 2. Create .env from example
if [[ ! -f .env ]]; then
    echo "[2/5] Creating .env from .env.example..."
    cp .env.example .env
    echo "  → Edit .env with your settings before starting"
else
    echo "[2/5] .env already exists, skipping"
fi

# 3. Create data directories
echo "[3/5] Creating data directories..."
mkdir -p data/{neo4j,qdrant,fuseki,ontology,shared/change_requests}

# 4. Pull Docker images
echo "[4/5] Pulling Docker images..."
docker compose pull neo4j qdrant fuseki ollama-kgbuilder ollama-graphqa ollama-ontology

# 5. Build service images
echo "[5/5] Building service images..."
docker compose build kgbuilder-api graphqa-api ontology-api frontend

echo ""
echo "=== Bootstrap complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env if needed"
echo "  2. docker compose up -d                    # start everything"
echo "  3. docker compose logs -f                  # watch logs"
echo "  4. Open http://localhost:8501               # Streamlit frontend"
echo "  5. API docs:"
echo "     - KGBuilder:   http://localhost:8001/docs"
echo "     - GraphQA:     http://localhost:8002/docs"
echo "     - Ontology:    http://localhost:8003/docs"
```

### `Makefile`

```makefile
.PHONY: bootstrap up down logs health build test

bootstrap:
	bash scripts/bootstrap.sh

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

health:
	@echo "KGBuilder:  $$(curl -s http://localhost:8001/api/v1/health | python3 -m json.tool 2>/dev/null || echo 'OFFLINE')"
	@echo "GraphQA:    $$(curl -s http://localhost:8002/api/v1/health | python3 -m json.tool 2>/dev/null || echo 'OFFLINE')"
	@echo "Ontology:   $$(curl -s http://localhost:8003/api/v1/health | python3 -m json.tool 2>/dev/null || echo 'OFFLINE')"

build:
	docker compose build

# Run just infrastructure (no app services)
infra:
	docker compose up -d neo4j qdrant fuseki

# Run a specific repo standalone
standalone-kgb:
	cd repos/KnowledgeGraphBuilder && docker compose up -d

standalone-qa:
	cd repos/GraphQAAgent && docker compose up -d

standalone-onto:
	cd repos/OntologyExtender && docker compose up -d
```

---

## 13. Environment Variables

### `.env.example`

```bash
# ============================================================
# KGPlatform Environment Configuration
# ============================================================

# --- Neo4j ---
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme

# --- Fuseki ---
FUSEKI_ADMIN_PASSWORD=admin
FUSEKI_DATASET=kgbuilder

# --- Qdrant ---
QDRANT_COLLECTION=kgbuilder

# --- Ollama Models ---
# Each service can use a different model
KGBUILDER_MODEL=qwen3:8b
GRAPHQA_MODEL=qwen3:8b
ONTOLOGY_MODEL=qwen3:8b
EMBED_MODEL=qwen3-embedding

# --- Service URLs (auto-resolved in Docker, override for host dev) ---
# KGBUILDER_API_URL=http://localhost:8001
# GRAPHQA_API_URL=http://localhost:8002
# ONTOLOGY_API_URL=http://localhost:8003

# --- Logging ---
LOG_LEVEL=INFO
```

---

## 14. Implementation Order

```
Phase 0: Repository setup                              (~1h)
  ├── Create KGPlatform repo
  ├── Add 3 submodules
  ├── Create directory structure
  ├── Write .env.example, Makefile, bootstrap.sh
  └── Write docker-compose.yml

Phase 1: KGBuilder API                                 (~3h)
  ├── Dockerfile
  ├── main.py + 4 route files
  ├── Wire to actual kgbuilder imports (build, validate, export)
  └── Test endpoints with curl/httpie

Phase 2: OntologyExtender API                          (~3h)
  ├── Dockerfile
  ├── main.py + 3 route files
  ├── Wire to actual ontology extender logic
  └── Test endpoints

Phase 3: GraphQAAgent API wrapper                      (~2h)
  ├── Dockerfile (delegates to existing server.py)
  ├── Add chat streaming + explorer + HITL routes
  └── Test SSE streaming

Phase 4: Inter-service wiring                          (~2h)
  ├── shared/client.py + shared/schemas.py
  ├── GraphQA → KGBuilder gap reporting
  ├── KGBuilder → OntologyExtender TBox routing
  └── Integration test: full HITL round-trip

Phase 5: Streamlit frontend                            (~4h)
  ├── Dashboard with service health
  ├── Build KG page
  ├── Chat page (SSE consumer)
  ├── Ontology browser page
  └── Review workflow page

Phase 6: Standalone compose files (per-repo)           (~1h)
  ├── Update KnowledgeGraphBuilder/docker-compose.yml
  ├── Create GraphQAAgent/docker-compose.yml
  └── Create OntologyExtender/docker-compose.yml
```

**Total estimated effort: ~16 hours**

---

## 15. Standalone Compose Files

Each repo should also work independently. Below are the standalone compose files
that include their own Ollama on the designated port.

### KnowledgeGraphBuilder `docker-compose.yml` (update existing)

```yaml
version: "3.8"

services:
  kgbuilder:
    build: .
    container_name: kgbuilder
    volumes:
      - ./:/app
      - ./data:/app/data
    env_file: .env
    environment:
      - PYTHONUNBUFFERED=1
      - OLLAMA_URL=${OLLAMA_URL:-http://ollama:11434}
      - NEO4J_URI=${NEO4J_URI:-bolt://neo4j:7687}
      - QDRANT_URL=${QDRANT_URL:-http://qdrant:6333}
      - FUSEKI_URL=${FUSEKI_URL:-http://fuseki:3030}
    depends_on: [qdrant, neo4j, fuseki]
    networks: [kgbuilder-net]

  kgbuilder-api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    container_name: kgbuilder-api
    restart: unless-stopped
    ports:
      - "8001:8001"
    volumes:
      - ./:/app/repo
    env_file: .env
    environment:
      - OLLAMA_URL=http://ollama:11434
      - NEO4J_URI=bolt://neo4j:7687
      - QDRANT_URL=http://qdrant:6333
      - FUSEKI_URL=http://fuseki:3030
    depends_on: [qdrant, neo4j, fuseki]
    networks: [kgbuilder-net]

  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    restart: unless-stopped
    volumes: ["./data/qdrant:/qdrant/storage"]
    ports: ["6333:6333"]
    networks: [kgbuilder-net]

  neo4j:
    image: neo4j:5.26.0
    container_name: neo4j
    restart: unless-stopped
    environment:
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
      - NEO4J_AUTH=neo4j/changeme
      - NEO4J_PLUGINS=["apoc", "n10s"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,n10s.*
      - NEO4J_dbms_security_procedures_allowlist=apoc.*,n10s.*
    volumes: ["./data/neo4j:/data"]
    ports: ["7474:7474", "7687:7687"]
    networks: [kgbuilder-net]

  fuseki:
    image: stain/jena-fuseki:latest
    container_name: fuseki
    restart: unless-stopped
    ports: ["3030:3030"]
    volumes: ["./data/fuseki:/fuseki"]
    environment: ["ADMIN_PASSWORD=admin"]
    networks: [kgbuilder-net]

  ollama:
    image: ollama/ollama:0.14.3
    container_name: ollama-kgbuilder-standalone
    restart: unless-stopped
    ports:
      - "11435:11434"
    volumes: ["ollama-data:/root/.ollama"]
    environment: ["OLLAMA_ALLOW_DOWNLOADS=true"]
    networks: [kgbuilder-net]

volumes:
  ollama-data:

networks:
  kgbuilder-net:
    driver: bridge
```

### GraphQAAgent `docker-compose.yml`

```yaml
version: "3.8"

services:
  graphqa-api:
    build: .
    container_name: graphqa-api
    restart: unless-stopped
    ports:
      - "8002:8002"
    volumes:
      - ./:/app
    env_file: .env
    environment:
      - OLLAMA_URL=http://ollama:11434
      - NEO4J_URI=bolt://neo4j:7687
      - QDRANT_URL=http://qdrant:6333
      - FUSEKI_URL=http://fuseki:3030
    depends_on: [neo4j, qdrant, fuseki]
    networks: [graphqa-net]

  neo4j:
    image: neo4j:5.26.0
    container_name: graphqa-neo4j
    restart: unless-stopped
    environment:
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
      - NEO4J_AUTH=neo4j/changeme
      - NEO4J_PLUGINS=["apoc", "n10s"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,n10s.*
    volumes: ["./data/neo4j:/data"]
    ports: ["7474:7474", "7687:7687"]
    networks: [graphqa-net]

  qdrant:
    image: qdrant/qdrant:latest
    container_name: graphqa-qdrant
    restart: unless-stopped
    volumes: ["./data/qdrant:/qdrant/storage"]
    ports: ["6333:6333"]
    networks: [graphqa-net]

  fuseki:
    image: stain/jena-fuseki:latest
    container_name: graphqa-fuseki
    restart: unless-stopped
    ports: ["3030:3030"]
    volumes: ["./data/fuseki:/fuseki"]
    environment: ["ADMIN_PASSWORD=admin"]
    networks: [graphqa-net]

  ollama:
    image: ollama/ollama:0.14.3
    container_name: ollama-graphqa-standalone
    restart: unless-stopped
    ports:
      - "11436:11434"
    volumes: ["ollama-data:/root/.ollama"]
    environment: ["OLLAMA_ALLOW_DOWNLOADS=true"]
    networks: [graphqa-net]

volumes:
  ollama-data:

networks:
  graphqa-net:
    driver: bridge
```

### OntologyExtender `docker-compose.yml`

```yaml
version: "3.8"

services:
  ontology-api:
    build: .
    container_name: ontology-api
    restart: unless-stopped
    ports:
      - "8003:8003"
    volumes:
      - ./:/app
    env_file: .env
    environment:
      - OLLAMA_URL=http://ollama:11434
      - FUSEKI_URL=http://fuseki:3030
    depends_on: [fuseki]
    networks: [ontology-net]

  fuseki:
    image: stain/jena-fuseki:latest
    container_name: ontology-fuseki
    restart: unless-stopped
    ports: ["3030:3030"]
    volumes: ["./data/fuseki:/fuseki"]
    environment: ["ADMIN_PASSWORD=admin"]
    networks: [ontology-net]

  ollama:
    image: ollama/ollama:0.14.3
    container_name: ollama-ontology-standalone
    restart: unless-stopped
    ports:
      - "11437:11434"
    volumes: ["ollama-data:/root/.ollama"]
    environment: ["OLLAMA_ALLOW_DOWNLOADS=true"]
    networks: [ontology-net]

volumes:
  ollama-data:

networks:
  ontology-net:
    driver: bridge
```

---

## Quick Reference: All URLs

| What | URL |
|------|-----|
| KGBuilder API docs | http://localhost:8001/docs |
| GraphQA API docs | http://localhost:8002/docs |
| Ontology API docs | http://localhost:8003/docs |
| Streamlit frontend | http://localhost:8501 |
| Neo4j browser | http://localhost:7474 |
| Qdrant dashboard | http://localhost:6333/dashboard |
| Fuseki admin | http://localhost:3030 |
| Ollama (KGBuilder) | http://localhost:11435 |
| Ollama (GraphQA) | http://localhost:11436 |
| Ollama (Ontology) | http://localhost:11437 |
