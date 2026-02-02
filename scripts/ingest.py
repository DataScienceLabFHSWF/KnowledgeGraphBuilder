#!/usr/bin/env python3
"""Advanced unified ingestion pipeline.

Single script that handles:
1. Document processing (text, tables, metadata, VLM)
2. Vector embedding and Qdrant indexing

Entity extraction and KG building happen in a separate step after all documents
are indexed in the vector store. That stage uses full FusionRAG capabilities for
deep research and knowledge graph construction.
"""

import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import structlog
import ollama

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.core.config import ProcessingConfig
from kgbuilder.document.advanced_processor import AdvancedDocumentProcessor
from kgbuilder.storage.vector import QdrantStore


logger = structlog.get_logger(__name__)


class AdvancedIngestionPipeline:
    """End-to-end document ingestion and KG building."""

    def __init__(self, config: ProcessingConfig | None = None) -> None:
        """Initialize pipeline.

        Args:
            config: Processing configuration.
        """
        self.config = config or ProcessingConfig()
        self.processor = AdvancedDocumentProcessor(self.config)
        self.qdrant = QdrantStore()
        self.logger = structlog.get_logger(__name__)

    def ingest_document(self, file_path: str | Path) -> dict[str, Any]:
        """Ingest single document through indexing pipeline.

        Processes document and indexes chunks to Qdrant vector store.
        Entity extraction and KG building happen in a separate stage.

        Args:
            file_path: Path to PDF.

        Returns:
            Dictionary with ingestion results (file_path, chunks, status, timing).
        """
        file_path = Path(file_path)
        self.logger.info("ingesting_document", file_path=str(file_path))

        start_time = time.time()
        result = {
            "file_path": str(file_path),
            "status": "success",
            "stages": {},
        }

        try:
            # Stage 1: Document Processing
            self.logger.info("stage_1_processing", action="start")

            proc_start = time.time()
            doc_result = self.processor.process_document(file_path)

            result["stages"]["processing"] = {
                "chunks": len(doc_result.chunks),
                "tables": len(doc_result.tables) if doc_result.tables else 0,
                "time_sec": time.time() - proc_start,
            }

            self.logger.info(
                "stage_1_complete",
                chunks=len(doc_result.chunks),
                tables=len(doc_result.tables) if doc_result.tables else 0,
            )

            # Stage 2: Vector Embedding and Indexing
            self.logger.info("stage_2_indexing", action="start")

            emb_start = time.time()
            indexed = 0
            embedding_errors = 0
            total_embedding_time = 0
            expected_dim = None  # Will be set from first embedding

            for chunk_id, chunk_text in enumerate(doc_result.chunks):
                try:
                    # Compute embedding for chunk using ollama directly
                    emb_chunk_start = time.time()
                    response = ollama.embed(
                        model="qwen3-embedding",
                        input=chunk_text,
                    )
                    
                    # ollama.embed returns EmbedResponse with embeddings attribute
                    embedding = np.array(response.embeddings[0], dtype=np.float32)
                    emb_time = time.time() - emb_chunk_start
                    total_embedding_time += emb_time

                    # Set expected dimension from first embedding
                    if expected_dim is None:
                        expected_dim = embedding.shape[0]
                        self.logger.info("embedding_dimension_detected", dimension=expected_dim)
                    
                    # Verify embedding dimensions match
                    if embedding.shape[0] != expected_dim:
                        self.logger.warning(
                            "unexpected_embedding_dimension",
                            chunk_id=chunk_id,
                            expected=expected_dim,
                            actual=embedding.shape[0],
                        )

                    # Index to Qdrant
                    # Add full chunk text to metadata for retrieval
                    chunk_metadata = doc_result.metadatas[chunk_id].copy()
                    chunk_metadata["content"] = chunk_text
                    
                    self.qdrant.store(
                        ids=[f"{file_path.stem}_chunk_{chunk_id}"],
                        embeddings=[embedding],
                        metadata=[chunk_metadata],
                    )

                    indexed += 1

                    if (chunk_id + 1) % 5 == 0:
                        self.logger.debug(
                            "chunks_processed",
                            file=file_path.name,
                            processed=chunk_id + 1,
                            total=len(doc_result.chunks),
                            indexed=indexed,
                        )

                except Exception as e:
                    embedding_errors += 1
                    self.logger.warning(
                        "chunk_indexing_failed",
                        chunk_id=chunk_id,
                        error=str(e),
                        chunk_preview=chunk_text[:50],
                    )

            result["stages"]["indexing"] = {
                "indexed_chunks": indexed,
                "failed_chunks": embedding_errors,
                "total_chunks": len(doc_result.chunks),
                "time_sec": time.time() - emb_start,
                "avg_embedding_time_sec": total_embedding_time / max(indexed, 1),
                "embedding_success_rate": indexed / len(doc_result.chunks) if doc_result.chunks else 0,
            }

            self.logger.info(
                "stage_2_complete",
                indexed_chunks=indexed,
                failed_chunks=embedding_errors,
                total_chunks=len(doc_result.chunks),
                success_rate=f"{(indexed / len(doc_result.chunks) * 100):.1f}%" if doc_result.chunks else "N/A",
            )

            # Overall timing
            result["total_time_sec"] = time.time() - start_time

            self.logger.info(
                "ingestion_complete",
                file_path=str(file_path),
                status=result["status"],
                chunks_indexed=indexed,
                total_time_sec=result["total_time_sec"],
            )

            return result

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)

            self.logger.error(
                "ingestion_failed",
                file_path=str(file_path),
                error=str(e),
            )

            return result

    def ingest_directory(self, directory: str | Path) -> list[dict[str, Any]]:
        """Ingest all PDFs from directory.

        Args:
            directory: Directory path.

        Returns:
            List of ingestion results.
        """
        directory = Path(directory)

        if not directory.exists():
            raise ValueError(f"Directory not found: {directory}")

        pdf_files = sorted(directory.glob("*.pdf"))

        self.logger.info(
            "batch_ingestion_start",
            directory=str(directory),
            pdf_count=len(pdf_files),
        )

        results = []

        for idx, pdf_file in enumerate(pdf_files, 1):
            self.logger.info(
                "processing_file",
                file_num=idx,
                total=len(pdf_files),
                filename=pdf_file.name,
            )

            result = self.ingest_document(pdf_file)
            results.append(result)

            # Brief pause between files
            if idx < len(pdf_files):
                time.sleep(0.5)

        # Summary
        successful = sum(1 for r in results if r["status"] == "success")
        failed = len(results) - successful

        self.logger.info(
            "batch_ingestion_complete",
            directory=str(directory),
            total=len(results),
            successful=successful,
            failed=failed,
        )

        return results

    def load_ontology(self, ontology_path: str | Path) -> bool:
        """Load ontology to Fuseki RDF store.

        Args:
            ontology_path: Path to ontology file (OWL/RDF).

        Returns:
            Success status.
        """
        ontology_path = Path(ontology_path)

        if not ontology_path.exists():
            self.logger.error("ontology_not_found", path=str(ontology_path))
            return False

        self.logger.info("loading_ontology", path=str(ontology_path))

        try:
            self.fuseki.load_ontology(str(ontology_path))
            self.logger.info("ontology_loaded", path=str(ontology_path))
            return True

        except Exception as e:
            self.logger.error(
                "ontology_loading_failed",
                path=str(ontology_path),
                error=str(e),
            )
            return False


def main() -> None:
    """Run advanced ingestion pipeline."""
    # Setup logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )

    pipeline_start = time.time()
    logger.info("===== DOCUMENT INDEXING PIPELINE START =====")
    logger.info("pipeline_configuration", caching=True, language_detection=True, vlm_enabled=True)

    # Configuration
    config = ProcessingConfig(
        enable_vlm=True,  # VLM enabled for enhanced document understanding
        enable_caching=True,
        language_detection=True,
    )

    try:
        pipeline = AdvancedIngestionPipeline(config)
        logger.info("pipeline_initialized", success=True)
    except Exception as e:
        logger.error("pipeline_initialization_failed", error=str(e))
        return

    # Setup storage systems
    logger.info("setting_up_storage", storage_systems=["qdrant", "neo4j", "fuseki"])
    # Collection will be created dynamically by QdrantStore when first chunk is indexed
    logger.info("qdrant_initialized", url="http://localhost:6333", collection_name="kgbuilder")

    # Ingest documents
    data_dir = Path(__file__).parent.parent / "data" / "Decommissioning_Files"

    if not data_dir.exists():
        logger.error("data_directory_not_found", path=str(data_dir))
        return

    pdf_files = sorted(data_dir.glob("*.pdf"))
    logger.info("batch_start", total_pdfs=len(pdf_files), directory=str(data_dir))

    results = pipeline.ingest_directory(data_dir)

    # Detailed summary statistics
    total_docs = len(results)
    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    total_chunks = sum(r.get("chunks_indexed", 0) for r in results if r["status"] == "success")
    total_time = time.time() - pipeline_start

    logger.info(
        "pipeline_complete",
        total_documents=total_docs,
        successful_documents=successful,
        failed_documents=failed,
        success_rate=f"{(successful/total_docs*100):.1f}%" if total_docs > 0 else "N/A",
        total_chunks_indexed=total_chunks,
        avg_chunks_per_doc=f"{(total_chunks/successful):.1f}" if successful > 0 else "N/A",
        total_time_sec=f"{total_time:.2f}",
        avg_time_per_doc_sec=f"{(total_time/total_docs):.2f}" if total_docs > 0 else "N/A",
    )

    # Detailed per-document results
    logger.info("\n=== PER-DOCUMENT RESULTS ===")
    for i, result in enumerate(results[:5], 1):
        logger.info(
            f"doc_{i}",
            file=Path(result["file_path"]).name,
            status=result["status"],
            chunks=result.get("chunks_indexed", 0),
            time_sec=f"{result.get('total_time_sec', 0):.2f}",
        )

    if failed > 0:
        logger.warning(f"\n=== FAILURES ({failed} DOCUMENTS) ===")
        for result in [r for r in results if r["status"] == "failed"]:
            logger.error(
                "document_failed",
                file=Path(result["file_path"]).name,
                error=result.get("error", "Unknown error"),
            )

    logger.info("===== PIPELINE COMPLETE =====")


if __name__ == "__main__":
    main()
