# Domain Pluggability

The pipeline is **ontology-agnostic**. Adding a new knowledge domain
requires no code changes to the core pipeline.

## How It Works

`FullKGPipeline` reads whatever OWL ontology is loaded in Fuseki and
auto-generates extraction prompts from it. SHACL shapes and validation
rules are also generated from the ontology. Different domains share the
same code -- only the ontology and document loaders change.

## Adding a New Domain

```
Step 1: Ontology
   Create or adopt an OWL ontology
   Load into a Fuseki dataset

Step 2: Documents
   Place source files in data/<domain>/
   Or implement a custom DocumentLoader

Step 3: Extractors (optional)
   Add domain-specific rule-based extractors:
     extraction/<domain>_rules.py
     extraction/<domain>_llm.py
     extraction/<domain>_ensemble.py

Step 4: Profile
   Create data/profiles/<domain>.json

Step 5: Run
   python scripts/full_kg_pipeline.py --profile data/profiles/<domain>.json
```

## Implemented Domains

### Nuclear Decommissioning

- **Ontology**: Custom plan-ontology loaded in Fuseki
- **Documents**: 33 PDFs (decommissioning project documents)
- **Extractors**: Generic LLM + rule-based
- **Results**: ~280 entities, ~156 relations, 92% ontology coverage

### German Federal Law

- **Ontology**: `law-ontology-v1.0.owl` aligned to LKIF-Core and ELI
- **Documents**: ~6,800 XML files from gesetze-im-internet.de
- **Extractors**: `legal_rules.py` (paragraph refs, authorities, deontic
  modalities) + `legal_llm.py` (German prompts) + `legal_ensemble.py`
- **Special**: Phase A structural import (XML to Neo4j without LLM)

## Domain Separation

- Each domain gets its own Fuseki dataset (ontology namespace)
- Each domain gets its own Qdrant collection (vector namespace)
- Neo4j uses `graph_type` property labels for filtering
- Config profiles in `data/profiles/` control all domain-specific settings
