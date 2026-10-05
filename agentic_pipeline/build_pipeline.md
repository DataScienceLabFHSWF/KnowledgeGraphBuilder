---
steps:
  - id: questions
    skill: ontology_gap_analysis
    bind:
      agent: question_generation_agent
      class_filter: class_filter
    kwargs:
      max_questions: 50
  - id: entities
    skill: module_extraction_batch
    bind:
      module_map: module_map
      class_definitions: class_definitions
      question_generation_agent: question_generation_agent
      retriever: retriever
      extractor: entity_extractor
    inputs:
      questions: questions
    kwargs:
      top_k: 10
  - id: relations
    skill: relation_extraction_batch
    bind:
      retriever: retriever
      relation_extractor: relation_extractor
      ontology_relations: ontology_relations
    inputs:
      questions: questions
      entities: entities
    kwargs:
      top_k: 10
  - id: synthesis
    skill: findings_synthesis
    bind:
      synthesizer: synthesizer
    inputs:
      entities: entities
      relations: relations
  - id: assembly
    skill: kg_assembly
    bind:
      builder: graph_builder
    inputs:
      entities: synthesis.entities
      relations: synthesis.relations
  - id: validation
    skill: build_validation
    bind:
      store: graph_store
      enabled: run_validation
      job_id: job_id
---

# Ontology-driven KG build

Generate competency questions from the selected ontology classes, route them
through parallel module-scoped extraction subagents, extract ontology
relations from retrieved evidence, synthesize duplicate findings, assemble
the KG, and validate the persisted graph. Step order and data flow are
declared here; preprocessing and vector indexing happen before this plan.
