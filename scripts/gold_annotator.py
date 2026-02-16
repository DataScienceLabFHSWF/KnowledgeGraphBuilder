"""Static HTML-based gold-standard annotator scaffold.

Generates a single-file HTML annotator that allows highlighting text and
creating entity annotations (span + label). The output can be downloaded
as JSON and moved into `data/evaluation/gold_standard/`.

No server required — colleagues can open the generated HTML in a browser.
"""
from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path

DEFAULT_LABELS = [
    "Paragraf",
    "Gesetzbuch",
    "Behoerde",
    "Betreiber",
    "Facility",
    "Obligation",
    "Permission",
    "Prohibition",
]

HTML_TEMPLATE = """<!doctype html>
<html>
  <head>
    <meta charset='utf-8'/>
    <title>Gold Standard Annotator - {doc_id}</title>
    <style>body{{font-family: sans-serif; padding: 2rem}} .text{{white-space: pre-wrap; border:1px solid #ddd; padding:1rem;}}</style>
  </head>
  <body>
    <h2>Annotator — {doc_id}</h2>
    <div id='text' class='text'>{text}</div>

    <div style='margin-top:1rem'>
      <label>Label: <select id='label'>{label_options}</select></label>
      <button id='add'>Add Annotation</button>
      <button id='download'>Download JSON</button>
    </div>

    <h3>Annotations</h3>
    <pre id='out'>[]</pre>

    <script>
      const textEl = document.getElementById('text');
      const outEl = document.getElementById('out');
      const labelEl = document.getElementById('label');
      const ann = [];

      document.getElementById('add').onclick = () => {
        const sel = window.getSelection();
        const s = sel.toString();
        if (!s) { alert('Select text to annotate'); return; }
        // Find first occurrence of selected text in the full text
        const full = textEl.innerText;
        const start = full.indexOf(s);
        if (start < 0) { alert('Could not find selection in text'); return; }
        const end = start + s.length;
        const label = labelEl.value;
        ann.push({start: start, end: end, text: s, label: label});
        outEl.innerText = JSON.stringify(ann, null, 2);
      };

      document.getElementById('download').onclick = () => {
        const b = new Blob([JSON.stringify({doc_id: '{doc_id}', text: textEl.innerText, entities: ann}, null, 2)], {type: 'application/json'});
        const url = URL.createObjectURL(b);
        const a = document.createElement('a');
        a.href = url; a.download = '{doc_id}_gold.json';
        document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
      };
    </script>
  </body>
</html>"""


def generate_annotator_html(text: str, doc_id: str = "doc", labels: list[str] | None = None) -> str:
    labels = labels or DEFAULT_LABELS
    label_options = "".join(f"<option>{l}</option>" for l in labels)
    return HTML_TEMPLATE.format(doc_id=doc_id, text=text.replace('<', '&lt;').replace('>', '&gt;'), label_options=label_options)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--text-file", help="Path to plaintext document to annotate")
    p.add_argument("--out", default="/tmp/gold_annotator.html")
    p.add_argument("--doc-id", default="doc_annot")
    p.add_argument("--open", action="store_true", help="Open HTML in browser after generation")
    args = p.parse_args(argv)

    if not args.text_file:
        print("Please provide --text-file <path> containing plaintext to annotate")
        return 2

    text = Path(args.text_file).read_text(encoding='utf8')
    html = generate_annotator_html(text, doc_id=args.doc_id)
    out = Path(args.out)
    out.write_text(html, encoding='utf8')
    print(f"Wrote annotator to {out}")
    if args.open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())