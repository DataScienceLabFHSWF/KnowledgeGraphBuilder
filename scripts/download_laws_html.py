"""
Script to download and store all referenced German laws as HTML from gesetze-im-internet.de.

- Infers the gesetze-im-internet.de URL naming scheme from law abbreviations (e.g., AtG, StrlSchG, KrWG, BImSchG, BBergG, etc.).
- Downloads the HTML for each referenced law.
- Stores each HTML file in data/law_html/ as <ABBR>.html (e.g., AtG.html, StrlSchG.html).
- Skips already-downloaded files.
- Prints summary of downloads and any failures.

Usage: python scripts/download_laws_html.py
"""
from __future__ import annotations

from pathlib import Path

import requests

# List of law abbreviations (expand as needed)
LAW_ABBRS = [
    "AtG", "StrlSchG", "StrlSchV", "BBergG", "BImSchG", "KrWG", "VwVfG", "VwGO", "AO", "StPO",
    "UVPG", "StandAG", "BauGB", "SGB_VII", "SprengG", "BGB", "VVG", "VwKostG", "OWiG"
]

# Mapping for special cases (abbreviation -> gesetze-im-internet.de path)
SPECIAL_CASES = {
    "SGB_VII": "sgb_7/BJNR023410971.html",
    # Add more if needed
}

# Default pattern: https://www.gesetze-im-internet.de/<abbr>/BJNR....html
# But most laws are at https://www.gesetze-im-internet.de/<abbr>/index.html
# We'll try both.

BASE_URL = "https://www.gesetze-im-internet.de/"
OUT_DIR = Path(__file__).parent.parent / "data" / "law_html"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def infer_url(abbr: str) -> str:
    if abbr in SPECIAL_CASES:
        return BASE_URL + SPECIAL_CASES[abbr]
    # Most laws: <abbr>/index.html
    return f"{BASE_URL}{abbr}/index.html"


def download_law_html(abbr: str) -> bool:
    url = infer_url(abbr)
    out_path = OUT_DIR / f"{abbr}.html"
    if out_path.exists():
        print(f"[SKIP] {abbr}: already downloaded.")
        return True
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200 and resp.text.strip():
            out_path.write_text(resp.text, encoding="utf-8")
            print(f"[OK]   {abbr}: {url}")
            return True
        else:
            print(f"[FAIL] {abbr}: HTTP {resp.status_code} {url}")
            return False
    except Exception as e:
        print(f"[ERR]  {abbr}: {e}")
        return False


def main() -> None:
    print(f"Downloading {len(LAW_ABBRS)} laws to {OUT_DIR}...")
    ok, fail = 0, 0
    for abbr in LAW_ABBRS:
        if download_law_html(abbr):
            ok += 1
        else:
            fail += 1
    print(f"Done. Success: {ok}, Failed: {fail}")


if __name__ == "__main__":
    main()
