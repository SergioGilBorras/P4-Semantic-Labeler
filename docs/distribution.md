# Installation, packaging and customer distribution

P4-Semantic-Labeler is a Python **library**, with optional CLI, HTTP and MCP entry points. The source repository and its two P4 Git-hosted dependencies are currently public. Python dependencies are distributed through PyPI or pinned GitHub source commits. A wheel does not embed dependency wheels or a Codex CLI installation.

## Supported environments and dependencies

- Python **3.11+**, Windows and Ubuntu verified through CI.
- Runtime: FastAPI, Pydantic v2, Uvicorn, python-multipart and [portable-tempdirs](https://github.com/SergioGilBorras/portable-tempdirs) **0.1.2** pinned to commit `aad3878ccd8347a1a23faf609b2db21265d30a1d`.
- Optional `[codex]`: [P4-Codex-Bridge](https://github.com/SergioGilBorras/P4-Codex-Bridge) **1.4.1** pinned to commit `a7e21c83670df925c478696c078d1cdc46fa3a9b`, plus an installed/authenticated Codex CLI.
- Optional `[mcp]`: official MCP Python SDK **2.x**, local stdio server only.
- Regular PyPI dependencies use compatible version ranges; exact Git dependencies use immutable SHA pins. Validate final resolved versions with `python -m pip check` and `python -m pip freeze`.

## Installation from GitHub

For development, clone the repository and install into the consumer application's virtual environment:

```bash
python -m pip install -e '.[codex]'
python -m pip check
```

For the **CI-verified 0.1.1 source version**, the following commands install from its immutable commit (rather than a moving `main` branch):

```bash
python -m pip install "p4-semantic-labeler @ git+https://github.com/SergioGilBorras/P4-Semantic-Labeler.git@f0dbaad366554241cc0bcf8e2c5f5f9d90223f3f"
python -m pip install "p4-semantic-labeler[codex] @ git+https://github.com/SergioGilBorras/P4-Semantic-Labeler.git@f0dbaad366554241cc0bcf8e2c5f5f9d90223f3f"
```

The first command installs the base package; the second requests the optional Codex integration. The referenced source commit has passed the six CI jobs, including a wheel build and isolated-install smoke test; **0.1.1 is not yet a published GitHub Release**. The existing tagged Release is `v0.1.0`, representing a different source revision. Once `v0.1.1` is published and verified, consumers can use its release tag.

Git is needed to resolve the direct source requirements. The repositories are currently public, but offline or restricted client networks still require an approved dependency distribution strategy. Never embed tokens in URLs or committed files. A wheel alone does not remove the need to resolve its declared dependencies.

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

Publish a release artifact only when its own tag/commit has successful CI, its wheel builds and installs in isolation, its dependency sources are reachable to the intended recipients, and its installation commands are reproducible. CI uploads a temporary workflow artifact; this is **not** a GitHub Release asset. Record a SHA-256 checksum and a manifest of exact dependencies. Provide the supported Python versions, sample usage, current security limitations, and a private vulnerability-reporting channel.

A version declared in `pyproject.toml` is **not automatically a GitHub Release**. Publish the corresponding immutable tag and attach the tested wheel through a controlled release process. See the [Roadmap](../ROADMAP.md) for operational distribution work.
