# Model providers and extraction benchmarks

## Select Ollama or vLLM

The API and build pipeline select a text-generation provider through
`LLM_BACKEND`. Ollama remains the default. The vLLM adapter uses the
OpenAI-compatible chat-completions API; relation extraction is routed through
the configured provider rather than constructing an Ollama-only chain.

```dotenv
LLM_BACKEND=ollama
```

For vLLM, set `LLM_BACKEND=vllm` and configure `VLLM_MODEL`,
`VLLM_EMBEDDING_MODEL`, and, if needed, `VLLM_API_KEY`. Docker Compose profiles
are derived from `COMPOSE_PROFILES`; set it to the same value as
`LLM_BACKEND` when switching providers:

```dotenv
LLM_BACKEND=vllm
COMPOSE_PROFILES=vllm
VLLM_MODEL=Qwen/Qwen3-8B
VLLM_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
VLLM_API_KEY=EMPTY
```

Stop the prior profile before switching, then start the selected one:

```bash
docker compose down
docker compose up -d --build
```

Only stop this project's services; do not stop shared Workbench or inference
services in a colleague's deployment.

The vLLM Compose profile starts separate generation and embedding servers. This
is necessary because their model tasks differ and means the two model
deployments can compete for GPU memory. Select models that fit the available
GPU and pin `VLLM_IMAGE` to a tested release for non-experimental deployments.
Do not assume the embedding model is interchangeable with one used to index
Qdrant: queries must use the same embedding model and dimensions as indexed
vectors. Re-embed/reindex if the model changes.

The existing Ollama profile uses Ollama 0.35.0 or later for decision-model
support. To pull TEV1 as well as the regular generation/embedding models, set:

```dotenv
LLM_BACKEND=ollama
COMPOSE_PROFILES=ollama
OLLAMA_DECISION_MODEL=tev1:0.8b
```

## Benchmark extraction

Run the current-domain bilingual pilot using the configured provider. It has
22 authored/paraphrased English and German examples (11 paired facts) grounded
in project PDFs. It is for development, not an independent held-out leaderboard:

```bash
LLM_BACKEND=ollama .venv/bin/python scripts/benchmark_kg_extraction.py \
  --entity-extractor llm \
  --relation-extractor llm \
  --dataset data/evaluation/kg_extraction_benchmark_current_domain_v1.json \
  --warmup 1 --repeats 1 \
  --output experiment_results/kg-extraction-ollama-qwen3-32b.json
```

The CLI disables Ollama response caching, warms the selected extractor, records
the dataset hash and raw predictions/errors, measures token provenance and
latency, validates relation domain/range, and reports grouped bootstrap
intervals. Each run writes the detailed raw JSON record, a sibling Markdown
summary, and refreshes `experiment_results/benchmark_paper/reports/README.md`.
`--corpus-probe` additionally samples passages from source PDFs.
That probe reports raw extraction counts, not accuracy, because those passages
do not have exhaustive gold labels.

Compare TEV1 candidate-triple scoring while keeping the same entity extractor:

```bash
OLLAMA_DECISION_MODEL=tev1:0.8b .venv/bin/python scripts/benchmark_kg_extraction.py \
  --entity-extractor llm \
  --relation-extractor decision \
  --output experiment_results/kg-extraction-tev1-smoke.json
```

Compare multilingual GLiNER entity recognition followed by the LLM relation
extractor:

```bash
pip install -e '.[gliner]'
.venv/bin/python scripts/benchmark_kg_extraction.py \
  --entity-extractor gliner \
  --relation-extractor llm \
  --output experiment_results/kg-extraction-gliner-smoke.json
```

The runner records per-passage wall time, provider-reported or explicitly
estimated prompt/completion tokens, exact entity/triple/attribute precision,
recall and F1, evidence endpoint coverage, graph type/attribute richness, raw
predictions, and dataset SHA-256. It disables cache for Ollama's structured
entity calls. The `smoke` data file is a tiny hand-authored wiring fixture,
not a statistically meaningful quality test. A model winner must be selected
from a larger reviewed, document-separated held-out dataset, with warm-up,
repeat trials, and memory measurements.

Initial live pilot results are saved (outside version control) under
`experiment_results/benchmark_paper/reports/`:

- Ollama 0.21.0 with `qwen3:32b` (Q4_K_M), temperature 0.2, top-p 0.9,
  seed 42: entity F1 0.041, triple F1 0.090, attribute F1 0.133; 78,509
  server-reported tokens for the 22-item one-repeat run, median 13.34 s/item.
- An unlabeled probe on 9 paragraphs from 3 source PDFs produced 108 entities
  and 42 triples in 359 s (~59,657 reported tokens). These are raw counts, not
  quality results.
- GLiNER multilingual v2.1 plus the rules relation extractor: entity F1 0.365,
  no triples, median 3.46 s/item, and no LLM tokens. The rules-only relations
  were insufficient for this dataset.
- Kolibri-1 FP8 on vLLM 0.29.0: entity F1 0.283, triple F1 0.281, attribute
  F1 0.000; 64,777 server-reported tokens and median 2.52 s/item.
- GLiNER multilingual v2.1 entities plus Kolibri relation extraction: entity
  F1 0.365, triple F1 0.062, attribute F1 0.000; 28,477 server-reported
  tokens and median 5.02 s/item. This used about 56% fewer tokens than the
  Kolibri all-LLM pilot, but its triple F1 was lower. The runs share the
  development dataset, not a held-out evaluation; the result suggests a
  cheaper entity stage, not a better end-to-end system.
- GLiNER entities plus TEV1 `0.8b` candidate decisions on isolated Ollama
  0.35.0: entity F1 0.365, triple F1 0.028, attribute F1 0.000; 26,340
  server-reported decision tokens, 11 decision calls, and median 4.03 s/item.
  It emitted 36 ontology-valid candidate triples, of which 1 matched gold.
  This demonstrates fast, bounded candidate scoring, but not competitive
  end-to-end triple quality on this pilot.
- Kolibri's separate unlabeled probe over 9 PDF passages produced 16 entities
  and 11 triples in 25 seconds using 24,699 reported tokens. These counts are
  not accuracy metrics because the passages have no exhaustive annotations.

These are first-pass pilot observations, not held-out scores or a model
ranking. The Qwen model digest and GLiNER revision are in their JSON results.
All live run JSON records are under
`experiment_results/benchmark_paper/reports/` (ignored by version control).

`--entity-extractor` accepts `llm`, `gliner`, `rules`, or `rules-first`;
`--relation-extractor` accepts `llm`, `decision`, `rules`, or `rules-first`.
The existing default rule patterns target the repository's nuclear domain, so
interpret rules-only and rules-first scores only on datasets where those
patterns are appropriate.

## What the decision-model experiment measures

TEV1 is not a free-form triple generator. The experimental
`DecisionModelRelationExtractor` enumerates directed entity-pair/relation
candidates that satisfy ontology domain/range constraints, then batches
yes/no evidence questions through Ollama's `/v1/systemone` endpoint (maximum
64 questions per request). It refuses to silently truncate oversized
candidate sets. The benchmark records end-to-end triple scores, ontology validity, and
candidate recall separately; a
decision model cannot recover a triple that the entity/relation candidate
generator never proposed.

### TEV instead of an LLM evidence judge

Add `--decision-judge --decision-base-url http://localhost:11436` to an
LLM/rules relation run to score only its proposed triples against source text.
The judge retains the accepted proposal's evidence and ID. It can replace a
bounded LLM source-support judgement, not the reasoning orchestrator or
ontology validation. Compare with the identical path without judging; report
precision, recall, candidate coverage, added tokens/time, and errors.

### Expanded development matrix and published reports

The approved expanded run covers all 22 examples with three repeats per path,
plus up to ten eligible passages from each of the 33 project PDFs. The ten paths
include rules-only, GLiNER/rules, GLiNER/TEV, Kolibri LLM/LLM, Kolibri with TEV
judging, Kolibri entities/TEV, GLiNER/Kolibri, rules-first/Kolibri, Qwen LLM/LLM,
and GLiNER/Qwen. The currently cached Qwen baseline is **Qwen3:8B**, not the
previous pilot's Qwen3:32B; these are not equal-size model comparisons.

```bash
.venv/bin/python scripts/run_extraction_matrix.py \
  --python "$PWD/.venv/bin/python" \
  --output-dir experiment_results/benchmark_paper/expanded \
  --publish-dir Planning/benchmarks/expanded
```

Install the package and optional API/GLiNER dependencies before running.
The services must already be responsive. Defaults target Ollama on host port
18134, Kolibri on 8000, and a separate TEV Ollama on 11436. The runner executes
paths sequentially, records status in `matrix-status.json`, captures per-path
logs, and exports each completed aggregate report. It does not automatically
commit or push. Failed paths and extraction errors remain explicit.
An explicit `--python` keeps workers in the virtualenv even if a detached
launcher resolves the driver's Python symlink to the system interpreter.

Publish existing reports with:

```bash
.venv/bin/python scripts/publish_extraction_reports.py \
  --input-dir experiment_results/benchmark_paper/reports \
  --output-dir Planning/benchmarks/pilots
```

Tracked aggregate-only JSON and Markdown live under `Planning/benchmarks/`.
Raw PDF passages, evidence quotes, predictions, and error messages remain in
the ignored experiment directory and are not pushed. More repetitions and
unlabeled passages do **not** turn these development examples into a held-out
quality benchmark. Corpus results measure throughput and graph size, not accuracy.
The first expanded rules-only path processed 260 passages. Four PDFs produced
no eligible text (one checked file had an empty text layer); these are recorded
as corpus skips/errors, not successful zero-extraction documents. OCR or improved
loading is needed before claiming extraction coverage of those files.

## Model availability caveats

GLiNER is an optional Python-side entity-span model and does not extract
relations or attributes by itself. It has not been part of the repository's
prior extraction implementation; its adapter is now available for benchmarking.
The benchmarked `urchade/gliner_multi-v2.1` revision is
`443d26d654e0324125a96bebd8e796c14ff2efe6`.

## Kolibri on vLLM

Kolibri is available as open weights on
[Hugging Face](https://huggingface.co/Aleph-Alpha/Kolibri-1). Its card specifies
Apache-2.0, German and English, 78.1B total / 3.46B active parameters, FP8
weights (~78 GB), and at least one H200 for serving. Serving requires Aleph
Alpha's [`aleph-alpha-inference`](https://github.com/Aleph-Alpha/aleph-alpha-inference)
plugin, which currently supports vLLM 0.29. The `kolibri` Compose profile uses
that plugin image pinned to its current linux/amd64 manifest digest in
`.env.example` and the model card's parser flags. Keep the generic and Kolibri
vLLM profiles mutually exclusive; they both bind port 8000.

For a single-GPU benchmark, configure:

```dotenv
LLM_BACKEND=vllm
COMPOSE_PROFILES=kolibri
VLLM_MODEL=Aleph-Alpha/Kolibri-1
LLM_TEMPERATURE=1.0
LLM_TOP_P=0.97
LLM_SEED=42
LLM_CHAT_TEMPLATE_KWARGS={"enable_thinking":false}
KOLIBRI_GPU_DEVICE=0
KOLIBRI_MODEL_REVISION=e52eb4627d11516b0c01de49210ab5a4e4061444
```

Then start only the inference service and run from the host:

```bash
docker compose --profile kolibri up -d kgb-vllm-kolibri
VLLM_BASE_URL=http://localhost:8000/v1 \
VLLM_EMBEDDING_BASE_URL=http://localhost:8002/v1 \
.venv/bin/python scripts/benchmark_kg_extraction.py \
  --backend vllm --model Aleph-Alpha/Kolibri-1 \
  --model-revision e52eb4627d11516b0c01de49210ab5a4e4061444 \
  --temperature 1.0 --top-p 0.97 --seed 42 \
  --corpus-probe --corpus-documents 3 --corpus-paragraphs 3 \
  --output experiment_results/kg-extraction-kolibri.json
```

The initial comparator is Qwen3-30B-A3B on the same vLLM 0.29 server; its
~30B total / ~3B active weights make active compute comparable, but it is not
parameter- or memory-identical to Kolibri. Start only one large model at a
time and record the image digest, HF model revision, and GPU snapshots. The
separate embedding service is not needed for extraction-only runs.
