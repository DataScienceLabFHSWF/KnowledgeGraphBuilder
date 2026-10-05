# KG extraction benchmark: Aleph-Alpha/Kolibri-1

- **Run:** 2026-10-05T12:39:18.463622+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats 3)
- **Configured backend/model:** vllm / Aleph-Alpha/Kolibri-1
- **Extractors:** entities `gliner`, relations `llm`
- **Generative LLM stage:** used
- **Decision evidence judge:** disabled
- **Model revision:** e52eb4627d11516b0c01de49210ab5a4e4061444
- **Dataset SHA-256:** `786f9d7bcbbfe8ab6ba23ae57d38e0ff37d45e3caedd11f320429d014998fde4`

## Quality

| Metric | Precision | Recall | F1 | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Entity | 0.383 | 0.348 | 0.365 | [0.193, 0.506] |
| Triple | 0.065 | 0.056 | 0.060 | [0.000, 0.148] |
| Attribute | 0.000 | 0.000 | 0.000 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 4.22 s |
| P95 latency/item | 5.48 s |
| Mean latency/item | 4.02 s |
| Prompt tokens | 76,119 |
| Completion tokens | 10,111 |
| Total tokens | 86,230 |
| Token source | server (66 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 183 / 198 |
| Predicted triples / gold | 93 / 108 |
| Ontology class coverage | 81.8% |
| Ontology relation coverage | 38.1% |
| Domain/range-valid relations | 40.9% |
| Predicted / gold attributes | 0 / 18 |

## Unlabeled source-document probe

This is an exploratory extraction count, not an accuracy score; the passages do not have exhaustive gold annotations.

- Entities: 2129
- Triples: 745
- Documents attempted: 33
- Passages processed: 260
- Corpus errors/skips: 4
- Reported corpus tokens: 507,620
- Elapsed: 1695.03 s

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.
Evidence/ontology validity ratios are vacuous when no relations are predicted; they do not establish extraction quality.

Aggregate-only measurements: [kg-extraction-gliner-kolibri.json](kg-extraction-gliner-kolibri.json). Source passages, predictions, and error messages are retained locally, not published.
