# SEMANTiCS 2026-Informed Improvement Plan

**Source**: [local-docs/SEMANTiCS2026-Summary.md](../local-docs/SEMANTiCS2026-Summary.md)
(22nd Int. Conf. on Semantic Systems, Ghent, Sep 2026)
**Status**: Planning only — no implementation in this document. Follows the
same "one stage at a time, tests before rewiring" discipline as
[AGENTIC_KG_PIPELINE_PLAN.md](AGENTIC_KG_PIPELINE_PLAN.md).
**Branch**: `refactor/clean-agent-skills-tools`

---

## 1. Where we already stand relative to the conference's own consensus

The conference's repeated pattern — *decompose → generate → validate with
symbolic tooling → repair*, driven by typed competency questions, with
provenance and human review at every step — is **already our architecture**,
not a new idea to adopt wholesale:

| SEMANTiCS 2026 pattern | Our equivalent | File |
|---|---|---|
| CQs as first-class, typed artifacts (CQ4OE, MASEO, OntoExtend) | `CQType` (SCQ/VCQ/RCQ/FCQ/MpCQ), `ResearchQuestion` | `agents/question_generator.py` |
| Per-module/per-requirement generation subagents (OntoExtend's RAG-scoped extension) | `ModuleExtractionAgent` + `OrchestratorAgent`, scoped by `kg:module` | `agents/module_extraction_agent.py`, `agents/orchestrator_agent.py` |
| Validation-stage consumer for "is this correct/complete" questions | `ValidationAgent` (VCQ-driven) | `agents/validation_agent.py` |
| Symbolic validation cascade (SHACL, rule engines) | `SHACLValidator`, `RulesEngine`, `ConsistencyChecker`, `StaticValidator` (SHACL2FOL/Vampire — more advanced than anything cited at the conference) | `validation/*.py` |
| Heterogeneous/per-task model assignment | `SwarmModelConfig`, `OrchestratorAgent(max_workers=...)` | `agents/swarm_config.py` |
| Human-in-the-loop review | `hitl/` package (gap detection, review workflow, feedback ingestion) | `hitl/*.py` |
| Ontology-agnostic, drift-tolerant design | Ontology read at runtime via Fuseki SPARQL, no hardcoded schema | `storage/ontology.py` |

**What is genuinely missing**, cross-referencing §10.2 of the summary against
this codebase, is the list in §2 below. This plan is scoped to *only* that
gap — it deliberately does not re-litigate things we already do at least as
well as what was presented.

---

## 2. Gap analysis (what's missing, verified against the codebase)

| # | Gap | Evidence it's missing | SEMANTiCS source |
|---|---|---|---|
| G1 | No axiom/entity-level **provenance rationale log** (which agent, which CQ/error/pitfall motivated a change) — we track `Evidence` (source doc + span) but not *why an agent made a decision* | `core/models.Evidence` has `source_type/source_id/text_span/confidence`, no `rationale`/`triggered_by` field; no append-only change log anywhere | MASEO `vaem:rationale` + `dc:source`; Sabou keynote (provenance + continuous auditing) |
| G2 | No **DL consistency reasoner** (disjointness, cardinality contradictions beyond what SHACL shapes encode) | `analytics/inference.py` does forward materialization (symmetry/inverse/transitivity) into Neo4j, not full OWL DL consistency checking; no HermiT/owlready2 dependency in `pyproject.toml` | MASEO's Logical Consistency Agent (HermiT) |
| G3 | No **ontology pitfall detection** (naming clashes, missing inverse, insufficient annotations, etc.) | No equivalent of OOPS! anywhere in `validation/` | MASEO's Pitfall Resolution Agent (OOPS!) |
| G4 | **No repair-agent pattern** — validation failures are reported, nothing loops back to fix them | `ValidationAgent`/`KGValidationSkill` report `valid: bool` + violations; nothing re-invokes extraction/generation with the failure as feedback | MASEO's per-failure-class repair agents |
| G5 | No **CQ→SPARQL functional test** — QA evaluation uses string-similarity matching, not a generated query executed against the KG | `evaluation/query_executor.py::QueryResult.is_correct` uses fuzzy string matching only | CQ4OE's CQCoverage dimension; "functional tests" pattern used everywhere at the conference |
| G6 | **No prompt-diversity + rule-based-validator pattern** for extraction — we run one extraction call per chunk, not N diverse candidates filtered by a cheap validator | `extraction/entity.py`, `extraction/chains.py` — single LCEL chain per call | Ontology-Aware Prompting paper (§3.5): 3-prompt diversity + rule-based filter beat bigger single models |
| G7 | **No CQ-quality coaching** — under-specified CQs are accepted as-is | `question_generator.py` generates questions from ontology gaps; nothing scores/negotiates CQ specificity before use | OntoExtend's stated failure mode: quality degrades sharply on open-ended/underspecified CQs |
| G8 | **No heterogeneous-LLM quorum voting** — `ConsensusVoter` exists but voting is over *sources*, not over *independent models* answering the same extraction | `confidence/voter.py::ConsensusVoter` | HARP: +7.0% F1 from quorum voting over a model ensemble; "no single LLM dominates" |
| G9 | Graph context fed to LLMs during extraction/enrichment is not GraphML-serialized (GraphML export exists but is an *output* format, not used as LLM input context) | `storage/export.py::KGExporter.to_graphml` | GraphRAG Best Practices: GraphML serialization measurably improves LLM quality/latency trade-off vs. ad-hoc text |
| G10 | **No cold-start / scope-revelation UI primitive** — question generation assumes an ontology already exists; nothing helps a user go from "I have a vague need" to a scoped CQ set | N/A (no conversational elicitation layer in this repo — GraphQAAgent may own this, needs cross-repo check) | UKG workshop (McNamara): initial-exploration problem, scope-revelation primitive |

---

## 3. Explicit non-goals (avoid over-engineering)

- **Not building a new benchmark.** CQ4OE's six ontologies don't cover our
  domains, but standing up a competing benchmark is out of scope. Instead:
  adopt CQ4OE's *evaluation dimensions* (§4, below) as internal regression
  metrics, computed against our own ontologies.
- **Not switching RDF triple store, reasoner backend, or LLM framework.**
  Every item below is additive: new tools/agents alongside `SHACLValidator`,
  `RulesEngine`, `ConsistencyChecker`, not replacements.
- **Not building the conversational elicitation workbench itself** (§10.3 of
  the summary — "the missing interactive layer"). That is squarely
  GraphQAAgent/OntologyExtender territory per the three-repo split in this
  project's README. This plan covers what KnowledgeGraphBuilder's KG
  *construction and validation* pipeline should expose so that a future
  conversational layer (in this repo or another) can consume it — e.g. G5
  (CQ→SPARQL tests) and G1 (rationale log) are exactly the primitives such a
  layer would need.
- **Not adopting OOPS! or HermiT as hard runtime dependencies by default.**
  Both are optional, feature-flagged, matching how `StaticValidator`
  (SHACL2FOL/Vampire) is already optional today.

---

## 4. Phased plan

Each phase follows the existing working agreement: implement behind new
tools/skills/agents, cover with mocked unit tests (no live Neo4j/Qdrant/
Ollama/HermiT/OOPS! dependency in unit tests), keep existing call sites
working, do not start phase *n+1* before phase *n* is green.

### Phase A — Provenance & rationale log (G1)

**Why first**: every other phase (repair loops, pitfall resolution, quorum
voting) becomes far more valuable once decisions are explainable, and this is
the cheapest, lowest-risk change — additive fields plus one new small module.

- Extend `core/models.py`: add a `RationaleEntry` dataclass
  (`agent: str`, `action: str`, `reason: str`, `triggered_by: str | None`
  — e.g. a CQ id, a pitfall id, or a SHACL violation id — `timestamp`).
  Add `rationale: list[RationaleEntry]` to `ExtractedEntity` and
  `ExtractedRelation` (default empty list — backward compatible).
- New `kgbuilder/provenance/rationale_log.py`: `RationaleLog` — an
  append-only in-memory/JSONL log keyed by entity/relation id, with
  `record(entity_id, agent, action, reason, triggered_by)` and
  `export_jsonld(base_uri)` producing PROV-O-shaped output
  (`prov:wasGeneratedBy`, `prov:wasDerivedFrom`, `dc:source`) so it composes
  with the existing JSON-LD exporter rather than inventing a new vocabulary.
- Wire `ModuleExtractionAgent`, `ValidationAgent`, and (once built) the
  repair agents from Phase C to call `RationaleLog.record(...)` at each
  decision point.
- Tests: unit tests for `RationaleEntry`/`RationaleLog` round-trip and
  JSON-LD shape; extend existing orchestrator tests to assert a rationale
  entry is recorded per module dispatch.

### Phase B — CQ→SPARQL functional testing (G5)

**Why second**: this closes the loop on whether generated CQs (SCQ/RCQ/VCQ)
actually hold against the KG, which is the functional-test pattern used
everywhere at the conference and directly strengthens `ValidationAgent`.

- New `kgbuilder/evaluation/cq_sparql.py`: `CompetencyQuestionTranslator`
  (LLM-assisted NL question -> SPARQL ASK/SELECT, ontology-guided, reusing
  the existing `OntologyService` for class/property URIs) and
  `CQSparqlRunner` (executes against `RDFStore`/Fuseki, returns
  boolean/bindings + timing).
- New tool `tools/cq_sparql_tool.py` wrapping `CQSparqlRunner.run(cq, store)`.
- Extend `ValidationAgent`/`QuestionValidationSkill` with an optional
  `sparql_runner` so VCQ validation can be backed by an executable query
  instead of only an LLM judgment call — the LLM-judgment path
  (`validate_question`) stays as the default/fallback for CQs that don't
  translate cleanly to SPARQL.
- Regression metric: report **CQCoverage** (fraction of SCQ/VCQ/RCQ
  questions with a passing SPARQL translation) per KG build, following
  CQ4OE's naming so results are comparable across our own runs over time.
- Tests: mock `RDFStore`/Fuseki; verify ASK-query translation + execution
  path and the fallback-to-LLM-judgment path when translation fails.

### Phase C — Validation cascade with repair agents (G2, G3, G4)

**Why third**: builds directly on Phases A (rationale) and B (functional
tests) — every repair now has both "why" and "does it now pass" available.

- New `validation/consistency_reasoner.py`: `ConsistencyReasoner` wrapping
  `owlready2` (bundles HermiT) as an **optional extra**
  (`pip install -e ".[reasoning]"`), mirroring how `StaticValidator` already
  treats SHACL2FOL/Vampire as optional. Exposes
  `check_consistency(ontology_path) -> ConsistencyResult` (consistent: bool,
  unsatisfiable_classes: list[str]).
- New `validation/pitfall_detector.py`: `OOPSPitfallDetector` — thin HTTP
  client for the public OOPS! REST API (no local install), with a
  **local rule-based fallback** for the handful of pitfall checks that are
  cheap to reimplement (e.g. P08 missing annotations, P11 missing
  domain/range) so the pipeline degrades gracefully without network access —
  this also mirrors G6's "rule-based validator" pattern instead of adding a
  second hard external dependency.
- New tools: `tools/consistency_reasoner_tool.py`,
  `tools/pitfall_detector_tool.py`, both following the existing
  `kg_validation_tools.py` pattern (stateless wrapper + `.handler`).
- New `agents/repair_agent.py`: `RepairAgent` — one instance per failure
  class (`SyntaxRepairAgent` isn't needed, we don't hand-author OWL; start
  with `ConsistencyRepairAgent` and `PitfallRepairAgent`), each taking a
  validation failure + `RationaleLog` context and re-invoking the relevant
  extraction/assembly step with the failure as additional prompt context,
  then re-validating. Bounded retry count (default 2, configurable) to avoid
  infinite loops — this is the one new piece of control flow, kept as small
  and inspectable as the existing `ModuleExtractionAgent.run_questions` loop.
- Extend `KGValidationSkill` with an optional `consistency_reasoner` and
  `pitfall_detector` param, following the exact pattern already used for
  `shacl_validator`/`rules_engine`/`consistency_checker` (only runs if
  configured, aggregates into the same `valid` flag).
- Tests: mock owlready2/OOPS! clients; verify repair-agent retry bound,
  rationale logging per repair attempt, and aggregate `valid` flag semantics.

### Phase D — Prompt diversity + rule-based extraction validator (G6)

- Extend `extraction/ensemble.py` (already has `TieredExtractor`/
  `EnsembleExtractor` — this is additive to an existing merge concept, not a
  new architecture): add a `DiverseExtractor` that runs 2–3 differently
  framed prompts per chunk (structured/schema-constrained, relaxed/open,
  and the existing ontology-guided prompt) through the *same* model, then
  filters candidates with a cheap rule-based validator: cross-prompt
  agreement, evidence-span grounding (reuse existing `TextAligner`), surface
  form alignment. This directly reuses `aligner.py` rather than adding new
  grounding logic.
- Gate behind a config flag (`enable_diverse_extraction`, default off) so it
  doesn't change existing extraction behavior/tests by default — evaluate
  its effect on hallucination rate and ontology-conformance before flipping
  the default, per the paper's own ablation methodology.
- Tests: unit test the rule-based filter in isolation (mocked LLM candidates
  with known agreement/disagreement patterns) plus one integration-style
  test exercising `DiverseExtractor` end-to-end with a fake LLM.

### Phase E — Heterogeneous-LLM quorum voting (G8)

- Extend `SwarmModelConfig` (already assigns one model per module) with an
  optional `quorum_models: list[str]` per module for high-stakes
  classification decisions (e.g. disambiguating entity type when confidence
  is low) — reuses the swarm config's existing per-module model resolution,
  just allows more than one model to be consulted for a single decision.
- Extend `confidence/voter.py::ConsensusVoter` with a `vote_across_models`
  path that takes N model outputs for the *same* input (as opposed to today's
  cross-source voting) and applies the same voting mechanism already tested
  there.
- Restrict to low-confidence cases only (configurable threshold) to bound
  the added LLM call cost — quorum voting only pays for itself where HARP
  found it mattered (ambiguous/low-agreement cases), not on every extraction.
- Tests: extend existing `ConsensusVoter` tests with a same-input,
  multi-model scenario.

### Phase F — GraphML context serialization for LLM prompts (G9)

- Add `retrieval/graph_context.py::serialize_subgraph_graphml(entities,
  relations) -> str`, reusing `KGExporter`'s existing GraphML writer logic
  (extract the node/edge XML building into a shared helper both
  `KGExporter.to_graphml` and this function call, rather than duplicating it).
- Use this when assembling extraction/enrichment prompts that need to show
  the LLM already-known related entities (e.g. coreference resolution,
  relation extraction domain/range context) instead of today's ad-hoc
  text/dict formatting.
- Tests: snapshot test comparing GraphML output for a small fixed
  entity/relation set; before/after extraction-quality comparison is a
  manual eval, not a unit test (matches the paper's own methodology — this
  is a prompt-formatting change, not a correctness change).

### Phase G — CQ-quality coaching (G7) *(exploratory, lowest priority)*

- New `agents/cq_coach_agent.py`: scores each generated `ResearchQuestion`
  for specificity (heuristics: length, presence of a concrete entity/relation
  reference, absence of vague quantifiers) and, for questions below
  threshold, either (a) drops them from the extraction batch with a
  rationale-logged reason, or (b) attempts one LLM-assisted rewrite pass
  before re-scoring. Kept simple and heuristic-first per this plan's
  non-goals — this is *not* the conversational elicitation workbench, just a
  quality gate on questions this repo already generates.
- Tests: table-driven tests over hand-picked good/bad CQ examples.

---

## 5. Priority and sequencing

| Phase | Priority | Rough size | Depends on |
|---|---|---|---|
| A — Rationale log | High | Small | — |
| B — CQ→SPARQL tests | High | Medium | A (for logging translation failures) |
| C — Validation cascade + repair agents | High | Large | A, B |
| D — Prompt diversity + rule validator | Medium | Medium | — (independent, can run parallel to A–C) |
| E — Quorum voting | Medium | Small | D helpful but not required |
| F — GraphML prompt context | Low | Small | — (independent) |
| G — CQ coaching | Low (exploratory) | Small | B (reuses SPARQL-translatability as one specificity signal) |

Recommended order: **A → B → C**, with **D** picked up opportunistically in
parallel since it touches a different subsystem (`extraction/`) than A–C
(`provenance/`, `validation/`, `agents/`). **E, F, G** are independent
follow-ups once A–D are stable.

---

## 6. New optional dependencies (all feature-flagged, none required by default)

| Dependency | Used by | Install extra |
|---|---|---|
| `owlready2` | Phase C consistency reasoning (HermiT) | `pip install -e ".[reasoning]"` |
| none (HTTP client only, `requests`/`httpx` already available transitively) | Phase C OOPS! pitfall detection | — |

No new required dependency changes `pyproject.toml`'s default install.

---

## 7. Cross-references

- Full conference notes: [local-docs/SEMANTiCS2026-Summary.md](../local-docs/SEMANTiCS2026-Summary.md)
- Current agentic architecture this plan builds on: [AGENTIC_KG_PIPELINE_PLAN.md](AGENTIC_KG_PIPELINE_PLAN.md)
- Validation architecture this plan extends: [VALIDATION_PLAN.md](VALIDATION_PLAN.md)
- Agent/skill/tool design reference: [docs/architecture/agentic-pipeline.md](../docs/architecture/agentic-pipeline.md)
