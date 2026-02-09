# Law Graph — Detailed Implementation Plan

> **Updated**: 2026-02-09  
> **Status**: Planning → stubs created, ontologies downloaded  
> **Branch**: `feat/law-graph`

This document supersedes the high-level plan in `LAW_GRAPH_PLAN.md` with
concrete implementation steps, file paths, data flow, and ontology alignment
details. All code stubs referenced here already exist.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Ontology Strategy](#2-ontology-strategy)
3. [Data Flow](#3-data-flow)
4. [Implementation Steps](#4-implementation-steps)
   - Step 1: XML Reader
   - Step 2: Document Adapter
   - Step 3: Phase A — Structural Import
   - Step 4: Legal Rule-Based Extractor
   - Step 5: Legal LLM Extractor + Ensemble
   - Step 6: Phase B — Semantic Extraction
   - Step 7: Custom Law Ontology (OWL)
   - Step 8: Qdrant Indexing
   - Step 9: End-to-End Integration
5. [Ontology Alignment Details](#5-ontology-alignment-details)
6. [Reuse from law_knowledge_graph](#6-reuse-from-law_knowledge_graph)
7. [File Inventory](#7-file-inventory)
8. [Effort Estimates](#8-effort-estimates)
9. [Open Decisions](#9-open-decisions)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LAW GRAPH PIPELINE                               │
│                                                                         │
│  data/law_html/{LawAbbr}/BJNR*.xml                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                   │
│  │  LawXMLReader   │  Parse <norm> elements                            │
│  │  (law_xml.py)   │  → LawDocument + Norm dataclasses                 │
│  └────────┬────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────────┐                                              │
│  │  LawDocumentAdapter  │  Convert to KGB Document/Chunk               │
│  │  (law_adapter.py)    │  + extract structural relations              │
│  └────────┬─────────────┘                                              │
│           │                                                             │
│     ┌─────┴──────┐                                                     │
│     ▼            ▼                                                     │
│  ┌──────────┐  ┌───────────────────────────────────────┐               │
│  │ PHASE A  │  │ PHASE B                               │               │
│  │ No LLM   │  │ Ensemble Extraction                   │               │
│  │          │  │                                       │               │
│  │ • Parse  │  │ ┌─────────────────┐ ┌──────────────┐ │               │
│  │ • Entity │  │ │ LegalRuleBased  │ │ LegalLLM     │ │               │
│  │   nodes  │  │ │ Extractor       │ │ Extractor    │ │               │
│  │ • TEIL_  │  │ │                 │ │              │ │               │
│  │   VON    │  │ │ • § regex       │ │ • Ontology-  │ │               │
│  │ • REFER- │  │ │ • Behörde gaz.  │ │   guided     │ │               │
│  │   ENZIERT│  │ │ • Deontic patt. │ │   prompts    │ │               │
│  │ • Embed  │  │ │ • Definitions   │ │ • Struct.    │ │               │
│  │   →Qdrant│  │ └────────┬────────┘ │   output     │ │               │
│  └────┬─────┘  │          └─────┬────┘└──────┬──────┘ │               │
│       │        │                └──────┬─────┘        │               │
│       │        │                       ▼              │               │
│       │        │              ┌──────────────┐        │               │
│       │        │              │ Ensemble     │        │               │
│       │        │              │ Merge +      │        │               │
│       │        │              │ Calibrate    │        │               │
│       │        │              └──────┬───────┘        │               │
│       │        └─────────────────────┤                │               │
│       │                              │                                │
│       └──────────────┬───────────────┘                                │
│                      ▼                                                 │
│  ┌──────────────────────────────────────┐                              │
│  │  Neo4j (graph_type: "law")           │                              │
│  │  Qdrant (collection: "lawgraph")     │                              │
│  │  Fuseki (dataset: "lawgraph")        │                              │
│  └──────────────────────────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Ontology Strategy

### 2.1 Three-Layer Approach

| Layer | Source | Purpose |
|-------|--------|---------|
| **Reference: LKIF-Core** | `data/ontology/legal/lkif-core/` (11 OWL modules) | Academic legal ontology — defines `Norm`, `Obligation`, `Permission`, `Prohibition`, `Right`, `Legal_Document`, `Public_Body`, etc. We _align to_ these classes but don't import them directly (too large, too generic). |
| **Reference: ELI** | `data/ontology/legal/eli/eli.owl` | EU legislation metadata model — defines `LegalResource`, `LegalExpression`, `LegalResourceSubdivision`, plus relations like `cites`, `amends`, `has_part`. We align document-level classes to ELI. |
| **Custom: law-ontology** | `data/ontology/law/law-ontology-v1.0.owl` (to be generated) | Our purpose-built ontology for the German law KG. Imports relevant concepts from LKIF-Core and ELI via `owl:equivalentClass` / `rdfs:subClassOf` alignments. This is what gets loaded into Fuseki and drives extraction. |

### 2.2 Class Mapping

| Our Class | LKIF-Core Alignment | ELI Alignment |
|-----------|-------------------|---------------|
| `law:Gesetzbuch` | — | `eli:LegalResource` |
| `law:Bundesgesetz` | `lkif-norm:Statute` | — |
| `law:Verordnung` | `lkif-norm:Regulation` | — |
| `law:Paragraf` | — | `eli:LegalResourceSubdivision` |
| `law:Obligation` | `lkif-norm:Obligation` | — |
| `law:Permission` | `lkif-norm:Permission` | — |
| `law:Prohibition` | `lkif-norm:Prohibition` | — |
| `law:Behoerde` | `lkif-laction:Public_Body` | — |
| `law:Betreiber` | `lkif-laction:Legal_Person` | — |
| `law:LegalReference` | — | (via `eli:cites`) |

### 2.3 Relation Mapping

| Our Relation | ELI Alignment | Description |
|-------------|---------------|-------------|
| `law:teilVon` | `eli:is_part_of` | Paragraph → Law |
| `law:referenziert` | `eli:cites` | Paragraph → Paragraph |
| `law:aendert` | `eli:amends` | Law → Law |
| `law:definiert` | — | Paragraph → Definition |
| `law:verpflichtet` | — | Paragraph → Obligation |
| `law:erlaubt` | — | Paragraph → Permission |
| `law:verbietet` | — | Paragraph → Prohibition |
| `law:zustaendig` | — | Authority → Obligation |
| `law:betrifft` | — | Obligation → Actor |
| `law:aufgehobenDurch` | `eli:repealed_by` | Paragraph → Paragraph |

### 2.4 Why Not Import LKIF-Core/ELI Directly?

- **LKIF-Core** is 11 interconnected modules (~400KB). Importing everything would pollute
  the extraction prompt with hundreds of irrelevant classes (Contract, Treaty, Custom,
  International_Agreement, etc.). We only need ~15 classes.
- **ELI** is designed for EU-wide legislation metadata, not paragraph-level KG construction.
  We use its document structure classes (LegalResource, LegalResourceSubdivision) and
  key relations (cites, amends, is_part_of) via alignment, not full import.
- Our ontology stays small, focused, and optimized for extraction prompt size.

---

## 3. Data Flow

### 3.1 Input: XML Law Files

```
data/law_html/
├── AtG/
│   ├── AtG.html                    # Human-readable (not used for KG)
│   ├── BJNR008140959.xml           # ← PRIMARY INPUT
│   └── xml.zip                     # Original download
├── StrlSchG/
│   ├── StrlSchG.html
│   ├── BJNR196610017.xml           # 293 norms
│   └── xml.zip
├── StrlSchV/
│   └── ...
└── ... (17 laws total)
```

### 3.2 XML Structure (per BJNR*.xml)

```xml
<dokumente builddate="20250130" doession="BJNR008140959">
  <norm builddate="20250130" doknr="BJNR008140959">  <!-- Norm 0: law metadata -->
    <metadaten>
      <jurabk>AtG</jurabk>
      <amtabk>AtG</amtabk>
      <ausfertigung-datum manuell="ja">1959-12-23</ausfertigung-datum>
      <kurzue>Atomgesetz</kurzue>
      <langue>Gesetz über die friedliche Verwendung der Kernenergie...</langue>
    </metadaten>
  </norm>
  <norm ...>  <!-- Norm 1: section heading -->
    <metadaten>
      <jurabk>AtG</jurabk>
      <gliederungseinheit>
        <gliederungsbez>Erster Abschnitt</gliederungsbez>
        <gliederungstitel>Allgemeine Vorschriften</gliederungstitel>
      </gliederungseinheit>
    </metadaten>
  </norm>
  <norm ...>  <!-- Norm 2: actual paragraph -->
    <metadaten>
      <jurabk>AtG</jurabk>
      <enbez>§ 1</enbez>
      <titel>Zweckbestimmung des Gesetzes</titel>
    </metadaten>
    <textdaten>
      <text format="XML">
        <Content>
          <P>Zweck dieses Gesetzes ist...</P>
          <P>(1) Die Nutzung der Kernenergie...</P>
        </Content>
      </text>
    </textdaten>
  </norm>
</dokumente>
```

### 3.3 Parsed Output (LawXMLReader)

```python
LawDocument(
    file_path=Path("data/law_html/AtG/BJNR008140959.xml"),
    metadata=LawMetadata(jurabk="AtG", kurzue="Atomgesetz", ...),
    norms=[
        Norm(norm_type=METADATA, jurabk="AtG", ...),
        Norm(norm_type=STRUCTURE, jurabk="AtG", gliederung=GliederungsEinheit(...)),
        Norm(norm_type=PARAGRAPH, jurabk="AtG", enbez="§ 1", title="Zweckbestimmung...",
             text="Zweck dieses Gesetzes ist...", cross_references=[...]),
        ...
    ]
)
```

### 3.4 Neo4j Target Schema

```
(:Gesetzbuch {
    label: "AtG",
    abkuerzung: "AtG",
    langtext: "Gesetz über die friedliche Verwendung der Kernenergie...",
    entity_type: "Bundesgesetz",
    graph_type: "law"
})

(:Paragraf {
    label: "AtG § 7",
    nummer: "§ 7",
    titel: "Genehmigung von Anlagen",
    gesetzestext: "...",
    entity_type: "Paragraf",
    graph_type: "law"
})

(:Gesetzbuch)-[:teilVon]->(:Paragraf)  -- wait, inverse:
(:Paragraf)-[:TEIL_VON]->(:Gesetzbuch)
(:Paragraf)-[:REFERENZIERT]->(:Paragraf)
(:Paragraf)-[:DEFINIERT]->(:Definition)
(:Paragraf)-[:VERPFLICHTET]->(:Obligation)
(:Behoerde)-[:ZUSTAENDIG]->(:Obligation)
```

---

## 4. Implementation Steps

### Step 1: XML Reader — `LawXMLReader` (2h)

**File**: `src/kgbuilder/document/loaders/law_xml.py` (stub exists)

**What to implement**:

1. `parse_file(path)` — open XML, find root `<dokumente>`, iterate `<norm>` elements
2. `_parse_law_metadata(first_norm)` — extract `<jurabk>`, `<amtabk>`, `<ausfertigung-datum>`,
   `<fundstelle>`, `<kurzue>`, `<langue>`, `<standangabe>` from the first norm
3. `_classify_norm(meta, text_elem)` — categorize as METADATA/STRUCTURE/PARAGRAPH/APPENDIX:
   - METADATA: first norm (no `<enbez>`, no `<gliederungseinheit>`)
   - STRUCTURE: has `<gliederungseinheit>` but no `<enbez>`
   - PARAGRAPH: has `<enbez>` (§ N, Art N, Anlage)
   - APPENDIX: `<enbez>` starts with "Anlage"
4. `_extract_text(text_elem)` — walk `<Content>` children, strip XML tags to plain text,
   preserve `<BR/>` as newlines, handle `<DL>/<DT>/<DD>` definition lists
5. `_extract_cross_references(text, source, law)` — apply `_XREF_PATTERN` regex,
   detect target law abbreviation (same law if no abbreviation suffix)
6. `_parse_gliederung(meta)` — extract `gliederungsbez` + `gliederungstitel`
7. `parse_directory(dir_path)` — glob `**/BJNR*.xml`, parse each

**Key parsing detail**: The `<Content>` element contains `<P>` paragraphs,
`<DL>` definition lists (with `<DT>` terms and `<DD>` definitions), `<table>`
elements, and `<BR/>` line breaks. The text extractor should produce clean
plain text suitable for both LLM extraction and embedding.

**Test**: Parse `data/law_html/AtG/BJNR008140959.xml`:
- Expect 111 norms total
- Expect `metadata.jurabk == "AtG"`
- Expect `paragraphs()` returns ~60 § norms
- Expect cross-references detected in § 7 (references to other AtG sections)

---

### Step 2: Document Adapter — `LawDocumentAdapter` (1.5h)

**File**: `src/kgbuilder/document/loaders/law_adapter.py` (stub exists)

**What to implement**:

1. `to_documents(law)` — convert LawDocument to KGB Documents:
   - Strategy "paragraph": one Document per `Norm` with `is_paragraph == True`
     - `doc.id` = `"{jurabk}_{enbez}"` (e.g. `"AtG_§ 7"`)
     - `doc.content` = norm.text
     - `doc.file_type` = `FileType.HTML` (closest type for law XML)
     - `doc.metadata.title` = norm.title
     - `doc.metadata.custom` = `{"jurabk": ..., "enbez": ..., "norm_type": ...}`
   - Strategy "section": group norms by gliederungseinheit, concatenate text
   - Strategy "law": all paragraph text in one Document

2. `to_structural_relations(law)` — extract ground-truth relations:
   - `TEIL_VON`: for each paragraph norm → `ExtractedRelation(source=paragraph_id, target=law_id, predicate="teilVon")`
   - `REFERENZIERT`: for each `CrossReference` → `ExtractedRelation(source=source_§, target=target_§, predicate="referenziert")`

3. Helper to generate entity IDs compatible with `generate_entity_id()` from core.models

**Test**: Convert AtG → expect ~60 Documents (paragraph strategy), expect TEIL_VON
relations for each, expect REFERENZIERT relations where cross-references exist.

---

### Step 3: Phase A — Structural Import (2.5h)

**File**: `scripts/build_law_graph.py` → `run_phase_a()` (stub exists)

**What to implement**:

```python
def run_phase_a(args):
    # 1. Discover XML files
    xml_files = discover_xml_files(args.law_data, args.laws)
    
    # 2. Parse all laws
    reader = LawXMLReader()
    laws = [reader.parse_file(f) for f in xml_files]
    
    # 3. Convert to Documents
    adapter = LawDocumentAdapter(chunking_strategy="paragraph")
    all_documents = []
    all_structural_relations = []
    for law in laws:
        all_documents.extend(adapter.to_documents(law))
        all_structural_relations.extend(adapter.to_structural_relations(law))
    
    # 4. Create Gesetzbuch entities
    gesetzbuch_entities = create_gesetzbuch_entities(laws)
    
    # 5. Create Paragraf entities
    paragraf_entities = create_paragraf_entities(laws)
    
    # 6. Embed paragraphs into Qdrant
    if not args.skip_embed:
        embed_documents(all_documents, collection=args.collection)
    
    # 7. Store in Neo4j
    if not args.dry_run:
        store_entities(gesetzbuch_entities + paragraf_entities, graph_type="law")
        store_relations(all_structural_relations, graph_type="law")
    
    return {"laws": len(laws), "paragraphs": len(paragraf_entities),
            "relations": len(all_structural_relations)}
```

**Dependencies**: LawXMLReader, LawDocumentAdapter, existing KGB storage (Neo4j, Qdrant)

**Tag all entities with** `graph_type: "law"` to keep separate from decommissioning KG.

---

### Step 4: Legal Rule-Based Extractor (3h)

**File**: `src/kgbuilder/extraction/legal_rules.py` (stub exists)

**What to implement**:

1. **`_extract_paragraph_references()`**:
   - Apply `PARAGRAPH_REF_PATTERN` to text
   - For each match, detect if target is same law (no abbreviation) or external
   - Create `ExtractedEntity(entity_type="LegalReference", label="§ 7 AtG", ...)`
   - Confidence: 0.95 (regex match on structured text)

2. **`_extract_authorities()`**:
   - Apply `AUTHORITY_PATTERN` for generic pattern matches
   - Apply `KNOWN_AUTHORITIES` gazetteer for abbreviation matches (BfS, BASE, etc.)
   - Create `ExtractedEntity(entity_type="Behoerde", label="Bundesamt für Strahlenschutz", ...)`
   - Confidence: 0.98 (gazetteer) / 0.85 (pattern)

3. **`_extract_definitions()`**:
   - Apply `DEFINITION_PATTERN` to detect definition paragraphs
   - Extract the defined term from context (next noun phrase after "im Sinne")
   - Create `ExtractedEntity(entity_type="Definition", ...)`
   - Confidence: 0.80 (pattern match, but term extraction is approximate)

4. **`_extract_deontic_modalities()`**:
   - Apply `OBLIGATION_PATTERN`, `PERMISSION_PATTERN`, `PROHIBITION_PATTERN`
   - Extract surrounding sentence as the obligation/permission/prohibition text
   - Create entities with types `Obligation`, `Permission`, `Prohibition`
   - Confidence: 0.85 (pattern is reliable, scope is approximate)

5. **`extract_relations()`**:
   - Pair `LegalReference` entities with source paragraph → `referenziert` relation
   - Pair `Behoerde` near `Obligation` → `zustaendig` relation (proximity heuristic)
   - Pair `Definition` with source paragraph → `definiert` relation

**Why rule-based first**: German law text is highly formulaic. Patterns like
"§ 7 Abs. 2 Satz 1" are 100% deterministic. Authorities are from a known set.
Deontic modalities use standard verbs (muss, darf, darf nicht). Rule-based
extraction catches these with near-perfect precision, while LLM handles the
semantic interpretation (what exactly is obligated).

---

### Step 5: Legal LLM Extractor + Ensemble (3h)

**Files**:
- `src/kgbuilder/extraction/legal_llm.py` (stub exists)
- `src/kgbuilder/extraction/legal_ensemble.py` (stub exists)

**LLM Extractor — what to implement**:

1. `_build_entity_prompt()`:
   - Load ontology class definitions from Fuseki
   - Format classes as structured list: name, description, examples
   - Inject paragraph text
   - Include few-shot examples of correct extractions
   - Use German-language system prompt (laws are in German)

2. `_build_relation_prompt()`:
   - Include already-extracted entities as context
   - List allowed relation types from ontology
   - Ask LLM to identify relations between provided entities

3. `_parse_entity_response()` / `_parse_relation_response()`:
   - Parse JSON from LLM response (handle markdown code blocks)
   - Validate entity types against ontology
   - Generate deterministic IDs via `generate_entity_id()`

4. `_validate_against_ontology()`:
   - Filter entities whose `entity_type` doesn't match any ontology class
   - Log dropped entities for debugging

**Ensemble — what to implement**:

1. Run `LegalRuleBasedExtractor.extract_entities()` first (fast)
2. Pass rule-based entities as context hint to `LegalLLMExtractor`
3. Run LLM extractor
4. Merge:
   - Exact match (same label + type) → keep rule-based, boost confidence +0.15
   - Rule-only entities → keep as-is (high precision)
   - LLM-only entities → keep if confidence > threshold (higher recall)
   - Type conflict (same entity, different type) → prefer rule-based if `prefer_rule_on_conflict`
5. Same merge strategy for relations

---

### Step 6: Phase B — Semantic Extraction (2h)

**File**: `scripts/build_law_graph.py` → `run_phase_b()` (stub exists)

**What to implement**:

```python
def run_phase_b(args):
    # 1. Load ontology from Fuseki
    ontology = load_ontology(args.fuseki_dataset)
    
    # 2. Init extractors
    llm = init_ollama_provider()  # qwen3
    rule_extractor = LegalRuleBasedExtractor()
    llm_extractor = LegalLLMExtractor(llm=llm, ontology=ontology)
    ensemble = LegalEnsembleExtractor(rule_extractor, llm_extractor)
    
    # 3. Load paragraphs (from Neo4j or re-parse XMLs)
    paragraphs = load_paragraph_entities(graph_type="law")
    
    # 4. For each paragraph, extract
    all_entities = []
    all_relations = []
    for para in paragraphs:
        entities, relations = ensemble.extract(
            text=para.properties["gesetzestext"],
            law_abbr=para.properties["jurabk"],
            paragraph_id=para.label,
        )
        all_entities.extend(entities)
        all_relations.extend(relations)
    
    # 5. Enrich (optional: use SemanticEnrichmentPipeline)
    # 6. Validate
    # 7. Store
    if not args.dry_run:
        store_entities(all_entities, graph_type="law")
        store_relations(all_relations, graph_type="law")
    
    return {"entities": len(all_entities), "relations": len(all_relations)}
```

**Note**: Phase B should be idempotent — running it again should update, not duplicate.

---

### Step 7: Custom Law Ontology (OWL) (1.5h)

**File**: `scripts/build_law_ontology.py` (stub exists)  
**Output**: `data/ontology/law/law-ontology-v1.0.owl`

**What to implement**:

Generate valid OWL/XML with:
- Namespace: `http://kgbuilder.2060.io/ontology/law#`
- All 14 classes from the CLASSES list (with German + English labels)
- All 10 object properties from RELATIONS (with domain/range)
- All 7 datatype properties from DATATYPE_PROPERTIES
- `owl:equivalentClass` axioms for LKIF-Core alignments
- `rdfs:subClassOf` axioms for ELI alignments
- Annotation properties for labels and comments

The ontology should be loadable by:
1. Fuseki (for extraction prompt generation)
2. Python `owlready2` or `rdflib` (for validation)
3. Protégé (for manual inspection)

**Validation**: Load with `rdflib`, verify class count, verify relation domains/ranges.

---

### Step 8: Qdrant Indexing (1h)

Paragraph-level embeddings for retrieval. Uses existing `OllamaEmbeddingProvider`.

**Strategy**:
- Collection: `"lawgraph"` (separate from decommissioning `"kgbuilder"`)
- One vector per paragraph § (not per sentence — paragraphs are short enough)
- Payload: `{jurabk, enbez, titel, norm_type, graph_type: "law"}`
- Embedding model: `qwen3-embedding` via Ollama

**Integration**: Called from `run_phase_a()` after document conversion.

---

### Step 9: End-to-End Integration (2h)

1. Run `scripts/build_law_ontology.py` → creates OWL file
2. Upload ontology to Fuseki (`lawgraph` dataset)
3. Run `scripts/build_law_graph.py --phase full --laws AtG StrlSchG StrlSchV`
4. Verify in Neo4j:
   - 3 Gesetzbuch nodes
   - ~464 Paragraf nodes (111 AtG + 293 StrlSchG + ~60 StrlSchV)
   - TEIL_VON relations for all paragraphs
   - REFERENZIERT relations for detected cross-references
   - Semantic entities (Obligations, Definitions, Authorities) from Phase B
5. Verify in Qdrant: `lawgraph` collection with paragraph embeddings
6. Run sample queries to validate graph quality

---

## 5. Ontology Alignment Details

### 5.1 LKIF-Core Modules We Use

| Module | Key Classes | Usage |
|--------|-------------|-------|
| `norm.owl` | `Norm`, `Obligation`, `Permission`, `Prohibition`, `Right`, `Statute`, `Regulation`, `Legal_Document` | Core deontic classification — our `Obligation`/`Permission`/`Prohibition` align to these. `Statute` ↔ `Bundesgesetz`, `Regulation` ↔ `Verordnung`. |
| `legal-action.owl` | `Public_Body`, `Legal_Person`, `Public_Act`, `Decision`, `Legislative_Body` | Actor classification — our `Behoerde` ↔ `Public_Body`, `Betreiber` ↔ `Legal_Person`. |
| `legal-role.owl` | `Legal_Role`, `Professional_Legal_Role`, `Social_Legal_Role` | Not directly used, but available for future extension. |
| `expression.owl` | `Expression`, `Qualified`, `Propositional_Attitude` | Foundation for LKIF-Core's expression model. Indirectly imported by norm.owl. |

### 5.2 ELI Properties We Use

| ELI Property | Our Mapping | Description |
|-------------|-------------|-------------|
| `eli:is_part_of` | `law:teilVon` | Subdivision → Resource |
| `eli:cites` | `law:referenziert` | Resource → Resource cross-reference |
| `eli:amends` | `law:aendert` | Resource → Resource amendment |
| `eli:repealed_by` | `law:aufgehobenDurch` | Repeal relation |
| `eli:date_document` | `law:letzteAenderung` | Last amendment date |
| `eli:title` | `law:langtext` | Full title |
| `eli:title_short` | `law:abkuerzung` | Abbreviation |

### 5.3 What About Akoma Ntoso and LegalRuleML?

Per `LAW_ONTOLOGY_SOURCES.md`, we identified four ontologies. Here's why we
use two and defer two:

| Ontology | Status | Reason |
|----------|--------|--------|
| **LKIF-Core** | ✅ Used | Best fit for normative classification (obligations, permissions, prohibitions). Well-maintained OWL. |
| **ELI** | ✅ Used | EU standard for legislation metadata. Perfect for document-level properties. |
| **Akoma Ntoso** | ⏸ Deferred | XML document markup standard, not an OWL ontology. Better suited for document authoring than KG construction. Could be used later for document structure markup. |
| **LegalRuleML** | ⏸ Deferred | Rule interchange format (if-then-else legal rules). Relevant for legal reasoning systems, not KG construction. Could extend the pipeline later for rule extraction. |

---

## 6. Reuse from law_knowledge_graph

### 6.1 What We Reuse

| Artifact | How |
|----------|-----|
| **Graph schema concept** (Gesetzbuch → Paragraf → TEIL_VON/REFERENZIERT) | Our Phase A implements the same structural graph, enriched with metadata from XML (they used JSON). |
| **Cross-reference data model** | Same concept — we extract REFERENZIERT from XML regex instead of pre-parsed JSON. |
| **GraphReader pattern** | Note for future C3/GraphQAAgent integration. The rational_plan → node_selection → fact_check flow is reusable. |

### 6.2 What We Do Differently

| Aspect | law_knowledge_graph | Our Pipeline |
|--------|-------------------|-------------|
| **Data source** | Pre-processed JSON | Official XML from gesetze-im-internet.de (richer metadata) |
| **Extraction** | GPT-4o atomic facts (unstructured) | Ontology-guided rule-based + LLM ensemble |
| **Ontology** | None | Custom OWL aligned to LKIF-Core + ELI |
| **LLM** | OpenAI GPT-4o (cloud, paid) | Ollama qwen3 (local, free) |
| **Embeddings** | OpenAI text-embedding-3-small | Ollama qwen3-embedding (local) |
| **Storage** | Neo4j only | Neo4j + Qdrant + Fuseki |
| **Granularity** | Paragraph text only | Full metadata (dates, amendments, structure, sections) |
| **Cross-references** | Pre-computed in JSON | Extracted via regex from XML text |

### 6.3 Potential Data Import

If we ever want to import the `law_knowledge_graph` JSON data (for laws we
don't have in XML), we could write a `LawJSONLoader`. This is low priority
since we have XML for all target laws.

---

## 7. File Inventory

### New Files (created in this branch)

| File | Type | Status |
|------|------|--------|
| `src/kgbuilder/document/loaders/law_xml.py` | XML reader | Stub |
| `src/kgbuilder/document/loaders/law_adapter.py` | Document adapter | Stub |
| `src/kgbuilder/extraction/legal_rules.py` | Rule-based extractor | Stub |
| `src/kgbuilder/extraction/legal_llm.py` | LLM extractor | Stub |
| `src/kgbuilder/extraction/legal_ensemble.py` | Ensemble extractor | Stub |
| `scripts/build_law_graph.py` | Main pipeline script | Stub |
| `scripts/build_law_ontology.py` | Ontology generator | Stub |
| `scripts/crawl_law_index.py` | Law index crawler | Complete |
| `scripts/download_decom_laws_html.py` | Law HTML downloader | Complete |
| `scripts/download_law_xml_zips.py` | XML ZIP downloader | Complete |
| `scripts/full_law_pipeline.py` | Data acquisition pipeline | Complete |
| `scripts/organize_and_download_xml.py` | XML organizer | Complete |
| `Planning/LAW_GRAPH_PLAN.md` | High-level plan | Complete |
| `Planning/LAW_ONTOLOGY_SOURCES.md` | Ontology citations | Complete |
| `Planning/LAW_GRAPH_IMPLEMENTATION.md` | This document | Complete |
| `data/ontology/README.md` | Ontology directory docs | Complete |
| `data/ontology/legal/lkif-core/*.owl` | LKIF-Core (11 files) | Downloaded |
| `data/ontology/legal/eli/*.owl` | ELI ontology | Downloaded |

### Gitignored (downloaded at runtime)

| Path | Content |
|------|---------|
| `data/law_html/` | Downloaded law HTML + XML files |
| `data/law_index/` | Crawled law index JSON |
| `data/law_jsons/` | Future: processed JSON paragraphs |

---

## 8. Effort Estimates

| Step | Description | Effort | Dependencies |
|------|-------------|--------|-------------|
| 1 | LawXMLReader implementation | 2.0h | None |
| 2 | LawDocumentAdapter | 1.5h | Step 1 |
| 3 | Phase A (structural import) | 2.5h | Steps 1-2 |
| 4 | LegalRuleBasedExtractor | 3.0h | Step 1 |
| 5 | LegalLLMExtractor + Ensemble | 3.0h | Step 4 |
| 6 | Phase B (semantic extraction) | 2.0h | Steps 4-5 |
| 7 | Law ontology OWL generation | 1.5h | None |
| 8 | Qdrant indexing integration | 1.0h | Step 2 |
| 9 | End-to-end test | 2.0h | All above |
| **Total** | | **~18.5h** | |

Parallelizable: Steps 1+7 can run in parallel. Steps 4+7+8 can follow Step 2.

---

## 9. Open Decisions

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | **Absatz granularity**: Import at § level or § Abs. level? | Start § level. XML doesn't always cleanly separate Absätze. LLM can reference Absatz in extraction output. |
| 2 | **Neo4j separation**: `graph_type` property or separate database? | `graph_type: "law"` property (Neo4j Community = 1 DB). |
| 3 | **Atomic facts** (from law_knowledge_graph): Include? | No — that's a retrieval optimization for C3, not KG construction. |
| 4 | **Law scope**: Nuclear-only or broader? | Start with nuclear-relevant (AtG, StrlSchG, StrlSchV, BBergG, BImSchG, KrWG). Expand after validation. |
| 5 | **LLM model**: qwen3 8B or larger? | Start with qwen3:8b. German law extraction may benefit from larger model — benchmark on 10 paragraphs first. |
| 6 | **Batch vs streaming**: LLM call per paragraph or batch? | Per paragraph (simpler, resumable). Batch optimization later if needed. |
