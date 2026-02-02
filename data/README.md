# Data Directory

**Status**: 🟢 Ready for processing

---

## Contents

### ontology/
- **plan-ontology-v1.0.owl** – AI Planning Ontology (28 KB)
- **download_ontology.py** – Script to update/download ontologies

### Decommissioning_Files/
- **33 German PDFs** – Nuclear plant decommissioning documents (126 MB)
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
from kgbuilder.document import DocumentLoaderFactory

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
