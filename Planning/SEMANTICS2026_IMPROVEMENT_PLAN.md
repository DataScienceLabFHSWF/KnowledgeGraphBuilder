# SEMANTiCS 2026-Informed Improvement Plan

**Source**: [local-docs/SEMANTiCS2026-Summary.md](../local-docs/SEMANTiCS2026-Summary.md)
(22nd Int. Conf. on Semantic Systems, Ghent, Sep 2026)
**Status**: Phase A (provenance/rationale log) and Phase B (CQ→SPARQL
functional testing) implemented. Phase C partially implemented (G2 OWL DL
consistency reasoning, G3 OOPS! pitfall detection, and a consolidated
ontology validation report are done and verified against the real
decommissioning ontology; G4 repair agents are not implemented). Phases
D–G not started. Follows the same "one stage at a time, tests before
rewiring" discipline as [AGENTIC_KG_PIPELINE_PLAN.md](AGENTIC_KG_PIPELINE_PLAN.md).
**Branch**: `feat/semantics2026-phase-a-provenance` (off
`refactor/clean-agent-skills-tools`)

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

### Phase A — Provenance & rationale log (G1) ✅ implemented

**Why first**: every other phase (repair loops, pitfall resolution, quorum
voting) becomes far more valuable once decisions are explainable, and this is
the cheapest, lowest-risk change — additive fields plus one new small module.

**Status**: implemented on `feat/semantics2026-phase-a-provenance`.

- `core/models.RationaleEntry` (`agent`, `action`, `reason`,
  `triggered_by: str | None`, `timestamp`). Added
  `rationale: list[RationaleEntry] = field(default_factory=list)` to
  `ExtractedEntity` and `ExtractedRelation` (backward compatible).
- `kgbuilder/provenance/rationale_log.py`: `RationaleLog` — append-only,
  keyed by subject id. `record(subject, agent, action, reason,
  triggered_by=None)` for entities/relations (also appends to
  `subject.rationale`); `record_for_id(subject_id, ...)` for decisions with
  no entity/relation carrier (e.g. a VCQ question's validation outcome).
  `export_jsonld(base_uri)` produces PROV-O/VAEM/Dublin-Core-shaped output
  (`prov:wasGeneratedBy`, `prov:generatedAtTime`, `dc:source`,
  `vaem:rationale`) — see full citations in the module docstring and in
  §8 below.
- Wired (optional `rationale_log` param, `None` by default — no behavior
  change unless supplied) into `ModuleExtractionAgent.run_questions()`
  (records `action="extracted"`, `triggered_by=question_id` per entity) and
  `ValidationAgent.run_questions()` (records `action="validated"`, keyed by
  `question_id`, via `record_for_id` since a VCQ result isn't itself an
  entity/relation).
- Tests: `tests/unit/test_rationale_log.py` (log + JSON-LD shape),
  extended `tests/unit/test_orchestrator_agent.py` (rationale recorded by
  both agents when a log is supplied, no-op when it isn't).

Deferred to Phase C (repair agents haven't been built yet): wiring
`RepairAgent` to call `rationale_log.record(..., action="repaired", ...)`.

### Phase B — CQ→SPARQL functional testing (G5) ✅ implemented

**Why second**: this closes the loop on whether generated CQs (SCQ/RCQ/VCQ)
actually hold against the KG, which is the functional-test pattern used
everywhere at the conference and directly strengthens `ValidationAgent`.

**Status**: implemented on `feat/semantics2026-phase-a-provenance`.

- New `kgbuilder/evaluation/cq_sparql.py`:
  - `CompetencyQuestionTranslator.translate(question) -> CQSparqlTranslation`
    — LLM-assisted NL question -> SPARQL ASK/SELECT (any `LLMProvider`-shaped
    `generate(prompt) -> str`), ontology-guided via `OntologyService`
    (resolves `question.entity_class` to a class URI hint when available).
    Extracts the query from a fenced or bare LLM response; returns
    `sparql=None` + `translation_error` (not an exception) when the LLM
    declines or fails, so callers treat "not translatable" as a normal,
    handleable outcome rather than an error.
  - `CQSparqlRunner.run(translation, store) -> CQSparqlResult` — executes
    against any `RDFStore`-shaped `query_sparql(sparql) -> dict` (Fuseki
    response shape). ASK -> boolean `passed`; SELECT -> `passed = len(bindings) > 0`.
    `translate_and_run(question, store, translator)` convenience wrapper.
  - `compute_cq_translation_coverage(results) -> float` — fraction of
    results with a successful translation, named **CQCoverage** to match
    CQ4OE's dimension naming for cross-run comparability.
- New tool `tools/cq_sparql_tool.py::CQSparqlTool` wrapping
  `runner.translate_and_run(question, store, translator)`.
- New skill `skills/question_validation_skill.py::SparqlQuestionValidationSkill`
  (`question_validation_sparql`) composing the above.
- `ValidationAgent` gained optional `sparql_translator`, `sparql_runner`,
  `rdf_store` constructor params. When all three are supplied,
  `run_questions()` attempts the SPARQL functional test first for each VCQ
  question; only when translation doesn't produce a usable query
  (`translation.sparql is None`) does it fall back to the existing
  `question_validation` (retrieve + LLM-judgment) skill. Rationale entries
  (Phase A) now note which method was used
  (`"VCQ validation via sparql functional test: ..."` vs.
  `"... via LLM judgment: ..."`).
- Tests: `tests/unit/test_cq_sparql.py` (translator fence/bare extraction,
  ontology hint injection, LLM-failure handling, ASK/SELECT execution,
  store-error handling, no-op on failed translation, coverage metric);
  extended `tests/unit/test_orchestrator_agent.py` with three tests covering
  the SPARQL-preferred path, the LLM-judgment fallback, and rationale-method
  tagging.

Deferred to Phase C: no `CQSparqlRunner`/`CompetencyQuestionTranslator`
wiring into repair agents yet (they don't exist until Phase C); the
`compute_cq_translation_coverage` metric isn't yet surfaced anywhere in a
KG-build report (no reporting consumer built — the function exists and is
tested, but nothing calls it end-to-end over a real discovery run yet).

### Phase C — Validation cascade with repair agents (G2, G3, G4) ⚠️ partially implemented

**Why third**: builds directly on Phases A (rationale) and B (functional
tests) — every repair now has both "why" and "does it now pass" available.

**Status**: G2 (consistency reasoning) and G3 (pitfall detection) implemented
and verified against the real `data/ontology/domain/decommissioning.owl`,
plus a consolidated report generator (not in the original plan text, added
because it was needed to make the two checks actually useful together).
**G4 (repair agents) is not implemented.**

- `validation/consistency_reasoner.py`: `ConsistencyReasoner` wraps
  `owlready2` (bundles HermiT *and* Pellet — both usable via
  `reasoner="hermit"|"pellet"`) as an **optional extra**
  (`pip install -e ".[reasoning]"`, added to `pyproject.toml`), mirroring
  how `StaticValidator` treats SHACL2FOL/Vampire as optional. No separate
  JAR download needed (unlike SHACL2FOL) — owlready2 bundles HermiT.jar/
  Pellet's jars itself; only a Java runtime on PATH is required, which is
  already a `StaticValidator` prerequisite. `check_consistency(ontology_path)
  -> ConsistencyCheckResult` (`consistent: bool`, `unsatisfiable_classes:
  list[str]`, `error: str | None` — never raises, degrades to `error` set).
  **Verified live**: ran against the real decommissioning ontology (58
  classes, 120 object properties, 29 data properties) — reports
  `consistent=True`, zero unsatisfiable classes.
- `validation/pitfall_detector.py`: `OOPSPitfallDetector` — HTTP client
  (`httpx`, already a core dependency) for the public OOPS! REST API, with a
  **local rule-based fallback** (rdflib-based, no network) covering P08
  (missing `rdfs:label`/`rdfs:comment`) and P11 (missing `rdfs:domain`/
  `rdfs:range` on object properties) so the pipeline degrades gracefully
  without network access — mirrors G6's "rule-based validator" pattern
  instead of adding a second hard external dependency. **Verified live**
  against the real decommissioning ontology: OOPS! reports **P10** (missing
  disjointness, Important), **P08** (missing annotations, 64 elements,
  Minor), **P04** (2 unconnected elements, Minor), **P22** (naming
  convention inconsistency, Minor) — concrete findings to address before
  publication.
- New tools in the existing `tools/kg_validation_tools.py` (not separate
  files as originally sketched — same pattern, consolidated file):
  `OntologyConsistencyReasoningTool` (`ontology_consistency_reasoning`),
  `OntologyPitfallScanTool` (`ontology_pitfall_scan`). Both take an
  `ontology_path`, distinct from the existing KG-instance-data
  `consistency_check` tool.
- `KGValidationSkill` extended with optional `consistency_reasoner`,
  `pitfall_detector`, and `ontology_path` params — only runs when
  configured, following the exact pattern already used for
  `shacl_validator`/`rules_engine`/`consistency_checker`. Ontology
  inconsistency (when the check actually completes) now gates the
  aggregate `valid` flag; pitfalls are informational only and never gate it.
- **Hardened `StaticValidator._parse_output`** (separately-tracked TODO in
  `VALIDATION_PLAN.md`, resolved as part of this phase): added the missing
  **containment**-mode branch (`"contained in the second?"` — previously
  unhandled, always fell through to "could not parse"), verified against
  real JAR/Vampire output for all three modes (satisfiability, containment,
  static validation), and improved the unparseable-output error message to
  include a text snippet for debugging. **Verified live**: real
  satisfiability check against shapes generated from a toy ontology returns
  `valid=True` in 0.005s using the vendored `lib/SHACL2FOL.jar`/`lib/vampire`.
- New `validation/ontology_report.py`: `OntologyValidationReportBuilder` +
  `OntologyValidationReport` — consolidates OWL DL consistency, SHACL shape
  satisfiability, OOPS! pitfalls, and CQ coverage (Phase B) into one
  artifact with `to_dict()`/`to_markdown()`, intended for a publication's
  reproducibility appendix. **Verified live**: generated a full markdown
  report for the decommissioning ontology (consistency + pitfalls; CQ
  coverage needs a live LLM + RDF store, not exercised in this environment).
- **Not implemented**: `agents/repair_agent.py` (G4 — no automatic
  re-invocation of extraction/assembly when a check fails; findings are
  reported, not yet acted on). This remains the next step if pursued.
- Tests: `tests/unit/test_consistency_reasoner.py`,
  `tests/unit/test_pitfall_detector.py`, `tests/unit/test_ontology_report.py`
  (all mock owlready2/HTTP — no live Java/network dependency in unit tests),
  extended `tests/unit/test_kg_validation_tools_and_skill.py` and
  `tests/validation/test_static_validator.py`.

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

| Phase | Priority | Rough size | Depends on | Status |
|---|---|---|---|---|
| A — Rationale log | High | Small | — | ✅ Done |
| B — CQ→SPARQL tests | High | Medium | A (for logging translation failures) | ✅ Done |
| C — Validation cascade + repair agents | High | Large | A, B | ⚠️ Partial (G2/G3 + report done; G4 repair agents not started) |
| D — Prompt diversity + rule validator | Medium | Medium | — (independent, can run parallel to A–C) | Not started |
| E — Quorum voting | Medium | Small | D helpful but not required | Not started |
| F — GraphML prompt context | Low | Small | — (independent) | Not started |
| G — CQ coaching | Low (exploratory) | Small | B (reuses SPARQL-translatability as one specificity signal) | Not started |

Recommended order: **A → B → C**, with **D** picked up opportunistically in
parallel since it touches a different subsystem (`extraction/`) than A–C
(`provenance/`, `validation/`, `agents/`). **E, F, G** are independent
follow-ups once A–D are stable.

---

## 6. New optional dependencies (all feature-flagged, none required by default)

| Dependency | Used by | Install extra |
|---|---|---|
| `owlready2` | Phase C consistency reasoning (HermiT/Pellet) — **added to `pyproject.toml`** | `pip install -e ".[reasoning]"` |
| none (HTTP client only, `httpx` already a core dependency) | Phase C OOPS! pitfall detection | — |

No new required dependency changes `pyproject.toml`'s default install.

---

## 7. Cross-references

- Full conference notes: [local-docs/SEMANTiCS2026-Summary.md](../local-docs/SEMANTiCS2026-Summary.md)
- Current agentic architecture this plan builds on: [AGENTIC_KG_PIPELINE_PLAN.md](AGENTIC_KG_PIPELINE_PLAN.md)
- Validation architecture this plan extends: [VALIDATION_PLAN.md](VALIDATION_PLAN.md)
- Agent/skill/tool design reference: [docs/architecture/agentic-pipeline.md](../docs/architecture/agentic-pipeline.md)

---

## 8. Attribution / sources

Every phase above is inspired by a specific paper, tool, or talk from
SEMANTiCS 2026 (Ghent, 15–17 Sep 2026). Proceedings: IOS Press, *Studies on
the Semantic Web* vol. 63, ISBN 978-1-64368-686-8, doi:10.3233/SSW63, CC BY
4.0. Cited per-phase, so contributions can be traced back to their source
when this plan is implemented.

| Phase / gap | Source | Citation |
|---|---|---|
| A (G1) — rationale log | **MASEO** (Multi-Agent System for Explainable Ontology Generation), OEG-UPM | Repo: <https://github.com/oeg-upm/maseo> (Apache-2.0) · Docs: <https://maseo.readthedocs.io> · doi:10.5281/zenodo.19052003 · funded by SOEL, <https://w3id.org/soel>, grant PID2023-152703NA-I00 |
| A (G1) — provenance-as-trust framing | Sabou, M. — *"Beyond Data: Why the Future of AI is Neurosymbolic"* | NeSy workshop keynote, SEMANTiCS 2026, WU Wien, 14 Sep 2026 |
| A (G1) — JSON-LD vocabulary | W3C PROV Ontology (PROV-O) | <https://www.w3.org/TR/prov-o/> |
| A (G1) — JSON-LD vocabulary | Dublin Core Metadata Terms (`dc:`) | <https://www.dublincore.org/specifications/dublin-core/dcmi-terms/> |
| A (G1) — JSON-LD vocabulary | VAEM (Vocabulary for Attaching Essential Metadata), used by MASEO for `vaem:rationale` | <http://www.linkedmodel.org/schema/vaem> |
| B (G5) — CQ→SPARQL functional testing | **CQ4OE** benchmark, OEG-UPM | <https://oeg-upm.github.io/cq4oe-benchmark/> · leaderboard: <https://oeg-upm.github.io/cq4oe-benchmark/leaderboard/> · HF dataset `oeg/CQ4OE` · doi:10.5281/zenodo.20080309 |
| C (G2) — DL consistency reasoning | MASEO's Logical Consistency Agent (HermiT reasoner) | See MASEO citation above; HermiT: <http://www.hermit-reasoner.com/> |
| C (G3) — ontology pitfall detection | MASEO's Pitfall Resolution Agent (OOPS! REST API) | See MASEO citation above; OOPS!: <http://oops.linkeddata.es/> |
| C (G4) — per-failure-class repair agents | MASEO's 4-stage sequential agent pipeline | See MASEO citation above |
| C (G2–G4) — RAG-scoped, requirement-driven extension pattern | **OntoExtend** — Lippolis, Saeedizade, Schmid, Blattner, Keskisärkkä, Gangemi, Blomqvist, Nuzzolese (Bologna / Linköping / Bosch / ISTC-CNR) | Proceedings pp. 107–122, doi:10.3233/SSW260011 |
| D (G6) — prompt diversity + rule-based validator | **Ontology-Aware Prompting for KG Construction from Text** — Tiwari, Lopes Oliveira, Firmansyah, Zahera, Hopfgartner, Ngonga Ngomo (Paderborn / Koblenz) | Proceedings pp. 87–102, doi:10.3233/SSW260009 · code: <https://github.com/dice-group/ontology-aware-kg-construction> |
| D (G6) — self-demonstration pattern (related, not directly adopted) | **Surprising Effectiveness of Self-Demonstrations in Schema–Ontology Mapping** — Thombre, Patwardhan, Sarawagi (TCS Research / IIT Bombay) | Proceedings pp. 70–85, doi:10.3233/SSW260008 |
| E (G8) — heterogeneous-LLM quorum voting | **HARP: Navigating Schema Drift** — Diettrich, Friedenberger, Both (HTWK Leipzig / DB Systel) | Proceedings pp. 160–174, doi:10.3233/SSW260014 |
| F (G9) — GraphML LLM-context serialization | **GraphRAG Best Practices** — Liao, Collarana, Pack, Grass, Both, Decker, Beecks (RWTH / Fraunhofer FIT / HTWK) | Proceedings pp. 141–156, doi:10.3233/SSW260013 |
| G (G7) — CQ-quality coaching, underspecified-CQ failure mode | OntoExtend (see above); also motivated by SoCK's expert-in-the-loop disagreement handling — Ehrenmüller, Kook, Ekaputra, Sabou (WU Wien) | SoCK: proceedings pp. 19–33, doi:10.3233/SSW260004 |
| §1 — CQ typology underpinning `CQType` (pre-existing, not new in this plan) | Keet, C.M. & Khan, Z.C. — Question-answering ontology model (QuO) | arXiv:2412.13688 |
| §2 non-goal — cold-start / scope-revelation (deferred to GraphQAAgent/OntologyExtender) | McNamara, C. — *"The Initial Exploration Problem in KG Exploration"* | UKG workshop, SEMANTiCS 2026 |

