"""Adapter that converts LawDocument / Norm objects into KGB Document objects.

Bridges the law XML reader with the KGB extraction pipeline by converting
parsed law data into the standard Document / Chunk format used by extractors.

Usage::

    xml_reader = LawXMLReader()
    adapter = LawDocumentAdapter(chunking_strategy="paragraph")
    law = xml_reader.parse_file(Path("data/law_html/AtG/BJNR008140959.xml"))
    documents = adapter.to_documents(law)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kgbuilder.core.models import (
    Chunk,
    ChunkMetadata,
    Document,
    DocumentMetadata,
    ExtractedRelation,
    FileType,
)
from kgbuilder.document.loaders.law_xml import CrossReference, LawDocument, Norm


@dataclass
class LawDocumentAdapter:
    """Convert LawDocument into KGB Document objects.

    Supports different granularity levels for chunking:
    - "paragraph": One Document per § (recommended for extraction)
    - "law": One Document per law (all paragraphs concatenated)
    - "section": One Document per structural section (Abschnitt/Teil)
    """

    chunking_strategy: str = "paragraph"  # "paragraph" | "law" | "section"

    def to_documents(self, law: LawDocument) -> list[Document]:
        """Convert a LawDocument into one or more KGB Documents.

        Args:
            law: Parsed LawDocument from LawXMLReader.

        Returns:
            List of Document objects ready for embedding/extraction.
        """
        raise NotImplementedError  # TODO: Step 2 implementation

    def to_structural_relations(
        self, law: LawDocument
    ) -> list[ExtractedRelation]:
        """Extract structural relations (teilVon, referenziert) from law metadata.

        These are ground-truth relations requiring no LLM — derived from
        XML structure and cross-reference regex matches.

        Args:
            law: Parsed LawDocument.

        Returns:
            List of ExtractedRelation objects for TEIL_VON and REFERENZIERT.
        """
        raise NotImplementedError  # TODO: Step 2 implementation

    # ------------------------------------------------------------------
    # Internal conversion helpers
    # ------------------------------------------------------------------

    def _norm_to_document(self, norm: Norm, law: LawDocument) -> Document:
        """Convert a single Norm to a Document (paragraph-level)."""
        raise NotImplementedError

    def _norms_to_document(self, norms: list[Norm], law: LawDocument) -> Document:
        """Merge multiple Norms into a single Document (section/law level)."""
        raise NotImplementedError

    def _build_teil_von_relations(self, law: LawDocument) -> list[ExtractedRelation]:
        """Create TEIL_VON relations (Paragraf → Gesetzbuch)."""
        raise NotImplementedError

    def _build_referenziert_relations(
        self, refs: list[CrossReference], source_law: str
    ) -> list[ExtractedRelation]:
        """Create REFERENZIERT relations from cross-references."""
        raise NotImplementedError
