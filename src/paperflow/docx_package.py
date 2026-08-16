from __future__ import annotations

import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path

from .commands import PaperflowError


def read_docx_members(path: Path) -> tuple[dict[str, bytes], dict[str, zipfile.ZipInfo]]:
    """Read every part of a DOCX package, preserving order and per-entry metadata."""
    try:
        with zipfile.ZipFile(path) as source:
            info_list = source.infolist()
            members = {item.filename: source.read(item.filename) for item in info_list}
            infos = {item.filename: item for item in info_list}
    except (OSError, zipfile.BadZipFile) as exc:
        raise PaperflowError(f"Could not read the DOCX package: {path}") from exc
    return members, infos


def write_docx_members(
    path: Path,
    members: Mapping[str, bytes],
    infos: Mapping[str, zipfile.ZipInfo],
) -> None:
    """Write a DOCX package atomically, keeping each part's original entry metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.stem}-package-",
        suffix=".docx",
        dir=path.parent,
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)

    try:
        with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED) as target:
            for name, data in members.items():
                target.writestr(infos.get(name, name), data)
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
