---
name: relation_extraction_batch
tool: relation_extraction
requires_binding: [retriever, relation_extractor, ontology_relations]
default_kwargs:
  top_k: 10
---

For each competency question, retrieve supporting document passages and
extract relations only between entities grounded in that passage. Apply the
ontology relation definitions and deduplicate repeated relation evidence.
