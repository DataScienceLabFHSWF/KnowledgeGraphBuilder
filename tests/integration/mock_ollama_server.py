"""Small deterministic Ollama-compatible server for HTTP integration tests."""

from __future__ import annotations

import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

_TEXT = "Ada Lovelace works for Acme GmbH."


def _entity_id(label: str, entity_type: str) -> str:
    key = f"{label.lower().strip()}::{entity_type.lower().strip()}"
    return f"ent_{hashlib.sha256(key.encode()).hexdigest()[:12]}"


class MockOllamaHandler(BaseHTTPRequestHandler):
    """Serve just the Ollama endpoints exercised by extraction integration tests."""

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/api/tags":
            self.send_error(404)
            return
        self._send_json({"models": [{"name": "integration-stub"}]})

    def do_POST(self) -> None:
        if self.path != "/api/generate":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        prompt = request.get("prompt", "")
        if "RelationExtractionOutput" in prompt:
            output = {
                "relationships": [
                    {
                        "id": "rel_001",
                        "source_id": _entity_id("Ada Lovelace", "Person"),
                        "source_label": "Ada Lovelace",
                        "type": "works-for",
                        "target_id": _entity_id("Acme GmbH", "Organization"),
                        "target_label": "Acme GmbH",
                        "confidence": 0.99,
                    }
                ]
            }
        else:
            output = {
                "entities": [
                    {
                        "id": "ent_001",
                        "label": "Ada Lovelace",
                        "type": "Person",
                        "confidence": 0.99,
                        "start_char": 0,
                        "end_char": 12,
                        "context": _TEXT,
                        "attributes": [],
                    },
                    {
                        "id": "ent_002",
                        "label": "Acme GmbH",
                        "type": "Organization",
                        "confidence": 0.99,
                        "start_char": 25,
                        "end_char": 34,
                        "context": _TEXT,
                        "attributes": [
                            {"attribute_name": "Name", "value": "Acme GmbH"}
                        ],
                    },
                ]
            }
        self._send_json(
            {
                "response": json.dumps(output),
                "prompt_eval_count": len(prompt.split()),
                "eval_count": len(json.dumps(output).split()),
            }
        )

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 11434), MockOllamaHandler).serve_forever()
