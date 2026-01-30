
# KnowledgeGraphBuilder

Ontology-driven Knowledge Graph Construction Pipeline

---

## What is this?

**KnowledgeGraphBuilder** is a modular, ontology-guided pipeline for building, validating, and versioning knowledge graphs from unstructured documents (PDF, DOCX, PPTX, etc.).

- **Ingests documents** (PDF, DOCX, PPTX, TXT, Markdown)
- **Extracts entities and relations** using an ontology
- **Builds and validates** a Knowledge Graph (KG)
- **Exports** KG in multiple formats (JSON-LD, YARRRML, RDF)
- **Tracks experiments and KG versions** for research and reproducibility

---

## Research Questions

This project is designed to answer key research questions in ontology-driven KG construction:

- **How does ontology guidance impact the quality and coverage of KGs built from unstructured documents?**
- **How do different ontology/CQ versions affect KG structure, validation, and downstream QA/RAG performance?**
- **What are the trade-offs between classic vector-based, hybrid, and KG-only RAG architectures?**
- **How can we systematically track, compare, and reproduce KG building experiments for academic evaluation?**

## Research Contributions

- A modular, protocol-based Python framework for KG construction and validation
- Full experiment tracking, versioning, and metrics for reproducible research
- Support for ontology/CQ evolution and ablation studies
- Extensible architecture for integrating new document types, chunking, extraction, and storage backends
- Export and validation in multiple KG formats (JSON-LD, YARRRML, RDF)

---

## Quick Start
1. Copy [.env.example](.env.example) to `.env` and fill in secrets
2. Run `docker-compose up` (Ollama must run externally)
3. See [src/](src/) for main code, [Planning/](Planning/) for all specs and design docs

---

## Documentation
- [Planning/ARCHITECTURE.md](Planning/ARCHITECTURE.md) – System architecture, diagrams
- [Planning/INTERFACES.md](Planning/INTERFACES.md) – All protocol/interface definitions
- [Planning/ISSUES_BACKLOG.md](Planning/ISSUES_BACKLOG.md) – Feature backlog and roadmap
- [Planning/KG_VERSIONING.md](Planning/KG_VERSIONING.md) – KG versioning design
- [.github/copilot-instructions.md](.github/copilot-instructions.md) – Code style and repo guidelines

---

## Repo Organization
- [src/](src/) – Implementation code
- [Planning/](Planning/) – All documentation/specs (not in root)
- [tests/](tests/) – Tests
- [scripts/](scripts/) – Utilities
- Root: only essentials ([README.md](README.md), [docker-compose.yml](docker-compose.yml), [.env.example](.env.example), etc.)

---

## License
MIT
