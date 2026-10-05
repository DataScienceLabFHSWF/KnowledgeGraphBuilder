"""Request/response schemas for the KGBuilder API.

Pydantic models used across route modules. Kept separate from internal
dataclasses so the API layer stays decoupled from pipeline internals.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ------------------------------------------------------------------
# Build pipeline
# ------------------------------------------------------------------


class BuildStatus(str, Enum):
    """Status of a background build job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionStatusValue(str, Enum):
    """Status of an extraction request."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionFile(BaseModel):
    """Base64-encoded document supplied for extraction."""

    name: str = Field(min_length=1)
    content_type: str = Field(alias="contentType", min_length=1)
    base64: str = Field(min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class ExtractionOntologyAttribute(BaseModel):
    """Class attribute supplied as part of an extraction ontology."""

    id: str
    name: str
    data_type: str = Field(alias="dataType")
    required: bool = False
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ExtractionOntologyClass(BaseModel):
    """Entity class supplied as part of an extraction ontology."""

    id: str
    name: str
    module_id: str | None = Field(default=None, alias="moduleId")
    module: str | None = None
    description: str | None = None
    parent_class_id: str | None = Field(default=None, alias="parentClassId")
    attributes: list[ExtractionOntologyAttribute] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ExtractionOntologyRelation(BaseModel):
    """Relation supplied as part of an extraction ontology."""

    id: str
    name: str
    domain_class_id: str = Field(alias="domainClassId")
    range_class_id: str = Field(alias="rangeClassId")
    description: str | None = None
    inverse_name: str | None = Field(default=None, alias="inverseName")
    cardinality: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ExtractionOntologyModule(BaseModel):
    """Ontology module grouping entity classes."""

    id: str
    name: str
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ExtractionOntologyExample(BaseModel):
    """Example value attached to an ontology class or relation."""

    target_type: str = Field(alias="targetType")
    target_id: str = Field(alias="targetId")
    value: str
    subject_label: str | None = Field(default=None, alias="subjectLabel")
    predicate_label: str | None = Field(default=None, alias="predicateLabel")
    object_label: str | None = Field(default=None, alias="objectLabel")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ExtractionOntology(BaseModel):
    """Ontology subset and metadata provided to the extraction agent."""

    name: str = Field(min_length=1)
    default_language: str | None = Field(default=None, alias="defaultLanguage")
    languages: list[dict[str, str]] = Field(default_factory=list)
    usecase: str | None = None
    version: str | None = None
    modules: list[ExtractionOntologyModule] = Field(default_factory=list)
    classes: list[ExtractionOntologyClass] = Field(min_length=1)
    relations: list[ExtractionOntologyRelation] = Field(default_factory=list)
    competency_questions: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="competencyQuestions",
    )
    examples: list[ExtractionOntologyExample] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ExtractionRequest(BaseModel):
    """Request to start an asynchronous document extraction."""

    run_id: str = Field(alias="runId", min_length=1)
    document_id: str = Field(alias="documentId", min_length=1)
    ontology_id: str = Field(alias="ontologyId", min_length=1)
    file: ExtractionFile
    ontology: ExtractionOntology

    model_config = ConfigDict(populate_by_name=True)


class ExtractionStartResponse(BaseModel):
    """Response returned after accepting an extraction request."""

    run_id: str = Field(alias="runId")

    model_config = ConfigDict(populate_by_name=True)


class ExtractionStatusResponse(BaseModel):
    """Current state of an extraction run."""

    run_id: str = Field(alias="runId")
    status: ExtractionStatusValue
    progress: int = Field(ge=0, le=100)

    model_config = ConfigDict(populate_by_name=True)


class ExtractionParagraph(BaseModel):
    """Paragraph included in the extracted document outline."""

    id: str
    content: str


class ExtractionSection(BaseModel):
    """Section included in the extracted document outline."""

    id: str
    title: str
    paragraphs: list[ExtractionParagraph]


class ExtractionEntityAttribute(BaseModel):
    """Extracted entity attribute."""

    attribute_name: str
    value: Any


class ExtractionEntityResult(BaseModel):
    """Entity result in the inter-application extraction contract."""

    temp_id: str
    text: str
    class_name: str = Field(alias="className")
    attributes: list[ExtractionEntityAttribute]


class ExtractionEvidence(BaseModel):
    """Evidence for an extracted relation."""

    quote: str
    section_title: str | None = Field(alias="sectionTitle")
    paragraph_id: str | None = Field(alias="paragraphId")
    page_from: int | None = Field(alias="pageFrom")
    page_to: int | None = Field(alias="pageTo")

    model_config = ConfigDict(populate_by_name=True)


class ExtractionFact(BaseModel):
    """Relation result in the inter-application extraction contract."""

    subject_temp_id: str
    relation_text: str
    object_temp_id: str
    subject_class_name: str = Field(alias="subjectClassName")
    object_class_name: str = Field(alias="objectClassName")
    relation_name: str = Field(alias="relationName")
    confidence: float = Field(ge=0.0, le=1.0)
    is_cross_chapter: bool = Field(alias="isCrossChapter")
    evidence: ExtractionEvidence

    model_config = ConfigDict(populate_by_name=True)


class ExtractionResults(BaseModel):
    """Completed extraction result."""

    sections: list[ExtractionSection]
    entities: list[ExtractionEntityResult]
    facts: list[ExtractionFact]


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
    run_validation: bool = Field(default=True, description="Run SHACL validation after build")
    link_laws: bool = True
    model: str = Field(default="gemma4:e2b")


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
    llm_backend: str = "unknown"
    llm: str = "unknown"


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
