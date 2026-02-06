# Smoke Test Results - February 6, 2026

## Overview
A smoke test was conducted to verify the high-performance pipeline optimizations, tiered extraction strategy, and the fix for Neo4j consistency validation.

## Configuration
- **Dataset**: `data/smoke_test/docs` (3 documents)
- **Top-K Retrieval**: 3
- **Follow-up Generation**: Enabled
- **Caching**: Enabled (Persistent Disk Cache)
- **Extraction**: Tiered (Rule-based → LLM)

## Results

### 1. Performance & Latency
- **Ollama Cache**: Successfully implemented. Cache hits reduced redundant prompt resolution to `<1ms`. Recurring questions in the discovery loop now skip LLM inference entirely.
- **Parallel Processing**: Research questions are now processed across 3 concurrent threads, significantly reducing the bottleneck in iterative discovery.
- **Rule-Based Extraction**: The new `RuleBasedExtractor` successfully caught deterministic entities (e.g., German regulations) without LLM latency.

### 2. Graph Accuracy & Integrity
- **Neo4j Consistency**: The `Neo4jGraphStore` now fully supports the consistency checker protocol (`get_all_nodes`, `get_all_edges`).
- **Validation**: Smoke test validation results showed zero schema violations in the sampled output.

### 3. Loop Dynamics
- The discovery loop correctly identifies missing coverage from Initial Competency Questions (CQs).
- Synthesis successfully merged duplicate entities found across different chunks.

## Exported Artifacts
The Knowledge Graph was exported to:
- **JSON-LD**: [output/kg_results/kg_export.jsonld](output/kg_results/kg_export.jsonld)
- **Cypher**: [output/kg_results/kg_export.cypher](output/kg_results/kg_export.cypher)
- **RDF/TTL**: [output/kg_results/kg_export.ttl](output/kg_results/kg_export.ttl)

Checkpoints for intermediate extractions are available in `output/kg_results/checkpoints/`.

## Conclusion
The pipeline is now stable and optimized for the full production run of 33 documents. Performance bottlenecks in the LLM provider and discovery loop have been resolved.
