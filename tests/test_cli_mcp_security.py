from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from p4_semantic_labeler.config import Settings
from p4_semantic_labeler.core.errors import InputLimitError, RequestValueError
from p4_semantic_labeler.core.file_utils import decode_text, read_authorized_file
from p4_semantic_labeler.core.service import Labeler
from p4_semantic_labeler.interfaces.mcp_tools import MCPTools


def run_cli(*args, input=None):
    env = dict(os.environ, P4_LABELER_PROVIDER="mock")
    return subprocess.run(
        [sys.executable, "-m", "p4_semantic_labeler.interfaces.cli", *args],
        env=env, text=True, input=input, capture_output=True, check=False,
    )


def test_cli_label_file_json(portable_tmp_path):
    filename = portable_tmp_path / "demo.py"
    filename.write_text("def get_users():\n  return []\n", encoding="utf-8")
    result = run_cli("label", "--name", "get_users", "--kind", "function",
                     "--file", str(filename), "--max-chars", "20", "--json")
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["label"] == "get users"
    assert parsed["char_count"] == 9


def test_cli_short_label_below_soft_minimum_succeeds_without_padding():
    response = run_cli(
        "label", "--name", "calculate_median", "--kind", "function",
        "--min-chars", "25", "--max-chars", "30", "--json",
    )
    assert response.returncode == 0, response.stderr
    result = json.loads(response.stdout)
    assert result["label"] == "calculate median"
    assert "below_preferred_min_chars" in result["warnings"]


def test_cli_stdin_and_batch():
    result = run_cli("label", "--name", "has_access", "--stdin", input="Access is denied")
    assert result.returncode == 0 and result.stdout.strip() == "has access"
    batch = '\n'.join([
        '{"subject":{"name":"one_item"}}',
        '{"subject":{"name":"second_item"}}'])
    result = run_cli("batch", input=batch)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 2
    assert json.loads(result.stdout.splitlines()[1])["index"] == 1


def test_cli_bad_input_no_secret_leak():
    result = run_cli("label", "--name", "x", "--documentation", "SECRET",
                     "--max-chars", "9999")
    assert result.returncode == 2
    assert "SECRET" not in result.stderr


def test_file_security_multiplatform(portable_tmp_path):
    allowed = portable_tmp_path / "allowed"
    denied = portable_tmp_path / "denied"
    allowed.mkdir()
    denied.mkdir()
    filename = allowed / "safe.md"
    filename.write_text("safe", encoding="utf-8")
    forbidden = denied / "secret.md"
    forbidden.write_text("confidential", encoding="utf-8")
    settings = Settings(provider="mock", mcp_roots=(allowed,))
    assert read_authorized_file(str(filename), settings)[1] == "safe"
    with pytest.raises(RequestValueError):
        read_authorized_file(str(forbidden), settings)
    with pytest.raises(RequestValueError):
        decode_text(b"xx", "file.exe", settings)
    with pytest.raises(RequestValueError):
        decode_text(b"hello\x00bye", "file.txt", settings)
    with pytest.raises(InputLimitError):
        decode_text(b"a" * (settings.max_file_bytes + 1), "huge.txt", settings)


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="La prueba de symlinks se ejecuta exclusivamente en Linux",
)
def test_file_security_rejects_symlink_to_external_file(portable_tmp_path):
    allowed = portable_tmp_path / "allowed"
    denied = portable_tmp_path / "denied"
    allowed.mkdir()
    denied.mkdir()
    forbidden = denied / "secret.md"
    forbidden.write_text("confidential", encoding="utf-8")
    link = allowed / "link.md"
    link.symlink_to(forbidden)
    settings = Settings(provider="mock", mcp_roots=(allowed,))

    with pytest.raises(RequestValueError):
        read_authorized_file(str(link), settings)


@pytest.mark.asyncio
async def test_mcp_handler_tools_and_roots(settings, portable_tmp_path):
    f = portable_tmp_path / "doc.txt"
    f.write_text("Documentation example", encoding="utf-8")
    cfg = Settings(provider="mock", mcp_roots=(portable_tmp_path,))
    handler = MCPTools(Labeler(settings=cfg), cfg)
    for result in (
        await handler.generate_label("foo_bar"),
        await handler.generate_summary("architecture", text="Architecture overview"),
        await handler.summarize_file(str(f), name="document"),
    ):
        assert result["char_count"] == len(result["label"])
    short = await handler.generate_label("short", min_chars=20, max_chars=35)
    assert short["label"] == "short"
    assert "below_preferred_min_chars" in short["warnings"]
    short_summary = await handler.generate_summary(
        "brief_note", text="Short summary", min_chars=25, max_chars=35
    )
    assert short_summary["label"] == "brief note"
    assert "below_preferred_min_chars" in short_summary["warnings"]
    batch = await handler.generate_labels_batch([{"subject": {"name": "alpha_beta"}}])
    assert batch["success_count"] == 1
    with pytest.raises(RequestValueError):
        await MCPTools(Labeler(settings=settings), settings).summarize_file(str(f))


@pytest.mark.asyncio
async def test_official_mcp_registration_if_installed(settings):
    pytest.importorskip("mcp.server.mcpserver")
    from p4_semantic_labeler.interfaces.mcp_server import create_mcp_server

    app = create_mcp_server(settings)
    names = [tool.name for tool in await app.list_tools()]
    assert set(names) == {"generate_label", "generate_summary", "generate_labels_batch", "summarize_file"}


def test_mcp_missing_file_sanitized(portable_tmp_path):
    settings = Settings(provider="mock", mcp_roots=(portable_tmp_path,))
    with pytest.raises(RequestValueError):
        read_authorized_file(str(portable_tmp_path / "no-file.txt"), settings)
