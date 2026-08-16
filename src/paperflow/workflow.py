from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import PaperflowConfig, load_config
from .open_items import OpenItemsBuild, build_open_items
from .review import render_docx


@dataclass(frozen=True)
class ProjectBuild:
    manuscript: Path
    open_items: OpenItemsBuild | None


def build_project(config: PaperflowConfig | None = None) -> ProjectBuild:
    resolved = config or load_config()
    manuscript = render_docx(config=resolved)
    open_items = build_open_items(resolved) if resolved.open_items.enabled else None
    return ProjectBuild(manuscript=manuscript, open_items=open_items)
