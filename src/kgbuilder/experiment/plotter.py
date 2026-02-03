"""Visualization module for experiment results.

Provides plotting and visualization of experiment metrics, convergence
analysis, and comparative results across multiple KG builder variants.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.figure import Figure
from matplotlib.axes import Axes

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PlotConfig:
    """Configuration for plot generation.
    
    Attributes:
        figsize: Figure size as (width, height) in inches.
        dpi: Resolution in dots per inch.
        style: Matplotlib style (seaborn, ggplot, default).
        colors: Color palette for plots.
        font_size: Base font size for labels.
        line_width: Line width for plot lines.
    """
    figsize: tuple[float, float] = (12, 6)
    dpi: int = 100
    style: str = "seaborn-v0_8-darkgrid"
    colors: list[str] | None = None
    font_size: int = 10
    line_width: float = 2.0
    
    def __post_init__(self) -> None:
        """Initialize default colors if not provided."""
        if self.colors is None:
            self.colors = [
                "#1f77b4",  # blue
                "#ff7f0e",  # orange
                "#2ca02c",  # green
                "#d62728",  # red
                "#9467bd",  # purple
                "#8c564b",  # brown
                "#e377c2",  # pink
                "#7f7f7f",  # gray
            ]


class ExperimentPlotter:
    """Generate visualizations for experiment results.
    
    Creates plots for convergence analysis, variant comparison, parameter
    sensitivity, and metric distributions. Supports multiple export formats.
    
    Attributes:
        config: Plot configuration settings.
        output_dir: Directory for saving plots.
    """
    
    def __init__(
        self,
        output_dir: Path | str | None = None,
        config: PlotConfig | None = None
    ) -> None:
        """Initialize the plotter.
        
        Args:
            output_dir: Directory to save plots. If None, uses current dir.
            config: Plot configuration. If None, uses defaults.
        """
        self.output_dir = Path(output_dir) if output_dir else Path(".")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or PlotConfig()
        
        # Apply style
        try:
            plt.style.use(self.config.style)
        except Exception:
            logger.debug("style_not_found", style=self.config.style)
    
    def plot_convergence(
        self,
        convergence_data: dict[str, list[float]],
        metric_name: str = "Accuracy",
        save_path: str | None = None,
        show: bool = False
    ) -> Figure:
        """Plot convergence curves for each variant.
        
        Shows how metrics improve (or plateau) across iterations for each
        KG builder configuration variant.
        
        Args:
            convergence_data: Dict mapping variant names to metric values
                across iterations. E.g., {"baseline": [0.5, 0.7, 0.75], ...}
            metric_name: Name of metric being plotted (for title/labels).
            save_path: Path to save plot. If None, uses output_dir.
            show: Whether to display plot interactively.
        
        Returns:
            Matplotlib figure object.
        """
        fig, ax = plt.subplots(figsize=self.config.figsize, dpi=self.config.dpi)
        
        for idx, (variant, values) in enumerate(convergence_data.items()):
            color = self.config.colors[idx % len(self.config.colors)]
            iterations = list(range(1, len(values) + 1))
            ax.plot(
                iterations,
                values,
                marker="o",
                label=variant,
                color=color,
                linewidth=self.config.line_width,
                markersize=8
            )
        
        ax.set_xlabel("Iteration", fontsize=self.config.font_size + 2)
        ax.set_ylabel(metric_name, fontsize=self.config.font_size + 2)
        ax.set_title(
            f"{metric_name} Convergence Across Iterations",
            fontsize=self.config.font_size + 4,
            fontweight="bold"
        )
        ax.legend(loc="best", fontsize=self.config.font_size)
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        
        if save_path or not show:
            path = Path(save_path) if save_path else self._get_save_path(
                f"convergence_{metric_name.lower()}.png"
            )
            fig.savefig(path, dpi=self.config.dpi, bbox_inches="tight")
            logger.info("convergence_plot_saved", path=str(path), metric=metric_name)
        
        if show:
            plt.show()
        
        return fig
    
    def plot_comparison(
        self,
        variant_metrics: dict[str, dict[str, float]],
        metric_names: list[str] | None = None,
        save_path: str | None = None,
        show: bool = False
    ) -> Figure:
        """Plot variant comparison as grouped bar charts.
        
        Compares performance metrics across variants for easy visual ranking.
        
        Args:
            variant_metrics: Dict mapping variant names to metric dicts.
                E.g., {"baseline": {"accuracy": 0.75, "f1": 0.73}, ...}
            metric_names: Specific metrics to plot. If None, uses all.
            save_path: Path to save plot.
            show: Whether to display plot interactively.
        
        Returns:
            Matplotlib figure object.
        """
        # Extract metrics
        if not variant_metrics:
            logger.warning("comparison_empty_data")
            return plt.figure()
        
        if metric_names is None:
            metric_names = list(next(iter(variant_metrics.values())).keys())
        
        variants = list(variant_metrics.keys())
        x = np.arange(len(metrics := metric_names))
        width = 0.8 / len(variants)
        
        fig, ax = plt.subplots(
            figsize=(max(12, len(metrics) * 2), 6),
            dpi=self.config.dpi
        )
        
        for idx, variant in enumerate(variants):
            values = [
                variant_metrics[variant].get(m, 0.0)
                for m in metric_names
            ]
            offset = width * (idx - len(variants) / 2 + 0.5)
            color = self.config.colors[idx % len(self.config.colors)]
            ax.bar(x + offset, values, width, label=variant, color=color)
        
        ax.set_xlabel("Metric", fontsize=self.config.font_size + 2)
        ax.set_ylabel("Score", fontsize=self.config.font_size + 2)
        ax.set_title(
            "Variant Comparison",
            fontsize=self.config.font_size + 4,
            fontweight="bold"
        )
        ax.set_xticks(x)
        ax.set_xticklabels(metric_names, rotation=45, ha="right")
        ax.legend(loc="best", fontsize=self.config.font_size)
        ax.set_ylim([0, 1.0])
        ax.grid(True, alpha=0.3, axis="y")
        
        fig.tight_layout()
        
        if save_path or not show:
            path = Path(save_path) if save_path else self._get_save_path(
                "comparison_metrics.png"
            )
            fig.savefig(path, dpi=self.config.dpi, bbox_inches="tight")
            logger.info("comparison_plot_saved", path=str(path))
        
        if show:
            plt.show()
        
        return fig
    
    def plot_heatmap(
        self,
        data: dict[str, dict[str, float]],
        title: str = "Parameter Sensitivity",
        save_path: str | None = None,
        show: bool = False
    ) -> Figure:
        """Plot parameter sensitivity as heatmap.
        
        Shows how metrics vary across different parameter combinations
        (e.g., confidence vs similarity thresholds).
        
        Args:
            data: Nested dict mapping param1 values to param2->metric maps.
                E.g., {"0.5": {"0.7": 0.75, "0.8": 0.73}, ...}
            title: Plot title.
            save_path: Path to save plot.
            show: Whether to display plot interactively.
        
        Returns:
            Matplotlib figure object.
        """
        if not data:
            logger.warning("heatmap_empty_data")
            return plt.figure()
        
        # Build matrix
        param1_vals = sorted(data.keys())
        param2_vals = sorted(set(
            k for subdict in data.values() for k in subdict.keys()
        ))
        
        matrix = np.zeros((len(param1_vals), len(param2_vals)))
        for i, p1 in enumerate(param1_vals):
            for j, p2 in enumerate(param2_vals):
                matrix[i, j] = data[p1].get(p2, 0.0)
        
        fig, ax = plt.subplots(figsize=self.config.figsize, dpi=self.config.dpi)
        
        im = ax.imshow(matrix, cmap="YlGn", aspect="auto", vmin=0.0, vmax=1.0)
        
        ax.set_xticks(np.arange(len(param2_vals)))
        ax.set_yticks(np.arange(len(param1_vals)))
        ax.set_xticklabels(param2_vals, rotation=45, ha="right")
        ax.set_yticklabels(param1_vals)
        ax.set_xlabel("Parameter 2", fontsize=self.config.font_size + 2)
        ax.set_ylabel("Parameter 1", fontsize=self.config.font_size + 2)
        ax.set_title(title, fontsize=self.config.font_size + 4, fontweight="bold")
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label("Metric Value", fontsize=self.config.font_size)
        
        # Add text annotations
        for i in range(len(param1_vals)):
            for j in range(len(param2_vals)):
                text = ax.text(
                    j, i,
                    f"{matrix[i, j]:.2f}",
                    ha="center", va="center",
                    color="black" if matrix[i, j] > 0.5 else "white",
                    fontsize=self.config.font_size - 1
                )
        
        fig.tight_layout()
        
        if save_path or not show:
            path = Path(save_path) if save_path else self._get_save_path(
                "heatmap_sensitivity.png"
            )
            fig.savefig(path, dpi=self.config.dpi, bbox_inches="tight")
            logger.info("heatmap_plot_saved", path=str(path))
        
        if show:
            plt.show()
        
        return fig
    
    def plot_distribution(
        self,
        variant_distributions: dict[str, list[float]],
        metric_name: str = "Metric",
        save_path: str | None = None,
        show: bool = False
    ) -> Figure:
        """Plot metric distributions across variants.
        
        Shows distribution (box plots and violins) of metrics across
        multiple runs for each variant.
        
        Args:
            variant_distributions: Dict mapping variant names to lists of
                metric values from multiple runs.
                E.g., {"baseline": [0.75, 0.76, 0.74], ...}
            metric_name: Name of metric for title/labels.
            save_path: Path to save plot.
            show: Whether to display plot interactively.
        
        Returns:
            Matplotlib figure object.
        """
        if not variant_distributions:
            logger.warning("distribution_empty_data")
            return plt.figure()
        
        fig, ax = plt.subplots(figsize=self.config.figsize, dpi=self.config.dpi)
        
        variants = list(variant_distributions.keys())
        data = [variant_distributions[v] for v in variants]
        
        # Create violin plot
        parts = ax.violinplot(data, positions=range(len(variants)), widths=0.7)
        
        # Color violins
        for idx, pc in enumerate(parts["bodies"]):
            color = self.config.colors[idx % len(self.config.colors)]
            pc.set_facecolor(color)
            pc.set_alpha(0.7)
        
        # Add box plots on top
        bp = ax.boxplot(
            data,
            positions=range(len(variants)),
            widths=0.3,
            patch_artist=True,
            showmeans=True,
            meanprops=dict(marker="D", markerfacecolor="red", markersize=8)
        )
        
        for patch, variant_idx in zip(bp["boxes"], range(len(variants))):
            color = self.config.colors[variant_idx % len(self.config.colors)]
            patch.set_facecolor(color)
            patch.set_alpha(0.5)
        
        ax.set_xticks(range(len(variants)))
        ax.set_xticklabels(variants)
        ax.set_ylabel(metric_name, fontsize=self.config.font_size + 2)
        ax.set_title(
            f"{metric_name} Distribution Across Variants",
            fontsize=self.config.font_size + 4,
            fontweight="bold"
        )
        ax.grid(True, alpha=0.3, axis="y")
        
        # Legend
        legend_elements = [
            mpatches.Patch(color="red", label="Mean"),
            mpatches.Patch(color="black", label="Median")
        ]
        ax.legend(handles=legend_elements, loc="best", fontsize=self.config.font_size)
        
        fig.tight_layout()
        
        if save_path or not show:
            path = Path(save_path) if save_path else self._get_save_path(
                f"distribution_{metric_name.lower()}.png"
            )
            fig.savefig(path, dpi=self.config.dpi, bbox_inches="tight")
            logger.info("distribution_plot_saved", path=str(path), metric=metric_name)
        
        if show:
            plt.show()
        
        return fig
    
    def plot_parameter_impact(
        self,
        param_name: str,
        param_values: list[str],
        metrics_per_param: dict[str, dict[str, float]],
        save_path: str | None = None,
        show: bool = False
    ) -> Figure:
        """Plot impact of parameter variation on metrics.
        
        Shows how different parameter values affect multiple metrics.
        
        Args:
            param_name: Name of the parameter being varied.
            param_values: List of parameter values tested.
            metrics_per_param: Dict mapping param value to metric dict.
                E.g., {"0.5": {"accuracy": 0.75, "f1": 0.73}, ...}
            save_path: Path to save plot.
            show: Whether to display plot interactively.
        
        Returns:
            Matplotlib figure object.
        """
        if not metrics_per_param:
            logger.warning("parameter_impact_empty_data")
            return plt.figure()
        
        metrics = list(next(iter(metrics_per_param.values())).keys())
        
        fig, ax = plt.subplots(figsize=self.config.figsize, dpi=self.config.dpi)
        
        for idx, metric in enumerate(metrics):
            values = [
                metrics_per_param[p].get(metric, 0.0)
                for p in param_values
            ]
            color = self.config.colors[idx % len(self.config.colors)]
            ax.plot(
                param_values,
                values,
                marker="o",
                label=metric,
                color=color,
                linewidth=self.config.line_width,
                markersize=8
            )
        
        ax.set_xlabel(param_name, fontsize=self.config.font_size + 2)
        ax.set_ylabel("Score", fontsize=self.config.font_size + 2)
        ax.set_title(
            f"Impact of {param_name} on Metrics",
            fontsize=self.config.font_size + 4,
            fontweight="bold"
        )
        ax.legend(loc="best", fontsize=self.config.font_size)
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        
        if save_path or not show:
            path = Path(save_path) if save_path else self._get_save_path(
                f"impact_{param_name.lower()}.png"
            )
            fig.savefig(path, dpi=self.config.dpi, bbox_inches="tight")
            logger.info("parameter_impact_plot_saved", path=str(path), param=param_name)
        
        if show:
            plt.show()
        
        return fig
    
    def export_all_formats(
        self,
        figure: Figure,
        base_name: str
    ) -> dict[str, Path]:
        """Export figure to multiple formats.
        
        Args:
            figure: Matplotlib figure to export.
            base_name: Base filename without extension.
        
        Returns:
            Dict mapping format to saved file path.
        """
        formats = {"png": 300, "pdf": 100, "svg": 100}
        paths = {}
        
        for fmt, dpi in formats.items():
            path = self.output_dir / f"{base_name}.{fmt}"
            figure.savefig(path, format=fmt, dpi=dpi, bbox_inches="tight")
            paths[fmt] = path
            logger.debug("figure_exported", format=fmt, path=str(path))
        
        return paths
    
    def _get_save_path(self, filename: str) -> Path:
        """Get save path for a figure.
        
        Args:
            filename: Filename for the figure.
        
        Returns:
            Full path in output directory.
        """
        return self.output_dir / filename
    
    def create_summary_dashboard(
        self,
        convergence_data: dict[str, dict[str, list[float]]],
        variant_metrics: dict[str, dict[str, float]],
        save_path: str | None = None
    ) -> Figure:
        """Create summary dashboard with multiple plots.
        
        Combines convergence, comparison, and distribution plots into
        a single multi-panel figure.
        
        Args:
            convergence_data: Nested dict with metrics -> variants -> values.
                E.g., {"accuracy": {"baseline": [0.5, 0.7], ...}, ...}
            variant_metrics: Dict mapping variants to metric dicts.
            save_path: Path to save dashboard.
        
        Returns:
            Matplotlib figure object.
        """
        if not convergence_data or not variant_metrics:
            logger.warning("dashboard_empty_data")
            return plt.figure()
        
        metrics = list(convergence_data.keys())
        num_metrics = len(metrics)
        
        fig = plt.figure(
            figsize=(16, 4 + 4 * ((num_metrics + 1) // 2)),
            dpi=self.config.dpi
        )
        
        # Plot convergence for each metric
        for idx, metric in enumerate(metrics):
            ax = fig.add_subplot(((num_metrics + 1) // 2) + 1, 2, idx + 1)
            
            for v_idx, (variant, values) in enumerate(convergence_data[metric].items()):
                color = self.config.colors[v_idx % len(self.config.colors)]
                iterations = list(range(1, len(values) + 1))
                ax.plot(
                    iterations,
                    values,
                    marker="o",
                    label=variant,
                    color=color,
                    linewidth=self.config.line_width,
                    markersize=6
                )
            
            ax.set_xlabel("Iteration", fontsize=self.config.font_size)
            ax.set_ylabel(metric, fontsize=self.config.font_size)
            ax.set_title(f"{metric} Convergence", fontsize=self.config.font_size + 1)
            ax.legend(fontsize=self.config.font_size - 1)
            ax.grid(True, alpha=0.3)
        
        # Add comparison plot
        ax_comp = fig.add_subplot(((num_metrics + 1) // 2) + 1, 2, num_metrics + 1)
        variants = list(variant_metrics.keys())
        x = np.arange(len(metrics))
        width = 0.8 / len(variants)
        
        for v_idx, variant in enumerate(variants):
            values = [variant_metrics[variant].get(m, 0.0) for m in metrics]
            offset = width * (v_idx - len(variants) / 2 + 0.5)
            color = self.config.colors[v_idx % len(self.config.colors)]
            ax_comp.bar(x + offset, values, width, label=variant, color=color)
        
        ax_comp.set_xlabel("Metric", fontsize=self.config.font_size)
        ax_comp.set_ylabel("Score", fontsize=self.config.font_size)
        ax_comp.set_title("Variant Comparison", fontsize=self.config.font_size + 1)
        ax_comp.set_xticks(x)
        ax_comp.set_xticklabels(metrics, rotation=45, ha="right")
        ax_comp.legend(fontsize=self.config.font_size - 1)
        ax_comp.set_ylim([0, 1.0])
        ax_comp.grid(True, alpha=0.3, axis="y")
        
        fig.tight_layout()
        
        if save_path:
            fig.savefig(save_path, dpi=self.config.dpi, bbox_inches="tight")
            logger.info("dashboard_saved", path=str(save_path))
        
        return fig
