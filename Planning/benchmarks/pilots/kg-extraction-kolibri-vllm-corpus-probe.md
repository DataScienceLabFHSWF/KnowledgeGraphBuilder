# KG extraction benchmark: Aleph-Alpha/Kolibri-1

- **Run:** 2026-10-05T09:29:44.744891+00:00
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
| Entity | 0.250 | 0.242 | 0.246 | [0.098, 0.394] |
| Triple | 0.207 | 0.167 | 0.185 | [0.000, 0.452] |
| Attribute | 0.333 | 0.167 | 0.222 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 2.56 s |
| P95 latency/item | 4.68 s |
| Mean latency/item | 2.79 s |
| Prompt tokens | 57,543 |
| Completion tokens | 9,535 |
| Total tokens | 67,078 |
| Token source | server (44 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 64 / 66 |
| Predicted triples / gold | 29 / 36 |
| Ontology class coverage | 100.0% |
| Ontology relation coverage | 47.6% |
| Domain/range-valid relations | 48.3% |
| Predicted / gold attributes | 3 / 6 |

## Unlabeled source-document probe

This is an exploratory extraction count, not an accuracy score; the passages do not have exhaustive gold annotations.

- Entities: 16
- Triples: 11
- Elapsed: 24.65 s

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.

Aggregate-only measurements: [kg-extraction-kolibri-vllm-corpus-probe.json](kg-extraction-kolibri-vllm-corpus-probe.json). Source passages, predictions, and error messages are retained locally, not published.
