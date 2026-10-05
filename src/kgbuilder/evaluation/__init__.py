"""QA evaluation framework for knowledge graphs.

Provides QA dataset management, query execution, metrics computation,
and report generation for evaluating KG quality.
"""

from kgbuilder.evaluation.metrics import EvaluationMetrics, MetricsComputer
from kgbuilder.evaluation.qa_dataset import QADataset, QAQuestion
from kgbuilder.evaluation.query_executor import QueryExecutor, QueryResult
from kgbuilder.evaluation.reporter import EvaluationReport, EvaluationReporter
from kgbuilder.evaluation.cq_sparql import (
    CompetencyQuestionTranslator,
    CQSparqlResult,
    CQSparqlRunner,
    CQSparqlTranslation,
    compute_cq_translation_coverage,
)
from kgbuilder.evaluation.gold_standard import (
    evaluate_entities,
    evaluate_relations,
    load_gold_documents,
)

__all__ = [
    "QAQuestion",
    "QADataset",
    "QueryResult",
    "QueryExecutor",
    "EvaluationMetrics",
    "MetricsComputer",
    "EvaluationReport",
    "EvaluationReporter",
    "CompetencyQuestionTranslator",
    "CQSparqlTranslation",
    "CQSparqlResult",
    "CQSparqlRunner",
    "compute_cq_translation_coverage",
    # Gold-standard utilities
    "load_gold_documents",
    "evaluate_entities",
    "evaluate_relations",
]
