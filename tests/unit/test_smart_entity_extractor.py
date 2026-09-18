"""Tests for SmartEntityExtractor with semantic filtering.

Tests cover:
- Initialization with/without embedding provider
- Semantic filtering of ontology classes
- Token tracking and filtering metrics
- Fallback behavior when embedding provider unavailable
- Integration with parent LLMEntityExtractor
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from kgbuilder.extraction.entity import OntologyClassDef
from kgbuilder.extraction.smart_entity_extractor import (
    FilteringMetrics,
    SmartEntityExtractor,
)


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Create mock LLM provider."""
    provider = MagicMock()
    provider.model_name = "test-model"
    return provider


@pytest.fixture
def mock_embedding_provider() -> MagicMock:
    """Create mock embedding provider with embed_text method."""
    provider = MagicMock()

    def mock_embed(text: str) -> np.ndarray:
        # Return deterministic embedding based on text
        np.random.seed(hash(text) % (2**32))
        return np.random.randn(128).astype(np.float32)

    provider.embed_text = MagicMock(side_effect=mock_embed)
    return provider


@pytest.fixture
def sample_ontology_classes() -> list[OntologyClassDef]:
    """Create sample ontology classes for testing."""
    return [
        OntologyClassDef(
            uri="http://example.org/Person",
            label="Person",
            description="A human individual",
            examples=["John", "Jane"],
        ),
        OntologyClassDef(
            uri="http://example.org/Organization",
            label="Organization",
            description="A legal entity",
            examples=["ACME Corp", "Google"],
        ),
        OntologyClassDef(
            uri="http://example.org/Location",
            label="Location",
            description="A geographic place",
            examples=["New York", "London"],
        ),
        OntologyClassDef(
            uri="http://example.org/Vehicle",
            label="Vehicle",
            description="A transportation device",
            examples=["Car", "Truck"],
        ),
        OntologyClassDef(
            uri="http://example.org/Document",
            label="Document",
            description="Written material",
            examples=["Letter", "Contract"],
        ),
    ]


class TestSmartEntityExtractorInitialization:
    """Test SmartEntityExtractor initialization."""

    def test_init_with_embedding_provider(
        self, mock_llm_provider: MagicMock, mock_embedding_provider: MagicMock
    ) -> None:
        """Test initialization with embedding provider."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
            max_classes=10,
        )

        assert extractor.embedding_provider is mock_embedding_provider
        assert extractor.max_classes == 10
        assert extractor.last_filtering_metrics is None

    def test_init_without_embedding_provider(
        self, mock_llm_provider: MagicMock
    ) -> None:
        """Test initialization without embedding provider."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=None,
            max_classes=15,
        )

        assert extractor.embedding_provider is None
        assert extractor.max_classes == 15

    def test_init_with_custom_parameters(
        self, mock_llm_provider: MagicMock, mock_embedding_provider: MagicMock
    ) -> None:
        """Test initialization with custom parameters."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
            max_classes=5,
            confidence_threshold=0.7,
            max_retries=5,
            token_budget_target=2000,
        )

        assert extractor.max_classes == 5
        assert extractor.confidence_threshold == 0.7
        assert extractor.max_retries == 5
        assert extractor.token_budget_target == 2000


class TestOntologyFiltering:
    """Test semantic ontology class filtering."""

    def test_filter_when_below_threshold(
        self,
        mock_llm_provider: MagicMock,
        mock_embedding_provider: MagicMock,
        sample_ontology_classes: list[OntologyClassDef],
    ) -> None:
        """Test filtering when classes already below threshold."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
            max_classes=20,  # Higher than available classes
        )

        text = "Test document about people and places"
        filtered = extractor._filter_relevant_classes(text, sample_ontology_classes)

        # Should return all classes since they're below max_classes
        assert len(filtered) == len(sample_ontology_classes)
        metrics = extractor.get_filtering_metrics()
        assert metrics is not None
        assert metrics.reduction_percent == 0.0
        assert metrics.total_classes == 5

    def test_filter_reduces_classes(
        self,
        mock_llm_provider: MagicMock,
        mock_embedding_provider: MagicMock,
        sample_ontology_classes: list[OntologyClassDef],
    ) -> None:
        """Test filtering reduces number of classes."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
            max_classes=2,
        )

        text = "John Smith is a person working at ACME Corp"
        filtered = extractor._filter_relevant_classes(text, sample_ontology_classes)

        assert len(filtered) <= 2
        metrics = extractor.get_filtering_metrics()
        assert metrics is not None
        assert metrics.filtered_classes <= 2
        assert metrics.total_classes == 5

    def test_filter_tracking_metrics(
        self,
        mock_llm_provider: MagicMock,
        mock_embedding_provider: MagicMock,
        sample_ontology_classes: list[OntologyClassDef],
    ) -> None:
        """Test that filtering metrics are tracked correctly."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
            max_classes=2,
        )

        text = "Sample text"
        extractor._filter_relevant_classes(text, sample_ontology_classes)

        metrics = extractor.get_filtering_metrics()
        assert metrics is not None
        assert metrics.total_classes == 5
        assert metrics.filtered_classes <= 2
        assert 0 <= metrics.reduction_percent <= 100
        assert metrics.embedding_time_ms >= 0
        assert metrics.filtering_time_ms >= 0
        assert metrics.estimated_token_savings >= 0

    def test_filter_no_embedding_provider_fallback(
        self,
        mock_llm_provider: MagicMock,
        sample_ontology_classes: list[OntologyClassDef],
    ) -> None:
        """Test fallback when embedding provider is None."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=None,
            max_classes=2,
        )

        text = "Sample text"
        filtered = extractor._filter_relevant_classes(text, sample_ontology_classes)

        # Should return first max_classes
        assert len(filtered) == 2
        assert filtered == sample_ontology_classes[:2]

    def test_filter_embedding_error_fallback(
        self,
        mock_llm_provider: MagicMock,
        mock_embedding_provider: MagicMock,
        sample_ontology_classes: list[OntologyClassDef],
    ) -> None:
        """Test fallback when embedding provider raises error."""
        mock_embedding_provider.embed_text.side_effect = RuntimeError("Embedding failed")

        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
            max_classes=2,
        )

        text = "Sample text"
        filtered = extractor._filter_relevant_classes(text, sample_ontology_classes)

        # Should still return first max_classes as fallback
        assert len(filtered) == 2
        assert filtered == sample_ontology_classes[:2]


class TestCosineSimilarity:
    """Test cosine similarity computation."""

    def test_cosine_similarity_identical_vectors(self) -> None:
        """Test cosine similarity for identical vectors."""
        vec = np.array([1.0, 0.0, 0.0])
        similarity = SmartEntityExtractor._cosine_similarity(vec, vec)
        assert np.isclose(similarity, 1.0)

    def test_cosine_similarity_orthogonal_vectors(self) -> None:
        """Test cosine similarity for orthogonal vectors."""
        vec_a = np.array([1.0, 0.0, 0.0])
        vec_b = np.array([0.0, 1.0, 0.0])
        similarity = SmartEntityExtractor._cosine_similarity(vec_a, vec_b)
        assert np.isclose(similarity, 0.0, atol=1e-6)

    def test_cosine_similarity_zero_vector_handling(self) -> None:
        """Test cosine similarity with zero vectors."""
        vec_a = np.array([0.0, 0.0, 0.0])
        vec_b = np.array([1.0, 0.0, 0.0])
        similarity = SmartEntityExtractor._cosine_similarity(vec_a, vec_b)
        assert similarity == 0.0

    def test_cosine_similarity_list_input(self) -> None:
        """Test cosine similarity with list inputs."""
        list_a = [1.0, 0.0, 0.0]
        list_b = [0.7, 0.7, 0.0]
        similarity = SmartEntityExtractor._cosine_similarity(list_a, list_b)
        # Should be close to 0.7 (normalized)
        assert 0.6 < similarity < 0.8

    def test_cosine_similarity_error_handling(self) -> None:
        """Test cosine similarity error handling."""
        similarity = SmartEntityExtractor._cosine_similarity(None, None)
        assert similarity == 0.0

        similarity = SmartEntityExtractor._cosine_similarity([1, 2], "invalid")
        assert similarity == 0.0


class TestClassToText:
    """Test class-to-text conversion."""

    def test_class_with_all_fields(self) -> None:
        """Test class-to-text with all fields populated."""
        cls = OntologyClassDef(
            uri="http://example.org/Person",
            label="Person",
            description="A human individual",
            examples=["John", "Jane"],
        )

        text = SmartEntityExtractor._class_to_text(cls)

        assert "Person" in text
        assert "A human individual" in text
        assert "John" in text
        assert "Jane" in text

    def test_class_minimal_fields(self) -> None:
        """Test class-to-text with minimal fields."""
        cls = OntologyClassDef(
            uri="http://example.org/Thing",
            label="Thing",
        )

        text = SmartEntityExtractor._class_to_text(cls)

        assert "Thing" in text
        # Should not crash with None description/examples


class TestExtractWithFiltering:
    """Test extract method with filtering integration."""

    def test_extract_with_filtering_enabled(
        self,
        mock_llm_provider: MagicMock,
        mock_embedding_provider: MagicMock,
        sample_ontology_classes: list[OntologyClassDef],
    ) -> None:
        """Test extract calls parent with filtered classes."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
            max_classes=2,
        )

        # Mock parent extract method
        with patch.object(
            extractor.__class__.__bases__[0], "extract", return_value=[]
        ) as mock_parent_extract:
            text = "Test document"
            extractor.extract(text, sample_ontology_classes)

            # Parent extract should be called with filtered classes
            mock_parent_extract.assert_called_once()
            args, kwargs = mock_parent_extract.call_args
            # Check that ontology_classes argument is filtered
            assert len(kwargs.get("ontology_classes", [])) <= 2

    def test_extract_with_filtering_disabled(
        self,
        mock_llm_provider: MagicMock,
        mock_embedding_provider: MagicMock,
        sample_ontology_classes: list[OntologyClassDef],
    ) -> None:
        """Test extract with filtering disabled."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
            max_classes=2,
        )

        with patch.object(
            extractor.__class__.__bases__[0], "extract", return_value=[]
        ) as mock_parent_extract:
            text = "Test document"
            extractor.extract(
                text, sample_ontology_classes, apply_filtering=False
            )

            # Parent extract should be called with all classes
            mock_parent_extract.assert_called_once()
            args, kwargs = mock_parent_extract.call_args
            assert len(kwargs.get("ontology_classes", [])) == len(
                sample_ontology_classes
            )

    def test_extract_empty_ontology(
        self,
        mock_llm_provider: MagicMock,
        mock_embedding_provider: MagicMock,
    ) -> None:
        """Test extract with empty ontology."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
        )

        result = extractor.extract("Test text", [])

        assert result == []


class TestTokenOptimization:
    """Test token optimization aspects."""

    def test_filtering_reduces_token_budget(
        self,
        mock_llm_provider: MagicMock,
        mock_embedding_provider: MagicMock,
        sample_ontology_classes: list[OntologyClassDef],
    ) -> None:
        """Test that filtering estimates token savings."""
        extractor = SmartEntityExtractor(
            llm_provider=mock_llm_provider,
            embedding_provider=mock_embedding_provider,
            max_classes=2,
        )

        text = "Test"
        extractor._filter_relevant_classes(text, sample_ontology_classes)

        metrics = extractor.get_filtering_metrics()
        assert metrics is not None

        # Estimate tokens for each class: ~15 tokens per class description
        expected_reduction = (
            sample_ontology_classes.__len__() - 2
        ) * 15
        assert metrics.estimated_token_savings >= (
            expected_reduction * 0.8
        )  # Allow some variance
