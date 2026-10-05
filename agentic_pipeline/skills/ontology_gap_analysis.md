---
name: ontology_gap_analysis
tool: ontology_query
requires_binding: [agent]
default_kwargs:
  max_questions: 50
  covered_threshold: 1
---

Identify ontology classes that are under-covered by extracted entities and
generate priority-ranked research questions for them.

Prioritization considers class hierarchy depth (parent classes first),
whether the class participates in relations, and how many instances have
already been found. Run this at the start of a discovery iteration, or
whenever coverage should be re-assessed after new entities are found.
