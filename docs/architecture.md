# Architecture / ADR-0001 — Stateless semantic transformation

## Scope and design

The service implements one-shot transformations, not an agent. The application core has no knowledge of business domains or particular AI SDKs. Dependency direction:

```text
HTTP FastAPI  ─┐
CLI argparse  ─┼─> Labeler (shared orchestration)
MCP FastMCP  ─┤     ├─ ContextBuilder (budget + Python AST, no exec)
Python lib   ─┘     ├─ PromptBuilder (trusted system / untrusted data JSON)
                     ├─ LabelProvider protocol -> mock / CodexBridgeProvider / future adapters
                     └─ Output validator (NFC, length, retry, safe truncation)
```

Public models are Pydantic v2 models in `core/models.py`. Provider contracts are the typed `ProviderPrompt`, `ProviderResponse` and async `LabelProvider` protocol. The transport interface does not know which model a bridge will use. Synchronous `Labeler.generate()` wraps `agenerate()` with `asyncio.run`; call the async version inside an existing loop.

## Context selection

1. Collect subject kind, name, module, class name, signature plus optional purpose, original title, document type, documentation, text, code and before/after context.
2. Verify raw subject/context length before processing (`max_input_chars`, default 48,000 chars). Subject fields also have their own Pydantic maxima.
3. For Python function/method/class snippets, use `ast.parse()` to choose the first matching node. Extract declaration, docstring, up to 20 called function names and the source segment. If parsing fails, retain the supplied source text. No import, exec, eval, or subprocess on received code.
4. Include available fields in this priority order: purpose (450), title (300), document type (150), documentation (3,500), text (3,500), source (6,000), preceding (1,000) and subsequent text (1,000). Field budgets are in characters; overall selected context defaults to 12,000 characters.
5. If a field is clipped/omitted, return a warning. Use a conservative configurable *heuristic* token estimate of roughly three characters per token for context fields. It is not an actual tokenizer and does not cover provider-specific serialization overhead. Accurate provider token accounting is not implemented in this release and is not claimed as part of the completed V1 scope.
6. Serialize selected data as JSON. The provider-neutral contract has separate instruction and reference-data fields; the Codex bridge accepts one prompt, so its adapter combines them into a single string. No system-role isolation is asserted. The service never executes received source. Prompt injection remains a risk.

## Generation and validation

`Labeler.agenerate` validates the configured request character range, builds context, constructs the provider-neutral prompt, enforces a per-call timeout, checks the response type and non-emptiness, normalizes to NFC and one line, checks `len(label)` and requests shorter output when needed. As a last resort a safe prefix is used, with a warning of possible semantic loss. All successes have `char_count == len(label) <= max_chars`; provider failures do not become successful placeholder labels.

Provider-neutral errors map to 413 (limits), 422 (request constraints), 502 (provider failures), 503 (provider unavailable) and 504 (timeout). FastAPI input schema failures map to 422. Per-item generation or validation errors do not poison a well-formed batch. HTTP body-size limit is independent of provider and allows at most 1 MiB by default; uploads have a separate 512 KiB cap.

## Operational security

The API is stateless except for a local IP-based rolling-window limiter. It stores no input texts. A production deployment should use gateway auth, rate limit and TLS; the built-in Bearer check is suitable as an additional simple protection for one service. Authentication on `/v1` is optional for localhost demos, not an endorsement of publicly unauthenticated deployments. `/health` is liveness; never treat it as proof of downstream Codex availability.

MCP stdio accesses disk only if `P4_LABELER_MCP_ROOTS` contains allowed directories. The service resolves paths and symlinks before checking containment and rejects non-regular files and disallowed formats. For high-adversary or multi-user deployments isolate filesystem mounts at OS/container boundary as well; a path-check/read race cannot be ruled out without stronger OS-level enforcement.

## Extension points

- Add `providers/my_provider.py` implementing async `generate(ProviderPrompt) -> ProviderResponse`.
- Register the implementation in `providers/factory.py` without changing `Labeler`, HTTP routes, CLI commands or MCP tool names.
- Add provider contract tests plus optional gated integration tests.
- Replace/extend `ContextBuilder` extraction strategies and prompt templates behind interfaces without introducing consumer-specific dictionaries or heuristics.

## Known limitations

- `mock` formats names deterministically; it neither uses context to reason nor translates output. It is intentionally identifiable.
- The Codex adapter requires optional P4-Codex-Bridge 1.2.0 or later because it passes `ephemeral=True` explicitly. Each label request constructs a new bridge with unique disposable workspace and state, uses a one-shot call, and attempts cleanup afterward. It skips the CLI Git check only for managed workspaces. Explicitly configured external workspaces are never deleted and may retain user-controlled filesystem context. An authenticated, end-to-end Codex invocation is not run in CI. Inherited external MCP tools and Codex CLI authentication/configuration are not isolated per run.
- Style, language and fidelity are model-level goals, **not mechanically provable**; automated tests currently validate correct propagation, constraints and failure paths, not semantic correctness.
- Token guard is approximate; provider-specific model token limits still require integration.
- Rate limit is per process; multi-instance deployments require a shared quota service or API gateway.
- MCP SDK registration is tested separately when the optional MCP package is present.
