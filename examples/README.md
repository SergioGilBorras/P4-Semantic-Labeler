# Examples

Minimal inputs for the documented interfaces. These are **examples**, not training data or proof of semantic quality.

| File | Purpose |
|---|---|
| [`orders.py`](orders.py) | Python source provided as text; P4 parses it but never executes it |
| [`request.json`](request.json) | One `LabelRequest` for the Python or HTTP interface |
| [`batch.jsonl`](batch.jsonl) | Two requests for the CLI's JSONL batch format |

From the repository root, install the package and select the **non-AI mock provider**. Example with Windows PowerShell:

```powershell
$env:P4_LABELER_PROVIDER = 'mock'; p4-labeler label --name process_pending_orders --kind function --file .\examples\orders.py --max-chars 45 --json
```

```powershell
$env:P4_LABELER_PROVIDER = 'mock'; p4-labeler batch --input .\examples\batch.jsonl --format jsonl
```

The mock provider formats subject names deterministically; it does **not** understand the accompanying code or translate to the requested language. For real model generation, see [Codex setup](../docs/codex.md). Do not execute real inference without explicit authorization.
