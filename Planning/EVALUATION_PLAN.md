# Evaluation Plan — Paper A (KG Construction Pipeline)

**Goal**: Produce quantitative results for the conference paper on ontology-driven KG construction.  
**Owner**: Felix (ablation runs, statistical analysis), Ole (parallel ablation axes, scoring)  
**Benchmark queue position**: Step 1 (runs first, ~Mar 16–25)  
**Resource constraint**: Benchmarks run sequentially — only this suite should be running during its window.

---

## Prerequisites

### 1. Services (Docker Compose)

All services must be running before any experiment:

```bash
docker compose up -d
```

| Service | Port | Check |
|---------|------|-------|
| Neo4j | 7474 (browser), 7687 (bolt) | `curl http://localhost:7474` |
| Qdrant | 6333 | `curl http://localhost:6333/health` |
| Fuseki | 3030 | `curl http://localhost:3030/$/ping` |
| Ollama | 18134→11434 | `curl http://localhost:18134/api/tags` |

### 2. Models

Pull required models into Ollama:

```bash
docker exec -it ollama ollama pull qwen3:8b          # primary model
docker exec -it ollama ollama pull llama3.2:3b        # small baseline
```

### 3. Environment

Copy `.env.example` to `.env` and verify:

```
QDRANT_URL=http://localhost:6333
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
FUSEKI_URL=http://localhost:3030
FUSEKI_DATASET=ontology
OLLAMA_URL=http://localhost:18134
OLLAMA_MODEL=qwen3:8b
```

### 4. Data

Ensure documents are in place:
- Nuclear decommissioning docs: `data/documents/nuclear/`
- Law documents: `data/documents/law/`
- Seed ontology: `data/ontology/` (OWL + SHACL shapes)

---

## Phase 1: Statistical Rigor (Quick Wins)

**Who**: Felix  
**Time**: ~1 hour  
**Why**: These are already implemented in `src/kgbuilder/analytics/statistical.py` — just need to run them and capture output.

```bash
# Run structural analysis (includes all 6 statistical metrics)
python -c "
from kgbuilder.analytics.statistical import run_structural_analysis
from kgbuilder.stores import Neo4jStore

store = Neo4jStore()
results = run_structural_analysis(store)
import json
print(json.dumps(results, indent=2))
" > results/statistical_metrics.json
```

**Metrics produced**:
1. Power-law KS test (degree distribution fit)
2. Community vs ontology NMI
3. Modularity vs config-model baseline
4. Small-world sigma (C/L ratios)
5. Bootstrap confidence intervals (edge-resampling)
6. Per-type degree distributions

**Output**: `results/statistical_metrics.json` — include these numbers in Paper A Section 4.

---

## Phase 2: Ablation Study (Core Evaluation)

**Who**: Felix + Ole (split axes between you)  
**Time**: ~5–8 days (runs overnight, one config at a time)  
**Reference**: `examples/ABLATION_STUDY_GUIDE.md`

### Axis 1: Question Generation (Felix)

```bash
for q in 1 3 5 10; do
  python scripts/full_kg_pipeline.py \
    --questions-per-class $q \
    --max-iterations 5 \
    --similarity-threshold 0.85 \
    --confidence-threshold 0.60 \
    2>&1 | tee logs/ablation_questions_${q}.log
  
  # Score the resulting KG
  python scripts/run_kg_scoring.py > results/scoring_questions_${q}.json
  
  # Clear Neo4j for next run (or use separate databases)
done
```

### Axis 2: Iteration Count (Felix)

```bash
for iter in 1 3 5 10 15; do
  python scripts/full_kg_pipeline.py \
    --max-iterations $iter \
    --questions-per-class 3 \
    --similarity-threshold 0.85 \
    --confidence-threshold 0.60 \
    2>&1 | tee logs/ablation_iterations_${iter}.log
  
  python scripts/run_kg_scoring.py > results/scoring_iterations_${iter}.json
done
```

### Axis 3: Entity Deduplication Threshold (Ole)

```bash
for sim in 0.70 0.80 0.85 0.90 0.95; do
  python scripts/full_kg_pipeline.py \
    --similarity-threshold $sim \
    --questions-per-class 3 \
    --max-iterations 5 \
    --confidence-threshold 0.60 \
    2>&1 | tee logs/ablation_similarity_${sim}.log
  
  python scripts/run_kg_scoring.py > results/scoring_similarity_${sim}.json
done
```

### Axis 4: Confidence Filtering (Ole)

```bash
for conf in 0.30 0.45 0.60 0.75 0.85; do
  python scripts/full_kg_pipeline.py \
    --confidence-threshold $conf \
    --questions-per-class 3 \
    --max-iterations 5 \
    --similarity-threshold 0.85 \
    2>&1 | tee logs/ablation_confidence_${conf}.log
  
  python scripts/run_kg_scoring.py > results/scoring_confidence_${conf}.json
done
```

### Axis 5: Retrieval Strategy (Ole)

```bash
for dw in 0.0 0.3 0.5 0.7 1.0; do
  sw=$(python -c "print(round(1.0 - $dw, 1))")
  python scripts/full_kg_pipeline.py \
    --dense-weight $dw \
    --sparse-weight $sw \
    --questions-per-class 3 \
    --max-iterations 5 \
    2>&1 | tee logs/ablation_retrieval_dw${dw}.log
  
  python scripts/run_kg_scoring.py > results/scoring_retrieval_dw${dw}.json
done
```

### Axis 6: Combined Best Config

After reviewing Axes 1–5, run the best combination:

```bash
python scripts/run_experiment.py \
  --config examples/experiment_baseline.json \
  --output experiment_results/ablation_combined/
```

---

## Phase 3: Multi-Variant Experiment (Config-Driven)

**Who**: Felix  
**Time**: ~2–4 hours

Run the pre-built baseline/strict/permissive comparison:

```bash
python scripts/run_experiment.py \
  --config examples/experiment_baseline.json \
  --output experiment_results/baseline/ \
  --formats markdown json html
```

This produces:
- `experiment_results/baseline/report.md` — comparison table
- `experiment_results/baseline/plots/` — visualisations
- W&B dashboard entries (if configured)

---

## Phase 4: KG Quality Scoring

**Who**: Ole  
**Time**: ~10 min per KG

After each ablation run, score the resulting graph:

```bash
# SHACL + structural quality
python scripts/run_kg_scoring.py

# Full validation (ontology + extraction + KG + integration)
python scripts/validate_kg_complete.py --focus complete --output results/validation_full.json
```

**Metrics captured**:
- `consistency` — logical consistency score
- `acceptance_rate` — SHACL shape conformance
- `class_coverage` — ontology class representation in KG
- `shacl_score` — shape validation pass rate
- `violations` — list of SHACL violations
- `combined_score` — weighted aggregate

---

## Phase 5: Law Domain (Second Case Study)

**Who**: Felix  
**Time**: ~1 day

Run the pipeline on German law documents to show domain-agnosticism:

```bash
# Build law ontology
python scripts/build_law_ontology.py

# Build law KG
python scripts/build_law_graph.py

# Score
ONTOLOGY_OWL_PATH=./data/ontology/law/law-ontology-v1.0.owl \
  python scripts/run_kg_scoring.py > results/scoring_law.json

# Validate
python scripts/validate_kg_complete.py --focus complete --output results/validation_law.json
```

---

## Output Checklist (What Goes Into the Paper)

| Result | Script | Paper Section |
|--------|--------|---------------|
| Ablation tables (6 axes × multiple values) | `full_kg_pipeline.py` + `run_kg_scoring.py` | 4.2 Ablation Study |
| Statistical metrics (power-law, NMI, sigma) | `run_structural_analysis()` | 4.3 Quality Analysis |
| SHACL conformance scores | `run_kg_scoring.py` | 4.3 Quality Analysis |
| Validation report | `validate_kg_complete.py` | 4.3 Quality Analysis |
| Baseline/strict/permissive comparison | `run_experiment.py` | 4.2 Ablation Study |
| Law domain scores (second case study) | `build_law_graph.py` + scoring | 4.1 Experimental Setup |
| Execution time per config | Log files | 4.2 Ablation Study |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Ollama OOM on large docs | Reduce `--questions-per-class` or use `llama3.2:3b` for faster runs |
| Neo4j connection refused | Check `docker compose ps`, restart if needed |
| SHACL shapes not found | Verify `STATIC_SHAPES_PATH` and `ONTOLOGY_OWL_PATH` in `.env` |
| W&B not logging | Set `WANDB_API_KEY` in `.env` or disable with `--no-wandb` |
| Run crashes overnight | Use `nohup python scripts/full_kg_pipeline.py ... &` and check `logs/` |

---

*Created: 2026-03-16*
