---
name: module_extraction
tool: entity_extraction
requires_binding: [retriever, extractor]
default_kwargs:
  top_k: 10
---

Retrieve documents relevant to a research question, then extract entities
scoped to a single ontology module's class definitions.

This is the core skill of a `ModuleExtractionAgent`: one subagent per
ontology module (e.g. "Radiological Characterization", "Waste and
Materials") runs this skill over the SCQ/RCQ research questions assigned to
that module. Different modules may bind different retriever/extractor
pairs — e.g. a smaller, cheaper model for a simpler module.
