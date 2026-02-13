"""
Download all paragraph/article HTMLs for each important law into a structured subdirectory.

- For each law in data/law_html/<ABBR>.html:
  - Create data/law_html/<ABBR>/
  - Parse index.html to extract all paragraph/article links
  - Download each linked HTML into the subdir as <PARA>.html (e.g., 1.html, 2.html, ... or §1.html)
"""
from __future__ import annotations
import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup

LAW_DIR = Path(__file__).parent.parent / "data" / "law_html"

# List of abbreviations to process (should match downloaded laws)
IMPORTANT_ABBRS = [
    "AO", "AtG", "BauGB", "BBergG", "BGB", "BImSchG", "KrWG", "OWiG", "SprengG", "StandAG",
    "StPO", "StrlSchG", "StrlSchV", "UVPG", "VVG", "VwGO", "VwVfG"
]

BASE_URL = "https://www.gesetze-im-internet.de/"


def download_paragraphs_for_law(abbr: str) -> None:
    law_html_path = LAW_DIR / f"{abbr}.html"
    if not law_html_path.exists():
        print(f"[SKIP] {abbr}: reference HTML not found.")
        return
    out_dir = LAW_DIR / abbr
    out_dir.mkdir(parents=True, exist_ok=True)
    html = law_html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    # Find all links to paragraphs/articles (usually <a href="...#BJNR...__1.html"> or similar)
    para_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Only keep links to paragraphs/articles (not navigation, not PDF, not external)
        if re.match(r"^/.*?/\d+\.html$", href) or re.match(r"^/.*?/BJNR.*?__\d+\.html$", href):
            para_links.append((a.text.strip(), href))
    print(f"[{abbr}] Found {len(para_links)} paragraph/article links.")
    for text, href in para_links:
        # Normalize filename: use the number or § from the link text, fallback to last part of href
        fname = re.sub(r"[^\w§]+", "_", text) or Path(href).stem
        if not fname.endswith(".html"):
            fname += ".html"
        out_path = out_dir / fname
        if out_path.exists():
            print(f"[SKIP] {abbr}/{fname}")
            continue
        url = BASE_URL.rstrip("/") + href
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200 and resp.text.strip():
                out_path.write_text(resp.text, encoding="utf-8")
                print(f"[OK]   {abbr}/{fname}")
            else:
                print(f"[FAIL] {abbr}/{fname}: HTTP {resp.status_code} {url}")
        except Exception as e:
            print(f"[ERR]  {abbr}/{fname}: {e}")

def main() -> None:
    for abbr in IMPORTANT_ABBRS:
        download_paragraphs_for_law(abbr)

if __name__ == "__main__":
    main()
