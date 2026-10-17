# Roadmap

P4-Semantic-Labeler is a provider-neutral labeling library exposing Python, CLI, HTTP and local MCP interfaces. This roadmap tracks **proposed work**, not released functionality or a delivery commitment.

## Packaging and distribution

- Build and verify signed-off Python wheels against an immutable release commit.
- Establish a documented customer distribution channel for the publicly hosted source and its Git-hosted dependencies; document offline installation where required.
- Publish a versioned GitHub Release with tested artifacts, SHA-256 checksums and resolved dependency manifests.
- Run clean-environment installation tests for supported Python versions and both operating systems.

## Quality and automation

- Keep static OpenAPI documentation automatically checked against runtime schema.
- Validate current provider compatibility using offline contract tests in CI.
- Strengthen independent, blinded semantic-fidelity evaluation with frozen rubrics and explicit acceptance decisions.
- Maintain documentation, packaging smoke tests and the supported-version matrix.

## Repository governance and security

- Require successful CI and reviewed PRs through branch protection/rulesets.
- Establish a verified confidential vulnerability-reporting path for customers.
- Review optional provider permissions, dependency updates and licensing obligations before external distribution.

Features not listed above are not implied; customer commitments require a separately approved release plan.
