"""Entity and relation extraction.

Implementation of Issues #5.1-#5.3: Knowledge Extraction

Provides:
- LLMEntityExtractor: Ontology-guided entity extraction with confidence scores
- LLMRelationExtractor: Entity relation extraction
- ExtractionChains: LangChain LCEL chains for extraction
- FindingsSynthesizer: Synthesis of extracted findings
- Pydantic schemas for structured JSON output
"""

from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.chains import ExtractionChains, build_extraction_pipeline
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
    "LLMRelationExtractor",
    "FindingsSynthesizer",
    "SynthesizedFinding",
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

