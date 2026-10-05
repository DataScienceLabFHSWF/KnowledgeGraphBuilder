# KG extraction benchmark: Aleph-Alpha/Kolibri-1

- **Run:** 2026-10-05T09:27:58.579592+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats not recorded)
- **Configured backend/model:** vllm / Aleph-Alpha/Kolibri-1
- **Extractors:** entities `llm`, relations `llm`
- **Generative LLM stage:** used
- **Decision evidence judge:** disabled
- **Model revision:** hf:e52eb4627d11516b0c01de49210ab5a4e4061444; image:sha256:ac93d782890eb942dd59afa7cee9fa1e681d09f63a0036b21ea7664a254ed7d5
- **Dataset SHA-256:** `786f9d7bcbbfe8ab6ba23ae57d38e0ff37d45e3caedd11f320429d014998fde4`

## Quality

| Metric | Precision | Recall | F1 | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Entity | 0.295 | 0.273 | 0.283 | [0.153, 0.400] |
| Triple | 0.321 | 0.250 | 0.281 | [0.000, 0.538] |
| Attribute | 0.000 | 0.000 | 0.000 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 2.52 s |
| P95 latency/item | 4.37 s |
| Mean latency/item | 2.68 s |
| Prompt tokens | 55,893 |
| Completion tokens | 8,884 |
| Total tokens | 64,777 |
| Token source | server (43 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 61 / 66 |
| Predicted triples / gold | 28 / 36 |
| Ontology class coverage | 90.9% |
| Ontology relation coverage | 42.9% |
| Domain/range-valid relations | 53.6% |
| Predicted / gold attributes | 2 / 6 |

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.
Evidence/ontology validity ratios are vacuous when no relations are predicted; they do not establish extraction quality.

Aggregate-only measurements: [kg-extraction-kolibri-vllm-pilot.json](kg-extraction-kolibri-vllm-pilot.json). Source passages, predictions, and error messages are retained locally, not published.
