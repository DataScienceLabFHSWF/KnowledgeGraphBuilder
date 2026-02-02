#!/usr/bin/env python3
"""Quick test of the advanced document processor."""

import sys
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kgbuilder.core.config import ProcessingConfig
from kgbuilder.document.advanced_processor import AdvancedDocumentProcessor


def main() -> None:
    """Test advanced processor on a sample PDF."""
    print("\n" + "=" * 70)
    print("Testing Advanced Document Processor")
    print("=" * 70 + "\n")

    # Find first PDF
    data_dir = Path(__file__).parent.parent / "data"
    pdfs = list(data_dir.rglob("*.pdf"))  # Recursive search

    if not pdfs:
        print("❌ No PDFs found in data/ directory")
        return

    pdf_file = pdfs[0]
    print(f"📄 Testing with: {pdf_file.name}")
    print(f"📦 File size: {pdf_file.stat().st_size / 1024:.1f} KB\n")

    # Configure processor (disable cache for fresh test)
    config = ProcessingConfig(
        enable_vlm=False,
        enable_caching=False,  # Disable for clean test
        language_detection=True,
    )

    processor = AdvancedDocumentProcessor(config)

    # Process document
    print("Processing document...")
    try:
        result = processor.process_document(pdf_file)

        print(f"\n✅ Processing Complete!\n")
        print(f"📊 Results:")
        print(f"   • Chunks: {len(result.chunks)}")
        print(f"   • Metadata entries: {len(result.metadatas)}")
        print(f"   • Tables: {len(result.tables) if result.tables else 0}")
        print(f"   • Pages: {result.stats.total_pages}")

        if result.stats.languages_detected:
            print(f"   • Languages: {', '.join(result.stats.languages_detected)}")

        if result.chunks:
            print(f"\n📝 First chunk preview:")
            print(f"   {result.chunks[0][:100]}...")

        if result.metadatas:
            print(f"\n📌 First metadata:")
            for key, value in list(result.metadatas[0].items())[:5]:
                print(f"   {key}: {value}")

        # Test caching
        print(f"\n🔄 Testing cache...")
        result2 = processor.process_document(pdf_file)
        if result2.chunks == result.chunks:
            print(f"   ✅ Cache working! Returned cached result")
        else:
            print(f"   ⚠️  Cache inconsistency")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
