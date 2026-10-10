"""P4-Codex-Bridge 1.x adapter using its documented public Python API.

Only this module imports the bridge. One-shot inference uses a read-only Codex
workspace; received code/text is passed as prompt data and is never written or
executed by the labeler. Codex may inherit external MCP tools, whose effects
are outside the filesystem sandbox (see SECURITY.md).
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import re
import threading
from pathlib import Path
from typing import Any

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.errors import ProviderFailure, ProviderTimeout, ProviderUnavailable
from p4_semantic_labeler.core.prompt_builder import read_prompt
from p4_semantic_labeler.providers.codex_diagnostics import (
    AUTHENTICATION,
    BRIDGE_EXECUTION_FAILED,
    CAPABILITY_UNAVAILABLE,
    CLI_UNAVAILABLE,
    DIAGNOSTIC_CATEGORIES,
    EMPTY_RESPONSE,
    PERMISSION_DENIED,
    STRUCTURED_ERROR_CATEGORIES,
    TIMEOUT,
    UNKNOWN,
    category_for_structured_code,
)
from p4_semantic_labeler.temp_directories import (
    TemporaryDirectoryError,
    create_run_subdirectory,
    managed_run_directory,
)
from p4_semantic_labeler.providers.base import ProviderPrompt, ProviderResponse


class CodexBridgeProvider:
    name = "codex"
    MINIMUM_BRIDGE_VERSION = (1, 1, 0)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._telemetry_lock = threading.Lock()
        self._telemetry = {
            "bridge_calls_attempted": 0,
            "bridge_results_received": 0,
            "provider_responses_received": 0,
            "inferences_confirmed": 0,
        }

    def telemetry_snapshot(self) -> dict[str, int]:
        """Return aggregate counts without prompts, paths, stderr, or error text."""
        with self._telemetry_lock:
            return dict(self._telemetry)

    def _record_telemetry(self, **increments: int) -> None:
        with self._telemetry_lock:
            for key, value in increments.items():
                self._telemetry[key] += value

    @staticmethod
    def _bridge_exception_type(module: Any, name: str) -> type[BaseException] | None:
        candidate = getattr(module, name, None)
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            return candidate
        return None

    @classmethod
    def _exception_diagnostic(
        cls, exc: Exception, module: Any, *, cli_failure: bool = False
    ) -> tuple[type, str]:
        if isinstance(exc, TimeoutError):
            return ProviderTimeout, TIMEOUT
        if isinstance(exc, PermissionError):
            return ProviderFailure, PERMISSION_DENIED
        if isinstance(exc, FileNotFoundError):
            return ProviderFailure, CLI_UNAVAILABLE if cli_failure else UNKNOWN

        if getattr(exc, "permission_denied", False):
            return ProviderFailure, PERMISSION_DENIED

        exception_categories = (
            ("AuthenticationError", ProviderUnavailable, AUTHENTICATION),
            ("CapabilityUnavailableError", ProviderUnavailable, CAPABILITY_UNAVAILABLE),
            ("ServiceUnavailableError", ProviderUnavailable, BRIDGE_EXECUTION_FAILED),
            ("RunSecurityRejectedError", ProviderUnavailable, PERMISSION_DENIED),
        )
        for exception_name, public_error, category in exception_categories:
            exception_type = cls._bridge_exception_type(module, exception_name)
            if exception_type is not None and isinstance(exc, exception_type):
                return public_error, category
        return ProviderFailure, UNKNOWN

    @staticmethod
    def _annotate_error(
        error_type: type,
        category: str,
        *,
        bridge_result_received: bool = False,
        provider_response_received: bool = False,
        bridge_error_code: str | None = None,
    ) -> Exception:
        error = error_type()
        error.diagnostic_category = (
            category if category in DIAGNOSTIC_CATEGORIES else UNKNOWN
        )
        error.bridge_result_received = bridge_result_received
        error.provider_response_received = provider_response_received
        error.inference_confirmed = False
        if (
            isinstance(bridge_error_code, str)
            and bridge_error_code in STRUCTURED_ERROR_CATEGORIES
        ):
            error.bridge_error_code = bridge_error_code
        return error

    @classmethod
    def _structured_result_error(cls, result: Any) -> Exception:
        error_data = getattr(result, "error", None)
        code = error_data.get("code") if isinstance(error_data, dict) else None
        category = category_for_structured_code(code)
        if category == TIMEOUT:
            error_type: type = ProviderTimeout
        elif category in {AUTHENTICATION, CLI_UNAVAILABLE, CAPABILITY_UNAVAILABLE}:
            error_type = ProviderUnavailable
        else:
            error_type = ProviderFailure
        return cls._annotate_error(
            error_type,
            category,
            bridge_result_received=True,
            provider_response_received=bool(
                isinstance(getattr(result, "content", None), str)
                and getattr(result, "content", "").strip()
            ),
            bridge_error_code=code if isinstance(code, str) else None,
        )

    def _new_bridge(self, module: Any, run_directory: Path) -> tuple[Any, Path]:
        """Create one new CodexBridge and distinct workspace/state per request."""
        if self.settings.codex_workspace is None:
            workspace = create_run_subdirectory(run_directory, "workspace")
        else:
            # Caller owns external data; it must not be deleted by this adapter.
            workspace = self.settings.codex_workspace
        state_dir = create_run_subdirectory(run_directory, "bridge-state")
        bridge = module.CodexBridge(
            state_dir=state_dir,
            allowed_roots=[str(workspace)],
        )
        return bridge, workspace

    @classmethod
    def _bridge_supports_managed_workspace(cls, module: Any) -> bool:
        version = getattr(module, "__version__", None)
        if not isinstance(version, str):
            return False
        match = re.match(
            r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?(?:\.post(\d+))?(?:\+[-a-zA-Z0-9.]+)?$",
            version,
        )
        if match is None:
            return False
        installed = tuple(int(part) for part in match.group(1, 2, 3))
        prerelease = match.group(4) is not None
        if installed < cls.MINIMUM_BRIDGE_VERSION or (
            installed == cls.MINIMUM_BRIDGE_VERSION and prerelease
        ):
            return False
        try:
            parameters = inspect.signature(module.CodexBridge.run).parameters
        except (AttributeError, TypeError, ValueError):
            return False
        return "skip_git_repo_check" in parameters

    def _generate_sync(self, prompt: ProviderPrompt) -> ProviderResponse:
        try:
            module = importlib.import_module("p4_codex_bridge")
        except ImportError as exc:
            raise self._annotate_error(ProviderUnavailable, UNKNOWN) from exc

        if not self._bridge_supports_managed_workspace(module):
            raise self._annotate_error(
                ProviderUnavailable,
                CAPABILITY_UNAVAILABLE,
            ) from None

        try:
            with managed_run_directory() as run_directory:
                return self._generate_in_run(module, prompt, run_directory)
        except TemporaryDirectoryError as exc:
            public_error, category = self._exception_diagnostic(exc, module)
            raise self._annotate_error(public_error, category) from exc

    def _generate_in_run(
        self, module: Any, prompt: ProviderPrompt, run_directory: Path
    ) -> ProviderResponse:
        """Run a fresh one-shot Codex session inside one owned temporary root."""
        skip_git_repo_check = self.settings.codex_workspace is None

        try:
            bridge, workspace = self._new_bridge(module, run_directory)
            permissions = module.CodexPermissions(
                module.SandboxMode.READ_ONLY, module.ApprovalPolicy.NEVER
            )
            # The bridge cannot guarantee per-run isolation of inherited MCPs.
            # This project intentionally acknowledges that risk for Codex mode;
            # it never assumes read-only filesystem permissions restrict MCPs.
            policy = module.RunSecurityPolicy(
                project_trust=module.ProjectTrust.TRUSTED,
                allow_external_mcps=True,
                allow_side_effect_mcps=True,
                explicit_risk_acknowledgement=True,
                policy_id="p4-semantic-labeler-codex",
            )
            combined_prompt = prompt.system + "\n\n" + read_prompt("codex_data_delimiter.txt") + "\n" + prompt.user
        except Exception as exc:
            public_error, category = self._exception_diagnostic(exc, module)
            raise self._annotate_error(public_error, category) from exc

        self._record_telemetry(bridge_calls_attempted=1)
        try:
            result = bridge.run(
                combined_prompt,
                cwd=workspace,
                profile="analysis",
                timeout_seconds=self.settings.provider_timeout_seconds,
                permissions=permissions,
                config_policy="isolated",
                capture_last_message=True,
                security_policy=policy,
                skip_git_repo_check=skip_git_repo_check,
            )
        except Exception as exc:
            public_error, category = self._exception_diagnostic(
                exc, module, cli_failure=True
            )
            raise self._annotate_error(public_error, category) from exc

        self._record_telemetry(bridge_results_received=1)
        try:
            content = result.content
            has_response = isinstance(content, str) and bool(content.strip())
            if has_response:
                self._record_telemetry(provider_responses_received=1)
            if not result.ok:
                raise self._structured_result_error(result)
            if not has_response:
                raise self._annotate_error(
                    ProviderFailure,
                    EMPTY_RESPONSE,
                    bridge_result_received=True,
                )
            self._record_telemetry(inferences_confirmed=1)
            return ProviderResponse(text=content)
        except (ProviderFailure, ProviderTimeout, ProviderUnavailable):
            raise
        except Exception as exc:
            raise self._annotate_error(
                ProviderFailure,
                UNKNOWN,
                bridge_result_received=True,
                provider_response_received=bool(
                    isinstance(locals().get("content"), str)
                    and locals()["content"].strip()
                ),
            ) from exc

    async def generate(self, prompt: ProviderPrompt) -> ProviderResponse:
        # CodexBridge.run is a synchronous, blocking public API.
        return await asyncio.to_thread(self._generate_sync, prompt)
