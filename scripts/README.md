# Packaging scripts

[`build-distribution.ps1`](build-distribution.ps1) is the Windows PowerShell 5.1 build and mock-only packaging-verification entry point. From a **clean checkout of the repository root**:

```powershell
.\scripts\build-distribution.ps1
```

The script selects `.venv\Scripts\python.exe` if present (otherwise `python` from PATH), runs `python -m build`, verifies both archives and their required resources, and tests each archive in its own new temporary virtual environment using **mock only**. It prints SHA-256 checksums and removes only its **own newly created** verification environments and build folder. It does **not** delete the normal `.venv/`, protected evaluation output or the final `dist/`.

The script refuses to overwrite a non-empty `dist/` or existing verification environments. Review or archive existing files deliberately before repeating the operation. See [Distribution](../docs/distribution.md) and [CI](../.github/README.md).
