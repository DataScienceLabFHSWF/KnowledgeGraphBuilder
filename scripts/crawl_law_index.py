"""
Script to crawl all Teilliste_X.html index pages from gesetze-im-internet.de,
extract all law links and metadata, and save as a structured JSON file.

- Crawls all A-Z index pages (Teilliste_A.html, ... Teilliste_Z.html)
- Extracts: abbreviation, full name, canonical law URL
- Stores results in data/law_index/law_index.json
- Can be extended to download each law's HTML later

Usage: python scripts/crawl_law_index.py
"""
from __future__ import annotations

import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.gesetze-im-internet.de/"
INDEX_DIR = Path(__file__).parent.parent / "data" / "law_index"
INDEX_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = INDEX_DIR / "law_index.json"

ALPHANUM = [chr(i) for i in range(ord('A'), ord('Z')+1)] + [str(i) for i in range(1, 10)]


def crawl_index_page(letter: str) -> list[dict[str, str]]:
    # For offline test: if letter == 'N', parse local file
    if letter == 'N':
        html_path = Path(__file__).parent.parent / 'data' / 'law_index' / 'Teilliste_N.html'
        html = html_path.read_text(encoding='iso-8859-1')
        print("[INFO] Parsing local Teilliste_N.html for structure analysis.")
    else:
        url = f"{BASE_URL}Teilliste_{letter}.html"
        print(f"[INFO] Crawling index page: {url}")
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    results = []
    level2 = soup.find("div", id="level2")
    if not level2:
        print(f"[WARN] Could not find <div id='level2'> on {letter}")
        return results
    for p in level2.find_all('p'):
        a = p.find('a', href=True)
        if not a:
            continue
        abbr_tag = a.find('abbr')
        abbr = abbr_tag.text.strip() if abbr_tag else a.text.strip()
        href = a['href'].strip()
        # Normalize relative URLs
        if href.startswith('./'):
            href = href[1:]
        law_url = BASE_URL.rstrip('/') + href
        # The full name is the text after <br/>
        br = p.find('br')
        full_name = ''
        if br:
            # Get all text after <br/>, up to next <a> (PDF)
            texts = []
            for sib in br.next_siblings:
                if getattr(sib, 'name', None) == 'a':
                    break
                if isinstance(sib, str):
                    texts.append(sib.strip())
            full_name = ' '.join(texts).strip()
        results.append({
            'abbreviation': abbr,
            'full_name': full_name,
            'url': law_url
        })
    print(f"[INFO] Found {len(results)} law entries in Teilliste_{letter}.")
    return results

def main() -> None:
    all_laws = []
    for letter in ALPHANUM:
        try:
            laws = crawl_index_page(letter)
            all_laws.extend(laws)
        except Exception as e:
            print(f"[ERR] {letter}: {e}")
    # Deduplicate by canonical URL (primary), then abbreviation (secondary)
    unique_by_url: dict[str, dict[str, str]] = {}
    unique_by_abbr: dict[str, dict[str, str]] = {}
    for law in all_laws:
        url = law["url"].strip()
        abbr = law["abbreviation"].strip()
        # Prefer first occurrence by URL
        if url not in unique_by_url:
            unique_by_url[url] = law
        # Also track by abbreviation if not already present
        if abbr and abbr not in unique_by_abbr:
            unique_by_abbr[abbr] = law
    # Merge both sets, prioritizing unique URLs
    deduped_laws = list(unique_by_url.values())
    # Add any unique abbreviations not already in the URL set
    for abbr, law in unique_by_abbr.items():
        if law["url"].strip() not in unique_by_url:
            deduped_laws.append(law)
    print(f"Total laws found: {len(all_laws)} | Unique: {len(deduped_laws)}")
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(deduped_laws, f, ensure_ascii=False, indent=2)
    print(f"Saved deduplicated law index to {OUT_PATH}")
    unique_by_abbr: dict[str, dict[str, str]] = {}
    for law in all_laws:
        url = law["url"].strip()
        abbr = law["abbreviation"].strip()
        # Prefer first occurrence by URL
        if url not in unique_by_url:
            unique_by_url[url] = law
        # Also track by abbreviation if not already present
        if abbr and abbr not in unique_by_abbr:
            unique_by_abbr[abbr] = law

    # Merge both sets, prioritizing unique URLs
    deduped_laws = list(unique_by_url.values())
    # Add any unique abbreviations not already in the URL set
    for abbr, law in unique_by_abbr.items():
        if law["url"].strip() not in unique_by_url:
            deduped_laws.append(law)

    print(f"Total laws found: {len(all_laws)} | Unique: {len(deduped_laws)}")
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(deduped_laws, f, ensure_ascii=False, indent=2)
    print(f"Saved deduplicated law index to {OUT_PATH}")

if __name__ == "__main__":
    main()
