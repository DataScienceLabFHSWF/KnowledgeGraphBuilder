---
name: semantic_enrichment
tool: semantic_enrichment
requires_binding: [pipeline]
default_kwargs: {}
---

Run the 5-phase semantic enrichment pipeline over extracted entities and
relations: descriptions, embeddings, competency questions, ontology type
constraints, and aliases.

Run this after assembly, once entities/relations exist in a form ready to
be enriched. The `pipeline` binding is a `SemanticEnrichmentPipeline`
instance configured with an LLM and embedding provider.
