# Codex provider

P4-Semantic-Labeler integrates with the official Codex CLI through the Python package [P4-Codex-Bridge](https://github.com/SergioGilBorras/P4-Codex-Bridge). This integration is **optional** and activates only when `P4_LABELER_PROVIDER=codex`.

## Install and configure

Use the Python interpreter that runs P4; Git must be installed to resolve the exact GitHub-source dependencies.

```bash
python -m pip install -e '.[codex]'
python -m pip check
codex login
```

On Windows PowerShell: `$env:P4_LABELER_PROVIDER = "codex"`. The Bridge uses the official CLI's existing login; P4 does not store Codex credentials or require a separate API key for this integration.

Current source pins used in `pyproject.toml`:

| Package | Installed version | Verified source commit |
|---|---|---|
| [P4-Codex-Bridge](https://github.com/SergioGilBorras/P4-Codex-Bridge) | **1.4.1** | `a7e21c83670df925c478696c078d1cdc46fa3a9b` |
| [portable-tempdirs](https://github.com/SergioGilBorras/portable-tempdirs) | **0.1.2** | `aad3878ccd8347a1a23faf609b2db21265d30a1d` |

Bridge and P4 require the **same portable-tempdirs Git commit**. These are immutable source dependencies, not floating `main` references. External model availability is controlled by the installed Codex CLI and account.

## Execution isolation

Each labeling request constructs a new `CodexBridge` and invokes its public `run()` API for a one-shot request; provider instances are not reused across labels. Each request gets a unique managed temporary tree with independent `workspace` and `bridge-state` directories. P4 attempts identity-checked cleanup on exit and reports sanitized errors if cleanup fails; it does not delete external user directories.

If `P4_LABELER_CODEX_WORKSPACE` is explicitly set, that existing directory is used as the working directory and **is not deleted**. Its contents and repository instructions may influence future requests. Leave the setting unset when an isolated temporary workspace is preferable.

The adapter sets a read-only filesystem sandbox, no interactive approval, isolated configuration, output capture and the Bridge's default ephemeral mode. The managed empty workspace bypasses only the CLI Git-repository check (`skip_git_repo_check=True`); this is not a sandbox escape and does not change MCP access.

## Security and limitations

Codex receives the selected source/document context as untrusted prompt text. The Bridge accepts one combined prompt string, so it does not provide independently enforced system/user role isolation. **Inherited external MCP tools may still cause side effects, even in read-only filesystem mode.** P4 explicitly acknowledges that risk in the Bridge security policy; operators remain responsible for controlling the Codex CLI configuration and any inherited MCP servers.

Provider calls are subject to `P4_LABELER_PROVIDER_TIMEOUT`. Timeout of P4's asynchronous wrapper may not immediately terminate a worker thread, although the Bridge enforces an execution timeout. `GET /health` checks process liveness, not CLI/model readiness. P4's CI uses the installed Bridge's public API and test doubles; it never consumes real inference.

See [Architecture](architecture.md), [Security policy](../SECURITY.md), [Distribution](distribution.md).
