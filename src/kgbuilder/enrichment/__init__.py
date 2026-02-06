"""Semantic enrichment pipeline for KG enhancement.

Five enrichment phases:
1. Descriptions — LLM-generated descriptions
2. Embeddings — Semantic vector representations
3. Competency Questions — Questions each entity answers
4. Type Constraints — Type compatibility scoring
5. Aliases — Synonyms and alternate names
"""

from kgbuilder.enrichment.enrichers import (
    AliasEnricher,
    CompetencyQuestionEnricher,
    DescriptionEnricher,
    EmbeddingEnricher,
    TypeConstraintEnricher,
)
from kgbuilder.enrichment.pipeline import SemanticEnrichmentPipeline, EnrichmentMetrics
from kgbuilder.enrichment.protocols import Enricher, EnrichedEntity, EnrichedRelation

__all__ = [
    "SemanticEnrichmentPipeline",
    "EnrichmentMetrics",
    "Enricher",
    "EnrichedEntity",
    "EnrichedRelation",
    "DescriptionEnricher",
    "EmbeddingEnricher",
    "CompetencyQuestionEnricher",
    "TypeConstraintEnricher",
    "AliasEnricher",
]
