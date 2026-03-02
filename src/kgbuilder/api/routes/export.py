"""KG export endpoints.

Exports the knowledge graph in various standard formats.
Wraps ``kgbuilder.storage.export.KGExporter``.
"""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from kgbuilder.api.schemas import ExportFormat, ExportRequest, ExportResponse

logger = structlog.get_logger(__name__)
router = APIRouter()

_MEDIA_TYPES = {
    ExportFormat.JSON: "application/json",
    ExportFormat.JSON_LD: "application/ld+json",
    ExportFormat.TURTLE: "text/turtle",
    ExportFormat.CYPHER: "text/plain",
    ExportFormat.GRAPHML: "application/xml",
}


@router.post("/export", response_model=ExportResponse)
async def export_kg_to_file(request: ExportRequest) -> ExportResponse:
    """Export the KG to a file on disk."""
    from kgbuilder.api.dependencies import get_neo4j_store
    from kgbuilder.storage.export import ExportConfig, KGExporter

    try:
        store = get_neo4j_store()
        exporter = KGExporter(
            graph_store=store,
            config=ExportConfig(include_metadata=request.include_metadata),
        )

        output_path = request.output_path or f"output/kg_export.{request.format.value}"
        exporter.export_to_file(output_path, format=request.format.value)

        stats = store.get_statistics()

        return ExportResponse(
            format=request.format.value,
            output_path=output_path,
            node_count=stats.node_count if hasattr(stats, "node_count") else 0,
            edge_count=stats.edge_count if hasattr(stats, "edge_count") else 0,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}") from e


@router.get("/export/{fmt}")
async def export_kg_download(fmt: ExportFormat) -> Response:
    """Export the KG and return it directly as a download."""
    from kgbuilder.api.dependencies import get_neo4j_store
    from kgbuilder.storage.export import ExportConfig, KGExporter

    try:
        store = get_neo4j_store()
        exporter = KGExporter(
            graph_store=store,
            config=ExportConfig(include_metadata=True),
        )

        format_map = {
            ExportFormat.JSON: "json",
            ExportFormat.JSON_LD: "jsonld",
            ExportFormat.TURTLE: "turtle",
            ExportFormat.CYPHER: "cypher",
            ExportFormat.GRAPHML: "graphml",
        }
        method_name = f"to_{format_map[fmt]}"
        content = getattr(exporter, method_name)()

        return Response(
            content=content,
            media_type=_MEDIA_TYPES[fmt],
            headers={
                "Content-Disposition": f'attachment; filename="kg_export.{fmt.value}"',
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}") from e
