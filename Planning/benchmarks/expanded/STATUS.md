# Expanded benchmark publication status

Final execution snapshot: 2026-10-05, 23:09 Europe/Berlin.
The matrix finished with failures: seven configurations produced scored
reports and three failed without scored reports.

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
| Qwen3:8B entities / relations | Failed during warm-up; no scored report | Not measured | Not measured |
| GLiNER / Qwen3:8B | Failed during warm-up; no scored report | Not measured | Not measured |

The TEV evidence-judge run failed when its relation extractor supplied a
proposal that the judge did not recognize as an ontology-valid triple.
No quality or performance score is published for that configuration.
The failed run must be investigated and rerun before drawing conclusions
about TEV judging.

Both Qwen configurations failed after repeated Ollama inference read timeouts,
eventually opening the provider's circuit breaker. No scored report was
generated, so these failures are not zero quality scores. A post-run provider
check was responsive and reported Qwen loaded with zero VRAM allocation;
this observation does not establish its allocation throughout the failed runs.
Check GPU placement and provider capacity, then verify a bounded warm-up before
rerunning either configuration.

GLiNER / TEV1 candidate recall on the labeled set was 0.028. This means the
candidate stage itself omitted most gold triples; end-to-end TEV results
cannot be interpreted as an isolated test of decision-model accuracy.
Corpus graph sizes are not accuracy measurements, and the 93 corpus
errors/skips for that configuration must be considered alongside its counts.

Raw predictions, source passages, evidence, detailed error messages, logs,
and the live matrix status remain local under the ignored
`experiment_results/benchmark_paper/expanded/` directory. Only aggregate
measurements and this status summary are published.

The runner stopped the dedicated TEV and Kolibri containers after completing
the matrix. Shared model services were left running.
No additional scored reports were produced after the seven published runs.
Corrected Qwen and judge runs require a new execution and results publication;
the runner never automatically commits or pushes reports.

See [the comparison index](README.md) for the published measurements.
