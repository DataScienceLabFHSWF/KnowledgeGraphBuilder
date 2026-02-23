"""PDF document loader implementation.

Implementation of Issue #2.2: PDF Document Loader

See Planning/ISSUES_BACKLOG.md Issue #2.2 for acceptance criteria.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from kgbuilder.core.exceptions import DocumentLoadError
from kgbuilder.core.models import Document, DocumentMetadata, FileType


class PDFLoader:
    """PDF document loader using pdfplumber."""

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".pdf", ".PDF"]

    def load(self, file_path: Path) -> Document:
        """Load PDF document.

        Args:
            file_path: Path to PDF file

        Returns:
            Document with extracted text

        Raises:
            DocumentLoadError: If PDF cannot be read
        """
        try:
            import pdfplumber
        except ImportError:
            raise DocumentLoadError(
                str(file_path), "pdfplumber not installed"
            ) from None

        try:
            text_content = []
            page_count = 0

            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        text_content.append(text)

            content = "\n\n".join(text_content)

            return Document(
                id=str(uuid4()),
                content=content,
                source_path=file_path,
                file_type=FileType.PDF,
                metadata=DocumentMetadata(
                    title=file_path.stem,
                    page_count=page_count,
                ),
            )
        except Exception as e:
            raise DocumentLoadError(str(file_path), str(e)) from e

    def load_batch(self, file_paths: list[Path]) -> list[Document]:
        """Load multiple PDFs."""
        documents = []
        for file_path in file_paths:
            try:
                doc = self.load(file_path)
                documents.append(doc)
            except DocumentLoadError:
                continue
        return documents
