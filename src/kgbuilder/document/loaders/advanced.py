"""Advanced document loader using docling for better extraction.

Uses docling for layout understanding and markitdown for format conversion.
Supports: PDF, DOCX, PPTX with improved structure preservation.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from kgbuilder.core.exceptions import DocumentLoadError
from kgbuilder.core.models import Document, DocumentMetadata, FileType


class DoclingPDFLoader:
    """Advanced PDF loader using docling for layout understanding."""

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".pdf", ".PDF"]

    def load(self, file_path: Path) -> Document:
        """Load PDF with docling for better structure understanding.

        Args:
            file_path: Path to PDF file

        Returns:
            Document with improved structure preservation

        Raises:
            DocumentLoadError: If PDF cannot be loaded
        """
        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            raise DocumentLoadError(
                str(file_path), "docling not installed"
            ) from None

        try:
            converter = DocumentConverter()
            result = converter.convert(file_path)
            
            # Convert to markdown for better structure preservation
            content = result.document.export_to_markdown()
            
            # Alternative: export_to_text() for plain text
            # content = result.document.export_to_text()

            return Document(
                id=str(uuid4()),
                content=content,
                source_path=file_path,
                file_type=FileType.PDF,
                metadata=DocumentMetadata(
                    title=file_path.stem,
                    page_count=len(result.document.pages) if hasattr(result.document, 'pages') else None,
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


class MarkitdownDocumentLoader:
    """Universal document loader using markitdown for format conversion."""

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported extensions: PDF, DOCX, PPTX, TXT, MD, HTML, etc."""
        return [
            ".pdf", ".PDF",
            ".docx", ".DOCX",
            ".pptx", ".PPTX",
            ".txt", ".TXT",
            ".md", ".MD",
            ".html", ".HTML",
        ]

    def load(self, file_path: Path) -> Document:
        """Load any supported document and convert to markdown.

        Args:
            file_path: Path to document file

        Returns:
            Document with markdown content

        Raises:
            DocumentLoadError: If document cannot be loaded
        """
        try:
            import markitdown
        except ImportError:
            raise DocumentLoadError(
                str(file_path), "markitdown not installed"
            ) from None

        try:
            md = markitdown.MarkItDown()
            result = md.convert(str(file_path))
            content = result.text_content

            # Determine file type
            suffix = file_path.suffix.lower()
            file_type_map = {
                ".pdf": FileType.PDF,
                ".docx": FileType.DOCX,
                ".pptx": FileType.PPTX,
                ".txt": FileType.TXT,
                ".md": FileType.MARKDOWN,
                ".html": FileType.HTML,
            }
            file_type = file_type_map.get(suffix, FileType.TXT)

            return Document(
                id=str(uuid4()),
                content=content,
                source_path=file_path,
                file_type=file_type,
                metadata=DocumentMetadata(title=file_path.stem),
            )
        except Exception as e:
            raise DocumentLoadError(str(file_path), str(e)) from e

    def load_batch(self, file_paths: list[Path]) -> list[Document]:
        """Load multiple documents."""
        documents = []
        for file_path in file_paths:
            try:
                doc = self.load(file_path)
                documents.append(doc)
            except DocumentLoadError:
                continue
        return documents
