"""
Move each main law HTML into its own subdirectory in data/law_html/<ABBR>/<ABBR>.html.
Then, parse each reference HTML to find and download the XML version (if available) into the same subdirectory.
"""
from __future__ import annotations
from pathlib import Path
from bs4 import BeautifulSoup
import requests
import shutil

LAW_DIR = Path(__file__).parent.parent.parent / "data" / "law_html"
IMPORTANT_ABBRS = [
    "AO", "AtG", "BauGB", "BBergG", "BGB", "BImSchG", "KrWG", "OWiG", "SprengG", "StandAG",
    "StPO", "StrlSchG", "StrlSchV", "UVPG", "VVG", "VwGO", "VwVfG"
]

def move_html_to_subdirs() -> None:
    for abbr in IMPORTANT_ABBRS:
        src = LAW_DIR / f"{abbr}.html"
        dst_dir = LAW_DIR / abbr
        dst = dst_dir / f"{abbr}.html"
        if src.exists():
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"Moved {src} -> {dst}")
        else:
            print(f"[SKIP] {src} not found.")

def download_xml_for_laws() -> None:
    for abbr in IMPORTANT_ABBRS:
        ref_html = LAW_DIR / abbr / f"{abbr}.html"
        if not ref_html.exists():
            print(f"[SKIP] {abbr}: reference HTML not found.")
            continue
        soup = BeautifulSoup(ref_html.read_text(encoding="utf-8"), "html.parser")
        xml_link = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".xml"):
                xml_link = href
                break
        if not xml_link:
            print(f"[NO XML] {abbr}: no XML link found.")
            continue
        # Normalize relative URLs
        if xml_link.startswith("./"):
            xml_link = xml_link[1:]
        if xml_link.startswith("/"):
            xml_url = f"https://www.gesetze-im-internet.de{xml_link}"
        else:
            xml_url = f"https://www.gesetze-im-internet.de/{xml_link}"
        out_path = LAW_DIR / abbr / f"{abbr}.xml"
        try:
            resp = requests.get(xml_url, timeout=20)
            if resp.status_code == 200 and resp.text.strip():
                out_path.write_text(resp.text, encoding="utf-8")
                print(f"[OK]   {abbr}: XML downloaded.")
            else:
                print(f"[FAIL] {abbr}: HTTP {resp.status_code} {xml_url}")
        except Exception as e:
            print(f"[ERR]  {abbr}: {e}")

def main() -> None:
    move_html_to_subdirs()
    download_xml_for_laws()

if __name__ == "__main__":
    main()
