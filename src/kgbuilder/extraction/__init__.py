"""Entity and relation extraction.

Implementation of Issues #5.1-#5.3: Knowledge Extraction

Provides:
- LLMEntityExtractor: Ontology-guided entity extraction with confidence scores
- LLMRelationExtractor: Entity relation extraction
- FindingsSynthesizer: Synthesis of extracted findings
- Pydantic schemas for structured JSON output
"""

from kgbuilder.extraction.entity import (
    EntityExtractor,
    LLMEntityExtractor,
    OntologyClassDef,
)
from kgbuilder.extraction.relation import (
    LLMRelationExtractor,
    RelationExtractor,
    OntologyRelationDef,
)
from kgbuilder.extraction.schemas import (
    EntityExtractionOutput,
    EntityItem,
    FindingItem,
    FindingsSynthesisOutput,
    RelationExtractionOutput,
    RelationItem,
)
from kgbuilder.extraction.synthesizer import FindingsSynthesizer

__all__ = [
    # Protocols
    "EntityExtractor",
    "RelationExtractor",
    # Implementations
    "LLMEntityExtractor",
    "LLMRelationExtractor",
    "FindingsSynthesizer",
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
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from .entity import EntityExtractor, LLMEntityExtractor, OntologyClassDef
from .relation import LLMRelationExtractor, OntologyRelationDef, RelationExtractor
from .synthesizer import FindingsSynthesizer, SynthesizedFinding

__all__ = [
    "ExtractedEntity",
    "ExtractedRelation",
    "EntityExtractor",
    "LLMEntityExtractor",
    "OntologyClassDef",
    "RelationExtractor",
    "LLMRelationExtractor",
    "OntologyRelationDef",
    "FindingsSynthesizer",
    "SynthesizedFinding",
]
