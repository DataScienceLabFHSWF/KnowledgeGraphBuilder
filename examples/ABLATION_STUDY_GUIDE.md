#!/usr/bin/env python3
"""
Ablation Study Configuration Examples

This document shows how to run the pipeline with different hyperparameters
for ablation studies as documented in Planning/ISSUES_BACKLOG.md Issue #12.10.

All examples assume Fuseki, Qdrant, Neo4j, and Ollama are running.

See: scripts/run_kg_pipeline_on_documents.py --help
"""

# =============================================================================
# BASELINE CONFIGURATION
# =============================================================================

# Standard baseline run with default hyperparameters
python scripts/run_kg_pipeline_on_documents.py

# Output: Baseline KG metrics
# - 3 classes processed
# - 3 questions per class = 9 total questions
# - 5 max iterations
# - 0.85 similarity threshold (7.5-15% deduplication expected)
# - 0.6 confidence threshold


# =============================================================================
# ABLATION 1: QUESTION GENERATION IMPACT
# =============================================================================

# Fewer questions = less comprehensive discovery
python scripts/run_kg_pipeline_on_documents.py --questions-per-class 1

# More questions = potentially better coverage but more computational cost
python scripts/run_kg_pipeline_on_documents.py --questions-per-class 10

# Expected impact:
# - Higher questions_per_class → Higher coverage, longer execution time
# - Lower questions_per_class → Lower coverage, faster execution


# =============================================================================
# ABLATION 2: ITERATION COUNT IMPACT  
# =============================================================================

# Fewer iterations = early convergence
python scripts/run_kg_pipeline_on_documents.py --max-iterations 1

# Standard iterations
python scripts/run_kg_pipeline_on_documents.py --max-iterations 5

# More iterations = potentially complete coverage
python scripts/run_kg_pipeline_on_documents.py --max-iterations 15

# Expected impact:
# - Iteration 1: Initial discovery, high marginal gain
# - Iteration 5: Convergence typically reached
# - Iteration 15: Diminishing returns, high computational cost


# =============================================================================
# ABLATION 3: ENTITY DEDUPLICATION IMPACT
# =============================================================================

# Strict deduplication = fewer nodes, high precision
python scripts/run_kg_pipeline_on_documents.py --similarity-threshold 0.95

# Standard deduplication
python scripts/run_kg_pipeline_on_documents.py --similarity-threshold 0.85

# Lenient deduplication = more nodes, potential duplicates
python scripts/run_kg_pipeline_on_documents.py --similarity-threshold 0.70

# Expected impact:
# - Higher threshold → Fewer nodes, better quality, possible missed relations
# - Lower threshold → More nodes, lower quality, better coverage


# =============================================================================
# ABLATION 4: CONFIDENCE FILTERING IMPACT
# =============================================================================

# Strict confidence = high precision, lower recall
python scripts/run_kg_pipeline_on_documents.py --confidence-threshold 0.85

# Standard confidence
python scripts/run_kg_pipeline_on_documents.py --confidence-threshold 0.60

# Lenient confidence = more entities, potential noise
python scripts/run_kg_pipeline_on_documents.py --confidence-threshold 0.30

# Expected impact:
# - Higher threshold → More conservative extraction, higher precision
# - Lower threshold → More permissive extraction, higher recall


# =============================================================================
# ABLATION 5: RETRIEVAL STRATEGY IMPACT (FusionRAG weights)
# =============================================================================

# Dense-only (semantic similarity)
python scripts/run_kg_pipeline_on_documents.py --dense-weight 1.0 --sparse-weight 0.0

# Standard fusion (70% dense, 30% sparse)
python scripts/run_kg_pipeline_on_documents.py --dense-weight 0.7 --sparse-weight 0.3

# Sparse-only (keyword matching)
python scripts/run_kg_pipeline_on_documents.py --dense-weight 0.0 --sparse-weight 1.0

# Balanced (50/50)
python scripts/run_kg_pipeline_on_documents.py --dense-weight 0.5 --sparse-weight 0.5

# Expected impact:
# - Dense > Sparse: Better semantic understanding, slower
# - Sparse > Dense: Better keyword matching, faster
# - Balanced: Trade-off between both


# =============================================================================
# ABLATION 6: COMBINED EXPERIMENTS
# =============================================================================

# Minimal configuration (fastest, lowest coverage)
python scripts/run_kg_pipeline_on_documents.py \
    --questions-per-class 1 \
    --max-iterations 1 \
    --similarity-threshold 0.95 \
    --confidence-threshold 0.85 \
    --dense-weight 0.5 \
    --sparse-weight 0.5

# Comprehensive configuration (slowest, highest coverage)
python scripts/run_kg_pipeline_on_documents.py \
    --questions-per-class 10 \
    --max-iterations 15 \
    --similarity-threshold 0.70 \
    --confidence-threshold 0.30 \
    --dense-weight 0.7 \
    --sparse-weight 0.3

# Conservative precision-focused configuration
python scripts/run_kg_pipeline_on_documents.py \
    --questions-per-class 3 \
    --max-iterations 10 \
    --similarity-threshold 0.90 \
    --confidence-threshold 0.75 \
    --classes-limit 5

# Aggressive recall-focused configuration
python scripts/run_kg_pipeline_on_documents.py \
    --questions-per-class 8 \
    --max-iterations 8 \
    --similarity-threshold 0.75 \
    --confidence-threshold 0.40 \
    --classes-limit 10


# =============================================================================
# MEASUREMENT FRAMEWORK
# =============================================================================

# For each experiment, capture these metrics:
#
# 1. EXECUTION METRICS
#    - Execution time (seconds)
#    - Questions generated
#    - Entities discovered
#    - Entities synthesized (after dedup)
#    - Neo4j nodes created
#    - Neo4j relationships created
#
# 2. GRAPH QUALITY METRICS (from Neo4j)
#    - Graph density
#    - Connected components
#    - Average degree
#    - Clustering coefficient
#
# 3. COVERAGE METRICS
#    - Ontology class coverage % (how many classes have ≥1 instance)
#    - Relation coverage % (how many relations are instantiated)
#    - Document coverage % (how many docs contributed entities)
#
# 4. SEMANTIC QUALITY METRICS
#    - Average entity confidence
#    - Deduplication rate (% merged during Phase 4c)
#    - Orphan node count (isolated entities)
#
# These metrics feed the comparison dashboard and ablation analysis.


# =============================================================================
# RESEARCH QUESTIONS ANSWERED BY ABLATION
# =============================================================================

# RQ1: Impact of question generation strategy
# -> Compare: --questions-per-class 1,3,5,10
# Metric: Final nodes created, coverage %, execution time

# RQ2: Impact of iterative refinement
# -> Compare: --max-iterations 1,3,5,10,15
# Metric: Convergence iteration, marginal gain per iteration

# RQ3: Impact of deduplication strategy
# -> Compare: --similarity-threshold 0.70,0.80,0.85,0.90,0.95
# Metric: Final nodes, merge rate, graph quality

# RQ4: Impact of confidence filtering
# -> Compare: --confidence-threshold 0.30,0.50,0.70,0.85
# Metric: Entity count, average confidence, error rate

# RQ5: Impact of hybrid retrieval
# -> Compare: dense_weight ratios
# Metric: Retrieval precision, recall, execution time

# RQ6: Joint impact (interactions)
# -> Compare: combinations of parameters
# Metric: All above metrics, interaction analysis
