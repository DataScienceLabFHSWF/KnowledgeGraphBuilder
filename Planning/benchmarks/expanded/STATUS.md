# Expanded benchmark publication status

Snapshot: 2026-10-05, approximately 16:00 Europe/Berlin.

This publication contains seven completed configurations, each with 22
development examples repeated three times (66 labeled trials) and an
unlabeled corpus probe over the 33 available PDFs. The probe processed 260
eligible passages per completed configuration; four PDFs had no eligible
extracted text. Counts and errors are retained in each aggregate report.
The dataset is not independently reviewed or held out.

| Configuration | Execution status | Labeled extraction errors | Corpus errors/skips |
|---|---|---:|---:|
| Rules-only | Completed with corpus skips | 0 | 4 |
| GLiNER / rules | Completed with corpus skips | 0 | 4 |
| GLiNER / TEV1 | Completed with corpus errors | 0 | 93 |
| Kolibri entities / Kolibri relations | Completed with corpus skips | 0 | 4 |
| Kolibri entities / TEV1 relations | Completed with corpus errors | 0 | 6 |
| GLiNER / Kolibri | Completed with corpus skips | 0 | 4 |
| Kolibri rules-first cascade | Completed with corpus skips | 0 | 4 |
| Kolibri with TEV1 evidence judge | Failed during warm-up; no scored report | Not measured | Not measured |
| Qwen3:8B entities / relations | Running at publication time | Pending | Pending |
| GLiNER / Qwen3:8B | Not yet started at publication time | Pending | Pending |

The TEV evidence-judge run failed when its relation extractor supplied a
proposal that the judge did not recognize as an ontology-valid triple.
No quality or performance score is published for that configuration.
The failed run must be investigated and rerun before drawing conclusions
about TEV judging.

GLiNER / TEV1 candidate recall on the labeled set was 0.028. This means the
candidate stage itself omitted most gold triples; end-to-end TEV results
cannot be interpreted as an isolated test of decision-model accuracy.
Corpus graph sizes are not accuracy measurements, and the 93 corpus
errors/skips for that configuration must be considered alongside its counts.

Raw predictions, source passages, evidence, detailed error messages, logs,
and the live matrix status remain local under the ignored
`experiment_results/benchmark_paper/expanded/` directory. Only aggregate
measurements and this status summary are published.

The persistent runner exports additional completed configurations locally,
but does not automatically commit or push them. A follow-up results commit
is required for the Qwen runs and any corrected judge run.

See [the comparison index](README.md) for the published measurements.
