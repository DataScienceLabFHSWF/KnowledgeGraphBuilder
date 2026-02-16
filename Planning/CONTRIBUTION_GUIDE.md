# Contribution Guide — KnowledgeGraphBuilder

> Where help is needed, what each contribution area requires,
> and how to get started.

---

## Overview

This project builds an ontology-driven Knowledge Graph for nuclear
decommissioning and validates it using SHACL constraints, structural
graph metrics, and extraction quality evaluation. The areas below are
ordered by impact on the thesis.

---

## Area 1 — SHACL Shapes for the Law Ontology *(high impact, SHACL expertise)*

### Status
- The validator infrastructure is complete (`pyshacl` integration, SHACL2FOL
  theorem prover, shape generator, scorer).
- **Zero hand-crafted SHACL shape files exist.** The auto-generator only
  produces `sh:NodeShape` + `sh:targetClass` — no property constraints,
  no cardinality, no patterns.
- The 3 shapes embedded in `plan-ontology-v2.0.owl` are trivial
  (`rdfs:label sh:minCount 1` only).

### What's Needed

Create `data/ontology/law/law-shapes.ttl` (Turtle) covering the 13 classes
in `law-ontology-v1.0.owl`:

| Shape | Key Constraints Needed |
|-------|----------------------|
| `GesetzbuchShape` | `abkuerzung` required, `sh:pattern "^(AtG\|StrlSchG\|…)$"`, `langtext` required, `sh:closed true` |
| `ParagrafShape` | `nummer` required + `sh:pattern "^§\\s*\\d+"`, `gesetzestext` required, `teilVon` → `sh:class :Gesetzbuch`, `sh:minCount 1` |
| `AbsatzShape` | `nummer` required, `teilVon` → `sh:class :Paragraf` |
| `ObligationShape` / `PermissionShape` / `ProhibitionShape` | `sh:xone` (exactly one of the three subtypes per `LegalConcept`), `betrifft` → `sh:class :LegalActor` |
| `BehoerdeShape` / `BetreiberShape` | `sh:not` each other (disjointness) |
| `referenziertShape` | domain + range both `Paragraf`, referential integrity via `sh:sparql` |

Also create `data/ontology/domain/domain-shapes.ttl` for the 12
decommissioning classes in `plan-ontology-v2.0.owl` (currently only 3 have
shapes and those are trivially "must have a label").

### Severity levels
Use `sh:Warning` for missing optional fields (descriptions), `sh:Violation`
for missing required fields (IDs, types, key relations), `sh:Info` for
style suggestions.

### How to test
```bash
PYTHONPATH=src python -c "
from kgbuilder.validation.shacl_validator import SHACLValidator
v = SHACLValidator()
# point to Neo4j store + your shapes file
"
```

### Files to edit/create
- `data/ontology/law/law-shapes.ttl` — **CREATE** (primary deliverable)
- `data/ontology/domain/domain-shapes.ttl` — **CREATE**
- `src/kgbuilder/validation/scorer.py` L107–113 — **FIX** `_FileOntologyService`
  to parse `rdfs:domain`/`rdfs:range` (currently returns empty lists, making
  auto-generated shapes useless)

---

## Area 2 — Gold Standard Dataset *(highest scientific impact, domain expertise)*

### Status
- Only 9 competency questions exist in `data/evaluation/competency_questions.json`
- 2 QA benchmark template entries in `data/evaluation/qa_benchmark_template.json`
- **No annotated extraction ground truth** — cannot compute entity/relation
  extraction precision, recall, or F1.

### What's Needed

1. **Annotated reference documents** (3–5 documents):
   - Mark entity spans in source text with bounding offsets
   - Assign entity types from the ontology
   - Identify relations between marked entities (subject, predicate, object)
   - Format: JSON per the schema in `qa_benchmark_template.json`

2. **Expanded competency questions** (target: 50+):
   - Cover all 13 law ontology classes + 12 domain classes
   - Include expected SPARQL query + expected result set
   - Tag by difficulty (easy/medium/hard) and ontology class

3. **Entity resolution pairs**:
   - Manually identify which extracted entities in Neo4j refer to the same
     real-world concept
   - Creates ground truth for deduplication precision/recall

### Where to put it
- `data/evaluation/gold_standard/` — annotated documents (use `scripts/gold_annotator.py` to create templates)
- `data/evaluation/competency_questions.json` — expand existing
- `data/evaluation/entity_resolution_pairs.json` — new

### Quick annotator (scaffold)
A static HTML annotator is available at `scripts/gold_annotator.py`.

Example use:
```bash
python scripts/gold_annotator.py --text-file data/law_html/0001.txt --doc-id doc_0001 --out /tmp/doc_0001_annot.html --open
```
Open the generated HTML, highlight spans and download the JSON into `data/evaluation/gold_standard/`.


---

## Area 3 — Consistency Checker Domain Rules *(medium impact, domain expertise)*

### Status
The consistency checker (`src/kgbuilder/validation/consistency_checker.py`)
has **hardcoded rules from a generic Person/Organization ontology** that are
irrelevant to nuclear decommissioning:

- **Incompatible type pairs** (L219–221): `("Person", "Organization")`,
  `("Person", "Location")`, `("Organization", "Location")` — should be
  domain-specific
- **Functional properties** (L296–301): `["birthDate", "deathDate",
  "birthPlace", "SSN", "email"]` — should be from the law/domain ontology

### What's Needed

Replace with domain-appropriate rules:

```python
# Incompatible type pairs for nuclear decommissioning
INCOMPATIBLE_TYPES = [
    ("Bundesgesetz", "Verordnung"),
    ("Obligation", "Permission"),
    ("Obligation", "Prohibition"),
    ("Permission", "Prohibition"),
    ("Behoerde", "Betreiber"),
    ("Facility", "Regulation"),
    ("Paragraf", "Gesetzbuch"),
]

# Functional properties (at most 1 value per entity)
FUNCTIONAL_PROPERTIES = [
    "abkuerzung", "nummer", "gesetzestext",
    "teilVon",  # a Paragraf belongs to exactly one Gesetzbuch
    "aufgehobenDurch",
]
```

Also add:
- **Referential integrity** checks for `referenziert` edges
- **Temporal consistency**: `letzteAenderung` ≤ today, `aufgehobenDurch`
  implies the repealing paragraph exists
- **German-language label validation**: umlauts handled correctly,
  no mojibake

### File to edit
- `src/kgbuilder/validation/consistency_checker.py` — lines 219–221 and
  296–301

---

## Area 4 — Domain-Range Rule Auto-Generation *(medium impact, ontology expertise)*

### Status
The rules engine (`src/kgbuilder/validation/rules_engine.py`) can
auto-generate `InversePropertyRule`, `TransitiveRule`, and
`FunctionalPropertyRule` from the ontology. But `DomainRangeRule` is
**never auto-generated** — it requires manual setup despite domain/range
declarations existing in the OWL ontology.

### What's Needed
Extend `RulesEngine.from_ontology_service()` (L402–460) to also read
`rdfs:domain` and `rdfs:range` from the ontology service and auto-create
`DomainRangeRule` instances.

### File to edit
- `src/kgbuilder/validation/rules_engine.py` — `from_ontology_service()` factory

---

## Area 5 — SHACL Shape Generator OWL Coverage *(medium impact, OWL/SHACL expertise)*

### Status
`SHACLShapeGenerator.generate()` documents support for `rdfs:subClassOf` →
`sh:node` translation but **never implements it** (noted in docstring at L15).

Additionally missing:
- `owl:Restriction` + `owl:someValuesFrom` → `sh:minCount 1` + `sh:class`
- `owl:Restriction` + `owl:cardinality` → `sh:minCount`/`sh:maxCount`
- `owl:unionOf` → `sh:or`
- `owl:disjointWith` → `sh:not`
- `owl:equivalentClass` → shape alias

The plan ontology has ~10+ `owl:someValuesFrom` restrictions that are
completely ignored during shape generation.

### File to edit
- `src/kgbuilder/validation/shacl_generator.py`

---

## Area 6 — Ontology Alignment & Competency *(domain expertise)*

### Status
The ontology files exist but have gaps:
- `law-ontology-v1.0.owl`: No `owl:Restriction` axioms, no special property
  characteristics (`owl:TransitiveProperty` etc.)
- `plan-ontology-v2.0.owl`: Has some restrictions but minimal SHACL

### What's Needed
- Add `owl:TransitiveProperty` to `teilVon` (part-of is transitive)
- Add `owl:InverseFunctionalProperty` to `abkuerzung` (abbreviation is unique)
- Add `owl:someValuesFrom` restrictions where classes require at least one
  property (e.g., every `Gesetzbuch` must have at least one `Paragraf`)
- Map to standard vocabularies (ELI for legislation, CCO for process)

### Files to edit
- `data/ontology/law/law-ontology-v1.0.owl`
- `data/ontology/domain/plan-ontology-v2.0.owl`

---

## Quick-Start for Contributors

```bash
# Clone and setup
git clone <repo> && cd KnowledgeGraphBuilder
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start services (Neo4j must be running for validation tests)
docker compose up -d

# Run tests
PYTHONPATH=src pytest tests/ -q --no-cov

# Check existing SHACL shapes
find data/ontology -name "*.ttl" -o -name "*.shacl" | head

# See the current graph
# Neo4j Browser: http://localhost:7474 (neo4j/changeme)
# Run: MATCH (n) RETURN labels(n), count(n) ORDER BY count(n) DESC
```

---

## Contribution Checklist

- [ ] **SHACL shapes** for law ontology (`law-shapes.ttl`)
- [ ] **SHACL shapes** for domain ontology (`domain-shapes.ttl`)
- [ ] **Gold standard** annotated documents (3–5 docs)
- [ ] **50+ competency questions** with SPARQL + expected results
- [ ] **Entity resolution pairs** ground truth
- [ ] **Consistency checker** domain-specific type + property rules
- [ ] **Domain-range rules** auto-generation from OWL
- [ ] **OWL restrictions** in law and domain ontologies
- [ ] **SHACL generator** fix: `rdfs:subClassOf` → `sh:node`
- [ ] **Scorer** fix: `_FileOntologyService` property parsing
