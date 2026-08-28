---
name: join_module_results
tool: null
requires_binding: []
default_kwargs: {}
---

Merge entity lists produced by independent ontology-module subagents into
one deduplicated result.

Run this after all module subagents have finished, as the final step of the
orchestrator. Entities are deduped by `(label, entity_type)`; when the same
concept is found by more than one module, the highest-confidence version is
kept and evidence from all sources is merged.
