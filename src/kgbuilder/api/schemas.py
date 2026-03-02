"""Request/response schemas for the KGBuilder API.

Pydantic models used across route modules. Kept separate from internal
dataclasses so the API layer stays decoupled from pipeline internals.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Build pipeline
# ------------------------------------------------------------------


class BuildStatus(str, Enum):
    """Status of a background build job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BuildRequest(BaseModel):
    """Request to trigger a KG build pipeline run."""

    questions_per_class: int = Field(default=3, ge=1, le=20)
    max_iterations: int = Field(default=2, ge=1, le=50)
    classes_limit: int | None = Field(
        default=None,
        description="Limit ontology classes to process (None = all)",
    )
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    dense_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    sparse_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    top_k: int = Field(default=10, ge=1, le=100)
    validate: bool = True
    link_laws: bool = True
    model: str = Field(default="qwen3:8b")


class BuildResponse(BaseModel):
    """Response after starting a build job."""

    job_id: str
    status: BuildStatus
    message: str


class JobStatus(BaseModel):
    """Current status of a build job."""

    job_id: str
    status: BuildStatus
    progress: float = 0.0
    current_phase: str = ""
    entities_count: int = 0
    relations_count: int = 0
    current_iteration: int = 0
    started_at: str | None = None
    error: str | None = None


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


class ValidationRequest(BaseModel):
    """Request to run validation on the current KG."""

    run_shacl: bool = True
    run_rules: bool = True
    run_consistency: bool = True
    ontology_path: str | None = None
    shapes_path: str | None = None


class ValidationResponse(BaseModel):
    """Validation result summary."""

    passed: bool
    total_checks: int
    pass_rate: float
    violations_count: int
    conflicts_count: int
    violations: list[dict[str, str]]
    report_path: str | None = None


# ------------------------------------------------------------------
# Export
# ------------------------------------------------------------------


class ExportFormat(str, Enum):
    """Supported export formats."""

    JSON = "json"
    JSON_LD = "jsonld"
    TURTLE = "turtle"
    CYPHER = "cypher"
    GRAPHML = "graphml"


class ExportRequest(BaseModel):
    """Request to export the KG."""

    format: ExportFormat = ExportFormat.JSON
    include_metadata: bool = True
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    output_path: str | None = None


class ExportResponse(BaseModel):
    """Export result."""

    format: str
    output_path: str
    node_count: int
    edge_count: int


# ------------------------------------------------------------------
# HITL
# ------------------------------------------------------------------


class GapReportResponse(BaseModel):
    """Gap detection report."""

    untyped_entities: list[str]
    failed_queries: list[str]
    suggested_new_classes: list[str]
    suggested_new_relations: list[str]
    coverage_score: float
    low_confidence_answers: list[dict[str, str]]
    timestamp: str | None = None


class GapDetectRequest(BaseModel):
    """Trigger gap detection from QA feedback."""

    qa_results: list[dict[str, str | float]]


class FeedbackRequest(BaseModel):
    """Expert feedback submission."""

    review_item_id: str
    reviewer_id: str
    decision: str = Field(
        description="accepted | rejected | modified | needs_discussion",
    )
    rationale: str
    suggested_changes: dict[str, str] = Field(default_factory=dict)
    new_competency_questions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FeedbackResponse(BaseModel):
    """Feedback processing result."""

    status: str
    routed_to: list[str]
    change_request_paths: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------
# Status / health
# ------------------------------------------------------------------


class ServiceHealth(BaseModel):
    """Service health check response."""

    status: str
    service: str = "kgbuilder"
    version: str = "0.1.0"
    neo4j: str = "unknown"
    qdrant: str = "unknown"
    fuseki: str = "unknown"
    ollama: str = "unknown"


class KGStatistics(BaseModel):
    """Knowledge graph statistics."""

    node_count: int = 0
    edge_count: int = 0
    nodes_by_type: dict[str, int] = Field(default_factory=dict)
    edges_by_type: dict[str, int] = Field(default_factory=dict)
    avg_confidence: float = 0.0


# ------------------------------------------------------------------
# Ontology
# ------------------------------------------------------------------


class OntologyInfo(BaseModel):
    """Ontology metadata."""

    classes: list[str]
    relations: list[str]
    class_count: int
    relation_count: int
    hierarchy: list[dict[str, str]]
