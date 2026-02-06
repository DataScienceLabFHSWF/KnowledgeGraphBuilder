"""CLI commands for checkpoint-based re-enrichment and persistence.

Enables:
- Loading extraction checkpoints
- Running enrichment
- Writing to stores without re-extracting
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.embedding.ollama import OllamaProvider
from kgbuilder.enrichment import SemanticEnrichmentPipeline, EnrichedEntity, EnrichedRelation
from kgbuilder.experiment.checkpoint import CheckpointManager

logger = logging.getLogger(__name__)


def enrich_from_checkpoint(
    checkpoint_path: Path,
    output_dir: Path | None = None,
    llm_model: str | None = None,
    embedding_model: str | None = None,
    ollama_base_url: str | None = None,
) -> tuple[list[EnrichedEntity], list[EnrichedRelation]]:
    """Load checkpoint and run enrichment pipeline.

    Args:
        checkpoint_path: Path to extraction checkpoint
        output_dir: Optional output directory for enriched checkpoint
        llm_model: LLM model name (default: OLLAMA_LLM_MODEL or qwen3:8b)
        embedding_model: Embedding model name (default: OLLAMA_EMBED_MODEL or qwen3-embedding)
        ollama_base_url: Ollama API base URL

    Returns:
        Tuple of (enriched_entities, enriched_relations)

    Raises:
        FileNotFoundError: If checkpoint doesn't exist
        RuntimeError: If enrichment fails
    """
    llm_model = llm_model or os.environ.get("OLLAMA_LLM_MODEL", "qwen3:8b")
    embedding_model = embedding_model or os.environ.get("OLLAMA_EMBED_MODEL", "qwen3-embedding")
    # Load checkpoint
    checkpoint_mgr = CheckpointManager(checkpoint_path.parent)
    entities, relations, metadata = checkpoint_mgr.load_extraction(checkpoint_path)
    logger.info(
        f"Loaded checkpoint: {len(entities)} entities, {len(relations)} relations"
    )

    # Initialize providers
    resolved_url = ollama_base_url or os.environ.get("OLLAMA_URL", "http://localhost:18134")
    llm = OllamaProvider(model=llm_model, base_url=resolved_url)
    embedding_provider = OllamaProvider(model=embedding_model, base_url=resolved_url)

    # Initialize enrichment pipeline
    enrichment_pipeline = SemanticEnrichmentPipeline(
        llm=llm,
        embedding_provider=embedding_provider,
        ontology_classes={},
    )

    # Convert extracted entities to enriched format
    enriched_entities: list[EnrichedEntity] = []
    for entity in entities:
        enriched_entities.append(
            EnrichedEntity(
                entity_id=entity.id,
                label=entity.label,
                entity_type=entity.entity_type,
                confidence=entity.confidence,
            )
        )

    # Convert extracted relations to enriched format
    enriched_relations: list[EnrichedRelation] = []
    for relation in relations:
        enriched_relations.append(
            EnrichedRelation(
                relation_id=relation.id,
                source_id=relation.source_entity_id,
                target_id=relation.target_entity_id,
                predicate=relation.predicate,
                confidence=relation.confidence,
            )
        )

    # Run enrichment pipeline
    enriched_entities, enriched_relations, metrics = enrichment_pipeline.enrich(
        enriched_entities,
        enriched_relations,
    )

    logger.info(
        f"Enrichment complete: "
        f"descriptions={metrics.descriptions_added}, "
        f"embeddings={metrics.embeddings_added}, "
        f"cqs={metrics.competency_questions_added}, "
        f"aliases={metrics.aliases_added}"
    )

    # Optionally save enriched checkpoint
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        enriched_checkpoint = output_dir / f"{checkpoint_path.stem}_enriched.json"
        logger.info(f"Saving enriched checkpoint to {enriched_checkpoint}")
        # TODO: implement enriched checkpoint serialization
        # checkpoint_mgr.save_enriched(...)

    return enriched_entities, enriched_relations
