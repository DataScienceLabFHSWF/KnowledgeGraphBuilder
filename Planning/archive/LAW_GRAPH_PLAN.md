# Law Graph — Implementation Plan

Build a **Legal Knowledge Graph** from German regulatory texts using the existing
KGBuilder pipeline. The goal: link laws, paragraphs, cross-references, and legal
concepts into a navigable graph that can augment both the nuclear-decommissioning
KG and future legal QA.

---

## 1. Prior Art: `law_knowledge_graph` Repo

The team's existing [law_knowledge_graph](https://github.com/DataScienceLabFHSWF/law_knowledge_graph)
repo contains a working prototype. Key takeaways:

### What It Does

| Layer | Approach |
|-------|----------|
| **Data source** | Pre-processed JSON files from German federal law (gesetze-im-internet.de scraper). Each JSON = one paragraph: `{jurabk, paragraf, titel, gesetz, referenzen, amtabk, kurzue, langue}` |
| **Graph schema** | Two node types: `Gesetzbuch` (law book) and `Paragraf` (paragraph). Two edge types: `TEIL_VON` (paragraph → law book) and `REFERENZIERT` (paragraph → paragraph) |
| **Construction** | `setup.ipynb` — direct Cypher inserts from JSON (no LLM) |
| **GraphReader layer** | `graphreader_input.py` — chunks paragraph text, uses GPT-4o to extract `AtomicFact` + `KeyElement` nodes, imports into Neo4j alongside `Document → Chunk → AtomicFact → KeyElement` structure |
| **QA / retrieval** | `graphreader_agentic.py` — LangGraph agent using GraphReader pattern (rational plan → node selection → atomic fact check → chunk read → neighbor explore → answer reasoning) |
| **LLM** | OpenAI GPT-4-turbo / GPT-4o + text-embedding-3-small |

### What We Can Reuse

| Artifact | Reuse Strategy |
|----------|----------------|
| **JSON data format** (processed paragraphs) | Use as-is — write a `LawJSONLoader` that reads these files and produces KGB `Document` objects |
| **Cross-reference data** (`referenzen` field) | Import these as ground-truth `REFERENZIERT` relations — no LLM needed for structural relations |
| **Law book metadata** (`00_lawbooks/*.json`) | Import as `Gesetzbuch` entities with metadata (version, abbreviation, etc.) |
| **GraphReader pattern** | Interesting for GraphQAAgent, but out of scope for KGB. Note for C3 blueprint |

### What We Do Differently

| Aspect | `law_knowledge_graph` | KGB Law Graph |
|--------|----------------------|---------------|
| **Extraction** | GPT-4o atomic facts (unstructured) | Ontology-guided entity + relation extraction (our pipeline) |
| **Ontology** | None | Legal ontology defining classes + relations |
| **Embeddings** | OpenAI text-embedding-3-small | Ollama qwen3-embedding (local, no API cost) |
| **Graph structure** | Flat (Gesetzbuch → Paragraf) + GraphReader (Document → Chunk → AtomicFact → KeyElement) | Ontology-typed entities + relations (same as decommissioning KG) |
| **Storage** | Neo4j only | Neo4j + Qdrant + Fuseki (full KGB stack) |

---

## 2. Design Decisions

### 2.1 Same Pipeline, Different Config

The existing `full_kg_pipeline.py` is **ontology-agnostic** — it reads whatever
ontology is in Fuseki and generates extraction prompts from it. We need:

1. A **legal ontology** (OWL file)
2. A **legal document loader** (reads the JSON paragraph files)
3. A **config profile** mechanism (so `--profile legal` swaps ontology + documents + collection names)
4. Optionally, a **structural import** step (cross-references from JSON, no LLM needed)

### 2.2 Separate Graph Namespace

To keep the law graph distinct from the decommissioning KG:

| Resource | Decommissioning | Law Graph |
|----------|----------------|-----------|
| Fuseki dataset | `kgbuilder` | `lawgraph` |
| Qdrant collection | `kgbuilder` | `lawgraph` |
| Neo4j | Entity nodes (shared DB) | Entity nodes with `graph_type: "law"` property, or separate Neo4j database |
| Output dir | `output/kg_results` | `output/law_results` |

**Recommendation**: Use separate Fuseki dataset + separate Qdrant collection +
label-based separation in Neo4j (add `graph_type` property to all Entity nodes).
This keeps everything in the same infra while being queryable independently.

### 2.3 Two-Phase Construction

**Phase A — Structural Import** (no LLM, fast):
- Parse JSON files → create `Gesetzbuch` and `Paragraf` entities
- Import `TEIL_VON` and `REFERENZIERT` relations from structured data
- Embed paragraph text into Qdrant

**Phase B — Ontology-Guided Extraction** (LLM, same pipeline):
- Load legal ontology from Fuseki
- Run discovery loop over embedded paragraphs
- Extract typed entities (LegalConcept, Obligation, Definition, etc.)
- Extract semantic relations (defines, obliges, amends, etc.)

Phase A gives us a complete structural graph quickly. Phase B enriches it with
semantic content using the existing pipeline.

---

## 3. Legal Ontology Design

A minimal legal ontology for German federal law. Start small, extend via
OntologyExtender later.

### 3.1 Classes

```
owl:Thing
├── Gesetzbuch          # Law book (AtG, StrlSchV, BImSchG, ...)
│   ├── Bundesgesetz    # Federal law
│   └── Verordnung      # Regulation / ordinance
├── Paragraf            # §, article, section
│   ├── Artikel         # Used in some laws instead of §
│   └── Absatz          # Sub-paragraph (optional granularity)
├── LegalConcept        # Abstract legal concept defined in law
│   ├── Definition      # Explicitly defined term (Legaldefinition)
│   ├── Obligation      # Legal duty / requirement
│   ├── Permission      # Legal permission / authorization
│   └── Prohibition     # Legal prohibition
├── LegalActor          # Entity mentioned as responsible/affected
│   ├── Behörde         # Authority (BfS, BMU, etc.)
│   └── Betreiber       # Operator / licensee
└── LegalReference      # Cross-reference to another paragraph/law
```

### 3.2 Relations (ObjectProperties)

| Relation | Domain | Range | Description |
|----------|--------|-------|-------------|
| `teilVon` | Paragraf | Gesetzbuch | Paragraph belongs to law |
| `referenziert` | Paragraf | Paragraf | Cross-reference between paragraphs |
| `definiert` | Paragraf | Definition | Paragraph defines a legal term |
| `verpflichtet` | Paragraf | Obligation | Paragraph establishes an obligation |
| `erlaubt` | Paragraf | Permission | Paragraph grants a permission |
| `verbietet` | Paragraf | Prohibition | Paragraph establishes a prohibition |
| `zuständig` | Behörde | Obligation | Authority responsible for obligation |
| `betrifft` | Obligation | LegalActor | Obligation applies to actor |
| `ändert` | Gesetzbuch | Gesetzbuch | Law amends another law |
| `aufgehobenDurch` | Paragraf | Paragraf | Paragraph repealed by another |

### 3.3 Datatype Properties

| Property | Domain | XSD Type | Description |
|----------|--------|----------|-------------|
| `abkürzung` | Gesetzbuch | string | Official abbreviation (AtG, StrlSchV) |
| `langtext` | Gesetzbuch | string | Full title |
| `version` | Gesetzbuch | string | Version identifier |
| `letzteÄnderung` | Gesetzbuch | date | Last amendment date |
| `gesetzestext` | Paragraf | string | Full paragraph text |
| `nummer` | Paragraf | string | Paragraph number (§ 7, Art. 3) |
| `titel` | Paragraf | string | Paragraph title |

---

## 4. Implementation Steps

### Step 1: Legal Ontology OWL File (2h)

Create `data/ontology/law-ontology-v1.0.owl` with the classes and relations above.
Use the same OWL patterns as the existing `plan-ontology-v1.0.owl`.

**Deliverable**: `data/ontology/law-ontology-v1.0.owl`

### Step 2: Law JSON Document Loader (2h)

A new loader that reads the `processed_jsons/` format from `law_knowledge_graph`:

```python
# src/kgbuilder/document/loaders/law_json.py

@dataclass
class LawJSONLoader:
    """Load German law paragraphs from preprocessed JSON files.
    
    Expected JSON format (from law_knowledge_graph repo):
    {
        "jurabk": "AtG",
        "paragraf": "§ 7",
        "titel": "Genehmigung von Anlagen",
        "gesetz": "Wer eine ortsfeste Anlage...",
        "amtabk": "AtG",
        "kurzue": "Atomgesetz",
        "langue": "Gesetz über die friedliche Verwendung...",
        "referenzen": [["§ 9", "AtG"], ["§ 12", "StrlSchV"]]
    }
    """
    
    def load(self, path: Path) -> Document:
        """Load a single law JSON file as a Document."""
        ...
    
    def load_directory(self, dir_path: Path) -> list[Document]:
        """Load all JSON files from a directory."""
        ...
    
    def extract_structural_relations(
        self, docs: list[Document]
    ) -> list[ExtractedRelation]:
        """Extract TEIL_VON and REFERENZIERT relations from JSON metadata.
        
        These are ground-truth structural relations — no LLM needed.
        """
        ...
```

The loader produces `Document` objects with metadata:
- `doc.id` = `"{jurabk}_{paragraf}"` (e.g., `"AtG_§7"`)
- `doc.content` = `gesetz` (the paragraph text)
- `doc.metadata` = `{jurabk, paragraf, titel, amtabk, kurzue, langue, referenzen}`

**Deliverable**: `src/kgbuilder/document/loaders/law_json.py` + tests

### Step 3: Structural Import Script (2h)

A script that does Phase A — the fast, no-LLM import:

```bash
python scripts/import_law_structure.py \
    --law-data data/law_jsons/ \
    --lawbook-data data/law_jsons/00_lawbooks/ \
    --collection lawgraph
```

This script:
1. Reads all JSON files
2. Creates `Gesetzbuch` and `Paragraf` Entity nodes in Neo4j (with `graph_type: "law"`)
3. Creates `TEIL_VON` relation edges (paragraph → law book)
4. Creates `REFERENZIERT` relation edges (paragraph → paragraph)
5. Embeds all paragraph texts into Qdrant collection `"lawgraph"`

**Deliverable**: `scripts/import_law_structure.py`

### Step 4: Pipeline Profile Mechanism (2h)

Add a `--profile` flag to `full_kg_pipeline.py`:

```bash
# Default (decommissioning)
python scripts/full_kg_pipeline.py

# Legal graph  
python scripts/full_kg_pipeline.py --profile legal
```

Profile configs stored in `data/profiles/`:

```json
// data/profiles/legal.json
{
    "ontology_dataset": "lawgraph",
    "ontology_path": "data/ontology/law-ontology-v1.0.owl",
    "document_dir": "data/law_jsons",
    "document_extensions": [".json"],
    "vector_collection": "lawgraph",
    "output_dir": "output/law_results",
    "questions_path": "data/law_questions.json",
    "neo4j_graph_type": "law"
}
```

The profile is just a `PipelineConfig` overlay — merge profile values with
defaults, then override with any explicit CLI args.

**Deliverable**: Profile mechanism in `full_kg_pipeline.py`, `data/profiles/legal.json`

### Step 5: Legal Competency Questions (1h)

Initial set of questions to drive extraction:

```json
{
    "name": "German Nuclear Law QA",
    "version": "1.0",
    "questions": [
        {
            "id": "LCQ_001",
            "question": "Welche Genehmigungen sind nach § 7 AtG erforderlich?",
            "expected_answers": ["Errichtungsgenehmigung", "Betriebsgenehmigung"],
            "query_type": "entity",
            "difficulty": 2,
            "tags": ["permit", "AtG"]
        },
        {
            "id": "LCQ_002",
            "question": "Welche Behörde ist für die Genehmigung kerntechnischer Anlagen zuständig?",
            "expected_answers": ["Bundesamt für die Sicherheit der nuklearen Entsorgung"],
            "query_type": "entity",
            "difficulty": 2,
            "tags": ["authority", "AtG"]
        },
        {
            "id": "LCQ_003",
            "question": "Welche Paragraphen des AtG verweisen auf die StrlSchV?",
            "expected_answers": [],
            "query_type": "relation",
            "difficulty": 3,
            "tags": ["cross-reference", "AtG", "StrlSchV"]
        }
    ]
}
```

**Deliverable**: `data/law_questions.json`

### Step 6: Fuseki Dataset Setup (0.5h)

Add `lawgraph` dataset to Fuseki config or create at startup:

```bash
# Create dataset
curl -X POST http://localhost:3030/$/datasets \
  -d "dbName=lawgraph&dbType=tdb2"

# Upload ontology
curl -X POST http://localhost:3030/lawgraph/data \
  -H "Content-Type: application/rdf+xml" \
  --data-binary @data/ontology/law-ontology-v1.0.owl
```

Add to docker-compose or init script.

**Deliverable**: Updated startup/init scripts

### Step 7: End-to-End Test (2h)

1. Obtain or create sample law JSON files (AtG, StrlSchV — ~20 paragraphs)
2. Run structural import → verify graph in Neo4j
3. Run ontology-guided extraction → verify enriched entities
4. Validate combined graph

**Deliverable**: Test data, validation results

---

## 5. Data Acquisition

### Option A: Reuse `law_knowledge_graph` Data

The team's repo has `processed_jsons/` with pre-scraped German federal law.
Copy the relevant files (nuclear law subset):

```
AtG (Atomgesetz)
StrlSchV (Strahlenschutzverordnung)  
StrlSchG (Strahlenschutzgesetz)
GenTG (Gentechnikgesetz) — optional
BImSchG (Bundes-Immissionsschutzgesetz) — optional
```

### Option B: Fresh Scrape from gesetze-im-internet.de

The data comes from the official XML/JSON dump at:
- https://www.gesetze-im-internet.de/gii-toc.xml
- Individual law exports as XML

A small scraper script could fetch the target laws. But Option A is faster.

### Recommendation

**Start with Option A** — copy the existing data for target laws. It's already
in the right format. Later, we can add a fetcher for additional laws.

---

## 6. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     LAW GRAPH PIPELINE                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  data/law_jsons/                                                │
│  ├── processed_jsons/          ┌──────────────────────┐         │
│  │   ├── AtG_§1.json  ───────▶│  LawJSONLoader       │         │
│  │   ├── AtG_§7.json           │                      │         │
│  │   └── StrlSchV_§1.json      │  → Documents         │         │
│  └── 00_lawbooks/              │  → Structural rels   │         │
│      └── AtG.json              └──────────┬───────────┘         │
│                                           │                      │
│              ┌────────────────────────────┤                      │
│              ▼                            ▼                      │
│  ┌────────────────────┐    ┌──────────────────────────┐         │
│  │ Phase A: Structural │    │ Phase B: Ontology-Guided │         │
│  │ (No LLM, fast)      │    │ (Full KGB pipeline)      │         │
│  │                      │    │                          │         │
│  │ • Gesetzbuch nodes   │    │ • Load law-ontology.owl  │         │
│  │ • Paragraf nodes     │    │ • Discovery loop         │         │
│  │ • TEIL_VON edges     │    │ • Extract LegalConcepts  │         │
│  │ • REFERENZIERT edges │    │ • Extract Obligations    │         │
│  │ • Embed → Qdrant     │    │ • Enrich + validate      │         │
│  └──────────┬───────────┘    └──────────┬───────────────┘         │
│             │                           │                        │
│             └────────────┬──────────────┘                        │
│                          ▼                                       │
│              ┌───────────────────────┐                           │
│              │    Neo4j (lawgraph)    │                           │
│              │    Qdrant (lawgraph)   │                           │
│              │    Fuseki (lawgraph)   │                           │
│              └───────────────────────┘                           │
│                          │                                       │
│                          ▼                                       │
│              ┌───────────────────────┐                           │
│              │  GraphQAAgent (C3)    │  ← optional FusionRAG     │
│              │  queries both graphs  │     with legal retrieval  │
│              └───────────────────────┘                           │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. Integration with GraphQAAgent

Once the law graph exists, the GraphQAAgent FusionRAG pipeline can query both
the decommissioning KG and the law graph:

1. **Legal reference detector**: Regex / simple classifier to detect `§ N LawAbbr`
   patterns in user questions
2. **Law graph retriever**: If a legal reference is detected, query the law graph
   for the exact paragraph text + related paragraphs
3. **Context merger**: Combine domain KG context with legal paragraph context
   before sending to the answer generator

This is a C3 (GraphQAAgent) feature — we just need the law graph to exist.

---

## 8. Effort Estimate

| Step | Effort | Dependencies |
|------|--------|-------------|
| 1. Legal ontology OWL | 2h | None |
| 2. LawJSONLoader | 2h | None |
| 3. Structural import script | 2h | Step 2 |
| 4. Pipeline profile mechanism | 2h | None |
| 5. Competency questions | 1h | Step 1 |
| 6. Fuseki dataset setup | 0.5h | None |
| 7. End-to-end test | 2h | Steps 1-6 |
| **Total** | **~11.5h** | |

Steps 1, 2, 4 can be parallelized.

---

## 9. Open Questions

1. **Data licensing**: Can we redistribute the `processed_jsons` from
   `law_knowledge_graph`? (gesetze-im-internet.de data is public domain.)
2. **Scope**: Start with nuclear-relevant laws only (AtG, StrlSchV, StrlSchG)
   or include broader German federal law?
3. **Neo4j separation**: Single database with `graph_type` property, or separate
   Neo4j database? (Community edition supports only one DB — label-based it is.)
4. **Atomic facts**: The existing repo's GraphReader layer extracts atomic facts.
   Do we want that *in addition* to ontology-guided extraction, or just the
   ontology approach?
5. **Absatz granularity**: Import at paragraph level (§ 7) or sub-paragraph
   level (§ 7 Abs. 1)? The JSON data is at paragraph level.

### Recommended Answers

1. Public domain — yes.
2. Start nuclear (AtG, StrlSchV, StrlSchG), expand later.
3. Label-based (`graph_type: "law"` property on Entity nodes).
4. Ontology approach only — atomic facts are a retrieval optimization for C3,
   not a KG construction concern.
5. Start at paragraph level — sub-paragraph extraction can come from
   the ontology-guided LLM pass.
