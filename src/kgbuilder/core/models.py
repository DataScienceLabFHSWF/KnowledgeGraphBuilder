"""Shared data models for KnowledgeGraphBuilder."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class FileType(Enum):
    """Supported document file types."""

    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"


@dataclass
class DocumentMetadata:
    """Metadata for a document."""

    title: str | None = None
    author: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    page_count: int | None = None
    word_count: int | None = None
    language: str | None = None
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkMetadata:
    """Metadata for a chunk."""

    section_title: str | None = None
    page_number: int | None = None
    paragraph_index: int | None = None
    heading_level: int | None = None
    is_table: bool = False
    is_list: bool = False


@dataclass
class Chunk:
    """A document chunk with metadata and provenance."""

    id: str
    content: str
    document_id: str
    start_char: int
    end_char: int
    token_count: int
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)
    embedding: Any | None = None  # NDArray[np.float32] | None


@dataclass
class Document:
    """A loaded document with chunks."""

    id: str
    content: str
    source_path: Path
    file_type: FileType
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    chunks: list[Chunk] = field(default_factory=list)


@dataclass
class Evidence:
    """Evidence supporting an extraction."""

    source_type: str  # "local_doc", "web", "kg"
    source_id: str  # chunk_id, url, or node_id
    text_span: str | None = None
    confidence: float = 1.0


@dataclass
class ExtractedEntity:
    """An extracted entity from text."""

    id: str
    label: str
    entity_type: str  # Ontology class URI or name
    description: str
    aliases: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class ExtractedRelation:
    """An extracted relation between entities."""

    id: str
    source_entity_id: str
    target_entity_id: str
    predicate: str  # Ontology relation URI or name
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
