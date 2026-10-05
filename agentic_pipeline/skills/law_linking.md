---
name: law_linking
tool: law_linking
requires_binding: [linker]
default_kwargs: {}
---

Create cross-domain `LINKED_*` relationships between decommissioning KG
entities and law graph nodes, using explicit citation parsing, keyword
matching, and entity-type fallback.

Run this after assembly, once KG entities exist in Neo4j. The `linker`
binding is a `KGLawLinker` instance.
