# KnowledgeGraphBuilder

Ontology-driven Knowledge Graph construction pipeline for building validated,
traceable knowledge graphs from unstructured documents using local LLMs.

## Overview

KnowledgeGraphBuilder ingests documents (PDF, DOCX, PPTX, XML), extracts
entities and relations guided by an OWL ontology, assembles a validated
knowledge graph in Neo4j, and exports it in multiple standard formats.

The pipeline is **ontology-agnostic**: it reads whatever OWL ontology is
provided and auto-generates extraction prompts, SHACL shapes, and validation
rules from it.

## Key Features

- **Ontology-guided extraction** with tiered (rule-based + LLM) strategies
- **Iterative discovery loop** driven by competency questions
- **Confidence tuning** with multi-source boosting and coreference resolution
- **Five-phase enrichment** (descriptions, embeddings, CQs, type constraints, aliases)
- **SHACL validation** with automated quality scoring
- **OWL-RL inference** and SKOS enrichment
- **Multi-format export** (JSON-LD, RDF/Turtle, Cypher, GraphML)
- **Experiment framework** with W&B integration and checkpointing

## Research Ecosystem

| Repository | Purpose |
|-----------|---------|
| **KnowledgeGraphBuilder** (this repo) | KG construction, validation, and export |
| [GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent) | Ontology-informed GraphRAG QA agent |
| [OntologyExtender](https://github.com/DataScienceLabFHSWF/OntologyExtender) | Human-in-the-loop ontology extension |

## Quick Links

- [Quick Start](getting-started/quickstart.md)
- [Architecture Overview](architecture/overview.md)
- [API Reference](reference/)
