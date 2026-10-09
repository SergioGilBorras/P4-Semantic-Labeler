# P4-Semantic-Labeler

**Provider-neutral, domain-independent semantic labeling service.** Generate a single short title or mini-summary from a name plus optional context, with hard Unicode character limits. Use it as a Python library, HTTP service, CLI or local MCP server.

**Providers:** `codex` integrates with [P4-Codex-Bridge](https://github.com/SergioGilBorras/P4-Codex-Bridge) 1.x using its public Python API. The `mock` provider is a deterministic formatter for tests and demonstrations, not semantic AI. `disabled` is the default until a provider is selected. Authenticated real Codex inference requires an installed Codex CLI and is not called in CI.

## Quick start

Python 3.11+. Install the service and the optional Codex bridge in the same environment. For actual AI generation, authenticate the official Codex CLI:

```bash
python -m pip install 'git+https://github.com/SergioGilBorras/P4-Codex-Bridge.git'
codex login
export P4_LABELER_PROVIDER=codex
```

The Codex bridge uses that login, not an API key. Use `P4_LABELER_PROVIDER=mock` for tests and demonstrations without real model inference. On Windows, use `$env:NAME = 'value'` to set an environment variable.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
export P4_LABELER_PROVIDER=mock
pytest -q
p4-labeler label --name process_pending_orders --kind function \
  --file examples/orders.py --max-chars 45 --style formal --language es --json
```

In mock mode, the example label is `process pending orders`; the response explicitly warns that this is *not* AI-semantic output, despite carrying the requested `language` and `style` as metadata.

## API HTTP

```bash
export P4_LABELER_PROVIDER=mock
uvicorn p4_semantic_labeler.interfaces.api:app --host 127.0.0.1 --port 8000
```

OpenAPI documentation: `http://127.0.0.1:8000/docs` and `/openapi.json`.

```bash
curl -X POST http://127.0.0.1:8000/v1/labels \
  -H 'Content-Type: application/json' -d '{
  "subject": {"kind": "function", "name": "process_pending_orders"},
  "context": {"documentation": "Validates orders and prepares dispatch."},
  "output_type": "title", "max_chars": 45, "style": "formal", "language": "es"
}'
```

Mock response (illustrative, not a Codex response):

```json
{
  "label": "process pending orders",
  "char_count": 22,
  "language": "es",
  "style": "formal",
  "output_type": "title",
  "provider": "mock",
  "warnings": ["mock_provider: synthetic name formatting, not semantic AI"]
}
```

`POST /v1/labels/batch` accepts `{"items": [{...}, {...}]}` and returns ordered per-item results and errors. Invalid individual dictionary items do not prevent valid items from running. `POST /v1/labels/file` accepts multipart form fields (`file`, `name`, optionally `kind`, `output_type`, `max_chars`, `style`, `language`, `purpose`, `before`, `after`). `GET /health` returns the liveness status and configured provider, **not** AI-provider readiness.

## CLI

```bash
p4-labeler label --name cache_invalid --kind concept \
  --documentation 'A condition indicating cache invalidation' \
  --max-chars 35 --style technical --language en --json

printf 'Contextual notes' | p4-labeler label --name example --stdin --json

p4-labeler batch --input examples/batch.jsonl --format jsonl > labels-results.jsonl
# Or pipe a JSON array using --format json
```

CLI `--file` reads a local file explicitly chosen by the invoking user, subject to text/size limits. MCP file paths are **more restrictive**: only configured workspace roots can be used.

## Python library

```python
from p4_semantic_labeler import Labeler, LabelRequest, Subject, Context
from p4_semantic_labeler.config import Settings

labeler = Labeler(settings=Settings(provider="mock"))  # demo only
request = LabelRequest(
    subject=Subject(kind="function", name="process_pending_orders"),
    context=Context(documentation="Validate and prepare orders."),
    output_type="title", max_chars=45, style="formal", language="es",
)
result = labeler.generate(request)  # sync entry point, outside an event loop
# Inside async programs: result = await labeler.agenerate(request)
print(result.model_dump())
```

## MCP (Model Context Protocol)

Install the official Python SDK v1 extra and start a **local stdio** MCP server:

```bash
pip install -e '.[mcp]'
export P4_LABELER_PROVIDER=mock
export P4_LABELER_MCP_ROOTS="$PWD/examples"
p4-labeler-mcp
# Or: p4-labeler mcp
```

MCP tools: `generate_label`, `generate_summary`, `generate_labels_batch`, `summarize_file`. The latter rejects paths outside explicitly allowed roots, including symlinks pointing outside the roots. MCP stdout is reserved for protocol messages. Remote MCP/HTTP transport is out of scope for V0.1.

## Configuration

All settings are environment variables. Defaults are intended for local use.

| Variable | Default | Meaning |
|---|---:|---|
| `P4_LABELER_PROVIDER` | `disabled` | `disabled`, `mock`, or `codex` (requires optional P4-Codex-Bridge 1.1.0 or later; see [Codex setup](docs/codex.md)) |
| `P4_LABELER_CODEX_WORKSPACE` | managed temporary workspace | Existing absolute Codex working directory, if explicitly configured |
| `P4_LABELER_MIN_CHARS` | `1` | Min length requested |
| `P4_LABELER_MAX_CHARS` | `300` | Max length requested |
| `P4_LABELER_MAX_REQUEST_BYTES` | `1048576` | HTTP request body cap |
| `P4_LABELER_MAX_FILE_BYTES` | `524288` | Readable file cap |
| `P4_LABELER_MAX_SUBJECT_CHARS` | `256` | Subject name cap (also validated by schema) |
| `P4_LABELER_MAX_CONTEXT_CHARS` | `12000` | Selected context cap |
| `P4_LABELER_MAX_INPUT_CHARS` | `48000` | Raw text content cap |
| `P4_LABELER_MAX_PROMPT_TOKENS_ESTIMATE` | `5000` | Approximate context token guard; not actual LLM tokenizer |
| `P4_LABELER_MAX_BATCH_ITEMS` | `30` | Entries per batch |
| `P4_LABELER_BATCH_CONCURRENCY` | `4` | Parallel provider calls |
| `P4_LABELER_PROVIDER_TIMEOUT` | `20` | Seconds per provider call |
| `P4_LABELER_REDUCTION_ATTEMPTS` | `1` | Regeneration attempts if too long |
| `P4_LABELER_API_KEY` | *not set* | Optional Bearer token for HTTP `/v1` endpoints |
| `P4_LABELER_RATE_LIMIT_RPM` | `60` | Per-client-IP requests per minute, in-memory per process |
| `P4_LABELER_MCP_ROOTS` | *empty* | OS-path-separator-delimited allowed MCP roots; file tool disabled if empty |

## Length policy

1. Normalize output to Unicode **NFC** and collapse whitespace to one line.
2. Count **Python Unicode code points**, including punctuation, spaces and emoji code points (not UTF-8 bytes or grapheme clusters).
3. Ask the provider for a shorter response if over the limit.
4. As a last resort, trim without exceeding the limit, preferring word boundaries and avoiding common split emoji sequences; return warning `output_truncated: meaning may be incomplete`.
5. Empty or unusable provider output is **an error**, not a fake success. In extreme cases where no non-empty safe prefix fits, fail rather than emit a broken label.

The hard length guarantee is programmatic. Faithfulness, correct language and writing style still require a capable real provider and quality evaluation; truncation can reduce semantic fidelity.

## Security and privacy

- Inputs, source code and documentation are treated as **untrusted data**, never executed. Python AST extraction is parse-only. Embedded instructions are isolated from privileged prompt instructions, though prompt injection cannot be eliminated by prompting alone.
- Allowed UTF-8 text extensions: `.txt`, `.md`, `.rst`, `.py`, `.json`, `.jsonl`, `.yaml`, `.yml`, `.toml`, `.csv`. Binary and oversized files are rejected. Uploaded filenames are not used as local read paths.
- Body limits are enforced in ASGI even without a trustworthy `Content-Length`; API validation errors do not echo submitted code/docs. No source content or prompts are logged by the application by default.
- MCP filesystem roots are deny-by-default. Use a dedicated, least-privilege service account and read-only mounts for untrusted workspaces.
- Set `P4_LABELER_API_KEY` and terminate TLS at a trusted reverse proxy if exposing HTTP to other users. The included rate limit is **per process, not distributed**; use gateway rate limits and per-tenant quotas for internet deployment. Uvicorn examples bind to localhost, not all interfaces.
- When using Codex, selected context is sent to Codex via the bridge. Review privacy and retention policies and do not send confidential data without authorization. The bridge API accepts one prompt string, not distinct system/user roles; prompt injection remains possible.
- The bridge uses the official Codex CLI's existing authentication. Inherited external MCP tools **can cause side effects even under a read-only filesystem sandbox**. Codex mode explicitly acknowledges this documented bridge limitation; see [Codex provider](docs/codex.md).

See [Architecture](docs/architecture.md), [API contract](docs/api.md) and [Codex provider](docs/codex.md).

## Tests / CI

```bash
pip install -e '.[dev]'
pytest -q
ruff check .
```

CI runs pytest and Ruff on Python 3.11, 3.12 and 3.13. CI uses only mock and bridge contract test doubles, never actual Codex inference. Tests cover core constraints, Unicode, context, prompt boundaries, API, CLI, batching, errors, timeouts and MCP tool handlers. An SDK-level MCP registration test runs when the official MCP extra is installed; it is skipped otherwise.

## Roadmap

- **V1:** authenticated Codex smoke validation, improved token accounting and semantic quality tests.
- **V2:** additional AI providers, optional caching and batch observability.
- **V3:** optional IDE/document integrations and additional formats.

## License

MIT. See `LICENSE`.
