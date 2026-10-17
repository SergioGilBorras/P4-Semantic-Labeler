# Documentation

These documents describe the **current** P4-Semantic-Labeler source and the intended distribution workflow.

| Document | Purpose |
|---|---|
| [HTTP API](api.md) | Routes, request/response shapes, errors and file-upload limits |
| [Architecture](architecture.md) | Component boundaries, context handling and security limitations |
| [Codex provider](codex.md) | Optional Bridge integration, immutable source pins and permissions |
| [Packaging and distribution](distribution.md) | Build a wheel and source archive, verify them and distribute safely |
| [Evaluation](evaluation.md) | Test methodology, recorded evidence and quality limits |
| [OpenAPI snapshot](openapi.json) | Versioned snapshot; the running `/openapi.json` endpoint is canonical |

Start with the [project README](../README.md) for a quick introduction, [ROADMAP.md](../ROADMAP.md) for proposed work, and [SECURITY.md](../SECURITY.md) for deployment precautions.

Documentation is checked during CI for local links, Markdown fences, and core API/metadata consistency. The snapshot is not a substitute for querying a deployed API.
