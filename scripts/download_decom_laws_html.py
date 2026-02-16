"""
Download HTML for decommissioning-related laws (and related) using law_index.json.

- Reads law_index.json
- Filters for a list of important abbreviations (AtG, StrlSchG, StrlSchV, BBergG, BImSchG, KrWG, etc.)
- Downloads each law's HTML to data/law_html/<ABBR>.html
- Skips already-downloaded files
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

IMPORTANT_ABBRS = [
    "AtG", "StrlSchG", "StrlSchV", "BBergG", "BImSchG", "KrWG", "VwVfG", "VwGO", "AO", "StPO",
    "UVPG", "StandAG", "BauGB", "SGB VII", "SprengG", "BGB", "VVG", "VwKostG", "OWiG"
]

INDEX_PATH = Path(__file__).parent.parent / "data" / "law_index" / "law_index.json"
OUT_DIR = Path(__file__).parent.parent / "data" / "law_html"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def main() -> None:
    with INDEX_PATH.open("r", encoding="utf-8") as f:
        laws = json.load(f)
    abbr_set = {abbr.lower().replace(" ", "") for abbr in IMPORTANT_ABBRS}
    filtered = [law for law in laws if law["abbreviation"].lower().replace(" ", "") in abbr_set]
    print(f"Found {len(filtered)} important laws to download.")
    for law in filtered:
        abbr = law["abbreviation"].replace(" ", "")
        url = law["url"]
        out_path = OUT_DIR / f"{abbr}.html"
        if out_path.exists():
            print(f"[SKIP] {abbr}: already downloaded.")
            continue
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200 and resp.text.strip():
                out_path.write_text(resp.text, encoding="utf-8")
                print(f"[OK]   {abbr}: {url}")
            else:
                print(f"[FAIL] {abbr}: HTTP {resp.status_code} {url}")
        except Exception as e:
            print(f"[ERR]  {abbr}: {e}")

if __name__ == "__main__":
    main()
