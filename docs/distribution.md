# Installation, packaging and customer distribution

This document describes **P4-Semantic-Labeler v0.1.0** as currently published. It does not claim that a standalone commercial client-delivery bundle or a PyPI distribution exists.

## Source of truth and versioning

- Repository: [P4-Semantic-Labeler](https://github.com/SergioGilBorras/P4-Semantic-Labeler) (currently private).
- [Release v0.1.0](https://github.com/SergioGilBorras/P4-Semantic-Labeler/releases/tag/v0.1.0) points to commit `0179888727f96796e7c0a44a5b6631f15a1b3a51` and passed CI on Windows and Ubuntu, Python 3.11–3.13.
- Changes in `main` after that commit (including updated description and author metadata) are **not part of v0.1.0**. Do not label a wheel built from later `main` as an unmodified `v0.1.0` release. For a different artifact, bump the version consistently, run tests and publish a distinct tag/release.
- The published GitHub Release currently contains source archives, but **no attached `.whl` file**.

## Install in a consuming application

Prerequisites: Python 3.11+, `pip`, Git, and access to the private source repositories required by this package. Use the target application's virtual environment and do not embed GitHub access tokens in source files, dependency declarations or command history.

```bash
python -m pip install "p4-semantic-labeler @ git+https://github.com/SergioGilBorras/P4-Semantic-Labeler.git@v0.1.0"
python -m pip check
```

For **opt-in** real Codex support:

```bash
python -m pip install "p4-semantic-labeler[codex] @ git+https://github.com/SergioGilBorras/P4-Semantic-Labeler.git@v0.1.0"
python -m pip check
```

The package's regular dependencies include `portable-tempdirs` pinned to an immutable GitHub commit. The optional `codex` extra also installs `p4-codex-bridge` from an immutable GitHub commit. `pip` needs Git and appropriate repository access to resolve them. Codex requires its own CLI installation and authentication; no paid inference is needed for the checks below. The `mcp` extra is optional for the local stdio server.

Quick non-billable smoke test:

```bash
python -c "from p4_semantic_labeler import Labeler, LabelRequest, Subject; from p4_semantic_labeler.config import Settings; r=Labeler(settings=Settings(provider='mock')).generate(LabelRequest(subject=Subject(name='process_pending_orders'),max_chars=45)); assert r.provider=='mock' and 0<len(r.label)<=45; print(r.model_dump())"
```

The `mock` provider only formats names and **does not establish semantic AI quality**. Production Codex use must be configured deliberately, with the risks in [Codex provider](codex.md) and [Security policy](../SECURITY.md) reviewed.

## Build a wheel from an identified source ref

To reproduce **v0.1.0 source**, check out the published tag in a separate clean working tree or clone; do not replace your current `main` without checking for local changes. In that checkout:

```bash
python -m pip install build
python -m build --wheel --outdir dist
```

The expected wheel name is `p4_semantic_labeler-0.1.0-py3-none-any.whl`. The build creates `dist/` locally; the repository ignores it. For a reliable distribution, validate that the wheel contains the Python package, bundled prompt templates, metadata, license, and all required runtime files.

Test installation in a **fresh virtual environment** (not the project development environment):

```bash
python -m pip install "dist/p4_semantic_labeler-0.1.0-py3-none-any.whl"
python -m pip check
```

Run the non-billable smoke test above after installation. Repeat with the optional `[codex]` extra if client environments are expected to use it; installing `[codex]` does not itself perform inference. Git-hosted dependencies are **not included inside the wheel**. The actual artifact, environment, dependency availability and license obligations must be verified before delivery. Building a wheel alone is not sufficient to assert client readiness.

## Release gate for customers

Before declaring an artifact distributable, verify: source ref and package version; correct author/description metadata; green CI; successful clean-environment installation and `pip check`; sample Python import and mock inference; dependency access without shared developer credentials; license/security reporting; and checksum of the exact delivered wheel. Publish the verified artifact through an authorized channel (for example, an internal package index or a new GitHub Release) with installation instructions and stated limitations.

Since this repository and some dependencies are private, external clients **cannot necessarily install** a GitHub URL or wheel directly. Provide an authorized distribution/access strategy, including the transitive dependencies, before promising an easy `pip install` experience.
