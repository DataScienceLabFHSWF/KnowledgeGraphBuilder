"""Question generation agent for knowledge discovery.

Implementation of Issue #4.1: QuestionGenerationAgent

Generates strategic research questions by analyzing the ontology and identifying
coverage gaps. These questions guide the iterative discovery loop.
"""

from __future__ import annotations

import re
import structlog
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from kgbuilder.core.models import ExtractedEntity


@runtime_checkable
class OntologyService(Protocol):
    """Protocol for ontology query services."""

    def get_all_classes(self) -> list[str]:
        """Get all entity classes from ontology.

        Returns:
            List of class names
        """
        ...


logger = structlog.get_logger(__name__)


@dataclass
class ResearchQuestion:
    """A research question to guide discovery."""

    question_id: str
    text: str
    entity_class: str
    priority: float
    reason: str
    aspect: str = "existence"  # existence, properties, relations
    follow_up: bool = False  # Is this a follow-up from earlier findings?

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"Q[{self.priority:.2f}]: {self.text}\n"
            f"  Class: {self.entity_class}, Aspect: {self.aspect}"
        )


class QuestionGenerationAgent:
    """Generates research questions from ontology gaps.

    Strategy:
    1. Load ontology and identify all classes
    2. Calculate coverage: % of instances already extracted for each class
    3. Find under-covered classes (below threshold)
    4. Generate questions ranked by:
       - Class hierarchy level (parent classes first)
       - Class frequency (more important classes first)
       - Relation requirements (classes with many relations)
    5. Return prioritized question list
    """

    def __init__(
        self,
        ontology_service: OntologyService,
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> None:
        """Initialize question generator.

        Args:
            ontology_service: Service for loading and querying ontology
            existing_entities: Entities already extracted (for coverage calculation)
        """
        self._ontology = ontology_service
        self._existing = existing_entities or []
        self._logger = structlog.get_logger(__name__)

    def generate_questions(
        self,
        max_questions: int = 50,
        covered_threshold: float = 0.1,
        coverage_percentage_threshold: float = 0.8,
    ) -> list[ResearchQuestion]:
        """Generate prioritized research questions.

        Questions target under-covered classes in the ontology.
        Prioritized by class hierarchy and importance.

        Args:
            max_questions: Maximum questions to generate
            covered_threshold: Min # entities to consider class "covered" (absolute)
            coverage_percentage_threshold: Min coverage % before asking about class

        Returns:
            Sorted list of research questions (highest priority first)

        Raises:
            RuntimeError: If ontology service fails
        """
        self._logger.info(
            "question_generation_start",
            max_questions=max_questions,
            existing_entities=len(self._existing),
        )

        try:
            # 1. Get all classes from ontology
            all_classes = self._ontology.get_all_classes()
            if not all_classes:
                self._logger.warning("no_ontology_classes_found")
                return []

            self._logger.info("ontology_loaded", total_classes=len(all_classes))

            # 2. Calculate coverage for each class
            class_coverage = self._calculate_coverage(all_classes)
            self._logger.info(
                "coverage_calculated",
                covered_classes=sum(1 for c in class_coverage.values() if c >= 1),
                total_classes=len(class_coverage),
            )

            # 3. Find under-covered classes
            under_covered = [
                cls for cls, count in class_coverage.items()
                if count < covered_threshold
            ]

            if not under_covered:
                self._logger.info("all_classes_covered", total_classes=len(all_classes))
                return []

            self._logger.info(
                "under_covered_classes",
                count=len(under_covered),
                threshold=covered_threshold,
            )

            # 4. Generate questions for each under-covered class
            questions: list[ResearchQuestion] = []
            for class_name in under_covered[:max_questions]:
                question = self._generate_question_for_class(
                    class_name, class_coverage[class_name]
                )
                questions.append(question)

            # 5. Prioritize by importance
            prioritized = self._prioritize_questions(questions, all_classes)

            self._logger.info(
                "questions_generated",
                total=len(prioritized),
                top_3=[q.question_id for q in prioritized[:3]],
            )

            return prioritized

        except Exception as e:
            self._logger.error("question_generation_failed", error=str(e), exc_info=True)
            raise RuntimeError(f"Failed to generate questions: {e}") from e

    def _calculate_coverage(
        self, ontology_classes: list[str]
    ) -> dict[str, int]:
        """Calculate entity count per ontology class.

        Args:
            ontology_classes: All classes from ontology

        Returns:
            Dict mapping class name -> count of extracted entities
        """
        coverage: dict[str, int] = {cls: 0 for cls in ontology_classes}

        # Count entities by type
        for entity in self._existing:
            if entity.entity_type in coverage:
                coverage[entity.entity_type] += 1

        return coverage

    def _generate_question_for_class(
        self, class_name: str, current_count: int
    ) -> ResearchQuestion:
        """Generate a research question for an entity class.

        Args:
            class_name: Name of the ontology class
            current_count: Number of entities already extracted for this class

        Returns:
            Research question targeting this class
        """
        question_id = f"q_{self._sanitize_class_name(class_name)}"

        # Choose question template based on current coverage
        if current_count == 0:
            template = "What {pluralize}s are mentioned in the documents?"
            reason = "Class not yet covered"
            aspect = "existence"
        else:
            template = "What additional {pluralize}s can we find in the documents?"
            reason = f"Only {int(current_count)} {class_name} found so far"
            aspect = "expansion"

        # Format question text
        text = template.format(pluralize=class_name)

        # Calculate initial priority (will be re-ranked later)
        priority = 1.0 - (current_count / 10.0)  # Normalize to ~1.0 for uncovered
        priority = max(0.0, priority)

        return ResearchQuestion(
            question_id=question_id,
            text=text,
            entity_class=class_name,
            priority=priority,
            reason=reason,
            aspect=aspect,
        )

    def _prioritize_questions(
        self,
        questions: list[ResearchQuestion],
        ontology_classes: list[str],
    ) -> list[ResearchQuestion]:
        """Prioritize questions by importance.

        Ranking factors:
        1. Class hierarchy level (parents first)
        2. Class in relation domain (has relations)
        3. Alphabetical (tiebreaker)

        Args:
            questions: Generated questions to prioritize
            ontology_classes: All classes (for hierarchy lookup)

        Returns:
            Sorted questions by priority (highest first)
        """
        # Assign priority scores
        for question in questions:
            hierarchy_level = self._get_hierarchy_level(
                question.entity_class, ontology_classes
            )
            is_relation_domain = self._is_relation_domain(question.entity_class)
            has_relations = self._get_relation_count(question.entity_class)

            # Composite priority score:
            # - Hierarchy level (parents first): weight 0.5
            # - Has relations: weight 0.3
            # - Original priority: weight 0.2
            question.priority = (
                (1.0 - hierarchy_level / 10.0) * 0.5
                + (1.0 if is_relation_domain else 0.0) * 0.3
                + (1.0 if has_relations > 0 else 0.5) * 0.2
            )

        # Sort by priority descending
        sorted_questions = sorted(questions, key=lambda q: q.priority, reverse=True)

        return sorted_questions

    def _sanitize_class_name(self, class_name: str) -> str:
        """Convert class name to valid identifier.

        Args:
            class_name: Ontology class name

        Returns:
            Sanitized identifier (lowercase, alphanumeric + underscore)
        """
        # Convert to lowercase, remove non-alphanumeric
        sanitized = re.sub(r"[^a-z0-9]+", "_", class_name.lower())
        # Remove leading/trailing underscores
        sanitized = sanitized.strip("_")
        return sanitized

    def _get_hierarchy_level(
        self, class_name: str, ontology_classes: list[str]
    ) -> float:
        """Get hierarchy level of a class (0 for root, higher for deeper).

        Args:
            class_name: Class to check
            ontology_classes: All classes (not sufficient for full hierarchy)

        Returns:
            Hierarchy level (0 = root, ~0.5 = mid-level, ~1.0 = leaf)
        """
        # Simple heuristic: classes at beginning of alphabetical list tend to be root
        # In a real system, this would query the ontology directly for parent classes
        position = ontology_classes.index(class_name) if class_name in ontology_classes else 0
        level = position / max(len(ontology_classes), 1)
        return level

    def _is_relation_domain(self, class_name: str) -> bool:
        """Check if class is part of relation domain (has relations in ontology).

        Args:
            class_name: Class to check

        Returns:
            True if class participates in relations
        """
        # In real implementation, this would query the ontology for relations
        # For now, return True for most classes (assume they have relations)
        return True

    def _get_relation_count(self, class_name: str) -> int:
        """Get count of relations involving this class.

        Args:
            class_name: Class to check

        Returns:
            Number of relations this class participates in
        """
        # In real implementation, this would query the ontology
        # For now, return a default value
        return 1

    def generate_follow_up_questions(
        self,
        discoveries: list[ExtractedEntity],
        current_questions: list[ResearchQuestion],
        max_new_questions: int = 5,
    ) -> list[ResearchQuestion]:
        """Generate follow-up questions based on discovered entities.

        Follow-up questions ask about relationships and properties of discovered
        entities, enabling iterative discovery.

        Args:
            discoveries: Entities discovered in last iteration
            current_questions: Already-asked questions
            max_new_questions: Max follow-up questions to generate

        Returns:
            List of follow-up research questions
        """
        follow_ups: list[ResearchQuestion] = []
        asked_classes = {q.entity_class for q in current_questions}

        self._logger.info(
            "follow_up_generation_start",
            discoveries=len(discoveries),
            asked_classes=len(asked_classes),
        )

        # Extract new entity types from discoveries
        new_types = set(e.entity_type for e in discoveries)
        for entity_type in new_types:
            if entity_type not in asked_classes and len(follow_ups) < max_new_questions:
                # Create follow-up question about this newly discovered type
                q_id = f"followup_{self._sanitize_class_name(entity_type)}"
                follow_up = ResearchQuestion(
                    question_id=q_id,
                    text=f"How are {entity_type}s related to other discovered entities?",
                    entity_class=entity_type,
                    priority=0.9,  # High priority for follow-ups
                    reason=f"Newly discovered: {len([e for e in discoveries if e.entity_type == entity_type])} instances",
                    aspect="relations",
                    follow_up=True,
                )
                follow_ups.append(follow_up)

        self._logger.info(
            "follow_up_questions_generated",
            total=len(follow_ups),
        )

        return follow_ups
