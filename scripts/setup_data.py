#!/usr/bin/env python3
"""Setup script to ingest all data: PDFs to vector store and ontology to graph."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from langchain_community.embeddings.ollama import OllamaEmbeddings
from langchain_community.vectorstores.qdrant import Qdrant
from qdrant_client import QdrantClient

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.core.models import Document, DocumentMetadata
from kgbuilder.document.chunking.strategies import CharacterChunker
from kgbuilder.document.loaders import DocumentLoader
from kgbuilder.embedding.ollama import OllamaEmbeddingProvider
from kgbuilder.storage.graph import Neo4jStore
from kgbuilder.storage.vector import QdrantVectorStore

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger(__name__)


def load_ontology_to_neo4j(neo4j_store: Neo4jStore, ontology_path: Path) -> None:
    """Load OWL ontology into Neo4j as ontology nodes.
    
    Args:
        neo4j_store: Neo4j store instance
        ontology_path: Path to .owl file
    
    Raises:
        FileNotFoundError: If ontology file not found
    """
    if not ontology_path.exists():
        logger.error("ontology_not_found", path=str(ontology_path))
        raise FileNotFoundError(f"Ontology file not found: {ontology_path}")
    
    logger.info("loading_ontology", path=str(ontology_path))
    
    # For now, create ontology metadata in Neo4j
    # Full OWL parsing would require RDFlib - this just registers the ontology
    try:
        with open(ontology_path) as f:
            owl_content = f.read()
        
        # Store ontology metadata
        query = """
        MERGE (ont:Ontology {name: 'PlanningOntology'})
        SET ont.file = $file,
            ont.loaded_at = datetime(),
            ont.size_bytes = $size
        RETURN ont
        """
        
        result = neo4j_store.query(
            query,
            {"file": str(ontology_path), "size": len(owl_content)},
        )
        
        logger.info("ontology_loaded", ontology="PlanningOntology")
        
    except Exception as e:
        logger.error("ontology_load_failed", error=str(e))
        raise


def ingest_pdfs(
    pdf_dir: Path,
    qdrant_store: QdrantVectorStore,
    embedding_provider: OllamaEmbeddingProvider,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> int:
    """Ingest all PDFs from directory into vector store.
    
    Args:
        pdf_dir: Directory containing PDFs
        qdrant_store: Qdrant vector store
        embedding_provider: Embedding provider (Ollama)
        chunk_size: Characters per chunk
        chunk_overlap: Overlap between chunks
    
    Returns:
        Total number of chunks ingested
    """
    if not pdf_dir.exists():
        logger.error("pdf_dir_not_found", path=str(pdf_dir))
        raise FileNotFoundError(f"PDF directory not found: {pdf_dir}")
    
    # Find all PDFs
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    logger.info("found_pdfs", count=len(pdf_files))
    
    if not pdf_files:
        logger.warning("no_pdfs_found", directory=str(pdf_dir))
        return 0
    
    # Initialize chunker
    chunker = CharacterChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    # Initialize document loader - try different formats
    loader = DocumentLoader()
    
    total_chunks = 0
    
    for pdf_path in pdf_files:
        try:
            logger.info("processing_pdf", file=pdf_path.name)
            
            # Load document
            doc = loader.load(pdf_path)
            
            # Chunk the document
            chunks = chunker.chunk(doc.content)
            
            # Add to vector store with metadata
            for i, chunk in enumerate(chunks):
                metadata = {
                    "source": pdf_path.name,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk),
                }
                
                # Store in Qdrant
                qdrant_store.add_texts(
                    texts=[chunk],
                    metadatas=[metadata],
                )
                total_chunks += 1
            
            logger.info(
                "pdf_ingested",
                file=pdf_path.name,
                chunks=len(chunks),
            )
            
        except Exception as e:
            logger.error("pdf_ingestion_failed", file=pdf_path.name, error=str(e))
            continue
    
    logger.info("ingestion_complete", total_chunks=total_chunks)
    return total_chunks


def verify_data_setup() -> dict[str, Any]:
    """Verify data setup - check stores are populated.
    
    Returns:
        Dictionary with setup statistics
    """
    logger.info("verifying_setup")
    
    try:
        # Initialize clients
        neo4j_store = Neo4jStore(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password",
        )
        
        qdrant_client = QdrantClient(url="http://localhost:6333")
        
        # Get Neo4j stats
        node_count = neo4j_store.query("MATCH (n) RETURN count(n) as count")[0]["count"]
        edge_count = neo4j_store.query("MATCH ()-[r]->() RETURN count(r) as count")[0][
            "count"
        ]
        
        # Get Qdrant stats
        collections = qdrant_client.get_collections()
        vector_count = 0
        for collection in collections.collections:
            points = qdrant_client.count(collection.name)
            vector_count += points.count
        
        stats = {
            "neo4j_nodes": node_count,
            "neo4j_edges": edge_count,
            "qdrant_vectors": vector_count,
            "qdrant_collections": len(collections.collections),
        }
        
        logger.info("verification_complete", stats=stats)
        return stats
        
    except Exception as e:
        logger.error("verification_failed", error=str(e))
        return {}


def main() -> None:
    """Main setup flow."""
    logger.info("starting_data_setup")
    
    # Setup paths
    repo_root = Path(__file__).parent.parent
    pdf_dir = repo_root / "data" / "Decommissioning_Files"
    ontology_path = repo_root / "data" / "ontology" / "plan-ontology-v1.0.owl"
    
    # Initialize stores
    logger.info("initializing_stores")
    
    try:
        # Neo4j store
        neo4j_store = Neo4jStore(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password",
        )
        
        # Qdrant store
        qdrant_client = QdrantClient(url="http://localhost:6333")
        embedding_provider = OllamaEmbeddingProvider(
            model="nomic-embed-text",
            base_url="http://localhost:11434",
        )
        
        qdrant_store = QdrantVectorStore(client=qdrant_client)
        
        logger.info("stores_initialized")
        
        # Load ontology
        logger.info("step_1_loading_ontology")
        load_ontology_to_neo4j(neo4j_store, ontology_path)
        
        # Ingest PDFs
        logger.info("step_2_ingesting_pdfs")
        total_chunks = ingest_pdfs(pdf_dir, qdrant_store, embedding_provider)
        
        # Verify
        logger.info("step_3_verifying_setup")
        stats = verify_data_setup()
        
        logger.info(
            "setup_complete",
            chunks_ingested=total_chunks,
            stats=stats,
        )
        
    except Exception as e:
        logger.error("setup_failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
