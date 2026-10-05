---
name: module_extraction_batch
tool: entity_extraction
requires_binding: [module_map, class_definitions, question_generation_agent, retriever, extractor]
default_kwargs:
  top_k: 10
---

Create one extraction subagent per ontology module, assign competency
questions to the module owning each target class, retrieve grounded evidence,
and join the parallel entity results.
