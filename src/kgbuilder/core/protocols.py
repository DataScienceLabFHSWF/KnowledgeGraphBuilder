"""Protocol interfaces for KnowledgeGraphBuilder.

See Planning/INTERFACES.md for full protocol specifications.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from kgbuilder.core.models import Chunk, Document


@runtime_checkable
class DocumentLoader(Protocol):
    """Protocol for document loading implementations."""

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (e.g., ['.pdf', '.PDF'])."""
        ...

    def load(self, file_path: Path) -> Document:
        """Load a document from file path.

        Args:
            file_path: Path to the document file

        Returns:
            Document object with content and metadata

        Raises:
            DocumentLoadError: If file cannot be loaded
            UnsupportedFormatError: If file type not supported
        """
        ...

    def load_batch(self, file_paths: list[Path]) -> list[Document]:
        """Load multiple documents."""
        ...


@runtime_checkable
class ChunkingStrategy(Protocol):
    """Protocol for document chunking strategies."""

    @property
    def name(self) -> str:
        """Strategy identifier."""
        ...

    def chunk(
        self, document: Document, chunk_size: int = 512, chunk_overlap: int = 50
    ) -> list[Chunk]:
        """Split document into chunks.

        Args:
            document: Document to chunk
            chunk_size: Target chunk size (tokens or chars based on implementation)
            chunk_overlap: Overlap between consecutive chunks

        Returns:
            List of Chunk objects with provenance metadata
        """
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding generation."""

    @property
    def model_name(self) -> str:
        """Name of the embedding model."""
        ...

    @property
    def dimension(self) -> int:
        """Embedding vector dimension."""
        ...

    @property
    def max_tokens(self) -> int:
        """Maximum input tokens supported."""
        ...

    def embed_text(self, text: str) -> Any:
        """Generate embedding for single text.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector as numpy array
        """
        ...

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> Any:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts
            batch_size: Batch size for processing

        Returns:
            2D array of shape (len(texts), dimension)
        """
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM operations."""

    @property
    def model_name(self) -> str:
        """Name of the LLM model."""
        ...

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt.

        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters

        Returns:
            Generated text
        """
        ...

    def generate_structured(self, prompt: str, schema: type, **kwargs: Any) -> Any:
        """Generate structured output (JSON).

        Args:
            prompt: Input prompt
            schema: Pydantic model for output

        Returns:
            Structured output matching schema
        """
        ...
