"""Rule-based entity extraction using regex patterns and dictionaries.

Implementation of rule-based extraction strategy for known entity patterns.

Key features:
- Fast, deterministic extraction (no ML)
- Regex pattern matching per entity type
- Dictionary/gazetteer lookup
- Perfect for known formats and specific patterns
- Configurable patterns and confidence scoring
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from kgbuilder.core.models import ExtractedEntity, Evidence
from kgbuilder.extraction.entity import OntologyClassDef

logger = logging.getLogger(__name__)


@dataclass
class RulePattern:
    """Pattern rule for entity extraction."""

    label: str
    entity_type: str
    regex: str
    confidence: float = 1.0
    examples: list[str] = field(default_factory=list)


class RuleBasedExtractor:
    """Rule-based entity extractor using regex and dictionaries.

    Fast, deterministic extraction without ML.
    Works well for:
    - Known specific patterns (facility names, codes)
    - Dictionary/gazetteer lookup
    - Keyword matching
    """

    def __init__(self) -> None:
        """Initialize rule-based extractor."""
        self.patterns: dict[str, list[RulePattern]] = {}
        self._init_default_patterns()
        logger.info(f"✓ Initialized RuleBasedExtractor with {len(self.patterns)} pattern groups")

    def _init_default_patterns(self) -> None:
        """Initialize default patterns for common entity types.

        Patterns for nuclear domain:
        - Facility names (Kernkraftwerk, NPP, etc.)
        - Document types (Sicherheitsbericht, Safety Report, etc.)
        - Operations (Betrieb, Power generation, etc.)
        - Requirements (Sicherheitsanforderung, Safety requirement, etc.)
        """
        # Facility patterns (German & English)
        self.add_pattern(
            label="Kernkraftwerk",
            entity_type="Facility",
            regex=r"(?i)(?:Kernkraftwerk|Nuclear\s+Power\s+Plant|NPP|Nuklearkraftwerk|KKW)\s+\w+",
            confidence=0.95,
        )

        self.add_pattern(
            label="nuclear facility",
            entity_type="Facility",
            regex=r"(?i)(?:nuclear|atomic)\s+(?:facility|plant|reactor|power\s+plant)",
            confidence=0.85,
        )

        # Safety document patterns
        self.add_pattern(
            label="Sicherheitsbericht",
            entity_type="SafetyDocument",
            regex=r"(?i)(?:Sicherheitsbericht|Safety\s+(?:Report|Assessment|Document|Analysis))",
            confidence=0.95,
        )

        self.add_pattern(
            label="security assessment",
            entity_type="SafetyDocument",
            regex=r"(?i)(?:security|safety)\s+(?:assessment|evaluation|review|inspection)",
            confidence=0.85,
        )

        # Operation patterns
        self.add_pattern(
            label="Betrieb",
            entity_type="Operation",
            regex=r"(?i)(?:Betrieb|Operation|Power\s+Generation|Stromerzeugung)",
            confidence=0.90,
        )

        # Requirement patterns
        self.add_pattern(
            label="Sicherheitsanforderung",
            entity_type="Requirement",
            regex=r"(?i)(?:Sicherheitsanforderung|Safety\s+(?:Requirement|Standard|Specification))",
            confidence=0.90,
        )

        logger.debug(f"Initialized {sum(len(p) for p in self.patterns.values())} default patterns")

    def add_pattern(
        self,
        label: str,
        entity_type: str,
        regex: str,
        confidence: float = 1.0,
        examples: list[str] | None = None,
    ) -> None:
        """Add a pattern rule for extraction.

        Args:
            label: Pattern label/name
            entity_type: Entity type from ontology
            regex: Compiled regex pattern
            confidence: Confidence score (0.0-1.0)
            examples: Example matches for documentation
        """
        pattern = RulePattern(
            label=label,
            entity_type=entity_type,
            regex=regex,
            confidence=confidence,
            examples=examples or [],
        )

        if entity_type not in self.patterns:
            self.patterns[entity_type] = []

        self.patterns[entity_type].append(pattern)
        logger.debug(f"Added pattern: {label} → {entity_type}")

    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Extract entities using rule patterns.

        Fast, deterministic extraction. Returns entities found by
        regex patterns with perfect confidence (1.0).

        Args:
            text: Source text to extract from
            ontology_classes: Valid entity types (used to filter patterns)
            existing_entities: Existing entities (ignored in rule-based)

        Returns:
            List of extracted entities with confidence 1.0
        """
        if not text or not text.strip():
            logger.debug("Empty text provided to rule-based extractor")
            return []

        if not ontology_classes:
            logger.debug("No ontology classes provided, using all patterns")

        logger.debug(f"Rule-based extraction from {len(text)} chars")

        entities = []
        matched_keys = set()  # Track (label, type) to avoid duplicates

        # Apply patterns from each entity type
        for entity_type in self.patterns:
            # Filter by ontology if provided
            if ontology_classes:
                if not any(cls.label == entity_type for cls in ontology_classes):
                    continue

            # Apply all patterns for this entity type
            for pattern in self.patterns[entity_type]:
                try:
                    # Find all matches
                    matches = re.finditer(pattern.regex, text)

                    for match in matches:
                        matched_text = match.group(0).strip()
                        start = match.start()
                        end = match.end()

                        # Skip duplicates (same label and type)
                        key = (matched_text.lower(), entity_type)
                        if key in matched_keys:
                            continue

                        matched_keys.add(key)

                        # Create Evidence
                        context_start = max(0, start - 50)
                        context_end = min(len(text), end + 50)
                        context = text[context_start:context_end]

                        evidence = Evidence(
                            source_type="local_doc",
                            source_id=f"char_{start}_{end}",
                            text_span=matched_text,
                            confidence=pattern.confidence,
                        )

                        # Create Entity
                        entity = ExtractedEntity(
                            id=f"ent_rule_{len(entities):04d}",
                            label=matched_text,
                            entity_type=entity_type,
                            description=f"Extracted by pattern: {pattern.label}",
                            confidence=pattern.confidence,
                            evidence=[evidence],
                        )
                        entities.append(entity)

                except re.error as e:
                    logger.warning(f"Invalid regex pattern: {pattern.regex}: {e}")
                    continue

        logger.debug(f"Rule-based extractor found {len(entities)} entities")
        return entities
