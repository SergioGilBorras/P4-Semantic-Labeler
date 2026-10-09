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


def test_individual_case_prepare_preserves_input_and_excludes_rubric(monkeypatch, tmp_path):
    monkeypatch.setattr(lab, "OUTPUT", tmp_path)
    result, directory = lab.make_run(
        "piloto", None, "prepare", 1, 1, 1, 120, False, False, case_id="SL-0001"
    )
    expected = lab.manifest_path(lab.INPUT, "SL-0001", "entrada.json").read_bytes()
    assert result["set"] == "piloto"
    assert result["selected_case"] == "SL-0001"
    assert result["cases"] == ["SL-0001"]
    assert (directory / "inputs" / "SL-0001.json").read_bytes() == expected
    assert sorted(p.name for p in (directory / "inputs").iterdir()) == ["SL-0001.json"]
    assert result["model_invoked"] is False
    assert result["observed_calls"] == 0


@pytest.mark.parametrize("case_id", ["SL-0003", "SL-NOT-FOUND"])
def test_case_outside_selected_set_is_blocked_before_run_creation(monkeypatch, case_id):
    def unexpected_run_dir():
        pytest.fail("An invalid case must be rejected before creating a run")

    monkeypatch.setattr(lab, "new_run_dir", unexpected_run_dir)
    with pytest.raises(ValueError, match="not in the selected set"):
        lab.make_run(
            "piloto", None, "run", 1, 1, 1, 120, True, True, case_id=case_id
        )


def test_individual_case_budget_respects_repetitions_before_run_creation(monkeypatch):
    def unexpected_run_dir():
        pytest.fail("Insufficient budget must be rejected before creating a run")

    monkeypatch.setattr(lab, "new_run_dir", unexpected_run_dir)
    with pytest.raises(ValueError, match="exceed the explicitly approved cap"):
        lab.make_run(
            "piloto", None, "run", 2, 1, 1, 120, True, True, case_id="SL-0001"
        )


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


def test_mock_run_records_response_without_confirming_real_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "OUTPUT", tmp_path)
    manifest, directory = lab.make_run(
        "piloto", None, "run", 1, 1, 1, 120, False, False, case_id="SL-0001"
    )

    result = json.loads((directory / "results.json").read_text(encoding="utf-8"))[0]
    assert manifest["runner_calls_attempted"] == 1
    assert manifest["observed_calls"] == 1
    assert manifest["bridge_calls_attempted"] == 0
    assert manifest["bridge_results_received"] == 0
    assert manifest["responses_received"] == 1
    assert manifest["inferences_confirmed"] == 0
    assert manifest["model_invoked"] is False
    assert result["raw_output"]["provider"] == "mock"


def test_lab_error_diagnostics_allow_only_known_codes():
    error = RuntimeError("private provider message")
    error.diagnostic_category = "UNKNOWN"
    error.bridge_error_code = "CODEX_NOT_FOUND"
    assert lab.safe_error_diagnostics(error) == {
        "diagnostic_category": "UNKNOWN"
    }

    error.diagnostic_category = "CLI_UNAVAILABLE"
    assert lab.safe_error_diagnostics(error) == {
        "diagnostic_category": "CLI_UNAVAILABLE",
        "provider_error_code": "CODEX_NOT_FOUND",
    }

    error.diagnostic_category = ["PERMISSION_DENIED"]
    error.bridge_error_code = ["CODEX_NOT_FOUND"]
    assert lab.safe_error_diagnostics(error) == {"diagnostic_category": "UNKNOWN"}


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
