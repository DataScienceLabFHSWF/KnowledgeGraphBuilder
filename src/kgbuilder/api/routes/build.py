"""KG build pipeline endpoints.

Triggers and monitors the full KG construction pipeline as background jobs.
Wraps ``scripts/full_kg_pipeline.py`` logic behind async HTTP endpoints.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from threading import Lock, Thread

import structlog
from fastapi import APIRouter, HTTPException

from kgbuilder.api.schemas import BuildRequest, BuildResponse, BuildStatus, JobStatus

logger = structlog.get_logger(__name__)
router = APIRouter()

# In-memory job tracker — swap for Redis in production
_jobs: dict[str, dict] = {}
_jobs_lock = Lock()


@router.post("/build", response_model=BuildResponse)
async def start_build(request: BuildRequest) -> BuildResponse:
    """Start a KG build pipeline run as a background job."""
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "status": BuildStatus.PENDING,
            "progress": 0.0,
            "current_phase": "initializing",
            "entities_count": 0,
            "relations_count": 0,
            "current_iteration": 0,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "error": None,
        }

    thread = Thread(
        target=_run_build_pipeline,
        args=(job_id, request),
        daemon=True,
    )
    thread.start()

    return BuildResponse(
        job_id=job_id,
        status=BuildStatus.PENDING,
        message="Build pipeline started",
    )


@router.get("/build/{job_id}", response_model=JobStatus)
async def get_build_status(job_id: str) -> JobStatus:
    """Check status of a build job."""
    with _jobs_lock:
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        job_data = dict(_jobs[job_id])
    return JobStatus(job_id=job_id, **job_data)


@router.get("/build", response_model=list[JobStatus])
async def list_build_jobs() -> list[JobStatus]:
    """List all build jobs."""
    with _jobs_lock:
        jobs = [(job_id, dict(data)) for job_id, data in _jobs.items()]
    return [JobStatus(job_id=job_id, **data) for job_id, data in jobs]


def _run_build_pipeline(job_id: str, request: BuildRequest) -> None:
    """Run the markdown-defined, skill-composed KG build in a worker thread."""
    try:
        from kgbuilder.agents.markdown_pipeline import load_pipeline
        from kgbuilder.agents.pipeline_agent import PipelineAgent, PipelineStep
        from kgbuilder.api.dependencies import (
            get_llm_provider,
            get_neo4j_store,
            get_ontology_service,
            get_qdrant_store,
        )
        from kgbuilder.assembly.kg_builder import KGBuilder, KGBuilderConfig
        from kgbuilder.extraction.entity import LLMEntityExtractor, OntologyClassDef
        from kgbuilder.extraction.relation import LLMRelationExtractor, OntologyRelationDef
        from kgbuilder.extraction.synthesizer import FindingsSynthesizer
        from kgbuilder.retrieval import FusionRAGRetriever

        _update_job(job_id, status=BuildStatus.RUNNING, current_phase="loading_resources", progress=0.02)
        ontology_service = get_ontology_service()
        all_classes = ontology_service.get_all_classes()
        if not all_classes:
            raise RuntimeError("No classes found in Fuseki ontology")

        module_map = ontology_service.get_module_class_map()
        if not module_map:
            module_map = {"Ontology": all_classes}
        if request.classes_limit is not None:
            selected_classes = {name.lower() for name in all_classes[:request.classes_limit]}
            module_map = {
                module: [name for name in names if name.lower() in selected_classes]
                for module, names in module_map.items()
            }
            module_map = {module: names for module, names in module_map.items() if names}
        if not module_map:
            raise RuntimeError("No ontology classes remain after applying classes_limit")
        classes = [class_name for module_classes in module_map.values() for class_name in module_classes]

        _update_job(job_id, progress=0.08)
        llm = get_llm_provider()
        qdrant_store = get_qdrant_store()
        retriever = FusionRAGRetriever(
            qdrant_store=qdrant_store,
            llm_provider=llm,
            dense_weight=request.dense_weight,
            sparse_weight=request.sparse_weight,
            top_k=request.top_k,
        )
        extractor = LLMEntityExtractor(
            llm_provider=llm,
            confidence_threshold=request.confidence_threshold,
            max_retries=3,
        )
        class_definition_by_name = {
            name: OntologyClassDef(
                uri=f"http://example.org/ontology#{name}",
                label=name,
                description=ontology_service.get_class_description(name) or "",
            )
            for name in classes
        }
        class_definitions = {
            module: [class_definition_by_name[name] for name in module_classes]
            for module, module_classes in module_map.items()
        }
        ontology_relations = [
            OntologyRelationDef(uri=relation, label=relation)
            for relation in ontology_service.get_all_relations()
        ]
        relation_extractor = LLMRelationExtractor(
            llm_provider=llm,
            confidence_threshold=request.confidence_threshold,
            max_retries=3,
        )
        synthesizer = FindingsSynthesizer(
            similarity_threshold=request.similarity_threshold,
        )
        neo4j_store = get_neo4j_store()
        builder = KGBuilder(
            primary_store=neo4j_store,
            config=KGBuilderConfig(),
        )
        from kgbuilder.agents.question_generator import QuestionGenerationAgent

        question_agent = QuestionGenerationAgent(ontology_service=ontology_service)
        pipeline_path = Path(__file__).resolve().parents[4] / "agentic_pipeline" / "build_pipeline.md"
        steps = load_pipeline(pipeline_path)
        steps = [
            PipelineStep(
                id=step.id,
                skill=step.skill,
                kwargs={
                    **step.kwargs,
                    **(
                        {
                            "max_questions": max(
                                1,
                                request.questions_per_class * len(classes),
                            )
                        }
                        if step.id == "questions"
                        else {}
                    ),
                    **(
                        {"top_k": request.top_k}
                        if step.skill in {"module_extraction_batch", "relation_extraction_batch"}
                        else {}
                    ),
                },
                bind=step.bind,
                inputs=step.inputs,
            )
            for step in steps
        ]
        agent = PipelineAgent(
            bindings={
                "question_generation_agent": question_agent,
                "class_filter": classes,
                "module_map": module_map,
                "class_definitions": class_definitions,
                "retriever": retriever,
                "extractor": extractor,
                "entity_extractor": extractor,
                "relation_extractor": relation_extractor,
                "ontology_relations": ontology_relations,
                "synthesizer": synthesizer,
                "graph_builder": builder,
                "graph_store": neo4j_store,
                "run_validation": request.run_validation,
                "job_id": job_id,
            }
        )

        completed_steps = 0

        def update_progress(
            step: PipelineStep,
            state: str,
            result: object | None,
            iteration: int,
        ) -> None:
            nonlocal completed_steps
            if state == "completed":
                completed_steps += 1
            progress = min(
                0.1 + 0.85 * completed_steps / (len(steps) * request.max_iterations),
                0.98,
            )
            phase = step.id or step.skill
            updates: dict[str, object] = {
                "current_phase": phase if state != "failed" else f"{phase}_failed",
                "progress": progress,
                "current_iteration": iteration,
            }
            if state == "completed" and step.id == "entities":
                updates["entities_count"] = len(result) if isinstance(result, list) else 0
            elif state == "completed" and step.id == "assembly":
                updates["entities_count"] = getattr(result, "nodes_created", 0)
                updates["relations_count"] = getattr(result, "edges_created", 0)
            _update_job(job_id, **updates)

        agent.run_plan(
            steps,
            on_step=update_progress,
            iterations=request.max_iterations,
            stop_if_empty="questions",
        )
        _update_job(
            job_id,
            status=BuildStatus.COMPLETED,
            current_phase="completed",
            progress=1.0,
        )
        logger.info(
            "build_completed",
            job_id=job_id,
            entities=_jobs[job_id]["entities_count"],
            relations=_jobs[job_id]["relations_count"],
        )

    except Exception as exc:
        logger.exception("build_failed", job_id=job_id, error=str(exc))
        _update_job(
            job_id,
            status=BuildStatus.FAILED,
            current_phase="failed",
            error=str(exc),
        )


def _update_job(job_id: str, **updates: object) -> None:
    """Update job state under the shared jobs lock."""
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(updates)
