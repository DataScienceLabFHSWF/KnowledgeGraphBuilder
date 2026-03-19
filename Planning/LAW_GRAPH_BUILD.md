# Law Knowledge Graph — Build Process

**Date built**: 2026-03-19  
**Container**: `kgplatform-neo4j` (`bolt://localhost:7687`)  
**Vector store**: `kgplatform-qdrant` (`http://localhost:6333`, collection: `lawgraph`)  
**Embedding model**: `qwen3-embedding:latest` via `ollama-kgbuilder` (`http://localhost:18134`)

---

## Overview

The Law Knowledge Graph (Law KG) is a structured, paragraph-level representation of 17
German federal laws relevant to nuclear facility decommissioning. It is built **once** from
authoritative XML source files (gesetze-im-internet.de) and used throughout the KG building
pipeline to provide regulatory context during entity extraction and to create cross-domain
links between the decommissioning Knowledge Graph and the legal corpus.

The build is **purely structure-driven** — no LLM is used to extract entities from legal text.
Instead, the hierarchical XML structure (Gesetz → Abschnitt → Paragraf → Absatz) is parsed
directly. This makes the law graph deterministic, reproducible, and cheap to rebuild.

---

## Data Sources

### Law Corpus

All source files are downloaded from **[gesetze-im-internet.de](https://www.gesetze-im-internet.de)**
(the official German federal law database, maintained by the Federal Ministry of Justice).
Files are in the standardised **BJNR\*.xml** format (one XML file per law).

| Abbreviation | Full Name | Paragraphs | Sections | Cross-refs | Relevance to decommissioning |
|---|---|---|---|---|---|
| AtG | Atomgesetz | 101 | 7 | 392 | ★★★★★ Primary licensing law |
| StrlSchG | Strahlenschutzgesetz | 231 | 52 | 1 027 | ★★★★★ Radiation protection |
| StrlSchV | Strahlenschutzverordnung | 202 | 45 | 1 176 | ★★★★★ Radiation protection regulation |
| StandAG | Standortauswahlgesetz | 39 | 10 | 173 | ★★★★☆ Nuclear waste site selection |
| BImSchG | Bundes-Immissionsschutzgesetz | 119 | 14 | 616 | ★★★★☆ Emissions / environmental permits |
| UVPG | UVP-Gesetz | 80 | 15 | 320 | ★★★★☆ Environmental impact assessment |
| KrWG | Kreislaufwirtschaftsgesetz | 76 | 16 | 315 | ★★★☆☆ Waste management |
| VwVfG | Verwaltungsverfahrensgesetz | 122 | 22 | 240 | ★★★☆☆ Administrative procedure / Planfeststellung |
| BBergG | Bundesberggesetz | 192 | 45 | 728 | ★★★☆☆ Mining law (underground waste storage) |
| BauGB | Baugesetzbuch (BBauG) | 295 | 53 | 1 352 | ★★☆☆☆ Land-use / site planning |
| VwGO | Verwaltungsgerichtsordnung | 217 | 22 | 283 | ★★☆☆☆ Administrative court procedure |
| VVG | Versicherungsvertragsgesetz | 224 | 26 | 232 | ★★☆☆☆ Insurance / financial security |
| BGB | Bürgerliches Gesetzbuch | 2 541 | 289 | 2 273 | ★★☆☆☆ Civil liability / contracts |
| SprengG | Sprengstoffgesetz | 87 | 12 | 334 | ★★☆☆☆ Explosives (demolition) |
| AO | Abgabenordnung | 496 | 94 | 1 689 | ★☆☆☆☆ Tax law |
| OWiG | Ordnungswidrigkeitengesetz | 149 | 39 | 459 | ★☆☆☆☆ Administrative offences |
| StPO | Strafprozessordnung | 686 | 52 | 1 689 | ★☆☆☆☆ Criminal procedure |
| **Total** | | **5 657** | **813** | **13 298** | |

### Ontology

The law graph nodes are aligned to `data/ontology/legal/legal-foundations-merged.owl`,
which merges:
- **LKIF-Core** (Legal Knowledge Interchange Format, version 1.04, ESTRELLA project)
- **ELI** (European Legislation Identifier ontology)

---

## Pipeline

The build is implemented in `scripts/build_law_graph.py` and runs the following stages:

```
data/law_html/
  └── BJNR*.xml (one per law)
         │
   ┌─────▼──────────────────────────────────────────┐
   │  Stage 1: XML Parsing                           │
   │  LawXMLReader.parse_directory(Path)             │
   │  → LawDocument objects (one per law)            │
   │    .paragraphs()   → Norm objects (§§)          │
   │    .structure_nodes() → Abschnitte, Teile, ...  │
   │    .all_cross_references() → §§ cited           │
   └─────────────────────────────────────────────────┘
         │
   ┌─────▼──────────────────────────────────────────┐
   │  Stage 2: Structural Entity Extraction          │
   │  LawDocumentAdapter.to_structural_entities()    │
   │  Creates ExtractedEntity objects:               │
   │    type=Gesetzbuch  — one per law               │
   │    type=Abschnitt   — one per structural section│
   │    type=Paragraf    — one per § norm            │
   │  Entity IDs: SHA256({abbreviation}::{enbez})    │
   └─────────────────────────────────────────────────┘
         │
   ┌─────▼──────────────────────────────────────────┐
   │  Stage 3: Structural Relation Extraction        │
   │  LawDocumentAdapter.to_structural_relations()   │
   │  Creates ExtractedRelation objects:             │
   │    teilVon     — Paragraf → Gesetzbuch          │
   │    teilVon     — Abschnitt → Gesetzbuch         │
   │    referenziert — cross-law citations           │
   │  Edge IDs: SHA256({src}::{predicate}::{tgt})    │
   └─────────────────────────────────────────────────┘
         │
   ┌─────▼──────────────────────────────────────────┐
   │  Stage 4: Paragraph Embedding (Qdrant)          │
   │  Collection: "lawgraph"                         │
   │  Model: qwen3-embedding:latest                  │
   │  Format: paragraph title + text, batch_size=32  │
   │  Metadata: law, paragraph, title, text[:500]    │
   │  → Used for retrieval-augmented law context     │
   └─────────────────────────────────────────────────┘
         │
   ┌─────▼──────────────────────────────────────────┐
   │  Stage 5: Neo4j Storage                         │
   │  Neo4jGraphStore — kgplatform-neo4j :7687       │
   │  Node labels: Gesetzbuch, Abschnitt, Paragraf   │
   │  Relationship types: TEIL_VON, REFERENZIERT     │
   │  Idempotent: MERGE on node/edge id              │
   └─────────────────────────────────────────────────┘
         │
   ┌─────▼──────────────────────────────────────────┐
   │  Stage 6: Quality Validation                    │
   │  pySHACL validation against law ontology        │
   │  Results written to output/law_results/         │
   └─────────────────────────────────────────────────┘
```

### Running the Build

```bash
# Full build — all 17 laws (≈10–30 min depending on hardware)
python scripts/build_law_graph.py

# Specific laws only
python scripts/build_law_graph.py --laws AtG StrlSchG StrlSchV StandAG

# Without embedding (faster, no Qdrant; for graph structure only)
python scripts/build_law_graph.py --skip-embed

# Dry run (parse and extract, do not write to any database)
python scripts/build_law_graph.py --dry-run

# Background with timestamped log
nohup python scripts/build_law_graph.py \
  > output/law_results/build_$(date +%Y%m%d_%H%M%S).log 2>&1 &
```

Environment variables (from `.env` / Docker stack):

| Variable | Value | 
|----------|-------|
| `NEO4J_URI` | `bolt://localhost:7687` (`kgplatform-neo4j`) |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | `changeme` |
| `QDRANT_URL` | `http://localhost:6333` (`kgplatform-qdrant`) |
| `OLLAMA_URL` | `http://localhost:18134` (`ollama-kgbuilder`) |
| `LAW_DATA_DIR` | `data/law_html/` |

---

## Graph Schema

### Node Types

| Label | Properties | Count (confirmed) |
|-------|-----------|-------------------|
| `Gesetzbuch` | `id`, `label` (full name), `abbreviation`, `entity_type` | 17 |
| `Abschnitt` | `id`, `label` (title), `law`, `section_type`, `entity_type` | 789 |
| `Paragraf` | `id`, `label` (§ number + title), `law`, `enbez`, `text`, `entity_type` | 5 857 |

Node IDs are **deterministic SHA256 hashes**: `ent_{SHA256(label::type)[:12]}`

This ensures that rebuilding the law graph produces the same node IDs, which in turn
ensures the cross-domain links created by `KGLawLinker` remain valid across rebuilds.

### Relationship Types

| Type | Meaning | Example |
|------|---------|---------|
| `TEIL_VON` | Structural containment | `AtG_§7 --TEIL_VON--> AtG` |
| `REFERENZIERT` | Cross-law citation | `AtG_§7 --REFERENZIERT--> StrlSchG_§31` |

Cross-law citation edges are extracted from the `<xref>` elements in the XML.
Only inter-law references are stored (intra-law references are not stored to keep the graph manageable).

---

## How the Law Graph Is Used in the KG Builder

### During Entity Extraction (Law Context Augmentation)

When `LAW_GRAPH_ENABLED=true`, the `DiscoveryLoop` passes a `context_provider` callable
to the entity extractor. For each retrieved document chunk, the context provider:

1. Searches the Qdrant `lawgraph` collection for semantically similar paragraphs
2. Retrieves the top-k matching law paragraphs
3. Appends them to the extraction prompt:

```
[Document text]

--- Relevant Legal Context ---
§ 7 AtG (Genehmigung kerntechnischer Anlagen):
  Die Errichtung und der Betrieb von Kernkraftwerken bedürfen der Genehmigung...

§ 31 StrlSchG (Freigabe):
  Radioaktive Stoffe dürfen nur dann freigegeben werden, wenn ...
```

This allows the LLM extractor to identify regulatory references and domain entities
that would otherwise be missed in purely technical documents.

To enable/disable:
```bash
LAW_GRAPH_ENABLED=true  python scripts/full_kg_pipeline.py   # with law context
LAW_GRAPH_ENABLED=false python scripts/full_kg_pipeline.py   # without
```

### Post-Extraction: Cross-Domain Linking (`KGLawLinker`)

After each extraction run, `KGLawLinker.create_links()` scans all entities in
the decommissioning KG and creates three types of cross-domain edges:

| Edge type | Source | Logic | Confidence |
|-----------|--------|-------|-----------|
| `LINKED_GOVERNED_BY` | KG entity → Gesetzbuch/Paragraf | Tier 1: explicit citation in text | 0.90–0.95 |
| `LINKED_GOVERNED_BY` | KG entity → Gesetzbuch/Paragraf | Tier 2: keyword match on entity label | 0.70–0.85 |
| `LINKED_DEFINED_IN` | KG entity → Paragraf | Tier 3: entity type default fallback | 0.45–0.60 |

The 3-tier linking strategy ensures maximum recall while grading confidence by evidence quality.

### Linking Coverage (17 laws, 34 keyword patterns)

| Law | Keyword patterns | Entity type defaults |
|-----|-----------------|---------------------|
| AtG | Kernbrennstoff, Genehmigung, Stilllegung/Abbau/Rückbau, Kernanlage, Sicherung, Betreiber, Entsorgung/Endlager, Sicherheitsanalyse, Kernbrennstoff-Aufbewahrung | Facility, Operation, SafetySystem, NuclearMaterial, Permit |
| StrlSchG | radioaktiv, Freigabe, Dosisleistung, Überwachungsbereich, Kontamination, radioaktiver Abfall, Transport radioaktiv, Strahlenschutzbeauftragte, Dosimetrie | DomainRequirement, WasteCategory |
| StandAG | Endlager, Standortauswahl, Tiefenlagerung | — |
| UVPG | Umweltverträglichkeitsprüfung, UVP-Bericht, Scoping | — |
| VwVfG | Planfeststellung, öffentliche Auslegung, Verwaltungsakt | Process |
| VwGO | Verwaltungsgericht, Anfechtungsklage, aufschiebende Wirkung | — |
| VVG | Deckungsvorsorge, Haftpflichtversicherung | — |
| BauGB | Bebauungsplan, Bauleitplan | — |
| BGB | Schadensersatz, Haftung | — |
| BBergG | Bergbau, untertägig, Schacht | — |
| BImSchG | Emission, Immission | — |
| KrWG | konventioneller Abfall, Kreislaufwirtschaft | — |
| SprengG | Sprengstoff, Sprengarbeiten | — |
| AO, OWiG, StPO, StrlSchV | Citation detection only | — |

---

## Reproducibility

The law graph build is **fully deterministic**:
- Source data: fixed XML files in `data/law_html/` (version-controlled)
- Node IDs: SHA256 content hashes
- No LLM calls → no stochastic variation
- MERGE semantics in Neo4j → safe to re-run without duplicates

To rebuild from scratch:
```cypher
// Clear only law graph nodes (not decommissioning KG nodes):
MATCH (n) WHERE n:Gesetzbuch OR n:Abschnitt OR n:Paragraf
DETACH DELETE n;
```
Then re-run `build_law_graph.py`.

---

## Output Artefacts

After a successful build:

```
output/law_results/
├── build_YYYYMMDD_HHMMSS.log    — full console log
├── law_graph_results.json        — pipeline stats (entities, relations, time)
└── quality/
    └── shacl_report.ttl          — SHACL validation report
```

Neo4j (verified 2026-03-19, `MATCH (n:Gesetzbuch|Abschnitt|Paragraf) RETURN labels(n)[0], count(n)`):

| Label | Actual count |
|-------|----------------|
| Gesetzbuch | 17 |
| Abschnitt | 789 |
| Paragraf | 5 857 |

Qdrant collection `lawgraph`: **5 857 vectors** (one per paragraph, 4096-dim from `qwen3-embedding:latest`).

Note: 789 sections is slightly lower than the ~820 estimated from raw XML — some section nodes
were merged as duplicates during the MERGE-based Neo4j write (structural containers that
appear identically across editions of a law).

---

## Notes for the Paper

> The law knowledge graph provides a structured, paragraph-level representation of the
> regulatory framework governing nuclear facility decommissioning in Germany. It covers
> 17 federal laws comprising 5,857 paragraphs across 789 structural sections and 13,298
> cross-law citations (13,298 derived from XML `<xref>` elements; 5,657 unique § identifiers
> in the source XML; 5,857 nodes after splitting multi-absatz norms). Unlike the domain
> knowledge graph (built through iterative LLM-guided extraction), the law graph is derived
> deterministically from the formal XML structure of German federal law, with SHA256-based
> node IDs ensuring reproducibility across rebuilds. It serves a dual role: (1) providing
> regulatory context as retrieval-augmented input to the entity extractor (via
> `LawContextProvider` + Qdrant semantic search), and (2) enabling post-hoc cross-domain
> linking between extracted decommissioning entities and their governing legal provisions
> (via `KGLawLinker`, 34 keyword patterns across 17 laws, 3-tier confidence scoring).
