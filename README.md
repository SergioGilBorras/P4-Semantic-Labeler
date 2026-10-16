# P4-Semantic-Labeler

**Python library for domain-independent, context-aware semantic labels and concise summaries.** Generate one short title or summary from a subject and optional source code, text or documentation, with an enforced Unicode-character maximum. Integrate via the Python API, command-line tool, FastAPI HTTP API or local stdio MCP server.

**Author and maintainer:** [Sergio Gil-Borrás](AUTHORS.md). **License:** [MIT](LICENSE). **Python:** 3.11+.

## Capabilities

- Generates labels of type `title` or `summary` with configurable language, style and a hard `max_chars` limit.
- Accepts names, code, documentation and contextual text. Parses Python code to extract relevant facts without executing input.
- Supports individual and ordered batch requests, with isolated per-item errors.
- Offers Python (`Labeler`), CLI (`p4-labeler`), HTTP (`/v1/labels`) and local stdio MCP (`p4-labeler-mcp`) interfaces.
- Bounds input size and concurrency; keeps selected provider diagnostics sanitized and does not log source content by default.

## Providers

| Provider | Behavior | When to use |
|---|---|---|
| `codex` | Contextual generation through [P4-Codex-Bridge](https://github.com/SergioGilBorras/P4-Codex-Bridge) **1.4.1** and the official Codex CLI | Real AI-powered labeling, when configured and authorized |
| `mock` | Deterministically formats the supplied subject name; it does **not** perform semantic AI inference or translation | Automated tests and integration examples |
| `disabled` | Rejects generation requests with a provider-unavailable error | Safe default until a provider is selected |

P4 supplies context selection, length validation and interfaces; the model provider generates the semantic content. Output language, style and meaning depend on the real provider and are not automatically guaranteed. A short label may satisfy the technical length check without being semantically acceptable.

## Installation

This repository is private; install from a checkout that has access to Git-hosted dependencies. Required [portable-tempdirs](https://github.com/SergioGilBorras/portable-tempdirs) is pinned to a fixed Git commit. The optional Codex extra pins P4-Codex-Bridge to a fixed Git commit. The two packages use the **same portable-tempdirs commit**.

```bash
python -m pip install -e .
python -m pip check
```

For real Codex integration, install the optional extra, install/authenticate the official Codex CLI, and select the provider:

```bash
python -m pip install -e '.[codex]'
codex login
```

On Windows PowerShell, use `python -m pip install -e ".[codex]"` and `$env:P4_LABELER_PROVIDER = "codex"`. An editable checkout is intended for development, **not** a packaged customer distribution. See [Installation and distribution](docs/distribution.md) for an installable wheel, source pinning and release gates.

## Python API

```python
from p4_semantic_labeler import Context, Labeler, LabelRequest, Subject
from p4_semantic_labeler.config import Settings

labeler = Labeler(settings=Settings(provider="mock"))  # no AI inference
request = LabelRequest(
    subject=Subject(kind="function", name="process_pending_orders"),
    context=Context(documentation="Validate and prepare orders for dispatch."),
    output_type="title",
    min_chars=20,  # advisory
    max_chars=45,  # enforced
    style="formal",
    language="es",
)
result = labeler.generate(request)
print(result.model_dump())
```

Inside a running event loop, use `await labeler.agenerate(request)`. The mock result formats the name (`process pending orders`), regardless of the requested language; use `codex` for AI-generated semantics.

## CLI

```bash
p4-labeler label --name process_pending_orders --kind function --file examples/orders.py --max-chars 45 --json
p4-labeler batch --input examples/batch.jsonl --format jsonl
```

Configure `P4_LABELER_PROVIDER=mock` for examples that must not invoke Codex. CLI `--file` requires an explicitly selected local UTF-8 text file.

## HTTP interface

```bash
uvicorn p4_semantic_labeler.interfaces.api:app --host 127.0.0.1 --port 8000
```

The application exposes `POST /v1/labels`, `POST /v1/labels/batch`, `POST /v1/labels/file`, `GET /health`, and interactive docs at `/docs`. The canonical schema is `/openapi.json`. The `/health` route confirms process liveness, **not** provider readiness. Generation endpoints support an optional configured Bearer token; never expose an unauthenticated development server to the internet.

See [HTTP API contract](docs/api.md).

## MCP (local stdio)

```bash
python -m pip install -e '.[mcp]'
p4-labeler-mcp
```

The server uses the official **MCP Python SDK 2.x** and offers tools `generate_label`, `generate_summary`, `generate_labels_batch` and `summarize_file`. File access is disabled unless `P4_LABELER_MCP_ROOTS` lists explicitly allowed roots; symlinks resolving outside these roots are denied. The server communicates over **local stdio**, not a remotely hosted MCP endpoint.

## Configuration and length policy

All runtime settings are set via environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `P4_LABELER_PROVIDER` | `disabled` | `disabled`, `mock`, `codex` |
| `P4_LABELER_CODEX_WORKSPACE` | managed temporary workspace | Optional existing absolute Codex workspace |
| `P4_LABELER_MIN_CHARS` | `1` | Lower service guard for requested `max_chars` |
| `P4_LABELER_MAX_CHARS` | `300` | Service upper guard for requested `max_chars` |
| `P4_LABELER_MAX_REQUEST_BYTES` | `1048576` | HTTP request body cap |
| `P4_LABELER_MAX_FILE_BYTES` | `524288` | Readable file limit |
| `P4_LABELER_MAX_SUBJECT_CHARS` | `256` | Subject-name length limit |
| `P4_LABELER_MAX_CONTEXT_CHARS` | `12000` | Selected context limit |
| `P4_LABELER_MAX_INPUT_CHARS` | `48000` | Raw subject/context limit |
| `P4_LABELER_MAX_PROMPT_TOKENS_ESTIMATE` | `5000` | Heuristic token guard, not actual tokenizer |
| `P4_LABELER_MAX_BATCH_ITEMS` | `30` | Maximum requests per batch |
| `P4_LABELER_BATCH_CONCURRENCY` | `4` | Parallel provider calls |
| `P4_LABELER_PROVIDER_TIMEOUT` | `20` | Provider call timeout in seconds |
| `P4_LABELER_REDUCTION_ATTEMPTS` | `1` | Additional rewrites when output exceeds hard max |
| `P4_LABELER_API_KEY` | unset | Optional Bearer token for `/v1` |
| `P4_LABELER_RATE_LIMIT_RPM` | `60` | Per-process, per-IP request limit |
| `P4_LABELER_MCP_ROOTS` | empty | OS-path-separator-delimited allowed filesystem roots |

For individual requests, `min_chars` is **advisory**: a valid shorter response returns the warning `below_preferred_min_chars`, not padding or failure. `max_chars` is **mandatory**. Responses are NFC-normalized, whitespace-collapsed and measured in Python Unicode code points. Overlong provider output may be rewritten using a bounded extra provider call, then truncated with a semantic-loss warning if necessary. The service rejects empty or otherwise unusable output.

## Security, tests and quality

Untrusted input code is parsed, not executed. A Codex provider receives selected input as prompt data; inherited external MCP tools may have side effects, and a read-only filesystem sandbox does not isolate those tools. Operators must configure Codex and MCP permissions and follow applicable data-handling requirements. HTTP protection requires TLS termination and gateway-level quotas for external deployment. See [Security policy](SECURITY.md), [Architecture](docs/architecture.md) and [Codex integration](docs/codex.md).

```bash
python -m pip install -e '.[dev,codex]'
python -m pip check
ruff check .
pytest -q
```

CI tests Python 3.11, 3.12 and 3.13 on Windows and Ubuntu **without paid/live inference**. The mock provider is not evidence of AI semantic correctness. The current quality-evaluation methodology, recorded evidence and limitations are described in [Quality and evaluation](docs/evaluation.md).

## Roadmap and project policies

See [Roadmap](ROADMAP.md), [Contributing](CONTRIBUTING.md), [Authors](AUTHORS.md), [Security policy](SECURITY.md) and [Distribution](docs/distribution.md).
