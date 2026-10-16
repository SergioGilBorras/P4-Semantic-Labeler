"""Contract tests: exercise the pinned P4-Codex-Bridge 1.4.1 public surface.

These use a facade double so CI never invokes paid/external Codex inference.
"""
from __future__ import annotations

import asyncio
import builtins
import inspect
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.errors import (
    ProviderFailure,
    ProviderTimeout,
    ProviderUnavailable,
)
from p4_semantic_labeler.core.models import LabelRequest, Subject
from p4_semantic_labeler.core.service import Labeler
from p4_semantic_labeler.providers import codex_bridge as codex_bridge_provider
from p4_semantic_labeler.providers.codex_diagnostics import (
    AUTHENTICATION,
    BRIDGE_EXECUTION_FAILED,
    CAPABILITY_UNAVAILABLE,
    CLI_UNAVAILABLE,
    EMPTY_RESPONSE,
    PERMISSION_DENIED,
    TIMEOUT,
    UNKNOWN,
)
from p4_semantic_labeler.temp_directories import TemporaryDirectoryError


@pytest.fixture
def fake_bridge(monkeypatch):
    module = types.ModuleType("p4_codex_bridge")
    module.__version__ = "1.4.1"
    module.SandboxMode = SimpleNamespace(READ_ONLY="read-only")
    module.ApprovalPolicy = SimpleNamespace(NEVER="never")
    module.ProjectTrust = SimpleNamespace(TRUSTED="TRUSTED")
    module.CodexPermissions = lambda sandbox, approval_policy: SimpleNamespace(
        sandbox=sandbox, approval_policy=approval_policy
    )
    module.RunSecurityPolicy = lambda **kwargs: SimpleNamespace(**kwargs)
    module.BridgeTimeoutError = type("BridgeTimeoutError", (TimeoutError,), {})
    module.AuthenticationError = type("AuthenticationError", (RuntimeError,), {})
    module.CapabilityUnavailableError = type("CapabilityUnavailableError", (RuntimeError,), {})
    module.ServiceUnavailableError = type("ServiceUnavailableError", (RuntimeError,), {})
    module.RunSecurityRejectedError = type("RunSecurityRejectedError", (RuntimeError,), {})
    calls = []
    response = SimpleNamespace(ok=True, content="Validar pedidos pendientes", error=None)

    class Bridge:
        def __init__(self, *, state_dir, allowed_roots):
            self.state_dir = Path(state_dir)
            calls.append(("constructor", self.state_dir, allowed_roots))

        def run(self, prompt, *, skip_git_repo_check=False, **kwargs):
            workspace = Path(kwargs["cwd"])
            assert self.state_dir.is_dir() and workspace.is_dir()
            assert self.state_dir != workspace
            (self.state_dir / "test-state.txt").write_text("state", encoding="utf-8")
            if skip_git_repo_check:
                # The managed workspace must be empty at the start of every call.
                assert not any(workspace.iterdir())
                (workspace / "test-output.txt").write_text("disposable", encoding="utf-8")
            kwargs["skip_git_repo_check"] = skip_git_repo_check
            calls.append(("run", prompt, kwargs))
            if isinstance(response.error, BaseException):
                raise response.error
            return response

    module.CodexBridge = Bridge
    monkeypatch.setattr("p4_semantic_labeler.providers.codex_bridge.importlib.import_module",
                        lambda name: module)
    return calls, response, module


@pytest.mark.asyncio
async def test_codex_frozen_public_interface_with_accepted_mcp_risk(fake_bridge):
    calls, response, _ = fake_bridge
    settings = Settings(provider="codex", provider_timeout_seconds=5)
    labeler = Labeler(settings=settings)
    request = LabelRequest(subject=Subject(name="process_pending_orders"),
                           context={"documentation": "Validate pending orders"},
                           max_chars=45, language="es")
    result = await labeler.agenerate(request)
    assert result.label == response.content and result.provider == "codex"
    assert [call[0] for call in calls] == ["constructor", "run"]
    state_dir = calls[0][1]
    assert state_dir.name == "bridge-state"
    assert state_dir.parent.name.startswith("20")
    assert not state_dir.exists()
    assert not state_dir.parent.exists()
    assert len(calls[0][2]) == 1
    workspace = Path(calls[0][2][0])
    assert workspace.name == "workspace"
    assert workspace.parent == state_dir.parent
    assert workspace != state_dir
    assert not workspace.exists()
    assert not (workspace / ".git").exists()
    _, prompt, kwargs = calls[1]
    assert '"documentation"' in prompt
    assert "Validate pending orders" in prompt
    assert kwargs["profile"] == "analysis"
    assert kwargs["config_policy"] == "isolated"
    assert kwargs["capture_last_message"] is True
    assert kwargs["skip_git_repo_check"] is True
    assert kwargs["permissions"].sandbox == "read-only"
    assert kwargs["permissions"].approval_policy == "never"
    policy = kwargs["security_policy"]
    assert policy.project_trust == "TRUSTED"
    assert policy.allow_external_mcps
    assert policy.allow_side_effect_mcps
    assert policy.explicit_risk_acknowledgement
    assert kwargs["timeout_seconds"] == 5


@pytest.mark.asyncio
async def test_codex_error_also_cleans_workspace_and_state(fake_bridge):
    calls, response, _ = fake_bridge
    response.error = RuntimeError("offline synthetic error")
    with pytest.raises(ProviderFailure):
        await Labeler(settings=Settings(provider="codex")).agenerate(
            LabelRequest(subject=Subject(name="error_case"))
        )
    assert [call[0] for call in calls] == ["constructor", "run"]
    state = calls[0][1]
    workspace = Path(calls[0][2][0])
    assert not workspace.exists()
    assert not state.exists()
    assert not state.parent.exists()


@pytest.mark.asyncio
async def test_concurrent_requests_use_distinct_cleaned_workspaces(fake_bridge):
    calls, _, _ = fake_bridge
    labeler = Labeler(settings=Settings(provider="codex"))
    request = LabelRequest(subject=Subject(name="parallel"))
    await asyncio.gather(labeler.agenerate(request), labeler.agenerate(request))
    states = [call[1] for call in calls if call[0] == "constructor"]
    workspaces = [Path(call[2]["cwd"]) for call in calls if call[0] == "run"]
    assert len(states) == len(workspaces) == 2
    assert states[0] != states[1]
    assert workspaces[0] != workspaces[1]
    assert all(not state.parent.exists() for state in states)
    assert all(not workspace.exists() for workspace in workspaces)


@pytest.mark.asyncio
async def test_codex_error_results_are_not_false_success(fake_bridge):
    _, response, _ = fake_bridge
    response.ok = False
    response.content = "secret provider text"
    response.error = {"code": "CODEX_PROCESS_FAILED", "message": "SECRET"}
    with pytest.raises(ProviderFailure):
        await Labeler(settings=Settings(provider="codex")).agenerate(
            LabelRequest(subject=Subject(name="example")))


@pytest.mark.asyncio
async def test_codex_timeout_result(fake_bridge):
    _, response, _ = fake_bridge
    response.ok = False
    response.error = {"code": "CODEX_TIMEOUT", "message": "SECRET"}
    with pytest.raises(ProviderTimeout):
        await Labeler(settings=Settings(provider="codex")).agenerate(
            LabelRequest(subject=Subject(name="example")))


@pytest.mark.asyncio
async def test_codex_authentication_error(fake_bridge):
    _, response, _ = fake_bridge
    response.error = RuntimeError("not authorized")
    with pytest.raises(ProviderFailure):
        await Labeler(settings=Settings(provider="codex")).agenerate(
            LabelRequest(subject=Subject(name="example")))


@pytest.mark.asyncio
async def test_codex_uses_configured_existing_workspace(fake_bridge, portable_tmp_path):
    calls, _, _ = fake_bridge
    config = Settings(provider="codex", codex_workspace=portable_tmp_path)
    await Labeler(settings=config).agenerate(LabelRequest(subject=Subject(name="example")))
    assert calls[0][0] == "constructor"
    assert calls[0][2] == [str(portable_tmp_path)]
    assert calls[0][1].name == "bridge-state"
    assert not calls[0][1].exists()
    assert not calls[0][1].parent.exists()
    assert portable_tmp_path.is_dir()
    assert portable_tmp_path not in calls[0][1].parents
    assert calls[1][2]["skip_git_repo_check"] is False


@pytest.mark.asyncio
async def test_codex_creates_fresh_bridge_and_workspace_for_each_request(fake_bridge):
    calls, _, _ = fake_bridge
    labeler = Labeler(settings=Settings(provider="codex"))
    request = LabelRequest(subject=Subject(name="example"))

    await labeler.agenerate(request)
    await labeler.agenerate(request)

    assert [call[0] for call in calls] == ["constructor", "run", "constructor", "run"]
    first_state, second_state = calls[0][1], calls[2][1]
    first_workspace = Path(calls[1][2]["cwd"])
    second_workspace = Path(calls[3][2]["cwd"])
    assert first_state != second_state
    assert first_workspace != second_workspace
    assert not first_workspace.exists() and not second_workspace.exists()
    assert not first_state.exists() and not second_state.exists()
    assert not first_state.parent.exists() and not second_state.parent.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception_name", "public_error", "category"),
    [
        ("AuthenticationError", ProviderUnavailable, AUTHENTICATION),
        ("CapabilityUnavailableError", ProviderUnavailable, CAPABILITY_UNAVAILABLE),
        ("ServiceUnavailableError", ProviderUnavailable, BRIDGE_EXECUTION_FAILED),
        ("RunSecurityRejectedError", ProviderUnavailable, PERMISSION_DENIED),
        ("BridgeTimeoutError", ProviderTimeout, TIMEOUT),
        ("PermissionError", ProviderFailure, PERMISSION_DENIED),
        ("FileNotFoundError", ProviderFailure, CLI_UNAVAILABLE),
        ("RuntimeError", ProviderFailure, UNKNOWN),
    ],
)
async def test_codex_exception_diagnostics_are_categorized_without_text_leak(
    fake_bridge, exception_name, public_error, category
):
    _, response, module = fake_bridge
    exception_type = getattr(module, exception_name, None) or getattr(builtins, exception_name)
    response.error = exception_type("PRIVATE_SECRET detail")
    labeler = Labeler(settings=Settings(provider="codex"))

    with pytest.raises(public_error) as raised:
        await labeler.agenerate(LabelRequest(subject=Subject(name="example")))

    assert raised.value.diagnostic_category == category
    assert "PRIVATE_SECRET" not in str(raised.value)
    assert labeler.provider.telemetry_snapshot() == {
        "bridge_calls_attempted": 1,
        "bridge_results_received": 0,
        "provider_responses_received": 0,
        "inferences_confirmed": 0,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "category", "public_error"),
    [
        ("CODEX_AUTH_REQUIRED", AUTHENTICATION, ProviderUnavailable),
        ("CODEX_NOT_FOUND", CLI_UNAVAILABLE, ProviderUnavailable),
        ("CODEX_TIMEOUT", TIMEOUT, ProviderTimeout),
        ("CODEX_EXIT_NONZERO", BRIDGE_EXECUTION_FAILED, ProviderFailure),
        ("CODEX_EMPTY_RESPONSE", EMPTY_RESPONSE, ProviderFailure),
        ("OUTPUT_LAST_MESSAGE_MISSING", BRIDGE_EXECUTION_FAILED, ProviderFailure),
        ("UNRECOGNIZED_PRIVATE_CODE", UNKNOWN, ProviderFailure),
    ],
)
async def test_codex_structured_result_error_uses_allowlisted_code_only(
    fake_bridge, code, category, public_error
):
    _, response, _ = fake_bridge
    response.ok = False
    response.content = ""
    response.error = {"code": code, "message": "PRIVATE_SECRET provider detail"}
    labeler = Labeler(settings=Settings(provider="codex"))

    with pytest.raises(public_error) as raised:
        await labeler.agenerate(LabelRequest(subject=Subject(name="example")))

    assert raised.value.diagnostic_category == category
    assert raised.value.bridge_result_received is True
    assert "PRIVATE_SECRET" not in str(raised.value)
    if code == "UNRECOGNIZED_PRIVATE_CODE":
        assert not hasattr(raised.value, "bridge_error_code")
    else:
        assert raised.value.bridge_error_code == code
    assert labeler.provider.telemetry_snapshot() == {
        "bridge_calls_attempted": 1,
        "bridge_results_received": 1,
        "provider_responses_received": 0,
        "inferences_confirmed": 0,
    }


@pytest.mark.asyncio
async def test_codex_empty_response_is_distinct_from_execution_failure(fake_bridge):
    _, response, _ = fake_bridge
    response.content = "  "
    labeler = Labeler(settings=Settings(provider="codex"))

    with pytest.raises(ProviderFailure) as raised:
        await labeler.agenerate(LabelRequest(subject=Subject(name="example")))

    assert raised.value.diagnostic_category == EMPTY_RESPONSE
    assert raised.value.bridge_result_received is True
    assert labeler.provider.telemetry_snapshot() == {
        "bridge_calls_attempted": 1,
        "bridge_results_received": 1,
        "provider_responses_received": 0,
        "inferences_confirmed": 0,
    }


@pytest.mark.asyncio
async def test_codex_success_confirms_response_and_inference(fake_bridge):
    _, _, _ = fake_bridge
    labeler = Labeler(settings=Settings(provider="codex"))

    result = await labeler.agenerate(LabelRequest(subject=Subject(name="example")))

    assert result.provider == "codex"
    assert labeler.provider.telemetry_snapshot() == {
        "bridge_calls_attempted": 1,
        "bridge_results_received": 1,
        "provider_responses_received": 1,
        "inferences_confirmed": 1,
    }


@pytest.mark.asyncio
async def test_temp_workspace_permission_diagnostic_has_no_bridge_attempt(
    fake_bridge, monkeypatch
):
    from p4_semantic_labeler import temp_directories
    from portable_tempdirs import TemporaryDirectoryError as PortableError

    def deny_portable(_namespace):
        raise PortableError("secret path", code="PERMISSION_DENIED")

    monkeypatch.setattr(temp_directories, "temporary_directory", deny_portable)
    labeler = Labeler(settings=Settings(provider="codex"))

    with pytest.raises(ProviderFailure) as raised:
        await labeler.agenerate(LabelRequest(subject=Subject(name="example")))

    assert raised.value.diagnostic_category == PERMISSION_DENIED
    assert labeler.provider.telemetry_snapshot() == {
        "bridge_calls_attempted": 0,
        "bridge_results_received": 0,
        "provider_responses_received": 0,
        "inferences_confirmed": 0,
    }


@pytest.mark.asyncio
async def test_temp_bridge_state_permission_diagnostic_has_no_bridge_attempt(
    fake_bridge, monkeypatch
):
    def deny_state(_parent, _name):
        raise TemporaryDirectoryError(
            "PermissionError while creating bridge state", permission_denied=True
        )

    monkeypatch.setattr(codex_bridge_provider, "create_run_subdirectory", deny_state)
    labeler = Labeler(settings=Settings(provider="codex"))

    with pytest.raises(ProviderFailure) as raised:
        await labeler.agenerate(LabelRequest(subject=Subject(name="example")))

    assert raised.value.diagnostic_category == PERMISSION_DENIED
    assert labeler.provider.telemetry_snapshot() == {
        "bridge_calls_attempted": 0,
        "bridge_results_received": 0,
        "provider_responses_received": 0,
        "inferences_confirmed": 0,
    }


@pytest.mark.asyncio
async def test_old_bridge_version_is_rejected_as_capability_unavailable(fake_bridge):
    calls, _, module = fake_bridge
    module.__version__ = "1.0.0"
    labeler = Labeler(settings=Settings(provider="codex"))

    with pytest.raises(ProviderUnavailable) as raised:
        await labeler.agenerate(LabelRequest(subject=Subject(name="example")))

    assert raised.value.diagnostic_category == CAPABILITY_UNAVAILABLE
    assert "1.0.0" not in str(raised.value)
    assert calls == []
    assert labeler.provider.telemetry_snapshot() == {
        "bridge_calls_attempted": 0,
        "bridge_results_received": 0,
        "provider_responses_received": 0,
        "inferences_confirmed": 0,
    }


@pytest.mark.asyncio
async def test_bridge_1_1_is_rejected_before_ephemeral_call(fake_bridge):
    calls, _, module = fake_bridge
    module.__version__ = "1.1.0"
    labeler = Labeler(settings=Settings(provider="codex"))

    with pytest.raises(ProviderUnavailable) as raised:
        await labeler.agenerate(LabelRequest(subject=Subject(name="example")))

    assert raised.value.diagnostic_category == CAPABILITY_UNAVAILABLE
    assert calls == []
    assert labeler.provider.telemetry_snapshot()["bridge_calls_attempted"] == 0


def test_installed_bridge_api_supports_skip_git_repo_check():
    bridge = pytest.importorskip("p4_codex_bridge")
    assert codex_bridge_provider.CodexBridgeProvider._bridge_supports_managed_workspace(bridge)
    assert "skip_git_repo_check" in inspect.signature(bridge.CodexBridge.run).parameters
    assert inspect.signature(bridge.CodexBridge.run).parameters["ephemeral"].default is True


@pytest.mark.asyncio
async def test_mock_provider_does_not_import_codex_bridge(monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "p4_codex_bridge":
            raise AssertionError("mock provider attempted to import Codex Bridge")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(
        codex_bridge_provider.importlib, "import_module", guarded_import
    )
    result = await Labeler(settings=Settings(provider="mock")).agenerate(
        LabelRequest(subject=Subject(name="pending_orders"))
    )

    assert result.provider == "mock"
