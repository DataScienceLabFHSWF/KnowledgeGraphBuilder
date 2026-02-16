"""Optional Langsmith tracing integration for LangChain components.

This module exposes a small helper that returns LangChain callback
objects (LangsmithTracer) when LANGSMITH_TRACING env var is enabled.

Design goals:
- Non-breaking: if langsmith is not installed or env vars are missing,
  functions return None and callers should continue without tracing.
- Centralized so multiple factories can reuse the same tracer logic.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _env_enabled(name: str) -> bool:
    return str(os.environ.get(name, "false")).lower() in ("1", "true", "yes")


def get_langsmith_callbacks() -> list[Any] | None:
    """Return a list with a LangsmithTracer instance or None.

    Reads the following environment variables (already present in .env):
    - LANGSMITH_TRACING (bool-like)
    - LANGSMITH_API_KEY (optional; LangChain client will also read it)
    - LANGSMITH_PROJECT (optional project name)
    - LANGSMITH_ENDPOINT (optional)

    Callers should pass the returned list into LangChain models/chains via
    `callbacks=` or continue if None.
    """
    if not _env_enabled("LANGSMITH_TRACING"):
        return None

    try:
        # Import lazily so package is optional at runtime
        from langchain.callbacks.tracers import LangsmithTracer
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("LangsmithTracer not available: %s", e)
        return None

    project = os.environ.get("LANGSMITH_PROJECT")
    endpoint = os.environ.get("LANGSMITH_ENDPOINT")

    try:
        # LangsmithTracer is permissive and will read API key from env vars
        tracer = LangsmithTracer(project=project) if project else LangsmithTracer()
        # If an endpoint is provided, set it on the tracer client (best-effort)
        if endpoint:
            try:
                # tracer.client may or may not be present depending on version
                setattr(tracer, "_endpoint", endpoint)
            except Exception:
                pass
        logger.info("Langsmith tracing enabled (project=%s)", project)
        return [tracer]
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("Failed to create LangsmithTracer: %s", e)
        return None
