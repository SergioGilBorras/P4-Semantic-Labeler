# Codex provider

Set `P4_LABELER_PROVIDER=codex` and install [P4-Codex-Bridge](https://github.com/SergioGilBorras/P4-Codex-Bridge) version 1.x with a supported installed, authenticated official Codex CLI. The service imports the bridge lazily; the Python library and mock provider do not depend on it.

The adapter calls the bridge's stable `CodexBridge.run(prompt, *, cwd, profile, timeout_seconds, permissions, config_policy, capture_last_message, security_policy)` method. It sets `profile="analysis"`, `config_policy="isolated"`, `capture_last_message=True`, `SandboxMode.READ_ONLY` and `ApprovalPolicy.NEVER`. It passes a combined instruction and JSON reference-data prompt, because `run()` accepts one prompt string rather than separate system/user roles. It consumes the final `RunResult.content` and rejects unsuccessful/empty results.

By default it creates a temporary empty working directory and restricts the bridge's `allowed_roots` to that directory. Optionally set `P4_LABELER_CODEX_WORKSPACE` to an existing absolute directory; protect this directory and avoid introducing untrusted Codex configuration or `AGENTS.md` into it. Input source code is included as **prompt text**, never written to the working directory or executed by this service.

**External MCP risk:** P4-Codex-Bridge 1.0 cannot guarantee a per-run allow/deny list of inherited MCP tools. An external MCP can cause side effects even with a read-only filesystem sandbox. The adapter therefore passes `RunSecurityPolicy(project_trust=TRUSTED, allow_external_mcps=True, allow_side_effect_mcps=True, explicit_risk_acknowledgement=True)` when a user selects Codex. This explicitly acknowledges the risk; it does not provide MCP isolation or guarantee that external MCP tools are read-only. Operators must control which MCP servers their Codex installation exposes and should not enable untrusted remote consumers without access controls.

The bridge uses the Codex CLI's existing authentication. This project stores no Codex credentials. `P4_LABELER_PROVIDER_TIMEOUT` is forwarded to bridge calls; service-side async timeout cannot always terminate an already running thread immediately, although the bridge also enforces its own process timeout.

The integration is covered by mocked public-interface tests. Real inference requires Codex CLI login and availability; CI does not run live, paid inference. `GET /health` only confirms the labeler process is alive, not Codex availability.
