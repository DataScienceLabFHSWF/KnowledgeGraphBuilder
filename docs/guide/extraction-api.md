# Extraction API

The extraction API accepts a document and its ontology, starts module-scoped
entity/relation extraction in the background, and exposes run status/results.
The API uses the request's `runId`; run state is held in memory and is lost if
the service restarts. Use one API process unless job storage is moved to a
shared backend.

Set `KGBUILDER_API_KEY` on the API service. `POST /api/extract` is unauthenticated
to match the integration contract. The status and results endpoints require
`Authorization: Bearer <KGBUILDER_API_KEY>`.

Supported document inputs are UTF-8 `text/*`, PDF, DOCX, PPTX, and XML files.
Non-text files must have a matching supported filename extension. The supplied
ontology needs at least one class; its modules, class attributes, examples,
relations, and relation domain/range are passed into extraction where relevant.

## Start a run

```http
POST /api/extract
Content-Type: application/json
```

Send the contract's JSON object, including `runId`, `documentId`, `ontologyId`,
`file` (with base64 content), and `ontology`. The response is:

```json
{
  "runId": "run_01HZX6Y6E2VQ2P9K3W8A6J4M9T"
}
```

Reusing an active or completed `runId` returns `409 Conflict`. Invalid base64
or unsupported file formats are rejected before a run is created.

## Check status

```http
GET /api/extract/{runId}/status
Authorization: Bearer <KGBUILDER_API_KEY>
```

The response contains `runId`, `status` (`running`, `completed`, or `failed`),
and integer `progress` from 0 to 100.

## Fetch results

```http
GET /api/extract/{runId}/results
Authorization: Bearer <KGBUILDER_API_KEY>
```

Completed runs return `sections`, `entities`, and `facts` in the integration
contract's response shape. Results requested while extraction is running return
`409 Conflict`; failed runs return `500` with an error detail. Plain-text files
are represented as one section with paragraphs split on blank lines. Page
evidence is reported as page 1 for plain text. If the loader cannot provide
reliable page attribution, the unknown page fields are omitted from JSON.

KG Workbench's current external response schema requires a `className` string
on every entity (including entities not referenced by a fact), and string
attribute values. KGBuilder supplies the class name from the input ontology and
serializes non-string property values as strings. For document formats without
reliable page numbers, `pageFrom` and `pageTo` are omitted rather than returned
as `null`; this matches Workbench's optional integer fields.

For a live adapter-to-container integration test, start the API and Workbench
on a shared Docker network, configure `EXTRACTION_API_URL` to the KGBuilder
service name and port, and set the same `KGBUILDER_API_KEY` in KGBuilder and
Workbench's external extractor API-key field. Run:

```bash
KGBUILDER_EXTRACTION_BASE_URL=http://localhost:8001 \
KGBUILDER_API_KEY=<integration-key> \
.venv/bin/pytest -m integration tests/integration/test_workbench_extraction_api.py
```

The test submits a small ontology/document payload, polls every three seconds
(matching Workbench's polling cadence and remaining below the API rate limit),
and checks the response fields KG Workbench imports. The
URL must be reachable from the test process. The cloned KG Workbench's
`extraction-adapter.ts` was also exercised from a Node 22 container on the
shared Docker network. That end-to-end call used the deterministic test
Ollama-compatible server in `tests/integration/mock_ollama_server.py`, so it
verified container routing and the request/status/results contract without
depending on inference speed or claiming extraction quality.

## Colleague handoff: KG Workbench beside KGBuilder

Build the API from this branch; older deployed images do not contain these
routes. Start one API process (run storage is not shared across workers).
For this repository's Compose stack:

```bash
cp .env.example .env
# Set KGBUILDER_API_KEY and the desired model/profile in .env.
docker compose up -d --build
docker network connect kg-workbench_default kgb-api
```

Use the actual Workbench network name if its Compose project name differs.
Do not repeat `docker network connect` if the API is already attached.
In Workbench, select the **external** extractor and configure:

```dotenv
EXTRACTION_API_URL=http://kgb-api:8001
```

Set its external extractor API-key field to the same secret as
`KGBUILDER_API_KEY`. Never commit either key. The base URL has no `/api/extract`
suffix: Workbench appends that path itself. Do not use `localhost` between
containers. Check `http://kgb-api:8001/api/v1/health` from the Workbench network
before submitting a run. Poll no faster than every three seconds, and allow
long model-backed requests enough time to complete.

The adapter integration was subsequently repeated on 2026-10-05 against
real Kolibri-1 inference on vLLM: Workbench revision `4d61c37`'s actual adapter
submitted, polled, and fetched a completed extraction across the shared Docker
network (1/1 Node test passed, approximately three seconds). The current source
was mounted into the integration API image. Earlier checks used a deterministic
model stub. This real-model test validates a small employment fixture, not
large-document quality, concurrency, or durability. A production handoff should
also submit a representative document to its configured provider.
POST is currently unauthenticated; keep the API on a trusted network or place
an authenticated reverse proxy in front of it. Jobs are memory-only and are
lost on restart; this is not yet a durable multi-worker extraction service.

## Supabase/PostgreSQL and vector retrieval

The current request supplies the document bytes and ontology. `/api/extract`
does **not** search any vector index, so the colleague can call it without
sharing Supabase credentials or changing their database. Supabase object/file
storage and PostgreSQL application tables are not automatically a vector index.
At the inspected Workbench revision `4d61c37`, storage supports Supabase, but
no embedding columns or vector-search RPC appeared in the app schema.

The separate `/api/v1/build` path retrieves from **Qdrant**, configured through
`QDRANT_URL` and `QDRANT_COLLECTION` (Compose uses `kgb-qdrant:6333`).
There is no Supabase/pgvector retriever implemented today; setting a PostgreSQL
URL cannot switch that path. The current extraction request has no vector-index
field, and the same `documentId` is an identifier, not an instruction to fetch
its text from a database.

For a future retrieval-backed contract, agree on these details before adding
an adapter:

- A read-only database connection or Supabase RPC endpoint configured
  **server-side**, not arbitrary URLs/credentials accepted per request.
- Vector table/schema or RPC name; chunk ID, text, document ID, page/section
  provenance columns; and a document/workspace filter.
- Embedding model **and revision**, dimension, normalization, and distance
  metric. Query embeddings must match indexed embeddings; selecting a chat
  provider does not change the existing embedding space.
- Tenant/workspace authorization and read-only access rules, top-k bounds,
  timeouts, and explicit error handling.

Keep the uploaded-file mode backward compatible. A retrieval source should
eventually be a server-configured name with scoped document/workspace IDs,
not a client-supplied connection string. Until that adapter exists, Workbench
can retrieve its own relevant text and submit it as a UTF-8 file through the
existing contract, acknowledging that synthesized text loses original PDF
page mapping unless the contract is extended with provenance.
