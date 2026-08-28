---
name: document_retrieval
tool: document_retrieval
requires_binding: [retriever]
default_kwargs:
  top_k: 10
---

Retrieve the top-k documents most relevant to a research question or query.

Use this before extraction so downstream tools have grounded source text to
work with. The `retriever` binding may point at a FusionRAG retriever, a
standard dense-vector retriever, or any object implementing
`retrieve(query, top_k) -> list[...]`.
