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
        if self.chunking_strategy == "paragraph":
            return [self._norm_to_document(norm, law) for norm in law.paragraphs()]
        elif self.chunking_strategy == "law":
            return [self._norms_to_document(law.paragraphs(), law)]
        elif self.chunking_strategy == "section":
            # Group by section
            sections: dict[str, list[Norm]] = {}
            current_section = "General"
            for norm in law.norms:
                if norm.is_structure and norm.gliederung:
                    current_section = norm.gliederung.kennung
                elif norm.is_paragraph:
                    sections.setdefault(current_section, []).append(norm)
            return [self._norms_to_document(norms, law) for norms in sections.values()]
        else:
            raise ValueError(f"Unknown chunking strategy: {self.chunking_strategy}")

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
        relations: list[ExtractedRelation] = []
        relations.extend(self._build_teil_von_relations(law))
        relations.extend(self._build_referenziert_relations(law.all_cross_references(), law.abbreviation))
        return relations

    # ------------------------------------------------------------------
    # Internal conversion helpers
    # ------------------------------------------------------------------

    def _norm_to_document(self, norm: Norm, law: LawDocument) -> Document:
        """Convert a single Norm to a Document (paragraph-level)."""
        doc_id = f"{law.abbreviation}_{norm.enbez}".replace(" ", "_").replace("§", "S")
        content = f"{norm.title}\n\n{norm.text}" if norm.title else norm.text

        # Create a single chunk for the whole paragraph
        chunk = Chunk(
            id=f"{doc_id}_chunk",
            content=content,
            document_id=doc_id,
            start_char=0,
            end_char=len(content),
            token_count=len(content.split()),  # rough estimate
            metadata=ChunkMetadata(
                section_title=norm.title,
                paragraph_index=self._parse_paragraph_number(norm.enbez),
            ),
        )

        return Document(
            id=doc_id,
            content=content,
            source_path=law.file_path,
            file_type=FileType.XML,
            metadata=DocumentMetadata(
                title=f"{law.abbreviation} {norm.enbez}: {norm.title}",
                language="de",
                custom={
                    "law_abbreviation": law.abbreviation,
                    "paragraph": norm.enbez,
                    "build_date": norm.build_date,
                    "doc_number": norm.doc_number,
                },
            ),
            chunks=[chunk],
        )

    def _norms_to_document(self, norms: list[Norm], law: LawDocument) -> Document:
        """Merge multiple Norms into a single Document (section/law level)."""
        if not norms:
            return Document(
                id=f"{law.abbreviation}_empty",
                content="",
                source_path=law.file_path,
                file_type=FileType.XML,
            )

        # Use first norm's ID as base
        base_norm = norms[0]
        doc_id = f"{law.abbreviation}_{base_norm.enbez}".replace(" ", "_").replace("§", "S")
        if len(norms) > 1:
            doc_id += f"_to_{norms[-1].enbez}".replace(" ", "_").replace("§", "S")

        # Concatenate all content
        content_parts = []
        for norm in norms:
            if norm.title:
                content_parts.append(f"{norm.enbez}: {norm.title}")
            content_parts.append(norm.text)
        content = "\n\n".join(content_parts)

        # Single chunk for the whole document
        chunk = Chunk(
            id=f"{doc_id}_chunk",
            content=content,
            document_id=doc_id,
            start_char=0,
            end_char=len(content),
            token_count=len(content.split()),
        )

        return Document(
            id=doc_id,
            content=content,
            source_path=law.file_path,
            file_type=FileType.XML,
            metadata=DocumentMetadata(
                title=f"{law.abbreviation} {base_norm.enbez}" + (f" to {norms[-1].enbez}" if len(norms) > 1 else ""),
                language="de",
                custom={
                    "law_abbreviation": law.abbreviation,
                    "paragraphs": [n.enbez for n in norms],
                    "build_date": norms[0].build_date,
                },
            ),
            chunks=[chunk],
        )

    def _build_teil_von_relations(self, law: LawDocument) -> list[ExtractedRelation]:
        """Create TEIL_VON relations (Paragraf → Gesetzbuch)."""
        relations: list[ExtractedRelation] = []
        for norm in law.paragraphs():
            relations.append(ExtractedRelation(
                source_id=f"{law.abbreviation}_{norm.enbez}",
                source_label=norm.enbez,
                source_type="Paragraf",
                predicate="teilVon",
                target_id=law.abbreviation,
                target_label=law.full_title,
                target_type="Gesetzbuch",
                confidence=1.0,
                evidence=[],
            ))
        return relations

    def _build_referenziert_relations(
        self, refs: list[CrossReference], source_law: str
    ) -> list[ExtractedRelation]:
        """Create REFERENZIERT relations from cross-references."""
        relations: list[ExtractedRelation] = []
        for ref in refs:
            target_law = ref.target_law or source_law
            target_id = f"{target_law}_{ref.target_paragraph}"

            relations.append(ExtractedRelation(
                source_id=f"{source_law}_{ref.source_paragraph}",
                source_label=ref.source_paragraph,
                source_type="Paragraf",
                predicate="referenziert",
                target_id=target_id,
                target_label=ref.target_paragraph,
                target_type="Paragraf",
                confidence=0.9,  # High but not 1.0 since regex-based
                evidence=[],
            ))
        return relations

    def _parse_paragraph_number(self, enbez: str) -> int | None:
        """Parse paragraph number from enbez string like '§ 2', '§ 2a', 'Art. 1'."""
        if not enbez:
            return None
        
        # Extract number after § or Art.
        import re
        match = re.search(r'(?:§|Art\.)\s*(\d+)', enbez)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None
