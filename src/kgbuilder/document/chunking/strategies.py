"""Chunking strategies for document processing.

Implementation of Issue #2.4: Chunking Strategy System


See Planning/ISSUES_BACKLOG.md Issue #2.4 for acceptance criteria.
"""

from __future__ import annotations

from uuid import uuid4

from kgbuilder.core.models import Chunk, ChunkMetadata, Document


class FixedSizeChunker:
    """Fixed-size chunking strategy based on token count."""

    @property
    def name(self) -> str:
        """Strategy identifier."""
        return "fixed_size"

    def chunk(
        self, document: Document, chunk_size: int = 512, chunk_overlap: int = 50
    ) -> list[Chunk]:
        """Split document into fixed-size chunks.

        Args:
            document: Document to chunk
            chunk_size: Target chunk size in characters
            chunk_overlap: Character overlap between chunks

        Returns:
            List of chunks with provenance
        """
        chunks = []
        content = document.content
        step = chunk_size - chunk_overlap

        for start in range(0, len(content), step):
            end = min(start + chunk_size, len(content))
            if start > 0:
                start = max(start - chunk_overlap // 2, 0)

            chunk_content = content[start:end]
            if not chunk_content.strip():
                continue

            chunk = Chunk(
                id=str(uuid4()),
                content=chunk_content,
                document_id=document.id,
                start_char=start,
                end_char=end,
                token_count=len(chunk_content.split()),
                metadata=ChunkMetadata(),
            )
            chunks.append(chunk)

        return chunks


class SemanticChunker:
    """Semantic chunking strategy based on paragraph boundaries."""

    @property
    def name(self) -> str:
        """Strategy identifier."""
        return "semantic"

    def chunk(
        self, document: Document, chunk_size: int = 512, chunk_overlap: int = 50
    ) -> list[Chunk]:
        """Split document at paragraph boundaries.

        Args:
            document: Document to chunk
            chunk_size: Target chunk size in characters (guidance)
            chunk_overlap: Overlap in characters (guidance)

        Returns:
            List of chunks at semantic boundaries
        """
        chunks = []
        paragraphs = document.content.split("\n\n")
        current_chunk_content = []
        current_start = 0
        current_size = 0

        for para_idx, para in enumerate(paragraphs):
            para_size = len(para)

            if current_size + para_size > chunk_size and current_chunk_content:
                chunk_content = "\n\n".join(current_chunk_content)
                chunk = Chunk(
                    id=str(uuid4()),
                    content=chunk_content,
                    document_id=document.id,
                    start_char=current_start,
                    end_char=current_start + len(chunk_content),
                    token_count=len(chunk_content.split()),
                    metadata=ChunkMetadata(paragraph_index=para_idx),
                )
                chunks.append(chunk)

                current_chunk_content = [para]
                current_start += len(chunk_content) + 2  # +2 for "\n\n"
                current_size = para_size
            else:
                current_chunk_content.append(para)
                current_size += para_size

        if current_chunk_content:
            chunk_content = "\n\n".join(current_chunk_content)
            chunk = Chunk(
                id=str(uuid4()),
                content=chunk_content,
                document_id=document.id,
                start_char=current_start,
                end_char=current_start + len(chunk_content),
                token_count=len(chunk_content.split()),
                metadata=ChunkMetadata(),
            )
            chunks.append(chunk)

        return chunks


class StructuralChunker:
    """Structural chunking strategy based on section headings."""

    @property
    def name(self) -> str:
        """Strategy identifier."""
        return "structural"

    def chunk(
        self, document: Document, chunk_size: int = 512, chunk_overlap: int = 50
    ) -> list[Chunk]:
        """Split document at structural boundaries (headings, sections).

        Args:
            document: Document to chunk
            chunk_size: Target chunk size in characters (guidance)
            chunk_overlap: Overlap in characters (guidance)

        Returns:
            List of chunks at structural boundaries with hierarchy metadata
        """
        import re

        chunks = []
        content = document.content

        # Pattern for common heading markers (##, ###, etc.)
        heading_pattern = r"^(#{1,6})\s+(.+?)$"
        lines = content.split("\n")

        current_chunk = []
        current_heading = None
        current_level = 0
        current_start = 0
        start_pos = 0

        for line_idx, line in enumerate(lines):
            heading_match = re.match(heading_pattern, line)

            if heading_match:
                # Found a heading - save current chunk if exists
                if current_chunk:
                    chunk_content = "\n".join(current_chunk)
                    chunk = Chunk(
                        id=str(uuid4()),
                        content=chunk_content,
                        document_id=document.id,
                        start_char=current_start,
                        end_char=current_start + len(chunk_content),
                        token_count=len(chunk_content.split()),
                        metadata=ChunkMetadata(
                            heading=current_heading,
                            heading_level=current_level,
                            section_index=line_idx,
                        ),
                    )
                    chunks.append(chunk)

                # Start new section
                current_heading = heading_match.group(2)
                current_level = len(heading_match.group(1))
                current_chunk = [line]
                current_start = start_pos
            else:
                current_chunk.append(line)

            start_pos += len(line) + 1  # +1 for newline

        # Save final chunk
        if current_chunk:
            chunk_content = "\n".join(current_chunk)
            chunk = Chunk(
                id=str(uuid4()),
                content=chunk_content,
                document_id=document.id,
                start_char=current_start,
                end_char=current_start + len(chunk_content),
                token_count=len(chunk_content.split()),
                metadata=ChunkMetadata(
                    heading=current_heading,
                    heading_level=current_level,
                ),
            )
            chunks.append(chunk)

        return chunks


class HierarchicalChunker:
    """Hierarchical chunking with parent-child relationships.
    
    Creates nested chunks where parent chunks contain child chunks,
    preserving document structure and enabling context-aware retrieval.
    """

    @property
    def name(self) -> str:
        """Strategy identifier."""
        return "hierarchical"

    def chunk(
        self, document: Document, chunk_size: int = 512, chunk_overlap: int = 50
    ) -> list[Chunk]:
        """Split document hierarchically with parent-child relationships.

        Creates a two-level hierarchy:
        - Parent chunks: sections/large units (2000 chars)
        - Child chunks: subsections/small units (500 chars)

        Args:
            document: Document to chunk
            chunk_size: Target chunk size for child chunks
            chunk_overlap: Overlap in characters

        Returns:
            List of chunks with parent_id relationships
        """

        # First, create structural chunks (parents)
        structural_chunker = StructuralChunker()
        parent_chunks = structural_chunker.chunk(
            document, chunk_size=2000, chunk_overlap=100
        )

        all_chunks = list(parent_chunks)  # Include parent chunks

        # For each parent chunk, create child chunks
        for parent_chunk in parent_chunks:
            content = parent_chunk.content

            # Split parent into smaller child chunks
            step = chunk_size - chunk_overlap

            for start in range(0, len(content), step):
                end = min(start + chunk_size, len(content))

                child_content = content[start:end].strip()
                if not child_content or len(child_content) < 50:
                    continue

                child_chunk = Chunk(
                    id=str(uuid4()),
                    content=child_content,
                    document_id=document.id,
                    start_char=parent_chunk.start_char + start,
                    end_char=parent_chunk.start_char + end,
                    token_count=len(child_content.split()),
                    metadata=ChunkMetadata(
                        parent_chunk_id=parent_chunk.id,
                        hierarchy_level=1,  # 0 = parent (section), 1 = child (subsection)
                        heading=parent_chunk.metadata.heading if parent_chunk.metadata else None,
                    ),
                )
                all_chunks.append(child_chunk)

        return all_chunks
