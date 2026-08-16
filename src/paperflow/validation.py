from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from .commands import (
    PaperflowError,
    executable,
    find_project_root,
    git,
    python_is_venv,
    run_command,
)
from .config import CONFIG_FILE, LOCAL_CONFIG_FILE, load_config

ABSOLUTE_WINDOWS_RE = re.compile(rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^<>\"]+")
ABSOLUTE_POSIX_RE = re.compile(rb"(?<![A-Za-z]):?/(Users|home|tmp|var|mnt)/[^<>\"]+")


def docx_contains_omml(path: Path) -> bool:
    with zipfile.ZipFile(path) as archive:
        try:
            document = archive.read("word/document.xml")
        except KeyError:
            return False
    return b"m:oMath" in document or b"m:oMathPara" in document


def docx_core_files_present(path: Path) -> bool:
    required = {"[Content_Types].xml", "word/document.xml", "_rels/.rels"}
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    return required.issubset(names)


def docx_contains_absolute_paths(path: Path) -> bool:
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith((".xml", ".rels")):
                continue
            content = archive.read(name)
            if ABSOLUTE_WINDOWS_RE.search(content) or ABSOLUTE_POSIX_RE.search(content):
                return True
    return False


def doctor(*, allow_missing_tools: bool = False) -> int:
    root = find_project_root()
    checks: list[tuple[str, bool, str]] = []

    checks.append(("project root", True, str(root)))
    try:
        config = load_config(root)
    except PaperflowError as exc:
        checks.append(("paperflow configuration", False, str(exc)))
        config = None
    else:
        checks.append(("paperflow configuration", True, str(root / CONFIG_FILE)))
        local = root / LOCAL_CONFIG_FILE
        checks.append(
            (
                "local configuration",
                True,
                str(local) if local.exists() else "not present (optional)",
            )
        )
        checks.append(
            (
                "manuscript source",
                config.project.manuscript.is_file(),
                str(config.project.manuscript),
            )
        )
        checks.append(
            (
                "formatting rules",
                config.project.formatting_rules.is_file(),
                str(config.project.formatting_rules),
            )
        )
        if config.word.reference_docx is not None:
            checks.append(
                (
                    "Word reference document",
                    config.word.reference_docx.is_file(),
                    str(config.word.reference_docx),
                )
            )
    checks.append(("python executable", True, sys.executable))
    checks.append(("python version", True, sys.version.split()[0]))
    checks.append(("python inside .venv", python_is_venv(root), "expected under .venv"))

    missing_tool_details = {
        "git": "missing; install manually: https://git-scm.com/downloads",
        "uv": (
            "missing; install manually before setup: "
            "https://docs.astral.sh/uv/getting-started/installation/"
        ),
        "quarto": (
            "missing; install manually: https://quarto.org/docs/download/; then use PATH "
            "or executables.quarto in .paperflow.local.yml"
        ),
    }
    for tool in ["git", "uv", "quarto"]:
        path = executable(tool, root=root)
        checks.append(
            (
                f"{tool} executable",
                path is not None,
                path or missing_tool_details[tool],
            )
        )

    git_root = git(["rev-parse", "--show-toplevel"], cwd=root, check=False)
    checks.append(("git repository", git_root.returncode == 0, git_root.stdout or git_root.stderr))

    if executable("quarto", root=root):
        quarto = run_command(["quarto", "--version"], cwd=root, check=False)
        checks.append(("quarto version", quarto.returncode == 0, quarto.stdout or quarto.stderr))
        pandoc = run_command(["quarto", "pandoc", "--version"], cwd=root, check=False)
        pandoc_output = pandoc.stdout or pandoc.stderr
        first_line = pandoc_output.splitlines()[0] if pandoc_output else ""
        checks.append(("quarto pandoc", pandoc.returncode == 0, first_line))

    for package in ["yaml"]:
        try:
            __import__(package)
        except ImportError:
            checks.append((f"python package {package}", False, "missing"))
        else:
            checks.append((f"python package {package}", True, "importable"))

    failed = [name for name, ok, _detail in checks if not ok]
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")

    if failed and not allow_missing_tools:
        print("\nBlocking checks failed:")
        for name in failed:
            print(f"- {name}")
        return 1
    return 0
