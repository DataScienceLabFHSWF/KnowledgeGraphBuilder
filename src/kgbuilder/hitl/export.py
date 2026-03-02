"""Export KG and ontology artefacts to interactive HTML for expert inspection.

Generates self-contained HTML files with embedded JS (Cytoscape.js / D3.js)
that experts can open locally in a browser — no server required.

Three viewers are produced:
1. **Ontology Viewer** (TBox): Hierarchical tree with class details sidebar
2. **KG Explorer** (ABox): Force-directed graph with zoom/pan/search
3. **Law Graph Navigator**: Paragraph-level view with cross-reference links
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from kgbuilder.hitl.config import ExportConfig

logger = structlog.get_logger(__name__)


class HTMLExporter:
    """Export KG and ontology data to interactive HTML inspection pages.

    Args:
        config: Export configuration including output dir and JS library choice.
    """

    def __init__(self, config: ExportConfig) -> None:
        self._config = config

    def export_ontology_tree(
        self,
        ontology_data: dict[str, list[dict[str, str]]],
        output_path: Path | None = None,
    ) -> Path:
        """Export ontology class hierarchy as an interactive HTML tree.

        The tree view is inspired by Protégé's sidebar: collapsible subtrees,
        click to see properties/axioms/SHACL shapes, annotation panel for
        expert feedback.

        Args:
            ontology_data: Dict with keys 'classes', 'properties', 'axioms'.
                Each value is a list of dicts with at minimum 'uri' and 'label'.
            output_path: Override output file path.

        Returns:
            Path to the generated HTML file.
        """
        out = output_path or self._config.output_dir / "ontology_tree.html"
        out.parent.mkdir(parents=True, exist_ok=True)

        html = self._render_ontology_html(ontology_data)
        out.write_text(html, encoding="utf-8")

        logger.info("exported_ontology_tree", path=str(out),
                     class_count=len(ontology_data.get("classes", [])))
        return out

    def export_kg_explorer(
        self,
        nodes: list[dict[str, str]],
        edges: list[dict[str, str]],
        output_path: Path | None = None,
    ) -> Path:
        """Export KG as an interactive force-directed graph.

        Features: zoom/pan, click node for details + provenance,
        search/filter by entity type, link suggestion mode.

        Args:
            nodes: List of dicts with 'id', 'label', 'type', 'properties'.
            edges: List of dicts with 'source', 'target', 'label'.
            output_path: Override output file path.

        Returns:
            Path to the generated HTML file.
        """
        out = output_path or self._config.output_dir / "kg_explorer.html"
        out.parent.mkdir(parents=True, exist_ok=True)

        html = self._render_kg_html(nodes, edges)
        out.write_text(html, encoding="utf-8")

        logger.info("exported_kg_explorer", path=str(out),
                     node_count=len(nodes), edge_count=len(edges))
        return out

    def export_law_graph(
        self,
        paragraphs: list[dict[str, str]],
        cross_refs: list[dict[str, str]],
        output_path: Path | None = None,
    ) -> Path:
        """Export Law Graph as a navigable HTML page.

        Paragraph-level display with cross-reference highlighting
        and links to domain KG entities.

        Args:
            paragraphs: List of dicts with 'id', 'law', 'section', 'text'.
            cross_refs: List of dicts with 'source', 'target'.
            output_path: Override output file path.

        Returns:
            Path to the generated HTML file.
        """
        out = output_path or self._config.output_dir / "law_graph.html"
        out.parent.mkdir(parents=True, exist_ok=True)

        html = self._render_law_html(paragraphs, cross_refs)
        out.write_text(html, encoding="utf-8")

        logger.info("exported_law_graph", path=str(out),
                     paragraph_count=len(paragraphs))
        return out

    # ── Private rendering methods (to be implemented) ─────────────────────

    def _render_ontology_html(
        self, data: dict[str, list[dict[str, str]]],
    ) -> str:
        """Render ontology data into a self-contained HTML string.

        TODO: Implement with D3.js / Cytoscape.js collapsible tree.
        """
        classes_json = json.dumps(data.get("classes", []), indent=2)
        return _ONTOLOGY_TEMPLATE.replace("{{CLASSES_JSON}}", classes_json)

    def _render_kg_html(
        self,
        nodes: list[dict[str, str]],
        edges: list[dict[str, str]],
    ) -> str:
        """Render KG nodes/edges into a self-contained HTML string.

        TODO: Implement with Cytoscape.js force-directed layout.
        """
        graph_json = json.dumps({"nodes": nodes, "edges": edges}, indent=2)
        return _KG_TEMPLATE.replace("{{GRAPH_JSON}}", graph_json)

    def _render_law_html(
        self,
        paragraphs: list[dict[str, str]],
        cross_refs: list[dict[str, str]],
    ) -> str:
        """Render law paragraphs into a navigable HTML string.

        TODO: Implement with collapsible law sections + cross-ref links.
        """
        data_json = json.dumps(
            {"paragraphs": paragraphs, "cross_refs": cross_refs}, indent=2,
        )
        return _LAW_TEMPLATE.replace("{{DATA_JSON}}", data_json)


# ── HTML Templates (minimal scaffolds — to be expanded) ──────────────────────

_ONTOLOGY_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ontology Inspector — TBox</title>
  <style>
    body { font-family: 'Fira Sans', sans-serif; margin: 20px; }
    .tree { list-style: none; padding-left: 20px; }
    .tree li { cursor: pointer; padding: 4px 0; }
    .tree li:hover { background: #e3f2fd; }
    .details { border-left: 3px solid #7B1FA2; padding: 12px; margin: 12px 0;
               background: #f5f0ff; }
    .annotation { margin-top: 12px; padding: 8px; border: 1px dashed #ef6c00;
                  background: #fff8e1; }
    #search { padding: 8px; width: 300px; margin-bottom: 16px; font-size: 14px; }
  </style>
</head>
<body>
  <h1>Ontology Inspector (TBox)</h1>
  <input id="search" type="text" placeholder="Search classes...">
  <div id="tree-container"></div>
  <div id="detail-panel" class="details" style="display:none;"></div>
  <div class="annotation">
    <h3>Expert Annotation</h3>
    <textarea id="annotation" rows="3" cols="60"
              placeholder="Flag an issue or suggest a new class..."></textarea>
    <br><button id="submit-annotation">Submit Feedback</button>
  </div>
  <script>
    const classes = {{CLASSES_JSON}};
    // TODO: Build collapsible tree, click handlers, search filter
    const container = document.getElementById('tree-container');
    container.innerHTML = '<pre>' + JSON.stringify(classes, null, 2) + '</pre>';
  </script>
</body>
</html>
"""

_KG_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>KG Explorer — ABox</title>
  <script src="https://unpkg.com/cytoscape@3/dist/cytoscape.min.js"></script>
  <style>
    body { font-family: 'Fira Sans', sans-serif; margin: 0; }
    #cy { width: 100vw; height: 80vh; border-bottom: 1px solid #ccc; }
    #info { padding: 16px; }
    #search { padding: 8px; width: 300px; margin: 12px; font-size: 14px; }
    .link-suggest { color: #c62828; font-weight: bold; }
  </style>
</head>
<body>
  <input id="search" type="text" placeholder="Search entities...">
  <div id="cy"></div>
  <div id="info"><em>Click a node to see details and provenance.</em></div>
  <script>
    const graphData = {{GRAPH_JSON}};
    // TODO: Initialize Cytoscape with force-directed layout
    // TODO: Click handler showing properties, source text, confidence
    // TODO: Link suggestion mode (shift+drag between nodes)
    document.getElementById('info').innerHTML =
      '<pre>' + JSON.stringify(graphData, null, 2).slice(0, 2000) + '...</pre>';
  </script>
</body>
</html>
"""

_LAW_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Law Graph Navigator</title>
  <style>
    body { font-family: 'Fira Sans', sans-serif; margin: 20px; max-width: 900px; }
    .paragraph { padding: 8px; margin: 4px 0; border-left: 3px solid #2e7d32; }
    .paragraph:hover { background: #e8f5e9; }
    .cross-ref { color: #1565C0; text-decoration: underline; cursor: pointer; }
    .law-header { background: #f5f5f5; padding: 12px; margin-top: 20px;
                  border-radius: 4px; }
  </style>
</head>
<body>
  <h1>Law Graph Navigator</h1>
  <div id="law-container"></div>
  <script>
    const data = {{DATA_JSON}};
    // TODO: Render law sections with collapsible paragraphs
    // TODO: Cross-reference links scroll to target paragraph
    // TODO: Show linked domain entities on click
    const container = document.getElementById('law-container');
    container.innerHTML = '<pre>' + JSON.stringify(data, null, 2).slice(0, 3000) + '...</pre>';
  </script>
</body>
</html>
"""
