# Contributing

Please open a GitHub issue to discuss behavior changes. Keep this library free of consumer-specific dictionaries, special cases or unrelated agent functionality. Target Python >=3.11. Create a feature branch rather than editing `main`; open a pull request with tests and a description of privacy implications for any provider integration.

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check .
```

Unit tests must never require external AI credentials or paid requests. Real-provider integration tests, if added later, should be opt-in and disabled in CI by default. Never place private source code, credentials or proprietary documentation into fixtures. For security issues see `SECURITY.md`.
