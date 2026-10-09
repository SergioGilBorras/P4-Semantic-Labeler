# Evaluation laboratory

Versioned synthetic requests live in `entrada/casos/`; case-specific rubrics live only in `criterios.json`. The generator receives `entrada.json` only. Author-known cohorts: 36 calibration, 12 regression and 12 reserve, with an explicit eight-case pilot.

The baseline is frozen before optimization. Existing cases may be rerun as often as needed. A fresh batch under `entrada/nuevas/<id>` is first evaluated once without retrospective edits, then explicitly incorporated into `entrada/incorporados.json` and becomes part of the accumulated regression set. Later generalization claims require a genuinely different unseen batch.

Commands:
```bash
python -m evaluacion.herramientas.lab validate
python -m evaluacion.herramientas.lab list
python -m evaluacion.herramientas.lab prepare --set piloto
python -m evaluacion.herramientas.lab run --set piloto
python -m evaluacion.herramientas.lab run --set acumulada
```

Real inference requires explicit CLI consent, provider codex and a bounded call budget; it is disabled by default. Output directories under `salida/` are disposable but **never automatically deleted**. No semantic quality score is assigned by the runner. Evaluation needs a separate assessor receiving frozen rubric only after production. Run output should not be checked into Git.
