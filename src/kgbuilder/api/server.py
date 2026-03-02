"""KGBuilder FastAPI application.

Main entry point for the KnowledgeGraphBuilder REST API.

Run with:
    uvicorn kgbuilder.api.server:app --host 0.0.0.0 --port 8001 --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kgbuilder.api.routes.build import router as build_router
from kgbuilder.api.routes.export import router as export_router
from kgbuilder.api.routes.hitl import router as hitl_router
from kgbuilder.api.routes.status import router as status_router
from kgbuilder.api.routes.validate import router as validate_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup / shutdown hooks."""
    logger.info("kgbuilder_api_starting")
    yield
    logger.info("kgbuilder_api_stopping")


app = FastAPI(
    title="KGBuilder API",
    description=(
        "REST API for the KnowledgeGraphBuilder ontology-driven KG construction pipeline. "
        "Provides endpoints for building, validating, exporting knowledge graphs, "
        "and cross-repo HITL feedback routing."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules
app.include_router(status_router, prefix="/api/v1", tags=["status"])
app.include_router(build_router, prefix="/api/v1", tags=["build"])
app.include_router(validate_router, prefix="/api/v1", tags=["validate"])
app.include_router(export_router, prefix="/api/v1", tags=["export"])
app.include_router(hitl_router, prefix="/api/v1/hitl", tags=["hitl"])


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Redirect to docs."""
    return {"message": "KGBuilder API — visit /docs for interactive documentation"}
