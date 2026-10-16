# Installation, packaging and customer distribution

P4-Semantic-Labeler is a Python **library**, with optional CLI, HTTP and MCP entry points. The source repository is private; some dependencies are supplied directly from GitHub. A wheel does not embed dependency wheels or a Codex CLI installation.

## Supported environments and dependencies

- Python **3.11+**, Windows and Ubuntu verified through CI.
- Runtime: FastAPI, Pydantic v2, Uvicorn, python-multipart and [portable-tempdirs](https://github.com/SergioGilBorras/portable-tempdirs) **0.1.2** pinned to commit `aad3878ccd8347a1a23faf609b2db21265d30a1d`.
- Optional `[codex]`: [P4-Codex-Bridge](https://github.com/SergioGilBorras/P4-Codex-Bridge) **1.4.1** pinned to commit `a7e21c83670df925c478696c078d1cdc46fa3a9b`, plus an installed/authenticated Codex CLI.
- Optional `[mcp]`: official MCP Python SDK **2.x**, local stdio server only.
- Regular PyPI dependencies use compatible version ranges; exact Git dependencies use immutable SHA pins. Validate final resolved versions with `python -m pip check` and `python -m pip freeze`.

## Installation from GitHub

For development or authorized internal use, clone the repository and install into the consumer application's virtual environment:

```bash
python -m pip install -e '.[codex]'
python -m pip check
```

To consume a **published immutable release**, use an actual release tag or commit SHA that exists in GitHub. Do not use a moving `@main` in customer dependency declarations.

```bash
python -m pip install "p4-semantic-labeler[codex] @ git+https://github.com/SergioGilBorras/P4-Semantic-Labeler.git@<PUBLISHED_TAG_OR_COMMIT>"
```

Replace `<PUBLISHED_TAG_OR_COMMIT>` with a real, verified tag/SHA. This placeholder is intentionally **not** a published release. Private repositories require authorized credentials; never store access tokens in `pyproject.toml`, URLs, CI logs or command history. A wheel alone does not remove the need to resolve its declared source dependencies.

## Build and verify a wheel

From a **clean checkout of the exact candidate commit**:

```bash
python -m pip install build
python -m build --wheel --outdir dist
```

When packaging version `0.1.1`, the expected name is `p4_semantic_labeler-0.1.1-py3-none-any.whl`. Inspect the resulting wheel to confirm its package metadata, prompt templates, `LICENSE` and console entry points. The `dist/` and `build/` directories are generated artifacts and are intentionally excluded by `.gitignore`.

Install in a **fresh virtual environment**, not the build environment:

```bash
python -m pip install "dist/p4_semantic_labeler-0.1.1-py3-none-any.whl"
python -m pip check
python -c "from p4_semantic_labeler import Labeler, LabelRequest, Subject; from p4_semantic_labeler.config import Settings; r=Labeler(settings=Settings(provider='mock')).generate(LabelRequest(subject=Subject(name='process_pending_orders'),max_chars=45)); assert r.provider=='mock' and r.label == 'process pending orders'; print('Packaging OK')"
```

The commands do not invoke Codex. For `[codex]` installations, also verify that the **same interpreter** imports Bridge 1.4.1 and portable-tempdirs 0.1.2 and that the Codex CLI is installed and authenticated. A real semantic-quality assessment must be conducted separately.

## Customer release gate

Publish a release artifact only when its own tag/commit has successful CI, its wheel builds and installs in isolation, its dependency sources are reachable to the intended recipients, and its installation commands are reproducible. Record a SHA-256 checksum and a manifest of exact dependencies. Provide the supported Python versions, sample usage, current security limitations, and a private vulnerability-reporting channel.

A version declared in `pyproject.toml` is **not automatically a GitHub Release**. Publish the corresponding immutable tag and attach the tested wheel through a controlled release process. See the [Roadmap](../ROADMAP.md) for operational distribution work.
