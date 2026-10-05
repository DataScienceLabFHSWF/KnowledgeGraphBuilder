# KG extraction model and serving benchmark

## Goal

Compare ontology-grounded triple extraction quality, runtime, and token use
across local model families and serving backends before changing the default
pipeline. Preserve a selectable Ollama deployment and add vLLM as an
OpenAI-compatible generation backend.

## Facts and constraints verified so far

- TEV1 is a decision model. Ollama exposes it through `/v1/systemone` with
  choice, yes/no, and rubric questions; it returns decisions and probabilities,
  not unconstrained text or generated spans/triples. A triple-extraction
  experiment must generate bounded candidate triples first and measure that
  candidate-generation work and its token cost.
- TEV1 can test up to 64 questions per request; the user-facing Ollama library
  page says its decision-model endpoint requires Ollama 0.35 or later.
- vLLM exposes OpenAI-compatible chat-completions and embeddings APIs, but each
  model is served as a configured model deployment. Generation, embeddings,
  and decision models may therefore require separate containers/endpoints and
  compete for GPU memory.
- Current retrieval asks the LLM provider for embeddings. Replacing only chat
  generation with vLLM is insufficient; the vLLM configuration needs a
  compatible embedding endpoint/model as well, or must explicitly retain a
  separate embedding service.
- No GLiNER package or implementation was found in the repository.
- The [Kolibri-1 model card](https://huggingface.co/Aleph-Alpha/Kolibri-1)
  identifies an Apache-2.0, German/English `Kolibri1ForCausalLM` MoE with
  78.1B total and 3.46B active parameters, FP8 weights (~78 GB), and one-H200
  minimum serving support. It requires Aleph Alpha's `aleph-alpha-inference`
  plugin; that plugin currently supports vLLM 0.29.
- The benchmark host has two NVIDIA H200 NVL GPUs (143,771 MiB each). Before
  the current Ollama trial, GPU 0 had ~142 GiB free and GPU 1 had ~92 GiB free
  with another workload using ~50 GiB. GPU 0 is being used for the sequential
  baseline/Kolibri trials; avoid concurrent model launches.

## Benchmark design

### Systems under test

1. Current LLM entity + relation extraction baseline.
2. GLiNER entity recognition followed by relation extraction, to isolate the
   value of a small span-labeling model.
3. Rules-only and rules-first tiered extraction, measuring the quality/speed
   trade-off rather than assuming high-precision rules are complete.
4. TEV1 candidate-triple decision scoring: generate candidates from detected
   entities and ontology relations, then score in batches (at most 64 questions
   per `/v1/systemone` call). Report candidate recall separately, since a
   decision model cannot recover a triple that candidate generation omitted.
5. A combined cascade with a generative fallback for candidates/attributes
   that earlier stages cannot resolve.

Compare models only on capabilities they support. Include TEV1's Qwen3.5-4B
base as a same-family control if it is locally servable. For Kolibri, use
Qwen3-30B-A3B as a comparable active-compute MoE baseline; record the
substantial total-weight difference and serve both sequentially on the same
GPU/vLLM release.

### Dataset and metrics

The first current-domain development set now contains 22 labeled German and
English passages (11 paired source-grounded facts), including attributes and
evidence spans, with source PDF references. German and English samples are
authored paraphrases/translations rather than copied PDF text. The pairs share
`variant_of` groups for document/split integrity and bootstrap intervals.
This is a development pilot annotated by the implementation team, not an
independent expert-reviewed or held-out benchmark. Expand it with expert
review and source-document-separated samples before making quality claims.

Record per document and aggregate:

- elapsed time, time-to-first-result if available, and throughput;
- input/output/total tokens from provider usage; mark estimates separately
  where a server does not expose token counts;
- entity and triple precision, recall, and F1 after documented canonicalization;
- relation-type accuracy, ontology domain/range validity, grounded-evidence
  rate, attribute precision/recall, and JSON/schema failure/retry rate;
- KG richness: unique entities and triples, ontology class/relation coverage,
  attribute coverage, and evidence coverage. Report richness alongside
  precision/recall so noisy over-extraction cannot appear better by count;
- peak GPU/host memory and model footprint when measurable.

Disable response caching, warm each server/model before timed trials, use fixed
decoding parameters and seeds where supported, repeat trials, and report
median/p95 latency and confidence intervals. Retain raw per-item outputs and
errors for audit.

## Delivery phases

1. **Provider seam** (implemented): add `LLM_BACKEND=ollama|vllm`, an
   OpenAI-compatible provider for vLLM chat and embeddings, preserve Ollama as
   default, and test both through mocked HTTP calls. Relation extraction now
   uses the configured provider seam. Compose profiles configure separate
   vLLM chat and embedding servers.
2. **Gold dataset and harness** (pilot implemented): define the data contract,
   add a bilingual current-domain pilot, warmups/repeats, token provenance,
   raw predictions/errors, ontology validity, coverage, and group-bootstrap
   intervals. The CLI can also run an unlabeled exploratory pass over source
   PDFs; that output is not scored as accuracy.
3. **Candidate systems** (partially implemented): add GLiNER entity extraction
   and a TEV1 decision client/candidate-relation scorer. Remaining: add
   ontology-aware configurable rule/tiered baselines; keep candidate-generation
   recall and model decision quality independently measurable in the final
   annotation/evaluation set.
4. **Deployment profiles** (initial profiles implemented): add Ollama and vLLM
   Compose configurations, pin generic vLLM to 0.29.0, and add a separate
   Kolibri profile using the official plugin image and parser flags. vLLM
   configures generation and embeddings independently; TEV1 still requires
   Ollama >=0.35.0. Keep profile selection explicit and schedule large models
   sequentially on constrained GPUs. Validate image digest and resource sizing.
5. **Evaluation and decision** (development pilots run): ran Qwen3:32B on the
   bilingual pilot and a 9-passage unlabeled PDF probe; GLiNER with rules-only
   relations; Kolibri-1 on vLLM for the labeled pilot and unlabeled probe;
   GLiNER entities with Kolibri relation extraction; and GLiNER entities with
   TEV1 candidate scoring on isolated Ollama 0.35.0. Their first-pass results
   are recorded in `experiment_results/benchmark_paper/reports/`. The set is
   not held out and is not expert-reviewed. The GLiNER/Kolibri hybrid used
   about 56% fewer reported tokens than the Kolibri all-LLM run, but triple F1
   was lower (0.062 versus 0.281). GLiNER/TEV1 triple F1 was 0.028; the current
   harness now reports candidate recall separately and supports TEV judging
   of LLM/rules proposals via `--decision-judge`. The comparable
   Qwen vLLM run remains unrun; no default selection is justified.

## Acceptance criteria

- Provider selection is explicit, validates supported backend names, and does
  not change the existing Ollama default.
- The benchmark records token counts with provenance (server-reported versus
  estimated), elapsed time, structured-output failures, and quality/richness
  metrics for every item.
- All systems consume identical text, ontology definitions, chunking, and
  candidate boundaries where comparable.
- No model is declared a winner from an unheld-out set or raw KG size alone.
- The benchmark can run in mocked smoke mode without GPU/network access; live
  model comparisons require documented hardware, model revisions, and serving
  configuration.

## Approved expanded run and publication

The expanded development matrix uses all 22 bilingual examples, three repeat
trials per path, and ten eligible passages per PDF across all 33 current PDFs.
It includes ten rule/GLiNER/LLM/decision/judging paths. Qwen3:8B is the available
generation control; the old Qwen3:32B pilot is kept separate. Execution is
sequential through `scripts/run_extraction_matrix.py`, with durable per-path
status and logs. This is a larger **development/performance** evaluation, not
a full-document run or independently reviewed quality benchmark.

The user approved a persistent background run and staged publication. Commit
aggregate-only JSON and Markdown under `Planning/benchmarks/`; retain raw
corpus passages, evidence, predictions, and error messages locally. Each
completed run is exported automatically; commits/pushes are manual. A later
results commit is required when the long matrix completes.

## Questions to resolve during implementation

- Run Kolibri on the available H200 and record image/model revisions, actual
  memory, cold-start time, and inference results.
- Confirm whether TEV1 can be enabled in the running benchmark service and
  measure its candidate-generation recall.
- Expand the development pilot into an independent, source-document-separated
  gold set with a domain reviewer before publishing comparative claims.
