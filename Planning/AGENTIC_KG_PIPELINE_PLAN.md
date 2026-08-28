# Agentic KG-Building Pipeline — Migration Plan

**Status**: Phase 1 (foundation) complete. Phases 2–6 not yet started.
**Branch**: `refactor/clean-agent-skills-tools` (based on `main`)
**Scope boundary** (explicit, do not expand):
- Document preprocessing/indexing (loading, chunking, embedding into Qdrant) **stays a
  hardcoded pipeline**. It is I/O-heavy, deterministic, and not a good fit for
  agentic control.
- Everything from "what to look for next" onward — question generation,
  retrieval, extraction, enrichment, validation, assembly, law linking — becomes
  **agentic**: composed from `AgentTool`/`AgentSkill` building blocks, orchestrated
  by an agent instead of a hardcoded call sequence.
- The pipeline's behavior must be tweakable **in natural language** by editing
  markdown files, without touching Python.

---

## 1. Architecture overview

```
src/kgbuilder/
  tools/        # atomic, stateless capabilities (AgentTool) — one per module wrapped
  skills/       # composed capabilities (AgentSkill) — what an agent can be asked to do
  agents/
    base_agent.py     # BaseAgent + LangChainReactAgent (LangChain 1.x create_agent)
    registry.py        # SKILL_REGISTRY / TOOL_REGISTRY — single source of truth
    pipeline_agent.py  # declarative PipelineAgent, runs an ordered plan of skills
    markdown_pipeline.py  # loads skills/*.md + pipeline.md into PipelineStep objects
    question_generator.py, discovery_loop.py  # being migrated onto BaseAgent
agentic_pipeline/        # NEW: markdown skill + pipeline definitions (human/LLM-editable)
  skills/<skill_name>.md
  pipeline.md
```

Already implemented (Phase 1, this session):
- `kgbuilder.skills.base.AgentSkill`, `kgbuilder.tools.base.AgentTool` — minimal dataclasses with `.execute(**kwargs)`.
- `kgbuilder.agents.base_agent.BaseAgent` — generic `run_skill`/`run_tool` registry, abstract `run()`.
- `kgbuilder.agents.base_agent.LangChainReactAgent` — wraps our tools as LangChain `Tool`s and drives them via `langchain.agents.create_agent` (LangGraph tool-calling loop; the legacy `AgentExecutor`/`create_react_agent` API was removed in LangChain 1.x).
- `QuestionGenerationAgent` now subclasses `BaseAgent`; its skills/tools are bound instances of shared, reusable skill/tool definitions (`ontology_gap_analysis`, `follow_up_gap_analysis`, `ontology_query`, `coverage_snapshot`).
- Facade tools/skills wrapping **existing, untouched** implementations:
  - `semantic_enrichment` → `SemanticEnrichmentPipeline.enrich`
  - `document_retrieval` → any `Retriever.retrieve`
  - `retrieval_evaluation` → `kgbuilder.retrieval.evaluation.evaluate_retrieval`
  - `law_linking` → `KGLawLinker.create_links`
  - `law_context_lookup` → `LawContextProvider.get_context`
- `kgbuilder.agents.registry` — `SKILL_REGISTRY`/`TOOL_REGISTRY`, `get_skill()`/`get_tool()`.
- `kgbuilder.agents.pipeline_agent.PipelineAgent` — runs a `list[PipelineStep]` plan, resolving bound resources (retriever, enrichment pipeline, linker, ...) by name instead of hardcoding call order.
- Tests: `tests/unit/test_base_agent.py`, `tests/unit/test_agent_tool_skill_facades.py`, extended `tests/unit/test_question_generator.py`. All green; 4 pre-existing unrelated failures confirmed present on `main` too (SHACL/evaluation edge cases).

Deliberately **not** rewritten yet: internals of `enrichment/`, `retrieval/`, `linking/`, `validation/`, `assembly/`, `discovery_loop.py`. They are wrapped, not replaced — this keeps the large existing test surface valid while the orchestration layer above them changes.

---

## 2. Markdown-driven skills and pipeline (Phase 2 — this session)

Goal: a domain expert can change *what the agent does and in what order* by
editing `.md` files, without touching Python.

### 2.1 `agentic_pipeline/skills/<name>.md` format

```markdown
---
name: document_retrieval
tool: document_retrieval        # maps to TOOL_REGISTRY key
requires_binding: [retriever]    # resource names PipelineAgent must supply
---

Retrieve the top-k documents relevant to the current research question.
Use this before extraction so the extractor has grounded source text.
```

- YAML front matter is machine-readable (skill/tool name, required bindings,
  default kwargs).
- The prose body is the **natural-language description** — this is what gets
  fed to an LLM-driven planner/ReAct agent as the tool description, and what a
  human edits to change agent behavior (e.g. "only retrieve German-language
  sources", "prefer law paragraphs over technical manuals").

### 2.2 `agentic_pipeline/pipeline.md` format

```markdown
---
steps:
  - skill: ontology_gap_analysis
    kwargs: {max_questions: 20}
  - skill: document_retrieval
    bind: {retriever: retriever}
    kwargs: {top_k: 10}
  - skill: semantic_enrichment
    bind: {pipeline: enrichment_pipeline}
  - skill: retrieval_evaluation
    kwargs: {}
---

# KG Build Pipeline

Ordered plan the `PipelineAgent` executes for one discovery iteration.
Edit the `steps` list to reorder, add, or remove stages — no code changes
required. Each `skill` must exist in `skills/*.md` and the skill registry.
```

### 2.3 Loader

`kgbuilder/agents/markdown_pipeline.py`:
- `load_pipeline(path) -> list[PipelineStep]` — parses YAML front matter,
  validates each `skill` exists in `SKILL_REGISTRY`, returns
  `PipelineAgent`-ready steps.
- `load_skill_doc(path) -> SkillDoc` — parses a single skill markdown file,
  used to (a) validate `pipeline.md` references and (b) generate tool/skill
  descriptions for LLM-driven planning instead of hardcoding description
  strings in Python.
- Validation errors are explicit (unknown skill name, missing binding,
  malformed YAML) since these files are meant to be edited by non-engineers.
- Implemented: `agentic_pipeline/skills/*.md` (7 skill docs matching the
  Phase 1 registry) and `agentic_pipeline/pipeline.md` (one discovery
  iteration expressed declaratively). Covered by
  `tests/unit/test_markdown_pipeline.py`.

This phase's outputs are consumed by `PipelineAgent.run_plan(...)` exactly
like the Python-constructed steps from Phase 1 — the loader only changes
*where the plan comes from*, not how it executes.

---

## 3. Migration stages for the KG-building pipeline itself

Each stage below turns one more hardcoded call site into a tool/skill the
`PipelineAgent` (or a `LangChainReactAgent`) invokes, and keeps the existing
call sites working via thin delegation until the old call site is deleted.

1. **Discovery loop** (`agents/discovery_loop.py`): today `IterativeDiscoveryLoop`
   directly calls retriever → extractor → relation extractor → static
   validator in a fixed order per question. Turn `entity_extraction`,
   `relation_extraction`, and `static_validation` into tools; express one
   discovery iteration as a `pipeline.md` plan; keep `IterativeDiscoveryLoop`
   as a thin compatibility wrapper calling `PipelineAgent.run_plan(...)`.
2. **Assembly** (`assembly/*.py`): wrap `KGAssembler.assemble` /
   `SimpleKGAssembler` phases (dedup, store, stats) as tools; add an
   `assembly` skill.
3. **Validation** (`validation/*.py`): wrap SHACL validation, rules engine,
   and consistency checker as tools; add a `validation` skill used after
   assembly.
4. **Enrichment**: already wrapped (Phase 1) — extend to expose each of the 5
   enrichers individually as tools so `pipeline.md` can include/exclude
   phases without code changes.
5. **Law linking**: already wrapped (Phase 1) — add a skill combining
   `law_context_lookup` (pre-extraction context) and `law_linking`
   (post-assembly cross-linking) into the discovery-loop plan.
6. **Full pipeline swap**: once stages 1–5 are covered by tools/skills and the
   markdown loader exists, replace the hardcoded call sequence in
   `pipeline/orchestrator.py` / `BuildPipeline` with a `PipelineAgent` driven
   by `pipeline.md`. Old orchestrator logic is deleted only after the
   `PipelineAgent` path has equivalent test coverage and passes an end-to-end
   smoke test against `data/smoke_test/`.

Preprocessing/indexing (`document/loaders/*`, `document/chunking/*`,
embedding into Qdrant) is explicitly **out of scope** and stays as-is.

---

## 4. Working agreement for this migration

- One stage at a time, in the order above; do not start stage *n+1* before
  stage *n*'s tests are green.
- Never delete or rewrite an existing hardcoded implementation until its
  tool/skill wrapper has equivalent test coverage.
- Every new tool/skill gets a unit test using mocks — no live Neo4j/Qdrant/
  Ollama dependency in unit tests.
- All work happens on `refactor/clean-agent-skills-tools`; `main` stays
  untouched until the branch is reviewed and merged deliberately.
