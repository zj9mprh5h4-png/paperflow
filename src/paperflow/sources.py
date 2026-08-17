"""Which files make up the rendered manuscript, and what they ask of the template."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

INCLUDE_RE = re.compile(r"\{\{<\s*include\s+(.+?)\s*>\}\}")
CUSTOM_STYLE_RE = re.compile(r"""custom-style=["']([^"']+)["']""")

# The section files are the single source of truth for what a manuscript contains.
# Paperflow regenerates the include list between these markers and nothing else, so
# anything a user writes elsewhere in the entry point survives untouched. Removing the
# markers opts out of the mechanism and returns the list to manual care.
SECTIONS_BEGIN = "<!-- paperflow:sections -->"
SECTIONS_END = "<!-- /paperflow:sections -->"


@dataclass(frozen=True)
class StyleRequest:
    name: str
    source: Path
    line: int


def included_sources(text: str, qmd: Path) -> tuple[Path, ...]:
    """Return the existing files a QMD pulls in with Quarto include shortcodes."""
    included: list[Path] = []
    for match in INCLUDE_RE.finditer(text):
        target = (qmd.parent / match.group(1).strip().strip("\"'")).resolve()
        if target.is_file() and target not in included:
            included.append(target)
    return tuple(included)


def rendered_sources(entry: Path) -> tuple[Path, ...]:
    """Return the entry point and every file reachable from it through includes."""
    seen: list[Path] = []
    pending = [entry.resolve()]
    while pending:
        current = pending.pop(0)
        if current in seen or not current.is_file():
            continue
        seen.append(current)
        try:
            text = current.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        pending.extend(path for path in included_sources(text, current) if path not in seen)
    return tuple(seen)


def include_targets(text: str, qmd: Path) -> tuple[Path, ...]:
    """Return every path a QMD asks for, whether or not the file exists."""
    targets: list[Path] = []
    for match in INCLUDE_RE.finditer(text):
        target = (qmd.parent / match.group(1).strip().strip("\"'")).resolve()
        if target not in targets:
            targets.append(target)
    return tuple(targets)


def missing_includes(entry: Path) -> tuple[Path, ...]:
    """Return every include target that does not exist, following includes transitively.

    Quarto reports this as an uncaught JavaScript error with a stack trace. Paperflow
    knows the failure precisely, so it is worth catching before the renderer is called.
    """
    missing: list[Path] = []
    seen: set[Path] = set()
    pending = [entry.resolve()]
    while pending:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)
        try:
            text = current.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for target in include_targets(text, current):
            if not target.is_file():
                if target not in missing:
                    missing.append(target)
            elif target not in seen:
                pending.append(target)
    return tuple(missing)


def section_files(directory: Path) -> tuple[Path, ...]:
    """Return the Markdown section files in document order, which is filename order."""
    if not directory.is_dir():
        return ()
    return tuple(sorted(path for path in directory.glob("*.md") if path.is_file()))


def find_section_block(text: str) -> tuple[int, int] | None:
    """Return the line span Paperflow may rewrite, excluding the markers themselves."""
    lines = text.splitlines()
    begin = end = None
    for number, line in enumerate(lines):
        stripped = line.strip()
        if stripped == SECTIONS_BEGIN and begin is None:
            begin = number
        elif stripped == SECTIONS_END and begin is not None:
            end = number
            break
    if begin is None or end is None:
        return None
    return begin, end


def render_section_block(manuscript: Path, files: tuple[Path, ...]) -> list[str]:
    """Render one include line per section file, relative to the manuscript."""
    return [
        f"{{{{< include {path.relative_to(manuscript.parent).as_posix()} >}}}}"
        for path in files
    ]


def replace_section_block(text: str, includes: list[str]) -> str | None:
    """Rewrite only the lines between the markers, leaving the rest of the file alone."""
    span = find_section_block(text)
    if span is None:
        return None
    begin, end = span
    lines = text.splitlines()
    updated = lines[: begin + 1] + includes + lines[end:]
    trailing = "\n" if text.endswith("\n") else ""
    return "\n".join(updated) + trailing


def custom_style_requests(paths: tuple[Path, ...]) -> tuple[StyleRequest, ...]:
    """Return every Word style the sources request by name, with where it was requested."""
    requests: list[StyleRequest] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for match in CUSTOM_STYLE_RE.finditer(line):
                requests.append(StyleRequest(name=match.group(1), source=path, line=number))
    return tuple(requests)
