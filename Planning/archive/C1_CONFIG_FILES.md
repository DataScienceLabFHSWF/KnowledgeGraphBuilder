# ontology-hitl — Config & Boilerplate Files

---

## `.env.example`

```env
# Fuseki (shared with KGB or own instance)
HITL_FUSEKI_URL=http://localhost:3030
HITL_FUSEKI_DATASET=kgbuilder
HITL_FUSEKI_STAGING_DATASET=kgbuilder-staging
HITL_FUSEKI_USER=admin
HITL_FUSEKI_PASSWORD=

# LLM
HITL_OLLAMA_URL=http://localhost:18134
HITL_OLLAMA_MODEL=qwen3:8b
HITL_LLM_TEMPERATURE=0.5

# Gap Analysis
HITL_MIN_ENTITY_FREQUENCY=3
HITL_SEMANTIC_SIMILARITY_THRESHOLD=0.65

# Evaluation Targets
HITL_CQ_ANSWERABILITY_TARGET=0.80
HITL_ENTITY_COVERAGE_TARGET=0.80

# Paths
HITL_SEED_ONTOLOGY_PATH=data/seed_ontology/plan-ontology-v1.0.owl
HITL_ITERATIONS_DIR=data/iterations
HITL_EXPORTS_DIR=data/exports
```

---

## `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/

# Virtual environment
.venv/
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Environment
.env

# OS
.DS_Store
Thumbs.db

# Iteration data (large outputs)
data/iterations/*/extraction_checkpoint.json

# Logs
*.log
```

---

## `docker-compose.yml`

```yaml
# Only needed if NOT sharing Fuseki with KnowledgeGraphBuilder
version: "3.8"

services:
  fuseki-staging:
    image: secoresearch/fuseki:latest
    container_name: hitl-fuseki
    ports:
      - "3031:3030"    # Use 3031 to avoid conflict with KGB's Fuseki
    environment:
      - ADMIN_PASSWORD=${HITL_FUSEKI_PASSWORD:-admin}
    volumes:
      - fuseki_data:/fuseki
    restart: unless-stopped

volumes:
  fuseki_data:
```

---

## `Makefile`

```makefile
.PHONY: install dev lint test format check gap proposals review export evaluate cycle

# Setup
install:
	pip install -e .

dev:
	pip install -e ".[dev]"

# Code quality
lint:
	ruff check src/ tests/ scripts/
	mypy src/

format:
	ruff format src/ tests/ scripts/
	ruff check --fix src/ tests/ scripts/

test:
	pytest tests/ -v --tb=short

check: lint test

# Workflow steps
gap:
	python scripts/run_gap_analysis.py \
		--checkpoint $(CHECKPOINT) \
		--output data/iterations/$(V)/gap_report.json

proposals:
	python scripts/generate_proposals.py \
		--gap-report data/iterations/$(V)/gap_report.json \
		--output data/iterations/$(V)/proposals.json

review:
	python scripts/review_proposals.py \
		--proposals data/iterations/$(V)/proposals.json \
		--output data/iterations/$(V)/decisions.json

export:
	python scripts/export_ontology.py \
		--decisions data/iterations/$(V)/decisions.json \
		--proposals data/iterations/$(V)/proposals.json \
		--output-owl data/exports/ontology_$(V).owl \
		--output-cq data/exports/cq_$(V).json

evaluate:
	python scripts/evaluate_iteration.py \
		--before data/iterations/$(V)/metrics_before.json \
		--after data/iterations/$(V)/metrics_after.json \
		--output data/iterations/$(V)/evaluation_report.json

# Full cycle (set V=v1 and CHECKPOINT=path)
cycle: gap proposals review export
	@echo "Iteration $(V) complete. Now re-run KGB with exported ontology."
	@echo "  python scripts/full_kg_pipeline.py \\"
	@echo "    --ontology-path data/exports/ontology_$(V).owl \\"
	@echo "    --questions data/exports/cq_$(V).json"
```

---

## `README.md` (for ontology-hitl repo)

```markdown
# ontology-hitl

**Human-in-the-Loop Ontology Extension** for Knowledge Graph Construction.

Discovers ontology gaps from document extraction results, proposes new classes
via LLM, enables expert review, and exports extended ontologies compatible with
[KnowledgeGraphBuilder](https://github.com/yourorg/KnowledgeGraphBuilder).

## Quick Start

### Setup

    cp .env.example .env
    pip install -e ".[dev]"

### Run an Iteration Cycle

    # 1. After running KGB pipeline, take the checkpoint
    make gap V=v1 CHECKPOINT=../KnowledgeGraphBuilder/output/extraction_checkpoint.json

    # 2. Generate class proposals
    make proposals V=v1

    # 3. Expert review (interactive CLI)
    make review V=v1

    # 4. Export extended ontology + CQs
    make export V=v1

    # 5. Re-run KGB with extended ontology
    cd ../KnowledgeGraphBuilder
    python scripts/full_kg_pipeline.py \
      --ontology-path ../ontology-hitl/data/exports/ontology_v1.owl \
      --questions ../ontology-hitl/data/exports/cq_v1.json \
      --max-iterations 1

    # 6. Evaluate improvement
    make evaluate V=v1

## Interface with KnowledgeGraphBuilder

**Inputs** (from KGB):
- Extraction checkpoint JSON (entities, relations, confidence)
- KG metrics JSON

**Outputs** (to KGB):
- Extended ontology (OWL/TTL) → `--ontology-path`
- Updated competency questions (JSON) → `--questions`

## Architecture

    discovery/     → Gap analysis + LLM class generation
    schema/        → Ontology management + SHACL + versioning
    review/        → CLI/web expert review interface
    evaluation/    → CQ coverage + entity coverage metrics

## Success Criteria

| Metric              | Target |
|---------------------|--------|
| CQ Answerability    | 80%+   |
| Entity Coverage     | 80%+   |
| Expert Agreement    | 75%+   |
| Ontology Growth     | 20-30 new classes |

## License

MIT
```
