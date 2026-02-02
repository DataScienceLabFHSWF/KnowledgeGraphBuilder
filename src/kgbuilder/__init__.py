"""KnowledgeGraphBuilder – Ontology-driven Knowledge Graph construction pipeline."""

from kgbuilder.assembly import (
    GraphStatistics,
    KGAssembler,
    SimpleKGAssembler,
)
from kgbuilder.core import (
    Document,
    ExtractedEntity,
    ExtractedRelation,
    KGBuilderError,
)
from kgbuilder.extraction import (
    EntityExtractor,
    FindingsSynthesizer,
    LLMEntityExtractor,
    LLMRelationExtractor,
    OntologyClassDef,
    OntologyRelationDef,
    RelationExtractor,
)
from kgbuilder.storage import (
    FusekiStore,
    GraphStore,
    Neo4jStore,
    QdrantStore,
    RDFStore,
    VectorStore,
)
from kgbuilder.validation import (
    CompetencyQuestionValidator,
    OntologyValidator,
    SHACLValidator,
    Validator,
    ValidationReport,
    ValidationViolation,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Core models and exceptions
    "Document",
    "ExtractedEntity",
    "ExtractedRelation",
    "KGBuilderError",
    # Extraction
    "EntityExtractor",
    "LLMEntityExtractor",
    "OntologyClassDef",
    "RelationExtractor",
    "LLMRelationExtractor",
    "OntologyRelationDef",
    "FindingsSynthesizer",
    # Storage
    "VectorStore",
    "QdrantStore",
    "GraphStore",
    "Neo4jStore",
    "RDFStore",
    "FusekiStore",
    # Assembly
    "KGAssembler",
    "SimpleKGAssembler",
    "GraphStatistics",
    # Validation
    "Validator",
    "ValidationReport",
    "ValidationViolation",
    "SHACLValidator",
    "OntologyValidator",
    "CompetencyQuestionValidator",
]
