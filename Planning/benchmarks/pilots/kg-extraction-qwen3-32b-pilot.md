# KG extraction benchmark: qwen3:32b

- **Run:** 2026-10-05T09:06:39.568259+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats not recorded)
- **Configured backend/model:** ollama / qwen3:32b
- **Extractors:** entities `llm`, relations `llm`
- **Generative LLM stage:** used
- **Decision evidence judge:** disabled
- **Model revision:** qwen3:32b sha256:030ee887880fc378860c2dd35101da424377520441ae4bfe7be6deff8ade7840
- **Dataset SHA-256:** `786f9d7bcbbfe8ab6ba23ae57d38e0ff37d45e3caedd11f320429d014998fde4`

## Quality

| Metric | Precision | Recall | F1 | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Entity | 0.037 | 0.045 | 0.041 | [0.000, 0.121] |
| Triple | 0.075 | 0.111 | 0.090 | [0.000, 0.213] |
| Attribute | 0.111 | 0.167 | 0.133 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 13.34 s |
| P95 latency/item | 16.63 s |
| Mean latency/item | 12.69 s |
| Prompt tokens | 64,732 |
| Completion tokens | 13,777 |
| Total tokens | 78,509 |
| Token source | server (44 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 81 / 66 |
| Predicted triples / gold | 53 / 36 |
| Ontology class coverage | 100.0% |
| Ontology relation coverage | 27.3% |
| Domain/range-valid relations | 69.8% |
| Predicted / gold attributes | 9 / 6 |

## Unlabeled source-document probe

This is an exploratory extraction count, not an accuracy score; the passages do not have exhaustive gold annotations.

- Entities: 108
- Triples: 42
- Documents attempted: 3
- Passages processed: 9
- Corpus errors/skips: 0
- Reported corpus tokens: 59,657
- Elapsed: 359.18 s

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.
Evidence/ontology validity ratios are vacuous when no relations are predicted; they do not establish extraction quality.

Aggregate-only measurements: [kg-extraction-qwen3-32b-pilot.json](kg-extraction-qwen3-32b-pilot.json). Source passages, predictions, and error messages are retained locally, not published.
