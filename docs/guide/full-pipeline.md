# Full Pipeline

## Overview

`scripts/full_kg_pipeline.py` is the main entry point for end-to-end KG
construction. It orchestrates all three layers: extraction, enrichment,
and persistence.

## Usage

```bash
export PYTHONPATH=$PWD/src:$PYTHONPATH

# Standard run (3 discovery iterations)
python scripts/full_kg_pipeline.py --max-iterations 3

# Quick test (1 iteration)
python scripts/full_kg_pipeline.py --max-iterations 1

# Dry run (no database writes)
python scripts/full_kg_pipeline.py --max-iterations 1 --dry-run

# Re-enrich from checkpoint (94% time savings)
python scripts/full_kg_pipeline.py --enrich-only --checkpoint output/checkpoint.json

# Skip enrichment
python scripts/full_kg_pipeline.py --skip-enrichment

# Skip analytics
python scripts/full_kg_pipeline.py --skip-analytics

# With law graph context augmentation
LAW_GRAPH_ENABLED=true python scripts/full_kg_pipeline.py
```

## Pipeline Phases

1. **Ontology loading** -- reads OWL classes and relations from Fuseki
2. **Question generation** -- generates research questions per ontology class
3. **Iterative discovery** -- retrieve chunks, extract entities/relations,
   measure coverage, generate follow-up questions
4. **Confidence tuning** -- six-stage refinement pipeline
5. **Checkpointing** -- save extraction results to JSON
6. **Enrichment** -- five-phase semantic enrichment
7. **Assembly** -- write to Neo4j, Qdrant, Fuseki
8. **Validation** -- SHACL shapes, pySHACL, consistency checks
9. **Analytics** -- OWL-RL inference, SKOS, graph metrics
10. **Export** -- JSON-LD, Turtle, Cypher, GraphML

## Output

Results are written to `output/`:

- `checkpoint.json` -- extraction results (entities + relations + metadata)
- `exports/` -- multi-format KG exports
- `validation_reports/` -- SHACL quality reports
- `experiment_output/` -- experiment-specific artifacts
