# KG extraction benchmark: Aleph-Alpha/Kolibri-1

- **Run:** 2026-10-05T12:06:18.704063+00:00
- **Dataset:** KGBuilder nuclear decommissioning bilingual pilot (1.0.0, pilot-evaluation; 22 items; de, en; repeats 3)
- **Configured backend/model:** vllm / Aleph-Alpha/Kolibri-1
- **Extractors:** entities `llm`, relations `decision`
- **Generative LLM stage:** used
- **Decision evidence judge:** disabled
- **Model revision:** e52eb4627d11516b0c01de49210ab5a4e4061444
- **Dataset SHA-256:** `786f9d7bcbbfe8ab6ba23ae57d38e0ff37d45e3caedd11f320429d014998fde4`

## Quality

| Metric | Precision | Recall | F1 | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Entity | 0.268 | 0.227 | 0.246 | [0.101, 0.387] |
| Triple | 0.000 | 0.000 | 0.000 | [0.000, 0.000] |
| Attribute | 0.000 | 0.000 | 0.000 | - |

## Runtime and usage

| Measure | Result |
|---|---:|
| Median latency/item | 1.70 s |
| P95 latency/item | 2.68 s |
| Mean latency/item | 1.56 s |
| Prompt tokens | 95,328 |
| Completion tokens | 15,903 |
| Total tokens | 111,231 |
| Token source | server (69 calls) |
| Errors | 0 |

## Knowledge-graph coverage

| Measure | Result |
|---|---:|
| Predicted entities / gold | 168 / 198 |
| Predicted triples / gold | 3 / 108 |
| Ontology class coverage | 90.9% |
| Ontology relation coverage | 4.8% |
| Domain/range-valid relations | 100.0% |
| Predicted / gold attributes | 0 / 18 |


## Decision candidate coverage

- Candidates: 3; gold covered: 0/108.
- Candidate recall: 0.000.
- This bounds decision-stage recall; missing proposals cannot be recovered by judging.
- **Decision model:** tev1:0.8b

## Unlabeled source-document probe

This is an exploratory extraction count, not an accuracy score; the passages do not have exhaustive gold annotations.

- Entities: 1187
- Triples: 44
- Documents attempted: 33
- Passages processed: 260
- Corpus errors/skips: 6
- Reported corpus tokens: 657,243
- Elapsed: 969.22 s

## Interpretation

This is a development-pilot result, not a held-out or independently expert-reviewed model ranking. Read quality alongside richness, latency, and token usage; do not select a production winner from this run alone.
Evidence/ontology validity ratios are vacuous when no relations are predicted; they do not establish extraction quality.

Aggregate-only measurements: [kg-extraction-kolibri-entities-tev1.json](kg-extraction-kolibri-entities-tev1.json). Source passages, predictions, and error messages are retained locally, not published.
