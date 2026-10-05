---
name: build_validation
tool: kg_validation
requires_binding: [store, enabled, job_id]
---

Run the knowledge-graph validation skill after assembly when validation is
enabled. Preserve per-check results and report failures rather than treating
an unavailable validator as a successful validation.
