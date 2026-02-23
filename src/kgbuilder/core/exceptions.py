"""Core exceptions for KnowledgeGraphBuilder."""


class KGBuilderError(Exception):
    """Base exception for KGBuilder."""


class DocumentLoadError(KGBuilderError):
    """Error loading a document."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"Failed to load {path}: {reason}")
        self.path = path
        self.reason = reason


class UnsupportedFormatError(KGBuilderError):
    """Unsupported document format."""

    def __init__(self, format_type: str) -> None:
        super().__init__(f"Unsupported format: {format_type}")


class ExtractionError(KGBuilderError):
    """Error during entity/relation extraction."""


class ValidationError(KGBuilderError):
    """Error during KG validation."""


class OntologyError(KGBuilderError):
    """Error with ontology loading or processing."""


class StorageError(KGBuilderError):
    """Error with database operations."""


class VersioningError(KGBuilderError):
    """Error with KG versioning."""


class LLMError(KGBuilderError):
    """Error occurred during LLM interaction (generation or embeddings)."""
