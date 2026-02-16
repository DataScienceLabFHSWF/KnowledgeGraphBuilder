"""Report generation for validation results.

Exports validation results in multiple formats:
- JSON: Machine-readable structured format
- Markdown: Human-readable documentation format
- HTML: Interactive web-based reports

Usage:
    >>> result = validator.validate(kg)
    >>> reporter = ReportGenerator()
    >>> reporter.to_json(result, "report.json")
    >>> reporter.to_markdown(result, "report.md")
    >>> reporter.to_html(result, "report.html")
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from kgbuilder.validation.models import ValidationResult

logger = structlog.get_logger(__name__)


class ReportGenerator:
    """Generate validation reports in multiple formats.

    Supports JSON, Markdown, and HTML output formats.
    Each format can be customized with templates and styles.
    """

    def __init__(self, title: str = "KG Validation Report") -> None:
        """Initialize report generator.

        Args:
            title: Report title for non-JSON formats
        """
        self.title = title
        self.generated_at = datetime.now().isoformat()

    def to_dict(self, result: ValidationResult) -> dict[str, Any]:
        """Convert validation result to dictionary.

        Args:
            result: ValidationResult to convert

        Returns:
            Dictionary representation of validation result
        """
        return {
            "title": self.title,
            "generated_at": self.generated_at,
            "valid": result.valid,
            "metrics": {
                "node_count": result.node_count,
                "edge_count": result.edge_count,
                "violation_count": len(result.violations),
                "rule_violation_count": len(result.rule_violations),
                "pass_rate": round(result.pass_rate, 4),
                "duration_ms": round(result.validation_duration_ms, 2),
            },
            "violations": [v.to_dict() for v in result.violations],
            "rule_violations": [v.to_dict() for v in result.rule_violations],
        }

    def to_json(self, result: ValidationResult, path: str | Path) -> None:
        """Export result as JSON file.

        Args:
            result: ValidationResult to export
            path: Output file path
        """
        try:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            report_dict = self.to_dict(result)
            with open(output_path, "w") as f:
                json.dump(report_dict, f, indent=2)

            logger.info("json_report_generated", path=str(output_path))

        except Exception as e:
            logger.error("json_report_generation_failed", path=str(path), error=str(e))
            raise

    def to_markdown(self, result: ValidationResult, path: str | Path) -> None:
        """Export result as Markdown file.

        Args:
            result: ValidationResult to export
            path: Output file path
        """
        try:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            md_content = self._generate_markdown(result)
            with open(output_path, "w") as f:
                f.write(md_content)

            logger.info("markdown_report_generated", path=str(output_path))

        except Exception as e:
            logger.error("markdown_report_generation_failed", path=str(path), error=str(e))
            raise

    def to_html(self, result: ValidationResult, path: str | Path) -> None:
        """Export result as HTML file.

        Args:
            result: ValidationResult to export
            path: Output file path
        """
        try:
            output_path = Path(path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            html_content = self._generate_html(result)
            with open(output_path, "w") as f:
                f.write(html_content)

            logger.info("html_report_generated", path=str(output_path))

        except Exception as e:
            logger.error("html_report_generation_failed", path=str(path), error=str(e))
            raise

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _generate_markdown(self, result: ValidationResult) -> str:
        """Generate Markdown report content.

        Args:
            result: ValidationResult to format

        Returns:
            Markdown-formatted report
        """
        md_lines = [
            f"# {self.title}",
            "",
            f"**Generated**: {self.generated_at}",
            "",
            "## Summary",
            "",
            f"- **Valid**: {'✓ Yes' if result.valid else '✗ No'}",
            f"- **Pass Rate**: {round(result.pass_rate * 100, 1)}%",
            f"- **Nodes**: {result.node_count}",
            f"- **Edges**: {result.edge_count}",
            f"- **Violations**: {len(result.violations)}",
            f"- **Rule Violations**: {len(result.rule_violations)}",
            f"- **Duration**: {round(result.validation_duration_ms, 2)} ms",
            "",
        ]

        # SHACL Violations
        if result.violations:
            md_lines.extend([
                "## SHACL Violations",
                "",
                "| Severity | Path | Message |",
                "|----------|------|---------|",
            ])

            for v in result.violations:
                severity = v.severity.value
                path = v.path or "—"
                message = v.message or "—"
                md_lines.append(f"| {severity} | `{path}` | {message} |")

            md_lines.append("")
        else:
            # Explicit helpful message when there are no violations
            md_lines.extend(["\nNo violations found\n"])

        # Rule Violations
        if result.rule_violations:
            md_lines.extend([
                "## Rule Violations",
                "",
                "| Rule | Subject | Predicate | Object | Reason |",
                "|------|---------|-----------|--------|--------|",
            ])

            for v in result.rule_violations:
                rule = v.rule_name or "—"
                subject = v.subject_id or "—"
                predicate = v.predicate or "—"
                obj = v.object_id or "—"
                reason = v.reason or "—"
                md_lines.append(f"| {rule} | {subject} | {predicate} | {obj} | {reason} |")

            md_lines.append("")

        return "\n".join(md_lines)

    def _generate_html(self, result: ValidationResult) -> str:
        """Generate HTML report content.

        Args:
            result: ValidationResult to format

        Returns:
            HTML-formatted report
        """
        status_icon = "[OK]" if result.valid else "[FAIL]"
        status_color = "green" if result.valid else "red"

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            '  <meta charset="UTF-8">',
            f"  <title>{self.title}</title>",
            "  <style>",
            "    body { font-family: Arial, sans-serif; margin: 20px; }",
            "    .header { background: #f0f0f0; padding: 20px; border-radius: 5px; }",
            "    .status { font-size: 18px; font-weight: bold; }",
            "    .status-yes { color: green; }",
            "    .status-no { color: red; }",
            "    .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }",
            "    .metric { background: #f9f9f9; padding: 15px; border-left: 4px solid #007bff; }",
            "    .metric-value { font-size: 24px; font-weight: bold; }",
            "    .metric-label { color: #666; }",
            "    table { width: 100%; border-collapse: collapse; margin: 20px 0; }",
            "    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }",
            "    th { background: #007bff; color: white; }",
            "    tr:hover { background: #f5f5f5; }",
            "    .section { margin: 30px 0; }",
            "    h2 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }",
            "    .empty { color: #999; font-style: italic; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <div class='header'>",
            f"    <h1>{self.title}</h1>",
            f"    <div class='status status-{'yes' if result.valid else 'no'}'>",
            f"      {status_icon} {'VALID' if result.valid else 'INVALID'}",
            "    </div>",
            f"    <p><small>Generated: {self.generated_at}</small></p>",
            "  </div>",
        ]

        # Metrics
        html_parts.extend([
            "  <div class='metrics'>",
            "    <div class='metric'>",
            f"      <div class='metric-value'>{result.node_count}</div>",
            "      <div class='metric-label'>Nodes</div>",
            "    </div>",
            "    <div class='metric'>",
            f"      <div class='metric-value'>{result.edge_count}</div>",
            "      <div class='metric-label'>Edges</div>",
            "    </div>",
            "    <div class='metric'>",
            f"      <div class='metric-value'>{round(result.pass_rate * 100, 1)}%</div>",
            "      <div class='metric-label'>Pass Rate</div>",
            "    </div>",
            "  </div>",
        ])

        # SHACL Violations
        html_parts.append("  <div class='section'>")
        html_parts.append("    <h2>SHACL Violations</h2>")

        if result.violations:
            html_parts.extend([
                "    <table>",
                "      <thead>",
                "        <tr>",
                "          <th>Severity</th>",
                "          <th>Path</th>",
                "          <th>Message</th>",
                "          <th>Expected</th>",
                "        </tr>",
                "      </thead>",
                "      <tbody>",
            ])

            for v in result.violations:
                html_parts.append("        <tr>")
                html_parts.append(f"          <td>{v.severity.value}</td>")
                html_parts.append(f"          <td><code>{v.path or '—'}</code></td>")
                html_parts.append(f"          <td>{v.message or '—'}</td>")
                html_parts.append(f"          <td>{v.expected or '—'}</td>")
                html_parts.append("        </tr>")

            html_parts.extend([
                "      </tbody>",
                "    </table>",
            ])
        else:
            html_parts.append("    <p class='empty'>No violations found</p>")

        html_parts.append("  </div>")

        # Rule Violations
        html_parts.append("  <div class='section'>")
        html_parts.append("    <h2>Rule Violations</h2>")

        if result.rule_violations:
            html_parts.extend([
                "    <table>",
                "      <thead>",
                "        <tr>",
                "          <th>Rule</th>",
                "          <th>Subject</th>",
                "          <th>Predicate</th>",
                "          <th>Object</th>",
                "          <th>Reason</th>",
                "        </tr>",
                "      </thead>",
                "      <tbody>",
            ])

            for v in result.rule_violations:
                html_parts.append("        <tr>")
                html_parts.append(f"          <td>{v.rule_name or '—'}</td>")
                html_parts.append(f"          <td><code>{v.subject_id or '—'}</code></td>")
                html_parts.append(f"          <td>{v.predicate or '—'}</td>")
                html_parts.append(f"          <td><code>{v.object_id or '—'}</code></td>")
                html_parts.append(f"          <td>{v.reason or '—'}</td>")
                html_parts.append("        </tr>")

            html_parts.extend([
                "      </tbody>",
                "    </table>",
            ])
        else:
            html_parts.append("    <p class='empty'>No rule violations found</p>")

        html_parts.extend([
            "  </div>",
            "</body>",
            "</html>",
        ])

        return "\n".join(html_parts)
