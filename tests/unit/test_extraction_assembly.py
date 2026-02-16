"""Tests for entity extraction, relation extraction, and KG assembly.

Tests cover:
- LangChain extraction chains
- Entity deduplication
- SimpleKGAssembler orchestration
- End-to-end document-to-KG pipeline
"""

from unittest.mock import Mock, patch

import pytest

from kgbuilder.assembly.core import GraphStatistics, SimpleKGAssembler
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation
from kgbuilder.extraction.chains import ExtractionChains
from kgbuilder.extraction.entity import OntologyClassDef
from kgbuilder.extraction.relation import OntologyRelationDef


class TestExtractionChains:
    """Tests for LangChain extraction chains."""

    def test_create_entity_extraction_chain(self) -> None:
        """Test entity extraction chain creation."""
        with patch("kgbuilder.extraction.chains.ChatOllama"):
            chain = ExtractionChains.create_entity_extraction_chain()
            assert chain is not None

    def test_create_relation_extraction_chain(self) -> None:
        """Test relation extraction chain creation."""
        with patch("kgbuilder.extraction.chains.ChatOllama"):
            chain = ExtractionChains.create_relation_extraction_chain()
            assert chain is not None

    def test_format_ontology_section(self) -> None:
        """Test ontology section formatting."""
        classes = [
            OntologyClassDef(
                uri="http://ex.org/Person",
                label="Person",
                description="A human being",
                examples=["Alice", "Bob"],
            ),
            OntologyClassDef(
                uri="http://ex.org/Organization",
                label="Organization",
                description="A group or institution",
                examples=["Google", "MIT"],
            ),
        ]

        result = ExtractionChains.format_ontology_section(classes)
        assert "Person" in result
        assert "Organization" in result
        assert "Alice" in result
        assert "Google" in result
        assert "A human being" in result

    def test_format_entities_list(self) -> None:
        """Test entities list formatting for prompts."""
        entities = [
            ExtractedEntity(
                id="ent_1",
                label="Alice",
                entity_type="Person",
                description="A researcher",
                confidence=0.95,
            ),
            ExtractedEntity(
                id="ent_2",
                label="Google",
                entity_type="Organization",
                description="Tech company",
                confidence=0.99,
            ),
        ]

        result = ExtractionChains.format_entities_list(entities)
        assert "ent_1" in result
        assert "ent_2" in result
        assert "Alice" in result
        assert "Google" in result
        assert "0.95" in result
        assert "0.99" in result

    def test_format_relations_section(self) -> None:
        """Test relations section formatting."""
        relations = [
            OntologyRelationDef(
                uri="http://ex.org/worksAt",
                label="works at",
                description="Employment relation",
                domain=["Person"],
                range=["Organization"],
                is_functional=False,
            ),
            OntologyRelationDef(
                uri="http://ex.org/locatedIn",
                label="located in",
                description="Location relation",
                domain=["Organization", "Facility"],
                range=["Location"],
                is_functional=True,
            ),
        ]

        result = ExtractionChains.format_relations_section(relations)
        assert "works at" in result
        assert "located in" in result
        assert "Person" in result
        assert "Organization" in result
        assert "Functional: Yes" in result


class TestSimpleKGAssembler:
    """Tests for SimpleKGAssembler."""

    @pytest.fixture
    def mock_graph_store(self) -> Mock:
        """Create mock Neo4j store."""
        return Mock()

    @pytest.fixture
    def mock_vector_store(self) -> Mock:
        """Create mock Qdrant store."""
        return Mock()

    @pytest.fixture
    def assembler(
        self, mock_graph_store: Mock, mock_vector_store: Mock
    ) -> SimpleKGAssembler:
        """Create assembler with mocked stores."""
        with patch("kgbuilder.assembly.core.ChatOllama"):
            with patch("kgbuilder.assembly.core.CharacterTextSplitter"):
                return SimpleKGAssembler(
                    graph_store=mock_graph_store,
                    vector_store=mock_vector_store,
                )

    def test_assembler_initialization(self, assembler: SimpleKGAssembler) -> None:
        """Test assembler initialization."""
        assert assembler is not None
        assert assembler._graph is not None
        assert assembler._vector_store is not None
        assert assembler.dedup_threshold == 0.85

    def test_build_extraction_pipeline(self, assembler: SimpleKGAssembler) -> None:
        """Test extraction pipeline creation."""
        with patch("kgbuilder.extraction.chains.ChatOllama"):
            pipeline = assembler.build_extraction_pipeline()
            assert pipeline is not None

    def test_assemble_with_entities_and_relations(
        self, assembler: SimpleKGAssembler, mock_graph_store: Mock
    ) -> None:
        """Test assembling entities and relations."""
        entities = [
            ExtractedEntity(
                id="ent_1",
                label="Alice",
                entity_type="Person",
                description="A researcher",
                confidence=0.95,
            ),
            ExtractedEntity(
                id="ent_2",
                label="Bob",
                entity_type="Person",
                description="Another researcher",
                confidence=0.90,
            ),
        ]

        relations = [
            ExtractedRelation(
                id="rel_1",
                source_entity_id="ent_1",
                target_entity_id="ent_2",
                predicate="knows",
                confidence=0.85,
            ),
        ]

        assembler.assemble(entities, relations)

        # Verify calls to graph store
        assert mock_graph_store.add_entities.called
        assert mock_graph_store.add_relations.called

    def test_deduplicate_entities_same_label_type(
        self, assembler: SimpleKGAssembler
    ) -> None:
        """Test entity deduplication with same label and type."""
        entities = [
            ExtractedEntity(
                id="ent_1",
                label="Alice",
                entity_type="Person",
                description="Researcher",
                confidence=0.85,
            ),
            ExtractedEntity(
                id="ent_2",
                label="Alice",
                entity_type="Person",
                description="Another mention",
                confidence=0.95,
            ),
        ]

        deduplicated = assembler._deduplicate_entities(entities)

        assert len(deduplicated) == 1
        assert deduplicated[0].id == "ent_2"  # Higher confidence wins
        assert deduplicated[0].confidence == 0.95

    def test_deduplicate_entities_case_insensitive(
        self, assembler: SimpleKGAssembler
    ) -> None:
        """Test entity deduplication is case insensitive."""
        entities = [
            ExtractedEntity(
                id="ent_1",
                label="alice",
                entity_type="Person",
                description="Researcher",
                confidence=0.85,
            ),
            ExtractedEntity(
                id="ent_2",
                label="ALICE",
                entity_type="Person",
                description="Another mention",
                confidence=0.90,
            ),
        ]

        deduplicated = assembler._deduplicate_entities(entities)

        assert len(deduplicated) == 1
        assert deduplicated[0].label in ("alice", "ALICE")

    def test_deduplicate_entities_different_types(
        self, assembler: SimpleKGAssembler
    ) -> None:
        """Test entity deduplication with different types keeps both."""
        entities = [
            ExtractedEntity(
                id="ent_1",
                label="Apple",
                entity_type="Company",
                description="Tech company",
                confidence=0.95,
            ),
            ExtractedEntity(
                id="ent_2",
                label="Apple",
                entity_type="Fruit",
                description="A fruit",
                confidence=0.90,
            ),
        ]

        deduplicated = assembler._deduplicate_entities(entities)

        assert len(deduplicated) == 2

    def test_get_statistics(self, assembler: SimpleKGAssembler) -> None:
        """Test statistics retrieval."""
        stats = assembler.get_statistics()

        assert isinstance(stats, GraphStatistics)
        assert stats.num_nodes == 0
        assert stats.num_edges == 0

    def test_query_graph(
        self, assembler: SimpleKGAssembler, mock_graph_store: Mock
    ) -> None:
        """Test graph query execution."""
        mock_graph_store.query.return_value = [
            {"n": {"id": "ent_1", "label": "Alice"}},
        ]

        result = assembler.query_graph("MATCH (n:Entity) RETURN n")

        assert len(result) == 1
        assert result[0]["n"]["id"] == "ent_1"
        mock_graph_store.query.assert_called_once()


class TestEntityDeduplication:
    """Tests for entity deduplication logic."""

    @pytest.fixture
    def assembler(self) -> SimpleKGAssembler:
        """Create assembler with mocked stores."""
        with patch("kgbuilder.assembly.core.ChatOllama"):
            with patch("kgbuilder.assembly.core.CharacterTextSplitter"):
                return SimpleKGAssembler(
                    graph_store=Mock(),
                    vector_store=Mock(),
                )

    def test_deduplicate_preserves_highest_confidence(
        self, assembler: SimpleKGAssembler
    ) -> None:
        """Test that deduplication preserves highest confidence entity."""
        entities = [
            ExtractedEntity(
                id="low",
                label="Entity",
                entity_type="Type",
                description="Low confidence",
                confidence=0.5,
            ),
            ExtractedEntity(
                id="high",
                label="Entity",
                entity_type="Type",
                description="High confidence",
                confidence=0.99,
            ),
        ]

        deduplicated = assembler._deduplicate_entities(entities)

        assert len(deduplicated) == 1
        assert deduplicated[0].confidence == 0.99
        assert deduplicated[0].id == "high"

    def test_deduplicate_empty_list(self, assembler: SimpleKGAssembler) -> None:
        """Test deduplication with empty entity list."""
        deduplicated = assembler._deduplicate_entities([])
        assert deduplicated == []

    def test_deduplicate_single_entity(
        self, assembler: SimpleKGAssembler
    ) -> None:
        """Test deduplication with single entity."""
        entities = [
            ExtractedEntity(
                id="ent_1",
                label="Alice",
                entity_type="Person",
                description="A person",
                confidence=0.95,
            ),
        ]

        deduplicated = assembler._deduplicate_entities(entities)

        assert len(deduplicated) == 1
        assert deduplicated[0] == entities[0]


class TestAssemblyResult:
    """Tests for assembly result data model."""

    def test_assembly_result_creation(self) -> None:
        """Test creating assembly result."""
        from kgbuilder.assembly.core import AssemblyResult

        result = AssemblyResult(
            document_id="doc_1",
            entities_extracted=10,
            relations_extracted=5,
            entities_stored=8,
            relations_stored=4,
            duplicates_removed=2,
            processing_time_ms=150.5,
        )

        assert result.document_id == "doc_1"
        assert result.entities_extracted == 10
        assert result.entities_stored == 8
        assert result.duplicates_removed == 2
