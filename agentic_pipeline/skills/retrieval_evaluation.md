---
name: retrieval_evaluation
tool: retrieval_evaluation
requires_binding: []
default_kwargs: {}
---

Score a retrieval result set against a set of known-relevant document IDs,
producing recall@5/10, precision@5/10, NDCG@10, and MRR.

Use this in evaluation/benchmarking runs, or to sanity-check retrieval
quality before trusting extracted entities from those documents.
