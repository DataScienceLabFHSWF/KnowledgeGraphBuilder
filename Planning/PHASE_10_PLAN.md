# Phase 10: Experiment Framework & Comparative Analysis

**Status**: Planning (Ready to implement)  
**Effort**: 12-15 hours  
**Priority**: DO FOURTH (after Phase 9 metrics)  
**Purpose**: Enable reproducible experiments and comparative analysis for publication-quality results

---

## Overview

Phase 10 implements a comprehensive experiment framework for running and analyzing multiple KG construction configurations in parallel. Enables comparative science: how do different extraction parameters, ontologies, and settings affect KG quality?

### Core Goals

1. **Run multiple KG configurations** with different hyperparameters
2. **Collect metrics across all experiments** (accuracy, F1, coverage, etc.)
3. **Analyze convergence behavior** (how quality improves with more data)
4. **Generate comparison reports** (Markdown, JSON, HTML)
5. **Publication-ready visualizations** (plots, tables)

### Success Criteria

- ✅ Run 3+ different KG configurations with different parameters
- ✅ Collect and aggregate metrics from Phase 9 evaluator
- ✅ Generate comparative analysis reports
- ✅ Produce convergence plots and performance tables
- ✅ All test coverage ≥75%

---

## Architecture

### Module Structure

```
src/kgbuilder/experiment/
├── __init__.py                 # Public API
├── config.py                   # ExperimentConfig, ConfigVariant
├── manager.py                  # ExperimentManager (orchestrates runs)
├── runner.py                   # ConfigRunner (single config execution)
├── analyzer.py                 # ExperimentAnalyzer (metrics analysis)
├── plotter.py                  # ExperimentPlotter (visualizations)
└── reporter.py                 # ExperimentReporter (reports)
```

### Data Flow

```
ExperimentConfig (multiple variants)
    ↓
ExperimentManager.run_experiments()
    ↓ [parallel for each variant]
ConfigRunner.run() → Builds KG → Evaluates → Metrics
    ↓
ExperimentAnalyzer.analyze()
    ↓
[Convergence Analysis, Comparative Stats]
    ↓
ExperimentReporter.generate_report()
    ↓
[Markdown/JSON/HTML Report + Plots]
```

---

## Phase 10 Tasks

### Task 10.1: Experiment Configuration (2-3 hours)

**Goal**: Define experiment setup with multiple configuration variants

**Deliverables**:
- `ExperimentConfig` dataclass
  - Base parameters (output_dir, num_runs, parallel_jobs)
  - Eval dataset path and QA questions
  - Reporting format preferences
  
- `ConfigVariant` dataclass  
  - Variant name and description
  - KG builder parameters (model, max_iterations, thresholds)
  - Optional modifications to base config
  
- `ExperimentSpec` - complete experiment specification
  - Metadata (experiment_name, description, date)
  - List of ConfigVariant objects
  - Evaluation settings

**Files Created**: `src/kgbuilder/experiment/config.py`

**Code Size**: ~200 LOC

---

### Task 10.2: Experiment Manager & Runner (3-4 hours)

**Goal**: Execute multiple KG configurations and collect results

**Deliverables**:
- `ConfigRunner` class
  - `run(config_variant) → ExperimentRun`
  - Orchestrate: build KG → evaluate → collect metrics
  - Error handling and logging
  - Save intermediate results
  
- `ExperimentManager` class
  - `run_experiments(spec) → list[ExperimentRun]`
  - Parallel execution (configurable workers)
  - Progress tracking
  - Aggregate results into `ExperimentResults`
  
- `ExperimentRun` dataclass
  - Config variant info
  - Build metrics (time, nodes, edges)
  - Evaluation metrics from Phase 9
  - Status and errors

**Files Created**: `src/kgbuilder/experiment/manager.py`, `src/kgbuilder/experiment/runner.py`

**Code Size**: ~400 LOC

---

### Task 10.3: Metrics Analysis & Convergence (2-3 hours)

**Goal**: Analyze metrics across experiments and convergence patterns

**Deliverables**:
- `ExperimentAnalyzer` class
  - `analyze_convergence()` - track metrics over iterations
  - `compare_variants()` - comparative analysis
  - `aggregate_statistics()` - means, stddev, ranges
  
- `ConvergenceAnalysis` dataclass
  - Convergence curves (accuracy vs iteration)
  - Plateau detection
  - Rate of improvement
  
- `ComparativeAnalysis` dataclass
  - Best/worst performing variants
  - Statistical significance
  - Parameter sensitivity analysis
  
- Statistics computation
  - Mean, median, std deviation
  - Confidence intervals
  - Ranking and ordering

**Files Created**: `src/kgbuilder/experiment/analyzer.py`

**Code Size**: ~350 LOC

---

### Task 10.4: Visualization & Plotting (2-3 hours)

**Goal**: Create publication-ready plots and charts

**Deliverables**:
- `ExperimentPlotter` class (using matplotlib)
  - `plot_convergence()` - line plots of metrics vs iteration
  - `plot_comparison()` - bar charts comparing variants
  - `plot_heatmap()` - parameter sensitivity heatmaps
  - `plot_distribution()` - metric distributions
  
- Plot types:
  - Convergence curves (accuracy, F1, coverage)
  - Variant comparison (grouped bar charts)
  - Parameter sensitivity (heatmaps)
  - Distribution plots (violin plots)
  
- Export formats: PNG, PDF, SVG

**Files Created**: `src/kgbuilder/experiment/plotter.py`

**Code Size**: ~300 LOC

---

### Task 10.5: Report Generation (2-3 hours)

**Goal**: Generate comprehensive experiment reports

**Deliverables**:
- `ExperimentReport` dataclass
  - Title, date, description
  - Summary statistics
  - Detailed results per variant
  - Visualizations (embedded)
  
- `ExperimentReporter` class
  - `generate_markdown()` - Markdown report with embedded plots
  - `generate_json()` - JSON export for further analysis
  - `generate_html()` - Interactive HTML dashboard
  - `save_report()` - Save to file
  
- Report sections:
  - Executive summary (best/worst variants)
  - Detailed metrics tables
  - Convergence analysis
  - Comparative analysis
  - Visualizations with captions
  - Methodology and parameters
  
- HTML dashboard with:
  - Interactive tables (sortable, filterable)
  - Plotly charts (zoomable, hoverable)
  - Parameter sensitivity explorer

**Files Created**: `src/kgbuilder/experiment/reporter.py`

**Code Size**: ~400 LOC

---

### Task 10.6: Integration & Testing (2-3 hours)

**Goal**: Integrate into CLI and create comprehensive tests

**Deliverables**:
- Update `scripts/build_kg.py`
  - Add `--experiment-config` argument (YAML/JSON file path)
  - Add `--run-experiment` flag to run full experiment
  - Add `--experiment-variants` for quick multi-config runs
  
- Test suite: `tests/test_experiment.py`
  - `TestExperimentConfig` - configuration parsing (5 tests)
  - `TestConfigRunner` - single run execution (5 tests)
  - `TestExperimentManager` - orchestration (5 tests)
  - `TestExperimentAnalyzer` - analysis (8 tests)
  - `TestExperimentPlotter` - visualization (5 tests)
  - `TestExperimentReporter` - reporting (5 tests)
  - Integration tests (5 tests)
  
- Total: 38+ tests, ≥75% coverage

**Files Modified**: `scripts/build_kg.py`, `src/kgbuilder/experiment/__init__.py`

**Files Created**: `tests/test_experiment.py`, example config files

**Code Size**: ~700 LOC (including tests)

---

## Example Usage

### Configuration File (experiment.yaml)

```yaml
experiment:
  name: "KG Quality Baseline"
  description: "Compare different extraction configurations"
  output_dir: "./experiment_results/"
  num_runs: 1  # runs per variant
  parallel_jobs: 3

evaluation:
  qa_dataset: "data/qa_benchmark.json"
  metrics: ["accuracy", "f1_score", "coverage"]

variants:
  - name: "baseline"
    description: "Default parameters"
    params:
      model: "qwen3:8b"
      max_iterations: 2
      similarity_threshold: 0.85
      confidence_threshold: 0.6

  - name: "strict"
    description: "High confidence threshold"
    params:
      model: "qwen3:8b"
      max_iterations: 2
      similarity_threshold: 0.90
      confidence_threshold: 0.75

  - name: "permissive"
    description: "Low thresholds, more entities"
    params:
      model: "qwen3:8b"
      max_iterations: 2
      similarity_threshold: 0.70
      confidence_threshold: 0.50
```

### Python Usage

```python
from kgbuilder.experiment import ExperimentConfig, ExperimentManager

# Load experiment spec
config = ExperimentConfig.from_yaml("experiment.yaml")

# Run all variants
manager = ExperimentManager(config)
results = manager.run_experiments()

# Analyze results
analyzer = ExperimentAnalyzer(results)
convergence = analyzer.analyze_convergence()
comparison = analyzer.compare_variants()

# Generate reports
reporter = ExperimentReporter(results)
reporter.generate_markdown("report.md")
reporter.generate_html("report.html")
reporter.generate_json("results.json")

# Plot visualizations
plotter = ExperimentPlotter(results)
plotter.plot_convergence().savefig("convergence.png")
plotter.plot_comparison().savefig("comparison.png")
```

---

## Dependencies

**New dependencies**:
- `matplotlib` - Plotting (likely already installed)
- `PyYAML` - YAML config parsing (likely already installed)

**Existing dependencies used**:
- `structlog` - Logging
- `pydantic` - Validation
- Phase 9 evaluation module (QA evaluation)

---

## Testing Strategy

**Unit Tests**:
- Config parsing and validation (5 tests)
- Runner with mock KG builder (5 tests)
- Manager orchestration (5 tests)
- Analysis functions (8 tests)
- Plotter output validation (5 tests)
- Reporter output formats (5 tests)

**Integration Tests**:
- Full experiment run with 2 variants (2 tests)
- End-to-end report generation (2 tests)
- File I/O operations (1 test)

**Mocking Strategy**:
- Mock KG builder to avoid long runs
- Mock QA evaluator to use cached results
- Use temporary directories for output

**Target Coverage**: ≥75%

---

## Success Metrics

- ✅ All 38+ tests passing
- ✅ Can run 3 different KG configs in parallel
- ✅ Metrics aggregated correctly
- ✅ Convergence plots generated
- ✅ Comparison reports generated (all formats)
- ✅ Documentation complete
- ✅ Example configs provided

---

## Timeline

| Task | Duration | Notes |
|------|----------|-------|
| 10.1: Config | 2-3h | Dataclass definitions |
| 10.2: Manager/Runner | 3-4h | Orchestration logic |
| 10.3: Analysis | 2-3h | Statistics/convergence |
| 10.4: Plotting | 2-3h | Matplotlib visualizations |
| 10.5: Reports | 2-3h | Multi-format output |
| 10.6: Integration/Tests | 2-3h | CLI, 38+ tests |
| **Total** | **12-15h** | |

---

## Acceptance Criteria

Phase 10 is COMPLETE when:

1. ✅ All tasks 10.1-10.6 implemented
2. ✅ 38+ tests passing with ≥75% coverage
3. ✅ Can execute `python scripts/build_kg.py --run-experiment experiment.yaml`
4. ✅ Generates Markdown + HTML + JSON reports
5. ✅ Produces convergence and comparison plots
6. ✅ Full docstrings and type hints
7. ✅ Example experiment configs provided
8. ✅ Merged to main branch

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Long experiment runs | Use mock KG builder in tests, cache results |
| Plot generation issues | Test with simple plots first, handle missing data |
| Config parsing errors | Validate with pydantic, provide clear error messages |
| Memory usage (parallel) | Limit parallel jobs, stream results to disk |

---

## Next Steps (After Phase 10)

Phase 11: **Publication Pipeline**
- Format results for academic publication
- Statistical tests and significance
- Citation management
- Paper generation (LaTeX/Word)

Phase 12: **Web Dashboard**
- Real-time experiment monitoring
- Interactive result exploration
- KG visualization
- Configuration builder UI

---

## Implementation Notes

1. **ConfigRunner** should integrate seamlessly with `scripts/build_kg.py` build logic
2. **Parallel execution** using `asyncio.gather()` or `concurrent.futures`
3. **Caching** intermediate results to disk (checkpointing)
4. **Progress tracking** with structlog and tqdm
5. **Result persistence** - save all intermediate metrics
6. **Visualization** - embed plots in HTML reports
7. **Statistics** - use scipy for confidence intervals if available

---

**Last Updated**: Feb 3, 2026  
**Ready to implement**: YES ✓
