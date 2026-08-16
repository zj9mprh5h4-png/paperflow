from __future__ import annotations

import fnmatch
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from .commands import PaperflowError, relpath
from .config import PaperflowConfig
from .publication import publish_docx_outputs
from .rendering import stage_qmd_to_docx

HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*$")
SECTION_COMMENT_RE = re.compile(r"^<!--\s*Section:\s*(.+?)\s*-->$")


@dataclass(frozen=True)
class OpenItem:
    text: str
    source: Path
    line: int
    group: str


@dataclass(frozen=True)
class OpenItemsBuild:
    count: int
    markdown: Path
    docx: Path


@dataclass(frozen=True)
class StagedOpenItems:
    count: int
    markdown: Path
    docx: Path


def _excluded(relative: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)


def source_files(config: PaperflowConfig) -> list[Path]:
    files: set[Path] = set()
    for pattern in config.open_items.source_globs:
        files.update(path.resolve() for path in config.root.glob(pattern) if path.is_file())
    return sorted(
        path
        for path in files
        if not _excluded(relpath(path, config.root), config.open_items.exclude_globs)
    )


def collect_open_items(config: PaperflowConfig) -> list[OpenItem]:
    marker = re.compile(config.open_items.marker_pattern)
    items: list[OpenItem] = []
    for path in source_files(config):
        relative = relpath(path, config.root)
        chapter = path.stem.replace("-", " ").replace("_", " ").title()
        section = ""
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            section_comment = SECTION_COMMENT_RE.match(stripped)
            if section_comment:
                section = section_comment.group(1)
                continue
            heading = HEADING_RE.match(line)
            if heading:
                if heading.group(1) == "#":
                    chapter = heading.group(2)
                    section = ""
                else:
                    section = heading.group(2)
            if stripped.startswith("<!--"):
                continue
            for match in marker.finditer(line):
                text = match.group(1).strip()
                if not text:
                    raise PaperflowError(f"Empty OPEN marker in {relative}:{line_number}")
                group = chapter if not section else f"{chapter} / {section}"
                items.append(OpenItem(text=text, source=path, line=line_number, group=group))
    return items


def open_items_markdown(items: list[OpenItem], config: PaperflowConfig) -> str:
    grouped: OrderedDict[str, list[OpenItem]] = OrderedDict()
    for item in items:
        grouped.setdefault(item.group, []).append(item)

    output = [
        "# Open Items",
        "",
        (
            "This report is generated from the current manuscript placeholders for "
            f"{config.project.name}."
        ),
        "",
        f"- Total: {len(items)}",
        "",
    ]
    if not items:
        output.extend(["No open items were found.", ""])
    for group, group_items in grouped.items():
        output.extend([f"## {group}", ""])
        for item in group_items:
            output.append(
                f"- [ ] {item.text} _(`{relpath(item.source, config.root)}`, line {item.line})_"
            )
        output.append("")
    return "\n".join(output).rstrip() + "\n"


def stage_open_items(config: PaperflowConfig) -> StagedOpenItems:
    if not config.open_items.enabled:
        raise PaperflowError("Open-items generation is disabled in paperflow.yml.")
    items = collect_open_items(config)
    markdown = open_items_markdown(items, config)
    config.open_items.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    config.open_items.output_markdown.write_text(markdown, encoding="utf-8")

    config.paths.work_dir.mkdir(parents=True, exist_ok=True)
    source = config.paths.work_dir / "open_items.qmd"
    source.write_text(
        "---\n"
        "from: markdown+tex_math_single_backslash\n"
        f"lang: {config.project.language}\n"
        "---\n\n"
        + markdown,
        encoding="utf-8",
    )
    try:
        staged = stage_qmd_to_docx(
            source,
            config.open_items.output_docx,
            config=config,
            execute=False,
        )
    finally:
        source.unlink(missing_ok=True)
    return StagedOpenItems(
        count=len(items),
        markdown=config.open_items.output_markdown,
        docx=staged,
    )


def build_open_items(config: PaperflowConfig) -> OpenItemsBuild:
    staged = stage_open_items(config)
    try:
        publish_docx_outputs(
            {config.open_items.output_docx: staged.docx},
            config=config,
        )
    finally:
        staged.docx.unlink(missing_ok=True)
    return OpenItemsBuild(
        count=staged.count,
        markdown=staged.markdown,
        docx=config.open_items.output_docx,
    )
