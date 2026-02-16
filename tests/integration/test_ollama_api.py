"""
Test Ollama API endpoints for the ollama-kg-builder container (GPU, port 18134).

This script checks:
- /api/tags (list models)
- /api/generate (basic prompt)
- /api/embeddings (embedding test)

Usage:
  python scripts/test_ollama_api.py
"""
import os
import sys

import requests

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:18134")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")


def test_tags():
    url = f"{OLLAMA_BASE_URL}/api/tags"
    print(f"Testing /api/tags at {url} ...")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print("Available models:", [m['name'] for m in data.get('models', [])])
    except Exception as e:
        print(f"/api/tags failed: {e}")
        return False
    return True


def test_generate():
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {"model": MODEL, "prompt": "What is the capital of France?", "stream": False}
    print(f"Testing /api/generate at {url} with model '{MODEL}' ...")
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        print("Model response:", data.get("response", "<no response field>"))
    except Exception as e:
        print(f"/api/generate failed: {e}")
        return False
    return True


def test_embeddings():
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {"model": MODEL, "prompt": "Paris"}
    print(f"Testing /api/embeddings at {url} with model '{MODEL}' ...")
    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print("Embedding vector length:", len(data.get("embedding", [])))
    except Exception as e:
        print(f"/api/embeddings failed: {e}")
        return False
    return True


def main():
    print(f"Ollama base URL: {OLLAMA_BASE_URL}")
    print(f"Model: {MODEL}")
    print()
    ok = test_tags()
    print()
    ok2 = test_generate()
    print()
    ok3 = test_embeddings()
    print()
    if all([ok, ok2, ok3]):
        print("All Ollama API tests passed.")
    else:
        print("Some Ollama API tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
