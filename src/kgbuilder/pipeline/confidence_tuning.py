"""Confidence tuning pipeline orchestrator.

Integrates Phase 5 confidence tuning components into the main KG pipeline:
- Task 5.1: ConfidenceAnalyzer
- Task 5.2: ConfidenceBooster
- Task 5.3: CoreferenceResolver
- Task 5.4: ConfidenceCalibrator
- Task 5.5: ConsensusVoter
- Task 5.6: EntityQualityFilter

Run AFTER discovery extraction, BEFORE semantic enrichment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from kgbuilder.confidence import (
    ConfidenceAnalyzer,
    ConfidenceBooster,
    CoreferenceResolver,
    ConfidenceCalibrator,
    ConsensusVoter,
    EntityQualityFilter,
)
from kgbuilder.core.models import ExtractedEntity, ExtractedRelation

logger = structlog.get_logger(__name__)


@dataclass
class ConfidenceTuningResult:
    """Result from confidence tuning pipeline."""

    total_entities_input: int
    total_entities_output: int
    entities_filtered: int
    avg_confidence_before: float
    avg_confidence_after: float
    coreference_clusters_merged: int
    unique_entities_after_merge: int
    calibration_applied: bool
    consensus_votes_requested: int
    consensus_votes_unanimous: int
    consensus_votes_split: int
    processing_time_sec: float


class ConfidenceTuningPipeline:
    """Orchestrates confidence tuning phases (5.1-5.6).

    Process:
    1. Analyze confidence distribution
    2. Boost based on evidence quality
    3. Resolve coreferences (merge similar entities)
    4. Calibrate confidence → actual correctness
    5. Request consensus votes (optional LLM re-check)
    6. Filter low-quality entities

    Result: High-confidence, deduplicated entity set.
    """

    def __init__(
        self,
        llm_provider: Any | None = None,
        enable_calibration: bool = True,
        enable_consensus_voting: bool = False,
        quality_threshold: float = 0.6,
    ) -> None:
        """Initialize confidence tuning pipeline.

        Args:
            llm_provider: Optional LLM for consensus voting (Task 5.5)
            enable_calibration: Whether to calibrate confidence (Task 5.4)
            enable_consensus_voting: Whether to request second opinions (Task 5.5)
            quality_threshold: Minimum confidence to keep entities (Task 5.6)
        """
        self.llm = llm_provider
        self.enable_calibration = enable_calibration
        self.enable_consensus = enable_consensus_voting
        self.quality_threshold = quality_threshold

        # Initialize components
        self.analyzer = ConfidenceAnalyzer()
        self.booster = ConfidenceBooster()
        self.coreference_resolver = CoreferenceResolver()
        self.calibrator = ConfidenceCalibrator()
        self.voter = ConsensusVoter(llm_provider) if self.llm and enable_consensus_voting else None
        self.filter = EntityQualityFilter(confidence_threshold=quality_threshold)

    def tune(
        self,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation] | None = None,
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation], ConfidenceTuningResult]:
        """Run full confidence tuning pipeline.

        Args:
            entities: Discovered entities from extraction phase
            relations: Discovered relations (optional, preserved as-is)

        Returns:
            Tuple of (tuned_entities, relations, metrics)
        """
        import time

        start_time = time.time()
        if not entities:
            logger.warning("no_entities_to_tune")
            return entities, relations or [], ConfidenceTuningResult(
                total_entities_input=0,
                total_entities_output=0,
                entities_filtered=0,
                avg_confidence_before=0.0,
                avg_confidence_after=0.0,
                coreference_clusters_merged=0,
                unique_entities_after_merge=0,
                calibration_applied=False,
                consensus_votes_requested=0,
                consensus_votes_unanimous=0,
                consensus_votes_split=0,
                processing_time_sec=0.0,
            )

        logger.info("confidence_tuning_start", entity_count=len(entities))

        # Store baseline metrics
        initial_count = len(entities)
        initial_avg_conf = sum(e.confidence for e in entities) / len(entities) if entities else 0.0

        # Task 5.1: Analyze confidence distribution
        logger.info("phase_1_analyze")
        report = self.analyzer.analyze(entities)
        logger.info(
            "confidence_analysis_complete",
            mean=f"{report.mean:.2f}",
            median=f"{report.percentiles[50]:.2f}",
            std_dev=f"{report.std:.2f}",
            anomalies=len(report.anomalies),
        )

        # Task 5.2: Boost confidence based on evidence
        logger.info("phase_2_boost")
        entities = self.booster.boost_batch(entities)
        boosted_avg = sum(e.confidence for e in entities) / len(entities) if entities else 0.0
        logger.info("confidence_boost_complete", avg_before=f"{initial_avg_conf:.2f}", avg_after=f"{boosted_avg:.2f}")

        # Task 5.3: Resolve coreferences (merge similar entities)
        logger.info("phase_3_coreference_resolution")
        clusters = self.coreference_resolver.find_clusters(
            entities,
            similarity_threshold=0.85,
        )
        logger.info("coreference_clusters_found", cluster_count=len(clusters))

        entities_map = {e.id: e for e in entities}
        merged_entities = []
        for cluster in clusters:
            merged = self.coreference_resolver.merge_cluster(cluster, entities_map)
            merged_entities.append(merged)
            logger.debug("cluster_merged", size=len(cluster.entities), result_label=merged.label)

        # Non-clustered entities stay as-is
        clustered_ids: set[str] = set()
        for cluster in clusters:
            clustered_ids.update(cluster.entities)  # entities is list[str] of IDs

        for entity in entities:
            if entity.id not in clustered_ids:
                merged_entities.append(entity)

        entities = merged_entities
        logger.info("coreference_complete", entities_before=initial_count, entities_after=len(entities))

        # Task 5.4: Calibrate confidence (optional)
        calibration_applied = False
        if self.enable_calibration:
            logger.info("phase_4_calibration")
            try:
                calibration_result = self.calibrator.calibrate(entities)
                entities = calibration_result.calibrated_entities
                calibration_applied = True
                logger.info(
                    "calibration_complete",
                    model_used=calibration_result.calibrator_type,
                    correlation=f"{calibration_result.correlation:.3f}",
                )
            except Exception as e:
                logger.warning("calibration_failed", error=str(e))

        # Task 5.5: Consensus voting (optional, if LLM available)
        consensus_votes_requested = 0
        consensus_votes_unanimous = 0
        consensus_votes_split = 0
        if self.voter:
            logger.info("phase_5_consensus_voting")
            try:
                high_confidence = [e for e in entities if e.confidence >= 0.8]
                consensus_votes_requested = len(high_confidence)
                
                voting_results = self.voter.request_votes_batch(high_confidence)
                unanimous = sum(
                    1 for r in voting_results
                    if r.agreement_level == "unanimous"
                )
                split = sum(
                    1 for r in voting_results
                    if r.agreement_level == "split"
                )
                consensus_votes_unanimous = unanimous
                consensus_votes_split = split

                # Update confidence based on votes
                entities_by_id = {e.id: e for e in entities}
                for result in voting_results:
                    if result.entity_id in entities_by_id:
                        entities_by_id[result.entity_id].confidence = result.consensus_confidence

                logger.info(
                    "consensus_voting_complete",
                    votes_requested=consensus_votes_requested,
                    unanimous=unanimous,
                    split=split,
                )
            except Exception as e:
                logger.warning("consensus_voting_failed", error=str(e))

        # Task 5.6: Quality filtering
        logger.info("phase_6_quality_filter")
        entities_pre_filter = len(entities)
        entities = self.filter.filter_entities(
            entities,
            confidence_threshold=self.quality_threshold,
        )
        entities_filtered = entities_pre_filter - len(entities)
        logger.info(
            "quality_filter_complete",
            threshold=f"{self.quality_threshold:.2f}",
            removed=entities_filtered,
            remaining=len(entities),
        )

        # Final metrics
        final_avg_conf = sum(e.confidence for e in entities) / len(entities) if entities else 0.0
        processing_time = time.time() - start_time

        result = ConfidenceTuningResult(
            total_entities_input=initial_count,
            total_entities_output=len(entities),
            entities_filtered=entities_filtered,
            avg_confidence_before=initial_avg_conf,
            avg_confidence_after=final_avg_conf,
            coreference_clusters_merged=len(clusters),
            unique_entities_after_merge=len(entities),
            calibration_applied=calibration_applied,
            consensus_votes_requested=consensus_votes_requested,
            consensus_votes_unanimous=consensus_votes_unanimous,
            consensus_votes_split=consensus_votes_split,
            processing_time_sec=processing_time,
        )

        logger.info(
            "confidence_tuning_complete",
            **{
                "input": result.total_entities_input,
                "output": result.total_entities_output,
                "avg_conf_before": f"{result.avg_confidence_before:.2f}",
                "avg_conf_after": f"{result.avg_confidence_after:.2f}",
                "clusters_merged": result.coreference_clusters_merged,
                "time_sec": f"{result.processing_time_sec:.1f}",
            },
        )

        return entities, relations or [], result
