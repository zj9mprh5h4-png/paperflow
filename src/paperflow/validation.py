from __future__ import annotations

import difflib
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
    relpath,
    run_command,
)
from .config import CONFIG_FILE, LOCAL_CONFIG_FILE, PaperflowConfig, load_config
from .sources import custom_style_requests, rendered_sources

ABSOLUTE_WINDOWS_RE = re.compile(rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^<>\"]+")
ABSOLUTE_POSIX_RE = re.compile(rb"(?<![A-Za-z]):?/(Users|home|tmp|var|mnt)/[^<>\"]+")

# Markers that explain why a DOCX part carries an absolute path, most specific first.
ABSOLUTE_PATH_KINDS: tuple[tuple[bytes, str], ...] = (
    (b"attachedTemplate", "attached document template"),
    (b"HyperlinkBase", "hyperlink base"),
    (b"subDoc", "subdocument link"),
    (b'TargetMode="External"', "external relationship"),
)
# Human-readable image metadata. Word stores the original file path here when a picture
# is inserted, which is invisible in the document body but travels with every copy.
ALT_TEXT_ATTRIBUTE_RE = re.compile(rb'(?:descr|alt|title)="[^"]*"')


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


def absolute_path_matches(content: bytes) -> list[int]:
    """Return the start offset of every absolute local path in an XML part."""
    return sorted(
        match.start()
        for pattern in (ABSOLUTE_WINDOWS_RE, ABSOLUTE_POSIX_RE)
        for match in pattern.finditer(content)
    )


def _absolute_path_kind(
    content: bytes,
    start: int,
    alt_text_spans: list[tuple[int, int]],
) -> str:
    if any(begin <= start < end for begin, end in alt_text_spans):
        return "image alt text"
    for marker, label in ABSOLUTE_PATH_KINDS:
        if marker in content:
            return label
    return "embedded path"


def docx_absolute_path_locations(path: Path) -> tuple[str, ...]:
    """Name the DOCX parts that carry an absolute local path, and what kind it is.

    The path itself is deliberately not reported. It normally contains the account
    name of whoever produced the template, and Doctor output is meant to stay safe
    to paste into an issue. The part and the kind are enough to repair the file.
    """
    locations: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith((".xml", ".rels")):
                continue
            content = archive.read(name)
            starts = absolute_path_matches(content)
            if not starts:
                continue
            alt_text_spans = [
                (match.start(), match.end())
                for match in ALT_TEXT_ATTRIBUTE_RE.finditer(content)
            ]
            kinds = dict.fromkeys(
                _absolute_path_kind(content, start, alt_text_spans) for start in starts
            )
            locations.extend(f"{name} ({kind})" for kind in kinds)
    return tuple(locations)


@dataclass(frozen=True)
class ReferenceDocxStatus:
    valid: bool
    path_safe: bool
    absolute_paths: tuple[str, ...] = ()


def docx_reference_status(path: Path) -> ReferenceDocxStatus:
    """Report whether a reference file is a DOCX and free of absolute local paths."""
    try:
        valid = docx_core_files_present(path)
        locations = docx_absolute_path_locations(path) if valid else ()
    except (OSError, zipfile.BadZipFile):
        return ReferenceDocxStatus(valid=False, path_safe=False)
    return ReferenceDocxStatus(
        valid=valid,
        path_safe=valid and not locations,
        absolute_paths=locations,
    )


def docx_revision_counts(path: Path) -> tuple[int, int]:
    """Return tracked insertion and deletion element counts from the main Word document."""
    with zipfile.ZipFile(path) as archive:
        document = archive.read("word/document.xml")
    insertions = len(re.findall(rb"<w:ins(?:\s|>)", document))
    deletions = len(re.findall(rb"<w:del(?:\s|>)", document))
    return insertions, deletions


def _custom_style_check(config: PaperflowConfig) -> DoctorCheck:
    """Verify that every Word style the manuscript requests exists in the reference.

    A misspelled name renders as unstyled text without any warning, and swapping the
    reference for another publisher's template breaks every mapping just as quietly.
    """
    from .template import reference_docx_styles

    reference = config.word.reference_docx
    assert reference is not None
    try:
        available = {style.name for style in reference_docx_styles(reference)}
    except PaperflowError as exc:
        return DoctorCheck(
            "word.custom_styles",
            "manuscript styles in reference",
            False,
            str(exc),
            exc.remediation,
            error_code=exc.code,
        )

    requests = custom_style_requests(rendered_sources(config.project.manuscript))
    missing = [request for request in requests if request.name not in available]
    if not missing:
        detail = (
            f"{len({request.name for request in requests})} requested style(s) exist"
            if requests
            else "no styles requested"
        )
        return DoctorCheck("word.custom_styles", "manuscript styles in reference", True, detail)

    reported: list[str] = []
    remediation: list[str] = []
    for request in missing:
        location = f"{relpath(request.source, config.root)}:{request.line}"
        reported.append(f"{request.name!r} at {location}")
        closest = difflib.get_close_matches(request.name, available, n=1, cutoff=0.6)
        if closest:
            remediation.append(f"Did you mean {closest[0]!r}? Used at {location}.")
    remediation.append(
        "Run uv run paperflow template-styles to list the names the reference defines."
    )
    remediation.append(
        "Correct the custom-style name, or add the style to the reference document."
    )
    return DoctorCheck(
        "word.custom_styles",
        "manuscript styles in reference",
        False,
        "not defined in the reference: " + "; ".join(reported),
        tuple(remediation),
        error_code="word.custom_style_missing",
    )


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
                reference = docx_reference_status(config.word.reference_docx)
                checks.append(
                    DoctorCheck(
                        "word.reference.structure",
                        "Word reference DOCX structure",
                        reference.valid,
                        "valid" if reference.valid else "invalid or unreadable DOCX",
                        ()
                        if reference.valid
                        else (
                            "Replace the file with a valid Word DOCX and rerun Doctor.",
                            "Follow docs/word-template.md before using a publisher template.",
                        ),
                    )
                )
                if reference.valid:
                    checks.append(_custom_style_check(config))
                    checks.append(
                        DoctorCheck(
                            "word.reference.paths",
                            "Word reference local paths",
                            reference.path_safe,
                            "none found"
                            if reference.path_safe
                            else "absolute local path in "
                            + "; ".join(reference.absolute_paths),
                            ()
                            if reference.path_safe
                            else (
                                "Follow the 'Remove absolute local paths' steps in "
                                "docs/word-template.md; they name the Word setting behind each "
                                "reported part.",
                                "Repair a copy of the template rather than disabling "
                                "word.reject_absolute_paths, and keep the original private "
                                "template outside version control.",
                            ),
                        )
                    )
    checks.append(DoctorCheck("python.executable", "python executable", True, sys.executable))
    checks.append(
        DoctorCheck("python.version", "python version", True, sys.version.split()[0])
    )
    inside_venv = python_is_venv(root)
    expected_venv = (root / ".venv").resolve()
    if inside_venv:
        venv_detail = str(expected_venv)
        venv_remediation: tuple[str, ...] = ()
    elif sys.prefix == sys.base_prefix:
        venv_detail = f"no virtual environment is active; expected {expected_venv}"
        venv_remediation = (
            "Run uv sync --frozen --extra dev from the project root.",
            "Invoke Paperflow with uv run rather than a system Python interpreter.",
        )
    else:
        venv_detail = (
            f"a different environment is active: {Path(sys.prefix).resolve()}; "
            f"expected {expected_venv}"
        )
        venv_remediation = (
            "Prefix commands with uv run; it always selects this project's .venv, whatever "
            "the shell has activated.",
            "Run uv sync --frozen --extra dev from this project root if .venv is missing.",
        )
    checks.append(
        DoctorCheck(
            "python.venv",
            "python inside .venv",
            inside_venv,
            venv_detail,
            venv_remediation,
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
            "If Quarto is installed outside PATH, run uv run paperflow init-local to record "
            "its location in .paperflow.local.yml.",
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
