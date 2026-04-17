# External Reference Ontologies

Downloaded public ontologies referenced in the team's ontology issues
(DataScienceLabFHSWF/wiki_alisa_kiko #100, #62, #63, #54).

## Contents

### CCO — Common Core Ontologies
- **Source**: [CommonCoreOntology/CommonCoreOntologies](https://github.com/CommonCoreOntology/CommonCoreOntologies) (develop branch)
- **License**: BSD-3-Clause
- **Built on**: BFO (Basic Formal Ontology)
- **Files**:
  - `cco/CommonCoreOntologiesMerged.ttl` — Full merged ontology (19,756 lines)
  - `cco/AgentOntology.ttl` — Agent module (organizations, persons, roles)
  - `cco/EventOntology.ttl` — Event module (processes, temporal entities)
  - `cco/AllCoreOntology.ttl` — Top-level import manifest
- **Relevance**: Issue #100 (subclassing), entity typing, agent/organization modeling

### BOT — Building Topology Ontology
- **Source**: [w3c-lbd-cg/bot](https://github.com/w3c-lbd-cg/bot)
- **License**: W3C Community Group
- **Standard**: W3C Linked Building Data
- **Files**:
  - `bot/bot.ttl` — Full ontology (1,126 lines)
- **Relevance**: Issue #62 (Gebäude ontology module), facility/building modeling

### SAREF — Smart Applications REFerence
- **Source**: [saref.etsi.org](https://saref.etsi.org), [mariapoveda/saref-ext](https://github.com/mariapoveda/saref-ext)
- **License**: ETSI
- **Standard**: ETSI TS 103 264
- **Files**:
  - `saref/saref.ttl` — Core SAREF ontology (2,253 lines)
  - `saref/saref4bldg.ttl` — SAREF for Buildings extension (4,242 lines)
- **Relevance**: Building systems, devices, measurements — complements BOT

## Not Available

| Ontology | Why | Action |
|----------|-----|--------|
| **GRS Ontology** (issue #124) | Internal/private document | Ask Alisa for the file |
| **vault-kg-ontologies** (issue #132) | Private repo (`hennkar/vault-kg-ontologies`) | Request access from team |
| **Alisa's Protege modules** (issues #1, #62, #63) | Built locally in Protege, not committed | Ask Alisa to export & share |

## Usage

These ontologies can be used for:
1. **Class alignment** — Map our extracted entity types to standard classes
2. **Ontology enrichment** — Import relevant classes into our domain ontology
3. **Entity linking** — Same approach as OntologyExtender's entity_linker.py
4. **Validation** — Cross-reference our KG structure against established patterns
