"""Pin and validate the public APIs installed by pip (no live Codex calls)."""

from __future__ import annotations

import inspect
from importlib.metadata import version
from pathlib import Path

import pytest

from portable_tempdirs import TemporaryDirectory, temporary_directory


def test_portable_tempdirs_install_and_one_shot_cleanup():
    assert version("portable-tempdirs") == "0.1.1"
    assert callable(getattr(TemporaryDirectory, "detach", None))

    with temporary_directory("SemanticDependencyContract") as path:
        root = Path(path)
        assert root.is_dir()
        (root / "probe.txt").write_text("temporary", encoding="utf-8")
        assert (root / "probe.txt").read_text(encoding="utf-8") == "temporary"

    assert not root.exists()


def test_optional_bridge_installed_version_and_public_exec_contract():
    bridge = pytest.importorskip("p4_codex_bridge")
    assert version("p4-codex-bridge") == bridge.__version__ == "1.2.0"

    params = inspect.signature(bridge.CodexBridge.run).parameters
    assert "skip_git_repo_check" in params
    assert params["ephemeral"].default is True
    assert callable(bridge.RunSecurityPolicy)
    assert bridge.SandboxMode.READ_ONLY is not None
    assert bridge.ApprovalPolicy.NEVER is not None
