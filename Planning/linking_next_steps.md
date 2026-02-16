# Law-Domain Linking — Next Steps & Implementation Plan

**Date**: 2026-02-16  
**Status**: Current linking produces only 5 edges (all `LINKED_GOVERNED_BY → AtG`)

---

## 1. Current State

### What Exists

The rule-based linker (`scripts/link_kg_to_laws.py`) finds explicit law citations
in domain entity labels and properties using regex patterns.

**Result**: Out of 530 domain entities, only 5 had recognisable law references,
all pointing to AtG (via keywords like "Strahlenschutzgesetz" or "§ 4 Absatz 1").

### Why It Fails

| Problem | Impact |
|---|---|
| **Regex only matches explicit citations** (`§ X AtG`, law abbreviations) | Only 30/530 entities contain such text |
| **No concept-to-law mapping** | "Kernbrennstoff" should link to AtG § 2 (definitions) but doesn't because the entity label contains no `§` reference |
| **No paragraph-level linking** | Cross-links point to Gesetzbuch (law) level, not specific paragraphs |
| **No entity-type-based inference** | All 26 Facilities should be linked to AtG § 7 (licensing) but the linker doesn't know this |
| **Orphan node bug** | `MERGE` on `{abbreviation}` created a duplicate Gesetzbuch without an `id` — **Fixed** |
| **No semantic similarity** | Can't match "Abbau" (decommissioning) to "AtG § 7 Abs. 3" (decommissioning license) by content |

---

## 2. Short-Term Fixes (Regex Extension)

### 2a. Keyword-to-Law Mapping (Implemented)

Add a **keyword-based linking strategy** that maps domain-specific German terms to
their governing law paragraphs. This doesn't require any NLP — just domain knowledge.

```python
KEYWORD_LAW_MAPPINGS = [
    # Keyword in entity label → (law_code, section, relationship_type, confidence)
    (r"Kernbrennstoff", "AtG", "§ 2", "DEFINED_IN", 0.85),
    (r"Genehmigung|genehmigt", "AtG", "§ 7", "GOVERNED_BY", 0.80),
    (r"Stilllegung|Abbau|Rückbau|Demontage", "AtG", "§ 7 Abs. 3", "GOVERNED_BY", 0.85),
    (r"kerntechnisch|Kernanlage|Kernkraftwerk", "AtG", "§ 7", "GOVERNED_BY", 0.80),
    (r"Sicherung|Objektschutz|Zutrittskontrolle", "AtG", "§ 7 Abs. 2", "GOVERNED_BY", 0.75),
    (r"radioaktiv|Aktivität", "StrlSchG", None, "GOVERNED_BY", 0.70),
    (r"Freigabe|Freigabewert", "StrlSchG", "§ 31", "GOVERNED_BY", 0.85),
    (r"Dosisleistung|Strahlenexposition|Strahlung", "StrlSchG", "§ 5", "GOVERNED_BY", 0.80),
    (r"Überwachungsbereich|Kontrollbereich|Strahlenschutzbereich", "StrlSchG", "§ 52", "GOVERNED_BY", 0.80),
    (r"Abfall.*radioaktiv|radioaktiv.*Abfall", "StrlSchG", "§ 9a", "GOVERNED_BY", 0.80),
    (r"Entsorgung|Endlager|Zwischen[- ]?lager", "AtG", "§ 9a", "GOVERNED_BY", 0.80),
    (r"Emission|Immission", "BImSchG", None, "GOVERNED_BY", 0.75),
    (r"Bergbau|untertägig|Schacht", "BBergG", None, "GOVERNED_BY", 0.70),
    (r"Abfall.*konventionell|Kreislaufwirtschaft", "KrWG", None, "GOVERNED_BY", 0.70),
    (r"Betreiber|Betriebsgenehmigung", "AtG", "§ 7", "GOVERNED_BY", 0.75),
    (r"Kontamination|dekontaminier", "StrlSchG", "§ 64", "GOVERNED_BY", 0.75),
]
```

**Expected yield**: ~80-120 additional links (estimated from keyword analysis).

### 2b. Entity-Type-to-Law Mapping

Map entity types directly to their most likely governing laws:

```python
TYPE_LAW_MAPPINGS = {
    "Facility": [("AtG", "§ 7", "GOVERNED_BY", 0.80)],
    "Operation": [("AtG", "§ 7 Abs. 3", "GOVERNED_BY", 0.80)],
    "DomainRequirement": [("StrlSchG", None, "GOVERNED_BY", 0.65)],
    "Action": [("AtG", "§ 7", "GOVERNED_BY", 0.60)],
    "Organization": [("AtG", "§ 7", "GOVERNED_BY", 0.55)],
}
```

**Expected yield**: ~100+ additional links for typed entities.

---

## 3. Medium-Term: Paragraph-Level Linking

Currently, cross-links only point to the Gesetzbuch root node (e.g., "AtG"). This
is too coarse — a facility should link to _specific_ paragraphs.

### Strategy: Match Keywords Against Paragraph IDs

- Law paragraphs have IDs like `AtG_S_7` (= AtG § 7)
- When keyword mapping specifies a section (e.g., `"§ 7 Abs. 3"`), resolve to the
  specific Paragraf node: `AtG_S_7`

```python
def resolve_paragraph_node(law_code: str, section: str | None) -> str:
    """Resolve law code + section to a Paragraf node ID.
    
    Examples:
        ("AtG", "§ 7") → "AtG_S_7"
        ("StrlSchG", "§ 31") → "StrlSchG_S_31"
        ("AtG", "§ 7 Abs. 3") → "AtG_S_7"  (paragraph level)
        ("AtG", None) → "AtG"  (Gesetzbuch level)
    """
    if section is None:
        return law_code
    # Extract paragraph number from section string
    m = re.match(r"§?\s*(\d+\w*)", section)
    if m:
        return f"{law_code}_S_{m.group(1)}"
    return law_code
```

**Impact**: Instead of 5 edges all pointing to AtG, we'd get edges to `AtG_S_7`,
`StrlSchG_S_31`, `StrlSchG_S_52`, etc. — dramatically improving the graph's granularity.

---

## 4. Long-Term: Semantic Linking

Regex and keyword matching will always miss implicit relationships. For full coverage,
implement **embedding-based cross-linking**:

### 4a. Embedding Similarity Approach

1. Embed all domain entity labels + descriptions using Ollama
2. Embed all law paragraph titles + content
3. For each domain entity, find the top-k most similar paragraphs
4. Create `SEMANTIC_GOVERNED_BY` edges with similarity score as confidence

```python
async def semantic_cross_link(
    domain_entities: list[Node],
    law_paragraphs: list[Node],
    embedding_provider: EmbeddingProvider,
    similarity_threshold: float = 0.65,
    top_k: int = 3,
) -> list[Edge]:
    """Create cross-domain links based on embedding similarity."""
    domain_texts = [e.label + " " + e.properties.get("description", "") for e in domain_entities]
    law_texts = [p.label + " " + p.properties.get("text", "") for p in law_paragraphs]
    
    domain_embeds = await embedding_provider.embed_batch(domain_texts)
    law_embeds = await embedding_provider.embed_batch(law_texts)
    
    # Cosine similarity matrix
    sim_matrix = cosine_similarity(domain_embeds, law_embeds)
    
    edges = []
    for i, entity in enumerate(domain_entities):
        top_indices = np.argsort(sim_matrix[i])[-top_k:][::-1]
        for j in top_indices:
            if sim_matrix[i, j] >= similarity_threshold:
                edges.append(Edge(
                    id=generate_relation_id(entity.id, law_paragraphs[j].id, "SEMANTIC_GOVERNED_BY"),
                    source_id=entity.id,
                    target_id=law_paragraphs[j].id,
                    edge_type="SEMANTIC_GOVERNED_BY",
                    properties={"similarity": float(sim_matrix[i, j])},
                ))
    return edges
```

**Expected yield**: 200-500+ cross-links with meaningful paragraph-level granularity.

### 4b. LLM-Assisted Linking

For highest quality, ask the LLM directly:

```
Given entity "{label}" of type {entity_type} in nuclear decommissioning,
which German law paragraphs govern or define this concept?
Available laws: AtG, BBergG, BImSchG, KrWG, StrlSchG
```

**Pros**: Highest accuracy, can capture nuanced legal reasoning  
**Cons**: Expensive, slow, needs careful prompt engineering  
**Expected yield**: Similar to semantic but higher precision.

---

## 5. Domain-to-Law Mapping Reference

Key conceptual mappings for the nuclear decommissioning domain:

| Domain Concept | Governing Law | Section | Relationship |
|---|---|---|---|
| Nuclear facility (Kernanlage) | AtG | § 7 | GOVERNED_BY |
| Decommissioning (Stilllegung/Abbau) | AtG | § 7 Abs. 3 | GOVERNED_BY |
| Nuclear fuel (Kernbrennstoff) | AtG | § 2 | DEFINED_IN |
| Waste disposal (Entsorgung) | AtG | § 9a | GOVERNED_BY |
| Radiation protection | StrlSchG | entire law | GOVERNED_BY |
| Clearance (Freigabe) | StrlSchG | § 31 | GOVERNED_BY |
| Dose limits (Dosisgrenzwerte) | StrlSchG | § 5 | DEFINED_IN |
| Monitoring areas (Überwachungsbereiche) | StrlSchG | § 52 | DEFINED_IN |
| Decontamination | StrlSchG | § 64 | GOVERNED_BY |
| Radioactive waste | StrlSchG | §§ 9a, 78 | GOVERNED_BY |
| Environmental impact | BImSchG | §§ 4-6 | GOVERNED_BY |
| Mining operations | BBergG | §§ 1-3 | GOVERNED_BY |
| Conventional waste | KrWG | §§ 7-8 | GOVERNED_BY |
| Operator responsibilities | AtG | § 7 Abs. 2 | GOVERNED_BY |
| Transport of radioactive material | StrlSchG | § 27 | GOVERNED_BY |
| Physical protection (Objektschutz) | AtG | § 7 Abs. 2 | GOVERNED_BY |
| Safety analysis | AtG | §§ 7a-7c | GOVERNED_BY |

---

## 6. Implementation Priority

| Priority | Task | Effort | Impact |
|---|---|---|---|
| **P0** | Keyword-to-law mapping (regex extension) | 2h | +80-120 links |
| **P0** | Entity-type-to-law mapping | 1h | +100 links |
| **P1** | Paragraph-level resolution | 2h | Granular linking |
| **P1** | Fix `link_kg_to_laws.py` MERGE to use `id` | **Done** | No more orphans |
| **P2** | Embedding similarity cross-linking | 4h | +200-500 links |
| **P2** | Store embeddings during KG build | 3h | Enables GraphSAGE comparison |
| **P3** | LLM-assisted linking | 4h | Highest quality |
| **P3** | Entity resolution / dedup across extraction runs | 6h | Reduce 226→~50 components |

---

## 7. Validation Strategy

After implementing new linking strategies, validate by:

1. **Count**: Cross-links should go from 5 → 100+ (keyword) → 300+ (semantic)
2. **Component reduction**: Combined graph components should drop from 362 to <100
3. **Diameter**: Combined graph diameter should increase from 2 to reflect actual paths
4. **Manual review**: Sample 20 random cross-links and verify correctness
5. **Precision/Recall**: Compare against manually curated gold standard (subset)
6. **Re-run analytics**: All quality metrics should improve for the combined graph
