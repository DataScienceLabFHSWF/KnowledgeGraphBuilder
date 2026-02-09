"""XML loader for German federal law files.

Implements DocumentLoader protocol using LawXMLReader + LawDocumentAdapter.
Loads German law XML files and converts them to KGB Document objects.

Usage::

    loader = LawXMLLoader()
    documents = loader.load(Path("data/law_html/AtG/BJNR008140959.xml"))
"""

from __future__ import annotations

from pathlib import Path

from kgbuilder.core import DocumentLoader
from kgbuilder.core.models import Document
from kgbuilder.document.loaders.law_adapter import LawDocumentAdapter
from kgbuilder.document.loaders.law_xml import LawXMLReader


class LawXMLLoader(DocumentLoader):
    """XML loader for German federal law files.

    Uses LawXMLReader to parse XML and LawDocumentAdapter to convert
    to KGB Document objects. Supports paragraph-level chunking.
    """

    def __init__(self, chunking_strategy: str = "paragraph") -> None:
        """Initialize loader.

        Args:
            chunking_strategy: How to chunk the law ("paragraph", "law", "section")
        """
        self.reader = LawXMLReader()
        self.adapter = LawDocumentAdapter(chunking_strategy=chunking_strategy)

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".xml", ".XML"]

    def load(self, file_path: Path) -> list[Document]:
        """Load XML law document.

        Args:
            file_path: Path to XML law file

        Returns:
            List of Document objects (one per paragraph by default)
        """
        law = self.reader.parse_file(file_path)
        return self.adapter.to_documents(law)