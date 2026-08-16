"""Automatic repair of Word reference templates that carry machine-specific links.

The edits below are byte-level on purpose. Re-serialising a Word part with
ElementTree renames its namespace prefixes, and ``word/settings.xml`` carries an
``mc:Ignorable`` attribute that lists prefixes by name. Renaming them there produces a
file Word refuses to open, so each part is edited in place instead of rewritten.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .commands import PaperflowError
from .docx_package import read_docx_members, write_docx_members
from .validation import (
    ABSOLUTE_POSIX_RE,
    ABSOLUTE_WINDOWS_RE,
    docx_absolute_path_locations,
    docx_core_files_present,
)

SETTINGS_MEMBER = "word/settings.xml"
SETTINGS_RELATIONSHIPS_MEMBER = "word/_rels/settings.xml.rels"
APP_PROPERTIES_MEMBER = "docProps/app.xml"
CORE_PROPERTIES_MEMBER = "docProps/core.xml"

ATTACHED_TEMPLATE_ELEMENT_RE = re.compile(rb"<w:attachedTemplate\b[^>]*/>")
ATTACHED_TEMPLATE_PAIR_RE = re.compile(
    rb"<w:attachedTemplate\b[^>]*>.*?</w:attachedTemplate>", re.DOTALL
)
ATTACHED_TEMPLATE_RELATIONSHIP_RE = re.compile(
    rb"<Relationship\b[^>]*attachedTemplate[^>]*/>"
)
HYPERLINK_BASE_RE = re.compile(rb"<HyperlinkBase>.*?</HyperlinkBase>", re.DOTALL)
COMPANY_RE = re.compile(rb"<Company>.*?</Company>", re.DOTALL)
MANAGER_RE = re.compile(rb"<Manager>.*?</Manager>", re.DOTALL)
CREATOR_RE = re.compile(rb"<dc:creator>.*?</dc:creator>", re.DOTALL)
LAST_MODIFIED_BY_RE = re.compile(rb"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", re.DOTALL)


@dataclass(frozen=True)
class TemplateSanitisation:
    path: Path
    removed: tuple[str, ...]
    remaining: tuple[str, ...]


def _drop(members: dict[str, bytes], member: str, pattern: re.Pattern[bytes]) -> bool:
    content = members.get(member)
    if content is None:
        return False
    replaced = pattern.sub(b"", content)
    if replaced == content:
        return False
    members[member] = replaced
    return True


def _clear(
    members: dict[str, bytes],
    member: str,
    pattern: re.Pattern[bytes],
    empty: bytes,
) -> bool:
    content = members.get(member)
    if content is None:
        return False
    replaced = pattern.sub(empty, content)
    if replaced == content:
        return False
    members[member] = replaced
    return True


ALT_TEXT_VALUE_RE = re.compile(rb'((?:descr|alt|title)=")([^"]*)(")')


def _strip_paths_from_alt_text(members: dict[str, bytes]) -> bool:
    """Remove file paths from image alt text while keeping any real description.

    Word writes the original file path into an image's alternative text. The picture
    itself is embedded, so the path is metadata only, but it travels with every copy of
    the template and reaches every generated document.
    """
    changed = False

    def repair(match: re.Match[bytes]) -> bytes:
        value = match.group(2)
        stripped = ABSOLUTE_POSIX_RE.sub(b"", ABSOLUTE_WINDOWS_RE.sub(b"", value))
        if stripped == value:
            return match.group(0)
        return match.group(1) + stripped.strip(b" \t,;-") + match.group(3)

    for name, content in members.items():
        if not name.endswith((".xml", ".rels")):
            continue
        repaired = ALT_TEXT_VALUE_RE.sub(repair, content)
        if repaired != content:
            members[name] = repaired
            changed = True
    return changed


def _sanitise_members(members: dict[str, bytes]) -> list[str]:
    removed: list[str] = []

    attached = _drop(members, SETTINGS_MEMBER, ATTACHED_TEMPLATE_ELEMENT_RE)
    attached |= _drop(members, SETTINGS_MEMBER, ATTACHED_TEMPLATE_PAIR_RE)
    attached |= _drop(
        members,
        SETTINGS_RELATIONSHIPS_MEMBER,
        ATTACHED_TEMPLATE_RELATIONSHIP_RE,
    )
    if attached:
        removed.append("attached document template")

    if _drop(members, APP_PROPERTIES_MEMBER, HYPERLINK_BASE_RE):
        removed.append("hyperlink base")
    if _drop(members, APP_PROPERTIES_MEMBER, COMPANY_RE):
        removed.append("company name")
    if _drop(members, APP_PROPERTIES_MEMBER, MANAGER_RE):
        removed.append("manager name")
    if _clear(members, CORE_PROPERTIES_MEMBER, CREATOR_RE, b"<dc:creator></dc:creator>"):
        removed.append("author name")
    if _clear(
        members,
        CORE_PROPERTIES_MEMBER,
        LAST_MODIFIED_BY_RE,
        b"<cp:lastModifiedBy></cp:lastModifiedBy>",
    ):
        removed.append("last-modified-by name")
    if _strip_paths_from_alt_text(members):
        removed.append("file paths in image alt text")
    return removed


def sanitise_reference_docx(
    *,
    source: Path,
    target: Path,
    force: bool = False,
) -> TemplateSanitisation:
    """Write a repaired copy of a Word template and report what could not be fixed."""
    if not source.is_file():
        raise PaperflowError(
            f"Word template does not exist: {source}",
            code="sanitize_template.source_missing",
            remediation=(
                "Pass --docx with the path to the template you want to repair.",
            ),
        )
    try:
        valid = docx_core_files_present(source)
    except (OSError, zipfile.BadZipFile) as exc:
        raise PaperflowError(
            f"Word template is not a readable DOCX: {source}",
            code="sanitize_template.source_invalid",
            remediation=(
                "Open the file in Word and save it as .docx, then repeat the command.",
                "A .dotx or .dot template must be saved as .docx first.",
            ),
        ) from exc
    if not valid:
        raise PaperflowError(
            f"Word template is not a valid DOCX package: {source}",
            code="sanitize_template.source_invalid",
            remediation=(
                "Open the file in Word and save it as .docx, then repeat the command.",
                "A .dotx or .dot template must be saved as .docx first.",
            ),
        )
    if target.exists() and not force:
        raise PaperflowError(
            f"Sanitized template already exists: {target}",
            code="sanitize_template.target_exists",
            remediation=(
                "Rerun with --force to replace it, or choose a different --out path.",
            ),
        )

    members, infos = read_docx_members(source)
    removed = _sanitise_members(members)
    write_docx_members(target, members, infos)
    return TemplateSanitisation(
        path=target,
        removed=tuple(removed),
        remaining=docx_absolute_path_locations(target),
    )
