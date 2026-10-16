# Security Policy

Report vulnerabilities privately to the repository maintainers, preferably through GitHub private vulnerability reporting when enabled. Do not disclose confidential source code, credentials or exploitable details in public issues. Before onboarding external customers, repository maintainers should confirm that an accessible private reporting channel is configured and communicated to those customers.

The service limits input sizes and file formats, parses code without executing it, and treats all supplied text as untrusted prompt data. Submitted code or documents are not logged in full by default. MCP file reads require explicitly allowed roots. Prompt injection remains a risk even when untrusted reference data is separated logically from instructions.

In Codex mode, selected reference context is sent through P4-Codex-Bridge and the official Codex CLI. The adapter uses read-only filesystem permissions, but **the bridge does not guarantee per-run isolation of inherited external MCP tools**. These tools may cause side effects. When the Codex provider is selected, the adapter explicitly acknowledges this documented risk; operators must review their Codex MCP configuration and control untrusted clients.

For public HTTP deployment, configure TLS, authentication, gateway rate limiting and least-privilege service accounts. The built-in per-IP limiter is local to each process, and the health endpoint is only a liveness check. Follow applicable data storage and provider retention policies.
