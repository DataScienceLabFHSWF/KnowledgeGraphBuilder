# KG extraction benchmark: qwen3:8b

- **Run:** 2026-10-05T10:49:23.920001+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats 3)
- **Configured backend/model:** ollama / qwen3:8b
- **Extractors:** entities `gliner`, relations `rules`
- **Generative LLM stage:** not invoked by this path
- **Decision evidence judge:** disabled
- **Model revision:** 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
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
| Median latency/item | 3.77 s |
| P95 latency/item | 4.01 s |
| Mean latency/item | 3.78 s |
| Prompt tokens | not reported |
| Completion tokens | not reported |
| Total tokens | not reported |
| Token source | unavailable (0 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 183 / 198 |
| Predicted triples / gold | 0 / 108 |
| Ontology class coverage | 81.8% |
| Ontology relation coverage | 0.0% |
| Domain/range-valid relations | 100.0% |
| Predicted / gold attributes | 0 / 18 |

## Unlabeled source-document probe

This is an exploratory extraction count, not an accuracy score; the passages do not have exhaustive gold annotations.

- Entities: 2129
- Triples: 0
- Documents attempted: 33
- Passages processed: 260
- Corpus errors/skips: 4
- Reported corpus tokens: not reported
- Elapsed: 1387.14 s

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.
Evidence/ontology validity ratios are vacuous when no relations are predicted; they do not establish extraction quality.

Aggregate-only measurements: [kg-extraction-gliner-rules.json](kg-extraction-gliner-rules.json). Source passages, predictions, and error messages are retained locally, not published.
