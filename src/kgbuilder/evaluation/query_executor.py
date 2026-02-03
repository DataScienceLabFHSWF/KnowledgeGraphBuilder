"""Query execution for QA evaluation.

Executes questions against knowledge graphs and collects results.
Supports different query types (entity, relation, count, boolean, complex).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from kgbuilder.storage.protocol import GraphStore

logger = structlog.get_logger(__name__)


@dataclass
class QueryResult:
    """Result of executing a single question.

    Attributes:
        question_id: ID of the question
        question_text: Question text
        query_type: Type of query
        retrieved_answers: List of answers found in KG
        confidence_scores: Confidence score for each answer
        execution_time_ms: Query execution time in milliseconds
        error: Error message if query failed
        metadata: Additional metadata about the query
    """

    question_id: str
    question_text: str
    query_type: str
    retrieved_answers: list[str] = field(default_factory=list)
    confidence_scores: list[float] = field(default_factory=list)
    execution_time_ms: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_correct(self, expected_answers: list[str], similarity_threshold: float = 0.8) -> bool:
        """Check if at least one retrieved answer matches expected.

        Args:
            expected_answers: List of expected correct answers
            similarity_threshold: Similarity threshold for fuzzy matching

        Returns:
            True if any retrieved answer matches any expected answer
        """
        if not self.retrieved_answers:
            return False

        for retrieved in self.retrieved_answers:
            for expected in expected_answers:
                if self._string_similarity(retrieved, expected) >= similarity_threshold:
                    return True

        return False

    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """Compute string similarity (Levenshtein-based).

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity score (0.0-1.0)
        """
        s1_lower = s1.lower().strip()
        s2_lower = s2.lower().strip()

        if s1_lower == s2_lower:
            return 1.0

        # Simple character overlap similarity
        matches = sum(1 for c1, c2 in zip(s1_lower, s2_lower) if c1 == c2)
        max_len = max(len(s1_lower), len(s2_lower))

        return matches / max_len if max_len > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "query_type": self.query_type,
            "retrieved_answers": self.retrieved_answers,
            "confidence_scores": self.confidence_scores,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "error": self.error,
            "metadata": self.metadata,
        }


class QueryExecutor:
    """Execute questions against knowledge graphs.

    Supports different query types and handles both structured (SPARQL) and
    simple queries (entity/relation lookups).
    """

    def __init__(self, store: GraphStore) -> None:
        """Initialize query executor.

        Args:
            store: GraphStore to query against
        """
        self.store = store
        logger.info("query_executor_initialized", store_type=type(store).__name__)

    def execute(
        self,
        question_id: str,
        question_text: str,
        query_type: str,
        **kwargs: Any,
    ) -> QueryResult:
        """Execute a question against the KG.

        Args:
            question_id: ID of the question
            question_text: Question text
            query_type: Type of query ("entity", "relation", "count", "boolean", "complex")
            **kwargs: Query-specific parameters

        Returns:
            QueryResult with retrieved answers
        """
        start_time = time.time()

        try:
            if query_type == "entity":
                answers = self._execute_entity_query(question_text, kwargs)
            elif query_type == "relation":
                answers = self._execute_relation_query(question_text, kwargs)
            elif query_type == "count":
                answers = self._execute_count_query(question_text, kwargs)
            elif query_type == "boolean":
                answers = self._execute_boolean_query(question_text, kwargs)
            elif query_type == "complex":
                answers = self._execute_complex_query(question_text, kwargs)
            else:
                answers = []
                logger.warning("unknown_query_type", query_type=query_type)

            execution_time = (time.time() - start_time) * 1000

            logger.info(
                "query_executed",
                question_id=question_id,
                query_type=query_type,
                answer_count=len(answers),
                time_ms=execution_time,
            )

            return QueryResult(
                question_id=question_id,
                question_text=question_text,
                query_type=query_type,
                retrieved_answers=answers,
                confidence_scores=[1.0] * len(answers),
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000

            logger.error(
                "query_execution_failed",
                question_id=question_id,
                query_type=query_type,
                error=str(e),
            )

            return QueryResult(
                question_id=question_id,
                question_text=question_text,
                query_type=query_type,
                retrieved_answers=[],
                execution_time_ms=execution_time,
                error=str(e),
            )

    def _execute_entity_query(self, question: str, params: dict[str, Any]) -> list[str]:
        """Execute entity lookup query.

        Searches for entities matching the question.

        Args:
            question: Question text
            params: Query parameters (e.g., entity_name, entity_type)

        Returns:
            List of entity IDs/names found
        """
        try:
            # Simple approach: get all nodes and filter by label
            nodes = self.store.get_all_nodes()

            # Extract potential entity names from question
            # (simplified - in production would use NER or semantic parsing)
            question_words = question.lower().split()

            matching_nodes = []
            for node in nodes:
                if node.label:
                    node_label_lower = node.label.lower()
                    # Match if any word from question matches node label
                    for word in question_words:
                        if word in node_label_lower or node_label_lower in word:
                            matching_nodes.append(node.label)
                            break

            return matching_nodes[:10]  # Return top 10 matches

        except Exception as e:
            logger.warning("entity_query_failed", error=str(e))
            return []

    def _execute_relation_query(self, question: str, params: dict[str, Any]) -> list[str]:
        """Execute relation query.

        Finds relations between entities mentioned in the question.

        Args:
            question: Question text
            params: Query parameters (e.g., subject, relation, object)

        Returns:
            List of related entities
        """
        try:
            edges = self.store.get_all_edges()

            # Simple approach: extract entities and find edges between them
            # (simplified - in production would use semantic parsing)
            question_lower = question.lower()

            results = []
            for edge in edges:
                # Simple heuristic: match edge type to keywords in question
                edge_type_lower = edge.edge_type.lower()

                # Check if edge type appears in question
                if any(
                    keyword in question_lower
                    for keyword in edge_type_lower.split("_")
                ):
                    results.append(f"{edge.source_id}-{edge.edge_type}-{edge.target_id}")

            return results[:10]  # Return top 10 matches

        except Exception as e:
            logger.warning("relation_query_failed", error=str(e))
            return []

    def _execute_count_query(self, question: str, params: dict[str, Any]) -> list[str]:
        """Execute count query.

        Counts entities of a given type.

        Args:
            question: Question text
            params: Query parameters (e.g., entity_type)

        Returns:
            List with single count result
        """
        try:
            nodes = self.store.get_all_nodes()

            # Extract entity type from question
            # (simplified - in production would use semantic parsing)
            entity_type = params.get("entity_type", "")

            if entity_type:
                count = sum(1 for n in nodes if n.node_type == entity_type)
            else:
                count = len(nodes)

            return [str(count)]

        except Exception as e:
            logger.warning("count_query_failed", error=str(e))
            return []

    def _execute_boolean_query(self, question: str, params: dict[str, Any]) -> list[str]:
        """Execute boolean query.

        Checks if a fact exists in the KG.

        Args:
            question: Question text
            params: Query parameters (subject, relation, object)

        Returns:
            List with single "true" or "false" result
        """
        try:
            subject = params.get("subject", "")
            relation = params.get("relation", "")
            obj = params.get("object", "")

            if not (subject and relation and obj):
                return ["false"]

            # Check if edge exists
            edges = self.store.get_all_edges()

            for edge in edges:
                if (
                    edge.source_id == subject
                    and edge.edge_type == relation
                    and edge.target_id == obj
                ):
                    return ["true"]

            return ["false"]

        except Exception as e:
            logger.warning("boolean_query_failed", error=str(e))
            return ["false"]

    def _execute_complex_query(self, question: str, params: dict[str, Any]) -> list[str]:
        """Execute complex SPARQL query.

        Args:
            question: Question text
            params: Query parameters (sparql_query, etc.)

        Returns:
            Query results
        """
        try:
            sparql_query = params.get("sparql_query", "")

            if not sparql_query:
                logger.warning("no_sparql_query_provided")
                return []

            # Execute SPARQL query
            # (would depend on store supporting SPARQL)
            results = self.store.query(sparql_query)

            if hasattr(results, "records") and results.records:
                # Extract results from first variable
                results_list = []
                for record in results.records:
                    for value in record.values():
                        if value:
                            results_list.append(str(value))

                return results_list[:10]

            return []

        except Exception as e:
            logger.warning("complex_query_failed", error=str(e))
            return []
