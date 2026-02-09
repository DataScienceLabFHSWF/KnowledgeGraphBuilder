# ontology-hitl — Iteration Workflow

End-to-end workflow for one ontology extension iteration cycle.

---

## Prerequisites

- KnowledgeGraphBuilder has been run at least once (extraction checkpoint exists)
- Fuseki running with seed ontology loaded
- Ollama running with qwen3:8b model

---

## Full Iteration Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    ITERATION WORKFLOW                            │
└─────────────────────────────────────────────────────────────────┘

  KnowledgeGraphBuilder (existing repo)
  ========================================
  Step 1: Run KGB pipeline
    $ python scripts/full_kg_pipeline.py --max-iterations 1
    → output/extraction_checkpoint.json
    → output/kg_metrics.json

              │
              │ checkpoint + metrics
              ▼

  ontology-hitl (this repo)
  ========================================
  Step 2: Gap Analysis
    $ python scripts/run_gap_analysis.py \
        --checkpoint ../KGB/output/extraction_checkpoint.json
    → data/iterations/v1/gap_report.json
    Result: "450 entities extracted, 180 covered (40%), 270 uncovered"

  Step 3: Generate Proposals
    $ python scripts/generate_proposals.py \
        --gap-report data/iterations/v1/gap_report.json
    → data/iterations/v1/proposals.json
    Result: "25 proposed new classes with definitions"

  Step 4: Expert Review (interactive)
    $ python scripts/review_proposals.py \
        --proposals data/iterations/v1/proposals.json
    → data/iterations/v1/decisions.json
    Result: "18 accepted, 5 rejected, 2 needs revision"

  Step 5: Export Extended Ontology
    $ python scripts/export_ontology.py \
        --decisions data/iterations/v1/decisions.json \
        --proposals data/iterations/v1/proposals.json
    → data/exports/ontology_v2.0.owl
    → data/exports/cq_v2.0.json

              │
              │ ontology + CQs
              ▼

  KnowledgeGraphBuilder (existing repo)
  ========================================
  Step 6: Re-run KGB with extended ontology
    $ python scripts/full_kg_pipeline.py \
        --ontology-path ../ontology-hitl/data/exports/ontology_v2.0.owl \
        --questions ../ontology-hitl/data/exports/cq_v2.0.json \
        --max-iterations 1
    → output/kg_metrics.json (updated)

              │
              │ new metrics
              ▼

  ontology-hitl (this repo)
  ========================================
  Step 7: Evaluate Improvement
    $ python scripts/evaluate_iteration.py \
        --before data/iterations/v1/metrics_before.json \
        --after ../KGB/output/kg_metrics.json
    → data/iterations/v1/evaluation_report.json
    Result: "CQ coverage: 40% → 72%, Entity coverage: 40% → 68%"

  Step 8: Decide → Iterate or Ship
    If targets not met → Start iteration v2 from Step 2
    If targets met → Tag ontology as production release
```

---

## Data Flow Diagram

```
                    ┌──────────────────┐
                    │  KnowledgeGraph  │
                    │    Builder       │
                    │                  │
                    │ extraction_      │
                    │ checkpoint.json  │──────┐
                    │ kg_metrics.json  │──────┤
                    └────────▲─────────┘      │
                             │                │
                    ontology + CQs       checkpoint + metrics
                             │                │
                    ┌────────┴─────────┐      │
                    │  ontology-hitl   │◄─────┘
                    │                  │
                    │ gap_report.json  │
                    │ proposals.json   │
                    │ decisions.json   │
                    │ ontology_vN.owl  │
                    │ cq_vN.json       │
                    └──────────────────┘
```

---

## Iteration Schedule (Recommended)

| Iteration | Focus | Expected Classes | Target Coverage |
|-----------|-------|-----------------|-----------------|
| v1 | Core domain concepts (Facility, Permit, Regulation) | 8-12 | 55-65% |
| v2 | Process concepts (DecommStrategy, Phase, Activity) | 6-10 | 70-80% |
| v3 | Fine-grained (Hazard types, Material types) | 5-8 | 80-85% |
| v4 | Edge cases + refinement | 3-5 | 85%+ |

---

## Checkpoint Format (KGB → ontology-hitl)

The extraction checkpoint JSON produced by KGB should contain:

```json
{
  "pipeline_run_id": "baseline_33docs_20260209_0929",
  "timestamp": "2026-02-09T09:29:28",
  "ontology_version": "plan-ontology-v1.0",
  "entities": [
    {
      "id": "ent_a1b2c3d4e5f6",
      "label": "Kernkraftwerk Greifswald",
      "entity_type": "Facility",
      "confidence": 0.87,
      "evidence": [
        {
          "chunk_id": "chunk_042",
          "document": "doc_15.pdf",
          "text_snippet": "Das Kernkraftwerk Greifswald..."
        }
      ]
    }
  ],
  "relations": [...],
  "metrics": {
    "total_entities": 450,
    "unique_entity_types": 35,
    "avg_confidence": 0.72
  }
}
```

---

## Exported Ontology Format (ontology-hitl → KGB)

Standard OWL file with new classes added as subclasses of seed:

```xml
<!-- Extended from plan-ontology-v1.0 -->
<owl:Class rdf:about="&ex;Facility">
    <rdfs:subClassOf rdf:resource="&planning;DomainConstant"/>
    <rdfs:label xml:lang="en">Facility</rdfs:label>
    <rdfs:comment>A nuclear facility subject to decommissioning.</rdfs:comment>
</owl:Class>

<owl:ObjectProperty rdf:about="&ex;requiresPermit">
    <rdfs:domain rdf:resource="&ex;Facility"/>
    <rdfs:range rdf:resource="&ex;Permit"/>
    <rdfs:label>requires permit</rdfs:label>
</owl:ObjectProperty>
```

---

## Updated CQ Format (ontology-hitl → KGB)

```json
[
  {
    "id": "CQ_001",
    "question": "Was ist der Unterschied zwischen Freigabe und Freisetzung?",
    "expected_entity_types": ["Action", "Regulation"],
    "expected_relations": ["regulatedBy", "appliesTo"],
    "difficulty": 3,
    "priority": 1,
    "added_in_iteration": "v0"
  },
  {
    "id": "CQ_010",
    "question": "Welche Genehmigungen sind für den Rückbau einer Anlage erforderlich?",
    "expected_entity_types": ["Facility", "Permit", "DecommissioningStrategy"],
    "expected_relations": ["requiresPermit", "hasStrategy"],
    "difficulty": 4,
    "priority": 1,
    "added_in_iteration": "v1"
  }
]
```
