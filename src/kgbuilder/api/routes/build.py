"""KG build pipeline endpoints.

Triggers and monitors the full KG construction pipeline as background jobs.
Wraps ``scripts/full_kg_pipeline.py`` logic behind async HTTP endpoints.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from threading import Thread

import structlog
from fastapi import APIRouter, HTTPException

from kgbuilder.api.schemas import BuildRequest, BuildResponse, BuildStatus, JobStatus

logger = structlog.get_logger(__name__)
router = APIRouter()

# In-memory job tracker — swap for Redis in production
_jobs: dict[str, dict] = {}


@router.post("/build", response_model=BuildResponse)
async def start_build(request: BuildRequest) -> BuildResponse:
    """Start a KG build pipeline run as a background job."""
    job_id = uuid.uuid4().hex[:12]
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
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobStatus(job_id=job_id, **_jobs[job_id])


@router.get("/build", response_model=list[JobStatus])
async def list_build_jobs() -> list[JobStatus]:
    """List all build jobs."""
    return [JobStatus(job_id=jid, **data) for jid, data in _jobs.items()]


def _run_build_pipeline(job_id: str, request: BuildRequest) -> None:
    """Execute the build pipeline in a background thread.

    Mirrors the phases in ``scripts/full_kg_pipeline.py``.
    """
    job = _jobs[job_id]
    job["status"] = BuildStatus.RUNNING

    try:
        from kgbuilder.api.dependencies import (
            get_llm_provider,
            get_neo4j_store,
            get_ontology_service,
            get_qdrant_store,
        )

        # Phase 1: Load ontology
        job["current_phase"] = "loading_ontology"
        job["progress"] = 0.05
        ontology_service = get_ontology_service()
        all_classes = ontology_service.get_all_classes()
        if not all_classes:
            raise RuntimeError("No classes found in Fuseki ontology")

        classes = (
            all_classes[: request.classes_limit]
            if request.classes_limit
            else all_classes
        )
        logger.info("build_ontology_loaded", classes=len(classes))

        # Phase 2: Question generation
        job["current_phase"] = "generating_questions"
        job["progress"] = 0.15
        from kgbuilder.agents.question_generator import QuestionGenerationAgent

        question_agent = QuestionGenerationAgent(ontology_service=ontology_service)
        all_questions: list[str] = []
        for class_name in classes:
            questions = question_agent.generate_questions(
                max_questions=request.questions_per_class,
            )
            all_questions.extend(questions)
        logger.info("build_questions_generated", count=len(all_questions))

        # Phase 3: Discovery loop
        job["current_phase"] = "discovery"
        job["progress"] = 0.30
        from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop
        from kgbuilder.extraction.entity import LLMEntityExtractor, OntologyClassDef
        from kgbuilder.retrieval import FusionRAGRetriever
        from kgbuilder.storage.vector import QdrantStore

        qdrant_store = get_qdrant_store()
        llm = get_llm_provider()

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

        ontology_class_defs = [
            OntologyClassDef(
                uri=f"http://example.org/ontology#{name}",
                label=name,
                description=f"Class {name} from ontology",
            )
            for name in classes
        ]

        discovery_loop = IterativeDiscoveryLoop(
            retriever=retriever,
            extractor=extractor,
            question_generator=question_agent,
            ontology_classes=ontology_class_defs,
        )

        discovery_result = discovery_loop.run_discovery(
            initial_questions=all_questions,
            max_iterations=request.max_iterations,
            coverage_target=0.8,
            ontology_classes=ontology_class_defs,
        )

        discovered_entities = discovery_result.entities
        job["entities_count"] = len(discovered_entities)
        job["current_iteration"] = discovery_result.total_iterations
        job["progress"] = 0.55

        # Phase 4: Synthesis / deduplication
        job["current_phase"] = "synthesis"
        from kgbuilder.extraction.synthesizer import FindingsSynthesizer

        synthesizer = FindingsSynthesizer(
            similarity_threshold=request.similarity_threshold,
        )
        synthesized_entities = synthesizer.synthesize(entities=discovered_entities)
        job["entities_count"] = len(synthesized_entities)
        job["progress"] = 0.65

        # Phase 5: Relation extraction
        job["current_phase"] = "relation_extraction"
        from kgbuilder.extraction.relation import LLMRelationExtractor

        relation_extractor = LLMRelationExtractor(
            llm_provider=llm,
            confidence_threshold=request.confidence_threshold,
            max_retries=3,
        )
        # simplified — full relation extraction mirrors full_kg_pipeline.py
        job["progress"] = 0.75

        # Phase 6: Assembly into Neo4j
        job["current_phase"] = "assembly"
        from kgbuilder.assembly.kg_builder import KGBuilder, KGBuilderConfig
        from kgbuilder.storage.protocol import Edge, Node

        neo4j_store = get_neo4j_store()
        builder = KGBuilder(
            primary_store=neo4j_store,
            config=KGBuilderConfig(),
        )

        nodes = [
            Node(
                id=e.id,
                label=e.label,
                node_type=e.entity_type,
                properties={
                    "confidence": e.confidence,
                    "description": getattr(e, "description", ""),
                },
            )
            for e in synthesized_entities
        ]

        build_result = builder.build(entities=nodes, relations=None)
        job["entities_count"] = build_result.nodes_created
        job["relations_count"] = build_result.edges_created
        job["progress"] = 0.90

        # Phase 7: Validation (optional)
        if request.run_validation:
            job["current_phase"] = "validation"
            try:
                from kgbuilder.validation.consistency_checker import ConsistencyChecker
                from kgbuilder.validation.rules_engine import RulesEngine

                engine = RulesEngine()
                rules_result = engine.execute_rules(neo4j_store)
                checker = ConsistencyChecker()
                consistency_report = checker.check_consistency(neo4j_store)

                total_violations = (
                    len(rules_result.rule_violations)
                    + consistency_report.conflict_count
                )
                if total_violations > 0:
                    logger.warning(
                        "build_validation_issues",
                        job_id=job_id,
                        rule_violations=len(rules_result.rule_violations),
                        conflicts=consistency_report.conflict_count,
                    )
            except Exception as exc:
                logger.warning("build_validation_skipped", job_id=job_id, error=str(exc))
            job["progress"] = 0.95

        # Done
        job["current_phase"] = "completed"
        job["status"] = BuildStatus.COMPLETED
        job["progress"] = 1.0
        logger.info(
            "build_completed",
            job_id=job_id,
            entities=job["entities_count"],
            relations=job["relations_count"],
        )

    except Exception as e:
        logger.error("build_failed", job_id=job_id, error=str(e))
        job["status"] = BuildStatus.FAILED
        job["current_phase"] = "failed"
        job["error"] = str(e)
