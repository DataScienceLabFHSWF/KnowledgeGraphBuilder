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


def _owl_class(cls: dict[str, object], indent: str = "    ") -> str:
    """Generate OWL/XML for a single class definition."""
    cls_id = cls["id"]
    uri = f"{LAW_NS}{cls_id}"
    lines = [f'{indent}<owl:Class rdf:about="{uri}">']
    if label_de := cls.get("label_de"):
        lines.append(f'{indent}    <rdfs:label xml:lang="de">{label_de}</rdfs:label>')
    if label_en := cls.get("label_en"):
        lines.append(f'{indent}    <rdfs:label xml:lang="en">{label_en}</rdfs:label>')
    if comment := cls.get("comment"):
        lines.append(f'{indent}    <rdfs:comment xml:lang="en">{comment}</rdfs:comment>')
    if parent := cls.get("parent"):
        lines.append(f'{indent}    <rdfs:subClassOf rdf:resource="{parent}"/>')
    if align_to := cls.get("align_to"):
        lines.append(f'{indent}    <owl:equivalentClass rdf:resource="{align_to}"/>')
    lines.append(f"{indent}</owl:Class>")
    return "\n".join(lines)


def _owl_object_property(rel: dict[str, object], indent: str = "    ") -> str:
    """Generate OWL/XML for an ObjectProperty."""
    rel_id = rel["id"]
    uri = f"{LAW_NS}{rel_id}"
    lines = [f'{indent}<owl:ObjectProperty rdf:about="{uri}">']
    if label := rel.get("label"):
        lines.append(f'{indent}    <rdfs:label xml:lang="de">{label}</rdfs:label>')
    if comment := rel.get("comment"):
        lines.append(f'{indent}    <rdfs:comment xml:lang="en">{comment}</rdfs:comment>')
    if domain := rel.get("domain"):
        lines.append(f'{indent}    <rdfs:domain rdf:resource="{LAW_NS}{domain}"/>')
    if range_ := rel.get("range"):
        lines.append(f'{indent}    <rdfs:range rdf:resource="{LAW_NS}{range_}"/>')
    if align_to := rel.get("align_to"):
        lines.append(f'{indent}    <rdfs:subPropertyOf rdf:resource="{align_to}"/>')
    lines.append(f"{indent}</owl:ObjectProperty>")
    return "\n".join(lines)


def _owl_datatype_property(dp: dict[str, object], indent: str = "    ") -> str:
    """Generate OWL/XML for a DatatypeProperty."""
    dp_id = dp["id"]
    uri = f"{LAW_NS}{dp_id}"
    xsd_type = dp.get("xsd_type", "string")
    lines = [f'{indent}<owl:DatatypeProperty rdf:about="{uri}">']
    if label := dp.get("label"):
        lines.append(f'{indent}    <rdfs:label xml:lang="de">{label}</rdfs:label>')
    if comment := dp.get("comment"):
        lines.append(f'{indent}    <rdfs:comment xml:lang="en">{comment}</rdfs:comment>')
    if domain := dp.get("domain"):
        lines.append(f'{indent}    <rdfs:domain rdf:resource="{LAW_NS}{domain}"/>')
    lines.append(
        f'{indent}    <rdfs:range rdf:resource='
        f'"http://www.w3.org/2001/XMLSchema#{xsd_type}"/>'
    )
    lines.append(f"{indent}</owl:DatatypeProperty>")
    return "\n".join(lines)


def build_ontology_owl() -> str:
    """Generate OWL/XML string for the legal ontology.

    Returns:
        Complete OWL/XML document as string.
    """
    header = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF
    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:owl="http://www.w3.org/2002/07/owl#"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
    xmlns:law="{LAW_NS}"
    xmlns:eli="{ELI_NS}"
    xmlns:lkif-norm="{LKIF_NORM_NS}"
    xmlns:lkif-la="{LKIF_LACTION_NS}"
    xml:base="{LAW_NS[:-1]}">

    <owl:Ontology rdf:about="{LAW_NS[:-1]}">
        <rdfs:label xml:lang="en">KGBuilder Legal Ontology</rdfs:label>
        <rdfs:label xml:lang="de">KGBuilder Rechtsontologie</rdfs:label>
        <rdfs:comment xml:lang="en">\
Ontology for German nuclear-domain legal knowledge graph. \
Aligned to LKIF-Core and ELI vocabularies.</rdfs:comment>
        <owl:versionInfo>1.0</owl:versionInfo>
        <owl:imports rdf:resource="http://www.estrellaproject.org/lkif-core/norm.owl"/>
        <owl:imports rdf:resource=\
"http://www.estrellaproject.org/lkif-core/legal-action.owl"/>
    </owl:Ontology>

"""
    sections: list[str] = []

    # Classes
    sections.append("    <!-- ===== Classes ===== -->")
    for cls in CLASSES:
        sections.append(_owl_class(cls))

    # Object properties
    sections.append("")
    sections.append("    <!-- ===== Object Properties ===== -->")
    for rel in RELATIONS:
        sections.append(_owl_object_property(rel))

    # Datatype properties
    sections.append("")
    sections.append("    <!-- ===== Datatype Properties ===== -->")
    for dp in DATATYPE_PROPERTIES:
        sections.append(_owl_datatype_property(dp))

    footer = "\n</rdf:RDF>\n"
    return header + "\n".join(sections) + footer


def main() -> None:
    """Generate and write the legal ontology OWL file."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    owl_content = build_ontology_owl()
    OUTPUT_PATH.write_text(owl_content, encoding="utf-8")
    logger.info("Written legal ontology to %s", OUTPUT_PATH)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
