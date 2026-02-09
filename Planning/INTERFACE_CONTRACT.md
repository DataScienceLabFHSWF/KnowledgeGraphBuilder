# Interface Contract — External-Facing Schemas

Canonical reference for sibling repositories consuming KnowledgeGraphBuilder outputs.

**Consumers**:
- [GraphQAAgent](https://github.com/DataScienceLabFHSWF/GraphQAAgent) (reads Neo4j, Qdrant, Fuseki)
- [OntologyExtender](https://github.com/DataScienceLabFHSWF/OntologyExtender) (reads checkpoints, reads/writes Fuseki)

**Last Updated**: February 9, 2026

---

## 1. Neo4j Schema

**Driver**: `neo4j` Python driver, bolt protocol.

| Setting | Default | Env Override |
|---------|---------|-------------|
| URI | `bolt://localhost:7687` | `NEO4J_URI` |
| Auth | None (local) | `NEO4J_USERNAME` / `NEO4J_PASSWORD` |

### Node Labels

| Label | Purpose |
|-------|---------|
| `Entity` | Extracted entity from documents |
| `Document` | Source document reference |

### Entity Node Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | **Unique**. Deterministic hash: `ent_<sha256(label::entity_type)[:12]>` |
| `label` | `str` | Human-readable name (e.g., `"Kernkraftwerk Greifswald"`) |
| `entity_type` | `str` | Ontology class name (e.g., `"Facility"`, `"Regulation"`) |
| `confidence` | `float` | Extraction confidence 0.0–1.0 |
| `description` | `str` | LLM-generated description |

### Relationship Properties

Relationship types are **dynamic** — they come from `ExtractedRelation.predicate`
(e.g., `requiresPermit`, `hasComponent`, `locatedIn`).

| Property | Type | Description |
|----------|------|-------------|
| `predicate` | `str` | Relation type name (same as relationship type) |
| `confidence` | `float` | Extraction confidence 0.0–1.0 |

### Constraints

```cypher
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
  FOR (e:Entity) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT document_id_unique IF NOT EXISTS
  FOR (d:Document) REQUIRE d.id IS UNIQUE;
```

### Cypher Examples

```cypher
-- Get all entities
MATCH (e:Entity) RETURN e.id, e.label, e.entity_type, e.confidence;

-- Get 1-hop neighborhood
MATCH (e:Entity {id: $entity_id})-[r]-(neighbor:Entity)
RETURN e, r, neighbor;

-- Get entity by type
MATCH (e:Entity {entity_type: $type}) RETURN e ORDER BY e.confidence DESC;

-- Get all relationship types
MATCH ()-[r]->() RETURN DISTINCT type(r), count(*) AS cnt ORDER BY cnt DESC;
```

### Known Limitations

- **Evidence not stored in Neo4j** — `Evidence` objects (text_span, source_id) are only in checkpoint JSON. To get evidence for a Neo4j entity, cross-reference by `entity.id` against the checkpoint file.
- **No relationship IDs** — Neo4j relationships have no stored `id` property. Identify relations by `(source.id, type(r), target.id)` tuple.

---

## 2. Qdrant Schema

**Client**: `qdrant-client` Python package.

| Setting | Default | Env Override |
|---------|---------|-------------|
| URL | `http://localhost:6333` | `QDRANT_URL` |
| Collection | `"kgbuilder"` | `QDRANT_COLLECTION` |
| Distance | `COSINE` | — |

### Vector Configuration

| Parameter | Value |
|-----------|-------|
| Dimensions | Dynamic — queried from Ollama model at runtime |
| Model | `qwen3-embedding` (env: `OLLAMA_EMBED_MODEL`) |
| Expected dims | ~1024 (model-dependent, not hardcoded) |
| Fallback dim | 768 (if model probe fails) |

### Point Structure

```json
{
  "id": 42,                           // Sequential integer (NOT the chunk string ID)
  "vector": [0.012, -0.034, ...],     // float[] of model-dependent dimension
  "payload": {
    "id": "chunk_042",                // String chunk identifier
    "doc_id": "document_015",         // String document identifier
    "content": "Das Kernkraftwerk...",  // Chunk text
    "strategy": "fixed_size"          // Chunking strategy used
  }
}
```

### Payload Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Chunk identifier |
| `doc_id` | `str` | Source document identifier |
| `content` | `str` | Full chunk text |
| `strategy` | `str` | Chunking strategy (e.g., `"fixed_size"`) |

### Search Example

```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")
results = client.search(
    collection_name="kgbuilder",
    query_vector=embedding,
    limit=10,
)
for hit in results:
    chunk_id = hit.payload["id"]
    text = hit.payload["content"]
    doc = hit.payload["doc_id"]
    score = hit.score
```

---

## 3. Fuseki Schema

**Access**: HTTP REST + SPARQL.

| Setting | Default | Env Override |
|---------|---------|-------------|
| URL | `http://localhost:3030` | `FUSEKI_URL` |
| Dataset | `"kgbuilder"` | `FUSEKI_DATASET` |
| DB Type | TDB2 | — |

### Endpoints

| Endpoint | URL Pattern |
|----------|-------------|
| SPARQL query | `{url}/{dataset}/sparql` |
| SPARQL update | `{url}/{dataset}/update` |
| Data upload | `{url}/{dataset}` (POST with RDF content) |
| Dataset admin | `{url}/$/datasets` |

### FusekiOntologyService Methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `get_all_classes()` | `() -> list[str]` | Class labels as strings |
| `get_class_properties(label)` | `(str) -> list[tuple[str,str,str]]` | `(name, xsd_type, description)` |
| `get_class_relations(uri)` | `(str) -> list[str]` | Relation names |
| `get_all_relations()` | `() -> list[str]` | Relation labels |
| `get_class_hierarchy()` | `() -> list[tuple[str,str]]` | `(child_label, parent_label)` |
| `get_special_properties()` | `() -> dict[str,list[str]]` | Keys: `transitive`, `symmetric`, `functional`, `inverse` |

### Known Limitations

- **`add_triple()` not implemented** in `FusekiStore` — raises `NotImplementedError`. Use SPARQL UPDATE via `{url}/{dataset}/update` endpoint directly for write operations.
- **No OWL reasoning** — Fuseki TDB2 does not perform OWL inference by default. `rdfs:subClassOf*` traversal works in SPARQL but transitive closure of custom properties does not.
- **No `skos:altLabel`** in the current seed ontology — queries relying on SKOS synonyms will return empty unless the ontology is extended.

---

## 4. Checkpoint Format

Produced by `CheckpointManager.save_extraction_checkpoint()`.
File pattern: `checkpoint_{run_id}_extraction.json`

```json
{
  "metadata": {
    "run_id": "baseline_33docs_20260209_0929",
    "variant_name": "baseline",
    "checkpoint_time": "2026-02-09T09:29:28",
    "entities_count": 450,
    "relations_count": 120,
    "extraction_seconds": 342.5,
    "questions_processed": 12
  },
  "entities": [
    {
      "id": "ent_a1b2c3d4e5f6",
      "label": "Kernkraftwerk Greifswald",
      "entity_type": "Facility",
      "description": "A nuclear power plant in Mecklenburg-Vorpommern...",
      "aliases": ["KGR", "Greifswald NPP"],
      "properties": {},
      "confidence": 0.87,
      "evidence": [
        {
          "source_type": "local_doc",
          "source_id": "chunk_042",
          "text_span": "Das Kernkraftwerk Greifswald...",
          "confidence": 1.0
        }
      ]
    }
  ],
  "relations": [
    {
      "id": "rel_b2c3d4e5f6a7",
      "source_entity_id": "ent_a1b2c3d4e5f6",
      "target_entity_id": "ent_c3d4e5f6a7b8",
      "predicate": "requiresPermit",
      "properties": {},
      "confidence": 0.82,
      "evidence": [
        {
          "source_type": "local_doc",
          "source_id": "chunk_045",
          "text_span": "Für den Rückbau ist eine Genehmigung...",
          "confidence": 1.0
        }
      ]
    }
  ]
}
```

### Entity Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Deterministic hash ID: `ent_<hex12>` |
| `label` | `str` | Entity name |
| `entity_type` | `str` | Ontology class |
| `description` | `str` | LLM-generated description |
| `aliases` | `list[str]` | Alternative names |
| `properties` | `dict` | Additional key-value pairs |
| `confidence` | `float` | 0.0–1.0 |
| `evidence` | `list[Evidence]` | Source evidence list |

### Evidence Fields

| Field | Type | Description |
|-------|------|-------------|
| `source_type` | `str` | `"local_doc"`, `"web"`, or `"kg"` |
| `source_id` | `str` | Chunk ID, URL, or node ID |
| `text_span` | `str \| null` | Relevant text excerpt |
| `confidence` | `float` | Evidence confidence (default 1.0) |

### Relation Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Relation ID: `rel_<hex12>` |
| `source_entity_id` | `str` | Source entity ID |
| `target_entity_id` | `str` | Target entity ID |
| `predicate` | `str` | Relation type from ontology |
| `properties` | `dict` | Additional key-value pairs |
| `confidence` | `float` | 0.0–1.0 |
| `evidence` | `list[Evidence]` | Source evidence list |

---

## 5. Competency Questions Format

Used by `CompetencyQuestionValidator` and exported by the pipeline.

### KGB Internal Format (evaluation/qa_dataset.py)

```json
{
  "name": "Nuclear Decommissioning QA",
  "description": "...",
  "version": "1.0",
  "source": "expert",
  "questions": [
    {
      "id": "CQ_001",
      "question": "Welche Genehmigungen werden für den Rückbau benötigt?",
      "expected_answers": ["Stilllegungsgenehmigung", "Abbaugenehmigung"],
      "query_type": "entity",
      "difficulty": 3,
      "tags": ["permit", "regulation"],
      "metadata": {}
    }
  ]
}
```

### QAQuestion Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Question identifier, e.g. `"CQ_001"` |
| `question` | `str` | Natural language question |
| `expected_answers` | `list[str]` | Gold-standard answers |
| `query_type` | `str` | `"entity"`, `"relation"`, `"count"`, `"boolean"`, `"complex"` |
| `difficulty` | `int` | 1–5 scale |
| `tags` | `list[str]` | Topic tags |
| `metadata` | `dict` | Arbitrary extra data |

This is the **canonical format** — both GraphQAAgent and OntologyExtender
should read/write CQs in this structure.

---

## 6. Export Formats

### JSON Export (`kgbuilder-json`)

```json
{
  "metadata": {
    "exported_at": "2026-02-09T10:00:00",
    "format": "kgbuilder-json",
    "version": "1.0"
  },
  "statistics": {
    "node_count": 280,
    "edge_count": 156,
    "nodes_by_type": {"Facility": 12, "Regulation": 45, ...},
    "edges_by_type": {"requiresPermit": 23, ...},
    "avg_confidence": 0.74
  },
  "nodes": [
    {"id": "ent_...", "label": "...", "type": "Facility", "properties": {}, "metadata": {}}
  ],
  "edges": [
    {"id": "rel_...", "source_id": "ent_...", "target_id": "ent_...", "type": "requiresPermit", "properties": {}, "metadata": {}}
  ]
}
```

### JSON-LD Export

Uses `@context` with namespace `kg: http://kgbuilder.io/ontology#`.
Node `@type` is `kg:{entity_type}`. Properties: `label`, `confidence`, `description`, `evidence_count`.
Edges embedded as `kg:{predicate}: {"@id": "kg:{target_id}"}`.

### Turtle / RDF Export

Uses same `kg:` prefix. Nodes as `:entity_id a kg:Type ; rdfs:label "..." .`

---

## 7. Seed Ontology

**File**: `data/ontology/plan-ontology-v1.0.owl` (28 KB)
**Source**: AI Planning Ontology (adapted for nuclear decommissioning)
**Base namespace**: Defined in OWL file header

### Current State

- ~18 seed classes
- No `skos:altLabel` synonyms (plain `rdfs:label` only)
- Object properties defined with `rdfs:domain` / `rdfs:range`
- Datatype properties use XSD types

### Type Mapping (Fuseki → Python)

| XSD Type | Python Type |
|----------|-------------|
| `xsd:string` | `string` |
| `xsd:integer` | `integer` |
| `xsd:float`, `xsd:double` | `float` |
| `xsd:boolean` | `boolean` |
| `xsd:date` | `date` |
| `xsd:dateTime` | `datetime` |
