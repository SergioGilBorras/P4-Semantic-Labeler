# P4-Semantic-Labeler

**Provider-neutral, domain-independent semantic labeling service.** Generate a single short title or mini-summary from a name plus optional context, with hard Unicode character limits. Use it as a Python library, HTTP service, CLI or local MCP server.

**Providers:** `codex` integrates with [P4-Codex-Bridge](https://github.com/SergioGilBorras/P4-Codex-Bridge) 1.x using its public Python API. The `mock` provider is a deterministic formatter for tests and demonstrations, not semantic AI. `disabled` is the default until a provider is selected. Authenticated real Codex inference requires an installed Codex CLI and is not called in CI.

## Install as a Python dependency

The validated source release is [v0.1.0](https://github.com/SergioGilBorras/P4-Semantic-Labeler/releases/tag/v0.1.0) (commit `0179888`). The GitHub repository is **private** and the package is **not advertised as published on PyPI**. Git and read access to this repository and its Git-hosted dependencies are required for direct installation.

From the **consumer's Python environment**, with access configured for private GitHub repositories:

```bash
python -m pip install "p4-semantic-labeler @ git+https://github.com/SergioGilBorras/P4-Semantic-Labeler.git@v0.1.0"
# For opt-in Codex integration:
python -m pip install "p4-semantic-labeler[codex] @ git+https://github.com/SergioGilBorras/P4-Semantic-Labeler.git@v0.1.0"
python -m pip check
```

Import `Labeler`, `LabelRequest`, `Subject` and `Context` from `p4_semantic_labeler`. By default the provider is `disabled`; `mock` is for tests, while `codex` additionally requires the Codex CLI installed and authenticated. Installing a wheel alone does **not** bundle the Git-hosted dependencies. See [Installation and distribution](docs/distribution.md) for wheel building, verification and client-delivery requirements.

## Quick start

Python 3.11+. To install the service **together with** the reviewed Codex Bridge 1.2.0 and portable-tempdirs 0.1.2 using pip from this checkout:

```bash
python -m pip install -e '.[codex]'
python -m pip check
codex login
export P4_LABELER_PROVIDER=codex
```

For offline/mocked development checks with the Codex integration installed, use `python -m pip install -e '.[dev,codex]'`. The two upstream packages are pinned to immutable Git commits and are **not** assumed to be published on PyPI. The bridge is optional for `mock` or `disabled` use. On Windows PowerShell, quote the extra as `".[dev,codex]"` and set provider variables using `$env:NAME = 'value'`.

The Codex bridge uses that login, not an API key. The independent
`portable-tempdirs` dependency creates an **isolated run directory per Codex
request** with separate `workspace` and `bridge-state` children. Each call
constructs a new bridge and performs a fresh one-shot invocation, then attempts
cleanup of that request's run directory. The adapter never uses `detach()` or
deletes historical run directories. If `P4_LABELER_CODEX_WORKSPACE` explicitly
points to an external directory, that external workspace is preserved and may
contain files or instructions from earlier work; only the per-request bridge
state is temporary. See [Codex setup](docs/codex.md). Use `P4_LABELER_PROVIDER=mock` for tests and demonstrations without real model inference. On Windows, use `$env:NAME = 'value'` to set an environment variable.

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
  "output_type": "title", "min_chars": 20, "max_chars": 45, "style": "formal", "language": "es"
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

The optional request field `min_chars` (default `1`) is **only a preferred
minimum**. A good shorter label succeeds, with informational warning
`below_preferred_min_chars`; it never triggers a retry, failure or artificial
padding. `max_chars` remains a **hard maximum**, with the existing
budget-controlled overlength rewrite and last-resort truncation warning.
Prompts favor **what the subject does**, without needless "not X" contrasts,
while retaining essential prohibitions and conditions.

`POST /v1/labels/batch` accepts `{"items": [{...}, {...}]}` and returns ordered per-item results and errors. Invalid individual dictionary items do not prevent valid items from running. `POST /v1/labels/file` accepts multipart form fields (`file`, `name`, optionally `kind`, `output_type`, `min_chars`, `max_chars`, `style`, `language`, `purpose`, `before`, `after`). `GET /health` returns the liveness status and configured provider, **not** AI-provider readiness.

## CLI

```bash
p4-labeler label --name cache_invalid --kind concept \
  --documentation 'A condition indicating cache invalidation' \
  --min-chars 15 --max-chars 35 --style technical --language en --json

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
    output_type="title", min_chars=20, max_chars=45, style="formal", language="es",
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

MCP tools: `generate_label`, `generate_summary`, `generate_labels_batch`, `summarize_file`. The latter rejects paths outside explicitly allowed roots, including symlinks pointing outside the roots. MCP stdout is reserved for protocol messages. Only local stdio MCP is included; HTTP via FastAPI is a separate supported interface. No remotely hosted MCP transport is supplied.

## Configuration

All settings are environment variables. Defaults are intended for local use.

| Variable | Default | Meaning |
|---|---:|---|
| `P4_LABELER_PROVIDER` | `disabled` | `disabled`, `mock`, or `codex` (requires optional P4-Codex-Bridge 1.2.0 or later; see [Codex setup](docs/codex.md)) |
| `P4_LABELER_CODEX_WORKSPACE` | managed temporary workspace | Existing absolute Codex working directory, if explicitly configured |
| `P4_LABELER_MIN_CHARS` | `1` | Minimum **allowed value for request `max_chars`** (configuration guard, not the optional per-request preferred output minimum) |
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

The per-request `min_chars` (default `1`) is **advisory** and must not
exceed `max_chars`; a shorter meaningful output is returned unchanged,
with `below_preferred_min_chars` in `warnings`. Such output is not a
technical failure and does not consume an additional provider call.

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

CI runs pytest and Ruff on Windows and Ubuntu with Python 3.11, 3.12 and 3.13. CI uses only mock and bridge contract test doubles, never actual Codex inference. Tests cover core constraints, Unicode, context, prompt boundaries, API, CLI, batching, errors, timeouts and MCP tool handlers. An SDK-level MCP registration test runs when the official MCP extra is installed; it is skipped otherwise.

## V1 status

The original **60-case** evaluation corpus has been exercised according to its purpose: 58 real Codex labeling cases and two negative validation cases. The evaluation history and known semantic limitations are recorded; this is **not** a claim that all labels passed independent semantic review or that production reliability has been established.

See the [V1 evaluation and scope-closure report](docs/v1-evaluacion-y-cierre.md). **V1** refers to the functional milestone, not to a SemVer `1.0.0` release: `pyproject.toml` still declares package version `0.1.0`.

**Published release:** [v0.1.0](https://github.com/SergioGilBorras/P4-Semantic-Labeler/releases/tag/v0.1.0) targets commit `0179888` and passed all six CI jobs (Windows and Ubuntu, Python 3.11–3.13). The later package metadata commit `820ad5b` is **not** part of the immutable `v0.1.0` tag. The release does not yet attach a wheel; any client artifact containing subsequent changes needs a distinct version, a clean build and verification. See [Distribution](docs/distribution.md).

No V2/V3 development phases are planned as part of this V1 closure.

## License

MIT. See `LICENSE`.
