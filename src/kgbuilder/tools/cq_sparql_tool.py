"""CQ->SPARQL functional-test tool: translate a competency question and run it.

See `kgbuilder.evaluation.cq_sparql` module docstring for source attribution
(CQ4OE, MASEO) and `Planning/SEMANTICS2026_IMPROVEMENT_PLAN.md` Phase B.
"""

from __future__ import annotations

from typing import Any

from kgbuilder.tools.base import AgentTool


def _cq_sparql_handler(
    translator: Any,
    runner: Any,
    question: Any,
    store: Any,
) -> Any:
    """Translate a VCQ/SCQ/RCQ question into SPARQL and execute it against the RDF store."""
    return runner.translate_and_run(question, store, translator)


CQSparqlTool = AgentTool(
    name="cq_sparql_test",
    description=(
        "Translate a competency question into a SPARQL ASK/SELECT query and execute it "
        "against the RDF store as a functional test of whether the KG answers it."
    ),
    parameters={
        "type": "object",
        "properties": {
            "question": {"type": "object"},
        },
        "required": ["question", "store"],
    },
    handler=_cq_sparql_handler,
)
