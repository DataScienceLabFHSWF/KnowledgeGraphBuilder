#!/usr/bin/env python3
import pytest
pytest.skip("legacy integration script - skip until converted", allow_module_level=True)

"""Test entity extraction on sample decommissioning documents.

This script demonstrates the extraction pipeline:
1. Load 3 sample PDFs
2. Extract text chunks
3. Extract entities using QWEN3 with planning ontology
4. Display results

Usage:
    python scripts/test_extraction.py [--skip-extraction]
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kgbuilder.document import DocumentLoaderFactory
from kgbuilder.document.chunking import FixedSizeChunker
from kgbuilder.embedding.ollama import OllamaProvider
from kgbuilder.extraction.entity import LLMEntityExtractor, OntologyClassDef


def load_sample_documents(max_docs: int = 3) -> list[tuple[str, str]]:
    """Load sample decommissioning documents.

    Args:
        max_docs: Maximum number of documents to load

    Returns:
        List of (filename, content) tuples
    """
    doc_dir = Path("data/Decommissioning_Files")

    if not doc_dir.exists():
        print(f"❌ Document directory not found: {doc_dir}")
        return []

    pdf_files = sorted(list(doc_dir.glob("*.pdf")))[:max_docs]

    if not pdf_files:
        print(f"❌ No PDF files found in {doc_dir}")
        return []

    print(f"\n📄 Found {len(pdf_files)} documents (loading first {max_docs})")

    documents = []

    for pdf_file in pdf_files:
        try:
            print(f"  Loading: {pdf_file.name}", end=" ... ")
            loader = DocumentLoaderFactory.get_loader(pdf_file)
            doc = loader.load(pdf_file)
            documents.append((pdf_file.name, doc.content))
            print(f"✓ ({len(doc.content)} chars)")
        except Exception as e:
            print(f"✗ Error: {e}")

    return documents


def create_ontology_classes() -> list[OntologyClassDef]:
    """Create ontology classes for entity extraction.

    Based on AI Planning Ontology + decommissioning domain.

    Returns:
        List of OntologyClassDef for guided extraction
    """
    return [
        OntologyClassDef(
            uri="http://planning.ontology/Facility",
            label="Facility",
            description="Nuclear power plant or facility component (e.g., reactor, building)",
            examples=[
                "Kernkraftwerk Emsland",
                "Reaktorgebäude",
                "Kontrollzentrum",
            ],
        ),
        OntologyClassDef(
            uri="http://planning.ontology/Organization",
            label="Organization",
            description="Company, contractor, or regulatory body involved in decommissioning",
            examples=[
                "E.ON",
                "Bundesamt für Strahlenschutz",
                "Stadtrat",
            ],
        ),
        OntologyClassDef(
            uri="http://planning.ontology/Operation",
            label="Operation",
            description="Decommissioning action or procedure (e.g., dismantling, demolition)",
            examples=[
                "Stilllegung",
                "Abbau",
                "Entsorgung",
            ],
        ),
        OntologyClassDef(
            uri="http://planning.ontology/Requirement",
            label="Requirement",
            description="Safety, environmental, or regulatory requirement",
            examples=[
                "Sicherheitsanforderung",
                "Umweltschutzanforderung",
                "Genehmigungsanforderung",
            ],
        ),
        OntologyClassDef(
            uri="http://planning.ontology/Document",
            label="Document",
            description="Regulatory, technical, or safety document",
            examples=[
                "Sicherheitsbericht",
                "Genehmigungsantrag",
                "UVP",
            ],
        ),
    ]


def test_extraction(
    text: str, filename: str, extractor: LLMEntityExtractor
) -> None:
    """Test entity extraction on a text chunk.

    Args:
        text: Text to extract from
        filename: Source filename (for logging)
        extractor: Entity extractor instance
    """
    print(f"\n{'='*70}")
    print(f"📋 File: {filename}")
    print(f"{'='*70}")
    print(f"Text preview ({len(text)} chars):")
    print(text[:300] + "..." if len(text) > 300 else text)
    print("\n⏳ Extracting entities...")

    try:
        ontology = create_ontology_classes()
        entities = extractor.extract(text, ontology)

        print(f"\n✓ Extracted {len(entities)} entities:")
        for entity in entities:
            print(f"\n  [{entity.entity_type}] {entity.label}")
            print(f"    ID: {entity.id}")
            print(f"    Confidence: {entity.confidence:.2f}")
            if entity.evidence:
                print(f"    Source: {entity.evidence[0].source_text[:50]}...")

    except Exception as e:
        print(f"\n✗ Extraction failed: {e}")
        import traceback

        traceback.print_exc()


def main() -> None:
    """Main test entry point."""
    print("=" * 70)
    print("🧪 Entity Extraction Test")
    print("=" * 70)

    # Step 1: Verify Ollama connection
    print("\n1️⃣ Connecting to Ollama...")
    try:
        llm = OllamaProvider(model="qwen3", temperature=0.5)
        print(f"✓ Connected to {llm.model_name}")
    except ConnectionError as e:
        print(f"✗ Cannot connect to Ollama: {e}")
        print(
            "\n💡 Make sure Ollama is running:\n"
            "   ollama serve\n"
            "   (in another terminal)\n\n"
            "   Then pull the QWEN model:\n"
            "   ollama pull qwen3"
        )
        return

    # Step 2: Load sample documents
    print("\n2️⃣ Loading sample documents...")
    documents = load_sample_documents(max_docs=3)
    if not documents:
        print("❌ Failed to load documents")
        return

    # Step 3: Initialize extractor
    print("\n3️⃣ Initializing entity extractor...")
    extractor = LLMEntityExtractor(llm, confidence_threshold=0.6)
    print("✓ Extractor ready")

    # Step 4: Test extraction on first chunk from each document
    print("\n4️⃣ Running extractions...")
    chunker = FixedSizeChunker()

    for filename, content in documents:
        # Take first 1000 chars for quick test
        test_chunk = content[:1000]
        test_extraction(test_chunk, filename, extractor)

    print(f"\n{'='*70}")
    print("✅ Test complete!")
    print(f"{'='*70}")
    print(
        "\n💡 Next steps:\n"
        "   1. Check extraction quality on decommissioning domain\n"
        "   2. Adjust confidence threshold if needed\n"
        "   3. Expand to full documents\n"
        "   4. Implement RelationExtractor\n"
        "   5. Store results in Neo4j & Qdrant"
    )


if __name__ == "__main__":
    main()
