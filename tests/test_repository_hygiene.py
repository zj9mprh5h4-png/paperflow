from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import unquote

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BINARY_SUFFIXES = {".doc", ".docx", ".xls", ".xlsx", ".zip", ".parquet"}


def tracked_files() -> list[Path]:
    top_level = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if Path(top_level).resolve() != ROOT.resolve():
        pytest.skip("Repository hygiene checks require Paperflow's own Git worktree.")
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode() for item in completed.stdout.split(b"\0") if item]


def test_repository_tracks_no_private_workflow_artifacts() -> None:
    relative = [path.relative_to(ROOT).as_posix() for path in tracked_files()]

    assert ".paperflow.local.yml" not in relative
    assert not any(path.startswith("reviews/round-") for path in relative)
    assert not any(path.startswith((".venv/", ".work/", ".quarto/")) for path in relative)
    assert not any(Path(path).suffix.lower() in BINARY_SUFFIXES for path in relative)
    assert max(path.stat().st_size for path in tracked_files()) < 1_000_000


def test_local_markdown_links_resolve() -> None:
    missing: list[str] = []
    for document in [path for path in tracked_files() if path.suffix.lower() == ".md"]:
        for raw_target in MARKDOWN_LINK_RE.findall(document.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_text = unquote(target.split("#", 1)[0])
            if path_text and not (document.parent / path_text).resolve().exists():
                missing.append(f"{document.relative_to(ROOT).as_posix()} -> {target}")

    assert not missing, "Missing local Markdown links:\n" + "\n".join(missing)


def test_github_yaml_files_parse() -> None:
    for document in sorted((ROOT / ".github").rglob("*.yml")):
        parsed = yaml.safe_load(document.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict), f"Expected a YAML mapping in {document.relative_to(ROOT)}"


def test_issue_forms_have_required_fields_and_unique_ids() -> None:
    issue_forms = ROOT / ".github" / "ISSUE_TEMPLATE"
    for document in sorted(issue_forms.glob("*.yml")):
        if document.name == "config.yml":
            continue
        parsed = yaml.safe_load(document.read_text(encoding="utf-8"))
        assert {"name", "description", "body"} <= parsed.keys()
        ids = [item["id"] for item in parsed["body"] if "id" in item]
        assert len(ids) == len(set(ids)), f"Duplicate field ID in {document.relative_to(ROOT)}"


def test_license_metadata_and_scope_are_consistent() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["license"] == "MIT"
    assert pyproject["project"]["license-files"] == ["LICENSE", "LICENSE-SCOPE.md"]

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License\n")
    assert "Copyright (c) 2026 Sam Bleker" in license_text
    assert (ROOT / "LICENSE-SCOPE.md").is_file()
