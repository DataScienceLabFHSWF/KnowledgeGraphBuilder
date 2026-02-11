# Law Graph Quick Start Guide

## Prerequisites

1. **Data**: Law XML files in `data/law_html/`
   - Already downloaded: AtG, StrlSchG, StrlSchV, BBergG, BImSchG, KrWG, etc.
   - Each law has a `BJNR*.xml` file

2. **Services Running**:
   ```bash
   # Check Neo4j
   docker ps | grep neo4j
   
   # Check Qdrant
   docker ps | grep qdrant
   
   # Check Ollama (for embeddings)
   curl http://localhost:18134/api/tags
   ```

3. **Environment Variables** (`.env`):
   ```bash
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=kgbuilder
   QDRANT_URL=http://localhost:6333
   OLLAMA_URL=http://localhost:18134
   LAW_DATA_DIR=data/law_html
   LAW_OUTPUT_DIR=output/law_results
   ```

---

## Quick Start (5 Minutes)

### Step 1: Generate the Ontology
```bash
python scripts/build_law_ontology.py
```
**Output**: `data/ontology/law/law-ontology-v1.0.owl`

### Step 2: Run Pipeline on Sample Laws (AtG only)
```bash
# Dry run first (no database writes)
python scripts/build_law_graph.py --laws AtG --dry-run --skip-embed

# Real run (writes to Neo4j, skips embedding for speed)
python scripts/build_law_graph.py --laws AtG --skip-embed
```

**Expected output**:
```
======================================================================
LAW GRAPH PIPELINE COMPLETE
======================================================================
  Laws parsed:       1
  Entities created:  172  (1 Gesetzbuch + 111 Paragraf + 60 Abschnitt)
  Relations created: 111  (TEIL_VON relations)
  Docs embedded:     0    (skipped)
  Nodes in Neo4j:    172
  Edges in Neo4j:    111
  Time:              8.2s
======================================================================
```

### Step 3: Check Neo4j Graph
```cypher
// Count law entities
MATCH (n) WHERE n.graph_type = "law" RETURN count(n);

// See the AtG law
MATCH (g:Gesetzbuch {graph_type: "law"}) RETURN g;

// See all paragraphs
MATCH (p:Paragraf {graph_type: "law", law_abbreviation: "AtG"}) 
RETURN p.label, p.title LIMIT 10;

// See the graph structure
MATCH (para:Paragraf)-[r:TEIL_VON]->(law:Gesetzbuch) 
WHERE law.abbreviation = "AtG"
RETURN para, r, law LIMIT 20;
```

---

## Full Pipeline Run (All Nuclear Laws, With Embeddings)

### Run on All Nuclear-Relevant Laws
```bash
python scripts/build_law_graph.py \
  --laws AtG StrlSchG StrlSchV BBergG BImSchG KrWG
```

**Expected runtime**: ~10-15 minutes (includes embedding)

**Expected output**:
```
Laws parsed:       6
Entities created:  ~800-1000
Relations created: ~500-700
Docs embedded:     ~800 (paragraph-level)
Nodes in Neo4j:    ~1000
Edges in Neo4j:    ~700
```

### Check Qdrant Collection
```bash
curl http://localhost:6333/collections/lawgraph
```

**Expected response**:
```json
{
  "result": {
    "status": "green",
    "vectors_count": 800,
    "points_count": 800
  }
}
```

---

## Background Execution (Recommended for Large Runs)

```bash
# Run in background with logging
nohup python scripts/build_law_graph.py \
  --laws AtG StrlSchG StrlSchV BBergG BImSchG KrWG \
  > law_graph_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# Check progress
tail -f law_graph_*.log
```

---

## Output Files

After successful run, check `output/law_results/`:
```
output/law_results/
├── law_entities.json         # All extracted entities (JSON array)
├── law_relations.json        # All extracted relations (JSON array)
└── law_graph_summary.json    # Pipeline stats + law metadata
```

### Example `law_graph_summary.json`:
```json
{
  "timestamp": "2026-02-11T15:30:00",
  "laws": [
    {
      "abbreviation": "AtG",
      "title": "Gesetz über die friedliche Verwendung der Kernenergie...",
      "paragraphs": 111,
      "sections": 60,
      "cross_references": 87
    }
  ],
  "totals": {
    "entities": 172,
    "relations": 111,
    "embedded": 111,
    "nodes_stored": 172,
    "edges_stored": 111
  },
  "execution_time_seconds": 8.2
}
```

---

## Troubleshooting

### Error: `ModuleNotFoundError: No module named 'langchain_core'`
**Cause**: Main package imports assembly module which needs langchain.  
**Fix**: Run the script directly (it has its own sys.path setup):
```bash
python scripts/build_law_graph.py
```
Don't import from Python REPL.

### Error: `ConnectionRefusedError: [Errno 111] Connection refused` (Neo4j)
**Fix**: Start Neo4j:
```bash
docker-compose up -d neo4j
```

### Error: `Cannot connect to Qdrant`
**Fix**: Start Qdrant:
```bash
docker-compose up -d qdrant
```

### Embedding fails (Ollama errors)
**Fix**: Check Ollama is running and has the embedding model:
```bash
curl http://localhost:18134/api/tags
# Should show "qwen3-embedding" in list
```

### No XML files found
**Check**: Law data directory has XML files:
```bash
find data/law_html -name "BJNR*.xml"
# Should show paths like data/law_html/AtG/BJNR008140959.xml
```

If missing, run the downloader:
```bash
python scripts/download_law_xml_zips.py
```

---

## Next Steps After Pipeline Run

1. **Validate graph structure** (Neo4j Browser)
2. **Test paragraph retrieval** (Qdrant queries)
3. **Run semantic extraction** (Phase B - not yet implemented):
   ```bash
   # TODO: Add script for Phase B (LLM-based semantic extraction)
   python scripts/enrich_law_graph.py --laws AtG
   ```
4. **Integrate with GraphQAAgent** (C3 component)

---

## Performance Tips

### For faster development iterations:
```bash
# Skip embedding (saves ~60% time)
python scripts/build_law_graph.py --skip-embed --laws AtG

# Dry run (no database writes)
python scripts/build_law_graph.py --dry-run --laws AtG
```

### For production:
```bash
# Full run with all features
python scripts/build_law_graph.py --laws AtG StrlSchG StrlSchV
```

---

**Questions?** Check `IMPLEMENTATION_SUMMARY.md` or `Planning/LAW_GRAPH_IMPLEMENTATION.md`
