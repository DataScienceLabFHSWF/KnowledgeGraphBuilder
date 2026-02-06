#!/usr/bin/env python
"""Load extraction checkpoint and apply semantic enrichment.

Usage:
    python scripts/enrich_checkpoint.py \\
        --checkpoint experiment_results/baseline/exp_20260205_110809_2ae9cdf1_baseline_1/checkpoint_*.json \\
        --output experiment_results/enriched/

This script:
1. Loads extracted entities and relations from checkpoint
2. Enriches them with semantic metadata (descriptions, embeddings, questions)
3. Saves enriched results for Neo4j persistence

See Planning/RETRIEVAL_SEMANTIC_ENRICHMENT.md Phase 1-2 for design details.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

import structlog

from kgbuilder.experiment.checkpoint import CheckpointManager
from kgbuilder.extraction.enrichment import SemanticEnrichmentPipeline

logger = structlog.get_logger(__name__)


def load_embedding_provider(model: str = "nomic-embed-text", base_url: str | None = None):
    if base_url is None:
        base_url = os.environ.get("OLLAMA_URL", "http://localhost:18134")
    """Load embedding provider from Ollama.
    
    Args:
        model: Ollama embedding model name
        base_url: Ollama API base URL
        
    Returns:
        EmbeddingProvider instance
    """
    from kgbuilder.embedding.ollama import OllamaEmbeddingProvider
    
    return OllamaEmbeddingProvider(model=model, base_url=base_url)


def load_llm_provider(model: str = "qwen3:8b", base_url: str | None = None):
    if base_url is None:
        base_url = os.environ.get("OLLAMA_URL", "http://localhost:18134")
    """Load LLM provider from Ollama.
    
    Args:
        model: Ollama model name
        base_url: Ollama API base URL
        
    Returns:
        LLMProvider instance
    """
    from kgbuilder.embedding.ollama import OllamaProvider
    
    return OllamaProvider(model=model, base_url=base_url)


def enrich_checkpoint(
    checkpoint_path: Path,
    output_dir: Path,
    embedding_model: str = "nomic-embed-text",
    llm_model: str = "qwen3:8b",
    confidence_threshold: float = 0.5,
) -> Path:
    """Load checkpoint and apply semantic enrichment.
    
    Args:
        checkpoint_path: Path to checkpoint file
        output_dir: Directory to save enriched results
        embedding_model: Ollama embedding model
        llm_model: Ollama LLM model
        confidence_threshold: Minimum confidence to keep entities
        
    Returns:
        Path to enriched results file
    """
    logger.info("enrichment_starting", checkpoint=str(checkpoint_path))
    
    # Load checkpoint
    checkpoint_manager = CheckpointManager(checkpoint_dir=checkpoint_path.parent)
    entities, relations, metadata = checkpoint_manager.load_extraction(checkpoint_path)
    
    logger.info(
        "checkpoint_loaded",
        entities=len(entities),
        relations=len(relations),
    )
    
    # Initialize enrichment pipeline
    logger.info("initializing_enrichment_pipeline")
    
    try:
        llm_provider = load_llm_provider(llm_model)
        embedding_provider = load_embedding_provider(embedding_model)
    except Exception as e:
        logger.warning(
            "provider_initialization_failed",
            error=str(e),
            message="Proceeding with basic enrichment (no LLM/embeddings)"
        )
        llm_provider = None
        embedding_provider = None
    
    pipeline = SemanticEnrichmentPipeline(
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        confidence_threshold=confidence_threshold,
    )
    
    # Enrich entities
    logger.info("enriching_entities")
    enriched_entities = pipeline.enrich_entities(entities)
    
    # Enrich relations
    logger.info("enriching_relations")
    entity_map = {e.id: e for e in entities}
    enriched_relations = pipeline.enrich_relations(relations, entities=entity_map)
    
    # Prepare output
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save enriched results
    enriched_data = {
        "metadata": asdict(metadata),
        "enriched_entities": [
            {
                "entity": asdict(ee.entity),
                "description": ee.description,
                "competency_questions": ee.competency_questions,
                "discovery_question_ids": ee.discovery_question_ids,
                "evidence_count": ee.evidence_count,
                "discovery_confidence": ee.discovery_confidence,
                # Note: numpy arrays can't be JSON serialized, so we skip embedding
            }
            for ee in enriched_entities
        ],
        "enriched_relations": [
            {
                "relation": asdict(er.relation),
                "description": er.description,
                # Note: numpy arrays can't be JSON serialized, so we skip embedding
            }
            for er in enriched_relations
        ],
    }
    
    output_path = output_dir / f"enriched_{metadata.run_id}.json"
    with open(output_path, "w") as f:
        json.dump(enriched_data, f, indent=2, default=str)
    
    logger.info(
        "enrichment_complete",
        output_path=str(output_path),
        enriched_entities=len(enriched_entities),
        enriched_relations=len(enriched_relations),
    )
    
    return output_path


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Enrich extraction checkpoint with semantic metadata"
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="Path to checkpoint file (e.g., checkpoint_exp_*.json)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiment_results/enriched"),
        help="Output directory for enriched results"
    )
    parser.add_argument(
        "--embedding-model",
        default="nomic-embed-text",
        help="Ollama embedding model name"
    )
    parser.add_argument(
        "--llm-model",
        default="qwen3:8b",
        help="Ollama LLM model name"
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Minimum confidence to retain entities"
    )
    
    args = parser.parse_args()
    
    # Validate checkpoint file exists
    if not args.checkpoint.exists():
        print(f"Error: Checkpoint file not found: {args.checkpoint}")
        return
    
    # Run enrichment
    start_time = time.time()
    output_path = enrich_checkpoint(
        checkpoint_path=args.checkpoint,
        output_dir=args.output,
        embedding_model=args.embedding_model,
        llm_model=args.llm_model,
        confidence_threshold=args.confidence_threshold,
    )
    elapsed = time.time() - start_time
    
    print(f"\n✓ Enrichment complete in {elapsed:.1f}s")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    main()
