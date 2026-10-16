# Quality evaluation and acceptance criteria

P4-Semantic-Labeler separates **mechanical correctness** (schema validity, length limits, error handling, sanitization and provider calls) from **semantic correctness** (fidelity, language, style and utility). CI tests the mechanical contract on Windows and Ubuntu; it does **not** make paid Codex calls or certify all AI-generated labels.

## Evaluation methodology

A versioned synthetic evaluation corpus contains **60 cases**: 58 for contextual generation and two for negative validation. Cases and scoring rubrics are kept under `evaluacion/entrada/`. Each case defines a 0–4 rubric with these weighted dimensions:

| Dimension | Weight |
|---|---:|
| Functionality | 25% |
| Fidelity | 35% |
| Utility | 20% |
| Coverage | 10% |
| Coherence | 5% |
| Safety | 5% |

An acceptable semantic assessment requires a weighted score of at least **3.2**, functionality at least **3**, fidelity at least **3**, and **no critical failure**, based on independent human evaluation. Automated validation is **not** a substitute for such assessment.

## Evidence and current limitations

The recorded V1 evaluation evidence comprises **231 runs** and **258 results** (250 Codex, 8 mock). Of 246 Codex outputs with labels, **17** have recorded semantic-review warnings; **4** of 250 Codex runs have technical errors. All 254 outputs bearing labels passed the recorded objective checks. These are counts from an evaluation snapshot, **not production reliability estimates**, and no overall independent semantic pass rate has been established.

The protected set of **231 unique run IDs** is recorded in `evaluacion/evaluation-retention.json`. The consolidated summary is kept outside Git under `evaluacion/salida/`; it is not part of a distributable wheel. Historical evidence is preserved for traceability. Do not apply destructive cleanup to protected runs.

Current limitations include possible semantic loss from hard-limit truncation; approximate token accounting; model-dependent language/style accuracy; environment-dependent Codex availability; inherited MCP side effects; and per-process HTTP rate limiting. Cases with negation, causal context or extreme character limits require independent review before use in high-stakes workflows.

## Run offline checks

```bash
python -m pip install -e '.[dev,codex]'
python -m pip check
ruff check .
pytest -q
python -m evaluacion.herramientas.lab validate
```

For bounded evaluation workflows, prompts and explicit opt-in real-inference controls see [Evaluation laboratory](../evaluacion/README.md). Real inference can incur cost and must be intentionally authorized.
