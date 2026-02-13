
import pytest
from unittest.mock import MagicMock
from kgbuilder.extraction.legal_llm import LegalLLMExtractor, LegalEntityExtractionOutput, LegalEntityItem, LegalExtractionConfig
from kgbuilder.core.models import ExtractedEntity

class MockLLM:
    def generate_structured(self, prompt, schema, **kwargs):
        return LegalEntityExtractionOutput(
            entities=[
                LegalEntityItem(
                    label="Test Entity",
                    entity_type="TestClass",
                    description="A test entity",
                    confidence=0.9,
                    evidence_span="found in text"
                )
            ]
        )
    @property
    def model_name(self): return "mock-model"

class MockOntology:
    def get_class_definitions(self): return [{"label": "TestClass"}]
    def get_relation_definitions(self): return []

def test_aligner_integration():
    llm = MockLLM()
    ontology = MockOntology()
    config = LegalExtractionConfig(confidence_threshold=0.1)
    extractor = LegalLLMExtractor(llm, ontology, config)
    
    # Text contains the evidence
    text = "This is some content where the entity Test Entity is found in text explicitly."
    
    entities = extractor.extract_entities(text, paragraph_id="p1")
    
    assert len(entities) == 1
    ent = entities[0]
    print(f"Entity: {ent.label}, Conf: {ent.confidence}")
    print(f"Evidence props: {ent.properties}")
    
    # Check alignment metadata
    assert ent.properties["alignment"] == "exact"
    assert ent.properties["matched_span"] == "found in text"
    
    # Test mismatch logic
    # Text DOES NOT contain the evidence
    text_mismatch = "This text has nothing to do with it."
    entities_mismatch = extractor.extract_entities(text_mismatch, paragraph_id="p1")
    
    ent_mismatch = entities_mismatch[0]
    print(f"Entity Mismatch: {ent_mismatch.label}, Conf: {ent_mismatch.confidence}")
    assert ent_mismatch.properties["alignment"] == "missing"
    # Should be penalized (0.9 * 0.5 = 0.45)
    assert ent_mismatch.confidence < 0.9

if __name__ == "__main__":
    test_aligner_integration()
