"""Chunking strategies for document processing.

Implementation of Issue #2.4: Chunking Strategy System

TODO:
- [x] Implement FixedSizeChunker (basic character-based)
- [x] Implement SemanticChunker (paragraph-based)
- [ ] Implement StructuralChunker (section-based with heading extraction)
- [ ] Implement HierarchicalChunker (nested chunks with parent-child relationships)
- [ ] Improve token counting (use tiktoken or proper tokenizers instead of split())
- [ ] Add configurable separators (\\n, \\n\\n, etc.)
- [ ] Add overlap handling to preserve context at chunk boundaries
- [ ] Add metadata enrichment (heading levels, page ranges, etc.)
- [ ] Add unit tests for each strategy
- [ ] Add benchmark tests for chunking performance

See Planning/ISSUES_BACKLOG.md Issue #2.4 for acceptance criteria.
"""

from __future__ import annotations

from uuid import uuid4

from kgbuilder.core import ChunkingStrategy
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
