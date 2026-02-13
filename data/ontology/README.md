# Ontologies

Ontology files used by the KGBuilder pipeline for guided entity/relation extraction.

## Directory Structure

```
ontology/
├── domain/              # Domain-specific ontologies (our own)
│   └── plan-ontology-v1.0.owl   # AI Planning / decommissioning ontology
├── legal/               # Third-party legal ontologies (reference)
│   ├── lkif-core/       # LKIF-Core v1.1 — Legal Knowledge Interchange Format
│   │   ├── lkif-core.owl        # Top-level import (imports all modules)
│   │   ├── lkif-top.owl         # Top-level concepts
│   │   ├── norm.owl             # Norms, rights, obligations, permissions
│   │   ├── legal-action.owl     # Legal acts, public bodies, decisions
│   │   ├── legal-role.owl       # Legal roles (professional, social)
│   │   ├── expression.owl       # Propositional content & expressions
│   │   ├── action.owl           # Actions & agents (generic)
│   │   ├── role.owl             # Roles (generic)
│   │   ├── process.owl          # Processes & state transitions
│   │   ├── mereology.owl        # Part-whole relations
│   │   └── time.owl             # Temporal concepts
│   └── eli/             # ELI — European Legislation Identifier
│       ├── eli.owl              # Core ELI metadata ontology
│       └── eli-sdo.ttl          # ELI ↔ Schema.org alignment
└── law/                 # Our custom legal ontology (to be created)
    └── law-ontology-v1.0.owl    # German law KG ontology (planned)
```

## How Ontologies Are Used

1. **Domain ontology** → loaded into Fuseki → drives extraction prompts
2. **LKIF-Core / ELI** → reference vocabularies we align our custom ontology to
3. **Custom law ontology** → built from LKIF-Core + ELI + German law specifics
