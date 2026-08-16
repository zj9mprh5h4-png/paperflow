from __future__ import annotations

import uuid
from pathlib import Path

from .commands import PaperflowError, relpath, require_tool, run_command
from .config import PaperflowConfig
from .docx_math import protect_docx_inline_math
from .validation import (
    docx_contains_absolute_paths,
    docx_core_files_present,
)


def render_qmd_to_docx(
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

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = f".paperflow-{uuid.uuid4().hex}.docx"
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
        if config.word.reject_absolute_paths and docx_contains_absolute_paths(rendered):
            raise PaperflowError(f"Generated DOCX contains an absolute local path: {output}")
        rendered.replace(output)
    finally:
        for temporary in config.root.rglob(temporary_name):
            temporary.unlink(missing_ok=True)

    return output
