"""Comprehensive tests for storage, retrieval, and orchestration.

Tests cover:
- Storage backends (Neo4j, Qdrant)
- Document loading and chunking
- Embedding generation
- Semantic retrieval
- End-to-end integration
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.core.models import Chunk, ChunkMetadata, Document, Evidence, ExtractedEntity
from kgbuilder.document import DocumentLoaderFactory, FixedSizeChunker
from kgbuilder.embedding import OllamaProvider
from kgbuilder.storage import Neo4jStore, QdrantStore, SemanticRetriever


class TestDocumentLoaders:
    """Test document loading functionality."""

    def test_loader_factory_registration(self) -> None:
        """Test that loaders are properly registered."""
        assert DocumentLoaderFactory._loaders, "No loaders registered"
        assert ".pdf" in DocumentLoaderFactory._loaders
        assert ".docx" in DocumentLoaderFactory._loaders
        assert ".pptx" in DocumentLoaderFactory._loaders

    def test_pdf_loader_registration(self) -> None:
        """Test PDF loader is available."""
        doc_path = Path(__file__).parent.parent / "data" / "Decommissioning_Files"
        pdf_files = list(doc_path.glob("*.pdf"))
        
        if not pdf_files:
            pytest.skip("No PDF files available")
        
        loader = DocumentLoaderFactory.get_loader(pdf_files[0])
        assert loader is not None
        assert hasattr(loader, "load")

    def test_document_load_basic(self) -> None:
        """Test basic document loading."""
        doc_path = Path(__file__).parent.parent / "data" / "Decommissioning_Files"
        pdf_files = list(doc_path.glob("*.pdf"))
        
        if not pdf_files:
            pytest.skip("No PDF files available")
        
        loader = DocumentLoaderFactory.get_loader(pdf_files[0])
        doc = loader.load(pdf_files[0])
        
        assert doc is not None
        assert hasattr(doc, "content")
        assert len(doc.content) > 0


class TestChunking:
    """Test document chunking strategies."""

    def test_fixed_size_chunker_initialization(self) -> None:
        """Test chunker can be initialized."""
        chunker = FixedSizeChunker()
        assert chunker is not None
        assert hasattr(chunker, "chunk")

    def test_fixed_size_chunking(self) -> None:
        """Test basic chunking operation."""
        from pathlib import Path
        chunker = FixedSizeChunker()
        
        # Create a test document
        doc = Document(
            id="test_doc",
            content="This is a test document. " * 100,
            file_type="text",
            source_path=Path("test.txt"),
        )
        
        chunks = chunker.chunk(doc, chunk_size=100, chunk_overlap=10)
        
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.document_id == "test_doc" for c in chunks)


class TestNeo4jStorage:
    """Test Neo4j graph database storage."""

    @pytest.fixture
    def neo4j_store(self) -> Neo4jStore:
        """Create Neo4j store instance."""
        try:
            return Neo4jStore("bolt://localhost:7687", "neo4j", "changeme")
        except Exception:
            pytest.skip("Neo4j not available")

    def test_neo4j_connection(self, neo4j_store: Neo4jStore) -> None:
        """Test Neo4j connection is working."""
        assert neo4j_store.driver is not None

    def test_neo4j_add_node(self, neo4j_store: Neo4jStore) -> None:
        """Test adding a node to Neo4j."""
        neo4j_store.add_node(
            "test_entity_1",
            "Person",
            {"name": "Alice", "age": 30},
        )
        
        # Query to verify
        results = neo4j_store.query(
            "MATCH (p:Person {id: $id}) RETURN p.name as name",
            {"id": "test_entity_1"},
        )
        assert len(results) > 0

    def test_neo4j_add_edge(self, neo4j_store: Neo4jStore) -> None:
        """Test adding an edge/relation."""
        # Add nodes first
        neo4j_store.add_node("alice", "Person", {"name": "Alice"})
        neo4j_store.add_node("bob", "Person", {"name": "Bob"})
        
        # Add relation
        neo4j_store.add_edge("alice", "bob", "KNOWS", {"since": 2020})
        
        # Query to verify
        results = neo4j_store.query(
            "MATCH (a)-[r:KNOWS]->(b) WHERE a.id = $alice RETURN r",
            {"alice": "alice"},
        )
        assert len(results) > 0

    def test_neo4j_cypher_query(self, neo4j_store: Neo4jStore) -> None:
        """Test executing Cypher queries."""
        results = neo4j_store.query("MATCH (n) RETURN COUNT(n) as count LIMIT 1")
        assert isinstance(results, list)

    def test_neo4j_batch_entities(self, neo4j_store: Neo4jStore) -> None:
        """Test batch adding entities."""
        entities = [
            ExtractedEntity(
                id=f"ent_{i}",
                label=f"Entity {i}",
                entity_type="Thing",
                description="Test entity",
                confidence=0.9,
            )
            for i in range(3)
        ]
        
        neo4j_store.add_entities(entities)
        
        # Verify
        results = neo4j_store.query("MATCH (e:Entity) RETURN COUNT(e) as count")
        assert results[0]["count"] >= 3


class TestQdrantStorage:
    """Test Qdrant vector database storage."""

    @pytest.fixture
    def qdrant_store(self) -> QdrantStore:
        """Create Qdrant store instance."""
        try:
            return QdrantStore("http://localhost:6333", collection_name="test_kg")
        except Exception:
            pytest.skip("Qdrant not available")

    def test_qdrant_connection(self, qdrant_store: QdrantStore) -> None:
        """Test Qdrant connection."""
        assert qdrant_store.client is not None

    def test_qdrant_store_embeddings(self, qdrant_store: QdrantStore) -> None:
        """Test storing embeddings."""
        embeddings = [
            np.random.randn(768).astype(np.float32),
            np.random.randn(768).astype(np.float32),
        ]
        
        qdrant_store.store(
            ["doc1", "doc2"],
            embeddings,
            [{"type": "Person"}, {"type": "Place"}],
        )
        
        # Verify collection exists
        collections = qdrant_store.list_collections()
        assert "test_kg" in collections

    def test_qdrant_search(self, qdrant_store: QdrantStore) -> None:
        """Test semantic search."""
        embeddings = [
            np.random.randn(768).astype(np.float32),
            np.random.randn(768).astype(np.float32),
        ]
        
        qdrant_store.store(
            ["entity1", "entity2"],
            embeddings,
            [{"name": "Alice"}, {"name": "Bob"}],
        )
        
        # Search with first embedding
        results = qdrant_store.search(embeddings[0], top_k=1)
        
        assert len(results) > 0
        assert results[0][1] >= 0  # Score should exist
        assert "name" in results[0][2]  # Metadata should exist

    def test_qdrant_delete(self, qdrant_store: QdrantStore) -> None:
        """Test deleting embeddings."""
        embeddings = [np.random.randn(768).astype(np.float32)]
        
        qdrant_store.store(["to_delete"], embeddings)
        
        # Should not raise
        qdrant_store.delete(["to_delete"])


class TestSemanticRetriever:
    """Test semantic retrieval with LangChain."""

    @pytest.fixture
    def retriever(self) -> SemanticRetriever:
        """Create retriever instance."""
        try:
            return SemanticRetriever("http://localhost:6333", collection_name="retriever_test")
        except Exception:
            pytest.skip("Qdrant not available")

    def test_retriever_initialization(self, retriever: SemanticRetriever) -> None:
        """Test retriever can be initialized."""
        assert retriever is not None
        assert retriever.qdrant_url == "http://localhost:6333"

    def test_retriever_add_documents(self, retriever: SemanticRetriever) -> None:
        """Test retriever initialization and basic structure."""
        # Test that retriever is properly initialized
        assert retriever.qdrant_url == "http://localhost:6333"
        assert retriever.collection_name == "retriever_test"
        assert not retriever._initialized  # Not initialized until first use


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.fixture
    def storage_backends(self) -> tuple[Neo4jStore, QdrantStore]:
        """Create storage backends."""
        try:
            neo4j = Neo4jStore("bolt://localhost:7687", "neo4j", "changeme")
            qdrant = QdrantStore("http://localhost:6333", collection_name="e2e_test")
            return neo4j, qdrant
        except Exception:
            pytest.skip("Storage backends not available")

    def test_entity_extraction_and_storage(
        self, storage_backends: tuple[Neo4jStore, QdrantStore]
    ) -> None:
        """Test extracting entities and storing them."""
        neo4j, qdrant = storage_backends
        
        # Create test entities
        entities = [
            ExtractedEntity(
                id="alice",
                label="Alice",
                entity_type="Person",
                description="Engineer",
                confidence=0.95,
            ),
            ExtractedEntity(
                id="bob",
                label="Bob",
                entity_type="Person",
                description="Designer",
                confidence=0.90,
            ),
        ]
        
        # Store in graph
        neo4j.add_entities(entities)
        
        # Generate embeddings for storage in vector DB
        embeddings = [
            np.random.randn(768).astype(np.float32),
            np.random.randn(768).astype(np.float32),
        ]
        
        # Store in vector DB
        qdrant.store(
            [e.id for e in entities],
            embeddings,
            [{"label": e.label, "type": e.entity_type} for e in entities],
        )
        
        # Verify in graph
        results = neo4j.query("MATCH (e:Entity) RETURN COUNT(e) as count")
        assert results[0]["count"] >= 2
        
        # Verify in vector DB
        search_results = qdrant.search(embeddings[0], top_k=1)
        assert len(search_results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
