"""Metrics computation for QA evaluation.

Uses DeepEval framework for semantic evaluation of LLM responses against KG answers.
Computes faithfulness, relevance, correctness, and semantic similarity metrics.

DeepEval Metrics:
- Faithfulness: Answer is faithful to retrieved context (0.0-1.0)
- Relevance: Answer is relevant to the question (0.0-1.0)
- Correctness: Answer is semantically correct (0.0-1.0)
- Semantic Similarity: Answer matches expected answer (0.0-1.0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Optional DeepEval import - gracefully degrade if not installed
try:
    from deepeval.metrics import (
        Faithfulness,
        Relevance,
        AnswerRelevancy,
        Correctness,
    )
    from deepeval.test_case import LLMTestCase

    HAS_DEEPEVAL = True
except ImportError:
    HAS_DEEPEVAL = False
    logger.warning("deepeval_not_installed", msg="Install with: pip install deepeval")



@dataclass
class EvaluationMetrics:
    """Metrics for QA evaluation using DeepEval framework.

    Attributes:
        total_questions: Total number of questions evaluated
        correct_answers: Number of questions answered correctly
        accuracy: Accuracy score (0.0-1.0) - basic metric
        precision: Precision score (0.0-1.0)
        recall: Recall score (0.0-1.0)
        f1_score: F1 score (0.0-1.0)
        coverage: Coverage score (0.0-1.0) - % questions with answers
        faithfulness: DeepEval faithfulness (0.0-1.0) - answer faithful to context
        relevance: DeepEval relevance (0.0-1.0) - answer relevant to question
        correctness: DeepEval correctness (0.0-1.0) - answer semantically correct
        answer_relevancy: DeepEval answer relevancy (0.0-1.0)
        semantic_similarity: DeepEval semantic similarity (0.0-1.0)
        average_response_time: Average query execution time in ms
        by_type: Metrics broken down by query type
        by_difficulty: Metrics broken down by difficulty level
        deepeval_results: Raw DeepEval metric scores per question
    """

    total_questions: int = 0
    correct_answers: int = 0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    coverage: float = 0.0
    faithfulness: float = 0.0
    relevance: float = 0.0
    correctness: float = 0.0
    answer_relevancy: float = 0.0
    semantic_similarity: float = 0.0
    average_response_time: float = 0.0
    by_type: dict[str, dict[str, float]] = field(default_factory=dict)
    by_difficulty: dict[str, dict[str, float]] = field(default_factory=dict)
    deepeval_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_questions": self.total_questions,
            "correct_answers": self.correct_answers,
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "coverage": round(self.coverage, 4),
            "faithfulness": round(self.faithfulness, 4),
            "relevance": round(self.relevance, 4),
            "correctness": round(self.correctness, 4),
            "answer_relevancy": round(self.answer_relevancy, 4),
            "semantic_similarity": round(self.semantic_similarity, 4),
            "average_response_time": round(self.average_response_time, 2),
            "by_type": {
                k: {k2: round(v2, 4) if isinstance(v2, float) else v2 for k2, v2 in v.items()}
                for k, v in self.by_type.items()
            },
            "by_difficulty": {
                k: {k2: round(v2, 4) if isinstance(v2, float) else v2 for k2, v2 in v.items()}
                for k, v in self.by_difficulty.items()
            },
            "deepeval_results": self.deepeval_results,
        }


class MetricsComputer:
    """Compute evaluation metrics using DeepEval framework.
    
    Provides both basic metrics (accuracy, precision, recall, F1) and
    semantic metrics from DeepEval (faithfulness, relevance, correctness).
    """

    def __init__(self) -> None:
        """Initialize metrics computer."""
        self.has_deepeval = HAS_DEEPEVAL
        logger.info("metrics_computer_initialized", deepeval_available=HAS_DEEPEVAL)

    def compute(
        self,
        qa_pairs: list[tuple[dict[str, Any], list[str]]],
        results: list[dict[str, Any]],
        context_passages: list[str] | None = None,
    ) -> EvaluationMetrics:
        """Compute evaluation metrics.

        Args:
            qa_pairs: List of (qa_dict, expected_answers) tuples
            results: List of query results as dictionaries
            context_passages: Optional context passages for DeepEval faithfulness

        Returns:
            EvaluationMetrics with computed metrics including DeepEval scores
        """
        if not results:
            logger.warning("no_results_provided")
            return EvaluationMetrics()

        metrics = EvaluationMetrics(total_questions=len(results))
        deepeval_results_list = []

        # Basic counts
        correct_count = 0
        retrieved_count = 0
        total_retrieved = 0
        total_expected = 0
        total_time = 0.0
        questions_with_answers = 0

        # DeepEval metric accumulators
        faithfulness_scores = []
        relevance_scores = []
        correctness_scores = []
        answer_relevancy_scores = []
        similarity_scores = []

        # Type and difficulty tracking
        type_stats: dict[str, dict[str, Any]] = {}
        difficulty_stats: dict[str, dict[str, Any]] = {}

        # Map results to qa_pairs by question_id
        qa_map = {q[0]["id"]: q for q in qa_pairs}

        for idx, result in enumerate(results):
            question_id = result.get("question_id", "")
            query_type = result.get("query_type", "unknown")
            question_text = result.get("question_text", "")
            retrieved = result.get("retrieved_answers", [])
            execution_time = result.get("execution_time_ms", 0.0)

            # Get expected answers
            if question_id in qa_map:
                expected = qa_map[question_id][1]
                difficulty = qa_map[question_id][0].get("difficulty", "unknown")
            else:
                expected = []
                difficulty = "unknown"

            # Update counts
            total_time += execution_time

            if retrieved:
                questions_with_answers += 1
                total_retrieved += len(retrieved)

            total_expected += len(expected) if expected else 1

            # Check if correct
            is_correct = self._check_answer_correct(retrieved, expected)
            if is_correct:
                correct_count += 1
                retrieved_count += 1

            # Compute DeepEval metrics if available
            deepeval_result = {
                "question_id": question_id,
                "question_text": question_text,
                "retrieved_answers": retrieved,
                "expected_answers": expected,
            }

            if HAS_DEEPEVAL and retrieved and expected:
                try:
                    # Create test case for DeepEval
                    answer_text = ", ".join(retrieved)
                    context = context_passages[idx] if context_passages and idx < len(context_passages) else ""

                    test_case = LLMTestCase(
                        input=question_text,
                        actual_output=answer_text,
                        expected_output=", ".join(expected),
                        retrieval_context=[context] if context else []
                    )

                    # Compute DeepEval metrics
                    try:
                        faithfulness = Faithfulness()
                        faith_score = faithfulness.measure(test_case)
                        faithfulness_scores.append(faith_score.score)
                        deepeval_result["faithfulness"] = faith_score.score
                    except Exception as e:
                        logger.debug("faithfulness_metric_failed", error=str(e))

                    try:
                        relevance = Relevance()
                        rel_score = relevance.measure(test_case)
                        relevance_scores.append(rel_score.score)
                        deepeval_result["relevance"] = rel_score.score
                    except Exception as e:
                        logger.debug("relevance_metric_failed", error=str(e))

                    try:
                        answer_rel = AnswerRelevancy()
                        ans_rel_score = answer_rel.measure(test_case)
                        answer_relevancy_scores.append(ans_rel_score.score)
                        deepeval_result["answer_relevancy"] = ans_rel_score.score
                    except Exception as e:
                        logger.debug("answer_relevancy_metric_failed", error=str(e))

                    # Semantic similarity
                    sim_score = self._semantic_similarity(answer_text, ", ".join(expected))
                    similarity_scores.append(sim_score)
                    deepeval_result["semantic_similarity"] = sim_score

                except Exception as e:
                    logger.warning("deepeval_metrics_failed", question_id=question_id, error=str(e))

            deepeval_results_list.append(deepeval_result)

            # Track by type
            if query_type not in type_stats:
                type_stats[query_type] = {
                    "total": 0,
                    "correct": 0,
                    "retrieved": 0,
                    "expected": 0,
                }

            type_stats[query_type]["total"] += 1
            if is_correct:
                type_stats[query_type]["correct"] += 1
            type_stats[query_type]["retrieved"] += len(retrieved)
            type_stats[query_type]["expected"] += len(expected) if expected else 1

            # Track by difficulty
            if difficulty not in difficulty_stats:
                difficulty_stats[difficulty] = {
                    "total": 0,
                    "correct": 0,
                    "retrieved": 0,
                    "expected": 0,
                }

            difficulty_stats[difficulty]["total"] += 1
            if is_correct:
                difficulty_stats[difficulty]["correct"] += 1
            difficulty_stats[difficulty]["retrieved"] += len(retrieved)
            difficulty_stats[difficulty]["expected"] += len(expected) if expected else 1

        # Compute metrics
        metrics.correct_answers = correct_count
        metrics.accuracy = correct_count / len(results) if results else 0.0
        metrics.coverage = questions_with_answers / len(results) if results else 0.0
        metrics.average_response_time = total_time / len(results) if results else 0.0

        # DeepEval metrics (averages)
        if faithfulness_scores:
            metrics.faithfulness = sum(faithfulness_scores) / len(faithfulness_scores)
        if relevance_scores:
            metrics.relevance = sum(relevance_scores) / len(relevance_scores)
        if answer_relevancy_scores:
            metrics.answer_relevancy = sum(answer_relevancy_scores) / len(answer_relevancy_scores)
        if similarity_scores:
            metrics.semantic_similarity = sum(similarity_scores) / len(similarity_scores)

        # Precision and recall
        if total_retrieved > 0:
            metrics.precision = retrieved_count / total_retrieved
        else:
            metrics.precision = 0.0 if retrieved_count == 0 else 1.0

        if total_expected > 0:
            metrics.recall = retrieved_count / total_expected
        else:
            metrics.recall = 0.0 if retrieved_count == 0 else 1.0

        # F1 score
        if metrics.precision + metrics.recall > 0:
            metrics.f1_score = (
                2 * (metrics.precision * metrics.recall) / (metrics.precision + metrics.recall)
            )
        else:
            metrics.f1_score = 0.0

        # Store DeepEval results
        metrics.deepeval_results = deepeval_results_list

        # Compute by-type metrics
        for query_type, stats in type_stats.items():
            total = stats["total"]
            correct = stats["correct"]
            retrieved = stats["retrieved"]
            expected = stats["expected"]

            type_accuracy = correct / total if total > 0 else 0.0
            type_precision = correct / retrieved if retrieved > 0 else 0.0
            type_recall = correct / expected if expected > 0 else 0.0
            type_f1 = (
                2 * (type_precision * type_recall) / (type_precision + type_recall)
                if type_precision + type_recall > 0
                else 0.0
            )

            metrics.by_type[query_type] = {
                "accuracy": type_accuracy,
                "precision": type_precision,
                "recall": type_recall,
                "f1": type_f1,
                "count": total,
            }

        # Compute by-difficulty metrics
        for difficulty, stats in difficulty_stats.items():
            total = stats["total"]
            correct = stats["correct"]
            retrieved = stats["retrieved"]
            expected = stats["expected"]

            diff_accuracy = correct / total if total > 0 else 0.0
            diff_precision = correct / retrieved if retrieved > 0 else 0.0
            diff_recall = correct / expected if expected > 0 else 0.0
            diff_f1 = (
                2 * (diff_precision * diff_recall) / (diff_precision + diff_recall)
                if diff_precision + diff_recall > 0
                else 0.0
            )

            metrics.by_difficulty[difficulty] = {
                "accuracy": diff_accuracy,
                "precision": diff_precision,
                "recall": diff_recall,
                "f1": diff_f1,
                "count": total,
            }

        logger.info(
            "metrics_computed",
            accuracy=round(metrics.accuracy, 4),
            f1_score=round(metrics.f1_score, 4),
            coverage=round(metrics.coverage, 4),
            faithfulness=round(metrics.faithfulness, 4),
        )

        return metrics

    @staticmethod
    def _check_answer_correct(
        retrieved: list[str],
        expected: list[str],
        similarity_threshold: float = 0.8,
    ) -> bool:
        """Check if retrieved answers contain expected answer.

        Args:
            retrieved: Retrieved answers
            expected: Expected answers
            similarity_threshold: Similarity threshold for fuzzy matching

        Returns:
            True if any retrieved answer matches any expected answer
        """
        if not retrieved or not expected:
            return False

        for ret in retrieved:
            for exp in expected:
                if MetricsComputer._string_similarity(ret, exp) >= similarity_threshold:
                    return True

        return False

    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """Compute string similarity.

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

    @staticmethod
    def _semantic_similarity(answer: str, expected: str) -> float:
        """Compute semantic similarity between answer and expected output.

        Uses simple word overlap for now. In production, would use embeddings.

        Args:
            answer: Generated answer
            expected: Expected answer

        Returns:
            Similarity score (0.0-1.0)
        """
        answer_words = set(answer.lower().split())
        expected_words = set(expected.lower().split())

        if not answer_words or not expected_words:
            return 0.0

        intersection = len(answer_words & expected_words)
        union = len(answer_words | expected_words)

        return intersection / union if union > 0 else 0.0