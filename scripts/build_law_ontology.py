"""Build the custom legal ontology OWL file for the Law Knowledge Graph.

Creates `data/ontology/law/law-ontology-v1.0.owl` by:
1. Defining German-law-specific classes (Gesetzbuch, Paragraf, etc.)
2. Aligning to LKIF-Core classes (Norm, Obligation, Right, etc.)
3. Aligning to ELI classes (LegalResource, LegalExpression, etc.)
4. Defining domain-specific relations and datatype properties

The generated ontology uses:
- Namespace: http://kgbuilder.2060.io/ontology/law#
- Imports: LKIF-Core norm.owl, legal-action.owl; ELI eli.owl
- Language: German labels + English definitions

Usage::

    python scripts/build_law_ontology.py
    # → data/ontology/law/law-ontology-v1.0.owl
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/ontology/law/law-ontology-v1.0.owl")

# Namespace for our legal ontology
LAW_NS = "http://kgbuilder.2060.io/ontology/law#"
LKIF_NORM_NS = "http://www.estrellaproject.org/lkif-core/norm.owl#"
LKIF_LACTION_NS = "http://www.estrellaproject.org/lkif-core/legal-action.owl#"
ELI_NS = "http://data.europa.eu/eli/ontology#"


# ---------------------------------------------------------------------------
# Class definitions (our classes → LKIF/ELI alignment)
# ---------------------------------------------------------------------------

CLASSES = [
    # --- Document-level ---
    {
        "id": "Gesetzbuch",
        "label_de": "Gesetzbuch",
        "label_en": "Law Book",
        "comment": "A German federal law (Bundesgesetz or Verordnung).",
        "parent": f"{ELI_NS}LegalResource",
        "subclasses": ["Bundesgesetz", "Verordnung"],
    },
    {
        "id": "Bundesgesetz",
        "label_de": "Bundesgesetz",
        "label_en": "Federal Law",
        "comment": "A federal statute (e.g. AtG, StrlSchG).",
        "parent": f"{LAW_NS}Gesetzbuch",
        "align_to": f"{LKIF_NORM_NS}Statute",
    },
    {
        "id": "Verordnung",
        "label_de": "Verordnung",
        "label_en": "Ordinance",
        "comment": "A regulation/ordinance (e.g. StrlSchV).",
        "parent": f"{LAW_NS}Gesetzbuch",
        "align_to": f"{LKIF_NORM_NS}Regulation",
    },
    # --- Paragraph-level ---
    {
        "id": "Paragraf",
        "label_de": "Paragraf",
        "label_en": "Paragraph",
        "comment": "A single § or Artikel within a law.",
        "parent": f"{ELI_NS}LegalResourceSubdivision",
    },
    {
        "id": "Absatz",
        "label_de": "Absatz",
        "label_en": "Sub-paragraph",
        "comment": "A numbered sub-paragraph within a §.",
        "parent": f"{LAW_NS}Paragraf",
    },
    # --- Legal concepts ---
    {
        "id": "LegalConcept",
        "label_de": "Rechtsbegriff",
        "label_en": "Legal Concept",
        "comment": "An abstract legal concept defined or referenced in law.",
        "parent": None,
    },
    {
        "id": "Definition",
        "label_de": "Legaldefinition",
        "label_en": "Legal Definition",
        "comment": "An explicitly defined term (Begriffsbestimmung).",
        "parent": f"{LAW_NS}LegalConcept",
    },
    {
        "id": "Obligation",
        "label_de": "Pflicht",
        "label_en": "Obligation",
        "comment": "A legal duty or requirement.",
        "parent": f"{LAW_NS}LegalConcept",
        "align_to": f"{LKIF_NORM_NS}Obligation",
    },
    {
        "id": "Permission",
        "label_de": "Erlaubnis",
        "label_en": "Permission",
        "comment": "A legal permission or authorization.",
        "parent": f"{LAW_NS}LegalConcept",
        "align_to": f"{LKIF_NORM_NS}Permission",
    },
    {
        "id": "Prohibition",
        "label_de": "Verbot",
        "label_en": "Prohibition",
        "comment": "A legal prohibition.",
        "parent": f"{LAW_NS}LegalConcept",
        "align_to": f"{LKIF_NORM_NS}Prohibition",
    },
    # --- Actors ---
    {
        "id": "LegalActor",
        "label_de": "Rechtsakteur",
        "label_en": "Legal Actor",
        "comment": "An entity with legal standing.",
        "parent": None,
    },
    {
        "id": "Behoerde",
        "label_de": "Behörde",
        "label_en": "Authority",
        "comment": "A public authority or regulatory body.",
        "parent": f"{LAW_NS}LegalActor",
        "align_to": f"{LKIF_LACTION_NS}Public_Body",
    },
    {
        "id": "Betreiber",
        "label_de": "Betreiber",
        "label_en": "Operator",
        "comment": "An operator or licensee subject to legal obligations.",
        "parent": f"{LAW_NS}LegalActor",
        "align_to": f"{LKIF_LACTION_NS}Legal_Person",
    },
    # --- References ---
    {
        "id": "LegalReference",
        "label_de": "Rechtsverweis",
        "label_en": "Legal Reference",
        "comment": "A cross-reference to another paragraph or law.",
        "parent": None,
    },
]

# ---------------------------------------------------------------------------
# Relation definitions (ObjectProperties)
# ---------------------------------------------------------------------------

RELATIONS = [
    {"id": "teilVon", "label": "teil von", "domain": "Paragraf", "range": "Gesetzbuch",
     "comment": "Paragraph belongs to law.", "align_to": f"{ELI_NS}is_part_of"},
    {"id": "referenziert", "label": "referenziert", "domain": "Paragraf", "range": "Paragraf",
     "comment": "Cross-reference between paragraphs.", "align_to": f"{ELI_NS}cites"},
    {"id": "definiert", "label": "definiert", "domain": "Paragraf", "range": "Definition",
     "comment": "Paragraph defines a legal term."},
    {"id": "verpflichtet", "label": "verpflichtet", "domain": "Paragraf", "range": "Obligation",
     "comment": "Paragraph establishes an obligation."},
    {"id": "erlaubt", "label": "erlaubt", "domain": "Paragraf", "range": "Permission",
     "comment": "Paragraph grants a permission."},
    {"id": "verbietet", "label": "verbietet", "domain": "Paragraf", "range": "Prohibition",
     "comment": "Paragraph establishes a prohibition."},
    {"id": "zustaendig", "label": "zuständig für", "domain": "Behoerde", "range": "Obligation",
     "comment": "Authority responsible for obligation."},
    {"id": "betrifft", "label": "betrifft", "domain": "Obligation", "range": "LegalActor",
     "comment": "Obligation applies to actor."},
    {"id": "aendert", "label": "ändert", "domain": "Gesetzbuch", "range": "Gesetzbuch",
     "comment": "Law amends another law.", "align_to": f"{ELI_NS}amends"},
    {"id": "aufgehobenDurch", "label": "aufgehoben durch",
     "domain": "Paragraf", "range": "Paragraf",
     "comment": "Paragraph repealed by another."},
]

# ---------------------------------------------------------------------------
# Datatype properties
# ---------------------------------------------------------------------------

DATATYPE_PROPERTIES = [
    {"id": "abkuerzung", "label": "Abkürzung", "domain": "Gesetzbuch",
     "xsd_type": "string", "comment": "Official abbreviation (AtG, StrlSchV)."},
    {"id": "langtext", "label": "Langtext", "domain": "Gesetzbuch",
     "xsd_type": "string", "comment": "Full title of the law."},
    {"id": "version", "label": "Version", "domain": "Gesetzbuch",
     "xsd_type": "string", "comment": "Version identifier."},
    {"id": "letzteAenderung", "label": "Letzte Änderung", "domain": "Gesetzbuch",
     "xsd_type": "date", "comment": "Date of last amendment."},
    {"id": "gesetzestext", "label": "Gesetzestext", "domain": "Paragraf",
     "xsd_type": "string", "comment": "Full paragraph text."},
    {"id": "nummer", "label": "Nummer", "domain": "Paragraf",
     "xsd_type": "string", "comment": "Paragraph number (§ 7, Art. 3)."},
    {"id": "titel", "label": "Titel", "domain": "Paragraf",
     "xsd_type": "string", "comment": "Paragraph title."},
]


def build_ontology_owl() -> str:
    """Generate OWL/XML string for the legal ontology.

    Returns:
        Complete OWL/XML document as string.
    """
    raise NotImplementedError  # TODO: Step 7 implementation


def main() -> None:
    """Generate and write the legal ontology OWL file."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    owl_content = build_ontology_owl()
    OUTPUT_PATH.write_text(owl_content, encoding="utf-8")
    logger.info("Written legal ontology to %s", OUTPUT_PATH)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
