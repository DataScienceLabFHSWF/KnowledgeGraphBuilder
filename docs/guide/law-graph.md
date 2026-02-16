# Law Graph

Build a Knowledge Graph from German federal law XML files.

## Overview

The law graph pipeline uses a **two-phase approach**:

- **Phase A (Structural)**: deterministic XML parsing, no LLM required
- **Phase B (Semantic)**: ontology-guided LLM extraction via ensemble

## Quick Start

```bash
# 1. Generate the legal ontology
python scripts/build_law_ontology.py

# 2. Dry run on a single law
python scripts/build_law_graph.py --laws AtG --dry-run --skip-embed

# 3. Real run (writes to Neo4j)
python scripts/build_law_graph.py --laws AtG --skip-embed

# 4. Full corpus with embeddings
python scripts/build_law_graph.py
```

## Legal Ontology

The ontology (`data/ontology/law/law-ontology-v1.0.owl`) defines:

- **14 classes**: Gesetzbuch, Paragraf, Absatz, Definition, Obligation,
  Permission, Prohibition, Behoerde, Betreiber, LegalActor, etc.
- **10 object properties**: teilVon, referenziert, definiert, verpflichtet,
  erlaubt, verbietet, zustaendig, betrifft, aendert, aufgehobenDurch
- **7 datatype properties**: abkuerzung, langtext, version, etc.
- **Alignments**: LKIF-Core (legal knowledge interchange) and ELI
  (European Legislation Identifier)

## Extraction Pipeline

### Rule-Based (`legal_rules.py`)

High-precision deterministic patterns:

- Paragraph references: `§ 7`, `§§ 7 bis 9`, `§ 7 Abs. 2 Satz 1`
- Authority names: Bundesamt, Behörde, etc.
- Known abbreviations: BfS, BASE, BMU (gazetteer)
- Legal definitions: "im Sinne dieses Gesetzes"
- Deontic modalities: obligations, permissions, prohibitions

### LLM-Based (`legal_llm.py`)

Ontology-guided extraction with German-language prompts, two-pass
extraction (entities first, then relations), and Pydantic schema
validation.

### Ensemble (`legal_ensemble.py`)

Merges rule-based and LLM results:

- Weighted confidence (rule=0.7, LLM=0.5)
- Overlap boost (+0.15 when both agree)
- Fuzzy entity matching (80% similarity threshold)
- Conflict resolution: prefer rule-based on type conflicts

## Data Sources

Law XML files from [gesetze-im-internet.de](https://www.gesetze-im-internet.de/)
are stored in `data/law_html/`. Each law directory contains a `BJNR*.xml` file.

For detailed setup, see [QUICKSTART_LAW_GRAPH.md](https://github.com/DataScienceLabFHSWF/KnowledgeGraphBuilder/blob/main/QUICKSTART_LAW_GRAPH.md).
