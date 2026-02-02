"""Entity and relation extraction.

Implementation of Issues #5.1-#5.3: Knowledge Extraction

TODO (Core interfaces):
- [ ] Define EntityExtractor protocol
- [ ] Define RelationExtractor protocol
- [ ] Define ExtractionResult dataclass with provenance

TODO (LLM-based extractors):
- [ ] Implement LLMEntityExtractor with ontology-guided prompting
  - Multi-pass extraction for complex documents
  - Entity deduplication within document
  - Confidence score calibration
- [ ] Implement LLMRelationExtractor with ontology constraints
  - Support for n-ary relations via reification
  - Domain/range validation
  - Cardinality constraints
- [ ] Implement FindingsSynthesizer for research findings (YAML output)

TODO (Quality & robustness):
- [ ] Add coreference resolution
- [ ] Add confidence thresholding
- [ ] Add structured output validation (JSON schema)
- [ ] Add error recovery and logging
- [ ] Add unit tests with sample texts

See Planning/ISSUES_BACKLOG.md Issues #5.1-#5.3 for acceptance criteria.
"""

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
