"""KnowledgeGraphBuilder – Ontology-driven Knowledge Graph construction pipeline.

Make top-level imports tolerant: many submodules (LangChain, optional extractors,
etc.) are optional for certain runtime uses (scoring, validation). Importing the
package should not fail when optional third-party packages are missing — those
submodules will be available only when their dependencies are installed.
"""

# Import lightweight core first; defer heavy/optional imports behind try/except
from kgbuilder.core import (
    Document,
    ExtractedEntity,
    ExtractedRelation,
    KGBuilderError,
)

__version__ = "0.1.0"

# Try to import optional feature groups; if unavailable, keep names undefined so
# callers can import specific modules directly when required.
_optional_symbols = {}

try:
    from kgbuilder.assembly import (
        GraphStatistics,
        KGAssembler,
        SimpleKGAssembler,
    )

    _optional_symbols.update(
        {
            "GraphStatistics": GraphStatistics,
            "KGAssembler": KGAssembler,
            "SimpleKGAssembler": SimpleKGAssembler,
        }
    )
except Exception:
    # LangChain or other heavy deps may be missing — skip assembly exports
    pass

try:
    from kgbuilder.extraction import (
        EntityExtractor,
        FindingsSynthesizer,
        LLMEntityExtractor,
        LLMRelationExtractor,
        OntologyClassDef,
        OntologyRelationDef,
        RelationExtractor,
    )

    _optional_symbols.update(
        {
            "EntityExtractor": EntityExtractor,
            "FindingsSynthesizer": FindingsSynthesizer,
            "LLMEntityExtractor": LLMEntityExtractor,
            "LLMRelationExtractor": LLMRelationExtractor,
            "OntologyClassDef": OntologyClassDef,
            "OntologyRelationDef": OntologyRelationDef,
            "RelationExtractor": RelationExtractor,
        }
    )
except Exception:
    pass

try:
    from kgbuilder.storage import (
        FusekiStore,
        GraphStore,
        Neo4jStore,
        QdrantStore,
        RDFStore,
        VectorStore,
    )

    _optional_symbols.update(
        {
            "FusekiStore": FusekiStore,
            "GraphStore": GraphStore,
            "Neo4jStore": Neo4jStore,
            "QdrantStore": QdrantStore,
            "RDFStore": RDFStore,
            "VectorStore": VectorStore,
        }
    )
except Exception:
    pass

try:
    from kgbuilder.validation import (
        SHACLValidator,
        ValidationViolation,
    )

    _optional_symbols.update(
        {
            "SHACLValidator": SHACLValidator,
            "ValidationViolation": ValidationViolation,
        }
    )
except Exception:
    pass

# Build __all__ dynamically to include only successfully imported names.
__all__ = ["__version__", "Document", "ExtractedEntity", "ExtractedRelation", "KGBuilderError"]
__all__.extend(sorted(_optional_symbols.keys()))

# Export optional symbols into module globals so `from kgbuilder import X` works
globals().update(_optional_symbols)
