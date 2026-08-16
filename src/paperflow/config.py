from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .commands import PaperflowError, find_project_root

CONFIG_FILE = "paperflow.yml"
LOCAL_CONFIG_FILE = ".paperflow.local.yml"

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "project": {
        "name": "paperflow-project",
        "language": "en",
        "manuscript": "manuscript/index.qmd",
        "formatting_rules": "manuscript/manuscript_formatting_rules.md",
    },
    "paths": {
        "output_dir": "build",
        "work_dir": ".work",
        "review_dir": "reviews",
    },
    "build": {
        "manuscript_filename": "paper_current.docx",
        "run_pre_render_hook": True,
        "archive_previous": True,
        "archive_dir": "build/archived",
        "embed_provenance": True,
    },
    "word": {
        "reference_docx": None,
        "protect_inline_math": True,
        "reject_absolute_paths": True,
    },
    "open_items": {
        "enabled": True,
        "marker_pattern": r"\[\[OPEN:\s*(.*?)\]\]",
        "source_globs": ["manuscript/**/*.md", "manuscript/**/*.qmd"],
        "exclude_globs": [
            "manuscript/archived/**",
            "manuscript/**/archived/**",
            "manuscript/manuscript_formatting_rules.md",
        ],
        "output_markdown": "build/open_items.md",
        "output_docx": "build/open_items_current.docx",
    },
    "review": {
        "require_clean_git": True,
        "auto_apply_word_changes": False,
    },
    "executables": {
        "git": None,
        "uv": None,
        "quarto": None,
    },
}


@dataclass(frozen=True)
class ProjectSettings:
    name: str
    language: str
    manuscript: Path
    formatting_rules: Path


@dataclass(frozen=True)
class PathSettings:
    output_dir: Path
    work_dir: Path
    review_dir: Path


@dataclass(frozen=True)
class BuildSettings:
    manuscript_filename: str
    run_pre_render_hook: bool
    archive_previous: bool
    archive_dir: Path
    embed_provenance: bool


@dataclass(frozen=True)
class WordSettings:
    reference_docx: Path | None
    protect_inline_math: bool
    reject_absolute_paths: bool


@dataclass(frozen=True)
class OpenItemsSettings:
    enabled: bool
    marker_pattern: str
    source_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...]
    output_markdown: Path
    output_docx: Path


@dataclass(frozen=True)
class ReviewSettings:
    require_clean_git: bool
    auto_apply_word_changes: bool


@dataclass(frozen=True)
class ExecutableSettings:
    git: str | None
    uv: str | None
    quarto: str | None

    def get(self, name: str) -> str | None:
        if name not in {"git", "uv", "quarto"}:
            return None
        return getattr(self, name)


@dataclass(frozen=True)
class PaperflowConfig:
    root: Path
    project: ProjectSettings
    paths: PathSettings
    build: BuildSettings
    word: WordSettings
    open_items: OpenItemsSettings
    review: ReviewSettings
    executables: ExecutableSettings
    raw: dict[str, Any]

    @property
    def manuscript_output(self) -> Path:
        return self.paths.output_dir / self.build.manuscript_filename


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PaperflowError(
            f"Could not read configuration {path}: {exc}",
            code="config.read",
            remediation=(
                f"Open {path.name} and correct the reported YAML syntax or file-access error.",
                "Keep indentation consistent and use spaces rather than tabs.",
            ),
        ) from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise PaperflowError(
            f"Configuration must contain a YAML mapping: {path}",
            code="config.root_mapping",
            remediation=(
                f"Replace the top level of {path.name} with YAML key-value mappings.",
                "Start from paperflow.yml or paperflow.local.example.yml as appropriate.",
            ),
        )
    return loaded


def _validate_keys(
    candidate: dict[str, Any],
    template: dict[str, Any],
    *,
    prefix: str = "",
    source: str,
) -> None:
    unknown = sorted(set(candidate).difference(template))
    if unknown:
        location = prefix or "configuration"
        raise PaperflowError(
            f"Unknown {location} key(s): {', '.join(unknown)}",
            code="config.unknown_keys",
            remediation=(
                f"Correct or remove the listed key(s) in {source}.",
                "Use docs/configuration.md for the supported schema_version 1 keys.",
            ),
        )
    for key, value in candidate.items():
        expected = template[key]
        if isinstance(expected, dict):
            if not isinstance(value, dict):
                label = f"{prefix}{key}"
                raise PaperflowError(
                    f"Configuration key {label} must be a mapping.",
                    code="config.mapping",
                    remediation=(
                        f"In {source}, make {label} a YAML mapping with indented child keys.",
                        "Compare the section with docs/configuration.md.",
                    ),
                )
            _validate_keys(value, expected, prefix=f"{prefix}{key}.", source=source)


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise PaperflowError(
            f"Configuration key {label} must be a non-empty string.",
            code="config.string",
            remediation=(
                f"Set {label} to a non-empty YAML string in paperflow.yml or the local override.",
            ),
        )
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise PaperflowError(
            f"Configuration key {label} must be true or false.",
            code="config.boolean",
            remediation=(
                f"Set {label} to the unquoted YAML boolean true or false.",
            ),
        )
    return value


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise PaperflowError(
            f"Configuration key {label} must be a list of strings.",
            code="config.string_list",
            remediation=(
                f"Set {label} to a YAML list whose items are non-empty strings.",
            ),
        )
    return tuple(value)


def _inside_project(root: Path, value: Any, label: str) -> Path:
    text = _string(value, label)
    path = Path(text)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise PaperflowError(
            f"Configuration path {label} must stay inside the project: {text}",
            code="config.path_outside_project",
            remediation=(
                f"Set {label} to a project-relative path that does not escape with '..'.",
                "Use .paperflow.local.yml only for permitted machine-local executable "
                "and Word-template paths.",
            ),
        ) from exc
    return resolved


def _optional_path(root: Path, value: Any, label: str) -> Path | None:
    if value is None:
        return None
    text = _string(value, label)
    path = Path(text).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _optional_executable(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _string(value, label)


def load_config(root: Path | None = None) -> PaperflowConfig:
    project_root = (root or find_project_root()).resolve()
    merged = copy.deepcopy(DEFAULT_CONFIG)
    for filename in (CONFIG_FILE, LOCAL_CONFIG_FILE):
        path = project_root / filename
        if not path.exists():
            continue
        override = _read_yaml(path)
        _validate_keys(override, DEFAULT_CONFIG, source=path.name)
        merged = _merge(merged, override)

    if merged["schema_version"] != 1:
        raise PaperflowError(
            "Only paperflow configuration schema_version 1 is supported.",
            code="config.schema_version",
            remediation=(
                "Set schema_version: 1 at the top level of paperflow.yml.",
                "Migrate unsupported keys using docs/configuration.md before rerunning Doctor.",
            ),
        )

    project = merged["project"]
    paths = merged["paths"]
    build = merged["build"]
    word = merged["word"]
    open_items = merged["open_items"]
    review = merged["review"]
    executables = merged["executables"]

    marker_pattern = _string(open_items["marker_pattern"], "open_items.marker_pattern")
    try:
        compiled = re.compile(marker_pattern)
    except re.error as exc:
        raise PaperflowError(
            f"Invalid open_items.marker_pattern: {exc}",
            code="config.marker_pattern",
            remediation=(
                "Correct open_items.marker_pattern so it is a valid regular expression.",
                r"Restore the default '\[\[OPEN:\s*(.*?)\]\]' if custom matching is not required.",
            ),
        ) from exc
    if compiled.groups != 1:
        raise PaperflowError(
            "open_items.marker_pattern must contain exactly one capture group.",
            code="config.marker_capture_group",
            remediation=(
                "Use exactly one (...) capture group for the OPEN-item text.",
                r"Restore the default '\[\[OPEN:\s*(.*?)\]\]' if custom matching is not required.",
            ),
        )

    auto_apply = _boolean(review["auto_apply_word_changes"], "review.auto_apply_word_changes")
    if auto_apply:
        raise PaperflowError(
            "review.auto_apply_word_changes must remain false for source safety.",
            code="config.review_auto_apply",
            remediation=(
                "Set review.auto_apply_word_changes: false in paperflow.yml.",
                "Use review-import and review the generated Markdown diff before changing QMD.",
            ),
        )

    filename = _string(build["manuscript_filename"], "build.manuscript_filename")
    if Path(filename).name != filename or not filename.lower().endswith(".docx"):
        raise PaperflowError(
            "build.manuscript_filename must be a DOCX filename without directories.",
            code="config.manuscript_filename",
            remediation=(
                "Set build.manuscript_filename to a bare filename ending in .docx, "
                "for example manuscript.docx.",
                "Configure the containing directory separately with paths.output_dir.",
            ),
        )

    output_dir = _inside_project(project_root, paths["output_dir"], "paths.output_dir")
    archive_dir = _inside_project(project_root, build["archive_dir"], "build.archive_dir")
    manuscript_output = output_dir / filename
    open_items_output_docx = _inside_project(
        project_root,
        open_items["output_docx"],
        "open_items.output_docx",
    )
    if archive_dir in {project_root, output_dir}:
        raise PaperflowError(
            "build.archive_dir must be a dedicated directory below the project root.",
            code="config.archive_dir",
            remediation=(
                "Set build.archive_dir to a dedicated project-relative directory such as "
                "build/archived.",
            ),
        )
    if manuscript_output.is_relative_to(archive_dir) or open_items_output_docx.is_relative_to(
        archive_dir
    ):
        raise PaperflowError(
            "Current DOCX outputs must not be placed inside build.archive_dir.",
            code="config.output_in_archive",
            remediation=(
                "Keep current DOCX outputs outside build.archive_dir, for example directly "
                "under build/.",
            ),
        )
    if _boolean(open_items["enabled"], "open_items.enabled") and (
        manuscript_output == open_items_output_docx
    ):
        raise PaperflowError(
            "The manuscript and Open Items DOCX outputs must use different paths.",
            code="config.duplicate_docx_output",
            remediation=(
                "Set build.manuscript_filename and open_items.output_docx to different DOCX "
                "filenames.",
            ),
        )

    return PaperflowConfig(
        root=project_root,
        project=ProjectSettings(
            name=_string(project["name"], "project.name"),
            language=_string(project["language"], "project.language"),
            manuscript=_inside_project(project_root, project["manuscript"], "project.manuscript"),
            formatting_rules=_inside_project(
                project_root,
                project["formatting_rules"],
                "project.formatting_rules",
            ),
        ),
        paths=PathSettings(
            output_dir=output_dir,
            work_dir=_inside_project(project_root, paths["work_dir"], "paths.work_dir"),
            review_dir=_inside_project(project_root, paths["review_dir"], "paths.review_dir"),
        ),
        build=BuildSettings(
            manuscript_filename=filename,
            run_pre_render_hook=_boolean(
                build["run_pre_render_hook"],
                "build.run_pre_render_hook",
            ),
            archive_previous=_boolean(
                build["archive_previous"],
                "build.archive_previous",
            ),
            archive_dir=archive_dir,
            embed_provenance=_boolean(
                build["embed_provenance"],
                "build.embed_provenance",
            ),
        ),
        word=WordSettings(
            reference_docx=_optional_path(
                project_root,
                word["reference_docx"],
                "word.reference_docx",
            ),
            protect_inline_math=_boolean(
                word["protect_inline_math"],
                "word.protect_inline_math",
            ),
            reject_absolute_paths=_boolean(
                word["reject_absolute_paths"],
                "word.reject_absolute_paths",
            ),
        ),
        open_items=OpenItemsSettings(
            enabled=_boolean(open_items["enabled"], "open_items.enabled"),
            marker_pattern=marker_pattern,
            source_globs=_string_list(open_items["source_globs"], "open_items.source_globs"),
            exclude_globs=_string_list(
                open_items["exclude_globs"],
                "open_items.exclude_globs",
            ),
            output_markdown=_inside_project(
                project_root,
                open_items["output_markdown"],
                "open_items.output_markdown",
            ),
            output_docx=open_items_output_docx,
        ),
        review=ReviewSettings(
            require_clean_git=_boolean(
                review["require_clean_git"],
                "review.require_clean_git",
            ),
            auto_apply_word_changes=auto_apply,
        ),
        executables=ExecutableSettings(
            git=_optional_executable(executables["git"], "executables.git"),
            uv=_optional_executable(executables["uv"], "executables.uv"),
            quarto=_optional_executable(executables["quarto"], "executables.quarto"),
        ),
        raw=merged,
    )
