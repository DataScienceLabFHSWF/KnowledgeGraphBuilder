# LangExtract Evaluation for KnowledgeGraphBuilder

> Analysis date: 2026-02-13
> Library: [google/langextract](https://github.com/google/langextract) v1.1.1 (31.8k stars)

## What LangExtract Does

LangExtract is a Python library for **few-shot, example-driven structured
extraction** from unstructured text using LLMs. Core paradigm:

1. Define extraction classes and provide human-authored example annotations
2. Chunk the document, send each chunk to an LLM with the few-shot prompt
3. Parse structured JSON output and **align extracted spans back to exact
   character positions** in the source via `WordAligner` (difflib-based)
4. Merge across chunks and multiple passes with overlap-based deduplication

### Key Strengths

| Feature | Description |
|---------|-------------|
| **Source grounding** | Every extraction carries `CharInterval(start, end)` with formal `AlignmentStatus` (EXACT, FUZZY, LESSER, GREATER) |
| **Multi-pass recall** | `extraction_passes=N` runs N independent extraction passes and merges non-overlapping results |
| **Interactive visualisation** | Generates self-contained HTML to review extractions in context |
| **Controlled generation** | Uses Gemini's structured output mode for guaranteed valid JSON |
| **Cross-chunk coreference** | Context window injection from the previous chunk for continuity |
| **Ollama support** | Built-in local LLM provider (also Gemini, OpenAI, custom plugins) |

---

## Fit Assessment for Our Pipeline

### Where it could slot in

```
Documents → Loaders → Chunking → [ EXTRACTION ] → Confidence → Assembly
                                        ↑
                                  LangExtract would go here
                                  as an alternative entity extractor
```

A `LangextractEntityExtractor` adapter would implement our `EntityExtractor`
protocol, translating OWL class definitions into few-shot `ExampleData`,
calling `lx.extract()`, and mapping `Extraction` objects back to
`ExtractedEntity`.

### Critical gaps for KG construction

| Gap | Severity | Notes |
|-----|----------|-------|
| **No explicit relation extraction** | Critical | LangExtract has no subject→predicate→object triples. Relations are encoded as shared attributes or "relationship" extraction classes — not usable as graph edges without heavy post-processing. |
| **No ontology awareness** | High | Schema is inferred from examples, not from OWL/RDFS classes. No domain/range validation, no cardinality enforcement. |
| **No confidence scores** | High | Extractions have no numeric confidence. Our ensemble/voting layer would have to assign them. |
| **No entity deduplication** | Medium | No built-in coreference resolution across documents. Our existing pipeline handles this. |
| **Attribute-based "relations"** | High | The `medication_group` pattern (co-reference by shared attribute) does not map to graph edges without significant impedance mismatch. |
| **Examples must be hand-crafted** | Medium | Each ontology change requires updating the few-shot examples, while our current system auto-generates prompts from the ontology. |

### What it does better than our pipeline

| Area | LangExtract | Our pipeline |
|------|-------------|--------------|
| Source grounding | `CharInterval` + `AlignmentStatus` (verified) | `start_char`/`end_char` (trusted from LLM, unverified) |
| Multi-pass extraction | Built-in `extraction_passes` with merge | Single pass + confidence tuning |
| Visualisation | Interactive HTML out of the box | Neo4j browser only |
| Cross-chunk context | Trailing-char injection from prior chunk | Chunk overlap window |

---

## Recommendation

**Do not integrate LangExtract as a dependency.**

The cost-benefit analysis is unfavourable:

- **Costs**: new dependency chain (google-genai, absl-py, pandas, ml-collections), significant adapter code, maintaining two extraction paradigms, hand-crafting examples per ontology
- **Benefits**: better source grounding and visualisation — both achievable with ~150 LOC in our existing codebase

### Ideas to adopt instead

Port three patterns from LangExtract into our existing extractors:

1. **`WordAligner` pattern** (~100 LOC) — Use `difflib.SequenceMatcher` to
   verify and correct LLM-reported character positions. Track
   `AlignmentStatus` on each `ExtractedEntity` for provenance quality.

2. **Multi-pass extraction** (~50 LOC) — Add `extraction_passes: int`
   parameter to `LLMEntityExtractor.extract()`. Run the same prompt N times
   and merge non-overlapping results to improve recall.

3. **Cross-chunk context injection** (~30 LOC) — Pass trailing characters
   from the previous chunk as context prefix. Helps with coreference across
   chunk boundaries.

These improvements give us LangExtract's main advantages without the
dependency or the loss of our ontology-guided extraction.

---

## Stub: `LangextractEntityExtractor` (if we ever integrate)

```python
# src/kgbuilder/extraction/langextract_adapter.py  (STUB — not implemented)

from __future__ import annotations

from pathlib import Path
from typing import Any

from kgbuilder.core.protocols import EntityExtractor
from kgbuilder.extraction.schemas import ExtractedEntity


class LangextractEntityExtractor:
    """Adapter wrapping google/langextract as an entity extractor.

    Converts ontology class definitions into few-shot ``ExampleData``,
    calls ``lx.extract()``, and maps results to ``ExtractedEntity``.

    NOTE: This is a design stub.  LangExtract lacks relation extraction
    and ontology-guided prompting, so it would only replace the entity
    extraction phase and must be paired with our ``LLMRelationExtractor``.
    """

    def __init__(
        self,
        model_id: str = "gemma2:2b",
        model_url: str = "http://localhost:11434",
        extraction_passes: int = 2,
    ) -> None:
        self._model_id = model_id
        self._model_url = model_url
        self._passes = extraction_passes

    def extract(
        self,
        text: str,
        ontology_classes: list[Any],
        **kwargs: Any,
    ) -> list[ExtractedEntity]:
        """Extract entities using LangExtract few-shot approach."""
        raise NotImplementedError(
            "LangExtract adapter is a design stub — see Planning/LANGEXTRACT_EVAL.md"
        )
```

---

## References

- Repository: https://github.com/google/langextract
- Paper (RadExtract): https://huggingface.co/spaces/google/radextract
- Related work on source grounding: LangExtract's `WordAligner` uses
  `difflib.SequenceMatcher` for fuzzy character-level alignment
