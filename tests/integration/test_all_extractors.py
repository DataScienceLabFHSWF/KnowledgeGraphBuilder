#!/usr/bin/env python3
"""Comprehensive test of all entity extraction methods.

Tests:
1. RuleBasedExtractor (fast, deterministic)
2. LLMEntityExtractor (semantic, high accuracy)
3. EnsembleExtractor (combining both)

Demonstrates the extraction pipeline with real data.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import logging

from kgbuilder.embedding.ollama import OllamaProvider
from kgbuilder.extraction import (
    EnsembleExtractor,
    LLMEntityExtractor,
    OntologyClassDef,
    RuleBasedExtractor,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run comprehensive extraction tests."""
    
    logger.info("=" * 80)
    logger.info("ENTITY EXTRACTION - ALL METHODS COMPARISON")
    logger.info("=" * 80)
    
    # Sample text
    text = """
    Kernkraftwerk Emsland betreibt die Stromerzeugung mit höchsten Sicherheitsstandards.
    Ein umfassender Sicherheitsbericht wird alle zwei Jahre eingereicht. Dieser Safety Report
    dokumentiert alle Sicherheitsanforderungen und Betriebsvorgaben. Die Facility muss alle
    Sicherheitsanforderungen der Behörde erfüllen.
    """
    
    # Ontology classes
    ontology_classes = [
        OntologyClassDef(
            uri="http://example.org/ontology/Facility",
            label="Facility",
            description="Nuclear power facility",
            examples=["Kernkraftwerk Emsland", "NPP Isar"],
        ),
        OntologyClassDef(
            uri="http://example.org/ontology/SafetyDocument",
            label="SafetyDocument",
            description="Safety-related document",
            examples=["Sicherheitsbericht", "Safety Report"],
        ),
        OntologyClassDef(
            uri="http://example.org/ontology/Operation",
            label="Operation",
            description="Operational activity",
            examples=["Stromerzeugung", "Power generation"],
        ),
        OntologyClassDef(
            uri="http://example.org/ontology/Requirement",
            label="Requirement",
            description="Safety requirement",
            examples=["Sicherheitsanforderung", "Safety requirement"],
        ),
    ]
    
    logger.info(f"\nTest text: {len(text)} chars")
    logger.info(f"Ontology: {len(ontology_classes)} entity types\n")
    
    # Test 1: Rule-Based Extractor
    logger.info("=" * 80)
    logger.info("1. RULE-BASED EXTRACTOR (Fast, Deterministic)")
    logger.info("=" * 80)
    
    rule_extractor = RuleBasedExtractor()
    rule_entities = rule_extractor.extract(text, ontology_classes)
    
    logger.info(f"Extracted {len(rule_entities)} entities:\n")
    for entity in rule_entities:
        logger.info(
            f"  • {entity.label:30s} | Type: {entity.entity_type:15s} | "
            f"Confidence: {entity.confidence:.2f}"
        )
    
    # Test 2: LLM Extractor (if Ollama available)
    logger.info("\n" + "=" * 80)
    logger.info("2. LLM ENTITY EXTRACTOR (Semantic, High Accuracy)")
    logger.info("=" * 80)
    
    try:
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:18134")
        llm_provider = OllamaProvider(
            model="qwen3",
            base_url=ollama_url,
            timeout=120.0,
        )
        llm_extractor = LLMEntityExtractor(
            llm_provider=llm_provider,
            confidence_threshold=0.5,
            max_retries=1,
        )
        
        logger.info("Calling LLM (this may take a moment)...")
        llm_entities = llm_extractor.extract(text, ontology_classes)
        
        logger.info(f"Extracted {len(llm_entities)} entities:\n")
        for entity in llm_entities:
            logger.info(
                f"  • {entity.label:30s} | Type: {entity.entity_type:15s} | "
                f"Confidence: {entity.confidence:.2f}"
            )
        
    except Exception as e:
        logger.error(f"LLM extraction failed (Ollama may not be running): {e}")
        logger.info("Continuing with rule-based results only...\n")
        llm_entities = []
    
    # Test 3: Ensemble Extractor
    if llm_entities:
        logger.info("\n" + "=" * 80)
        logger.info("3. ENSEMBLE EXTRACTOR (Combined Methods)")
        logger.info("=" * 80)
        
        ensemble = EnsembleExtractor([rule_extractor, llm_extractor])
        ensemble_entities = ensemble.extract(text, ontology_classes)
        
        logger.info(f"Extracted {len(ensemble_entities)} entities:\n")
        for entity in ensemble_entities:
            votes = entity.properties.get("ensemble_votes", 1)
            logger.info(
                f"  • {entity.label:30s} | Type: {entity.entity_type:15s} | "
                f"Confidence: {entity.confidence:.2f} | Votes: {votes}"
            )
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Rule-based: {len(rule_entities)} entities (fast, 100% confidence)")
    if llm_entities:
        logger.info(f"LLM: {len(llm_entities)} entities (semantic, variable confidence)")
        logger.info(f"Ensemble: {len(ensemble_entities)} entities (combined)")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
