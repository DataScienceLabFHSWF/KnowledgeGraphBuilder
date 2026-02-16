"""Document processing module."""

from kgbuilder.document.advanced_processor import (
    AdvancedDocumentProcessor,
    ProcessedDocument,
    ProcessingStats,
)
from kgbuilder.document.chunking import FixedSizeChunker, SemanticChunker
from kgbuilder.document.loaders import (
    DocumentLoaderFactory,
    DOCXLoader,
    PDFLoader,
    PPTXLoader,
)

__all__ = [
    # Advanced processor
    "AdvancedDocumentProcessor",
    "ProcessedDocument",
    "ProcessingStats",
    # Loaders
    "DocumentLoaderFactory",
    "PDFLoader",
    "DOCXLoader",
    "PPTXLoader",
    # Chunking
    "FixedSizeChunker",
    "SemanticChunker",
]
