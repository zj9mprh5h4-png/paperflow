from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import PaperflowConfig, load_config
from .open_items import OpenItemsBuild, StagedOpenItems, stage_open_items
from .publication import publish_docx_outputs
from .rendering import stage_qmd_to_docx
from .review import run_pre_render_hook


@dataclass(frozen=True)
class ProjectBuild:
    manuscript: Path
    open_items: OpenItemsBuild | None


def build_project(config: PaperflowConfig | None = None) -> ProjectBuild:
    resolved = config or load_config()
    run_pre_render_hook(resolved.root, resolved)
    staged_manuscript = stage_qmd_to_docx(
        resolved.project.manuscript,
        resolved.manuscript_output,
        config=resolved,
    )
    staged_open_items: StagedOpenItems | None = None
    try:
        staged_outputs = {resolved.manuscript_output: staged_manuscript}
        if resolved.open_items.enabled:
            staged_open_items = stage_open_items(resolved)
            staged_outputs[resolved.open_items.output_docx] = staged_open_items.docx
        publish_docx_outputs(staged_outputs, config=resolved)
    finally:
        staged_manuscript.unlink(missing_ok=True)
        if staged_open_items is not None:
            staged_open_items.docx.unlink(missing_ok=True)

    open_items = (
        OpenItemsBuild(
            count=staged_open_items.count,
            markdown=staged_open_items.markdown,
            docx=resolved.open_items.output_docx,
        )
        if staged_open_items is not None
        else None
    )
    return ProjectBuild(manuscript=resolved.manuscript_output, open_items=open_items)
