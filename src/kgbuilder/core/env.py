from __future__ import annotations
import os

def get_base_url(url: str | None = None) -> str:
    if url is None or url == "http://localhost:11434":
        return os.environ.get("OLLAMA_URL", "http://localhost:18134")
    return url
