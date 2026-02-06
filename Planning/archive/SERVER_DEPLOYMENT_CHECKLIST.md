# Server Deployment Checklist

## Phase 3A: Extraction Pipeline - Ready for Deployment

**Last Updated**: February 2, 2026

---

## Pre-Deployment Verification

### ✅ Code Implementation
- [x] `src/kgbuilder/embedding/ollama.py` – OllamaProvider (QWEN3 support)
- [x] `src/kgbuilder/extraction/entity.py` – LLMEntityExtractor with ontology guidance
- [x] `src/kgbuilder/extraction/schemas.py` – Pydantic schemas for structured output
- [x] `src/kgbuilder/extraction/__init__.py` – Module exports
- [x] `src/kgbuilder/embedding/__init__.py` – Module exports

### ✅ Deployment Files
- [x] `requirements.txt` – All Python dependencies pinned
- [x] `Dockerfile` – Multi-stage build optimized for production
- [x] `docker-compose.yml` – Full service orchestration
- [x] `.env.example` – Environment variable template

### ✅ Test Scripts
- [x] `scripts/test_extraction.py` – Full extraction pipeline test
- [x] `scripts/test_imports.py` – Quick import verification
- [x] `scripts/download_ontology.py` – Ontology management

### ✅ Documentation
- [x] `README.md` – Updated with quick start
- [x] `data/README.md` – Data directory guide
- [x] `local-docs/PHASE_3A_EXTRACTION_COMPLETE.md` – Implementation summary

---

## Server Deployment Steps

### Step 1: Environment Setup
```bash
# Clone repository (if not already done)
git clone <repo> KnowledgeGraphBuilder
cd KnowledgeGraphBuilder

# Copy environment template
cp .env.example .env

# Edit .env with server-specific values
vim .env
```

### Step 2: Install Dependencies
```bash
# Option A: Docker (Recommended)
docker build -t kgbuilder:latest .

# Option B: Virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
```

### Step 3: Start Services
```bash
# Start Ollama (on server or external machine)
ollama serve &

# Pull QWEN3 model (one-time)
ollama pull qwen3

# Start database services
docker-compose up -d neo4j qdrant

# (Optional) Start Fuseki for RDF/SPARQL
docker-compose up -d fuseki
```

### Step 4: Verify Installation
```bash
# Test imports
python scripts/test_imports.py

# Test connection to Ollama
python scripts/test_extraction.py
```

### Step 5: Run Extraction Pipeline
```bash
# Test on 3 sample documents
python scripts/test_extraction.py

# Process full 33-document set (production run)
# (Script to be created in Phase 3B)
```

---

## Runtime Configuration

### Ollama Setup
```bash
# Model: QWEN3 or qwen3-next
# Memory: ~8GB per model
# Concurrency: Supports multiple requests

# Check available models
curl http://localhost:11434/api/tags

# Model performance (rough)
# - QWEN3 (8B): Fast, good for entity extraction
# - QWEN3-Next (32B): More accurate, slower
```

### Neo4j Setup
```bash
# Default credentials (from .env)
# User: neo4j
# Password: (set in .env)
# Port: 7687 (Bolt)
# HTTP: 7474

# Access web interface
# http://localhost:7474
```

### Qdrant Setup
```bash
# Vector database for semantic search
# Port: 6333
# REST API: http://localhost:6333/docs
```

---

## Performance Expectations

| Component | Time | Notes |
|-----------|------|-------|
| Model load (QWEN3) | ~5s | One-time per session |
| Entity extraction/chunk | 5-15s | Depends on chunk size (512 tokens) |
| Full document (20 chunks) | 2-5 min | Parallel processing possible |
| 33 documents (full set) | ~2-4 hours | With sequential processing |

**Optimization**:
- Parallel processing: Process multiple documents concurrently
- Batch extraction: Group small documents
- Model quantization: Use lower-precision for faster inference

---

## Troubleshooting

### Ollama Connection Issues
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Expected output:
# {"models":[{"name":"qwen3:latest",...}]}

# If connection fails:
# 1. Start Ollama: ollama serve
# 2. Check firewall rules
# 3. Verify OLLAMA_BASE_URL in .env
```

### Memory Issues
```bash
# Monitor model memory
ollama ps

# If out of memory:
# 1. Use smaller model (qwen3 vs qwen3-next)
# 2. Increase system swap
# 3. Reduce batch size
```

### Docker Issues
```bash
# Check container logs
docker-compose logs kgbuilder

# Rebuild if needed
docker-compose down
docker build --no-cache -t kgbuilder:latest .
docker-compose up -d
```

---

## Security Considerations

- [x] No API keys in .env (template only)
- [x] Database passwords in environment variables
- [x] Local-only Ollama (no exposure to internet)
- [x] Docker network isolation (kgbuilder-net)
- [x] Volume mounting (read-only where possible)

---

## Monitoring & Logging

### Enable Structured Logging
```python
import structlog
logger = structlog.get_logger(__name__)
logger.info("extraction_started", doc_id="doc_001", chunk_count=20)
```

### Log Destinations
- Console: Standard Python logging
- Files: (Configured in production)
- Metrics: (Phase 4+)

---

## Scaling Considerations

### For 33 Documents
- Current: Sequential processing (~4 hours)
- Next: Parallel workers (reduce to ~30-60 min)
- Future: Distributed processing (multi-machine)

### Document Size Handling
- Small (<5KB): Direct processing
- Medium (5-50KB): Chunk and process
- Large (>50KB): Multi-pass extraction

---

## Next Phase (Phase 3B)

1. **RelationExtractor** – Extract relationships
2. **Storage Backends** – Neo4j and Qdrant implementations
3. **KG Assembly** – Build unified knowledge graph
4. **Validation** – SHACL and ontology validation
5. **Production Script** – Full pipeline automation

---

## Contact & Support

- **Issues**: Check `Planning/ISSUES_BACKLOG.md`
- **Implementation Guide**: See `local-docs/IMPLEMENTATION_GUIDE.md`
- **Architecture**: See `Planning/ARCHITECTURE.md`

---

**Status**: 🟢 Ready for Deployment

Next command to run on server:
```bash
python scripts/test_extraction.py
```
