"""Document loaders package."""

from kgbuilder.document.loaders.base import DocumentLoaderFactory
from kgbuilder.document.loaders.office import DOCXLoader, PPTXLoader
from kgbuilder.document.loaders.pdf import PDFLoader
from kgbuilder.document.loaders.advanced import DoclingPDFLoader, MarkitdownDocumentLoader

__all__ = [
    "DocumentLoaderFactory",
    "PDFLoader",
    "DOCXLoader",
    "PPTXLoader",
    "DoclingPDFLoader",
    "MarkitdownDocumentLoader",
]
