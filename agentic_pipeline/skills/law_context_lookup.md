---
name: law_context_lookup
tool: law_context_lookup
requires_binding: [provider]
default_kwargs: {}
---

Retrieve relevant German law paragraph context for a document chunk via
semantic search against the `lawgraph` Qdrant collection.

Use this before extraction on technical/decommissioning documents so the
extractor also sees the regulatory context that governs them. The
`provider` binding is a `LawContextProvider` instance.
