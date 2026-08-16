from __future__ import annotations

import uuid
from pathlib import Path

from .commands import PaperflowError, relpath, require_tool, run_command
from .config import PaperflowConfig
from .docx_math import protect_docx_inline_math
from .publication import publish_docx_outputs
from .validation import (
    docx_absolute_path_locations,
    docx_core_files_present,
)


def stage_qmd_to_docx(
    source: Path,
    output: Path,
    *,
    config: PaperflowConfig,
    execute: bool = True,
) -> Path:
    require_tool("quarto", root=config.root)
    if not source.is_file():
        raise PaperflowError(f"QMD source does not exist: {source}")
    if config.word.reference_docx is not None and not config.word.reference_docx.is_file():
        raise PaperflowError(
            f"Word reference document does not exist: {config.word.reference_docx}"
        )

    config.paths.work_dir.mkdir(parents=True, exist_ok=True)
    temporary_name = f".paperflow-{uuid.uuid4().hex}.docx"
    staged = config.paths.work_dir / f".paperflow-staged-{uuid.uuid4().hex}.docx"
    args = [
        "quarto",
        "render",
        relpath(source, config.root),
        "--to",
        "docx",
        "--output",
        temporary_name,
        "--metadata",
        f"lang:{config.project.language}",
    ]
    if config.word.reference_docx is not None:
        args.extend(["--reference-doc", str(config.word.reference_docx)])
    if not execute:
        args.append("--no-execute")

    for stale in config.root.rglob(temporary_name):
        stale.unlink(missing_ok=True)
    try:
        run_command(args, cwd=config.root)
        candidates = [path for path in config.root.rglob(temporary_name) if path.is_file()]
        if len(candidates) != 1 or candidates[0].stat().st_size < 1000:
            raise PaperflowError(
                f"Expected one rendered DOCX named {temporary_name}, found {len(candidates)}."
            )
        rendered = candidates[0]
        if config.word.protect_inline_math:
            protect_docx_inline_math(rendered)
        if not docx_core_files_present(rendered):
            raise PaperflowError(f"Generated file is not a valid DOCX: {output}")
        if config.word.reject_absolute_paths:
            locations = docx_absolute_path_locations(rendered)
            if locations:
                raise PaperflowError(
                    "Generated DOCX contains an absolute local path in "
                    f"{'; '.join(locations)}; {output.name} was not replaced.",
                    code="render.absolute_path",
                    remediation=(
                        "Such a path almost always comes from the configured Word reference "
                        "document, which Quarto copies headers, footers, and styles from.",
                        "Run uv run paperflow sanitize-template --docx <template> to repair a "
                        "copy, then uv run paperflow doctor to confirm.",
                        "See docs/word-template.md for the parts sanitize-template reports "
                        "instead of repairing.",
                    ),
                )
        rendered.replace(staged)
        return staged
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    finally:
        for temporary in config.root.rglob(temporary_name):
            temporary.unlink(missing_ok=True)


def render_qmd_to_docx(
    source: Path,
    output: Path,
    *,
    config: PaperflowConfig,
    execute: bool = True,
) -> Path:
    staged = stage_qmd_to_docx(
        source,
        output,
        config=config,
        execute=execute,
    )
    try:
        publish_docx_outputs({output: staged}, config=config)
    finally:
        staged.unlink(missing_ok=True)
    return output
