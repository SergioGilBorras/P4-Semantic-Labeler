# Evaluation laboratory

Versioned synthetic requests live in `entrada/casos/`; case-specific rubrics live only in `criterios.json`. The generator receives `entrada.json` only. Author-known cohorts: 36 calibration, 12 regression and 12 reserve, with an explicit eight-case pilot.

The baseline is frozen before optimization. Existing cases may be rerun as often as needed. A fresh batch under `entrada/nuevas/<id>` is first evaluated once without retrospective edits, then explicitly incorporated into `entrada/incorporados.json` and becomes part of the accumulated regression set. Later generalization claims require a genuinely different unseen batch.

## Python laboratory

```bash
python -m evaluacion.herramientas.lab validate
python -m evaluacion.herramientas.lab list
python -m evaluacion.herramientas.lab prepare --set piloto
python -m evaluacion.herramientas.lab run --set piloto
python -m evaluacion.herramientas.lab run --set acumulada
```

Real inference requires explicit CLI consent, provider codex and a bounded call budget; it is disabled by default. Output directories under `salida/` are disposable but **never automatically deleted**. No semantic quality score is assigned by the runner. Evaluation needs a separate assessor receiving frozen rubric only after production. Run output should not be checked into Git.

## Windows PowerShell workflows

Run these commands from the repository root with the project's `.venv` installed:

```powershell
# Mock evaluation of the eight-case pilot; no real model calls.
.\evaluacion\run-evaluation-batch.ps1 -SetName piloto -MaxCases 8 -MaxCalls 8

# Mock evaluations for two selected cases in separate runs.
.\evaluacion\run-evaluation-batch.ps1 -SetName piloto -CaseIds SL-0001,SL-0002 -MaxCases 2 -MaxCalls 2

# Exactly one real inference; requires explicit authorization flags.
.\evaluacion\run-evaluation-batch.ps1 -SetName piloto -CaseIds SL-0001 -MaxCases 1 -MaxCalls 1 -Real -ApproveReal

# Full pilot with real inference: AT MOST eight model calls.
.\evaluacion\run-evaluation-batch.ps1 -SetName piloto -MaxCases 8 -MaxCalls 8 -Real -ApproveReal

# Read existing results only; creates no inference.
.\evaluacion\summarize-evaluations.ps1
```

`run-evaluation-batch.ps1` calls the existing Python laboratory. If no case IDs are supplied, the complete selected cohort is one Python run. With `-CaseIds`, each ID is a separate run; the total requested repetitions must fit within `-MaxCalls`. To evaluate a larger cohort, increase `-MaxCases` and `-MaxCalls` explicitly. For registered external batches, use `-SetName lote -Batch YOUR_EXISTING_BATCH_ID`. Real model requests only happen with both `-Real` and `-ApproveReal`, so each invocation can incur model usage. The launcher does not retry failed requests. By default it uses the project `.venv` on Windows; `-PythonExecutable` accepts an explicit absolute interpreter path for CI or a separate environment.

`summarize-evaluations.ps1` scans final runs under `evaluacion/salida/`, and writes **`evaluacion/salida/evaluation-summary.json`**. That single file contains run metadata, case IDs, labels, character counts, objective checks, and safe structured diagnostics. It excludes raw prompts, case input content, rubrics and raw provider output objects. It records skipped/incomplete runs rather than silently interpreting them as success. A multi-case `results.json` is parsed as a JSON array and each case is reported separately; structurally malformed runs are skipped with `malformed_results` instead of interrupting other runs. The report includes `complete: false` when any recognized run was skipped (including `access_denied` for a protected manifest). An access-denied directory does not prevent the accessible runs from being summarized; however, the resulting JSON is **partial** and must not be treated as a complete evaluation of the folder. It never repairs ACLs or deletes unreadable directories. Inspect the summary's `skipped` entries before sharing or scoring results, and investigate access permissions separately. Batch execution updates this file automatically, including after a failed attempt where possible.

## Truncated labels and semantic review

The production service may return a label truncated to the character limit, with
`output_truncated: meaning may be incomplete` in `raw_output.warnings`. The
evaluation laboratory deliberately sets `reduction_attempts=0` so the approved
call budget cannot silently grow. A truncated label is **not** automatic evidence
of semantic acceptance: for **new** runs, the result is recorded as
`SEMANTIC_REVIEW_REQUIRED` (the manifest becomes `COMPLETED_WITH_ERRORS`);
the original label and warning are preserved, and no retry is attempted. The
batch launcher consequently reports `evaluation_success=False` even when
`report_success=True`.

Historical `results.json` and manifests are never rewritten. The consolidated
report exposes `needs_semantic_review: true` per result and
`totals.results_requiring_review` for both historical and new truncations;
arbitrary provider warnings are not copied into the shareable report.
`complete: true` only says all remaining recognized run folders were read,
**not** that every label passed its semantic rubric. A separate evaluator
must assess fidelity and other quality criteria manually.

## Retention and cleanup

Edit **`evaluacion/evaluation-retention.json`** and add or remove exact `run_id` values in `keep_run_ids`. They must match the directory names under `evaluacion/salida/`. The checked-in file initially protects the known successful real pilots and a diagnostic failure from 2026-10-10. This JSON is a user-maintained policy; review changes before committing because your local run IDs may differ.

```powershell
# Preview only (default): shows eligible old runs but deletes nothing.
.\evaluacion\cleanup-evaluations.ps1

# Delete eligible runs only after inspecting the preview.
.\evaluacion\cleanup-evaluations.ps1 -Apply

# Optional: permit cleanup of runs created less than 60 minutes ago.
.\evaluacion\cleanup-evaluations.ps1 -MinAgeMinutes 0
```

The cleanup tool never removes a protected ID; by default, it skips runs modified in the last hour. It only considers directories with the laboratory's run-name shape, a matching valid manifest, `artifacts_disposable: true`, a final status, and no detected reparse points in the tree. Unknown, incomplete, and access-denied directories are retained, even when using `-Apply`; the script never attempts to bypass ACLs. Without `-Apply` it performs **no deletion**. It deliberately does not remove `salida/` itself or the consolidated JSON file. Shell-based deletion of intentionally persistent laboratory results is **not** the handle-identity-verified cleanup of `portable-tempdirs`; only run it on a trusted local tree with no concurrent writers. Keep evidence that may be needed for batch incorporation, comparison or investigation before applying cleanup. Removal is irreversible.

The shared pytest fixture uses `portable-tempdirs` both for a unique session parent created directly under the project root and for each per-test workspace. Both are managed with context managers and are removed when their owners exit, including on test failures. No persistent `.portable-test-workspaces/` parent is created by new sessions. An old `.portable-test-workspaces/` directory may still contain historical unowned artifacts; inspect it before removal. If it is empty and no tests are running, it can be removed nonrecursively. Old Codex CLI profile paths and historical test artifacts are **outside the scope** of the evaluation cleanup script; never delete them using unchecked recursive fallback code.

Legacy local `prueba*.ps1` scripts are not part of this GitHub workflow. Deleting your untracked local files, if desired, is a separate local action.
