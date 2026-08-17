"""Which files make up the rendered manuscript, and what they ask of the template."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

INCLUDE_RE = re.compile(r"\{\{<\s*include\s+(.+?)\s*>\}\}")
CUSTOM_STYLE_RE = re.compile(r"""custom-style=["']([^"']+)["']""")


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
