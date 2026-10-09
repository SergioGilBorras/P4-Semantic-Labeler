"""Offline checks for the evaluation laboratory."""
import json
import subprocess
import sys

import pytest

from evaluacion.herramientas import lab


def test_initial_cohorts_and_pilot():
    summary = lab.validate()
    assert summary["valid"]
    assert summary["initial_cases"] == 60
    assert summary["accumulated_cases"] == 60
    assert summary["pilot_cases"] == 8
    for key, expected in (("calibracion", 36), ("regresion", 12), ("reserva", 12)):
        assert len(lab.select_cases(key, None)) == expected


def test_input_isolation_and_rubrics():
    selection = lab.select_cases("piloto", None)
    for cid, root in selection:
        inp = lab.load_json(lab.manifest_path(root, cid, "entrada.json"))
        assert "dimensions" not in json.dumps(inp)
        rubric = lab.load_json(lab.manifest_path(root, cid, "criterios.json"))
        assert rubric["case_id"] == cid


def test_dry_run_without_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(lab, "OUTPUT", tmp_path)
    manifest, directory = lab.make_run("piloto", None, "prepare", 1, 60, 60, 120, False, False)
    assert manifest["model_invoked"] is False
    assert manifest["observed_calls"] == 0
    assert manifest["status"] == "COMPLETED"
    assert len(list((directory / "inputs").glob("*.json"))) == 8
    assert not (directory / "results.json").exists()


def test_real_inference_requires_explicit_consent(monkeypatch, tmp_path):
    monkeypatch.setattr(lab, "OUTPUT", tmp_path)
    with pytest.raises(ValueError):
        lab.make_run("piloto", None, "run", 1, 60, 60, 120, True, False)
    assert list(tmp_path.iterdir()) == []


def test_no_model_captured_in_preparation(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "OUTPUT", tmp_path)
    result, _ = lab.make_run("acumulada", None, "prepare", 1, 60, 60, 120, False, False)
    assert result["cases"][0] == "SL-0001"
    assert len(result["cases"]) == 60
    assert result["model_invoked"] is False


def test_invalid_new_batch_path():
    with pytest.raises(ValueError):
        lab.root_for_batch("../outside")


def test_module_entrypoint():
    result = subprocess.run(
        [sys.executable, "-m", "evaluacion.herramientas.lab", "validate"],
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["initial_cases"] == 60
