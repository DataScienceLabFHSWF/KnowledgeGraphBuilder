"""Shared annotator helper used by scripts and tests."""
from __future__ import annotations

from html import escape
from string import Template
from typing import List

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

HTML_TEMPLATE = Template("""<!doctype html>
<html>
  <head>
    <meta charset='utf-8'/>
    <title>Gold Standard Annotator - $doc_id</title>
    <style>body{font-family: sans-serif; padding: 2rem} .text{white-space: pre-wrap; border:1px solid #ddd; padding:1rem;}</style>
  </head>
  <body>
    <h2>Annotator — $doc_id</h2>
    <div id='text' class='text'>$text</div>

    <div style='margin-top:1rem'>
      <label>Label: <select id='label'>$label_options</select></label>
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
        const b = new Blob([JSON.stringify({doc_id: '$doc_id', text: textEl.innerText, entities: ann}, null, 2)], {type: 'application/json'});
        const url = URL.createObjectURL(b);
        const a = document.createElement('a');
        a.href = url; a.download = '${doc_id}_gold.json';
        document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
      };
    </script>
  </body>
</html>""")


def generate_annotator_html(text: str, doc_id: str = "doc", labels: List[str] | None = None) -> str:
    """Return a self-contained HTML annotator for `text` and `doc_id`.

    Uses Python's stdlib `string.Template` and `html.escape` so the template
    is safe from accidental formatting errors and the text is HTML-escaped.
    """
    labels = labels or DEFAULT_LABELS
    label_options = "".join(f"<option>{escape(l)}</option>" for l in labels)
    safe_text = escape(text)
    return HTML_TEMPLATE.substitute(doc_id=doc_id, text=safe_text, label_options=label_options)

