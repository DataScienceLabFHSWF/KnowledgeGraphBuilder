"""Asynchronous, ontology-guided document extraction endpoints."""

from __future__ import annotations

import base64
import binascii
import hmac
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, Thread
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException

from kgbuilder.api.schemas import (
    ExtractionEntityAttribute,
    ExtractionEntityResult,
    ExtractionEvidence,
    ExtractionFact,
    ExtractionFile,
    ExtractionOntologyClass,
    ExtractionOntologyRelation,
    ExtractionParagraph,
    ExtractionRequest,
    ExtractionResults,
    ExtractionSection,
    ExtractionStartResponse,
    ExtractionStatusResponse,
    ExtractionStatusValue,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

# In-memory storage follows the existing build-job API; use shared persistence
# before running multiple API workers or requiring durable job history.
_runs: dict[str, dict[str, Any]] = {}
_runs_lock = Lock()
_SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xml"}


@dataclass(frozen=True)
class _RetrievedText:
    """One in-memory retrieval result backed by the submitted document."""

    content: str


@dataclass(frozen=True)
class _ExtractionQuestion:
    """A question routed to one module-scoped extraction subagent."""

    text: str
    entity_class: str
    cq_type: Any


class _SubmittedDocumentRetriever:
    """Retriever adapter that exposes the submitted document to agent skills."""

    def __init__(self, text: str) -> None:
        self._paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", text.strip())
            if paragraph.strip()
        ]

    @property
    def paragraphs(self) -> list[str]:
        """Return paragraphs as independent retrieval results."""
        return self._paragraphs

    def retrieve(self, query: str, top_k: int = 10) -> list[_RetrievedText]:
        return [_RetrievedText(content=paragraph) for paragraph in self._paragraphs]


def _get_file_bytes(file: ExtractionFile) -> bytes:
    """Decode and validate the request's base64 document body."""
    try:
        return base64.b64decode(file.base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="file.base64 must be valid base64") from exc


def _validate_file_format(file: ExtractionFile, content: bytes) -> None:
    """Reject unsupported formats before accepting a background job."""
    media_type = file.content_type.split(";", maxsplit=1)[0].strip().lower()
    if media_type.startswith("text/"):
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail="Text files must be UTF-8 encoded",
            ) from exc
        return

    suffix = Path(file.name).suffix.lower()
    if suffix not in _SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported files are text/*, PDF, DOCX, PPTX, and XML",
        )


def _load_document_text(file: ExtractionFile, content: bytes) -> str:
    """Load text from plain-text or supported document uploads."""
    if file.content_type.split(";", maxsplit=1)[0].strip().lower().startswith("text/"):
        text = content.decode("utf-8")
    else:
        from kgbuilder.document.loaders import DocumentLoaderFactory

        suffix = Path(file.name).suffix.lower()
        with tempfile.TemporaryDirectory(prefix="kgbuilder-extract-") as temp_dir:
            path = Path(temp_dir) / f"submitted{suffix}"
            path.write_bytes(content)
            document = DocumentLoaderFactory.load(path)
            text = document.content

    if not text.strip():
        raise ValueError("No extractable text found in the submitted file")
    return text


def _class_definitions(
    ontology_id: str,
    classes: list[ExtractionOntologyClass],
    ontology_modules: list[Any],
    ontology_examples: list[Any],
) -> tuple[dict[str, list[Any]], dict[str, str]]:
    """Convert request classes to extractor definitions, grouped by module."""
    from kgbuilder.extraction.entity import OntologyClassDef, OntologyPropertyDef

    module_names = {module.id: module.name for module in ontology_modules}
    examples_by_class: dict[str, list[str]] = {}
    for example in ontology_examples:
        if example.target_type == "class":
            examples_by_class.setdefault(example.target_id, []).append(example.value)

    grouped: dict[str, list[Any]] = {}
    id_to_label: dict[str, str] = {}

    for item in classes:
        module = item.module or module_names.get(item.module_id or "") or "General"
        properties = [
            OntologyPropertyDef(
                name=attribute.name,
                data_type=attribute.data_type,
                description=attribute.description,
                required=attribute.required,
            )
            for attribute in item.attributes
        ]
        class_def = OntologyClassDef(
            uri=f"{ontology_id}#{item.id}",
            label=item.name,
            description=item.description,
            examples=examples_by_class.get(item.id, []),
            parent_uri=(f"{ontology_id}#{item.parent_class_id}" if item.parent_class_id else None),
            properties=properties,
        )
        grouped.setdefault(module, []).append(class_def)
        id_to_label[item.id] = item.name

    return grouped, id_to_label


def _build_relation_definitions(
    relations: list[ExtractionOntologyRelation],
    class_labels: dict[str, str],
    ontology_examples: list[Any],
) -> list[Any]:
    """Convert ontology relation entries to extractor relation definitions."""
    from kgbuilder.extraction.relation import OntologyRelationDef

    examples_by_relation: dict[str, list[tuple[str, str]]] = {}
    for example in ontology_examples:
        if example.target_type != "relation":
            continue
        if example.subject_label and example.object_label:
            examples_by_relation.setdefault(example.target_id, []).append(
                (example.subject_label, example.object_label)
            )

    return [
        OntologyRelationDef(
            uri=relation.id,
            label=relation.name,
            description=relation.description,
            domain=[class_labels[relation.domain_class_id]]
            if relation.domain_class_id in class_labels
            else [],
            range=[class_labels[relation.range_class_id]]
            if relation.range_class_id in class_labels
            else [],
            is_functional=relation.cardinality == "many-to-one",
            examples=examples_by_relation.get(relation.id, []),
        )
        for relation in relations
    ]


def _result_sections(file_name: str, text: str) -> list[ExtractionSection]:
    """Split document text into stable section and paragraph response IDs."""
    paragraphs = [
        paragraph.strip() for paragraph in re.split(r"\n\s*\n", text.strip()) if paragraph.strip()
    ]
    if not paragraphs:
        return []
    return [
        ExtractionSection(
            id="section-1",
            title=file_name,
            paragraphs=[
                ExtractionParagraph(id=f"paragraph-{index}", content=paragraph)
                for index, paragraph in enumerate(paragraphs, start=1)
            ],
        )
    ]


def _build_results(
    request: ExtractionRequest,
    text: str,
    entities: list[Any],
    relations: list[Any],
    class_labels: dict[str, str],
) -> ExtractionResults:
    """Map internal extraction models to the requested external response shape."""
    sections = _result_sections(request.file.name, text)
    paragraphs = [(section, paragraph) for section in sections for paragraph in section.paragraphs]
    entity_ids = {entity.id: f"entity-{index}" for index, entity in enumerate(entities, start=1)}
    entity_results = [
        ExtractionEntityResult(
            temp_id=entity_ids[entity.id],
            text=entity.label,
            className=_entity_class_name(entity.entity_type, class_labels),
            attributes=[
                ExtractionEntityAttribute(
                    attribute_name=name,
                    value=value if isinstance(value, str) else str(value),
                )
                for name, value in entity.properties.items()
            ],
        )
        for entity in entities
    ]

    relation_name_by_id = {relation.id: relation.name for relation in request.ontology.relations}
    relation_by_id = {relation.id: relation for relation in request.ontology.relations}
    facts: list[ExtractionFact] = []
    for relation in relations:
        if (
            relation.source_entity_id not in entity_ids
            or relation.target_entity_id not in entity_ids
        ):
            continue

        subject = next(entity for entity in entities if entity.id == relation.source_entity_id)
        obj = next(entity for entity in entities if entity.id == relation.target_entity_id)
        matching_paragraph = next(
            (
                (section, paragraph)
                for section, paragraph in paragraphs
                if subject.label.lower() in paragraph.content.lower()
                and obj.label.lower() in paragraph.content.lower()
            ),
            None,
        )
        relation_text = relation_name_by_id.get(
            relation.predicate,
            relation.predicate.rsplit("#", maxsplit=1)[-1].rsplit("/", maxsplit=1)[-1],
        )
        evidence_text = (
            matching_paragraph[1].content
            if matching_paragraph
            else next(
                (evidence.text_span for evidence in relation.evidence if evidence.text_span),
                text,
            )
        )
        evidence_values: dict[str, Any] = {
            "quote": evidence_text,
            "sectionTitle": (
                matching_paragraph[0].title if matching_paragraph else request.file.name
            ),
            "paragraphId": matching_paragraph[1].id if matching_paragraph else None,
        }
        if (
            request.file.content_type.split(";", maxsplit=1)[0]
            .strip()
            .lower()
            .startswith("text/")
        ):
            evidence_values.update(pageFrom=1, pageTo=1)
        evidence = ExtractionEvidence(**evidence_values)

        definition = relation_by_id.get(relation.predicate)
        relation_id = definition.id if definition else relation.predicate
        facts.append(
            ExtractionFact(
                subject_temp_id=entity_ids[relation.source_entity_id],
                relation_text=relation_text,
                object_temp_id=entity_ids[relation.target_entity_id],
                subjectClassName=_entity_class_name(subject.entity_type, class_labels),
                objectClassName=_entity_class_name(obj.entity_type, class_labels),
                relationName=relation_id,
                confidence=relation.confidence,
                isCrossChapter=False,
                evidence=evidence,
            )
        )

    return ExtractionResults(sections=sections, entities=entity_results, facts=facts)


def _entity_class_name(entity_type: str, class_labels: dict[str, str]) -> str:
    """Resolve an extractor entity type to its ontology class display name."""
    if entity_type in class_labels.values():
        return entity_type
    local_name = entity_type.rsplit("#", maxsplit=1)[-1].rsplit("/", maxsplit=1)[-1]
    return class_labels.get(local_name, local_name)


def _update_run(run_id: str, **updates: Any) -> None:
    """Apply background-worker updates atomically."""
    with _runs_lock:
        if run_id in _runs:
            _runs[run_id].update(updates)


def _run_extraction(run_id: str, request: ExtractionRequest, file_bytes: bytes) -> None:
    """Execute module extraction and relation extraction in a background thread."""
    _update_run(run_id, progress=5)
    try:
        text = _load_document_text(request.file, file_bytes)
        _update_run(run_id, progress=15)

        from kgbuilder.agents.orchestrator_agent import ModuleBinding, OrchestratorAgent
        from kgbuilder.agents.question_generator import CQType
        from kgbuilder.api.dependencies import get_llm_provider
        from kgbuilder.extraction.entity import LLMEntityExtractor
        from kgbuilder.extraction.relation import LLMRelationExtractor

        modules, class_labels = _class_definitions(
            request.ontology_id,
            request.ontology.classes,
            request.ontology.modules,
            request.ontology.examples,
        )
        if not modules:
            raise ValueError("The ontology must contain at least one class")

        llm = get_llm_provider()
        extractor = LLMEntityExtractor(llm_provider=llm)
        retriever = _SubmittedDocumentRetriever(text)
        module_bindings = [
            ModuleBinding(
                module_name=module_name,
                ontology_classes=class_defs,
                retriever=retriever,
                extractor=extractor,
                questions=_module_questions(request, module_name, CQType),
            )
            for module_name, class_defs in modules.items()
        ]

        orchestrator = OrchestratorAgent()
        entities = orchestrator.run_modules(module_bindings)
        _update_run(run_id, progress=65)

        relation_definitions = _build_relation_definitions(
            request.ontology.relations,
            class_labels,
            request.ontology.examples,
        )
        relations = []
        relation_extractor = LLMRelationExtractor(llm_provider=llm)
        for paragraph in retriever.paragraphs:
            paragraph_entities = [
                entity for entity in entities if entity.label.lower() in paragraph.lower()
            ]
            relations.extend(
                relation_extractor.extract(
                    text=paragraph,
                    entities=paragraph_entities,
                    ontology_relations=relation_definitions,
                )
            )
        result = _build_results(request, text, entities, relations, class_labels)
        _update_run(
            run_id,
            status=ExtractionStatusValue.COMPLETED,
            progress=100,
            results=result,
        )
        logger.info(
            "extraction_completed",
            run_id=run_id,
            document_id=request.document_id,
            entities=len(result.entities),
            facts=len(result.facts),
        )
    except Exception as exc:
        logger.exception("extraction_failed", run_id=run_id, error=str(exc))
        _update_run(
            run_id,
            status=ExtractionStatusValue.FAILED,
            progress=100,
            error=str(exc),
        )


def _module_questions(
    request: ExtractionRequest,
    module_name: str,
    cq_type: Any,
) -> list[_ExtractionQuestion]:
    """Use ontology competency questions as module agent tasks when available."""
    module_ids = {module.id for module in request.ontology.modules if module.name == module_name}
    class_module = {
        ontology_class.id: ontology_class.module
        or next(
            (
                module.name
                for module in request.ontology.modules
                if module.id == ontology_class.module_id
            ),
            "General",
        )
        for ontology_class in request.ontology.classes
    }
    question_texts: list[str] = []
    for item in request.ontology.competency_questions:
        assigned_modules = {
            str(module.get("id", ""))
            for module in item.get("modules", [])
            if isinstance(module, dict)
        }
        assigned_modules.update(
            str(module.get("name", ""))
            for module in item.get("modules", [])
            if isinstance(module, dict)
        )
        subject_module = class_module.get(str(item.get("subjectClassId", "")))
        if (
            module_name not in assigned_modules
            and not module_ids.intersection(assigned_modules)
            and subject_module != module_name
        ):
            continue
        text = item.get("question")
        if isinstance(text, str) and text.strip():
            question_texts.append(text.strip())
    task = (
        "\n".join(question_texts)
        if question_texts
        else f"Extract entities for the {module_name} ontology module."
    )
    return [
        _ExtractionQuestion(
            text=task,
            entity_class=module_name,
            cq_type=cq_type.SCQ,
        )
    ]


def _require_api_key(authorization: str | None) -> None:
    """Authenticate GET endpoints using the configured Bearer key."""
    expected_key = os.getenv("KGBUILDER_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=503,
            detail="Extraction API key is not configured on this server",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="A Bearer API key is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    supplied_key = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied_key, expected_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/extract", response_model=ExtractionStartResponse)
async def start_extraction(request: ExtractionRequest) -> ExtractionStartResponse:
    """Start an asynchronous ontology-guided extraction run."""
    file_bytes = _get_file_bytes(request.file)
    _validate_file_format(request.file, file_bytes)

    with _runs_lock:
        if request.run_id in _runs:
            raise HTTPException(status_code=409, detail=f"Run {request.run_id} already exists")
        _runs[request.run_id] = {
            "status": ExtractionStatusValue.RUNNING,
            "progress": 0,
            "results": None,
            "error": None,
        }

    try:
        Thread(
            target=_run_extraction,
            args=(request.run_id, request, file_bytes),
            daemon=True,
        ).start()
    except Exception as exc:
        _update_run(
            request.run_id,
            status=ExtractionStatusValue.FAILED,
            progress=100,
            error=f"Could not start extraction worker: {exc}",
        )
        raise HTTPException(status_code=500, detail="Could not start extraction worker") from exc

    return ExtractionStartResponse(runId=request.run_id)


@router.get(
    "/extract/{run_id}/status",
    response_model=ExtractionStatusResponse,
)
async def get_extraction_status(
    run_id: str,
    authorization: str | None = Header(default=None),
) -> ExtractionStatusResponse:
    """Return extraction run status."""
    _require_api_key(authorization)
    with _runs_lock:
        run = _runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return ExtractionStatusResponse(
            runId=run_id,
            status=run["status"],
            progress=run["progress"],
        )


@router.get(
    "/extract/{run_id}/results",
    response_model=ExtractionResults,
    response_model_exclude_unset=True,
)
async def get_extraction_results(
    run_id: str,
    authorization: str | None = Header(default=None),
) -> ExtractionResults:
    """Return completed extraction results."""
    _require_api_key(authorization)
    with _runs_lock:
        run = _runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        if run["status"] == ExtractionStatusValue.RUNNING:
            raise HTTPException(status_code=409, detail="Extraction is still running")
        if run["status"] == ExtractionStatusValue.FAILED:
            raise HTTPException(
                status_code=500,
                detail=f"Extraction failed: {run['error']}",
            )
        results = run["results"]
        if not isinstance(results, ExtractionResults):
            raise HTTPException(
                status_code=500, detail="Completed extraction results are unavailable"
            )
        return results
