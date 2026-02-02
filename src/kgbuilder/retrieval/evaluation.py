"""Retrieval evaluation metrics for Phase 2 comparison.

Metrics:
- Recall@k: Is correct doc in top-k results?
- Precision@k: What fraction of top-k are relevant?
- NDCG: Ranking quality
- MRR: Mean reciprocal rank
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RetrievalMetrics:
    """Metrics for retrieval evaluation."""

    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    precision_at_10: float
    ndcg_at_10: float
    mrr: float
    avg_rank_of_relevant: float | None = None


def compute_recall(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Compute recall@k.
    
    Args:
        retrieved_ids: List of retrieved document IDs
        relevant_ids: Set of relevant document IDs
        k: Cutoff position
        
    Returns:
        Recall@k (0-1)
    """
    if not relevant_ids:
        return 0.0

    retrieved_relevant = set(retrieved_ids[:k]) & relevant_ids
    return len(retrieved_relevant) / len(relevant_ids)


def compute_precision(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Compute precision@k.
    
    Args:
        retrieved_ids: List of retrieved document IDs
        relevant_ids: Set of relevant document IDs
        k: Cutoff position
        
    Returns:
        Precision@k (0-1)
    """
    if k == 0:
        return 0.0

    retrieved_relevant = set(retrieved_ids[:k]) & relevant_ids
    return len(retrieved_relevant) / k


def compute_ndcg(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
    scores: list[float] | None = None,
) -> float:
    """Compute NDCG@k (normalized discounted cumulative gain).
    
    Args:
        retrieved_ids: List of retrieved document IDs
        relevant_ids: Set of relevant document IDs
        k: Cutoff position
        scores: Optional relevance scores (if None, assumes binary relevance)
        
    Returns:
        NDCG@k (0-1)
    """
    # DCG: sum of relevance scores discounted by position
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k]):
        relevance = 1.0 if doc_id in relevant_ids else 0.0
        if scores and i < len(scores):
            relevance = scores[i] if doc_id in relevant_ids else 0.0
        dcg += relevance / np.log2(i + 2)  # i+2 because positions are 1-indexed

    # IDCG: ideal DCG (all relevant docs at top)
    idcg = 0.0
    for i in range(min(len(relevant_ids), k)):
        idcg += 1.0 / np.log2(i + 2)

    if idcg == 0:
        return 0.0
    return dcg / idcg


def compute_mrr(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """Compute MRR (mean reciprocal rank).
    
    Args:
        retrieved_ids: List of retrieved document IDs
        relevant_ids: Set of relevant document IDs
        
    Returns:
        MRR (0-1)
    """
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def evaluate_retrieval(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> RetrievalMetrics:
    """Evaluate retrieval performance.
    
    Args:
        retrieved_ids: List of retrieved document IDs (in rank order)
        relevant_ids: Set of relevant document IDs
        
    Returns:
        RetrievalMetrics dataclass
    """
    recall_5 = compute_recall(retrieved_ids, relevant_ids, 5)
    recall_10 = compute_recall(retrieved_ids, relevant_ids, 10)
    precision_5 = compute_precision(retrieved_ids, relevant_ids, 5)
    precision_10 = compute_precision(retrieved_ids, relevant_ids, 10)
    ndcg_10 = compute_ndcg(retrieved_ids, relevant_ids, 10)
    mrr = compute_mrr(retrieved_ids, relevant_ids)

    # Find average rank of relevant documents
    relevant_ranks = []
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_ids:
            relevant_ranks.append(i + 1)

    avg_rank = sum(relevant_ranks) / len(relevant_ranks) if relevant_ranks else None

    return RetrievalMetrics(
        recall_at_5=recall_5,
        recall_at_10=recall_10,
        precision_at_5=precision_5,
        precision_at_10=precision_10,
        ndcg_at_10=ndcg_10,
        mrr=mrr,
        avg_rank_of_relevant=avg_rank,
    )


def format_metrics(metrics: RetrievalMetrics) -> str:
    """Format metrics for display.
    
    Args:
        metrics: RetrievalMetrics instance
        
    Returns:
        Formatted string
    """
    lines = [
        f"Recall@5:  {metrics.recall_at_5:.4f}",
        f"Recall@10: {metrics.recall_at_10:.4f}",
        f"Precision@5:  {metrics.precision_at_5:.4f}",
        f"Precision@10: {metrics.precision_at_10:.4f}",
        f"NDCG@10: {metrics.ndcg_at_10:.4f}",
        f"MRR: {metrics.mrr:.4f}",
    ]
    if metrics.avg_rank_of_relevant is not None:
        lines.append(f"Avg Rank (Relevant): {metrics.avg_rank_of_relevant:.1f}")
    return "\n".join(lines)
