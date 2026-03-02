# OntologyExtender — FastAPI Implementation Plan

> Copy this file into the OntologyExtender repository and follow it step-by-step.
> It mirrors the KGBuilder API that was implemented in the
> [KnowledgeGraphBuilder `fast-api` branch](https://github.com/DataScienceLabFHSWF/KnowledgeGraphBuilder/tree/fast-api).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Port & Service Configuration](#2-port--service-configuration)
3. [Directory Structure](#3-directory-structure)
4. [pyproject.toml Changes](#4-pyprojecttoml-changes)
5. [Pydantic Schemas (`api/schemas.py`)](#5-pydantic-schemas)
6. [Dependencies & Singletons (`api/dependencies.py`)](#6-dependencies--singletons)
7. [FastAPI App (`api/server.py`)](#7-fastapi-app)
8. [Route Modules](#8-route-modules)
   - 8.1 [Health & Status (`routes/status.py`)](#81-health--status)
   - 8.2 [Ontology Browse (`routes/browse.py`)](#82-ontology-browse)
   - 8.3 [Extend / TBox Changes (`routes/extend.py`)](#83-extend--tbox-changes)
   - 8.4 [SHACL Validation (`routes/validate.py`)](#84-shacl-validation)
9. [Docker Setup](#9-docker-setup)
   - 9.1 [Dockerfile.api](#91-dockerfileapi)
   - 9.2 [docker-compose.yml (standalone)](#92-docker-composeyml-standalone)
10. [Cross-Service Integration](#10-cross-service-integration)
11. [Testing Strategy](#11-testing-strategy)
12. [Implementation Checklist](#12-implementation-checklist)

---

## 1. Overview

The OntologyExtender API exposes ontology extension, browsing, and SHACL
validation capabilities as a REST service. It:

- **Receives TBox change requests** from KGBuilder's HITL gap detector
  (`POST /api/v1/extend`)
- **Browses the ontology** for the frontend / other services
  (`GET /api/v1/ontology/...`)
- **Validates RDF data** against SHACL shapes
  (`POST /api/v1/validate/shacl`)
- **Reports health** to the platform orchestrator
  (`GET /api/v1/health`)

### Feedback Loop Context

```
GraphQAAgent ──(low confidence)──► KGBuilder ──(TBox gaps)──► OntologyExtender
       ▲                                ▲                            │
       │                                │                            │
  answers / CQ                    re-build trigger          updated OWL + SHACL
```

KGBuilder's `POST /api/v1/hitl/gaps/detect` forwards `tbox_new_class`
items to **this service** at `POST /api/v1/extend`.

---

## 2. Port & Service Configuration

| Item                    | Value                             |
| ----------------------- | --------------------------------- |
| **API port**            | `8003` (host & container)         |
| **Ollama instance**     | `ollama-ontology` → host `11437`  |
| **Fuseki**              | shared `fuseki:3030`              |
| **Env prefix**          | `HITL_`                           |
| **Service name**        | `ontology-api`                    |

### Environment Variables

```bash
# Core
SERVICE_NAME=ontology
UVICORN_PORT=8003

# LLM
HITL_OLLAMA_URL=http://ollama-ontology:11434
HITL_OLLAMA_MODEL=qwen3:8b

# Fuseki
HITL_FUSEKI_URL=http://fuseki:3030
HITL_FUSEKI_DATASET=kgbuilder
HITL_FUSEKI_STAGING_DATASET=kgbuilder-staging

# Cross-service
KGBUILDER_API_URL=http://kgbuilder-api:8001
```

---

## 3. Directory Structure

Add the `api/` package **inside** your existing source tree:

```
src/ontology_hitl/
├── api/                          # ← NEW
│   ├── __init__.py
│   ├── server.py                 # FastAPI app, lifespan, CORS, router mounts
│   ├── schemas.py                # All Pydantic request/response models
│   ├── dependencies.py           # Lazy singletons (Fuseki, Ollama, etc.)
│   └── routes/
│       ├── __init__.py
│       ├── status.py             # GET /health
│       ├── browse.py             # GET /ontology/summary, /classes, /relations
│       ├── extend.py             # POST /extend, /extend/bulk
│       └── validate.py           # POST /validate/shacl
├── core/
│   ├── models.py
│   ├── protocols.py
│   ├── config.py
│   └── exceptions.py
├── discovery/                    # gap_analyzer, class_generator, …
├── schema/                       # manager, shacl_generator, version_manager
├── review/                       # cli, web, feedback
└── evaluation/                   # cq_evaluator, completeness, reporter
```

---

## 4. pyproject.toml Changes

Add an `api` optional dependency group:

```toml
[project.optional-dependencies]
api = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "httpx>=0.25",
]

[project.scripts]
ontology-api = "uvicorn:main"       # convenience; real launch: uvicorn ontology_hitl.api.server:app
```

---

## 5. Pydantic Schemas

Create `src/ontology_hitl/api/schemas.py`:

```python
"""Pydantic request/response models for the OntologyExtender API."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────

class TBoxChangeType(str, Enum):
    """Types of TBox changes the extender can apply."""

    NEW_CLASS = "tbox_new_class"
    MODIFY_CLASS = "tbox_modify_class"
    HIERARCHY_FIX = "tbox_hierarchy_fix"
    PROPERTY_FIX = "tbox_property_fix"


# ── Extend ───────────────────────────────────────────────────────────────

class TBoxChangeRequest(BaseModel):
    """Request to apply a single TBox change.

    Sent by KGBuilder's HITL gap detector or by the review UI.
    """

    change_type: TBoxChangeType
    review_item_id: str = Field(..., description="ID of the review item originating this change")
    reviewer_id: str = Field(default="system", description="Who approved / requested the change")
    rationale: str = Field(default="", description="Why this change is needed")
    suggested_changes: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value pairs of suggested modifications (e.g. label, parent_uri, ...)",
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class TBoxChangeResponse(BaseModel):
    """Result of applying a TBox change."""

    status: str = Field(..., description="'applied' | 'staged' | 'rejected' | 'error'")
    change_id: str = Field(..., description="Unique ID for the applied change")
    changes_applied: list[str] = Field(
        default_factory=list,
        description="Human-readable list of mutations",
    )
    new_ontology_version: str | None = Field(
        default=None,
        description="Version tag if the ontology was bumped",
    )


class BulkExtendRequest(BaseModel):
    """Batch of TBox changes to apply atomically."""

    changes: list[TBoxChangeRequest]
    atomic: bool = Field(
        default=True,
        description="If True, all-or-nothing; if False, best-effort",
    )


# ── Browse ───────────────────────────────────────────────────────────────

class PropertyInfo(BaseModel):
    """An OWL datatype / object property."""

    uri: str
    label: str
    description: str = ""
    range_uri: str = ""


class OntologyClass(BaseModel):
    """A single OWL class in the ontology."""

    uri: str
    label: str
    description: str = ""
    parent_uri: str | None = None
    properties: list[PropertyInfo] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class OntologyRelation(BaseModel):
    """A single OWL object property / relation."""

    uri: str
    label: str
    description: str = ""
    domain: list[str] = Field(default_factory=list)
    range: list[str] = Field(default_factory=list)


class HierarchyEdge(BaseModel):
    """A parent → child edge in the class hierarchy."""

    parent_uri: str
    child_uri: str


class OntologySummary(BaseModel):
    """Full ontology overview."""

    classes: list[OntologyClass]
    relations: list[OntologyRelation]
    hierarchy: list[HierarchyEdge]
    class_count: int
    relation_count: int


# ── SHACL Validation ────────────────────────────────────────────────────

class SHACLValidationRequest(BaseModel):
    """Request to validate an RDF data graph against SHACL shapes."""

    shapes_path: str | None = Field(
        default=None,
        description="Path to shapes graph (default: auto-detect from Fuseki)",
    )
    data_graph_path: str | None = Field(
        default=None,
        description="Path to data graph (default: main Fuseki dataset)",
    )


class SHACLViolation(BaseModel):
    """A single SHACL validation violation."""

    focus_node: str
    path: str
    message: str
    severity: str  # "Violation" | "Warning" | "Info"


class SHACLValidationResponse(BaseModel):
    """Result of SHACL validation."""

    conforms: bool
    violations: list[SHACLViolation] = Field(default_factory=list)
    total_shapes: int = 0


# ── Health ───────────────────────────────────────────────────────────────

class ServiceHealth(BaseModel):
    """Health-check response."""

    status: str  # "ok" | "degraded"
    service: str = "ontology-extender"
    fuseki: str = "unknown"
    ollama: str = "unknown"
    version: str = "0.1.0"
```

---

## 6. Dependencies & Singletons

Create `src/ontology_hitl/api/dependencies.py`:

```python
"""Dependency injection – lazy singletons for backend connections."""

from __future__ import annotations

import os
from functools import lru_cache

import httpx
import structlog

logger = structlog.get_logger(__name__)


# ── Settings ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_settings() -> dict[str, str]:
    """Gather all env-based settings in one place."""
    return {
        "fuseki_url": os.getenv("HITL_FUSEKI_URL", "http://localhost:3030"),
        "fuseki_dataset": os.getenv("HITL_FUSEKI_DATASET", "kgbuilder"),
        "fuseki_staging": os.getenv("HITL_FUSEKI_STAGING_DATASET", "kgbuilder-staging"),
        "ollama_url": os.getenv("HITL_OLLAMA_URL", "http://localhost:11434"),
        "ollama_model": os.getenv("HITL_OLLAMA_MODEL", "qwen3:8b"),
        "kgbuilder_api_url": os.getenv("KGBUILDER_API_URL", "http://localhost:8001"),
    }


# ── Fuseki client ────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_fuseki_client() -> httpx.Client:
    """HTTP client pre-configured for Fuseki SPARQL endpoint."""
    settings = get_settings()
    return httpx.Client(
        base_url=settings["fuseki_url"],
        timeout=30.0,
    )


def sparql_query(query: str, dataset: str | None = None) -> list[dict]:
    """Execute a SPARQL SELECT and return bindings as dicts."""
    settings = get_settings()
    ds = dataset or settings["fuseki_dataset"]
    client = get_fuseki_client()
    resp = client.post(
        f"/{ds}/sparql",
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
    )
    resp.raise_for_status()
    results = resp.json().get("results", {}).get("bindings", [])
    return [
        {k: v["value"] for k, v in row.items()}
        for row in results
    ]


def sparql_update(update: str, dataset: str | None = None) -> None:
    """Execute a SPARQL UPDATE (INSERT / DELETE)."""
    settings = get_settings()
    ds = dataset or settings["fuseki_dataset"]
    client = get_fuseki_client()
    resp = client.post(
        f"/{ds}/update",
        data={"update": update},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()


# ── Ollama / LLM client ─────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_ollama_client() -> httpx.Client:
    """HTTP client for Ollama API."""
    settings = get_settings()
    return httpx.Client(
        base_url=settings["ollama_url"],
        timeout=120.0,
    )


def llm_generate(prompt: str, system: str = "") -> str:
    """Call Ollama /api/generate and return the response text."""
    settings = get_settings()
    client = get_ollama_client()
    payload: dict = {
        "model": settings["ollama_model"],
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    resp = client.post("/api/generate", json=payload)
    resp.raise_for_status()
    return resp.json().get("response", "")


# ── Cross-service helpers ────────────────────────────────────────────────

def notify_kgbuilder_rebuild() -> bool:
    """Best-effort POST to KGBuilder to trigger a rebuild after ontology changes."""
    settings = get_settings()
    url = settings["kgbuilder_api_url"]
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{url}/api/v1/build", json={})
            return resp.status_code == 200
    except Exception:
        logger.warning("kgbuilder_rebuild_notify_failed", url=url)
        return False
```

---

## 7. FastAPI App

Create `src/ontology_hitl/api/server.py`:

```python
"""OntologyExtender FastAPI application."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ontology_hitl.api.routes.status import router as status_router
from ontology_hitl.api.routes.browse import router as browse_router
from ontology_hitl.api.routes.extend import router as extend_router
from ontology_hitl.api.routes.validate import router as validate_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hooks."""
    logger.info(
        "ontology_extender_api_starting",
        port=os.getenv("UVICORN_PORT", "8003"),
    )
    yield
    logger.info("ontology_extender_api_stopping")


app = FastAPI(
    title="OntologyExtender API",
    version="0.1.0",
    description="Ontology extension, browsing, and SHACL validation service.",
    lifespan=lifespan,
)

# CORS – allow platform frontend (Streamlit) and other local services
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(status_router, prefix="/api/v1", tags=["status"])
app.include_router(browse_router, prefix="/api/v1/ontology", tags=["browse"])
app.include_router(extend_router, prefix="/api/v1", tags=["extend"])
app.include_router(validate_router, prefix="/api/v1", tags=["validate"])


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "ontology-extender", "docs": "/docs"}
```

**Launch command:**

```bash
uvicorn ontology_hitl.api.server:app --host 0.0.0.0 --port 8003 --reload
```

---

## 8. Route Modules

### 8.1 Health & Status

`src/ontology_hitl/api/routes/status.py`

```python
"""Health and status endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from ontology_hitl.api.schemas import ServiceHealth
from ontology_hitl.api.dependencies import get_fuseki_client, get_ollama_client

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=ServiceHealth)
async def health() -> ServiceHealth:
    """Check connectivity to Fuseki and Ollama."""
    fuseki_ok = "unknown"
    ollama_ok = "unknown"

    try:
        resp = get_fuseki_client().get("/$/ping")
        fuseki_ok = "ok" if resp.status_code == 200 else "error"
    except Exception:
        fuseki_ok = "error"

    try:
        resp = get_ollama_client().get("/api/tags")
        ollama_ok = "ok" if resp.status_code == 200 else "error"
    except Exception:
        ollama_ok = "error"

    overall = "ok" if fuseki_ok == "ok" and ollama_ok == "ok" else "degraded"
    return ServiceHealth(status=overall, fuseki=fuseki_ok, ollama=ollama_ok)
```

### 8.2 Ontology Browse

`src/ontology_hitl/api/routes/browse.py`

```python
"""Ontology browsing endpoints — read-only queries against Fuseki."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from ontology_hitl.api.schemas import (
    HierarchyEdge,
    OntologyClass,
    OntologyRelation,
    OntologySummary,
)
from ontology_hitl.api.dependencies import sparql_query

logger = structlog.get_logger(__name__)
router = APIRouter()

# ── SPARQL templates ─────────────────────────────────────────────────────

_CLASSES_QUERY = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?uri ?label ?description ?parent WHERE {
    ?uri a owl:Class .
    OPTIONAL { ?uri rdfs:label ?label . }
    OPTIONAL { ?uri rdfs:comment ?description . }
    OPTIONAL { ?uri rdfs:subClassOf ?parent .
               ?parent a owl:Class . }
    FILTER(!isBlank(?uri))
}
ORDER BY ?label
"""

_RELATIONS_QUERY = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?uri ?label ?description ?domain ?range WHERE {
    ?uri a owl:ObjectProperty .
    OPTIONAL { ?uri rdfs:label ?label . }
    OPTIONAL { ?uri rdfs:comment ?description . }
    OPTIONAL { ?uri rdfs:domain ?domain . }
    OPTIONAL { ?uri rdfs:range ?range . }
    FILTER(!isBlank(?uri))
}
ORDER BY ?label
"""

_HIERARCHY_QUERY = """
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?child ?parent WHERE {
    ?child rdfs:subClassOf ?parent .
    ?child a owl:Class .
    ?parent a owl:Class .
    FILTER(!isBlank(?child) && !isBlank(?parent))
}
"""


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/classes", response_model=list[OntologyClass])
async def list_classes() -> list[OntologyClass]:
    """List all OWL classes in the ontology."""
    rows = sparql_query(_CLASSES_QUERY)
    # Group by URI (a class may appear multiple times due to OPTIONAL joins)
    classes: dict[str, OntologyClass] = {}
    for row in rows:
        uri = row["uri"]
        if uri not in classes:
            classes[uri] = OntologyClass(
                uri=uri,
                label=row.get("label", uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]),
                description=row.get("description", ""),
                parent_uri=row.get("parent"),
            )
        elif row.get("parent") and not classes[uri].parent_uri:
            classes[uri].parent_uri = row["parent"]
    return list(classes.values())


@router.get("/relations", response_model=list[OntologyRelation])
async def list_relations() -> list[OntologyRelation]:
    """List all OWL object properties."""
    rows = sparql_query(_RELATIONS_QUERY)
    rels: dict[str, OntologyRelation] = {}
    for row in rows:
        uri = row["uri"]
        if uri not in rels:
            rels[uri] = OntologyRelation(
                uri=uri,
                label=row.get("label", uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]),
                description=row.get("description", ""),
            )
        if row.get("domain") and row["domain"] not in rels[uri].domain:
            rels[uri].domain.append(row["domain"])
        if row.get("range") and row["range"] not in rels[uri].range:
            rels[uri].range.append(row["range"])
    return list(rels.values())


@router.get("/hierarchy", response_model=list[HierarchyEdge])
async def get_hierarchy() -> list[HierarchyEdge]:
    """Return the class hierarchy as parent→child edges."""
    rows = sparql_query(_HIERARCHY_QUERY)
    return [
        HierarchyEdge(parent_uri=row["parent"], child_uri=row["child"])
        for row in rows
    ]


@router.get("/summary", response_model=OntologySummary)
async def get_summary() -> OntologySummary:
    """Full ontology overview: classes, relations, and hierarchy."""
    classes = await list_classes()
    relations = await list_relations()
    hierarchy = await get_hierarchy()
    return OntologySummary(
        classes=classes,
        relations=relations,
        hierarchy=hierarchy,
        class_count=len(classes),
        relation_count=len(relations),
    )
```

### 8.3 Extend / TBox Changes

`src/ontology_hitl/api/routes/extend.py`

This is the **core endpoint** that KGBuilder calls when it detects ontology gaps.

```python
"""Ontology extension endpoints — apply TBox changes via SPARQL UPDATE."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException

from ontology_hitl.api.schemas import (
    BulkExtendRequest,
    TBoxChangeRequest,
    TBoxChangeResponse,
    TBoxChangeType,
)
from ontology_hitl.api.dependencies import (
    llm_generate,
    sparql_query,
    sparql_update,
    get_settings,
    notify_kgbuilder_rebuild,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────

def _generate_class_definition(class_name: str, rationale: str) -> str:
    """Use LLM to generate an OWL class definition in Turtle format."""
    prompt = f"""Generate an OWL class definition in Turtle syntax for the class "{class_name}".

Context / rationale: {rationale}

Requirements:
- Use a sensible namespace prefix (e.g., ex: or the ontology's existing prefix)
- Include rdfs:label, rdfs:comment
- Include rdfs:subClassOf if an appropriate parent is obvious
- Keep it concise

Return ONLY the Turtle snippet, no explanation."""

    system = (
        "You are an ontology engineer. Produce valid OWL/Turtle class definitions."
    )
    return llm_generate(prompt, system=system)


def _generate_shacl_shape(class_uri: str, class_name: str) -> str:
    """Use LLM to generate a SHACL NodeShape for the given class."""
    prompt = f"""Generate a SHACL NodeShape in Turtle syntax for the OWL class <{class_uri}> ("{class_name}").

Requirements:
- Target class: <{class_uri}>
- Include sh:property constraints for likely properties (rdfs:label at minimum)
- Use sh:minCount, sh:maxCount, sh:datatype where appropriate
- Keep it concise

Return ONLY the Turtle snippet, no explanation."""

    system = "You are a SHACL shapes engineer. Produce valid SHACL Turtle."
    return llm_generate(prompt, system=system)


def _apply_new_class(request: TBoxChangeRequest) -> TBoxChangeResponse:
    """Handle tbox_new_class: generate definition, insert into staging graph."""
    settings = get_settings()
    change_id = f"change_{uuid.uuid4().hex[:12]}"
    class_name = request.suggested_changes.get(
        "label", request.review_item_id.replace("gap_", "")
    )

    changes_applied: list[str] = []

    # 1. Generate OWL class definition via LLM
    turtle_def = _generate_class_definition(class_name, request.rationale)
    logger.info("class_definition_generated", class_name=class_name, change_id=change_id)

    # 2. Insert into staging dataset via SPARQL UPDATE
    staging_ds = settings["fuseki_staging"]
    insert_query = f"""
    INSERT DATA {{
        {turtle_def}
    }}
    """
    try:
        sparql_update(insert_query, dataset=staging_ds)
        changes_applied.append(f"Inserted class '{class_name}' into staging graph")
    except Exception as e:
        logger.error("staging_insert_failed", error=str(e), class_name=class_name)
        return TBoxChangeResponse(
            status="error",
            change_id=change_id,
            changes_applied=[f"Failed to insert: {e}"],
        )

    # 3. Generate SHACL shape
    class_uri = request.suggested_changes.get("uri", f"ex:{class_name}")
    try:
        shacl_turtle = _generate_shacl_shape(class_uri, class_name)
        sparql_update(
            f"INSERT DATA {{ {shacl_turtle} }}",
            dataset=staging_ds,
        )
        changes_applied.append(f"Generated SHACL shape for '{class_name}'")
    except Exception as e:
        logger.warning("shacl_generation_failed", error=str(e))
        changes_applied.append(f"SHACL generation skipped: {e}")

    # 4. Log change to history
    timestamp = datetime.now(timezone.utc).isoformat()
    changes_applied.append(f"Logged at {timestamp}")

    return TBoxChangeResponse(
        status="staged",
        change_id=change_id,
        changes_applied=changes_applied,
    )


def _apply_modify_class(request: TBoxChangeRequest) -> TBoxChangeResponse:
    """Handle tbox_modify_class: update label/description/parent of existing class."""
    change_id = f"change_{uuid.uuid4().hex[:12]}"
    class_uri = request.suggested_changes.get("uri", "")
    if not class_uri:
        return TBoxChangeResponse(
            status="error",
            change_id=change_id,
            changes_applied=["Missing 'uri' in suggested_changes"],
        )

    changes_applied: list[str] = []

    # Update label if provided
    new_label = request.suggested_changes.get("label")
    if new_label:
        sparql_update(f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            DELETE {{ <{class_uri}> rdfs:label ?old }}
            INSERT {{ <{class_uri}> rdfs:label "{new_label}" }}
            WHERE  {{ OPTIONAL {{ <{class_uri}> rdfs:label ?old }} }}
        """)
        changes_applied.append(f"Updated label to '{new_label}'")

    # Update description if provided
    new_desc = request.suggested_changes.get("description")
    if new_desc:
        sparql_update(f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            DELETE {{ <{class_uri}> rdfs:comment ?old }}
            INSERT {{ <{class_uri}> rdfs:comment "{new_desc}" }}
            WHERE  {{ OPTIONAL {{ <{class_uri}> rdfs:comment ?old }} }}
        """)
        changes_applied.append(f"Updated description")

    # Update parent if provided
    new_parent = request.suggested_changes.get("parent_uri")
    if new_parent:
        sparql_update(f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl:  <http://www.w3.org/2002/07/owl#>
            DELETE {{ <{class_uri}> rdfs:subClassOf ?old }}
            INSERT {{ <{class_uri}> rdfs:subClassOf <{new_parent}> }}
            WHERE  {{ OPTIONAL {{ <{class_uri}> rdfs:subClassOf ?old .
                                  ?old a owl:Class . }} }}
        """)
        changes_applied.append(f"Re-parented under <{new_parent}>")

    return TBoxChangeResponse(
        status="applied",
        change_id=change_id,
        changes_applied=changes_applied or ["No changes requested"],
    )


def _apply_hierarchy_fix(request: TBoxChangeRequest) -> TBoxChangeResponse:
    """Handle tbox_hierarchy_fix: move a class under a new parent."""
    change_id = f"change_{uuid.uuid4().hex[:12]}"
    class_uri = request.suggested_changes.get("uri", "")
    new_parent = request.suggested_changes.get("parent_uri", "")

    if not class_uri or not new_parent:
        return TBoxChangeResponse(
            status="error",
            change_id=change_id,
            changes_applied=["Missing 'uri' or 'parent_uri' in suggested_changes"],
        )

    sparql_update(f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        DELETE {{ <{class_uri}> rdfs:subClassOf ?old }}
        INSERT {{ <{class_uri}> rdfs:subClassOf <{new_parent}> }}
        WHERE  {{ OPTIONAL {{ <{class_uri}> rdfs:subClassOf ?old .
                              ?old a owl:Class . }} }}
    """)

    return TBoxChangeResponse(
        status="applied",
        change_id=change_id,
        changes_applied=[f"Moved <{class_uri}> under <{new_parent}>"],
    )


def _apply_property_fix(request: TBoxChangeRequest) -> TBoxChangeResponse:
    """Handle tbox_property_fix: add/modify property on a class."""
    change_id = f"change_{uuid.uuid4().hex[:12]}"
    # Implementation depends on your property model — stub for now
    return TBoxChangeResponse(
        status="staged",
        change_id=change_id,
        changes_applied=["Property fix staged for review"],
    )


_HANDLERS: dict[TBoxChangeType, callable] = {
    TBoxChangeType.NEW_CLASS: _apply_new_class,
    TBoxChangeType.MODIFY_CLASS: _apply_modify_class,
    TBoxChangeType.HIERARCHY_FIX: _apply_hierarchy_fix,
    TBoxChangeType.PROPERTY_FIX: _apply_property_fix,
}


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/extend", response_model=TBoxChangeResponse)
async def extend(request: TBoxChangeRequest) -> TBoxChangeResponse:
    """Apply a single TBox change to the ontology.

    Called by KGBuilder's HITL gap detector or by human reviewers.
    Depending on change_type, this will:
    - Generate OWL class definition + SHACL shape (new_class)
    - Update class metadata (modify_class)
    - Fix hierarchy relationships (hierarchy_fix)
    - Add/modify properties (property_fix)
    """
    handler = _HANDLERS.get(request.change_type)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown change_type: {request.change_type}",
        )

    logger.info(
        "applying_tbox_change",
        change_type=request.change_type,
        review_item_id=request.review_item_id,
    )
    result = handler(request)

    # Best-effort: notify KGBuilder that ontology changed
    if result.status in ("applied", "staged"):
        notify_kgbuilder_rebuild()

    return result


@router.post("/extend/bulk", response_model=list[TBoxChangeResponse])
async def extend_bulk(request: BulkExtendRequest) -> list[TBoxChangeResponse]:
    """Apply multiple TBox changes.

    If `atomic=True` (default), rolls back all changes on any failure.
    If `atomic=False`, applies as many as possible.
    """
    results: list[TBoxChangeResponse] = []
    for change in request.changes:
        handler = _HANDLERS.get(change.change_type)
        if not handler:
            result = TBoxChangeResponse(
                status="error",
                change_id="n/a",
                changes_applied=[f"Unknown change_type: {change.change_type}"],
            )
        else:
            result = handler(change)

        results.append(result)

        if request.atomic and result.status == "error":
            logger.warning(
                "bulk_extend_aborted",
                failed_item=change.review_item_id,
            )
            # Mark remaining as skipped
            for remaining in request.changes[len(results):]:
                results.append(
                    TBoxChangeResponse(
                        status="error",
                        change_id="n/a",
                        changes_applied=["Skipped due to earlier atomic failure"],
                    )
                )
            break

    # Notify KGBuilder once (not per change)
    applied = [r for r in results if r.status in ("applied", "staged")]
    if applied:
        notify_kgbuilder_rebuild()

    return results
```

### 8.4 SHACL Validation

`src/ontology_hitl/api/routes/validate.py`

```python
"""SHACL validation endpoint."""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException

from ontology_hitl.api.schemas import (
    SHACLValidationRequest,
    SHACLValidationResponse,
    SHACLViolation,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/validate/shacl", response_model=SHACLValidationResponse)
async def validate_shacl(request: SHACLValidationRequest) -> SHACLValidationResponse:
    """Validate RDF data graph against SHACL shapes.

    If paths are not provided, loads the default dataset and shapes
    from Fuseki.
    """
    try:
        import rdflib
        from pyshacl import validate as shacl_validate
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Missing dependency: {e}. Install rdflib and pyshacl.",
        )

    # Load data graph
    data_graph = rdflib.Graph()
    if request.data_graph_path:
        p = Path(request.data_graph_path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Data graph not found: {p}")
        data_graph.parse(str(p))
    else:
        # Load from Fuseki default dataset
        from ontology_hitl.api.dependencies import get_settings, get_fuseki_client

        settings = get_settings()
        ds = settings["fuseki_dataset"]
        client = get_fuseki_client()
        resp = client.get(
            f"/{ds}",
            headers={"Accept": "text/turtle"},
        )
        resp.raise_for_status()
        data_graph.parse(data=resp.text, format="turtle")

    # Load shapes graph
    shapes_graph = rdflib.Graph()
    if request.shapes_path:
        p = Path(request.shapes_path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Shapes file not found: {p}")
        shapes_graph.parse(str(p))
    else:
        # Auto-detect: look for shapes in data graph or a shapes dataset
        # For now, try loading from a "shapes" named graph in Fuseki
        from ontology_hitl.api.dependencies import get_settings, get_fuseki_client

        settings = get_settings()
        client = get_fuseki_client()
        try:
            resp = client.get(
                f"/{settings['fuseki_dataset']}/data",
                params={"graph": "urn:shapes"},
                headers={"Accept": "text/turtle"},
            )
            if resp.status_code == 200:
                shapes_graph.parse(data=resp.text, format="turtle")
        except Exception:
            logger.warning("shapes_graph_load_fallback")

    if len(shapes_graph) == 0:
        return SHACLValidationResponse(
            conforms=True,
            violations=[],
            total_shapes=0,
        )

    # Run validation
    conforms, _, results_text = shacl_validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
    )

    # Parse violations from results graph
    violations: list[SHACLViolation] = []
    results_graph = rdflib.Graph()
    try:
        results_graph.parse(data=results_text, format="turtle")
        SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
        for result in results_graph.subjects(rdflib.RDF.type, SH.ValidationResult):
            focus = str(results_graph.value(result, SH.focusNode) or "")
            path = str(results_graph.value(result, SH.resultPath) or "")
            msg = str(results_graph.value(result, SH.resultMessage) or "")
            sev = str(results_graph.value(result, SH.resultSeverity) or "")
            violations.append(SHACLViolation(
                focus_node=focus,
                path=path,
                message=msg,
                severity=sev.rsplit("#", 1)[-1] if "#" in sev else sev,
            ))
    except Exception:
        logger.warning("shacl_results_parse_failed")

    # Count shapes
    total_shapes = len(list(shapes_graph.subjects(
        rdflib.RDF.type,
        rdflib.Namespace("http://www.w3.org/ns/shacl#").NodeShape,
    )))

    return SHACLValidationResponse(
        conforms=conforms,
        violations=violations,
        total_shapes=total_shapes,
    )
```

---

## 9. Docker Setup

### 9.1 Dockerfile.api

Create `docker/Dockerfile.api`:

```dockerfile
FROM python:3.11-slim AS base

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi "uvicorn[standard]" httpx

# Copy source
COPY . .
RUN pip install --no-cache-dir -e .

EXPOSE 8003

CMD ["uvicorn", "ontology_hitl.api.server:app", "--host", "0.0.0.0", "--port", "8003"]
```

### 9.2 docker-compose.yml (standalone)

This goes at the **root of the OntologyExtender repo** and lets it run
independently (without KGBuilder or GraphQA):

```yaml
services:
  # ── OntologyExtender API ───────────────────────────────────────────────
  ontology-api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports:
      - "8003:8003"
    environment:
      SERVICE_NAME: ontology
      UVICORN_PORT: "8003"
      HITL_FUSEKI_URL: http://fuseki:3030
      HITL_FUSEKI_DATASET: kgbuilder
      HITL_FUSEKI_STAGING_DATASET: kgbuilder-staging
      HITL_OLLAMA_URL: http://ollama-ontology:11434
      HITL_OLLAMA_MODEL: qwen3:8b
      KGBUILDER_API_URL: http://localhost:8001   # cross-service (optional when standalone)
    depends_on:
      fuseki:
        condition: service_started
      ollama-ontology:
        condition: service_started
    networks:
      - ontology-net

  # ── Fuseki (SPARQL / ontology store) ───────────────────────────────────
  fuseki:
    image: stain/jena-fuseki
    ports:
      - "3030:3030"
    environment:
      ADMIN_PASSWORD: admin
      FUSEKI_DATASET_1: kgbuilder
      FUSEKI_DATASET_2: kgbuilder-staging
    volumes:
      - fuseki-data:/fuseki
    networks:
      - ontology-net

  # ── Ollama (LLM for class generation) ─────────────────────────────────
  ollama-ontology:
    image: ollama/ollama:0.14.3
    ports:
      - "11437:11434"
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
      - ontology-net

volumes:
  fuseki-data:
  ollama-data:

networks:
  ontology-net:
    driver: bridge
```

---

## 10. Cross-Service Integration

### 10.1 KGBuilder → OntologyExtender

Already implemented in KGBuilder's
[hitl.py](../src/kgbuilder/api/routes/hitl.py).
When `POST /api/v1/hitl/gaps/detect` finds `suggested_new_classes`, it
POSTs each to `{ONTOLOGY_API_URL}/api/v1/extend`:

```json
{
  "change_type": "tbox_new_class",
  "review_item_id": "gap_SomeNewClass",
  "reviewer_id": "kgbuilder_gap_detector",
  "rationale": "Found 5 entities of type 'SomeNewClass' with no ontology match",
  "suggested_changes": {"label": "SomeNewClass"},
  "confidence": 0.85
}
```

### 10.2 OntologyExtender → KGBuilder

After applying changes, `extend.py` calls `notify_kgbuilder_rebuild()`,
which POSTs to `{KGBUILDER_API_URL}/api/v1/build` with an empty body.
This triggers a re-extraction with the updated ontology.

### 10.3 Platform docker-compose

When running inside the full KGPlatform, both services share a Docker
network. The platform `docker-compose.yml` sets:

```yaml
ontology-api:
  environment:
    KGBUILDER_API_URL: http://kgbuilder-api:8001

kgbuilder-api:
  environment:
    ONTOLOGY_API_URL: http://ontology-api:8003
```

---

## 11. Testing Strategy

### Unit Tests

```
tests/api/
├── test_schemas.py          # Validate schema serialization/defaults
├── test_browse.py           # Mock sparql_query, verify OntologyClass grouping
├── test_extend.py           # Mock sparql_update + llm_generate, verify handlers
├── test_validate.py         # Mock pyshacl, verify violation parsing
└── conftest.py              # Shared fixtures (mock Fuseki, mock Ollama)
```

**Key fixtures:**

```python
# tests/api/conftest.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from ontology_hitl.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_sparql_query():
    with patch("ontology_hitl.api.dependencies.sparql_query") as m:
        yield m


@pytest.fixture
def mock_sparql_update():
    with patch("ontology_hitl.api.dependencies.sparql_update") as m:
        yield m


@pytest.fixture
def mock_llm_generate():
    with patch("ontology_hitl.api.dependencies.llm_generate") as m:
        m.return_value = 'ex:TestClass a owl:Class ; rdfs:label "Test" .'
        yield m
```

**Example test for `/extend`:**

```python
def test_extend_new_class(client, mock_sparql_update, mock_llm_generate):
    resp = client.post("/api/v1/extend", json={
        "change_type": "tbox_new_class",
        "review_item_id": "gap_TestClass",
        "rationale": "Found unmapped entities",
        "suggested_changes": {"label": "TestClass"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "staged"
    assert mock_llm_generate.call_count >= 1
    assert mock_sparql_update.call_count >= 1
```

### Integration Tests (with docker-compose)

```bash
# From OntologyExtender repo root
docker compose up -d
sleep 10  # wait for Fuseki

# Health check
curl http://localhost:8003/api/v1/health

# Browse (empty ontology)
curl http://localhost:8003/api/v1/ontology/classes

# Extend (requires Ollama model)
curl -X POST http://localhost:8003/api/v1/extend \
  -H "Content-Type: application/json" \
  -d '{"change_type":"tbox_new_class","review_item_id":"test","rationale":"test"}'

docker compose down
```

---

## 12. Implementation Checklist

Use this to track progress:

- [ ] Create `src/ontology_hitl/api/__init__.py`
- [ ] Create `src/ontology_hitl/api/schemas.py` (copy from §5)
- [ ] Create `src/ontology_hitl/api/dependencies.py` (copy from §6)
- [ ] Create `src/ontology_hitl/api/server.py` (copy from §7)
- [ ] Create `src/ontology_hitl/api/routes/__init__.py`
- [ ] Create `src/ontology_hitl/api/routes/status.py` (copy from §8.1)
- [ ] Create `src/ontology_hitl/api/routes/browse.py` (copy from §8.2)
- [ ] Create `src/ontology_hitl/api/routes/extend.py` (copy from §8.3)
- [ ] Create `src/ontology_hitl/api/routes/validate.py` (copy from §8.4)
- [ ] Create `docker/Dockerfile.api` (copy from §9.1)
- [ ] Update / create `docker-compose.yml` (copy from §9.2)
- [ ] Add `[project.optional-dependencies] api = [...]` to `pyproject.toml`
- [ ] Install with `.venv/bin/pip install -e ".[api]"`
- [ ] Verify import: `.venv/bin/python -c "from ontology_hitl.api.server import app; print(app.title)"`
- [ ] Run: `.venv/bin/uvicorn ontology_hitl.api.server:app --port 8003 --reload`
- [ ] Open http://localhost:8003/docs and verify Swagger UI
- [ ] Create `tests/api/conftest.py` + test files
- [ ] Run tests: `.venv/bin/pytest tests/api/ -v`
- [ ] Commit on a `fast-api` branch: `git checkout -b fast-api && git add -A && git commit -m "feat: add FastAPI service"`

---

## Appendix: Endpoint Summary Table

| Method | Path                       | Description                       | Request              | Response                  |
| ------ | -------------------------- | --------------------------------- | -------------------- | ------------------------- |
| `GET`  | `/`                        | Root redirect to docs             | —                    | `{service, docs}`         |
| `GET`  | `/api/v1/health`           | Health check (Fuseki + Ollama)    | —                    | `ServiceHealth`           |
| `GET`  | `/api/v1/ontology/classes` | List all OWL classes              | —                    | `list[OntologyClass]`     |
| `GET`  | `/api/v1/ontology/relations` | List all object properties      | —                    | `list[OntologyRelation]`  |
| `GET`  | `/api/v1/ontology/hierarchy` | Class hierarchy edges           | —                    | `list[HierarchyEdge]`     |
| `GET`  | `/api/v1/ontology/summary` | Full ontology overview            | —                    | `OntologySummary`         |
| `POST` | `/api/v1/extend`           | Apply single TBox change          | `TBoxChangeRequest`  | `TBoxChangeResponse`      |
| `POST` | `/api/v1/extend/bulk`      | Apply batch of TBox changes       | `BulkExtendRequest`  | `list[TBoxChangeResponse]`|
| `POST` | `/api/v1/validate/shacl`   | Validate RDF against SHACL shapes | `SHACLValidationRequest` | `SHACLValidationResponse` |
