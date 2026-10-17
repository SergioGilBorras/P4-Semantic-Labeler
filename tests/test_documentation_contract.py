"""Verify that maintained documentation reflects package and HTTP contracts."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from p4_semantic_labeler import __version__
from p4_semantic_labeler.interfaces.api import app

ROOT = Path(__file__).resolve().parents[1]


def test_package_metadata_and_documentation_versions_agree():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    authors = (ROOT / "AUTHORS.md").read_text(encoding="utf-8")
    assert project["name"] == "p4-semantic-labeler"
    assert project["version"] == __version__
    assert f"`{__version__}`" in readme
    assert project["authors"] == [{"name": "Sergio Gil-Borrás"}]
    assert "Sergio Gil-Borrás" in authors
    assert "P4-Codex-Bridge" in project["description"]
    assert "P4-Bridge-Codex" not in project["description"]
    assert "This repository is private" not in readme


def test_openapi_snapshot_matches_current_http_contract():
    snapshot = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    runtime = app.openapi()
    assert snapshot["info"]["version"] == runtime["info"]["version"] == __version__
    assert set(snapshot["paths"]) == set(runtime["paths"])
    for endpoint in runtime["paths"]:
        assert set(snapshot["paths"][endpoint]) == set(runtime["paths"][endpoint])
    for schema in ("LabelRequest", "Body_label_file_v1_labels_file_post"):
        actual = runtime["components"]["schemas"][schema]
        documented = snapshot["components"]["schemas"][schema]
        assert documented["required"] == actual["required"] if "required" in actual else "required" not in documented
        assert set(documented["properties"]) == set(actual["properties"])
        assert documented["properties"]["min_chars"] == actual["properties"]["min_chars"]


def test_local_markdown_links_are_valid_and_fences_closed():
    documents = sorted(
        path for path in ROOT.rglob("*.md")
        if not any(part in {".venv", ".package-venv", "build", "dist", ".git"} for part in path.parts)
    )
    assert documents
    broken = []
    fences = []
    for doc in documents:
        in_code = False
        for lineno, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            for match in re.finditer(r"!?(?:\)?\[([^]\\n]+)\]\(([^)]+)\)", line):
                link = match.group(2).split("#", 1)[0].split("?", 1)[0]
                if not link or re.match(r"^(?:https?://|mailto:)", link):
                    continue
                if not (doc.parent / link).exists():
                    broken.append(f"{doc.relative_to(ROOT)}:{lineno}: {link}")
        if in_code:
            fences.append(str(doc.relative_to(ROOT)))
    assert not broken, "Broken local links: " + ", ".join(broken)
    assert not fences, "Unclosed code fences: " + ", ".join(fences)
