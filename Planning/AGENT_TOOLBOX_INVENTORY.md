# Agent, Subagent, Skill & Tool Inventory

**Purpose**: a single reference for everything the KnowledgeGraphBuilder
agentic pipeline can currently do — every subagent, every skill, every tool,
how they compose, and what's planned next. Written for onboarding and for
scoping new work without re-deriving the architecture from source each time.

**Status as of this document**: branch `feat/semantics2026-phase-a-provenance`
(based on `refactor/clean-agent-skills-tools`). Reflects code in the tree,
including uncommitted Phase A (provenance/rationale log) and Phase B
(CQ→SPARQL functional testing) work.

**Related documents**:
- [docs/architecture/agentic-pipeline.md](../docs/architecture/agentic-pipeline.md) — design rationale for the skill/tool/subagent split and CQType routing
- [AGENTIC_KG_PIPELINE_PLAN.md](AGENTIC_KG_PIPELINE_PLAN.md) — migration history and status (Phases 1–3 done)
- [SEMANTICS2026_IMPROVEMENT_PLAN.md](SEMANTICS2026_IMPROVEMENT_PLAN.md) — gap analysis and forward plan (Phases A–G), with source attribution

---

## 1. The three layers

```
Agent (BaseAgent subclass)
  │  holds resources (retriever, extractor, validator, model, ontology module...)
  │  exposes skills as callable methods
  ▼
Skill (AgentSkill dataclass, kgbuilder.skills)
  │  composes one or more tools into a bounded unit of work
  │  ("retrieve, then extract"; "retrieve, then validate")
  ▼
Tool (AgentTool dataclass, kgbuilder.tools)
     stateless wrapper around one existing capability
     (extractor.extract(...), validator.validate(...), a retriever call, ...)
```

- **`AgentTool`** (`tools/base.py`): `name`, `description`, `parameters` (JSON
  schema, informational for LLM tool-calling), `handler` (a plain callable).
  `.execute(**kwargs)` calls `handler(**kwargs)`. No framework dependency.
- **`AgentSkill`** (`skills/base.py`): `name`, `description`, `handler`. Same
  shape as a tool, but its handler typically calls one or more tools'
  `.handler` functions in sequence.
- **`BaseAgent`** (`agents/base_agent.py`): holds `skills: list[AgentSkill]`
  and `tools: list[AgentTool]`, exposes `run_skill(name, **kwargs)` /
  `run_tool(name, **kwargs)` by name lookup, and an abstract `run(prompt,
  **kwargs)` every concrete agent must implement. `LangChainReactAgent`
  (same file) is an alternate concrete agent that wraps the same tools as
  LangChain `Tool` objects and drives them via LangChain 1.x's
  `create_agent` (LangGraph tool-calling loop) instead of a hardcoded
  `run()` — used where an LLM should choose which tool to call, as opposed
  to the deterministic subagents below which always call the same
  skill/tool in a fixed order.

This mirrors how a LangChain/LangGraph tool-calling agent is structured, but
every non-`LangChainReactAgent` piece works as plain Python — the LLM is
only invoked *inside* extractor/validator implementations, not to drive
control flow itself.

---

## 2. Subagents (concrete `BaseAgent` implementations)

### 2.1 `QuestionGenerationAgent` — `agents/question_generator.py`

Generates prioritized `ResearchQuestion`s from ontology coverage gaps.

- **Skills used**: `ontology_gap_analysis` (initial questions from
  under-covered classes), `follow_up_gap_analysis` (new questions once a
  discovery pass finds new entity types).
- **Tools used**: `ontology_query` (class hierarchy/relations/description
  lookups), `coverage_snapshot` (which classes are under-covered right now).
- **Key type — `CQType`** (Keet & Khan's QuO model, arXiv:2412.13688): every
  `ResearchQuestion.cq_type` is one of:
  | CQType | Meaning | Consumed by |
  |---|---|---|
  | **SCQ** (Scoping) | "What exists?" | `ModuleExtractionAgent` |
  | **RCQ** (Relationship) | "How do things relate?" | `ModuleExtractionAgent` |
  | **VCQ** (Validating) | "Is the KG correct/complete?" | `ValidationAgent` |
  | **FCQ** (Foundational) | Align to CCO/BFO | *(not yet wired)* |
  | **MpCQ** (Metaproperty) | Rigidity/identity classification | *(not yet wired)* |

### 2.2 `ModuleExtractionAgent` — `agents/module_extraction_agent.py`

Scoped to exactly **one ontology module** (e.g. "Radiological
Characterization", grouped via the ontology's `kg:module` annotation). Holds
that module's class definitions and its own retriever/extractor pair
(different modules may use different, e.g. smaller/cheaper, models).

- **Skill used**: `module_extraction` (retrieve → extract for one question).
- **Filters** incoming questions to `EXTRACTION_CQ_TYPES = {SCQ, RCQ}` —
  VCQ/FCQ/MpCQ are skipped (routed elsewhere).
- **`run_questions(questions)`**: runs extraction per question, accumulating
  `existing_entities` across questions within the module for dedup context.
- **Provenance (Phase A)**: optional `rationale_log: RationaleLog` — when
  supplied, every extracted entity gets a `RationaleEntry` recorded
  (`agent=self.name`, `action="extracted"`, `reason="matched module '<name>'
  for question: <text>"`, `triggered_by=question_id`).

### 2.3 `OrchestratorAgent` — `agents/orchestrator_agent.py`

Builds and runs one `ModuleExtractionAgent` per ontology module, concurrently,
then merges their outputs.

- **`ModuleBinding`** dataclass: `module_name`, `ontology_classes`,
  `retriever`, `extractor`, `questions`, `top_k` — everything one module
  subagent needs.
- **`build_module_bindings(module_map, questions, retriever, extractor,
  top_k)`** *(static)*: assigns each question to the module(s) owning its
  `entity_class` (via `OntologyService.get_module_class_map()`), with a
  safe fallback to the first module for unmapped classes.
- **`run_modules(bindings, parallel=True)`**: instantiates one
  `ModuleExtractionAgent` per binding, runs them via `ThreadPoolExecutor`
  (`max_workers`, default 3) or sequentially, then merges results with the
  **`join_module_results`** skill.
- **Skill used**: `join_module_results`.

### 2.4 `ValidationAgent` — `agents/validation_agent.py`

Consumes **VCQ** questions: for each one, checks whether existing KG content
answers it correctly/completely. Two validation strategies, tried in order:

1. **SPARQL functional test** (Phase B, preferred when configured): if
   `sparql_translator`, `sparql_runner`, and `rdf_store` are all supplied,
   translates the question to SPARQL and executes it against the RDF store
   via the `question_validation_sparql` skill. Used only when translation
   succeeds (`translation.sparql is not None`).
2. **LLM-judgment fallback** (original path, always available): retrieves
   evidence and asks a validator via the `question_validation` skill. Used
   when SPARQL isn't configured, or a question doesn't translate cleanly.

- **Skills used**: `question_validation_sparql`, `question_validation`.
- **Filters** to `VALIDATION_CQ_TYPES = {VCQ}`.
- **Provenance (Phase A)**: optional `rationale_log` — records one
  `RationaleEntry` per validated question, keyed by `question_id`
  (`action="validated"`, `reason` notes *which* method was used —
  `"VCQ validation via sparql functional test: ..."` or
  `"... via LLM judgment: ..."` — plus the result, `triggered_by=question_id`),
  via `RationaleLog.record_for_id` (question outcomes aren't
  `ExtractedEntity`/`ExtractedRelation` objects, so they're keyed by plain id
  rather than attached to an object's `.rationale` list).

### 2.5 `IterativeDiscoveryLoop` — `agents/discovery_loop.py`

The top-level driver. Not itself a `BaseAgent` (it's the orchestration entry
point that owns a `QuestionGenerationAgent`, an `OrchestratorAgent`, and
optionally a `ValidationAgent`).

- Generates initial questions (or accepts a supplied list), splits every
  batch (initial + every follow-up round) by `cq_type`:
  - SCQ/RCQ → `OrchestratorAgent.build_module_bindings` +
    `run_modules` (module orchestration path) **when a `module_map` is
    supplied**; otherwise falls back to the legacy fixed per-question loop
    (retrieve → extract → extract relations → optional static validation —
    still hardcoded, tracked as a future migration stage).
  - VCQ → `ValidationAgent.run_questions`, results collected on
    `DiscoveryResult.validation_results`.
- Generates follow-up questions each iteration (`generate_follow_up_questions`
  skill on `QuestionGenerationAgent`) until coverage target or max
  iterations is reached.
- Nothing is silently dropped: every question type has an explicit
  destination (extraction, validation, or "not yet wired").

### 2.6 `PipelineAgent` — `agents/pipeline_agent.py`

Declarative alternative to a hardcoded call sequence: runs an ordered
`list[PipelineStep]` (`skill` name + `kwargs` + `bind` mapping of kwarg name
→ a resource supplied at construction time, e.g. `{"retriever": "retriever"}`).
Exposes the **entire skill/tool registry** (`ALL_SKILLS`, `ALL_TOOLS` from
`agents/registry.py`), not a fixed subset — any registered skill can appear
in a plan. Plans can be authored in Python or loaded from markdown (below).

### 2.7 Markdown-driven plans — `agents/markdown_pipeline.py`

Lets a plan be edited as `.md` files instead of Python:
- `agentic_pipeline/skills/<name>.md`: YAML front matter (`name`, `tool`
  mapping, `requires_binding`, `default_kwargs`) + a prose description body
  (used as the tool/skill description for LLM-driven planning).
- `agentic_pipeline/pipeline.md`: YAML front matter with an ordered `steps`
  list (`skill` + `kwargs` + `bind`), validated against `SKILL_REGISTRY` at
  load time (unknown skill names, missing bindings, and malformed YAML all
  raise `MarkdownPipelineError`).
- `load_pipeline(path)` → `list[PipelineStep]` ready for
  `PipelineAgent.run_plan(...)`.

### 2.8 `LangChainReactAgent` — `agents/base_agent.py`

The one agent in the stack that lets an **LLM** choose which tool to call
and in what order (LangChain 1.x `create_agent` / LangGraph tool-calling
loop), rather than a fixed Python `run()` method. Wraps the same
`AgentTool`s as LangChain `Tool` objects. Used where the calling order isn't
knowable ahead of time; every other agent above is deterministic.

### 2.9 `SwarmModelConfig` + `build_module_bindings_with_swarm_config` — `agents/swarm_config.py`

Not an agent itself — configuration for **how many models** the module
swarm uses and **which module gets which model**:
- `backend` ("ollama" | "vllm", informational), `base_url`, `default_model`,
  `module_models: dict[str, str]` (per-module override), `max_concurrent_agents`
  (→ `OrchestratorAgent(max_workers=...)`), `request_timeout_s`.
- `build_module_bindings_with_swarm_config(...)` builds one retriever/
  extractor pair **per distinct model** (via caller-supplied factory
  callables) and shares it across all modules assigned that model, then
  returns `ModuleBinding`s exactly like `OrchestratorAgent.build_module_bindings`.
- Example config: `data/profiles/agent_swarm.example.json`.
- `experiment.config.KGBuilderParams.swarm_config_path` lets experiment/
  benchmark variants reference one (optional, backward compatible).

---

## 3. Skills (`kgbuilder/skills/`)

| Skill name | File | Composes | Purpose |
|---|---|---|---|
| `ontology_gap_analysis` | `ontology_gap_analysis.py` | `QuestionGenerationAgent.generate_questions` | Identify under-covered ontology classes, return priority-ranked questions |
| `follow_up_gap_analysis` | `follow_up_gap_analysis.py` | `QuestionGenerationAgent.generate_follow_up_questions` | Generate follow-up questions once new entity types are found |
| `module_extraction` | `module_extraction_skill.py` | `document_retrieval` tool → `entity_extraction` tool | Retrieve docs for one question, then extract entities scoped to one module's classes |
| `join_module_results` | `join_skill.py` | (pure merge logic) | Dedupe entities across modules by `(label, entity_type)`, keep highest confidence, merge evidence |
| `question_validation` | `question_validation_skill.py` | `document_retrieval` tool → `kg_content_validation` tool | Retrieve evidence for a VCQ question, then validate KG content against it (LLM judgment) |
| `question_validation_sparql` | `question_validation_skill.py` | `cq_sparql_test` tool | Translate a VCQ question to SPARQL and execute it as a functional test *(Phase B, new)* |
| `kg_validation` | `kg_validation_skill.py` | `shacl_validation` + `rules_engine_validation` + `consistency_check` tools | Post-assembly validation: run whichever of SHACL/rules/consistency checkers are configured, aggregate to one `valid` flag |
| `semantic_enrichment` | `enrichment_skill.py` | `semantic_enrichment` tool | 5-phase enrichment (descriptions, embeddings, CQs, type scores, aliases) |
| `document_retrieval` | `retrieval_skill.py` | `document_retrieval` tool | Retrieve documents for a query |
| `retrieval_evaluation` | `retrieval_skill.py` | `retrieval_evaluation` tool | Score retrieval quality (recall/precision/NDCG/MRR) vs. ground truth |
| `law_linking` | `linking_skill.py` | `law_linking` tool | Cross-domain link KG entities to German law graph nodes |
| `law_context_lookup` | `linking_skill.py` | `law_context_lookup` tool | Retrieve relevant law paragraph context to augment extraction |

---

## 4. Tools (`kgbuilder/tools/`)

| Tool name | File | Wraps | Purpose |
|---|---|---|---|
| `entity_extraction` | `extraction_tool.py` | any `EntityExtractor.extract` | Extract entities from text guided by ontology classes |
| `relation_extraction` | `relation_extraction_tool.py` | any `RelationExtractor.extract` | Extract relations between known entities guided by ontology relation defs |
| `document_retrieval` | `retrieval_tool.py` | any `Retriever.retrieve` | Retrieve top-k documents relevant to a query |
| `retrieval_evaluation` | `evaluation_tool.py` | `retrieval.evaluation.evaluate_retrieval` | Compute recall@k/precision@k/NDCG/MRR |
| `kg_content_validation` | `validation_tool.py` | any `validator.validate_question` | Check whether KG content answers a VCQ question (LLM judgment) |
| `cq_sparql_test` | `cq_sparql_tool.py` | `CQSparqlRunner.translate_and_run` | Translate a competency question to SPARQL and execute it as a functional test *(Phase B, new)* |
| `static_validation` | `static_validation_tool.py` | `StaticValidator.validate_entities_and_relations` (SHACL2FOL/Vampire) | Pre-commit check: would adding these entities/relations preserve SHACL validity |
| `shacl_validation` | `kg_validation_tools.py` | `SHACLValidator.validate` | Validate KG against SHACL shapes |
| `rules_engine_validation` | `kg_validation_tools.py` | `RulesEngine.execute_rules` | Execute semantic rules (transitive/symmetric/functional/inverse) |
| `consistency_check` | `kg_validation_tools.py` | `ConsistencyChecker.check_consistency` | Detect type/value conflicts and duplicate entities |
| `semantic_enrichment` | `enrichment_tool.py` | `SemanticEnrichmentPipeline.enrich` | Run the 5-phase enrichment pipeline |
| `ontology_query` | `ontology_query.py` | `OntologyService` (hierarchy/relations/description) | Inspect ontology metadata for a class |
| `coverage_snapshot` | `coverage_snapshot.py` | `QuestionGenerationAgent._calculate_coverage` | Current ontology coverage + under-covered classes |
| `law_linking` | `law_linking_tool.py` | `KGLawLinker.create_links` | Create cross-domain `LINKED_*` relationships to law graph nodes |
| `law_context_lookup` | `law_linking_tool.py` | `LawContextProvider.get_context` | Retrieve relevant German law paragraph context for a chunk |

All tools follow the same shape: a module-level `_xxx_handler(...)` function
plus an `AgentTool(name=..., description=..., parameters=<JSON schema>,
handler=_xxx_handler)` instance. None import LangChain or any LLM client
directly — they wrap whatever object is passed in (`extractor`, `validator`,
`retriever`, ...), so the same tool works against a mock in unit tests or a
real Ollama-backed implementation in production.

---

## 5. Provenance layer — `kgbuilder/provenance/` *(Phase A, new)*

Closes the "why is this axiom/entity here?" gap: `Evidence` (on
`ExtractedEntity`/`ExtractedRelation`) grounds a **fact** in source text;
`RationaleLog` records **why an agent made a decision** about that fact.

- **`core/models.RationaleEntry`** (dataclass): `agent`, `action`, `reason`,
  `triggered_by` (optional — a CQ id, SHACL violation id, OOPS! pitfall id,
  ...), `timestamp` (auto-set, UTC ISO 8601).
- **`ExtractedEntity.rationale`** / **`ExtractedRelation.rationale`**:
  `list[RationaleEntry]`, default empty — additive, backward compatible.
- **`provenance/rationale_log.py::RationaleLog`**: append-only, keyed by
  subject id.
  - `record(subject, agent, action, reason, triggered_by=None)` — for
    `ExtractedEntity`/`ExtractedRelation` objects; appends to both the log's
    own index and `subject.rationale`.
  - `record_for_id(subject_id, agent, action, reason, triggered_by=None)` —
    for decisions not tied to an entity/relation object (e.g. a VCQ
    question's validation outcome).
  - `entries_for(subject_id)` → `list[RationaleEntry]`.
  - `export_jsonld(base_uri)` → PROV-O/VAEM/Dublin-Core-shaped JSON-LD
    (`prov:wasGeneratedBy`, `prov:generatedAtTime`, `dc:source`,
    `vaem:rationale`), so the log composes with the existing JSON-LD
    exporter (`storage/export.py`) instead of inventing a new vocabulary.
- **Wired into**: `ModuleExtractionAgent` (records `action="extracted"` per
  entity) and `ValidationAgent` (records `action="validated"` per VCQ
  question) via an optional `rationale_log: RationaleLog | None` constructor
  param — `None` by default, so existing call sites are unaffected until a
  caller opts in.
- **Attribution**: this design is modeled directly on **MASEO**'s per-axiom,
  agent-attributed, append-only provenance (`vaem:rationale` + `dc:source`);
  see [SEMANTICS2026_IMPROVEMENT_PLAN.md §8](SEMANTICS2026_IMPROVEMENT_PLAN.md#8-attribution--sources)
  for full citations.

---

## 5b. CQ→SPARQL functional testing — `kgbuilder/evaluation/cq_sparql.py` *(Phase B, new)*

Checks "does the KG answer this CQ?" by **executing a query**, not only by
an LLM judgment call — the functional-test pattern used throughout SEMANTiCS
2026 (CQ4OE, MASEO).

- **`CompetencyQuestionTranslator.translate(question) -> CQSparqlTranslation`**:
  any `LLMProvider`-shaped `generate(prompt) -> str` translates a
  `ResearchQuestion` into a SPARQL ASK/SELECT query; ontology-guided (resolves
  `question.entity_class` to a class URI hint via `OntologyService`).
  `sparql=None` + `translation_error` set (not an exception) when the LLM
  declines or the call fails — "not translatable" is a normal outcome.
- **`CQSparqlRunner.run(translation, store) -> CQSparqlResult`**: executes
  against any `RDFStore`-shaped `query_sparql(sparql) -> dict`. ASK →
  boolean `passed`; SELECT → `passed = len(bindings) > 0`.
  `translate_and_run(question, store, translator)` combines both steps.
- **`compute_cq_translation_coverage(results) -> float`**: fraction of
  results with a successful translation — named **CQCoverage** to match
  CQ4OE's evaluation-dimension naming for cross-run comparability.
- **Tool**: `tools/cq_sparql_tool.py::CQSparqlTool`. **Skill**:
  `skills/question_validation_skill.py::SparqlQuestionValidationSkill`
  (`question_validation_sparql`).
- **Wired into `ValidationAgent`**: optional `sparql_translator`,
  `sparql_runner`, `rdf_store` constructor params. When all three are set,
  each VCQ question is tried as a SPARQL functional test first; falls back
  to the LLM-judgment `question_validation` skill only when translation
  doesn't produce a usable query. Rationale entries (§5) note which method
  was used.
- **Attribution**: `CQCoverage` naming and the CQ-to-SPARQL functional-test
  pattern come from **CQ4OE** (OEG-UPM) and **MASEO**'s validation cascade;
  full citations in the module docstring and
  [SEMANTICS2026_IMPROVEMENT_PLAN.md §8](SEMANTICS2026_IMPROVEMENT_PLAN.md#8-attribution--sources).

---

## 6. How a full discovery iteration composes (call graph)

```
IterativeDiscoveryLoop.run_discovery()
 │
 ├─ QuestionGenerationAgent.generate_questions()          [ontology_gap_analysis skill]
 │    └─ ontology_query tool, coverage_snapshot tool
 │
 ├─ split questions by CQType
 │
 ├─ SCQ/RCQ ──► OrchestratorAgent.build_module_bindings() + run_modules()
 │                 └─ per module: ModuleExtractionAgent.run_questions()
 │                       └─ module_extraction skill
 │                             └─ document_retrieval tool ─► entity_extraction tool
 │                       └─ (optional) RationaleLog.record() per entity
 │                 └─ join_module_results skill (cross-module dedup)
 │
 ├─ VCQ ──► ValidationAgent.run_questions()
 │             ├─ (if SPARQL configured) question_validation_sparql skill
 │             │     └─ cq_sparql_test tool (translate → execute against RDF store)
 │             ├─ (fallback) question_validation skill
 │             │     └─ document_retrieval tool ─► kg_content_validation tool
 │             └─ (optional) RationaleLog.record_for_id() per question, notes method used
 │
 ├─ QuestionGenerationAgent.generate_follow_up_questions()  [follow_up_gap_analysis skill]
 │    (repeat split + dispatch above, until coverage target / max iterations)
 │
 ▼
DiscoveryResult(entities, relations, validation_results, iterations, ...)

(separately, post-assembly)
KGValidationSkill  ──►  shacl_validation + rules_engine_validation + consistency_check tools
```

---

## 7. What's still hardcoded (not yet agentic)

Per `AGENTIC_KG_PIPELINE_PLAN.md`:
- `IterativeDiscoveryLoop`'s **legacy per-question loop** (used only when no
  `module_map` is supplied) still calls retriever → extractor → relation
  extractor → static validator directly, not through skills/tools.
- `pipeline/orchestrator.py`'s `BuildPipeline` still calls
  SHACL/rules/consistency validation directly rather than via
  `KGValidationSkill`.
- Document preprocessing/indexing (loading, chunking, embedding into
  Qdrant) is **explicitly out of scope** for agentic conversion — I/O-heavy
  and deterministic, not a good fit.
- Assembly (`assembly/*.py`) has no skill/tool wrapper yet (migration stage
  2, not started).

## 8. What's planned next (not yet built)

Full detail and priority order in
[SEMANTICS2026_IMPROVEMENT_PLAN.md](SEMANTICS2026_IMPROVEMENT_PLAN.md):

| Phase | Adds | Status |
|---|---|---|
| A — Rationale log | §5 above | **Done** |
| B — CQ→SPARQL functional testing | §5b above | **Done** |
| C — Validation cascade + repair agents | `validation/consistency_reasoner.py` (HermiT via owlready2), `validation/pitfall_detector.py` (OOPS!), `agents/repair_agent.py` | Not started |
| D — Prompt diversity + rule-based extraction validator | `extraction/ensemble.py::DiverseExtractor` | Not started |
| E — Heterogeneous-LLM quorum voting | `SwarmModelConfig.quorum_models`, `ConsensusVoter.vote_across_models` | Not started |
| F — GraphML LLM context serialization | `retrieval/graph_context.py` | Not started |
| G — CQ-quality coaching | `agents/cq_coach_agent.py` | Not started (exploratory) |

---

## 9. Quick-reference: full name list

**Agents/subagents**: `QuestionGenerationAgent`, `ModuleExtractionAgent`,
`OrchestratorAgent`, `ValidationAgent`, `PipelineAgent`, `LangChainReactAgent`,
`IterativeDiscoveryLoop` (driver, not a `BaseAgent`).

**Skills** (12): `ontology_gap_analysis`, `follow_up_gap_analysis`,
`module_extraction`, `join_module_results`, `question_validation`,
`question_validation_sparql`, `kg_validation`, `semantic_enrichment`,
`document_retrieval`, `retrieval_evaluation`, `law_linking`,
`law_context_lookup`.

**Tools** (14): `entity_extraction`, `relation_extraction`,
`document_retrieval`, `retrieval_evaluation`, `kg_content_validation`,
`cq_sparql_test`, `static_validation`, `shacl_validation`,
`rules_engine_validation`, `consistency_check`, `semantic_enrichment`,
`ontology_query`, `coverage_snapshot`, `law_linking`, `law_context_lookup`
*(note: `semantic_enrichment`, `document_retrieval`, `retrieval_evaluation`,
`law_linking`, `law_context_lookup` each have both a skill and a
same-named/thin-wrapper tool — the skill is the one composable unit
`PipelineAgent`/markdown plans reference; the tool is what it calls)*.

**Config**: `SwarmModelConfig` (per-module model + concurrency).

**Provenance**: `RationaleEntry`, `RationaleLog`.

**CQ→SPARQL evaluation**: `CompetencyQuestionTranslator`, `CQSparqlTranslation`,
`CQSparqlRunner`, `CQSparqlResult`, `compute_cq_translation_coverage`.
