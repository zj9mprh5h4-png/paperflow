from __future__ import annotations

import json
import re
import sys
import zipfile
from dataclasses import dataclass
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


@dataclass(frozen=True)
class DoctorCheck:
    id: str
    label: str
    ok: bool
    detail: str
    remediation: tuple[str, ...] = ()
    error_code: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "status": "ok" if self.ok else "fail",
            "detail": self.detail,
            "error_code": self.error_code,
            "remediation": list(self.remediation),
        }


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


def docx_reference_status(path: Path) -> tuple[bool, bool]:
    """Return whether a reference file is a DOCX and free of absolute local paths."""
    try:
        valid = docx_core_files_present(path)
        path_safe = valid and not docx_contains_absolute_paths(path)
    except (OSError, zipfile.BadZipFile):
        return False, False
    return valid, path_safe


def docx_revision_counts(path: Path) -> tuple[int, int]:
    """Return tracked insertion and deletion element counts from the main Word document."""
    with zipfile.ZipFile(path) as archive:
        document = archive.read("word/document.xml")
    insertions = len(re.findall(rb"<w:ins(?:\s|>)", document))
    deletions = len(re.findall(rb"<w:del(?:\s|>)", document))
    return insertions, deletions


def doctor(*, allow_missing_tools: bool = False, output_format: str = "text") -> int:
    root = find_project_root()
    checks: list[DoctorCheck] = []

    checks.append(DoctorCheck("project.root", "project root", True, str(root)))
    config_path = root / CONFIG_FILE
    config_file_exists = config_path.is_file()
    checks.append(
        DoctorCheck(
            "configuration.file",
            "paperflow configuration file",
            config_file_exists,
            str(config_path),
            ()
            if config_file_exists
            else (
                "Restore paperflow.yml from the Paperflow template, or create it with "
                "schema_version: 1 and the project settings documented in "
                "docs/configuration.md.",
            ),
        )
    )
    try:
        config = load_config(root)
    except PaperflowError as exc:
        remediation = exc.remediation or (
            "Correct paperflow.yml or .paperflow.local.yml using docs/configuration.md.",
            "Rerun uv run paperflow doctor --format json after the correction.",
        )
        checks.append(
            DoctorCheck(
                "configuration",
                "paperflow configuration",
                False,
                str(exc),
                remediation,
                error_code=exc.code,
            )
        )
        config = None
    else:
        checks.append(
            DoctorCheck(
                "configuration",
                "paperflow configuration",
                True,
                str(config_path),
            )
        )
        local = root / LOCAL_CONFIG_FILE
        checks.append(
            DoctorCheck(
                "configuration.local",
                "local configuration",
                True,
                str(local) if local.exists() else "not present (optional)",
            )
        )
        manuscript_exists = config.project.manuscript.is_file()
        checks.append(
            DoctorCheck(
                "source.manuscript",
                "manuscript source",
                manuscript_exists,
                str(config.project.manuscript),
                ()
                if manuscript_exists
                else (
                    "Create the configured manuscript file, or update project.manuscript "
                    "in paperflow.yml to the correct project-relative QMD path.",
                ),
            )
        )
        formatting_rules_exist = config.project.formatting_rules.is_file()
        checks.append(
            DoctorCheck(
                "source.formatting_rules",
                "formatting rules",
                formatting_rules_exist,
                str(config.project.formatting_rules),
                ()
                if formatting_rules_exist
                else (
                    "Create the configured formatting-rules Markdown file, or update "
                    "project.formatting_rules in paperflow.yml.",
                ),
            )
        )
        if config.word.reference_docx is not None:
            reference_exists = config.word.reference_docx.is_file()
            checks.append(
                DoctorCheck(
                    "word.reference",
                    "Word reference document",
                    reference_exists,
                    str(config.word.reference_docx),
                    ()
                    if reference_exists
                    else (
                        "Correct word.reference_docx in .paperflow.local.yml, copy the intended "
                        "DOCX to that path, or set the value to null to use Quarto's default.",
                    ),
                )
            )
            if reference_exists:
                valid_reference, safe_reference = docx_reference_status(
                    config.word.reference_docx
                )
                checks.append(
                    DoctorCheck(
                        "word.reference.structure",
                        "Word reference DOCX structure",
                        valid_reference,
                        "valid" if valid_reference else "invalid or unreadable DOCX",
                        ()
                        if valid_reference
                        else (
                            "Replace the file with a valid Word DOCX and rerun Doctor.",
                            "Follow docs/word-template.md before using a publisher template.",
                        ),
                    )
                )
                if valid_reference:
                    checks.append(
                        DoctorCheck(
                            "word.reference.paths",
                            "Word reference local paths",
                            safe_reference,
                            "none found"
                            if safe_reference
                            else "absolute local path found; use a sanitized template",
                            ()
                            if safe_reference
                            else (
                                "Sanitize a copy of the DOCX to remove embedded absolute paths.",
                                "Keep the original private template outside version control and "
                                "follow docs/word-template.md.",
                            ),
                        )
                    )
    checks.append(DoctorCheck("python.executable", "python executable", True, sys.executable))
    checks.append(
        DoctorCheck("python.version", "python version", True, sys.version.split()[0])
    )
    inside_venv = python_is_venv(root)
    checks.append(
        DoctorCheck(
            "python.venv",
            "python inside .venv",
            inside_venv,
            "expected under .venv",
            ()
            if inside_venv
            else (
                "Run uv sync --frozen --extra dev from the project root.",
                "Invoke Paperflow with uv run rather than a system Python interpreter.",
            ),
        )
    )

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
    missing_tool_remediation = {
        "git": ("Install Git from https://git-scm.com/downloads and restart the terminal.",),
        "uv": (
            "Install uv from https://docs.astral.sh/uv/getting-started/installation/ "
            "and restart the terminal.",
        ),
        "quarto": (
            "Install Quarto from https://quarto.org/docs/download/ and restart the terminal.",
            "If Quarto is installed outside PATH, set executables.quarto in "
            ".paperflow.local.yml.",
        ),
    }
    for tool in ["git", "uv", "quarto"]:
        path = executable(tool, root=root)
        checks.append(
            DoctorCheck(
                f"tool.{tool}",
                f"{tool} executable",
                path is not None,
                path or missing_tool_details[tool],
                () if path is not None else missing_tool_remediation[tool],
            )
        )

    git_root = git(["rev-parse", "--show-toplevel"], cwd=root, check=False)
    git_ok = git_root.returncode == 0
    checks.append(
        DoctorCheck(
            "repository.git",
            "git repository",
            git_ok,
            git_root.stdout or git_root.stderr,
            ()
            if git_ok
            else (
                "Clone the repository with Git, or initialize Git in the project root before "
                "starting a Word review round.",
            ),
        )
    )

    if executable("quarto", root=root):
        quarto = run_command(["quarto", "--version"], cwd=root, check=False)
        quarto_ok = quarto.returncode == 0
        checks.append(
            DoctorCheck(
                "tool.quarto.version",
                "quarto version",
                quarto_ok,
                quarto.stdout or quarto.stderr,
                ()
                if quarto_ok
                else (
                    "Run quarto --version directly, then repair or reinstall Quarto.",
                    "Update executables.quarto in .paperflow.local.yml if it points "
                    "to an old file.",
                ),
            )
        )
        pandoc = run_command(["quarto", "pandoc", "--version"], cwd=root, check=False)
        pandoc_output = pandoc.stdout or pandoc.stderr
        first_line = pandoc_output.splitlines()[0] if pandoc_output else ""
        pandoc_ok = pandoc.returncode == 0
        checks.append(
            DoctorCheck(
                "tool.pandoc.version",
                "quarto pandoc",
                pandoc_ok,
                first_line,
                ()
                if pandoc_ok
                else (
                    "Repair or reinstall Quarto; Paperflow uses the Pandoc bundled with Quarto.",
                    "Do not add a separate Pandoc project dependency.",
                ),
            )
        )

    for package in ["yaml"]:
        try:
            __import__(package)
        except ImportError:
            checks.append(
                DoctorCheck(
                    f"package.{package}",
                    f"python package {package}",
                    False,
                    "missing",
                    (
                        "Run uv sync --frozen --extra dev from the project root.",
                        "Do not install packages with ad-hoc pip commands.",
                    ),
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    f"package.{package}",
                    f"python package {package}",
                    True,
                    "importable",
                )
            )

    failed = [check for check in checks if not check.ok]
    if output_format == "json":
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "ok": not failed,
                    "checks": [check.as_dict() for check in checks],
                },
                indent=2,
            )
        )
    else:
        for check in checks:
            status = "OK" if check.ok else "FAIL"
            print(f"[{status}] {check.label}: {check.detail}")
            for step in check.remediation:
                print(f"  Fix: {step}")

        if failed and not allow_missing_tools:
            print("\nBlocking checks failed:")
            for check in failed:
                print(f"- {check.label}")

    if failed and not allow_missing_tools:
        return 1
    return 0
