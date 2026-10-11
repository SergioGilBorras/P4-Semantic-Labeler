"""Versioned, non-destructive evaluation runner. No real model calls by default."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from p4_semantic_labeler.providers.codex_diagnostics import (
    DIAGNOSTIC_CATEGORIES,
    STRUCTURED_ERROR_CATEGORIES,
    UNKNOWN,
    category_for_structured_code,
)

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "entrada"
OUTPUT = ROOT / "salida"
SETS = {"calibracion", "regresion", "reserva", "piloto", "acumulada", "lote"}
ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,70}$")


def load_json(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing or unsafe evaluation file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_path(root: Path, case_id: str, filename: str) -> Path:
    if not ID_PATTERN.fullmatch(case_id):
        raise ValueError("Unsafe case identifier")
    candidate = root / "casos" / case_id / filename
    if candidate.is_symlink() or not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("Unsafe case path")
    return candidate


def load_catalog(root: Path):
    catalog = load_json(root / "catalogo.json")
    cases = catalog.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("Catalog must contain a list of cases")
    ids = [entry["id"] for entry in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case identifiers")
    return {entry["id"]: entry for entry in cases}


def root_for_batch(batch: str) -> Path:
    if not ID_PATTERN.fullmatch(batch):
        raise ValueError("Unsafe batch identifier")
    root = INPUT / "nuevas" / batch
    if root.is_symlink() or not root.is_dir() or not root.resolve().is_relative_to(INPUT.resolve()):
        raise ValueError("Unknown or unsafe batch")
    return root


def select_cases(which: str, batch: str | None):
    catalog = load_catalog(INPUT)
    selected = []
    if which == "lote":
        if not batch:
            raise ValueError("--batch is required for --set lote")
        root = root_for_batch(batch)
        batch_catalog = load_catalog(root)
        overlap = set(batch_catalog) & set(catalog)
        if overlap:
            raise ValueError("Batch contains existing case identifiers")
        return [(cid, root) for cid in batch_catalog]
    if which == "acumulada":
        selected = list(catalog)
        included = load_json(INPUT / "incorporados.json")
        roots = [(cid, INPUT) for cid in selected]
        for batch_id in included.get("batches", []):
            root = root_for_batch(batch_id)
            for cid in load_catalog(root):
                if cid in selected:
                    raise ValueError("Duplicate accumulated identifier")
                selected.append(cid)
                roots.append((cid, root))
        return roots
    ids = load_json(INPUT / "conjuntos" / f"{which}.json").get("ids", [])
    if len(ids) != len(set(ids)) or not set(ids).issubset(catalog):
        raise ValueError("Invalid or overlapping cohort identifiers")
    return [(cid, INPUT) for cid in ids]


def validate():
    catalog = load_catalog(INPUT)
    cohorts = {}
    for name in ("calibracion", "regresion", "reserva"):
        ids = load_json(INPUT / "conjuntos" / f"{name}.json")["ids"]
        if len(ids) != len(set(ids)) or not set(ids).issubset(catalog):
            raise ValueError(f"Invalid cohort: {name}")
        cohorts[name] = ids
    all_ids = cohorts["calibracion"] + cohorts["regresion"] + cohorts["reserva"]
    if len(all_ids) != len(set(all_ids)) or set(all_ids) != set(catalog):
        raise ValueError("Initial cohorts must be disjoint and exhaustive")
    for cid, record in catalog.items():
        if not ID_PATTERN.fullmatch(cid) or record["cohort"] not in cohorts:
            raise ValueError("Invalid catalog identifier/cohort")
        if cid not in cohorts[record["cohort"]]:
            raise ValueError("Catalog cohort mismatch")
        request = load_json(manifest_path(INPUT, cid, "entrada.json"))
        rubric = load_json(manifest_path(INPUT, cid, "criterios.json"))
        if rubric["case_id"] != cid or "subject" not in request:
            raise ValueError("Missing input or mismatched rubric")
        if rubric["expected_outcome"] not in ("label", "validation_error"):
            raise ValueError("Invalid expected outcome")
        if sum(rubric["dimensions"].values()) != 100:
            raise ValueError("Rubric dimensions must sum to 100")
    pilot = load_json(INPUT / "conjuntos" / "piloto.json")["ids"]
    if len(pilot) != len(set(pilot)) or not set(pilot).issubset(catalog):
        raise ValueError("Invalid pilot cohort")
    included = load_json(INPUT / "incorporados.json")
    if len(included.get("batches", [])) != len(set(included.get("batches", []))):
        raise ValueError("Duplicate incorporated batches")
    for batch in included.get("batches", []):
        root = root_for_batch(batch)
        batch_catalog = load_catalog(root)
        if set(batch_catalog) & set(catalog):
            raise ValueError("Batch duplicates initial catalog")
        for cid in batch_catalog:
            request = load_json(manifest_path(root, cid, "entrada.json"))
            rubric = load_json(manifest_path(root, cid, "criterios.json"))
            if not request or rubric["case_id"] != cid:
                raise ValueError("Invalid incorporated batch")
    return {"valid": True, "initial_cases": len(catalog),
            "accumulated_cases": len(select_cases("acumulada", None)),
            "pilot_cases": len(pilot), "incorporated_batches": included.get("batches", [])}


def new_run_dir():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = OUTPUT / f"{timestamp}_{uuid.uuid4().hex[:12]}"
    if os.name == "nt":
        destination.mkdir()  # Inherit ACLs from the authorized parent.
    else:
        destination.mkdir(mode=0o700)
    return destination


def record_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_error_diagnostics(exc: Exception) -> dict[str, str]:
    category = getattr(exc, "diagnostic_category", UNKNOWN)
    if not isinstance(category, str) or category not in DIAGNOSTIC_CATEGORIES:
        category = UNKNOWN
    diagnostic = {"diagnostic_category": category}
    code = getattr(exc, "bridge_error_code", None)
    if (
        isinstance(code, str)
        and code in STRUCTURED_ERROR_CATEGORIES
        and category_for_structured_code(code) == category
    ):
        diagnostic["provider_error_code"] = code
    return diagnostic


def sync_bridge_telemetry(labeler, manifest: dict) -> None:
    provider = getattr(labeler, "provider", None)
    snapshot_fn = getattr(provider, "telemetry_snapshot", None)
    if not callable(snapshot_fn):
        return
    snapshot = snapshot_fn()
    mappings = {
        "bridge_calls_attempted": "bridge_calls_attempted",
        "bridge_results_received": "bridge_results_received",
        "provider_responses_received": "responses_received",
        "inferences_confirmed": "inferences_confirmed",
    }
    for source, target in mappings.items():
        value = snapshot.get(source, 0)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            manifest[target] = value
    manifest["model_invoked"] = manifest["inferences_confirmed"] > 0
    # Unlike runner_calls_attempted, this includes any reduction retries.
    manifest["observed_calls"] = manifest["bridge_calls_attempted"]


def make_run(which: str, batch: str | None, mode: str, repetitions: int, max_cases: int,
             max_calls: int, timeout: float, real: bool, consent: bool,
             case_id: str | None = None, reduction_attempts: int = 0):
    config = yaml.safe_load((ROOT / "configuracion" / "evaluacion.yaml").read_text(encoding="utf-8"))
    if config.get("real_inference_default") is not False:
        raise ValueError("Real inference default must be disabled")
    if not 1 <= repetitions <= 10 or not 1 <= max_cases <= 1000:
        raise ValueError("Invalid run size")
    if not 1 <= max_calls <= 10000 or not 1 <= timeout <= 3600:
        raise ValueError("Invalid provider budget")
    if reduction_attempts not in (0, 1):
        raise ValueError("Reduction attempts must be 0 or 1")
    if real and (not consent or mode != "run"):
        raise ValueError("Real inference needs --real and --approve-real for run")
    selected = select_cases(which, batch)
    if case_id is not None:
        filtered = [(cid, root) for cid, root in selected if cid == case_id]
        if not filtered:
            raise ValueError("Case identifier is not in the selected set")
        selected = filtered
    if len(selected) > max_cases:
        raise ValueError("Selection exceeds --max-cases; no cases executed")
    # Reserve the worst case: one initial call plus each permitted rewrite.
    # This makes the approved limit a strict cap on actual provider calls.
    if len(selected) * repetitions * (1 + reduction_attempts) > max_calls:
        if real:
            raise ValueError("Requested calls exceed the explicitly approved cap")
        raise ValueError("Run exceeds maximum call budget")
    folder = new_run_dir()
    input_hashes = {}
    for cid, root in selected:
        input_hashes[cid] = record_sha(manifest_path(root, cid, "entrada.json"))
    manifest = {
        "run_id": folder.name, "started_utc": datetime.now(timezone.utc).isoformat(),
        "set": which, "batch": batch, "selected_case": case_id,
        "cases": [cid for cid, _ in selected],
        "input_sha256": input_hashes, "repetitions": repetitions,
        "provider_requested": "codex" if real else "mock",
        "model_requested": "provider_default" if real else "none",
        # Fingerprint the exact prompt used so before/after runs can be
        # compared without copying prompts or modifying historical evidence.
        "prompt_system_sha256": record_sha(
            ROOT.parent / "src" / "p4_semantic_labeler" / "prompts" / "label_system.txt"
        ),
        "model_effective": "NO_DISPONIBLE", "tokens": "NO_DISPONIBLE",
        "cost": "NO_DISPONIBLE", "timeout_seconds": timeout,
        "max_calls": max_calls, "reduction_attempts": reduction_attempts,
        "real_authorization": real and consent,
        "audit": config["audit"], "external_submission": False,
        "model_invoked": False, "observed_calls": 0,
        "runner_calls_attempted": 0, "bridge_calls_attempted": 0,
        "bridge_results_received": 0, "responses_received": 0,
        "inferences_confirmed": 0,
        "status": "PREPARED" if mode == "prepare" else "RUNNING",
        "artifacts_disposable": True
    }
    save_json(folder / "manifest.json", manifest)
    source = folder / "inputs"
    source.mkdir()
    for cid, root in selected:
        (source / f"{cid}.json").write_bytes(manifest_path(root, cid, "entrada.json").read_bytes())
    if mode == "prepare":
        manifest["status"] = "COMPLETED"
        save_json(folder / "manifest.json", manifest)
        return manifest, folder
    from p4_semantic_labeler.config import Settings
    from p4_semantic_labeler.core.models import LabelRequest
    from p4_semantic_labeler.core.service import Labeler
    settings = Settings(provider="codex" if real else "mock",
                        provider_timeout_seconds=timeout,
                        reduction_attempts=reduction_attempts)
    labeler = Labeler(settings=settings)
    async def call_one(req):
        return await asyncio.wait_for(
            labeler.agenerate(req), timeout=timeout * (1 + reduction_attempts) + 10
        )
    results = []
    try:
        for cid, root in selected:
            original = load_json(manifest_path(root, cid, "entrada.json"))
            for repeat in range(1, repetitions + 1):
                item = {"id": cid, "repeat": repeat,
                        "input_sha256": input_hashes[cid],
                        "raw_output": None, "status": "UNKNOWN"}
                try:
                    req = LabelRequest.model_validate(original)
                    if manifest["observed_calls"] + 1 + reduction_attempts > max_calls:
                        item.update(status="BUDGET_EXHAUSTED", error="call_cap")
                    else:
                        manifest["runner_calls_attempted"] += 1
                        manifest["observed_calls"] += 1
                        start = time.monotonic()
                        result = asyncio.run(call_one(req))
                        raw = result.model_dump()
                        if real:
                            sync_bridge_telemetry(labeler, manifest)
                        else:
                            manifest["responses_received"] += 1
                        # A length-safe fallback can still lose meaning. Keep
                        # the provider output as evidence, but require a separate
                        # semantic review instead of marking it fully completed.
                        needs_review = any(
                            isinstance(warning, str) and warning.startswith("output_truncated:")
                            for warning in raw.get("warnings", [])
                        )
                        item.update(status=("SEMANTIC_REVIEW_REQUIRED" if needs_review
                                            else "COMPLETED"), raw_output=raw,
                                    elapsed_seconds=round(time.monotonic() - start, 3),
                                    objective_checks={
                                        "not_empty": bool(raw.get("label")),
                                        "within_limit": len(raw.get("label", "")) <= req.max_chars,
                                        "char_count_matches": raw.get("char_count") == len(raw.get("label", "")),
                                        "provider_matches": raw.get("provider") == ("codex" if real else "mock")
                                    })
                        if not all(item["objective_checks"].values()):
                            item["status"] = "OBJECTIVE_FAILURE"
                except Exception as exc:
                    # Never record exception text: it can contain private user input.
                    if real:
                        sync_bridge_telemetry(labeler, manifest)
                    item.update(status="ERROR", error_type=type(exc).__name__,
                                **safe_error_diagnostics(exc))
                results.append(item)
                save_json(folder / "results.json", results)
    except (KeyboardInterrupt, SystemExit):
        manifest["status"] = "INTERRUPTED"
    if manifest["status"] != "INTERRUPTED":
        manifest["status"] = ("COMPLETED" if all(x["status"] in ("COMPLETED", "ERROR") for x in results)
                              else "COMPLETED_WITH_ERRORS")
        if any(x["status"] in ("ERROR", "OBJECTIVE_FAILURE", "BUDGET_EXHAUSTED") for x in results):
            manifest["status"] = "COMPLETED_WITH_ERRORS"
    manifest["completed_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["results_file"] = "results.json"
    save_json(folder / "manifest.json", manifest)
    return manifest, folder


def export_run(run_directory: str):
    folder = Path(run_directory).resolve()
    if not folder.is_relative_to(OUTPUT.resolve()) or not folder.is_dir():
        raise ValueError("Run path is outside evaluation output")
    manifest = load_json(folder / "manifest.json")
    results = load_json(folder / "results.json")
    if not manifest["cases"]:
        raise ValueError("Run contains no case records")
    by_id = dict(select_cases(manifest["set"], manifest["batch"]))
    export = folder / "independent_evaluation"
    export.mkdir(exist_ok=False)
    for cid in manifest["cases"]:
        root = by_id[cid]
        item = {"input": load_json(manifest_path(root, cid, "entrada.json")),
                "rubric_for_evaluator_only": load_json(manifest_path(root, cid, "criterios.json")),
                "outputs": [row for row in results if row["id"] == cid]}
        save_json(export / f"{cid}.json", item)
    save_json(export / "manifest.json", manifest)
    return export


def incorporate(batch: str, run_directory: str):
    root = root_for_batch(batch)
    cohort = load_catalog(root)
    for cid in cohort:
        load_json(manifest_path(root, cid, "entrada.json"))
        rubric = load_json(manifest_path(root, cid, "criterios.json"))
        if rubric["case_id"] != cid:
            raise ValueError("Rubric mismatch")
    folder = Path(run_directory).resolve()
    if not folder.is_relative_to(OUTPUT.resolve()):
        raise ValueError("Evidence must be in the evaluation output root")
    manifest = load_json(folder / "manifest.json")
    if manifest.get("set") != "lote" or manifest.get("batch") != batch or manifest.get("status") not in ("COMPLETED", "COMPLETED_WITH_ERRORS"):
        raise ValueError("First-run evidence for this batch is required")
    path = INPUT / "incorporados.json"
    included = load_json(path)
    if batch in included["batches"]:
        raise ValueError("Batch already incorporated")
    included["batches"].append(batch)
    save_json(path, included)
    return {"incorporated": batch, "accumulated": len(select_cases("acumulada", None))}


def main():
    parser = argparse.ArgumentParser(prog="semantic-evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("list")
    for command in ("prepare", "run"):
        p = sub.add_parser(command)
        p.add_argument("--set", choices=sorted(SETS), default="piloto")
        p.add_argument("--batch")
        p.add_argument("--case", dest="case_id")
        p.add_argument("--repetitions", type=int, default=1)
        p.add_argument("--max-cases", type=int, default=60)
        p.add_argument("--max-calls", type=int, default=60)
        p.add_argument("--reduction-attempts", type=int, choices=(0, 1), default=0)
        p.add_argument("--timeout", type=float, default=120)
        p.add_argument("--real", action="store_true")
        p.add_argument("--approve-real", action="store_true")
    p = sub.add_parser("export")
    p.add_argument("--run-dir", required=True)
    p = sub.add_parser("incorporate")
    p.add_argument("--batch", required=True)
    p.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            answer = validate()
        elif args.command == "list":
            answer = {"sets": {name: len(select_cases(name, None)) for name in SETS - {"lote"}}}
        elif args.command in ("prepare", "run"):
            answer, folder = make_run(args.set, args.batch, args.command,
                                      args.repetitions, args.max_cases, args.max_calls,
                                      args.timeout, args.real, args.approve_real,
                                      args.case_id, args.reduction_attempts)
            answer["directory"] = str(folder)
        elif args.command == "export":
            answer = {"export_directory": str(export_run(args.run_dir))}
        else:
            answer = incorporate(args.batch, args.run_dir)
        print(json.dumps(answer, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error_type": type(exc).__name__}), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
