# Experiments

## Overview

The experiment framework supports systematic, reproducible evaluation
of different pipeline configurations.

## Running Experiments

```bash
# Single experiment with W&B logging
python scripts/run_single_experiment.py

# From config file
python scripts/run_experiment.py --config examples/experiment_baseline.json

# Custom experiment config
python scripts/run_experiment.py --config examples/test_single_experiment.json
```

## Experiment Configuration

```json
{
  "experiment_name": "baseline_evaluation",
  "variants": [
    {
      "name": "default",
      "max_iterations": 3,
      "confidence_threshold": 0.5,
      "top_k_docs": 10
    }
  ]
}
```

## Features

- **Multi-variant runs** -- compare different configurations
- **Automatic checkpointing** -- resume interrupted experiments
- **W&B integration** -- metrics logged to Weights & Biases
- **SHACL quality scoring** -- every run gets a quality report
- **HTML reports** -- convergence analysis and variant comparison
- **Checkpoint re-enrichment** -- re-run enrichment without re-extracting

## Output Structure

```
experiment_output/
  exp_<timestamp>_<hash>/
    checkpoint.json          # Extraction results
    shacl_report.json        # Quality scores
    experiment_report.html   # Visual report
    wandb/                   # W&B artifacts
```

## Ablation Studies

See [ABLATION_STUDY_GUIDE.md](https://github.com/DataScienceLabFHSWF/KnowledgeGraphBuilder/blob/main/examples/ABLATION_STUDY_GUIDE.md)
for setting up systematic ablation studies comparing:

- Ontology variants (with/without specific classes)
- Extraction models (Qwen3 vs Llama3.1)
- Chunking strategies
- Confidence thresholds
