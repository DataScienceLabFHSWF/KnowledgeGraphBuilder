"""
Test script: Connect to Ollama Docker container and run qwen3:8b model from Python.

Requirements:
- ollama server running in Docker (default: http://localhost:11434)
- qwen3:8b model pulled and available in Ollama
- requests library installed

Usage:
  python scripts/test_ollama_qwen3.py
"""
import sys
import json
import requests

import os

# Allow override of Ollama base URL via environment variable, default to port 18134
OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://localhost:18134")
MODEL = "qwen3:8b"
PROMPT = "What is the capital of France?"

def main() -> None:
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "stream": False
    }
    try:
        print(f"Sending request to Ollama at {url} with model '{MODEL}'...")
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        print("Response from Ollama:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("\nModel output:")
        print(data.get("response", "<no response field>").strip())
    except Exception as e:
        print(f"Error communicating with Ollama: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()