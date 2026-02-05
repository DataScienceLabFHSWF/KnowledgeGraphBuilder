"""Iterative discovery loop for autonomous knowledge discovery.

Implementation of Issue #4.1: IterativeDiscoveryLoop

Orchestrates the discovery process:
1. For each research question:
   - Retrieve documents (FusionRAGRetriever)
   - Extract entities (EnsembleExtractor)
   - Track provenance
2. Synthesize findings
3. Generate follow-up questions
4. Iterate until coverage target reached
"""

from __future__ import annotations

import structlog
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from kgbuilder.agents.question_generator import QuestionGenerationAgent, ResearchQuestion
from kgbuilder.core.models import ExtractedEntity


logger = structlog.get_logger(__name__)


@runtime_checkable
class Retriever(Protocol):
    """Protocol for document retrieval implementations."""

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[Any]:
        """Retrieve documents for a query.

        Args:
            query: Search query text
            top_k: Number of results to return

        Returns:
            List of retrieval results with doc_id and content attributes
        """
        ...


@runtime_checkable
class EntityExtractor(Protocol):
    """Protocol for entity extraction implementations."""

    def extract(
        self,
        text: str,
        ontology_classes: list[Any] | None = None,
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Extract entities from text.

        Args:
            text: Source text to extract from
            ontology_classes: Valid entity types (optional)
            existing_entities: Known entities for deduplication (optional)

        Returns:
            List of extracted entities
        """
        ...


@dataclass
class IterationResult:
    """Results from one iteration of discovery."""

    iteration: int
    questions_processed: int
    entities_discovered: int
    total_entities: int
    coverage: float
    processing_time_sec: float
    new_entity_types: set[str] = field(default_factory=set)


@dataclass
class DiscoveryResult:
    """Complete results from discovery process."""

    success: bool
    total_iterations: int
    final_coverage: float
    total_entities_discovered: int
    total_time_sec: float
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[Any] = field(default_factory=list)  # NEW: Phase 5 relations
    iterations: list[IterationResult] = field(default_factory=list)
    error_message: str | None = None


class IterativeDiscoveryLoop:
    """Orchestrates iterative knowledge discovery.

    Process:
    1. Initialize: Load ontology and existing data
    2. Generate questions: Create list of discovery questions
    3. Iterate:
       a. Select next question
       b. Retrieve documents (FusionRAGRetriever)
       c. Extract entities (EnsembleExtractor)
       d. Update accumulated findings
       e. Track provenance
       f. Calculate coverage
       g. Generate follow-up questions
    4. Stop when:
       - Coverage target reached
       - Max iterations reached
       - No more questions
    5. Return consolidated findings
    """

    def __init__(
        self,
        retriever: Retriever,
        extractor: EntityExtractor,
        question_generator: QuestionGenerationAgent,
        ontology_classes: list[Any] | None = None,
        relation_extractor: Any | None = None,  # NEW: For Phase 5
        ontology_relations: list[Any] | None = None,  # NEW: For Phase 5
    ) -> None:
        """Initialize discovery loop.

        Args:
            retriever: Retriever implementation for document search
            extractor: EntityExtractor implementation for entity extraction
            question_generator: QuestionGenerationAgent for question generation
            ontology_classes: Optional list of ontology class definitions for extraction guidance
            relation_extractor: Optional RelationExtractor for Phase 5 (NEW)
            ontology_relations: Optional list of ontology relation definitions (NEW)
        """
        self._retriever = retriever
        self._extractor = extractor
        self._question_gen = question_generator
        self._ontology_classes = ontology_classes
        self._relation_extractor = relation_extractor  # NEW
        self._ontology_relations = ontology_relations  # NEW
        self._findings: dict[str, ExtractedEntity] = {}
        self._provenance: dict[str, set[str]] = {}  # entity_id -> source docs
        self._relations: list[Any] = []  # NEW: Store extracted relations
        self._logger = structlog.get_logger(__name__)

    def run_discovery(
        self,
        initial_questions: list[ResearchQuestion] | None = None,
        max_iterations: int = 5,
        coverage_target: float = 0.85,
        top_k_docs: int = 10,
        ontology_classes: list[Any] | None = None,
        extract_relations: bool = True,  # NEW: Phase 5 flag
    ) -> DiscoveryResult:
        """Run iterative discovery loop.

        Args:
            initial_questions: Starting questions (if None, generates from ontology)
            max_iterations: Maximum iterations to run
            coverage_target: Stop when coverage >= this threshold
            top_k_docs: Number of documents to retrieve per question
            ontology_classes: List of ontology class definitions for extraction guidance
            extract_relations: Whether to extract relations (Phase 5) during discovery (NEW)

        Returns:
            DiscoveryResult with all findings and metadata
        """
        start_time = time.time()
        
        # Use provided classes or fall back to instance variable
        classes_to_use = ontology_classes if ontology_classes is not None else self._ontology_classes

        self._logger.info(
            "discovery_start",
            max_iterations=max_iterations,
            coverage_target=coverage_target,
            top_k_docs=top_k_docs,
            ontology_classes_provided=classes_to_use is not None,
        )

        # Initialize
        self._findings = {}
        self._provenance = {}
        iterations: list[IterationResult] = []

        try:
            # Generate initial questions if not provided
            if initial_questions is None:
                self._logger.info("generating_initial_questions")
                initial_questions = self._question_gen.generate_questions(max_questions=20)

            current_questions = initial_questions
            iteration = 0
            coverage = 0.0

            while iteration < max_iterations and coverage < coverage_target:
                iteration += 1
                iter_start = time.time()

                self._logger.info(
                    "iteration_start",
                    iteration=iteration,
                    questions_to_process=len(current_questions),
                    current_coverage=f"{coverage:.2f}",
                )

                # Process questions in this iteration
                questions_processed = 0
                pre_iteration_count = len(self._findings)

                for question in current_questions:
                    self._process_question(question, top_k_docs, classes_to_use)
                    questions_processed += 1

                # Calculate coverage after this iteration
                entities_in_iteration = len(self._findings) - pre_iteration_count
                coverage = self._calculate_coverage()

                # Record iteration result
                new_types = set(e.entity_type for e in self._findings.values())
                iter_result = IterationResult(
                    iteration=iteration,
                    questions_processed=questions_processed,
                    entities_discovered=entities_in_iteration,
                    total_entities=len(self._findings),
                    coverage=coverage,
                    processing_time_sec=time.time() - iter_start,
                    new_entity_types=new_types,
                )
                iterations.append(iter_result)

                self._logger.info(
                    "iteration_complete",
                    iteration=iteration,
                    entities_found=entities_in_iteration,
                    total_entities=len(self._findings),
                    coverage=f"{coverage:.2f}",
                    time_sec=f"{iter_result.processing_time_sec:.2f}",
                )

                # Generate follow-up questions
                discoveries = [e for e in self._findings.values()]
                follow_ups = self._question_gen.generate_follow_up_questions(
                    discoveries=discoveries,
                    current_questions=current_questions,
                    max_new_questions=5,
                )

                # Check stopping criteria
                if coverage >= coverage_target:
                    self._logger.info(
                        "coverage_target_reached",
                        coverage=f"{coverage:.2f}",
                        target=f"{coverage_target:.2f}",
                    )
                    break

                if not follow_ups and len(current_questions) == 0:
                    self._logger.info("no_more_questions")
                    break

                # Update questions for next iteration
                current_questions = follow_ups if follow_ups else []

            # Final compilation
            total_time = time.time() - start_time
            final_entities = list(self._findings.values())

            result = DiscoveryResult(
                success=True,
                total_iterations=iteration,
                final_coverage=coverage,
                total_entities_discovered=len(final_entities),
                total_time_sec=total_time,
                entities=final_entities,
                relations=self._relations,  # NEW: Include Phase 5 relations
                iterations=iterations,
            )

            self._logger.info(
                "discovery_complete",
                success=True,
                iterations=iteration,
                entities=len(final_entities),
                relations=len(self._relations),  # NEW: Log relation count
                coverage=f"{coverage:.2f}",
                time_sec=f"{total_time:.2f}",
            )

            return result

        except Exception as e:
            total_time = time.time() - start_time
            self._logger.error(
                "discovery_failed",
                error=str(e),
                iterations=iteration,
                relations=len(self._relations),  # NEW: Log relations even on error
                time_sec=f"{total_time:.2f}",
                exc_info=True,
            )
            return DiscoveryResult(
                success=False,
                total_iterations=iteration,
                final_coverage=coverage,
                total_entities_discovered=len(self._findings),
                total_time_sec=total_time,
                entities=list(self._findings.values()),
                relations=self._relations,  # NEW: Return partial relations
                iterations=iterations,
                error_message=str(e),
            )

    def _process_question(
        self,
        question: ResearchQuestion,
        top_k_docs: int,
        ontology_classes: list[Any] | None = None,
    ) -> None:
        """Process a single research question.

        Steps:
        1. Retrieve relevant documents
        2. Extract entities from documents
        3. Update accumulated findings
        4. Track provenance

        Args:
            question: Research question to process
            top_k_docs: Number of documents to retrieve
            ontology_classes: Optional list of ontology classes for extraction guidance
        """
        self._logger.info(
            "processing_question",
            question_id=question.question_id,
            question=question.text,
        )

        try:
            # 1. Retrieve documents using FusionRAG
            retrieved = self._retriever.retrieve(
                query=question.text,
                top_k=top_k_docs,
            )

            self._logger.info(
                "documents_retrieved",
                question_id=question.question_id,
                doc_count=len(retrieved),
            )

            # 2. Extract entities from each document
            for result in retrieved:
                try:
                    # Extract entities from this document with ontology guidance
                    entities = self._extractor.extract(
                        text=result.content,
                        ontology_classes=ontology_classes
                    )

                    # 3. Update findings and provenance
                    for entity in entities:
                        if entity.id not in self._findings:
                            self._findings[entity.id] = entity
                            self._provenance[entity.id] = set()

                        # Update provenance
                        self._provenance[entity.id].add(result.doc_id)

                        # Update confidence if higher
                        if entity.confidence > self._findings[entity.id].confidence:
                            self._findings[entity.id] = entity

                    # 4. Extract relations from the text (NEW - Phase 5)
                    if extract_relations and self._relation_extractor and self._ontology_relations and entities:
                        try:
                            relations = self._relation_extractor.extract(
                                text=result.content,
                                entities=entities,
                                ontology_relations=self._ontology_relations
                            )
                            self._relations.extend(relations)
                            
                            if relations:
                                self._logger.debug(
                                    "relations_extracted_from_document",
                                    question_id=question.question_id,
                                    doc_id=result.doc_id,
                                    relation_count=len(relations),
                                )
                        except Exception as e:
                            self._logger.debug(
                                "relation_extraction_failed_for_document",
                                question_id=question.question_id,
                                doc_id=result.doc_id,
                                error=str(e),
                            )
                            # Continue on relation extraction failure (don't block entity success)
                    
                    self._logger.debug(
                        "extracted_from_document",
                        question_id=question.question_id,
                        doc_id=result.doc_id,
                        entity_count=len(entities),
                    )

                except Exception as e:
                    self._logger.warning(
                        "extraction_failed_for_document",
                        question_id=question.question_id,
                        doc_id=result.doc_id,
                    )
                    continue

        except Exception as e:
            self._logger.error(
                "question_processing_failed",
                question_id=question.question_id,
            )
            import traceback
            traceback.print_exc()

    def _calculate_coverage(self) -> float:
        """Calculate coverage of ontology classes.

        Coverage = (# of entity types found) / (total ontology classes)

        Returns:
            Coverage percentage (0.0-1.0)
        """
        if not self._findings:
            return 0.0

        # Count unique entity types
        entity_types = set(e.entity_type for e in self._findings.values())

        # Get total ontology classes
        all_classes = self._question_gen._ontology.get_all_classes()

        # Calculate coverage
        if not all_classes:
            return 0.0

        coverage = len(entity_types & set(all_classes)) / len(all_classes)
        return min(coverage, 1.0)

    def get_provenance(self, entity_id: str) -> set[str]:
        """Get source documents for an entity.

        Args:
            entity_id: Entity ID to look up

        Returns:
            Set of source document IDs
        """
        return self._provenance.get(entity_id, set())

    def get_findings_by_type(self, entity_type: str) -> list[ExtractedEntity]:
        """Get all findings of a specific type.

        Args:
            entity_type: Entity type to filter by

        Returns:
            List of entities of that type
        """
        return [
            e for e in self._findings.values()
            if e.entity_type == entity_type
        ]
