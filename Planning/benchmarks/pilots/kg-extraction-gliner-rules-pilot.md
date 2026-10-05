# KG extraction benchmark: qwen3:32b

- **Run:** 2026-10-05T09:11:47.798117+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats not recorded)
- **Configured backend/model:** ollama / qwen3:32b
- **Extractors:** entities `gliner`, relations `rules`
- **Generative LLM stage:** not invoked by this path
- **Decision evidence judge:** disabled
- **Model revision:** urchade/gliner_multi-v2.1@443d26d654e0324125a96bebd8e796c14ff2efe6
- **Dataset SHA-256:** `786f9d7bcbbfe8ab6ba23ae57d38e0ff37d45e3caedd11f320429d014998fde4`

## Quality

| Metric | Precision | Recall | F1 | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Entity | 0.383 | 0.348 | 0.365 | [0.193, 0.506] |
| Triple | 0.000 | 0.000 | 0.000 | [0.000, 0.000] |
| Attribute | 0.000 | 0.000 | 0.000 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 3.46 s |
| P95 latency/item | 3.56 s |
| Mean latency/item | 3.44 s |
| Prompt tokens | not reported |
| Completion tokens | not reported |
| Total tokens | not reported |
| Token source | unavailable (0 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 61 / 66 |
| Predicted triples / gold | 0 / 36 |
| Ontology class coverage | 81.8% |
| Ontology relation coverage | 0.0% |
| Domain/range-valid relations | 100.0% |
| Predicted / gold attributes | 0 / 6 |

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.
Evidence/ontology validity ratios are vacuous when no relations are predicted; they do not establish extraction quality.

Aggregate-only measurements: [kg-extraction-gliner-rules-pilot.json](kg-extraction-gliner-rules-pilot.json). Source passages, predictions, and error messages are retained locally, not published.
