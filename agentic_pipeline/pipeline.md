---
steps:
  - skill: ontology_gap_analysis
    bind: {agent: question_generation_agent}
    kwargs: {max_questions: 20}
  - skill: document_retrieval
    bind: {retriever: retriever}
    kwargs: {top_k: 10}
  - skill: law_context_lookup
    bind: {provider: law_context_provider}
  - skill: semantic_enrichment
    bind: {pipeline: enrichment_pipeline}
  - skill: law_linking
    bind: {linker: law_linker}
  - skill: retrieval_evaluation
---

# KG Build Pipeline

Ordered plan the `PipelineAgent` executes for one discovery iteration.
Edit the `steps` list to reorder, add, or remove stages — no code changes
required. Each `skill` must exist as a file in `skills/*.md` and be
registered in `kgbuilder.agents.registry.SKILL_REGISTRY`.

Each step's `bind` maps a keyword argument name to a resource the caller
supplies via `PipelineAgent(bindings={...})` (e.g. a retriever, a law
linker, an enrichment pipeline). `kwargs` are passed through as-is and
override the skill's markdown `default_kwargs`.

Document preprocessing and indexing (loading, chunking, embedding into
Qdrant) is intentionally not part of this file — it remains a hardcoded,
deterministic pipeline run before discovery begins.
