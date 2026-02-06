"""Core package exports."""

from kgbuilder.core.env import get_base_url
from kgbuilder.core.exceptions import (
    DocumentLoadError,
    ExtractionError,
    KGBuilderError,
    OntologyError,
    StorageError,
    UnsupportedFormatError,
    ValidationError,
    VersioningError,
)
from kgbuilder.core.models import (
    Chunk,
    ChunkMetadata,
    Document,
    DocumentMetadata,
    Evidence,
    ExtractedEntity,
    ExtractedRelation,
    FileType,
)
from kgbuilder.core.protocols import (
    ChunkingStrategy,
    DocumentLoader,
    EmbeddingProvider,
    LLMProvider,
)

__all__ = [
    # Env
    "get_base_url",
    # Exceptions
    "KGBuilderError",
    "DocumentLoadError",
    "UnsupportedFormatError",
    "ExtractionError",
    "ValidationError",
    "OntologyError",
    "StorageError",
    "VersioningError",
    # Models
    "FileType",
    "DocumentMetadata",
    "ChunkMetadata",
    "Chunk",
    "Document",
    "Evidence",
    "ExtractedEntity",
    "ExtractedRelation",
    # Protocols
    "DocumentLoader",
    "ChunkingStrategy",
    "EmbeddingProvider",
    "LLMProvider",
]
