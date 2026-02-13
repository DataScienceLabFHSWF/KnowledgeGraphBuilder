"""XML loader for German federal law files from gesetze-im-internet.de.

Parses the official XML format (BJNR*.xml) into structured LawDocument and
Norm objects. Supports both full-law and single-norm extraction.

The XML schema is:
    <dokumente> → <norm> elements, each with:
        <metadaten>  — jurabk, enbez (§ number), titel, gliederungseinheit
        <textdaten>  — <text><Content><P> markup with paragraph text

Usage::

    reader = LawXMLReader()
    law = reader.parse_file(Path("data/law_html/AtG/BJNR008140959.xml"))
    print(law.abbreviation, len(law.norms), "norms")
    for norm in law.paragraphs():
        print(norm.enbez, norm.title, len(norm.text))
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from kgbuilder.core.exceptions import DocumentLoadError


class NormType(Enum):
    """Classification of a <norm> element."""

    METADATA = "metadata"       # First norm (law-level metadata, no enbez)
    STRUCTURE = "structure"     # Section/chapter heading (has gliederungseinheit)
    PARAGRAPH = "paragraph"     # Actual § / Art. with content
    APPENDIX = "appendix"       # Anlage (appendix)


@dataclass
class GliederungsEinheit:
    """Structural grouping (Abschnitt, Teil, Kapitel, etc.)."""

    kennung: str        # e.g. "Erster Abschnitt", "Teil 2"
    titel: str          # e.g. "Allgemeine Vorschriften"
    level: int = 0      # Nesting depth (0 = top-level)


@dataclass
class CrossReference:
    """A cross-reference extracted from norm text."""

    target_paragraph: str       # e.g. "§ 7"
    target_law: str | None      # e.g. "AtG" or None if same law
    raw_text: str               # Original matched text
    source_paragraph: str = ""  # Set by caller


@dataclass
class LawMetadata:
    """Law-level metadata extracted from the first <norm>."""

    jurabk: str = ""                    # Short abbreviation (AtG)
    amtabk: str = ""                    # Official abbreviation
    ausfertigung_datum: str = ""        # Enactment date
    fundstelle: dict[str, str] = field(default_factory=dict)  # Publication ref
    kurzue: str = ""                    # Short title
    langue: str = ""                    # Full title
    standangabe: list[dict[str, str]] = field(default_factory=list)  # Amendments


@dataclass
class Norm:
    """A single <norm> element from the XML."""

    build_date: str             # From @builddate attribute
    doc_number: str             # From @doknr attribute (BJNR...)
    norm_type: NormType
    jurabk: str                 # Law abbreviation
    enbez: str = ""             # § number (e.g. "§ 7", "Art 3")
    title: str = ""             # Norm title
    text: str = ""              # Plain text content (HTML stripped)
    text_html: str = ""         # Raw XML/HTML content preserved
    gliederung: GliederungsEinheit | None = None
    cross_references: list[CrossReference] = field(default_factory=list)
    metadata_raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_paragraph(self) -> bool:
        return self.norm_type == NormType.PARAGRAPH

    @property
    def is_structure(self) -> bool:
        return self.norm_type == NormType.STRUCTURE

    @property
    def full_id(self) -> str:
        """Unique identifier like 'AtG_§ 7'."""
        return f"{self.jurabk}_{self.enbez}" if self.enbez else f"{self.jurabk}_{self.doc_number}"


@dataclass
class LawDocument:
    """A complete parsed law XML file."""

    file_path: Path
    metadata: LawMetadata
    norms: list[Norm]

    @property
    def abbreviation(self) -> str:
        return self.metadata.jurabk

    @property
    def full_title(self) -> str:
        return self.metadata.langue or self.metadata.kurzue

    def paragraphs(self) -> list[Norm]:
        """Return only actual §/Art norms (not structure/metadata)."""
        return [n for n in self.norms if n.is_paragraph]

    def structure_nodes(self) -> list[Norm]:
        """Return section/chapter headings."""
        return [n for n in self.norms if n.is_structure]

    def all_cross_references(self) -> list[CrossReference]:
        """Collect all cross-references across all norms."""
        refs: list[CrossReference] = []
        for norm in self.norms:
            refs.extend(norm.cross_references)
        return refs


# ---------------------------------------------------------------------------
# Regex for cross-reference extraction
# ---------------------------------------------------------------------------

# Matches patterns like: § 7, § 7a, §§ 7 bis 9, § 7 Absatz 2, § 7 Abs. 1
# Also: § 7 des Atomgesetzes, § 12 StrlSchV
_XREF_PATTERN = re.compile(
    r"§§?\s*(\d+[a-z]?)"                          # § number
    r"(?:\s*(?:bis|und|,)\s*§?\s*\d+[a-z]?)*"     # § ranges (§§ 7 bis 9)
    r"(?:\s+(?:Abs(?:atz)?\.?\s*\d+))?"            # Absatz (optional)
    r"(?:\s+(?:Satz|S\.)\s*\d+)?"                  # Satz (optional)
    r"(?:\s+(?:Nr\.?\s*\d+))?"                     # Nr. (optional)
    r"(?:\s+(?:des|der|von)\s+[A-ZÄÖÜ]\w+)?"      # "des Atomgesetzes" (optional)
    r"(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß]+V?)?"        # Law abbreviation suffix (optional)
)

# Matches law abbreviation after a reference, e.g. "StrlSchV" in "§ 12 StrlSchV"
_LAW_ABBR_PATTERN = re.compile(r"\b([A-ZÄÖÜ][A-Za-z]{1,15}(?:G|V|O))\b")


class LawXMLReader:
    """Parser for gesetze-im-internet.de XML law files.

    Extracts structured norms, metadata, and cross-references from the
    official BJNR*.xml format.
    """

    def parse_file(self, path: Path) -> LawDocument:
        """Parse a law XML file into a LawDocument.

        Args:
            path: Path to BJNR*.xml file.

        Returns:
            Fully parsed LawDocument with norms and cross-references.

        Raises:
            DocumentLoadError: If XML is malformed or unreadable.
        """
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise DocumentLoadError(path, f"Malformed XML: {e}") from e
        except OSError as e:
            raise DocumentLoadError(path, str(e)) from e

        return self._parse_root(root, path)

    def parse_directory(self, dir_path: Path) -> list[LawDocument]:
        """Parse all XML files in a directory (one law per XML).

        Args:
            dir_path: Directory containing BJNR*.xml files (e.g. data/law_html/).

        Returns:
            List of parsed LawDocument objects.
        """
        docs: list[LawDocument] = []
        for xml_path in sorted(dir_path.rglob("BJNR*.xml")):
            try:
                docs.append(self.parse_file(xml_path))
            except DocumentLoadError:
                pass  # logged upstream
        return docs

    # ------------------------------------------------------------------
    # Internal parsing methods
    # ------------------------------------------------------------------

    def _parse_root(self, root: ET.Element, path: Path) -> LawDocument:
        """Parse <dokumente> root element."""
        norm_elems = root.findall(".//norm")
        if not norm_elems:
            raise DocumentLoadError(path, "No <norm> elements found")

        metadata = self._parse_law_metadata(norm_elems[0])
        norms: list[Norm] = []
        for elem in norm_elems:
            norm = self._parse_norm(elem)
            # Enrich cross-references for paragraphs
            if norm.is_paragraph and norm.text:
                norm.cross_references = self._extract_cross_references(
                    norm.text, norm.enbez, metadata.jurabk
                )
            norms.append(norm)

        return LawDocument(file_path=path, metadata=metadata, norms=norms)

    def _parse_law_metadata(self, first_norm: ET.Element) -> LawMetadata:
        """Extract law-level metadata from the first <norm>."""
        meta_el = first_norm.find("metadaten")
        if meta_el is None:
            return LawMetadata()

        md = LawMetadata()
        md.jurabk = meta_el.findtext("jurabk", "")
        md.amtabk = meta_el.findtext("amtabk", "")
        md.kurzue = meta_el.findtext("kurzue", "")
        md.langue = meta_el.findtext("langue", "")
        md.ausfertigung_datum = meta_el.findtext("ausfertigung_datum", "")

        fnd = meta_el.find("fundstelle")
        if fnd is not None:
            md.fundstelle = {
                "periodikum": fnd.findtext("periodikum", ""),
                "zitstelle": fnd.findtext("zitstelle", ""),
            }

        for sa in meta_el.findall("standangabe"):
            md.standangabe.append({
                "standtyp": sa.findtext("standtyp", ""),
                "standkommentar": sa.findtext("standkommentar", ""),
            })

        return md

    def _parse_norm(self, elem: ET.Element) -> Norm:
        """Parse a single <norm> element into a Norm dataclass."""
        build_date = elem.get("builddate", "")
        doc_number = elem.get("doknr", "")

        meta_el = elem.find("metadaten")
        jurabk = ""
        enbez = ""
        title = ""
        gliederung: GliederungsEinheit | None = None

        if meta_el is not None:
            jurabk = meta_el.findtext("jurabk", "")
            enbez = meta_el.findtext("enbez", "")
            titel_el = meta_el.find("titel")
            if titel_el is not None:
                title = "".join(titel_el.itertext()).strip()
            gliederung = self._parse_gliederung(meta_el)

        text_elem = elem.find(".//textdaten/text/Content")
        norm_type = self._classify_norm(meta_el, text_elem)
        plain_text, raw_html = self._extract_text(text_elem)

        return Norm(
            build_date=build_date,
            doc_number=doc_number,
            norm_type=norm_type,
            jurabk=jurabk,
            enbez=enbez,
            title=title,
            text=plain_text,
            text_html=raw_html,
            gliederung=gliederung,
        )

    def _classify_norm(self, meta: ET.Element | None, text_elem: ET.Element | None) -> NormType:
        """Determine the NormType from metadata and text presence."""
        if meta is None:
            return NormType.METADATA

        enbez = meta.findtext("enbez", "")
        gliederung = meta.find("gliederungseinheit")

        if enbez.startswith("Anlage"):
            return NormType.APPENDIX
        if gliederung is not None and not enbez:
            return NormType.STRUCTURE
        if enbez:
            return NormType.PARAGRAPH
        return NormType.METADATA

    def _extract_text(self, text_elem: ET.Element | None) -> tuple[str, str]:
        """Extract plain text and raw HTML from <textdaten>/<text>/<Content>.

        Returns:
            Tuple of (plain_text, raw_html).
        """
        if text_elem is None:
            return "", ""

        raw_html = ET.tostring(text_elem, encoding="unicode", method="xml")
        plain_text = ET.tostring(text_elem, encoding="unicode", method="text").strip()
        # Collapse whitespace
        plain_text = re.sub(r"\s+", " ", plain_text)
        return plain_text, raw_html

    def _extract_cross_references(
        self, text: str, source_paragraph: str, source_law: str
    ) -> list[CrossReference]:
        """Extract §-references from paragraph text using regex."""
        refs: list[CrossReference] = []
        for match in _XREF_PATTERN.finditer(text):
            raw = match.group(0)
            target_para = f"§ {match.group(1)}"

            # Try to detect target law
            target_law: str | None = None
            remainder = raw[match.end(1):]
            law_match = _LAW_ABBR_PATTERN.search(remainder)
            if law_match:
                target_law = law_match.group(1)

            refs.append(CrossReference(
                target_paragraph=target_para,
                target_law=target_law,
                raw_text=raw.strip(),
                source_paragraph=source_paragraph,
            ))
        return refs

    def _parse_gliederung(self, meta: ET.Element) -> GliederungsEinheit | None:
        """Parse <gliederungseinheit> from metadata if present."""
        gl = meta.find("gliederungseinheit")
        if gl is None:
            return None

        kennung = gl.findtext("gliederungskennzahl", "")
        bez = gl.findtext("gliederungsbez", "")
        titel = gl.findtext("gliederungstitel", "")
        level = len(kennung) // 3 if kennung else 0

        return GliederungsEinheit(
            kennung=f"{bez} {titel}".strip() if bez else titel,
            titel=titel,
            level=level,
        )
