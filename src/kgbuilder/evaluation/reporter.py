"""Report generation for QA evaluation.

Generates evaluation reports in multiple formats (Markdown, JSON, HTML).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import structlog

from kgbuilder.evaluation.metrics import EvaluationMetrics

logger = structlog.get_logger(__name__)


@dataclass
class EvaluationReport:
    """Evaluation report.

    Attributes:
        title: Report title
        metrics: EvaluationMetrics
        results_summary: Summary of individual results
        timestamp: When report was generated
        metadata: Additional metadata
    """

    title: str
    metrics: EvaluationMetrics
    results_summary: list[dict[str, Any]] | None = None
    timestamp: str = ""
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "timestamp": self.timestamp,
            "metrics": self.metrics.to_dict(),
            "results_summary": self.results_summary or [],
            "metadata": self.metadata or {},
        }


class EvaluationReporter:
    """Generate evaluation reports in multiple formats."""

    def __init__(self) -> None:
        """Initialize reporter."""
        logger.info("evaluation_reporter_initialized")

    def generate_markdown(self, report: EvaluationReport) -> str:
        """Generate Markdown report.

        Args:
            report: EvaluationReport

        Returns:
            Markdown-formatted report string
        """
        lines = [
            f"# {report.title}",
            "",
            f"**Generated:** {report.timestamp}",
            "",
            "## Summary",
            "",
            f"- **Total Questions:** {report.metrics.total_questions}",
            f"- **Correct Answers:** {report.metrics.correct_answers}",
            f"- **Accuracy:** {report.metrics.accuracy:.1%}",
            f"- **Coverage:** {report.metrics.coverage:.1%}",
            f"- **Average Response Time:** {report.metrics.average_response_time:.1f}ms",
            "",
            "## Metrics",
            "",
            "| Metric | Score |",
            "|--------|-------|",
            f"| Accuracy | {report.metrics.accuracy:.4f} |",
            f"| Precision | {report.metrics.precision:.4f} |",
            f"| Recall | {report.metrics.recall:.4f} |",
            f"| F1 Score | {report.metrics.f1_score:.4f} |",
            f"| Coverage | {report.metrics.coverage:.4f} |",
            f"| Completeness | {report.metrics.completeness:.4f} |",
            "",
        ]

        # Metrics by type
        if report.metrics.by_type:
            lines.extend(["## Metrics by Query Type", "", "| Type | Accuracy | Precision | Recall | F1 |", "|------|----------|-----------|--------|-----|"])

            for query_type, metrics in report.metrics.by_type.items():
                lines.append(
                    f"| {query_type} | {metrics.get('accuracy', 0):.4f} | "
                    f"{metrics.get('precision', 0):.4f} | {metrics.get('recall', 0):.4f} | "
                    f"{metrics.get('f1', 0):.4f} |"
                )

            lines.append("")

        # Metrics by difficulty
        if report.metrics.by_difficulty:
            lines.extend(
                [
                    "## Metrics by Difficulty",
                    "",
                    "| Difficulty | Accuracy | Precision | Recall | F1 | Count |",
                    "|------------|----------|-----------|--------|-----|-------|",
                ]
            )

            for difficulty, metrics in report.metrics.by_difficulty.items():
                lines.append(
                    f"| {difficulty} | {metrics.get('accuracy', 0):.4f} | "
                    f"{metrics.get('precision', 0):.4f} | {metrics.get('recall', 0):.4f} | "
                    f"{metrics.get('f1', 0):.4f} | {metrics.get('count', 0)} |"
                )

            lines.append("")

        # Individual results summary (if provided)
        if report.results_summary and len(report.results_summary) > 0:
            lines.extend(
                [
                    "## Sample Results",
                    "",
                    "| Question ID | Type | Retrieved | Error |",
                    "|-------------|------|-----------|-------|",
                ]
            )

            # Show first 10 results
            for result in report.results_summary[:10]:
                question_id = result.get("question_id", "")
                query_type = result.get("query_type", "")
                retrieved_count = len(result.get("retrieved_answers", []))
                error = result.get("error", "")

                error_str = f"[ERROR] {error[:30]}..." if error else "[OK]"
                lines.append(
                    f"| {question_id} | {query_type} | {retrieved_count} | {error_str} |"
                )

            lines.append("")

        # Metadata
        if report.metadata:
            lines.extend(["## Metadata", ""])
            for key, value in report.metadata.items():
                lines.append(f"- **{key}:** {value}")

        return "\n".join(lines)

    def generate_json(self, report: EvaluationReport) -> str:
        """Generate JSON report.

        Args:
            report: EvaluationReport

        Returns:
            JSON-formatted report string
        """
        data = report.to_dict()
        return json.dumps(data, indent=2)

    def generate_html(self, report: EvaluationReport) -> str:
        """Generate HTML report.

        Args:
            report: EvaluationReport

        Returns:
            HTML-formatted report string
        """
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            f"<title>{report.title}</title>",
            "<style>",
            """
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 20px;
    background-color: #f5f5f5;
}
.container {
    max-width: 1200px;
    margin: 0 auto;
    background-color: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
h1, h2 {
    color: #333;
}
.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
    margin: 20px 0;
}
.summary-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 15px;
    border-radius: 8px;
    text-align: center;
}
.summary-card.success { background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%); }
.summary-card.warning { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
.metric-value {
    font-size: 28px;
    font-weight: bold;
    margin: 10px 0;
}
.metric-label {
    font-size: 12px;
    opacity: 0.9;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
}
th, td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #ddd;
}
th {
    background-color: #f9f9f9;
    font-weight: bold;
}
tr:hover { background-color: #f9f9f9; }
.timestamp {
    color: #666;
    font-size: 14px;
    margin-bottom: 20px;
}
            """,
            "</style>",
            "</head>",
            "<body>",
            "<div class='container'>",
            f"<h1>{report.title}</h1>",
            f"<p class='timestamp'>Generated: {report.timestamp}</p>",
        ]

        # Summary cards
        html_parts.extend(
            [
                "<h2>Summary</h2>",
                "<div class='summary-grid'>",
                f"""<div class='summary-card success'>
    <div class='metric-label'>Accuracy</div>
    <div class='metric-value'>{report.metrics.accuracy:.1%}</div>
</div>""",
                f"""<div class='summary-card'>
    <div class='metric-label'>F1 Score</div>
    <div class='metric-value'>{report.metrics.f1_score:.4f}</div>
</div>""",
                f"""<div class='summary-card success'>
    <div class='metric-label'>Coverage</div>
    <div class='metric-value'>{report.metrics.coverage:.1%}</div>
</div>""",
                f"""<div class='summary-card'>
    <div class='metric-label'>Questions</div>
    <div class='metric-value'>{report.metrics.total_questions}</div>
</div>""",
                "</div>",
            ]
        )

        # Metrics table
        html_parts.extend(
            [
                "<h2>Detailed Metrics</h2>",
                "<table>",
                "<tr><th>Metric</th><th>Score</th></tr>",
                f"<tr><td>Accuracy</td><td>{report.metrics.accuracy:.4f}</td></tr>",
                f"<tr><td>Precision</td><td>{report.metrics.precision:.4f}</td></tr>",
                f"<tr><td>Recall</td><td>{report.metrics.recall:.4f}</td></tr>",
                f"<tr><td>F1 Score</td><td>{report.metrics.f1_score:.4f}</td></tr>",
                f"<tr><td>Coverage</td><td>{report.metrics.coverage:.4f}</td></tr>",
                f"<tr><td>Completeness</td><td>{report.metrics.completeness:.4f}</td></tr>",
                f"<tr><td>Avg Response Time (ms)</td><td>{report.metrics.average_response_time:.2f}</td></tr>",
                "</table>",
            ]
        )

        # By type
        if report.metrics.by_type:
            html_parts.extend(
                [
                    "<h2>Metrics by Query Type</h2>",
                    "<table>",
                    "<tr><th>Type</th><th>Accuracy</th><th>Precision</th><th>Recall</th><th>F1</th><th>Count</th></tr>",
                ]
            )

            for query_type, metrics in report.metrics.by_type.items():
                html_parts.append(
                    f"""<tr>
    <td>{query_type}</td>
    <td>{metrics.get('accuracy', 0):.4f}</td>
    <td>{metrics.get('precision', 0):.4f}</td>
    <td>{metrics.get('recall', 0):.4f}</td>
    <td>{metrics.get('f1', 0):.4f}</td>
    <td>{metrics.get('count', 0)}</td>
</tr>"""
                )

            html_parts.append("</table>")

        # By difficulty
        if report.metrics.by_difficulty:
            html_parts.extend(
                [
                    "<h2>Metrics by Difficulty</h2>",
                    "<table>",
                    "<tr><th>Difficulty</th><th>Accuracy</th><th>Precision</th><th>Recall</th><th>F1</th><th>Count</th></tr>",
                ]
            )

            for difficulty, metrics in report.metrics.by_difficulty.items():
                html_parts.append(
                    f"""<tr>
    <td>{difficulty}</td>
    <td>{metrics.get('accuracy', 0):.4f}</td>
    <td>{metrics.get('precision', 0):.4f}</td>
    <td>{metrics.get('recall', 0):.4f}</td>
    <td>{metrics.get('f1', 0):.4f}</td>
    <td>{metrics.get('count', 0)}</td>
</tr>"""
                )

            html_parts.append("</table>")

        html_parts.extend(
            [
                "</div>",
                "</body>",
                "</html>",
            ]
        )

        return "\n".join(html_parts)

    def save_report(
        self,
        report: EvaluationReport,
        filepath: str,
        format: str = "json",
    ) -> None:
        """Save report to file.

        Args:
            report: EvaluationReport
            filepath: Path to save report to
            format: Report format ("json", "markdown", "html")

        Raises:
            ValueError: If unsupported format
        """
        if format == "json":
            content = self.generate_json(report)
        elif format == "markdown":
            content = self.generate_markdown(report)
        elif format == "html":
            content = self.generate_html(report)
        else:
            raise ValueError(f"Unsupported format: {format}")

        with open(filepath, "w") as f:
            f.write(content)

        logger.info("report_saved", filepath=filepath, format=format)
