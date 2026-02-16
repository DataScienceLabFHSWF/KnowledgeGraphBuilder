"""Analytics module for Knowledge Graph enhancement and measurement.

Provides semantic enhancement (OWL-RL inference, SKOS enrichment),
graph analytics (centrality, connectivity, community detection),
embedding analysis, GraphSAGE structural embeddings, visualization,
and cross-setting comparison tools.
"""

from __future__ import annotations

from kgbuilder.analytics.comparison import (
    ComparisonResult,
    SettingProfile,
    compare_settings,
    extract_profile,
    generate_quality_argument,
)
from kgbuilder.analytics.embeddings import (
    AlignmentResult,
    CoherenceResult,
    DimensionReduction,
    EmbeddingAnalysis,
    EmbeddingCluster,
    run_embedding_analysis,
)
from kgbuilder.analytics.graphsage import (
    GraphSAGEResult,
    run_graphsage_analysis,
)
from kgbuilder.analytics.interactive_plots import (
    interactive_centrality_heatmap,
    interactive_centrality_topk,
    interactive_community_explorer,
    interactive_degree_distribution,
    interactive_graph,
    interactive_radar_comparison,
    interactive_power_law_fit,
    interactive_nmi_heatmap,
    interactive_modularity_histogram,
    interactive_per_type_degree,
    save_all_interactive_plots,
)
from kgbuilder.analytics.plots import (
    plot_analytics_dashboard,
    plot_centrality_correlation,
    plot_centrality_topk,
    plot_cluster_community_confusion,
    plot_community_sizes,
    plot_degree_distribution,
    plot_divergent_entities,
    plot_embedding_scatter,
    plot_graph_layout,
    plot_graphsage_loss,
    plot_metric_comparison,
    plot_radar_comparison,
    plot_structural_vs_semantic,
    save_all_plots,
)
from kgbuilder.analytics.statistical import (
    BaselineModularityResult,
    BootstrapCI,
    NMIResult,
    PerTypeDegreeStats,
    PowerLawResult,
    SmallWorldResult,
    StatisticalAnalysis,
    baseline_modularity,
    bootstrap_ci,
    community_ontology_nmi,
    per_type_degree_stats,
    power_law_test,
    run_statistical_analysis,
    small_world_sigma,
)
from kgbuilder.analytics.entity_resolver import EntityResolver, ClusterResult
from kgbuilder.analytics.er_runner import find_merge_candidates
from kgbuilder.analytics.structural import (
    CentralityResult,
    CommunityResult,
    StructuralAnalysis,
    TopologyResult,
    run_structural_analysis,
)

__all__ = [
    # Existing
    "Neo4jInferenceEngine",
    "SKOSEnricher",
    "GraphMetrics",
    "AnalyticsPipeline",
    # Structural
    "CentralityResult",
    "CommunityResult",
    "TopologyResult",
    "StructuralAnalysis",
    "run_structural_analysis",
    # Statistical rigor
    "PowerLawResult",
    "NMIResult",
    "BaselineModularityResult",
    "SmallWorldResult",
    "BootstrapCI",
    "PerTypeDegreeStats",
    "StatisticalAnalysis",
    "power_law_test",
    "community_ontology_nmi",
    "baseline_modularity",
    "small_world_sigma",
    "bootstrap_ci",
    "per_type_degree_stats",
    "run_statistical_analysis",
    # Entity resolution
    "EntityResolver",
    "ClusterResult",
    "find_merge_candidates",
    # Embeddings
    "EmbeddingCluster",
    "DimensionReduction",
    "AlignmentResult",
    "CoherenceResult",
    "EmbeddingAnalysis",
    "run_embedding_analysis",
    # GraphSAGE
    "GraphSAGEResult",
    "run_graphsage_analysis",
    # Plots
    "plot_degree_distribution",
    "plot_centrality_topk",
    "plot_centrality_correlation",
    "plot_community_sizes",
    "plot_graph_layout",
    "plot_embedding_scatter",
    "plot_cluster_community_confusion",
    "plot_graphsage_loss",
    "plot_structural_vs_semantic",
    "plot_divergent_entities",
    "plot_radar_comparison",
    "plot_metric_comparison",
    "plot_analytics_dashboard",
    "save_all_plots",
    # Interactive plots
    "interactive_graph",
    "interactive_centrality_topk",
    "interactive_community_explorer",
    "interactive_degree_distribution",
    "interactive_power_law_fit",
    "interactive_nmi_heatmap",
    "interactive_modularity_histogram",
    "interactive_per_type_degree",
    "interactive_centrality_heatmap",
    "interactive_radar_comparison",
    "save_all_interactive_plots",
    # Comparison
    "SettingProfile",
    "ComparisonResult",
    "extract_profile",
    "compare_settings",
    "generate_quality_argument",
]
