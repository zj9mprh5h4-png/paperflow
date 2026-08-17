"""Inspection and automatic repair of Word reference templates.

The repair edits are byte-level on purpose. Re-serialising a Word part with
ElementTree renames its namespace prefixes, and ``word/settings.xml`` carries an
``mc:Ignorable`` attribute that lists prefixes by name. Renaming them there produces a
file Word refuses to open, so each part is edited in place instead of rewritten.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

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


STYLES_MEMBER = "word/styles.xml"
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Style names the Pandoc DOCX writer applies on its own when the reference defines
# them. Everything else has to be requested explicitly with a custom-style div or span.
PANDOC_APPLIED_STYLES = frozenset(
    {
        "Title",
        "Subtitle",
        "Author",
        "Date",
        "Abstract",
        "Abstract Title",
        "Compact",
        "Body Text",
        "First Paragraph",
        "Block Text",
        "Source Code",
        "Footnote Text",
        "Definition Term",
        "Definition",
        "Caption",
        "Table Caption",
        "Image Caption",
        "Figure",
        "Captioned Figure",
        "TOC Heading",
        "Bibliography",
        "Verbatim Char",
        "Footnote Reference",
        "Hyperlink",
        "Section Number",
        *(f"Heading {level}" for level in range(1, 10)),
    }
)


@dataclass(frozen=True)
class TemplateSanitisation:
    path: Path
    removed: tuple[str, ...]
    remaining: tuple[str, ...]


@dataclass(frozen=True)
class TemplateStyle:
    name: str
    kind: str
    applied_by_pandoc: bool
    hidden: bool


def reference_docx_styles(path: Path) -> tuple[TemplateStyle, ...]:
    """List the paragraph and character styles a reference DOCX defines, by Word name."""
    if not path.is_file():
        raise PaperflowError(
            f"Word reference document does not exist: {path}",
            code="template_styles.missing",
            remediation=(
                "Pass --docx with the template to inspect, or configure word.reference_docx "
                "with uv run paperflow init-local --reference-docx <path> --force.",
            ),
        )
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read(STYLES_MEMBER)
        root = ElementTree.fromstring(xml)
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise PaperflowError(
            f"Could not read the styles of {path}",
            code="template_styles.unreadable",
            remediation=(
                "Confirm the file is a valid DOCX; a .dotx or .dot must be saved as .docx.",
                "Run uv run paperflow doctor to check the configured reference document.",
            ),
        ) from exc

    styles: list[TemplateStyle] = []
    for style in root.findall(f"{{{WORD_NAMESPACE}}}style"):
        kind = style.get(f"{{{WORD_NAMESPACE}}}type", "")
        if kind not in {"paragraph", "character"}:
            continue
        name = style.find(f"{{{WORD_NAMESPACE}}}name")
        value = name.get(f"{{{WORD_NAMESPACE}}}val") if name is not None else None
        if not value:
            continue
        styles.append(
            TemplateStyle(
                name=value,
                kind=kind,
                applied_by_pandoc=value in PANDOC_APPLIED_STYLES,
                hidden=style.find(f"{{{WORD_NAMESPACE}}}semiHidden") is not None,
            )
        )
    return tuple(sorted(styles, key=lambda item: (item.kind, item.name.lower())))


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


DOCUMENT_MEMBER = "word/document.xml"
# Styles that carry no formatting worth requesting; their paragraphs become plain text.
PLAIN_STYLES = frozenset({"Normal", "Body Text", "First Paragraph", "Compact"})
HEADING_RE = re.compile(r"^heading (\d)$", re.IGNORECASE)
MARKDOWN_ESCAPES = {character: f"\\{character}" for character in "\\`*_[]<>^~"}


@dataclass(frozen=True)
class ExtractedFrontMatter:
    markdown: str
    styles: tuple[str, ...]
    skipped_tables: int
    skipped_drawings: int


def _style_names(root: ElementTree.Element) -> dict[str, str]:
    names: dict[str, str] = {}
    for style in root.findall(f"{{{WORD_NAMESPACE}}}style"):
        style_id = style.get(f"{{{WORD_NAMESPACE}}}styleId")
        name = style.find(f"{{{WORD_NAMESPACE}}}name")
        value = name.get(f"{{{WORD_NAMESPACE}}}val") if name is not None else None
        if style_id and value:
            names[style_id] = value
    return names


def _run_text(run: ElementTree.Element) -> str:
    pieces: list[str] = []
    for child in run:
        tag = child.tag.removeprefix(f"{{{WORD_NAMESPACE}}}")
        if tag == "t":
            pieces.append((child.text or "").translate(str.maketrans(MARKDOWN_ESCAPES)))
        elif tag == "tab":
            pieces.append(" ")
        elif tag == "br":
            pieces.append("\n")
    text = "".join(pieces)
    if not text:
        return ""
    properties = run.find(f"{{{WORD_NAMESPACE}}}rPr")
    alignment = (
        properties.find(f"{{{WORD_NAMESPACE}}}vertAlign") if properties is not None else None
    )
    value = alignment.get(f"{{{WORD_NAMESPACE}}}val") if alignment is not None else None
    if value == "superscript":
        return f"^{text}^"
    if value == "subscript":
        return f"~{text}~"
    return text


def _paragraph_style(paragraph: ElementTree.Element, names: dict[str, str]) -> str | None:
    properties = paragraph.find(f"{{{WORD_NAMESPACE}}}pPr")
    if properties is None:
        return None
    style = properties.find(f"{{{WORD_NAMESPACE}}}pStyle")
    identifier = style.get(f"{{{WORD_NAMESPACE}}}val") if style is not None else None
    return names.get(identifier, identifier) if identifier else None


def extract_front_matter(path: Path) -> ExtractedFrontMatter:
    """Turn the body of a Word template into Markdown that requests the same styles.

    A reference document's body text is discarded during rendering, so a publisher's
    author block, affiliations, and keyword lines never reach an output document. This
    converts that boilerplate into manuscript sources instead of throwing it away.
    """
    if not path.is_file():
        raise PaperflowError(
            f"Word reference document does not exist: {path}",
            code="template_front_matter.missing",
            remediation=(
                "Pass --docx with the template to read, or configure word.reference_docx.",
            ),
        )
    try:
        with zipfile.ZipFile(path) as archive:
            document = ElementTree.fromstring(archive.read(DOCUMENT_MEMBER))
            styles = ElementTree.fromstring(archive.read(STYLES_MEMBER))
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise PaperflowError(
            f"Could not read the body of {path}",
            code="template_front_matter.unreadable",
            remediation=(
                "Confirm the file is a valid DOCX; a .dotx or .dot must be saved as .docx.",
            ),
        ) from exc

    names = _style_names(styles)
    body = document.find(f"{{{WORD_NAMESPACE}}}body")
    blocks: list[str] = []
    used: list[str] = []
    tables = 0
    drawings = 0
    for element in list(body) if body is not None else []:
        tag = element.tag.removeprefix(f"{{{WORD_NAMESPACE}}}")
        if tag == "tbl":
            tables += 1
            continue
        if tag != "p":
            continue
        if element.find(f".//{{{WORD_NAMESPACE}}}drawing") is not None:
            drawings += 1
        text = "".join(
            _run_text(run) for run in element.findall(f"{{{WORD_NAMESPACE}}}r")
        ).strip()
        if not text:
            continue
        style = _paragraph_style(element, names)
        heading = HEADING_RE.match(style) if style else None
        if heading:
            blocks.append(f"{'#' * int(heading.group(1))} {text}")
        elif style is None or style in PLAIN_STYLES:
            blocks.append(text)
        else:
            if style not in used:
                used.append(style)
            blocks.append(f'::: {{custom-style="{style}"}}\n{text}\n:::')
    return ExtractedFrontMatter(
        markdown="\n\n".join(blocks) + "\n" if blocks else "",
        styles=tuple(used),
        skipped_tables=tables,
        skipped_drawings=drawings,
    )


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
