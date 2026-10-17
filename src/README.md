# Source code

Python package: [`p4_semantic_labeler/`](p4_semantic_labeler/).

| Location | Responsibility |
|---|---|
| [`core/`](p4_semantic_labeler/core/) | Request models, context extraction, prompt assembly, orchestration and output validation |
| [`providers/`](p4_semantic_labeler/providers/) | Provider abstraction, deterministic mock, optional Codex adapter and diagnostics |
| [`interfaces/`](p4_semantic_labeler/interfaces/) | Python-facing CLI, FastAPI and local stdio MCP server |
| [`prompts/`](p4_semantic_labeler/prompts/README.md) | UTF-8 prompt templates distributed as package resources |
| [`config.py`](p4_semantic_labeler/config.py) | Runtime settings and environment variable defaults |
| [`temp_directories.py`](p4_semantic_labeler/temp_directories.py) | Managed per-request temporary workspaces |

Public library objects are exported by [`p4_semantic_labeler/__init__.py`](p4_semantic_labeler/__init__.py). See [Architecture](../docs/architecture.md) and [Tests](../tests/README.md) before changing provider contracts.

Do not introduce consumer-specific heuristics or run untrusted supplied source code.
