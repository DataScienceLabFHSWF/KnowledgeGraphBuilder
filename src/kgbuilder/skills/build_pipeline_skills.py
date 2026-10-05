"""Composable skills for the ontology-driven KG build plan."""

from __future__ import annotations

from typing import Any, cast

from kgbuilder.skills.base import AgentSkill


def _module_extraction_handler(
    module_map: dict[str, list[Any]],
    class_definitions: dict[str, list[Any]],
    questions: list[Any],
    question_generation_agent: Any,
    retriever: Any,
    extractor: Any,
    top_k: int,
) -> list[Any]:
    """Dispatch research questions to parallel ontology-module subagents."""
    from kgbuilder.agents.orchestrator_agent import OrchestratorAgent

    orchestrator = OrchestratorAgent()
    bindings = orchestrator.build_module_bindings(
        module_map=module_map,
        questions=questions,
        retriever=retriever,
        extractor=extractor,
        top_k=top_k,
    )
    for binding in bindings:
        binding.ontology_classes = class_definitions.get(binding.module_name, [])
    entities = orchestrator.run_modules(bindings)
    question_generation_agent.add_existing_entities(entities)
    return entities


def _relation_extraction_handler(
    questions: list[Any],
    entities: list[Any],
    retriever: Any,
    relation_extractor: Any,
    ontology_relations: list[Any],
    top_k: int,
) -> list[Any]:
    """Extract ontology-constrained relations from retrieved evidence."""
    relations_by_id: dict[str, Any] = {}
    for question in questions:
        retrieved = retriever.retrieve(query=question.text, top_k=top_k)
        for result in retrieved:
            content = getattr(result, "content", None)
            if content is None and isinstance(result, dict):
                content = result.get("content")
            if not content:
                continue
            grounded_entities = [
                entity for entity in entities if entity.label.lower() in content.lower()
            ]
            if len(grounded_entities) < 2:
                continue
            for relation in relation_extractor.extract(
                text=content,
                entities=grounded_entities,
                ontology_relations=ontology_relations,
            ):
                relations_by_id[relation.id] = relation
    return list(relations_by_id.values())


def _synthesis_handler(
    entities: list[Any],
    relations: list[Any],
    synthesizer: Any,
) -> dict[str, list[Any]]:
    """Deduplicate discovered entities while preserving extracted relations."""
    return {
        "entities": synthesizer.synthesize(entities=entities),
        "relations": relations,
    }


def _assembly_handler(
    entities: list[Any],
    relations: list[Any],
    builder: Any,
) -> Any:
    """Convert synthesized findings to graph models and persist them."""
    from kgbuilder.storage.protocol import Edge, Node

    nodes = [
        Node(
            id=entity.id,
            label=entity.label,
            node_type=entity.entity_type,
            properties={
                **entity.attributes,
                "confidence": entity.confidence,
                "description": entity.description or "",
            },
            metadata={"sources": entity.sources, "merged_count": entity.merged_count},
        )
        for entity in entities
    ]
    entity_by_id = {entity.id: entity for entity in entities}
    edges = [
        Edge(
            id=relation.id,
            source_id=relation.source_entity_id,
            target_id=relation.target_entity_id,
            edge_type=relation.predicate.rsplit("#", maxsplit=1)[-1].rsplit("/", maxsplit=1)[-1],
            source_node_type=entity_by_id[relation.source_entity_id].entity_type,
            target_node_type=entity_by_id[relation.target_entity_id].entity_type,
            properties={
                **relation.properties,
                "confidence": relation.confidence,
                "evidence": [
                    evidence.text_span
                    for evidence in relation.evidence
                    if evidence.text_span
                ],
            },
        )
        for relation in relations
        if relation.source_entity_id in entity_by_id
        and relation.target_entity_id in entity_by_id
    ]
    result = builder.build(entities=nodes, relations=edges)
    if result.errors:
        raise RuntimeError(f"Knowledge graph assembly failed: {'; '.join(result.errors)}")
    return result


def _validation_handler(
    enabled: bool,
    store: Any,
    job_id: str,
) -> dict[str, Any]:
    """Run the reusable KG-validation skill when enabled for this build."""
    if not enabled:
        return {"skipped": True, "valid": True}

    from kgbuilder.skills.kg_validation_skill import KGValidationSkill
    from kgbuilder.validation.consistency_checker import ConsistencyChecker
    from kgbuilder.validation.rules_engine import RulesEngine

    return cast(
        dict[str, Any],
        KGValidationSkill.execute(
            store=store,
            rules_engine=RulesEngine(),
            consistency_checker=ConsistencyChecker(),
            run_id=job_id,
        ),
    )


ModuleExtractionBatchSkill = AgentSkill(
    name="module_extraction_batch",
    description=(
        "Route competency questions to ontology-module subagents, retrieve evidence, "
        "extract entities in parallel, and join their results."
    ),
    handler=_module_extraction_handler,
)

RelationExtractionBatchSkill = AgentSkill(
    name="relation_extraction_batch",
    description=(
        "Retrieve evidence for each competency question and extract ontology-constrained "
        "relations between grounded entities."
    ),
    handler=_relation_extraction_handler,
)

FindingsSynthesisSkill = AgentSkill(
    name="findings_synthesis",
    description="Deduplicate extracted entities and preserve their evidence and relations.",
    handler=_synthesis_handler,
)

KGAssemblySkill = AgentSkill(
    name="kg_assembly",
    description="Convert synthesized findings into ontology-typed graph nodes and edges and persist them.",
    handler=_assembly_handler,
)

BuildValidationSkill = AgentSkill(
    name="build_validation",
    description="Run the registered knowledge-graph validation skill after graph assembly.",
    handler=_validation_handler,
)
