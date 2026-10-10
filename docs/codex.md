# Codex provider

Set `P4_LABELER_PROVIDER=codex` and install the optional integration using the labeler's pip extra from this repository checkout:

```bash
python -m pip install -e '.[codex]'
python -m pip check
```

This extra pins P4-Codex-Bridge **1.2.0** to immutable commit `082705a0fb797d80d1010c6ead9b5dd2b3e69da4`, and the main dependencies pin portable-tempdirs **0.1.2** to `fd6dbd640630e6911a53b4d756089099ec870a8b`. The Bridge pins that *same* portable-tempdirs commit, avoiding mismatched source requirements. Both pins track the reviewed current `main` commits; Bridge and the direct dependency use the same portable-tempdirs revision. These packages must be installed into the **same interpreter** used by Semantic-Labeler. CI checks their installed metadata and public APIs without invoking Codex CLI.

The bridge remains an optional runtime integration: it is imported only for Codex requests, and the Python library and mock provider do not require it. The adapter requires Bridge 1.2.0 or later because it explicitly supplies `ephemeral=True`.

`cwd` is the working directory in which the Codex CLI process runs; it does not specify the bridge's state storage. **Every provider request creates a new `CodexBridge` instance and invokes a fresh, one-shot `CodexBridge.run()` execution.** No bridge instance, thread or managed filesystem workspace is reused for a later label request, including retries and concurrent batch items.

For each request, the adapter uses `portable-tempdirs` as a context manager to create a unique temporary run directory containing separate `workspace` and `bridge-state` children. The managed workspace starts empty; the adapter passes `skip_git_repo_check=True`, which only bypasses the CLI Git-repository check and does not create a repository or relax sandbox permissions. The state directory is not added to `allowed_roots`. **After the synchronous bridge call has finished (success or failure), the adapter attempts identity-checked cleanup of the entire run tree.** It does not call `detach()`; that feature is available for other consumers that deliberately need persistent directories. The namespace container under the system temporary root may remain. If cleanup fails because of permissions or file sharing, a sanitized failure is reported and some files may remain; there is no unsafe deletion fallback.

If `P4_LABELER_CODEX_WORKSPACE` names an existing external directory, each request still gets a fresh `CodexBridge` and a new temporary `bridge-state`, but the *external directory is reused by explicit configuration*. The adapter never deletes or clears that directory, uses `skip_git_repo_check=False`, and cannot guarantee that external files, repository instructions or `AGENTS.md` will not affect later requests. For maximum filesystem-context separation, leave this setting unset.

The adapter sets `profile="analysis"`, `config_policy="isolated"`, `capture_last_message=True`, `SandboxMode.READ_ONLY`, `ApprovalPolicy.NEVER` and `ephemeral=True`. It passes a combined instruction and JSON reference-data prompt, because `run()` accepts one prompt string rather than separate system/user roles. It consumes the final `RunResult.content` and rejects unsuccessful/empty results. A missing `skip_git_repo_check` capability or a bridge version older than 1.2.0 produces a safe capability diagnostic before a provider call.

In either mode, `allowed_roots` contains only the selected workspace; bridge state is never included. Protect an external workspace and avoid untrusted Codex configuration or `AGENTS.md` there. Input source code is included as **prompt text**, never written to the working directory or executed by this service.

**External MCP risk:** inherited MCP tools are not isolated by the temporary workspace, `skip_git_repo_check`, or the filesystem sandbox. An external MCP can cause side effects even with read-only filesystem permissions. The adapter therefore passes `RunSecurityPolicy(project_trust=TRUSTED, allow_external_mcps=True, allow_side_effect_mcps=True, explicit_risk_acknowledgement=True)` when a user selects Codex. This acknowledges the risk; it does not provide MCP isolation or guarantee that external MCP tools are read-only. Operators must control which MCP servers their Codex installation exposes.

The bridge uses the Codex CLI's existing authentication. This project stores no Codex credentials. `P4_LABELER_PROVIDER_TIMEOUT` is forwarded to bridge calls; service-side async timeout cannot always terminate an already running thread immediately, although the bridge also enforces its own process timeout.

The integration is covered by mocked public-interface tests. Real inference requires Codex CLI login and availability; CI does not run live, paid inference. `GET /health` only confirms the labeler process is alive, not Codex availability.
