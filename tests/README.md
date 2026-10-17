# Automated tests

The tests cover request validation, provider behavior, context building, output limits, CLI/HTTP/MCP interfaces, temporary workspaces, dependency contracts and documentation consistency.

From the repository root, in a Python 3.11+ environment:

```bash
python -m pip install -e '.[dev,codex]'
python -m pip check
ruff check .
pytest -q
```

- [`test_documentation_contract.py`](test_documentation_contract.py) checks package versions, author/metadata, OpenAPI shapes, local Markdown links and main-folder READMEs.
- [`test_dependency_contract.py`](test_dependency_contract.py) verifies installed GitHub-pinned dependencies and the optional Bridge public API.
- [`test_codex_bridge.py`](test_codex_bridge.py) exercises Bridge adapters through test doubles without launching Codex.
- [CI workflow](../.github/workflows/ci.yml) runs Windows/Ubuntu on Python 3.11–3.13. The packaging job builds and inspects both distribution formats.

Evaluation laboratory unit tests and PowerShell regressions live under [`evaluacion/tests/`](../evaluacion/tests/); see [Evaluation](../evaluacion/README.md).

**These tests never authorize or perform real AI inference.** Running a real provider is a separate, explicit operation.
