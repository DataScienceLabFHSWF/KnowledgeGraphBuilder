"""Offline smoke test for the agentic (skills/tools/subagents) KG pipeline.

Exercises the full new agent stack end-to-end with in-memory fakes for the
retriever/extractor/ontology/validator — no Neo4j/Qdrant/Fuseki/Ollama
required. This is a functional demonstration, not a unit test: run it
directly to see the module orchestration + VCQ validation flow in action.

Usage:
    python scripts/demo_agentic_pipeline.py
"""

from __future__ import annotations

from kgbuilder.agents.discovery_loop import IterativeDiscoveryLoop
from kgbuilder.agents.orchestrator_agent import OrchestratorAgent
from kgbuilder.agents.question_generator import CQType, QuestionGenerationAgent, ResearchQuestion
from kgbuilder.core.models import Evidence, ExtractedEntity


class FakeOntologyService:
    """Minimal in-memory ontology stand-in for the demo."""

    MODULE_MAP = {
        "Assets and Locations": ["Facility"],
        "Document Structure and Evidence": ["Document"],
    }

    def get_all_classes(self) -> list[str]:
        return ["Facility", "Document"]

    def get_class_hierarchy(self, class_name: str | None = None):
        return [] if class_name is None else {"parents": [], "children": [], "depth": 0}

    def get_class_relations(self, class_name: str) -> dict[str, list[str]]:
        return {}

    def get_class_description(self, class_name: str) -> str | None:
        return f"{class_name} (demo)"

    def get_module_class_map(self) -> dict[str, list[str]]:
        return self.MODULE_MAP


class FakeRetriever:
    """Retriever that returns one canned chunk per query."""

    def retrieve(self, query: str, top_k: int = 10):
        return [{"content": f"[demo chunk for: {query}]", "doc_id": "doc-1"}]


class FakeExtractor:
    """Extractor that fabricates one entity per call, scoped to the given classes."""

    def extract(self, text: str, ontology_classes=None, existing_entities=None):
        entity_type = (ontology_classes or ["Facility"])[0]
        return [
            ExtractedEntity(
                id=f"ent-{entity_type}",
                label=f"Demo {entity_type}",
                entity_type=entity_type,
                description="",
                confidence=0.9,
                evidence=[Evidence(source_type="local_doc", source_id="doc-1")],
            )
        ]


class FakeValidator:
    """Validator that always confirms KG content answers a VCQ question."""

    def validate_question(self, question: ResearchQuestion, evidence: list) -> dict:
        return {"question_id": question.question_id, "valid": True, "evidence_count": len(evidence)}


def main() -> None:
    ontology = FakeOntologyService()
    retriever = FakeRetriever()
    extractor = FakeExtractor()
    validator = FakeValidator()

    question_gen = QuestionGenerationAgent(ontology_service=ontology)
    orchestrator = OrchestratorAgent(max_workers=2)

    # Manually add a VCQ question alongside the generated SCQ/RCQ ones, to
    # exercise the validation-stage routing in the same run.
    questions = question_gen.generate_questions(max_questions=10)
    questions.append(
        ResearchQuestion(
            question_id="vcq-demo",
            text="Does the KG contain a Facility record?",
            entity_class="Facility",
            priority=1.0,
            reason="demo validation question",
            cq_type=CQType.VCQ,
        )
    )
    print(f"Generated {len(questions)} research questions "
          f"({sum(1 for q in questions if q.cq_type != CQType.VCQ)} extraction, "
          f"{sum(1 for q in questions if q.cq_type == CQType.VCQ)} validation)")

    loop = IterativeDiscoveryLoop(
        retriever=retriever,
        extractor=extractor,
        question_generator=question_gen,
        module_map=ontology.get_module_class_map(),
        orchestrator=orchestrator,
        content_validator=validator,
    )

    result = loop.run_discovery(initial_questions=questions)

    print(f"\nDiscovery success: {result.success}")
    print(f"Entities discovered: {result.total_entities_discovered}")
    for entity in result.entities:
        print(f"  - {entity.label} ({entity.entity_type}), confidence={entity.confidence}")
    print(f"Validation results: {result.validation_results}")


if __name__ == "__main__":
    main()
