# KG extraction benchmark: gemma4:e2b

- **Run:** 2026-10-05T09:37:14.060488+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats not recorded)
- **Configured backend/model:** ollama / gemma4:e2b
- **Extractors:** entities `gliner`, relations `decision`
- **Generative LLM stage:** not invoked by this path
- **Decision evidence judge:** disabled
- **Model revision:** ollama-0.35.0
- **Dataset SHA-256:** `786f9d7bcbbfe8ab6ba23ae57d38e0ff37d45e3caedd11f320429d014998fde4`

## Quality

| Metric | Precision | Recall | F1 | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Entity | 0.383 | 0.348 | 0.365 | [0.193, 0.506] |
| Triple | 0.028 | 0.028 | 0.028 | [0.000, 0.102] |
| Attribute | 0.000 | 0.000 | 0.000 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 4.03 s |
| P95 latency/item | 4.24 s |
| Mean latency/item | 4.06 s |
| Prompt tokens | 26,296 |
| Completion tokens | 44 |
| Total tokens | 26,340 |
| Token source | server (11 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 61 / 66 |
| Predicted triples / gold | 36 / 36 |
| Ontology class coverage | 81.8% |
| Ontology relation coverage | 23.8% |
| Domain/range-valid relations | 100.0% |
| Predicted / gold attributes | 0 / 6 |

- **Decision model:** tev1:0.8b

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.
Evidence/ontology validity ratios are vacuous when no relations are predicted; they do not establish extraction quality.

Aggregate-only measurements: [kg-extraction-gliner-tev1-pilot.json](kg-extraction-gliner-tev1-pilot.json). Source passages, predictions, and error messages are retained locally, not published.
