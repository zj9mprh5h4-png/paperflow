from __future__ import annotations

import zipfile
from pathlib import Path
from xml.dom import minidom

from paperflow.docx_math import docx_inline_math_protection, protect_docx_inline_math
from paperflow.validation import (
    docx_contains_absolute_paths,
    docx_contains_omml,
    docx_core_files_present,
    docx_reference_status,
    docx_revision_counts,
)


def make_minimal_docx(path: Path, document_xml: bytes) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")
        archive.writestr("word/document.xml", document_xml)


def test_docx_structure_detects_omml(tmp_path: Path) -> None:
    docx = tmp_path / "formula.docx"
    make_minimal_docx(
        docx,
        b'<w:document xmlns:w="w" xmlns:m="m"><w:body><m:oMath/></w:body></w:document>',
    )

    assert docx_core_files_present(docx)
    assert docx_contains_omml(docx)
    assert not docx_contains_absolute_paths(docx)


def test_docx_absolute_path_scan(tmp_path: Path) -> None:
    docx = tmp_path / "path.docx"
    make_minimal_docx(docx, b'<w:document xmlns:w="w">C:\\Users\\example\\secret.png</w:document>')

    assert docx_contains_absolute_paths(docx)
    status = docx_reference_status(docx)
    assert status.valid
    assert not status.path_safe
    assert status.absolute_paths == ("word/document.xml (embedded path)",)


def test_docx_absolute_paths_are_reported_by_part_and_kind_without_the_path(
    tmp_path: Path,
) -> None:
    docx = tmp_path / "template.docx"
    make_minimal_docx(docx, b'<w:document xmlns:w="w"><w:body/></w:document>')
    with zipfile.ZipFile(docx, "a") as archive:
        archive.writestr(
            "word/_rels/settings.xml.rels",
            b'<Relationships><Relationship Type="http://schemas.openxmlformats.org/'
            b'officeDocument/2006/relationships/attachedTemplate" '
            b'Target="file:///C:\\Users\\example\\Publisher.dotx" '
            b'TargetMode="External"/></Relationships>',
        )
        archive.writestr(
            "docProps/app.xml",
            b"<Properties><HyperlinkBase>C:\\Users\\example\\figures"
            b"</HyperlinkBase></Properties>",
        )

    status = docx_reference_status(docx)

    assert not status.path_safe
    assert set(status.absolute_paths) == {
        "word/_rels/settings.xml.rels (attached document template)",
        "docProps/app.xml (hyperlink base)",
    }
    # The account name of whoever produced the template must not leak into diagnostics.
    assert not any("example" in location for location in status.absolute_paths)


def test_docx_reference_status_rejects_non_docx(tmp_path: Path) -> None:
    path = tmp_path / "not-a-docx.docx"
    path.write_text("not a zip archive", encoding="utf-8")

    status = docx_reference_status(path)

    assert not status.valid
    assert not status.path_safe
    assert status.absolute_paths == ()


def test_docx_revision_counts_track_word_changes(tmp_path: Path) -> None:
    docx = tmp_path / "review.docx"
    make_minimal_docx(
        docx,
        (
            b'<w:document xmlns:w="w"><w:body><w:ins w:id="1"><w:r/></w:ins>'
            b'<w:del w:id="2"><w:r><w:delText>old</w:delText></w:r></w:del>'
            b"</w:body></w:document>"
        ),
    )

    assert docx_revision_counts(docx) == (1, 1)


def test_inline_math_is_wrapped_in_nobreak_box_without_changing_display_math(
    tmp_path: Path,
) -> None:
    docx = tmp_path / "math.docx"
    make_minimal_docx(
        docx,
        b"""<?xml version="1.0" encoding="UTF-8"?>
<w:document
    xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
  <w:body>
    <w:p><m:oMath><m:r><m:t>P</m:t></m:r><m:r><m:t>=</m:t></m:r></m:oMath></w:p>
    <m:oMathPara><m:oMath><m:r><m:t>Q=1</m:t></m:r></m:oMath></m:oMathPara>
  </w:body>
</w:document>""",
    )

    assert docx_inline_math_protection(docx) == (1, 0)
    assert protect_docx_inline_math(docx) == 1
    assert docx_inline_math_protection(docx) == (1, 1)

    with zipfile.ZipFile(docx) as archive:
        document = minidom.parseString(archive.read("word/document.xml"))
    inline, display = document.getElementsByTagNameNS(
        "http://schemas.openxmlformats.org/officeDocument/2006/math", "oMath"
    )
    assert inline.getElementsByTagNameNS(
        "http://schemas.openxmlformats.org/officeDocument/2006/math", "noBreak"
    ).length == 1
    assert display.getElementsByTagNameNS(
        "http://schemas.openxmlformats.org/officeDocument/2006/math", "noBreak"
    ).length == 0

    protected_xml = document.toxml()
    assert protect_docx_inline_math(docx) == 0
    with zipfile.ZipFile(docx) as archive:
        assert minidom.parseString(archive.read("word/document.xml")).toxml() == protected_xml
