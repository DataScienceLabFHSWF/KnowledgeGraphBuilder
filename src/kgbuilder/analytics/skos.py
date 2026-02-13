"""SKOS-based semantic enrichment for Knowledge Graphs.

Integrates SKOS vocabularies to add standardized concept hierarchies,
synonymy, and semantic relationships to extracted entities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SKOSMapping:
    """Result of mapping an entity to SKOS concepts."""

    entity_id: str
    entity_label: str
    skos_concepts: list[dict]  # [{uri, prefLabel, altLabels, narrower, broader}, ...]
    confidence: float


class SKOSEnricher:
    """Maps entities to SKOS vocabularies for standardized semantic enrichment.
    
    SKOS (Simple Knowledge Organization System) provides standardized ways to
    express semantic relationships like:
    - Preferred/alternative labels (prefLabel, altLabel)
    - Broader/narrower concepts (skos:broader, skos:narrower)
    - Related concepts (skos:related)
    
    This enricher:
    1. Maps entity labels to SKOS concept URIs
    2. Extracts hierarchical relationships
    3. Adds alternative labels/synonyms
    4. Creates broader/narrower concept relations
    """

    def __init__(self, ontology_service: object | None = None) -> None:
        """Initialize SKOS enricher.
        
        Args:
            ontology_service: Fuseki ontology service for SKOS queries (optional)
        """
        self.ontology_service = ontology_service

    def enrich_entity(
        self,
        entity_id: str,
        entity_label: str,
        entity_type: str | None = None,
    ) -> SKOSMapping | None:
        """Map an entity to SKOS concepts.
        
        Strategy:
        1. Query ontology for concept URIs matching entity label
        2. Extract prefLabel, altLabels, broader/narrower hierarchy
        3. Return mapping with confidence score
        
        Args:
            entity_id: Unique entity identifier
            entity_label: Entity label/name to map
            entity_type: Optional entity type for refined search
            
        Returns:
            SKOSMapping with matched concepts, or None if no matches
        """
        if not self.ontology_service:
            logger.warning("skos_enricher_no_ontology_service")
            return None

        try:
            # Query Fuseki for SKOS concepts matching this label
            # Using SPARQL: SELECT ?concept ?prefLabel ?altLabel ?broader ?narrower
            # WHERE { ?concept skos:prefLabel | skos:altLabel ?label . 
            #         FILTER(CONTAINS(LCASE(?label), LCASE(entity_label))) }
            
            concepts = self._query_skos_concepts(entity_label, entity_type)
            
            if not concepts:
                logger.debug(f"skos_no_match entity_id={entity_id} label={entity_label}")
                return None

            # Compute confidence based on label match quality
            confidence = self._compute_mapping_confidence(entity_label, concepts)

            return SKOSMapping(
                entity_id=entity_id,
                entity_label=entity_label,
                skos_concepts=concepts,
                confidence=confidence,
            )

        except Exception as e:
            logger.warning(f"skos_enrichment_error entity_id={entity_id}: {e}")
            return None

    def _query_skos_concepts(
        self, label: str, entity_type: str | None = None
    ) -> list[dict]:
        """Query ontology for SKOS concepts.
        
        Returns list of concepts with structure:
        {
            "uri": "...",
            "prefLabel": "...",
            "altLabels": [...],
            "broader": [...],
            "narrower": [...]
        }
        """
        # Placeholder: would call self.ontology_service.sparql_query()
        # For now return empty to show structure
        return []

    def _compute_mapping_confidence(
        self, entity_label: str, concepts: list[dict]
    ) -> float:
        """Compute confidence score for SKOS mapping.
        
        Factors:
        - prefLabel exact match: 1.0
        - prefLabel case-insensitive match: 0.95
        - altLabel match: 0.85
        - Substring match: 0.7
        
        Args:
            entity_label: Original entity label
            concepts: List of matched SKOS concepts
            
        Returns:
            Confidence score (0.0-1.0)
        """
        if not concepts:
            return 0.0

        # Take best match confidence
        best_conf = 0.0
        entity_lower = entity_label.lower()
        
        for concept in concepts:
            pref_label = concept.get("prefLabel", "").lower()
            
            # Exact match on prefLabel
            if pref_label == entity_lower:
                best_conf = max(best_conf, 1.0)
            # Case-insensitive match on prefLabel
            elif pref_label == entity_lower:
                best_conf = max(best_conf, 0.95)
            # Substring match
            elif entity_lower in pref_label or pref_label in entity_lower:
                best_conf = max(best_conf, 0.7)
            # Check altLabels
            else:
                for alt_label in concept.get("altLabels", []):
                    if alt_label.lower() == entity_lower:
                        best_conf = max(best_conf, 0.85)
                        break

        return best_conf

    def enrich_entities_batch(
        self, entities: list[dict]
    ) -> dict[str, SKOSMapping]:
        """Batch enrich multiple entities.
        
        Args:
            entities: List of {id, label, type} dicts
            
        Returns:
            Dict mapping entity_id -> SKOSMapping
        """
        results = {}
        
        for entity in entities:
            mapping = self.enrich_entity(
                entity_id=entity.get("id"),
                entity_label=entity.get("label"),
                entity_type=entity.get("type"),
            )
            if mapping:
                results[entity.get("id")] = mapping
        
        logger.info(f"skos_enrichment_batch entity_count={len(entities)} matched={len(results)}")
        return results
