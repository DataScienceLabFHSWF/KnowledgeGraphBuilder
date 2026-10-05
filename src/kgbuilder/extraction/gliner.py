"""Optional GLiNER-based open-label entity recognition."""

from __future__ import annotations

from typing import Any

import structlog

from kgbuilder.core.models import Evidence, ExtractedEntity, generate_entity_id
from kgbuilder.extraction.entity import OntologyClassDef

logger = structlog.get_logger(__name__)


class GLiNEREntityExtractor:
    """Recognize ontology-labeled entity spans without generative LLM calls.

    Install the optional `gliner` dependency to use the default model loader.
    A pre-loaded model can be injected for tests or shared across extractors.
    """

    def __init__(
        self,
        model_name: str = "urchade/gliner_multi-v2.1",
        threshold: float = 0.5,
        model: Any | None = None,
    ) -> None:
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between zero and one")
        self.model_name = model_name
        self.threshold = threshold
        self._model = model

    def extract(
        self,
        text: str,
        ontology_classes: list[OntologyClassDef],
        existing_entities: list[ExtractedEntity] | None = None,
    ) -> list[ExtractedEntity]:
        """Return detected entity spans mapped to the supplied ontology classes."""
        if not text.strip() or not ontology_classes:
            return []
        model = self._get_model()
        class_by_label = {item.label.casefold(): item for item in ontology_classes}
        predictions = model.predict_entities(
            text,
            [item.label for item in ontology_classes],
            threshold=self.threshold,
        )
        entities: list[ExtractedEntity] = []
        seen: set[tuple[str, str, int]] = set()
        for prediction in predictions:
            label = str(prediction.get("label", ""))
            ontology_class = class_by_label.get(label.casefold())
            entity_text = str(prediction.get("text", "")).strip()
            start = prediction.get("start")
            end = prediction.get("end")
            score = prediction.get("score", 0.0)
            if (
                ontology_class is None
                or not entity_text
                or not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end > len(text)
                or start >= end
                or not isinstance(score, (int, float))
                or not self.threshold <= score <= 1
            ):
                logger.warning("gliner_invalid_prediction", prediction=prediction)
                continue
            key = (entity_text.casefold(), ontology_class.label, start)
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                ExtractedEntity(
                    id=generate_entity_id(entity_text, ontology_class.uri),
                    label=entity_text,
                    entity_type=ontology_class.label,
                    description=ontology_class.description or "",
                    confidence=float(score),
                    evidence=[
                        Evidence(
                            source_type="gliner",
                            source_id=f"char_{start}_{end}",
                            text_span=text[start:end],
                            confidence=float(score),
                        )
                    ],
                )
            )
        return entities

    def _get_model(self) -> Any:
        """Load GLiNER on first use, keeping it optional for LLM-only installs."""
        if self._model is None:
            try:
                from gliner import GLiNER  # type: ignore[import-untyped]
            except ImportError as exc:
                raise RuntimeError(
                    "GLiNER support requires the optional dependency: "
                    "pip install 'kgbuilder[gliner]'"
                ) from exc
            self._model = GLiNER.from_pretrained(self.model_name)
        return self._model
