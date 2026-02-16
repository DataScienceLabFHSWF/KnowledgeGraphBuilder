# Architecture Overview

## Core Idea

The system constructs a Knowledge Graph through **iterative, ontology-guided
discovery**. Rather than making a single extraction pass, the pipeline
generates research questions from the ontology, retrieves relevant document
chunks, extracts entities and relations, measures coverage, and generates
follow-up questions -- repeating until the KG sufficiently covers the
ontology.

## Three-Layer Processing Model

```
 LAYER 1: EXTRACTION  (~6.8 h for 33 docs)
 ──────────────────────────────────────────────────────
   OWL Ontology
     -> Question Generation (competency-question driven)
     -> Iterative Discovery Loop
          Retrieve chunks (Qdrant)  ->  Tiered Extraction
          (Rule-based heuristics -> LLM fallback)
          ->  Ensemble merge  ->  Synthesize & deduplicate
     -> Confidence Tuning
   Output: checkpoint.json

 LAYER 2: ENRICHMENT  (~15 min)
 ──────────────────────────────────────────────────────
   Load checkpoint
     -> LLM descriptions -> Embeddings -> CQs
     -> Type constraints -> Aliases
   Output: enriched entities + relations

 LAYER 3: PERSISTENCE  (~5 min)
 ──────────────────────────────────────────────────────
   Write Neo4j -> Write Qdrant -> Write RDF/Fuseki
     -> Exports -> SHACL validation -> Analytics
   Output: populated stores + exports + quality report
```

## Iterative Discovery Loop

The `IterativeDiscoveryLoop` orchestrates a cycle of question-driven
extraction that progressively builds the KG:

1. **Question Generation** -- examine under-covered ontology classes,
   generate targeted research questions
2. **Retrieve** -- query Qdrant for top-K relevant document chunks
3. **Extract Entities** -- ontology-guided LLM extraction with
   structured output validation and retry logic
4. **Extract Relations** -- relation extraction with domain/range
   constraint validation
5. **Update Findings** -- merge, deduplicate, track provenance
6. **Measure Coverage** -- `|discovered types intersection ontology classes| / |ontology classes|`
7. **Generate Follow-Up Questions** -- target under-represented classes

**Stopping conditions**: coverage target reached, max iterations reached,
or no new questions generated.

## Key Design Decisions

- **Protocol-based architecture** -- all major interfaces defined as
  `typing.Protocol` for dependency injection and testability
- **Tiered extraction** -- deterministic rules first (fast, high precision),
  LLM fallback for semantic extraction
- **Source grounding** -- `TextAligner` (inspired by LangExtract) verifies
  extracted spans against source text
- **Checkpoint-based workflow** -- expensive extraction is checkpointed,
  enrichment and persistence can be re-run cheaply
- **Ontology-agnostic** -- swap ontology + documents for a new domain
  without code changes

For full details, see
[Planning/02_ARCHITECTURE.md](https://github.com/DataScienceLabFHSWF/KnowledgeGraphBuilder/blob/main/Planning/02_ARCHITECTURE.md).
