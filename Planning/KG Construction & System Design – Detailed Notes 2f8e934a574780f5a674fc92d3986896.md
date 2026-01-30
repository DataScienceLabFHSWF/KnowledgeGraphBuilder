# KG Construction & System Design – Detailed Notes

## A. Evidence Acquisition Layer

### Evidence Sources

1. **Local Indexed Documents**
    - Vector index
    - Primary trusted source
2. **Web Search (Optional)**
    - Used only when:
        - Competency questions fail
        - Ontology coverage is insufficient
        - Validation detects gaps
    - Every query is logged

---

## B. DeepResearch Agent

### Role

Ontology-guided researcher that gathers and synthesizes evidence.

### Inputs

- Ontology
- Competency questions
- Current KG snapshot
- Vector index
- Optional web search

### Outputs: Research Findings (NOT triples)

```yaml
finding_id:FR-0231
ontology_concepts:
-RootCause
question:
"What are common root causes in 8D problem solving?"
claims:
-text:"Root causes are often categorized as people, process, or system failures."
confidence:0.82
evidence:
-source_type:local_doc
chunk_id:DOC-112-CH-7
-source_type:web
url:example.com
timestamp:2026-01-30

```

---

## C. Layered Research Strategy

### Layer 1 – Ontology Core

- One question per ontology class
- Identify core entities
- High-level relations

### Layer 2 – Entity Expansion

- Attributes
- Sub-relations
- Dependencies

### Layer N – Refinement

- Triggered by:
    - Missing relations
    - SHACL violations
    - Low confidence
    - Unanswered CQs

### Stopping Criteria

- Fixed iterations
- Coverage thresholds
- Marginal gain vs cost
- Graph stability metrics

---

## D. KG Assembly

### Responsibilities

- Convert findings → nodes & edges
- Deduplicate & merge
- Enforce ontology constraints
- Attach provenance

### Node / Edge Metadata

- Description
- Evidence references
- Confidence
- Extraction method

---