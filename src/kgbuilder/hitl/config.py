"""Configuration for the HITL review system."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ExportConfig(BaseModel):
    """Configuration for HTML export of KG / ontology artefacts."""

    output_dir: Path = Path("output/hitl_export")
    include_ontology_tree: bool = True
    include_kg_explorer: bool = True
    include_law_graph: bool = True
    max_nodes_per_page: int = Field(default=500, ge=10, le=5000)
    js_library: str = "cytoscape"  # "cytoscape" | "vis" | "d3"
    enable_annotations: bool = True
    embed_source_text: bool = True


class GapDetectionConfig(BaseModel):
    """Configuration for gap detection triggers."""

    min_confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="QA answers below this confidence trigger review",
    )
    min_untyped_entity_ratio: float = Field(
        default=0.1, ge=0.0, le=1.0,
        description="If >10% of entities are untyped, trigger gap detection",
    )
    auto_trigger_on_new_docs: bool = True
    gap_report_output: Path = Path("output/hitl_export/gap_reports")


class FeedbackConfig(BaseModel):
    """Configuration for feedback collection and ingestion."""

    feedback_store: Path = Path("output/hitl_export/feedback")
    require_rationale: bool = True
    min_reviewers_per_item: int = Field(default=1, ge=1, le=5)
    auto_apply_accepted: bool = False  # Safety: require manual confirmation


class HITLConfig(BaseModel):
    """Top-level HITL system configuration."""

    export: ExportConfig = Field(default_factory=ExportConfig)
    gap_detection: GapDetectionConfig = Field(default_factory=GapDetectionConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
