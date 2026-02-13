# ontology-hitl — pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ontology-hitl"
version = "0.1.0"
description = "Human-in-the-Loop Ontology Extension for Knowledge Graph Construction"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "Your Name", email = "you@example.com" },
]
keywords = ["ontology", "knowledge-graph", "hitl", "shacl", "owl"]

dependencies = [
    # RDF / Ontology
    "rdflib>=7.0",
    "pyshacl>=0.25",
    "owlready2>=0.46",

    # Data models & config
    "pydantic>=2.0",
    "pydantic-settings>=2.0",

    # LLM access
    "httpx>=0.27",

    # CLI
    "typer>=0.12",
    "rich>=13.0",

    # Logging
    "structlog>=24.0",

    # Utilities
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
web = [
    "streamlit>=1.30",
]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.10",
    "pre-commit>=3.7",
]
all = ["ontology-hitl[web,dev]"]

[project.scripts]
hitl-review = "ontology_hitl.review.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/ontology_hitl"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "TCH"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```
