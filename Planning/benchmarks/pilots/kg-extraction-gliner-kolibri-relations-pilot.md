# KG extraction benchmark: Aleph-Alpha/Kolibri-1

- **Run:** 2026-10-05T09:32:07.276872+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats not recorded)
- **Configured backend/model:** vllm / Aleph-Alpha/Kolibri-1
- **Extractors:** entities `gliner`, relations `llm`
- **Generative LLM stage:** used
- **Decision evidence judge:** disabled
- **Model revision:** gliner:443d26d654e0324125a96bebd8e796c14ff2efe6; kolibri:hf-e52eb4627d11516b0c01de49210ab5a4e4061444
- **Dataset SHA-256:** `786f9d7bcbbfe8ab6ba23ae57d38e0ff37d45e3caedd11f320429d014998fde4`

## Quality

| Metric | Precision | Recall | F1 | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Entity | 0.383 | 0.348 | 0.365 | [0.193, 0.506] |
| Triple | 0.069 | 0.056 | 0.062 | [0.000, 0.149] |
| Attribute | 0.000 | 0.000 | 0.000 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 5.02 s |
| P95 latency/item | 5.83 s |
| Mean latency/item | 5.00 s |
| Prompt tokens | 25,373 |
| Completion tokens | 3,104 |
| Total tokens | 28,477 |
| Token source | server (22 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 61 / 66 |
| Predicted triples / gold | 29 / 36 |
| Ontology class coverage | 81.8% |
| Ontology relation coverage | 38.1% |
| Domain/range-valid relations | 41.4% |
| Predicted / gold attributes | 0 / 6 |

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.

Aggregate-only measurements: [kg-extraction-gliner-kolibri-relations-pilot.json](kg-extraction-gliner-kolibri-relations-pilot.json). Source passages, predictions, and error messages are retained locally, not published.
