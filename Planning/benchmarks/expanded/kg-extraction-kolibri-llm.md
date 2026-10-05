# KG extraction benchmark: Aleph-Alpha/Kolibri-1

- **Run:** 2026-10-05T11:48:04.701070+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats 3)
- **Configured backend/model:** vllm / Aleph-Alpha/Kolibri-1
- **Extractors:** entities `llm`, relations `llm`
- **Generative LLM stage:** used
- **Decision evidence judge:** disabled
- **Model revision:** e52eb4627d11516b0c01de49210ab5a4e4061444
- **Dataset SHA-256:** `786f9d7bcbbfe8ab6ba23ae57d38e0ff37d45e3caedd11f320429d014998fde4`

## Quality

| Metric | Precision | Recall | F1 | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Entity | 0.269 | 0.227 | 0.247 | [0.102, 0.386] |
| Triple | 0.120 | 0.093 | 0.105 | [0.000, 0.251] |
| Attribute | 0.200 | 0.056 | 0.087 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 2.40 s |
| P95 latency/item | 4.12 s |
| Mean latency/item | 2.41 s |
| Prompt tokens | 163,934 |
| Completion tokens | 24,615 |
| Total tokens | 188,549 |
| Token source | server (126 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 167 / 198 |
| Predicted triples / gold | 83 / 108 |
| Ontology class coverage | 90.9% |
| Ontology relation coverage | 42.9% |
| Domain/range-valid relations | 39.8% |
| Predicted / gold attributes | 5 / 18 |

## Unlabeled source-document probe

This is an exploratory extraction count, not an accuracy score; the passages do not have exhaustive gold annotations.

- Entities: 1295
- Triples: 896
- Documents attempted: 33
- Passages processed: 260
- Corpus errors/skips: 4
- Reported corpus tokens: 1,052,474
- Elapsed: 1638.03 s

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.
Evidence/ontology validity ratios are vacuous when no relations are predicted; they do not establish extraction quality.

Aggregate-only measurements: [kg-extraction-kolibri-llm.json](kg-extraction-kolibri-llm.json). Source passages, predictions, and error messages are retained locally, not published.
