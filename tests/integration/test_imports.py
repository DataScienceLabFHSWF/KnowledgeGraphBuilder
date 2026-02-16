#!/usr/bin/env python3
"""Quick import test."""
import sys

sys.path.insert(0, "src")

try:
    from kgbuilder.embedding import OllamaProvider
    from kgbuilder.extraction import LLMEntityExtractor
    from kgbuilder.extraction.schemas import EntityExtractionOutput
    print("✓ All imports successful")
    print(f"  - LLMEntityExtractor: {LLMEntityExtractor}")
    print(f"  - OllamaProvider: {OllamaProvider}")
    print(f"  - EntityExtractionOutput: {EntityExtractionOutput}")
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
