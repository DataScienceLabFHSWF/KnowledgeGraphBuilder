# Data Directory

**Status**: Ready — all documents processed by pipeline.

---

## Contents

### ontology/
- **plan-ontology-v1.0.owl** — Nuclear decommissioning planning ontology (28 KB)
- Loaded into Fuseki at `http://localhost:3030` via `scripts/load_ontology_to_fuseki.py`

### Decommissioning_Files/
- **33 German PDFs** — Nuclear plant decommissioning documents (126 MB)
  - Applications (Genehmigungsantrag)
  - Safety reports (Sicherheitsbericht)
  - Environmental assessments (UVP)
  - Technical descriptions (Kurzbeschreibung)

---

## Quick Usage

### Load Ontology
```python
from rdflib import Graph

g = Graph()
g.parse("data/ontology/plan-ontology-v1.0.owl", format="xml")
```

### Load Documents
```python
from pathlib import Path
from kgbuilder.document.loaders import DocumentLoaderFactory

loader = DocumentLoaderFactory.get_loader("pdf")
docs = [loader.load(f) for f in Path("data/Decommissioning_Files").glob("*.pdf")]
```

### Update Ontology
```bash
python scripts/download_ontology.py
```

---

## Stats

| Item | Value |
|------|-------|
| Ontology Version | v1.0 |
| Ontology Size | 28 KB |
| Documents | 33 PDFs |
| Document Size | 126 MB |
| Language | German |
| Domain | Nuclear Decommissioning |

---

For detailed setup and processing examples, see [QUICKSTART_DATA.md](../QUICKSTART_DATA.md).
