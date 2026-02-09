# ontology-hitl — Script Stubs

Entry-point scripts for each step in the iteration workflow.

---

## `scripts/run_gap_analysis.py`

```python
#!/usr/bin/env python3
"""Step 2: Analyze gaps between KGB extraction and current ontology.

Usage:
    python scripts/run_gap_analysis.py \
        --checkpoint ../KnowledgeGraphBuilder/output/extraction_checkpoint.json \
        --ontology data/seed_ontology/plan-ontology-v1.0.owl \
        --output data/iterations/v1/gap_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
import structlog

from ontology_hitl.core.config import Settings
from ontology_hitl.discovery.gap_analyzer import OntologyGapAnalyzer

logger = structlog.get_logger(__name__)
app = typer.Typer()


@app.command()
def main(
    checkpoint: Path = typer.Option(..., help="KGB extraction checkpoint JSON"),
    ontology: Path = typer.Option(None, help="Ontology file (OWL/TTL). Uses Fuseki if not set."),
    output: Path = typer.Option("data/iterations/v1/gap_report.json", help="Output gap report"),
    min_frequency: int = typer.Option(3, help="Min entity frequency to consider"),
) -> None:
    """Run gap analysis on KGB extraction results."""
    settings = Settings()
    
    analyzer = OntologyGapAnalyzer(
        fuseki_url=settings.fuseki_url,
        dataset=settings.fuseki_dataset,
        min_frequency=min_frequency,
    )
    
    report = analyzer.analyze(checkpoint_path=checkpoint)
    
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    logger.info(
        "gap_analysis_complete",
        total=report.total_extracted_entities,
        covered=report.covered_entities,
        gaps=len(report.gap_candidates),
        coverage_pct=f"{report.coverage_pct:.1%}",
    )


if __name__ == "__main__":
    app()
```

---

## `scripts/generate_proposals.py`

```python
#!/usr/bin/env python3
"""Step 3: Generate proposed ontology classes from gap report.

Usage:
    python scripts/generate_proposals.py \
        --gap-report data/iterations/v1/gap_report.json \
        --output data/iterations/v1/proposals.json
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
import structlog

from ontology_hitl.core.config import Settings
from ontology_hitl.discovery.class_generator import ClassDefinitionGenerator
from ontology_hitl.discovery.relation_generator import RelationProposalGenerator

logger = structlog.get_logger(__name__)
app = typer.Typer()


@app.command()
def main(
    gap_report: Path = typer.Option(..., help="Gap report JSON from step 2"),
    output: Path = typer.Option("data/iterations/v1/proposals.json", help="Output proposals"),
    max_proposals: int = typer.Option(30, help="Max number of proposals to generate"),
) -> None:
    """Generate class and relation proposals from gap analysis."""
    settings = Settings()
    
    with open(gap_report) as f:
        report = json.load(f)
    
    class_gen = ClassDefinitionGenerator(
        ollama_url=settings.ollama_url,
        model=settings.ollama_model,
        fuseki_url=settings.fuseki_url,
        dataset=settings.fuseki_dataset,
    )
    
    proposals = class_gen.generate_from_gaps(
        gap_candidates=report["gap_candidates"],
        max_proposals=max_proposals,
    )
    
    # Also generate relation proposals
    relation_gen = RelationProposalGenerator(
        ollama_url=settings.ollama_url,
        model=settings.ollama_model,
    )
    for proposal in proposals:
        proposal.suggested_relations = relation_gen.suggest_relations(
            proposed_class=proposal,
            existing_classes=report.get("existing_classes", []),
        )
    
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump([p.__dict__ for p in proposals], f, indent=2, default=str)
    
    logger.info("proposals_generated", count=len(proposals))


if __name__ == "__main__":
    app()
```

---

## `scripts/review_proposals.py`

```python
#!/usr/bin/env python3
"""Step 4: Interactive CLI review of proposed classes.

Usage:
    python scripts/review_proposals.py \
        --proposals data/iterations/v1/proposals.json \
        --output data/iterations/v1/decisions.json
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

logger = structlog.get_logger(__name__)
console = Console()
app = typer.Typer()


@app.command()
def main(
    proposals: Path = typer.Option(..., help="Proposals JSON from step 3"),
    output: Path = typer.Option("data/iterations/v1/decisions.json", help="Output decisions"),
    reviewer: str = typer.Option("expert", help="Reviewer name"),
) -> None:
    """Interactive review session for proposed ontology classes."""
    with open(proposals) as f:
        proposal_list = json.load(f)
    
    decisions = []
    total = len(proposal_list)
    
    console.print(f"\n[bold]Reviewing {total} proposals[/bold]\n")
    
    for i, proposal in enumerate(proposal_list, 1):
        console.print(Panel(
            f"[bold]{proposal['label']}[/bold]\n\n"
            f"Definition: {proposal['definition']}\n\n"
            f"Parent class: {proposal.get('parent_label', 'N/A')}\n"
            f"Examples: {', '.join(proposal.get('examples', [])[:5])}\n"
            f"Frequency: {proposal.get('frequency', 0)} occurrences\n"
            f"Confidence: {proposal.get('confidence', 0):.2f}",
            title=f"Proposal {i}/{total}",
        ))
        
        # Show suggested properties
        if proposal.get("suggested_properties"):
            table = Table(title="Suggested Properties")
            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Required")
            for prop in proposal["suggested_properties"]:
                table.add_row(prop["name"], prop["datatype"], str(prop.get("required", False)))
            console.print(table)
        
        # Show suggested relations
        if proposal.get("suggested_relations"):
            table = Table(title="Suggested Relations")
            table.add_column("Name")
            table.add_column("Domain")
            table.add_column("Range")
            for rel in proposal["suggested_relations"]:
                table.add_row(rel["name"], rel["domain"], rel["range"])
            console.print(table)
        
        decision = Prompt.ask(
            "Decision",
            choices=["accept", "reject", "revise", "skip"],
            default="skip",
        )
        
        rationale = ""
        if decision in ("reject", "revise"):
            rationale = Prompt.ask("Rationale")
        
        decisions.append({
            "proposal_id": proposal.get("id", f"prop_{i}"),
            "proposal_label": proposal["label"],
            "reviewer": reviewer,
            "decision": decision,
            "rationale": rationale,
        })
        
        console.print()
    
    # Summary
    accepted = sum(1 for d in decisions if d["decision"] == "accept")
    rejected = sum(1 for d in decisions if d["decision"] == "reject")
    console.print(f"\n[bold green]Accepted: {accepted}[/bold green]  "
                  f"[bold red]Rejected: {rejected}[/bold red]  "
                  f"Total: {total}\n")
    
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(decisions, f, indent=2)
    
    logger.info("review_complete", accepted=accepted, rejected=rejected)


if __name__ == "__main__":
    app()
```

---

## `scripts/export_ontology.py`

```python
#!/usr/bin/env python3
"""Step 5: Export accepted proposals as extended ontology + updated CQs.

Usage:
    python scripts/export_ontology.py \
        --decisions data/iterations/v1/decisions.json \
        --proposals data/iterations/v1/proposals.json \
        --seed data/seed_ontology/plan-ontology-v1.0.owl \
        --output-owl data/exports/ontology_v2.0.owl \
        --output-cq data/exports/cq_v2.0.json
"""
from __future__ import annotations

from pathlib import Path

import typer
import structlog

from ontology_hitl.schema.manager import OntologySchemaManager
from ontology_hitl.schema.shacl_generator import SHACLGenerator

logger = structlog.get_logger(__name__)
app = typer.Typer()


@app.command()
def main(
    decisions: Path = typer.Option(..., help="Review decisions JSON"),
    proposals: Path = typer.Option(..., help="Proposals JSON"),
    seed: Path = typer.Option("data/seed_ontology/plan-ontology-v1.0.owl", help="Seed ontology"),
    output_owl: Path = typer.Option("data/exports/ontology_latest.owl", help="Output OWL file"),
    output_cq: Path = typer.Option("data/exports/cq_latest.json", help="Output CQ JSON"),
) -> None:
    """Export accepted proposals as extended ontology."""
    manager = OntologySchemaManager(seed_ontology_path=seed)
    
    # Load accepted proposals
    accepted_classes = manager.apply_decisions(
        proposals_path=proposals,
        decisions_path=decisions,
    )
    
    # Generate SHACL shapes
    shacl_gen = SHACLGenerator()
    for cls in accepted_classes:
        shacl_gen.generate_shape(cls)
    
    # Export
    output_owl.parent.mkdir(parents=True, exist_ok=True)
    manager.export_owl(output_owl)
    manager.export_updated_cqs(output_cq)
    
    logger.info(
        "export_complete",
        classes_added=len(accepted_classes),
        owl_path=str(output_owl),
        cq_path=str(output_cq),
    )


if __name__ == "__main__":
    app()
```

---

## `scripts/evaluate_iteration.py`

```python
#!/usr/bin/env python3
"""Step 7: Evaluate improvement after re-running KGB with extended ontology.

Usage:
    python scripts/evaluate_iteration.py \
        --before output/kg_metrics_v1.json \
        --after ../KnowledgeGraphBuilder/output/kg_metrics.json \
        --output data/iterations/v1/evaluation_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
import structlog
from rich.console import Console
from rich.table import Table

from ontology_hitl.evaluation.reporter import IterationReporter

logger = structlog.get_logger(__name__)
console = Console()
app = typer.Typer()


@app.command()
def main(
    before: Path = typer.Option(..., help="KG metrics JSON before extension"),
    after: Path = typer.Option(..., help="KG metrics JSON after extension"),
    output: Path = typer.Option("data/iterations/v1/evaluation_report.json", help="Report output"),
) -> None:
    """Compare before/after metrics for an iteration."""
    reporter = IterationReporter()
    
    report = reporter.compare(before_path=before, after_path=after)
    
    # Display results
    table = Table(title="Iteration Evaluation")
    table.add_column("Metric", style="bold")
    table.add_column("Before", justify="right")
    table.add_column("After", justify="right")
    table.add_column("Change", justify="right")
    
    for metric in report["metrics"]:
        change = metric["after"] - metric["before"]
        color = "green" if change > 0 else "red" if change < 0 else "white"
        table.add_row(
            metric["name"],
            f"{metric['before']:.2%}",
            f"{metric['after']:.2%}",
            f"[{color}]{change:+.2%}[/{color}]",
        )
    
    console.print(table)
    
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info("evaluation_complete")


if __name__ == "__main__":
    app()
```
