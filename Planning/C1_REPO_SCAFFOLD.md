# C1 Ontology-HITL — Repository Scaffold

**Purpose**: Blueprint for creating the `ontology-hitl` repository.  
**Relationship**: Separate repo from KnowledgeGraphBuilder. Outputs OWL + CQ JSON consumed by KGB.

---

## Directory Structure

```
ontology-hitl/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
│
├── src/ontology_hitl/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py               # ProposedClass, ReviewDecision, OntologyDiff, etc.
│   │   ├── protocols.py            # OntologyProvider, LLMProvider, ReviewBackend
│   │   ├── config.py               # Pydantic Settings
│   │   └── exceptions.py           # Error hierarchy
│   │
│   ├── discovery/                   # C1.2 — Concept Discovery
│   │   ├── __init__.py
│   │   ├── gap_analyzer.py          # C1.2.1 — OntologyGapAnalyzer
│   │   ├── class_generator.py       # C1.2.2 — ClassDefinitionGenerator (LLM)
│   │   └── relation_generator.py    # C1.2.3 — RelationProposalGenerator
│   │
│   ├── schema/                      # C1.3 — Ontology Management
│   │   ├── __init__.py
│   │   ├── manager.py               # C1.3.1 — OntologySchemaManager (add/remove)
│   │   ├── shacl_generator.py       # C1.3.2 — Generate SHACL shapes
│   │   └── version_manager.py       # C1.3.3 — Staging/main/snapshot graphs
│   │
│   ├── review/                      # C1.4 — Human-in-the-Loop
│   │   ├── __init__.py
│   │   ├── cli.py                   # CLI review tool (Typer + Rich)
│   │   ├── web.py                   # Optional Streamlit dashboard
│   │   └── feedback.py              # FeedbackCollector + persistence
│   │
│   └── evaluation/                  # C1.5 — Metrics & Evaluation
│       ├── __init__.py
│       ├── cq_evaluator.py          # CQ answerability measurement
│       ├── completeness.py          # Entity schema coverage
│       └── reporter.py              # Comparison reports (before/after)
│
├── scripts/
│   ├── run_gap_analysis.py          # Step 2: KGB checkpoint → gap report
│   ├── generate_proposals.py        # Step 3: gap report → proposed classes
│   ├── review_proposals.py          # Step 4: interactive expert review
│   ├── export_ontology.py           # Step 5: decisions → OWL + CQ JSON
│   └── evaluate_iteration.py        # Step 7: compare before/after metrics
│
├── data/
│   ├── seed_ontology/
│   │   └── plan-ontology-v1.0.owl   # Copy of base ontology
│   ├── iterations/
│   │   ├── v1/
│   │   │   ├── gap_report.json
│   │   │   ├── proposals.json
│   │   │   ├── decisions.json
│   │   │   ├── extended_ontology.owl
│   │   │   └── competency_questions.json
│   │   └── v2/
│   └── exports/                     # Final outputs consumed by KGB
│       ├── ontology_latest.owl
│       └── cq_latest.json
│
├── tests/
│   ├── conftest.py
│   ├── discovery/
│   │   ├── test_gap_analyzer.py
│   │   ├── test_class_generator.py
│   │   └── test_relation_generator.py
│   ├── schema/
│   │   ├── test_manager.py
│   │   ├── test_shacl_generator.py
│   │   └── test_version_manager.py
│   ├── review/
│   │   └── test_feedback.py
│   └── evaluation/
│       ├── test_cq_evaluator.py
│       └── test_completeness.py
│
└── docs/
    ├── WORKFLOW.md                   # How to run a full iteration cycle
    ├── EXPERT_GUIDE.md              # Guide for domain expert reviewers
    └── INTERFACE_CONTRACT.md         # I/O contract with KnowledgeGraphBuilder
```

---

## Interface Contract with KnowledgeGraphBuilder

### Inputs FROM KGB

| Artifact | Path | Description |
|----------|------|-------------|
| Extraction checkpoint | `output/extraction_checkpoint.json` | All extracted entities/relations from pipeline run |
| KG metrics | `output/kg_metrics.json` | Entity counts, coverage stats, confidence distributions |

### Outputs TO KGB

| Artifact | KGB CLI Flag | Description |
|----------|-------------|-------------|
| Extended ontology OWL | `--ontology-path` | New ontology with accepted classes |
| Extended ontology TTL | Upload to Fuseki | Alternative format |
| Updated CQ JSON | `--questions` | New/refined competency questions |

### KGB Already Supports This

```bash
# KGB accepts any ontology file + CQ JSON
python scripts/full_kg_pipeline.py \
  --ontology-path ../ontology-hitl/data/exports/ontology_v2.0.owl \
  --questions ../ontology-hitl/data/exports/cq_v2.0.json \
  --max-iterations 1
```

---

## Implementation Order

1. **Core models + config** (Day 1)
2. **Gap analyzer** (Day 2-3) — needs KGB checkpoint format
3. **Class generator** (Day 4-5) — LLM-based definitions
4. **Schema manager** (Day 6-7) — Fuseki SPARQL updates
5. **SHACL generator** (Day 8) — constraint generation
6. **CLI review tool** (Day 9-10) — expert-facing
7. **Export script** (Day 11) — OWL/TTL output
8. **CQ evaluator** (Day 12-13) — metrics
9. **End-to-end test** (Day 14) — full iteration cycle
