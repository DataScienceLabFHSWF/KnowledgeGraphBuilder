# Agentic Pipeline: Skills, Tools, and Subagents

## Why this exists

The original discovery loop made one hardcoded call sequence per research
question: retrieve -> extract -> extract relations -> static-validate. That
works, but it can't easily be reconfigured (different model per ontology
module, skip a stage, run validation instead of extraction) without editing
`IterativeDiscoveryLoop` itself.

This refactor introduces three small abstractions and layers them on top of
the existing extraction/validation code, without removing it:

- **Tool** (`kgbuilder.tools`) -- a thin, stateless wrapper around one
  existing capability (`extractor.extract(...)`, `validator.validate(...)`,
  a retriever call, ...). Tools have no framework dependency; they are
  ordinary dataclasses with a `handler` callable.
- **Skill** (`kgbuilder.skills`) -- composes one or more tools into a
  bounded unit of work ("retrieve, then extract", "retrieve, then validate").
- **Subagent** (`kgbuilder.agents`) -- a `BaseAgent` bound to specific
  resources (a retriever/extractor pair, an ontology module, a validator)
  that exposes skills as callable methods.

This mirrors how a LangChain/LangGraph tool-calling agent is built, but
every piece works standalone with plain Python objects — no LLM required to
drive the control flow itself (the LLM is only used inside extractor/
validator implementations).

## Competency-question-driven routing

Per Keet & Khan's QuO model (arXiv:2412.13688), `CQType` classifies every
`ResearchQuestion`:

| CQType | Meaning | Routed to |
|--------|---------|-----------|
| **SCQ** (Scoping) | "What exists?" | Extraction subagents |
| **RCQ** (Relationship) | "How do things relate?" | Extraction subagents (relation-focused) |
| **VCQ** (Validating) | "Is what's in the KG correct/complete?" | `ValidationAgent` |
| **FCQ** (Foundational) | Align to a foundational ontology (CCO/BFO) | *(not yet wired to a pipeline stage)* |
| **MpCQ** (Metaproperty) | Classify by rigidity/identity/... | *(not yet wired to a pipeline stage)* |

`IterativeDiscoveryLoop` splits every batch of questions (initial and
follow-up) by `cq_type` before dispatching: SCQ/RCQ go to extraction, VCQ
goes to `ValidationAgent`. Nothing is silently dropped.

## Module-scoped extraction subagents

Ontology classes are grouped into modules via the `kg:module` SHACL/OWL
annotation (see `data/ontology/domain/decommissioning.owl`). Instead of one
monolithic extraction pass over the whole ontology:

```
OntologyService.get_module_class_map()
        │  {"Assets and Locations": ["Facility", ...], "Waste and Materials": [...], ...}
        ▼
OrchestratorAgent.build_module_bindings(module_map, questions, retriever, extractor)
        │  assigns each question to the module(s) owning its entity_class
        ▼
one ModuleExtractionAgent per module (own retriever/extractor pair)
        │  runs concurrently (ThreadPoolExecutor, max_workers)
        ▼
JoinModuleResultsSkill
        │  dedupes by (label, entity_type), keeps highest confidence, merges evidence
        ▼
merged entity list
```

Because each `ModuleBinding` carries its own retriever/extractor, different
modules can use different models — see [Agent Swarm Configuration](#agent-swarm-configuration)
below.

## Validation as a first-class stage

`ValidationAgent` (`agents/validation_agent.py`) consumes VCQ questions: for
each one, it retrieves evidence and asks a validator
`validate_question(question, evidence)` whether existing KG content answers
it correctly/completely. This is the pre-assembly validation-stage consumer
that was previously missing — VCQ questions were generated but never
executed.

Post-assembly validation (SHACL shapes, semantic rules, consistency
checking — the same checks `POST /validate` runs) is now also available as
tools (`kgbuilder.tools.kg_validation_tools`) and a combined skill
(`kgbuilder.skills.kg_validation_skill.KGValidationSkill`), so a
`pipeline.md` plan can invoke the same validation stage the FastAPI route
uses.

## Agent Swarm Configuration

`kgbuilder.agents.swarm_config.SwarmModelConfig` lets you assign a
different (e.g. smaller/cheaper) model per ontology module and bound how
many module subagents run concurrently:

```json
{
  "backend": "ollama",
  "base_url": "http://localhost:11434",
  "default_model": "qwen3:8b",
  "module_models": {
    "Assets and Locations": "qwen3:1.7b",
    "Waste and Materials": "qwen3:8b"
  },
  "max_concurrent_agents": 3
}
```

See [`data/profiles/agent_swarm.example.json`](https://github.com/DataScienceLabFHSWF/KnowledgeGraphBuilder/blob/main/data/profiles/agent_swarm.example.json).
`build_module_bindings_with_swarm_config()` builds one retriever/extractor
pair per *distinct model* (shared across modules assigned that model) via
factory callables you supply, then hands the resulting `ModuleBinding` list
to `OrchestratorAgent(max_workers=swarm_config.max_concurrent_agents)`.

`experiment.config.KGBuilderParams` gained an optional `swarm_config_path`
field so benchmarking/experiment variants can reference a swarm config
alongside the existing single `model` field (backward compatible — unset
means "one model for everything", as before).

### Ollama vs. vLLM for concurrent subagents

The module orchestrator runs several subagents concurrently, each issuing
LLM calls against a shared inference backend. Two practical options:

- **Ollama (current default)** -- simplest to run locally, good model
  management (`ollama pull`), fine for a handful of concurrent
  small-to-medium models on a single GPU/CPU box. Ollama serializes/queues
  requests to the same loaded model rather than batching them, so
  concurrency gains from `max_concurrent_agents` mostly come from using
  *different* models per module (each gets its own request queue) rather
  than many parallel calls to one model.
- **vLLM** -- an OpenAI-compatible server with continuous batching and
  PagedAttention, built for exactly this "many concurrent requests to one
  model" pattern. It scales much better when several module subagents hit
  the *same* model concurrently, and can serve multiple models behind one
  process with better GPU utilization than several Ollama instances.

**Recommendation**: keep Ollama as the default for local development and
small swarms (a few modules, mostly-distinct small models — the common case
here). Consider vLLM once concurrency actually becomes the bottleneck: many
modules sharing one larger model, or when running experiments/benchmarks at
higher throughput. Switching backends is a client-construction concern only
(point an OpenAI-compatible client at the vLLM server); it does not require
changes to `ModuleExtractionAgent`, `OrchestratorAgent`, or `ValidationAgent`,
since they only depend on the `retriever`/`extractor`/`validator` protocols,
not on how those talk to the LLM. **Not implemented in this repo yet** — the
existing extractor/embedder classes are built against `ChatOllama` directly;
adding a vLLM-backed extractor is a follow-up, not a config toggle today.

## What's still hardcoded

Per `Planning/AGENTIC_KG_PIPELINE_PLAN.md`, `IterativeDiscoveryLoop`'s legacy
per-question loop (used when no `module_map` is supplied) and
`pipeline/orchestrator.py`'s `BuildPipeline` still call extractors/validators
directly rather than through tools/skills. These are being migrated one
stage at a time; the tool/skill wrappers above are additive until each
stage has equivalent test coverage.
