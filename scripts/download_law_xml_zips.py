"""
Download XML ZIPs for all important laws by parsing their reference HTML.
- For each law in data/law_html/<ABBR>/<ABBR>.html:
  - Find the XML ZIP link (e.g., xml.zip)
  - Download to data/law_html/<ABBR>/xml.zip
  - Optionally extract the XML file(s) from the ZIP
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup

LAW_DIR = Path(__file__).parent.parent / "data" / "law_html"
INDEX_PATH = Path(__file__).parent.parent / "data" / "law_index" / "law_index.json"
IMPORTANT_ABBRS = [
    "AO", "AtG", "BauGB", "BBergG", "BGB", "BImSchG", "KrWG", "OWiG", "SprengG", "StandAG",
    "StPO", "StrlSchG", "StrlSchV", "UVPG", "VVG", "VwGO", "VwVfG"
]

def download_and_extract_xml_zip(abbr: str) -> None:
    ref_html = LAW_DIR / abbr / f"{abbr}.html"
    if not ref_html.exists():
        print(f"[SKIP] {abbr}: reference HTML not found.")
        return
    # Load lawdir from law_index.json
    with INDEX_PATH.open("r", encoding="utf-8") as f:
        law_index = json.load(f)
    abbr_map = {law["abbreviation"].replace(" ", "").lower(): law["url"] for law in law_index}
    abbr_key = abbr.replace(" ", "").lower()
    law_url = abbr_map.get(abbr_key)
    if not law_url:
        print(f"[NO URL] {abbr}: not found in law_index.json.")
        return
    # Extract lawdir from the URL (e.g., https://www.gesetze-im-internet.de/ao_1977/index.html -> ao_1977)
    try:
        lawdir = law_url.split("/")[-2]
    except Exception:
        lawdir = abbr.lower()
    soup = BeautifulSoup(ref_html.read_text(encoding="utf-8"), "html.parser")
    xml_link = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith("xml.zip"):
            xml_link = href
            break
    if not xml_link:
        print(f"[NO XML ZIP] {abbr}: no xml.zip link found.")
        return
    xml_url = f"https://www.gesetze-im-internet.de/{lawdir}/xml.zip"
    out_zip = LAW_DIR / abbr / "xml.zip"
    try:
        resp = requests.get(xml_url, timeout=30)
        if resp.status_code == 200 and resp.content:
            out_zip.write_bytes(resp.content)
            print(f"[OK]   {abbr}: xml.zip downloaded.")
            # Optionally extract XML(s)
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".xml"):
                        xml_out = LAW_DIR / abbr / name
                        with zf.open(name) as f_in, xml_out.open("wb") as f_out:
                            f_out.write(f_in.read())
                        print(f"[OK]   {abbr}: extracted {name}")
        else:
            print(f"[FAIL] {abbr}: HTTP {resp.status_code} {xml_url}")
    except Exception as e:
        print(f"[ERR]  {abbr}: {e}")

def main() -> None:
    for abbr in IMPORTANT_ABBRS:
        download_and_extract_xml_zip(abbr)

if __name__ == "__main__":
    main()
