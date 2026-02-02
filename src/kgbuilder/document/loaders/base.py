"""Document loader base class and factory.

Implementation of Issue #2.1: Document Ingestion Interface

TODO:
- [x] Define DocumentLoader protocol
- [x] Implement DocumentLoaderFactory for dynamic loader selection
- [ ] Implement TXT and Markdown loaders (Issue #2.1)
- [ ] Add batch processing with progress callbacks
- [ ] Add error recovery and logging via structlog
- [ ] Add unit tests (tests/document/test_loaders.py)

See Planning/ISSUES_BACKLOG.md Issue #2.1 for acceptance criteria.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Type

from kgbuilder.core import DocumentLoader
from kgbuilder.core.exceptions import UnsupportedFormatError
from kgbuilder.core.models import Document


class DocumentLoaderFactory:
    """Factory for creating appropriate document loaders."""

    _loaders: Dict[str, Type[DocumentLoader]] = {}

    @classmethod
    def register(cls, loader_class: Type[DocumentLoader]) -> None:
        """Register a loader class for its supported extensions.

        Args:
            loader_class: Loader class implementing DocumentLoader protocol
        """
        # Instantiate to get supported extensions
        loader = loader_class()
        for ext in loader.supported_extensions:
            cls._loaders[ext.lower()] = loader_class

    @classmethod
    def get_loader(cls, file_path: Path) -> DocumentLoader:
        """Get appropriate loader for file type.

        Args:
            file_path: Path to document file

        Returns:
            Instantiated loader for the file type

        Raises:
            UnsupportedFormatError: If no loader for file type
        """
        suffix = file_path.suffix.lower()
        if suffix not in cls._loaders:
            raise UnsupportedFormatError(suffix)
        loader_class = cls._loaders[suffix]
        return loader_class()

    @classmethod
    def load(cls, file_path: Path) -> Document:
        """Convenience method to load any supported document.

        Args:
            file_path: Path to document file

        Returns:
            Loaded document

        Raises:
            UnsupportedFormatError: If no loader for file type
        """
        loader = cls.get_loader(file_path)
        return loader.load(file_path)

    @classmethod
    def load_batch(cls, file_paths: list[Path]) -> list[Document]:
        """Load multiple documents.

        Args:
            file_paths: List of paths to documents

        Returns:
            List of loaded documents
        """
        documents = []
        for file_path in file_paths:
            try:
                doc = cls.load(file_path)
                documents.append(doc)
            except Exception:
                # Log but continue on individual document failures
                continue
        return documents
