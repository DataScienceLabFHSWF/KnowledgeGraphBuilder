"""Entity and relation extraction.

Implementation of Issues #5.1-#5.3: Knowledge Extraction

Provides:
- LLMEntityExtractor: Ontology-guided entity extraction with confidence scores
- RuleBasedExtractor: Fast regex-based entity extraction
- EnsembleExtractor: Combines multiple extraction methods
- LLMRelationExtractor: Entity relation extraction
- ExtractionChains: LangChain LCEL chains for extraction
- FindingsSynthesizer: Synthesis of extracted findings
- SemanticEnrichmentPipeline: Post-extraction semantic enrichment
- Pydantic schemas for structured JSON output
"""

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.chains import ExtractionChains, build_extraction_pipeline
from kgbuilder.extraction.ensemble import EnsembleExtractor
from kgbuilder.extraction.enrichment import (
    EnrichedEntity,
    EnrichedRelation,
    SemanticEnrichmentPipeline,
)
from kgbuilder.extraction.entity import (
    EntityExtractor,
    LLMEntityExtractor,
    OntologyClassDef,
)
from kgbuilder.extraction.relation import (
    LLMRelationExtractor,
    OntologyRelationDef,
    RelationExtractor,
)
from kgbuilder.extraction.rules import RuleBasedExtractor
from kgbuilder.extraction.schemas import (
    EntityExtractionOutput,
    EntityItem,
    FindingItem,
    FindingsSynthesisOutput,
    RelationExtractionOutput,
    RelationItem,
)
from kgbuilder.extraction.synthesizer import FindingsSynthesizer, SynthesizedFinding

__all__ = [
    # Core models
    "ExtractedEntity",
    "ExtractedRelation",
    # Protocols
    "EntityExtractor",
    "RelationExtractor",
    # Implementations
    "LLMEntityExtractor",
    "RuleBasedExtractor",
    "EnsembleExtractor",
    "LLMRelationExtractor",
    "FindingsSynthesizer",
    "SynthesizedFinding",
    # Enrichment
    "SemanticEnrichmentPipeline",
    "EnrichedEntity",
    "EnrichedRelation",
    # LangChain chains
    "ExtractionChains",
    "build_extraction_pipeline",
    # Data models
    "OntologyClassDef",
    "OntologyRelationDef",
    # Schemas
    "EntityExtractionOutput",
    "EntityItem",
    "RelationExtractionOutput",
    "RelationItem",
    "FindingsSynthesisOutput",
    "FindingItem",
]

