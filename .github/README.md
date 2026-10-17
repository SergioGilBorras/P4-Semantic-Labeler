# GitHub automation

This folder contains repository automation and continuous integration.

- [`workflows/ci.yml`](workflows/ci.yml) runs offline linting and tests on Ubuntu and Windows with Python 3.11, 3.12 and 3.13. It also validates Python distribution archives on the designated packaging job.
- [Contributing](../CONTRIBUTING.md) explains how to submit code and documentation changes.
- [Security](../SECURITY.md) documents security responsibilities and vulnerability reporting.

CI must not invoke live Codex inference or depend on private AI credentials. GitHub Actions artifacts are build outputs, **not** published GitHub Release assets.
