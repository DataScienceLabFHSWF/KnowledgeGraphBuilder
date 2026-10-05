# KG extraction benchmark: Aleph-Alpha/Kolibri-1

- **Run:** 2026-10-05T13:07:28.770576+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats 3)
- **Configured backend/model:** vllm / Aleph-Alpha/Kolibri-1
- **Extractors:** entities `rules-first`, relations `rules-first`
- **Generative LLM stage:** conditional fallback; may be skipped per item
- **Decision evidence judge:** disabled
- **Model revision:** e52eb4627d11516b0c01de49210ab5a4e4061444
- **Dataset SHA-256:** `786f9d7bcbbfe8ab6ba23ae57d38e0ff37d45e3caedd11f320429d014998fde4`

## Quality

| Metric | Precision | Recall | F1 | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Entity | 0.268 | 0.227 | 0.246 | [0.101, 0.387] |
| Triple | 0.138 | 0.111 | 0.123 | [0.000, 0.291] |
| Attribute | 0.000 | 0.000 | 0.000 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 2.41 s |
| P95 latency/item | 4.01 s |
| Mean latency/item | 2.40 s |
| Prompt tokens | 163,947 |
| Completion tokens | 24,807 |
| Total tokens | 188,754 |
| Token source | server (126 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 168 / 198 |
| Predicted triples / gold | 87 / 108 |
| Ontology class coverage | 90.9% |
| Ontology relation coverage | 38.1% |
| Domain/range-valid relations | 41.4% |
| Predicted / gold attributes | 0 / 18 |

## Unlabeled source-document probe

This is an exploratory extraction count, not an accuracy score; the passages do not have exhaustive gold annotations.

- Entities: 1186
- Triples: 753
- Documents attempted: 33
- Passages processed: 260
- Corpus errors/skips: 4
- Reported corpus tokens: 1,024,839
- Elapsed: 1516.76 s

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.
Evidence/ontology validity ratios are vacuous when no relations are predicted; they do not establish extraction quality.

Aggregate-only measurements: [kg-extraction-kolibri-rules-first.json](kg-extraction-kolibri-rules-first.json). Source passages, predictions, and error messages are retained locally, not published.
