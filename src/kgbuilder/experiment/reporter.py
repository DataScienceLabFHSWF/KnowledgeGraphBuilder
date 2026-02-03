"""Report generation for experiment results.

Generates comprehensive reports in multiple formats (Markdown, JSON, HTML)
summarizing experiment results, metrics, convergence analysis, and visualizations.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from kgbuilder.experiment.analyzer import ComparativeAnalysis, ConvergenceAnalysis

logger = structlog.get_logger(__name__)


@dataclass
class ExperimentReport:
    """Container for experiment report data.
    
    Attributes:
        experiment_name: Name of the experiment.
        timestamp: When report was generated.
        summary: High-level summary statistics.
        convergence: Convergence analysis per variant and metric.
        comparison: Comparative analysis results.
        details: Detailed metrics and raw results.
        visualizations: Paths to generated plots.
    """
    experiment_name: str
    timestamp: str
    summary: dict[str, Any]
    convergence: dict[str, dict[str, ConvergenceAnalysis]]
    comparison: dict[str, ComparativeAnalysis]
    details: dict[str, Any]
    visualizations: dict[str, str] | None = None


class ExperimentReporter:
    """Generate multi-format reports from experiment results.
    
    Creates comprehensive reports in Markdown, JSON, and HTML formats
    summarizing experiment execution, metrics, and analysis results.
    
    Attributes:
        output_dir: Directory for saving reports.
    """
    
    def __init__(self, output_dir: Path | str | None = None) -> None:
        """Initialize reporter.
        
        Args:
            output_dir: Directory to save reports. If None, uses current dir.
        """
        self.output_dir = Path(output_dir) if output_dir else Path(".")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_markdown(
        self,
        report: ExperimentReport,
        include_visualizations: bool = True,
        save_path: str | None = None
    ) -> str:
        """Generate Markdown report.
        
        Creates human-readable Markdown report with sections for summary,
        convergence, comparison, and detailed results. Optionally embeds
        visualization references.
        
        Args:
            report: Experiment report data.
            include_visualizations: Whether to include visualization references.
            save_path: Path to save Markdown file.
        
        Returns:
            Generated Markdown content as string.
        """
        lines = []
        
        # Header
        lines.append(f"# Experiment Report: {report.experiment_name}")
        lines.append("")
        lines.append(f"**Generated:** {report.timestamp}")
        lines.append("")
        
        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        summary = report.summary
        lines.append(f"- **Total Variants:** {summary.get('total_variants', 'N/A')}")
        lines.append(f"- **Total Runs:** {summary.get('total_runs', 'N/A')}")
        lines.append(f"- **Total Duration:** {summary.get('total_duration_hours', 'N/A'):.2f}h")
        lines.append(f"- **Average Run Duration:** {summary.get('avg_run_duration_min', 'N/A'):.2f}min")
        lines.append(f"- **Completed Successfully:** {summary.get('completed_runs', 0)}/{summary.get('total_runs', 0)}")
        lines.append("")
        
        # Best Variant
        best_variant = summary.get("best_variant")
        if best_variant:
            lines.append(f"### Best Performing Variant: **{best_variant['name']}**")
            lines.append("")
            for metric, value in best_variant.get("metrics", {}).items():
                lines.append(f"- {metric}: {value:.4f}")
            lines.append("")
        
        # Convergence Analysis
        if report.convergence:
            lines.append("## Convergence Analysis")
            lines.append("")
            
            for metric, variant_conv in report.convergence.items():
                lines.append(f"### {metric}")
                lines.append("")
                
                for variant, conv in variant_conv.items():
                    lines.append(f"#### {variant}")
                    lines.append("")
                    lines.append("| Statistic | Value |")
                    lines.append("|-----------|-------|")
                    lines.append(f"| Final Value | {conv.final_value:.4f} |")
                    lines.append(f"| Mean | {conv.mean:.4f} |")
                    lines.append(f"| Std Dev | {conv.std_dev:.4f} |")
                    lines.append(f"| Min | {conv.min_value:.4f} |")
                    lines.append(f"| Max | {conv.max_value:.4f} |")
                    
                    if conv.plateaued:
                        lines.append(f"| Plateau Detected | Yes (at run {conv.plateau_start}) |")
                    else:
                        lines.append(f"| Plateau Detected | No |")
                    
                    lines.append("")
                
                if include_visualizations:
                    lines.append(f"![{metric} Convergence]"
                                f"(convergence_{metric.lower()}.png)")
                    lines.append("")
        
        # Comparative Analysis
        if report.comparison:
            lines.append("## Comparative Analysis")
            lines.append("")
            
            for metric, comp in report.comparison.items():
                lines.append(f"### {metric}")
                lines.append("")
                lines.append(f"**Winner:** {comp.best_variant}")
                lines.append(f"**Margin:** {comp.best_margin:.4f}")
                lines.append("")
                
                lines.append("#### Ranking")
                lines.append("")
                lines.append("| Rank | Variant | Score | Margin |")
                lines.append("|------|---------|-------|--------|")
                
                for idx, (variant, score) in enumerate(comp.ranking.items(), 1):
                    margin = comp.margins.get(variant, 0.0)
                    lines.append(f"| {idx} | {variant} | {score:.4f} | {margin:.4f} |")
                
                lines.append("")
                
                if include_visualizations:
                    lines.append(f"![{metric} Comparison](comparison_{metric.lower()}.png)")
                    lines.append("")
        
        # Detailed Results
        if report.details:
            lines.append("## Detailed Results")
            lines.append("")
            
            for variant, metrics in report.details.items():
                lines.append(f"### {variant}")
                lines.append("")
                lines.append("| Metric | Value |")
                lines.append("|--------|-------|")
                
                for metric, value in metrics.items():
                    if isinstance(value, float):
                        lines.append(f"| {metric} | {value:.4f} |")
                    else:
                        lines.append(f"| {metric} | {value} |")
                
                lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*This report was automatically generated by KGBuilder Experiment Framework.*")
        
        content = "\n".join(lines)
        
        if save_path:
            path = Path(save_path) if save_path else self._get_save_path(
                f"{report.experiment_name}_report.md"
            )
            path.write_text(content)
            logger.info("markdown_report_saved", path=str(path))
        
        return content
    
    def generate_json(
        self,
        report: ExperimentReport,
        save_path: str | None = None,
        pretty: bool = True
    ) -> str:
        """Generate JSON report.
        
        Creates machine-readable JSON report with all experiment data
        for further processing or archiving.
        
        Args:
            report: Experiment report data.
            save_path: Path to save JSON file.
            pretty: Whether to pretty-print JSON.
        
        Returns:
            Generated JSON content as string.
        """
        data = {
            "experiment_name": report.experiment_name,
            "timestamp": report.timestamp,
            "summary": report.summary,
            "convergence": {
                metric: {
                    variant: asdict(conv)
                    for variant, conv in variant_conv.items()
                }
                for metric, variant_conv in report.convergence.items()
            },
            "comparison": {
                metric: asdict(comp)
                for metric, comp in report.comparison.items()
            },
            "details": report.details,
            "visualizations": report.visualizations or {}
        }
        
        # Convert dataclass instances to dicts
        def convert_dataclasses(obj: Any) -> Any:
            if hasattr(obj, "__dataclass_fields__"):
                return asdict(obj)
            elif isinstance(obj, dict):
                return {k: convert_dataclasses(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_dataclasses(item) for item in obj]
            return obj
        
        data = convert_dataclasses(data)
        
        indent = 2 if pretty else None
        content = json.dumps(data, indent=indent)
        
        if save_path:
            path = Path(save_path) if save_path else self._get_save_path(
                f"{report.experiment_name}_report.json"
            )
            Path(path).write_text(content)
            logger.info("json_report_saved", path=str(path))
        
        return content
    
    def generate_html(
        self,
        report: ExperimentReport,
        include_visualizations: bool = True,
        save_path: str | None = None
    ) -> str:
        """Generate interactive HTML report.
        
        Creates rich HTML report with styled tables, embedded visualizations,
        and interactive elements for exploring experiment results.
        
        Args:
            report: Experiment report data.
            include_visualizations: Whether to embed visualization images.
            save_path: Path to save HTML file.
        
        Returns:
            Generated HTML content as string.
        """
        html_parts = []
        
        # HTML Header
        html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Experiment Report</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 { color: #2c3e50; margin: 20px 0 10px; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin: 15px 0 8px; }
        h3 { color: #7f8c8d; margin: 10px 0 5px; font-size: 1.1em; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        th {
            background: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #ecf0f1;
        }
        tr:hover { background: #f9f9f9; }
        .summary-box {
            background: #ecf0f1;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .metric {
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 8px 12px;
            margin: 5px 5px 5px 0;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .winner {
            background: #2ecc71;
            padding: 3px 8px;
            border-radius: 3px;
            color: white;
            font-weight: 600;
        }
        .image-container {
            margin: 20px 0;
            text-align: center;
        }
        .image-container img {
            max-width: 100%;
            height: auto;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
""")
        
        # Title and timestamp
        html_parts.append(f"<h1>🧪 Experiment Report: {report.experiment_name}</h1>")
        html_parts.append(f"<p><strong>Generated:</strong> {report.timestamp}</p>")
        
        # Executive Summary
        html_parts.append("<h2>📊 Executive Summary</h2>")
        summary = report.summary
        html_parts.append('<div class="summary-box">')
        html_parts.append(f"<p><strong>Total Variants:</strong> {summary.get('total_variants', 'N/A')}</p>")
        html_parts.append(f"<p><strong>Total Runs:</strong> {summary.get('total_runs', 'N/A')}</p>")
        html_parts.append(
            f"<p><strong>Total Duration:</strong> {summary.get('total_duration_hours', 'N/A'):.2f}h</p>"
        )
        html_parts.append(
            f"<p><strong>Average Run Duration:</strong> {summary.get('avg_run_duration_min', 'N/A'):.2f}min</p>"
        )
        html_parts.append(
            f"<p><strong>Success Rate:</strong> {summary.get('completed_runs', 0)}/{summary.get('total_runs', 0)} "
            f"({summary.get('success_rate', 0):.1%})</p>"
        )
        
        # Best variant
        best = summary.get("best_variant")
        if best:
            html_parts.append(f"<h3>🏆 Best Performing Variant: <span class='winner'>{best['name']}</span></h3>")
            html_parts.append("<div style='margin: 10px 0;'>")
            for metric, value in best.get("metrics", {}).items():
                html_parts.append(f"<span class='metric'>{metric}: {value:.4f}</span>")
            html_parts.append("</div>")
        
        html_parts.append("</div>")
        
        # Convergence Analysis
        if report.convergence:
            html_parts.append("<h2>📈 Convergence Analysis</h2>")
            
            for metric, variant_conv in report.convergence.items():
                html_parts.append(f"<h3>{metric}</h3>")
                
                for variant, conv in variant_conv.items():
                    html_parts.append(f"<h4>{variant}</h4>")
                    html_parts.append("<table>")
                    html_parts.append("<tr><th>Metric</th><th>Value</th></tr>")
                    html_parts.append(f"<tr><td>Final Value</td><td>{conv.final_value:.4f}</td></tr>")
                    html_parts.append(f"<tr><td>Mean</td><td>{conv.mean:.4f}</td></tr>")
                    html_parts.append(f"<tr><td>Std Dev</td><td>{conv.std_dev:.4f}</td></tr>")
                    html_parts.append(f"<tr><td>Min</td><td>{conv.min_value:.4f}</td></tr>")
                    html_parts.append(f"<tr><td>Max</td><td>{conv.max_value:.4f}</td></tr>")
                    
                    plateau_text = f"Yes (run {conv.plateau_start})" if conv.plateaued else "No"
                    html_parts.append(f"<tr><td>Plateau</td><td>{plateau_text}</td></tr>")
                    html_parts.append("</table>")
                
                if include_visualizations and report.visualizations:
                    img_key = f"convergence_{metric.lower()}"
                    if img_key in report.visualizations:
                        html_parts.append(f'<div class="image-container">')
                        html_parts.append(
                            f'<img src="{report.visualizations[img_key]}" alt="{metric} Convergence">'
                        )
                        html_parts.append('</div>')
        
        # Comparative Analysis
        if report.comparison:
            html_parts.append("<h2>⚖️ Comparative Analysis</h2>")
            
            for metric, comp in report.comparison.items():
                html_parts.append(f"<h3>{metric}</h3>")
                html_parts.append(f"<p><strong>Winner:</strong> <span class='winner'>{comp.best_variant}</span></p>")
                html_parts.append(f"<p><strong>Winning Margin:</strong> {comp.best_margin:.4f}</p>")
                
                html_parts.append("<h4>Ranking</h4>")
                html_parts.append("<table>")
                html_parts.append("<tr><th>Rank</th><th>Variant</th><th>Score</th><th>Margin</th></tr>")
                
                for idx, (variant, score) in enumerate(comp.ranking.items(), 1):
                    margin = comp.margins.get(variant, 0.0)
                    html_parts.append(f"<tr><td>{idx}</td><td>{variant}</td><td>{score:.4f}</td><td>{margin:.4f}</td></tr>")
                
                html_parts.append("</table>")
                
                if include_visualizations and report.visualizations:
                    img_key = f"comparison_{metric.lower()}"
                    if img_key in report.visualizations:
                        html_parts.append(f'<div class="image-container">')
                        html_parts.append(
                            f'<img src="{report.visualizations[img_key]}" alt="{metric} Comparison">'
                        )
                        html_parts.append('</div>')
        
        # Detailed Results
        if report.details:
            html_parts.append("<h2>📋 Detailed Results</h2>")
            
            for variant, metrics in report.details.items():
                html_parts.append(f"<h3>{variant}</h3>")
                html_parts.append("<table>")
                html_parts.append("<tr><th>Metric</th><th>Value</th></tr>")
                
                for metric, value in metrics.items():
                    if isinstance(value, float):
                        html_parts.append(f"<tr><td>{metric}</td><td>{value:.4f}</td></tr>")
                    else:
                        html_parts.append(f"<tr><td>{metric}</td><td>{value}</td></tr>")
                
                html_parts.append("</table>")
        
        # Footer
        html_parts.append('<div class="footer">')
        html_parts.append("<p>This report was automatically generated by KGBuilder Experiment Framework.</p>")
        html_parts.append("</div>")
        
        html_parts.append("""
    </div>
</body>
</html>
""")
        
        content = "\n".join(html_parts)
        
        if save_path:
            path = Path(save_path) if save_path else self._get_save_path(
                f"{report.experiment_name}_report.html"
            )
            Path(path).write_text(content)
            logger.info("html_report_saved", path=str(path))
        
        return content
    
    def save_report(
        self,
        report: ExperimentReport,
        formats: list[str] | None = None
    ) -> dict[str, Path]:
        """Save report in multiple formats.
        
        Generates and saves report in specified formats (markdown, json, html).
        
        Args:
            report: Experiment report data.
            formats: List of formats to generate. If None, generates all.
                Valid values: 'markdown', 'json', 'html'
        
        Returns:
            Dict mapping format to saved file path.
        """
        if formats is None:
            formats = ["markdown", "json", "html"]
        
        paths = {}
        
        if "markdown" in formats:
            path = self._get_save_path(f"{report.experiment_name}_report.md")
            self.generate_markdown(report, save_path=str(path))
            paths["markdown"] = path
        
        if "json" in formats:
            path = self._get_save_path(f"{report.experiment_name}_report.json")
            self.generate_json(report, save_path=str(path))
            paths["json"] = path
        
        if "html" in formats:
            path = self._get_save_path(f"{report.experiment_name}_report.html")
            self.generate_html(report, save_path=str(path))
            paths["html"] = path
        
        logger.info("report_saved", formats=formats, paths={k: str(v) for k, v in paths.items()})
        return paths
    
    def _get_save_path(self, filename: str) -> Path:
        """Get save path for a report file.
        
        Args:
            filename: Filename for the report.
        
        Returns:
            Full path in output directory.
        """
        return self.output_dir / filename
