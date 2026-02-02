#!/usr/bin/env python3
"""Test LLMEntityExtractor with Ollama LLM.

Tests entity extraction end-to-end with:
- Real Ollama connection
- Sample nuclear domain text
- Ontology class guidance
- Structured output validation
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import logging
from pathlib import Path

from kgbuilder.embedding.ollama import OllamaProvider
from kgbuilder.extraction.entity import (
    LLMEntityExtractor,
    OntologyClassDef,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_llm_entity_extraction():
    """Test LLMEntityExtractor with real Ollama connection."""
    
    logger.info("=" * 80)
    logger.info("TESTING LLMEntityExtractor WITH OLLAMA")
    logger.info("=" * 80)
    
    # Initialize LLM provider (Ollama)
    logger.info("\n1. Initializing Ollama LLM provider...")
    try:
        llm_provider = OllamaProvider(
            model="qwen3",
            base_url="http://localhost:11434",
            timeout=60.0,
        )
        logger.info(f"   ✓ Connected to Ollama: {llm_provider.model_name}")
    except Exception as e:
        logger.error(f"   ✗ Failed to connect to Ollama: {e}")
        logger.error("   Make sure Ollama is running: docker-compose up")
        return False
    
    # Initialize entity extractor
    logger.info("\n2. Initializing LLMEntityExtractor...")
    extractor = LLMEntityExtractor(
        llm_provider=llm_provider,
        confidence_threshold=0.5,
        max_retries=2,
    )
    logger.info(f"   ✓ Extractor initialized (threshold: 0.5)")
    
    # Define ontology classes for nuclear domain
    logger.info("\n3. Defining ontology classes...")
    ontology_classes = [
        OntologyClassDef(
            uri="http://example.org/ontology/Facility",
            label="Facility",
            description="Nuclear power facility or plant",
            examples=["Kernkraftwerk Emsland", "Nuclear Power Plant", "NPP Isar"],
        ),
        OntologyClassDef(
            uri="http://example.org/ontology/SafetyDocument",
            label="SafetyDocument",
            description="Safety-related document or report",
            examples=["Sicherheitsbericht", "Safety Report", "Security Assessment"],
        ),
        OntologyClassDef(
            uri="http://example.org/ontology/Operation",
            label="Operation",
            description="Operational activity or process",
            examples=["Stromerzeugung", "Power generation", "Betrieb"],
        ),
        OntologyClassDef(
            uri="http://example.org/ontology/Requirement",
            label="Requirement",
            description="Safety or regulatory requirement",
            examples=["Sicherheitsanforderung", "Safety requirement", "Compliance"],
        ),
    ]
    logger.info(f"   ✓ Defined {len(ontology_classes)} entity types")
    
    # Test texts
    test_cases = [
        {
            "name": "Nuclear Facility Report",
            "text": """
            Der Kernkraftwerk Emsland ist eine der wichtigsten Einrichtungen für die Stromerzeugung
            in Deutschland. Der Betrieb verfolgt die höchsten Sicherheitsstandards. Nach den neuesten
            Regulierungen muss ein umfassender Sicherheitsbericht alle zwei Jahre eingereicht werden.
            Dieser Sicherheitsbericht dokumentiert alle Sicherheitsanforderungen.
            """,
        },
        {
            "name": "Safety Requirements",
            "text": """
            All nuclear facilities must comply with stringent safety requirements. The safety report
            must document emergency procedures, containment systems, and backup power. The facility
            manager is responsible for ensuring all safety requirements are met during operation.
            Regular safety inspections and assessments are mandatory.
            """,
        },
    ]
    
    # Run tests
    logger.info("\n4. Running extraction tests...")
    all_passed = True
    
    for test_case in test_cases:
        logger.info(f"\n   Test: {test_case['name']}")
        logger.info(f"   Text length: {len(test_case['text'])} chars")
        
        try:
            entities = extractor.extract(
                text=test_case['text'],
                ontology_classes=ontology_classes,
            )
            
            logger.info(f"   ✓ Extracted {len(entities)} entities")
            
            if entities:
                for i, entity in enumerate(entities, 1):
                    logger.info(
                        f"      [{i}] {entity.label} "
                        f"(type={entity.entity_type}, confidence={entity.confidence:.2f})"
                    )
            else:
                logger.warning("   ✗ No entities extracted (LLM returned empty)")
                all_passed = False
        
        except Exception as e:
            logger.error(f"   ✗ Extraction failed: {e}")
            all_passed = False
    
    # Summary
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("✓ ALL TESTS PASSED")
    else:
        logger.info("✗ SOME TESTS FAILED")
    logger.info("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    success = test_llm_entity_extraction()
    sys.exit(0 if success else 1)
