"""Document loaders package."""

from kgbuilder.document.loaders.base import DocumentLoaderFactory
from kgbuilder.document.loaders.office import DOCXLoader, PPTXLoader
from kgbuilder.document.loaders.pdf import PDFLoader
from kgbuilder.document.loaders.advanced import DoclingPDFLoader, MarkitdownDocumentLoader
from kgbuilder.document.loaders.law_xml_loader import LawXMLLoader

# Register loaders
DocumentLoaderFactory.register(PDFLoader)
DocumentLoaderFactory.register(DOCXLoader)
DocumentLoaderFactory.register(PPTXLoader)
DocumentLoaderFactory.register(LawXMLLoader)

__all__ = [
    "DocumentLoaderFactory",
    "PDFLoader",
    "DOCXLoader",
    "PPTXLoader",
    "LawXMLLoader",
    "DoclingPDFLoader",
    "MarkitdownDocumentLoader",
]
