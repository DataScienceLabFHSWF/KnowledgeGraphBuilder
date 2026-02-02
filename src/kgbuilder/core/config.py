"""Configuration models for document processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProcessingConfig:
    """Configuration for document processing pipeline.

    Attributes:
        enable_vlm: Enable Vision Language Model analysis.
        enable_caching: Cache processing results.
        language_detection: Detect document language.
        enhanced_table_extraction: Extract tables using advanced CV.
        enable_ocr: Use OCR for image-based documents.
        cache_dir: Directory for caching results.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap between chunks.
    """

    # Processing features
    enable_vlm: bool = False
    enable_caching: bool = True
    language_detection: bool = True
    enhanced_table_extraction: bool = True
    enable_ocr: bool = False

    # Paths and directories
    cache_dir: Path = field(default_factory=lambda: Path("/tmp/kgbuilder_cache"))
    temp_dir: Path = field(default_factory=lambda: Path("/tmp/kgbuilder_temp"))

    # Chunking configuration
    chunk_size: int = 1024
    chunk_overlap: int = 100

    # PDF processing
    pdf_dpi: int = 150
    pdf_max_pages: int | None = None

    # Model configuration
    preferred_vlm_model: str = "qwen2-vl"
    preferred_ocr_engine: str = "surya"

    # Resource limits
    max_document_size_mb: int = 100
    max_memory_usage_gb: int = 8
    max_workers: int = 4

    def __post_init__(self) -> None:
        """Ensure directories exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
