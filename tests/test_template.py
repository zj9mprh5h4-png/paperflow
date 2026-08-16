from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from paperflow.commands import PaperflowError
from paperflow.template import sanitise_reference_docx
from paperflow.validation import docx_reference_status

ATTACHED_TEMPLATE_RELS = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    b'relationships/attachedTemplate" '
    b'Target="file:///C:\\Users\\publisher\\Templates\\Journal.dotx" '
    b'TargetMode="External"/></Relationships>'
)
SETTINGS = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    b'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    b'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
    b'mc:Ignorable="w14">'
    b'<w:attachedTemplate r:id="rId1"/>'
    b"<w:defaultTabStop w:val=\"708\"/></w:settings>"
)
APP_PROPERTIES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b"<Properties><Application>Microsoft Office Word</Application>"
    b"<Company>Example Publisher Ltd</Company><Manager>Head of Production</Manager>"
    b"<HyperlinkBase>C:\\Users\\publisher\\Figures</HyperlinkBase></Properties>"
)
CORE_PROPERTIES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
    b'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">'
    b"<dc:creator>Jordan Publisher</dc:creator>"
    b"<cp:lastModifiedBy>Jordan Publisher</cp:lastModifiedBy>"
    b"</cp:coreProperties>"
)


def publisher_template(path: Path, *, linked_image: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")
        archive.writestr("word/document.xml", b'<w:document xmlns:w="w"><w:body/></w:document>')
        archive.writestr("word/settings.xml", SETTINGS)
        archive.writestr("word/_rels/settings.xml.rels", ATTACHED_TEMPLATE_RELS)
        archive.writestr("docProps/app.xml", APP_PROPERTIES)
        archive.writestr("docProps/core.xml", CORE_PROPERTIES)
        if linked_image:
            archive.writestr(
                "word/_rels/document.xml.rels",
                b'<Relationships><Relationship Id="rId9" Type="http://schemas.'
                b'openxmlformats.org/officeDocument/2006/relationships/image" '
                b'Target="C:\\Users\\publisher\\figure1.png" TargetMode="External"/>'
                b"</Relationships>",
            )


def test_sanitize_repairs_a_publisher_template_and_leaves_the_source_alone(
    tmp_path: Path,
) -> None:
    source = tmp_path / "original" / "Journal.docx"
    publisher_template(source)
    original = source.read_bytes()
    target = tmp_path / "templates" / "reference.local.docx"

    result = sanitise_reference_docx(source=source, target=target, force=False)

    assert result.path == target
    assert set(result.removed) == {
        "attached document template",
        "hyperlink base",
        "company name",
        "manager name",
        "author name",
        "last-modified-by name",
    }
    assert result.remaining == ()
    assert docx_reference_status(target).path_safe
    assert source.read_bytes() == original


def test_sanitize_keeps_the_rest_of_the_package_byte_identical(tmp_path: Path) -> None:
    source = tmp_path / "Journal.docx"
    publisher_template(source)
    target = tmp_path / "reference.local.docx"

    sanitise_reference_docx(source=source, target=target)

    with zipfile.ZipFile(source) as before, zipfile.ZipFile(target) as after:
        assert before.namelist() == after.namelist()
        assert before.read("word/document.xml") == after.read("word/document.xml")
        settings = after.read("word/settings.xml")
    # The mc:Ignorable prefix list must survive; renaming prefixes here breaks Word.
    assert b'mc:Ignorable="w14"' in settings
    assert b'w:defaultTabStop w:val="708"' in settings
    assert b"attachedTemplate" not in settings


def test_sanitize_reports_paths_it_cannot_repair(tmp_path: Path) -> None:
    source = tmp_path / "Journal.docx"
    publisher_template(source, linked_image=True)
    target = tmp_path / "reference.local.docx"

    result = sanitise_reference_docx(source=source, target=target)

    assert "attached document template" in result.removed
    assert result.remaining == ("word/_rels/document.xml.rels (external relationship)",)
    assert not docx_reference_status(target).path_safe


def test_sanitize_refuses_to_replace_an_existing_target_without_force(tmp_path: Path) -> None:
    source = tmp_path / "Journal.docx"
    publisher_template(source)
    target = tmp_path / "reference.local.docx"
    target.write_bytes(b"already here")

    with pytest.raises(PaperflowError, match="already exists") as error:
        sanitise_reference_docx(source=source, target=target)

    assert error.value.code == "sanitize_template.target_exists"
    assert target.read_bytes() == b"already here"

    assert sanitise_reference_docx(source=source, target=target, force=True).path == target
    assert target.read_bytes() != b"already here"


def test_sanitize_rejects_a_file_that_is_not_a_docx(tmp_path: Path) -> None:
    source = tmp_path / "Journal.dotx"
    source.write_text("not a zip archive", encoding="utf-8")

    with pytest.raises(PaperflowError, match="not a readable DOCX") as error:
        sanitise_reference_docx(source=source, target=tmp_path / "out.docx")

    assert error.value.code == "sanitize_template.source_invalid"
    assert "saved as .docx first" in " ".join(error.value.remediation)


def test_sanitize_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PaperflowError, match="does not exist") as error:
        sanitise_reference_docx(source=tmp_path / "absent.docx", target=tmp_path / "out.docx")

    assert error.value.code == "sanitize_template.source_missing"
