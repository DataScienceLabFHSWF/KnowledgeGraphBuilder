"""Pydantic schemas for structured extraction output.

These schemas define the JSON structure for:
- Entity extraction results
- Relation extraction results
- Structured findings
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityExtractionOutput(BaseModel):
    """Schema for entity extraction JSON output.

    Matches ExtractedEntity structure for seamless integration.
    """

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "entities": [
                    {
                        "id": "ent_001",
                        "label": "Kernkraftwerk Emsland",
                        "entity_type": "Facility",
                        "confidence": 0.95,
                        "start_char": 42,
                        "end_char": 68,
                        "context": "...",
                    }
                ]
            }
        },
    }

    entities: list[EntityItem] = Field(
        description="List of extracted entities from text"
    )


class EntityItem(BaseModel):
    """Individual extracted entity."""

    model_config = {"populate_by_name": True}

    id: str = Field(description="Unique entity identifier")
    label: str = Field(description="Entity text/label from source")
    entity_type: str = Field(
        alias="type",
        description="Entity type from ontology (e.g., Facility, Organization, Operation)",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score (0.0-1.0)"
    )
    start_char: int = Field(description="Start character position in source text")
    end_char: int = Field(description="End character position in source text")
    context: str = Field(
        description="Context window around entity (50 chars before/after)"
    )


class RelationExtractionOutput(BaseModel):
    """Schema for relation extraction JSON output."""

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "relations": [
                    {
                        "id": "rel_001",
                        "source_id": "ent_001",
                        "source_label": "Kernkraftwerk Emsland",
                        "relation_type": "requires",
                        "target_id": "ent_002",
                        "target_label": "Sicherheitsbericht",
                        "confidence": 0.88,
                    }
                ]
            }
        },
    }

    relations: list[RelationItem] = Field(
        alias="relationships",
        description="List of extracted relations between entities",
    )


class RelationItem(BaseModel):
    """Individual extracted relation."""

    model_config = {"populate_by_name": True}

    id: str = Field(description="Unique relation identifier")
    source_id: str = Field(description="ID of source entity")
    source_label: str = Field(description="Label of source entity")
    relation_type: str = Field(
        alias="type",
        description="Relation type from ontology (e.g., requires, involves, documents)",
    )
    target_id: str = Field(description="ID of target entity")
    target_label: str = Field(description="Label of target entity")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score (0.0-1.0)"
    )


class FindingsSynthesisOutput(BaseModel):
    """Schema for synthesized findings combining entities and relations."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "findings": [
                    {
                        "id": "find_001",
                        "finding_type": "Safety_Requirement",
                        "summary": "Kernkraftwerk Emsland requires Sicherheitsbericht",
                        "entities": ["ent_001", "ent_002"],
                        "confidence": 0.91,
                    }
                ]
            }
        },
    }

    findings: list[FindingItem] = Field(
        description="List of extracted findings/facts"
    )


class FindingItem(BaseModel):
    """Individual extracted finding."""

    id: str = Field(description="Unique finding identifier")
    finding_type: str = Field(
        description="Finding category (e.g., Safety_Requirement, Regulatory_Requirement, Operation)"
    )
    summary: str = Field(description="Natural language summary of finding")
    entities: list[str] = Field(description="IDs of entities involved in finding")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Overall confidence score (0.0-1.0)"
    )
