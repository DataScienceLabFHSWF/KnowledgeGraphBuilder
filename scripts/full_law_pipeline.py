"""
One-run pipeline to download, organize, and extract all key German laws for reproducible research.

Steps performed:
1. Download all Teilliste_X.html (A-Z, 1-9) index files for archiving.
2. Crawl all Teilliste_X.html to build a law index (law_index.json).
3. Download main HTML for all important laws (by abbreviation) into data/law_html/<ABBR>/<ABBR>.html.
4. Download and extract XML ZIPs for all important laws into their subdirectories.

Usage:
    python scripts/full_law_pipeline.py

Requirements:
- Python 3.11+
- requests, beautifulsoup4

This script is idempotent: it skips already-downloaded files.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Step 1: Download all Teilliste_X.html

def download_teilliste():
    print("[STEP 1] Downloading Teilliste_X.html (A-Z, 1-9)...")
    teilliste_dir = Path(__file__).parent.parent / "data" / "law_index"
    teilliste_dir.mkdir(parents=True, exist_ok=True)
    for x in [chr(i) for i in range(ord('A'), ord('Z')+1)] + [str(i) for i in range(1, 10)]:
        out = teilliste_dir / f"Teilliste_{x}.html"
        if out.exists():
            print(f"[SKIP] Teilliste_{x}.html already exists.")
            continue
        url = f"https://www.gesetze-im-internet.de/Teilliste_{x}.html"
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
        import requests
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            out.write_text(resp.text, encoding="utf-8")
            print(f"[OK]   Downloaded Teilliste_{x}.html")
        else:
            print(f"[FAIL] Teilliste_{x}.html: HTTP {resp.status_code}")

# Step 2: Crawl all Teilliste_X.html to build law_index.json

def crawl_law_index():
    print("[STEP 2] Crawling law index from Teilliste_X.html...")
    subprocess.run([sys.executable, "scripts/crawl_law_index.py"], check=True)

# Step 3: Download main HTML for all important laws

def download_main_law_html():
    print("[STEP 3] Downloading main HTML for important laws...")
    subprocess.run([sys.executable, "scripts/download_decom_laws_html.py"], check=True)
    # Move HTMLs to subdirs
    subprocess.run([sys.executable, "scripts/organize_and_download_xml.py"], check=True)

# Step 4: Download and extract XML ZIPs for all important laws

def download_and_extract_xmls():
    print("[STEP 4] Downloading and extracting XML ZIPs for important laws...")
    subprocess.run([sys.executable, "scripts/download_law_xml_zips.py"], check=True)


def main():
    download_teilliste()
    crawl_law_index()
    download_main_law_html()
    download_and_extract_xmls()
    print("\n[ALL DONE] All laws and XMLs downloaded and organized. See data/law_html/ for results.")

if __name__ == "__main__":
    main()
