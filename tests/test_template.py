from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from paperflow.commands import PaperflowError
from paperflow.template import (
    ExtractedTemplateBody,
    extract_template_body,
    reference_docx_styles,
    sanitise_reference_docx,
    template_sections,
)
from paperflow.validation import docx_reference_status

STYLES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    b'<w:style w:type="paragraph" w:styleId="Author"><w:name w:val="Author"/></w:style>'
    b'<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
    b'<w:style w:type="paragraph" w:styleId="FrontiersAuthor">'
    b'<w:name w:val="Frontiers Author"/></w:style>'
    b'<w:style w:type="paragraph" w:styleId="FrontiersAffiliation">'
    b'<w:name w:val="Frontiers Affiliation"/></w:style>'
    b'<w:style w:type="character" w:styleId="FrontiersMarker">'
    b'<w:name w:val="Frontiers Marker"/></w:style>'
    b'<w:style w:type="paragraph" w:styleId="LegacyThing">'
    b'<w:name w:val="Legacy Thing"/><w:semiHidden/></w:style>'
    b'<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style>'
    b"</w:styles>"
)

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


# Shape taken from a real Frontiers template: the picture is embedded, but both
# alt-text attributes carry the original author's file path.
LOGO_HEADER = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    b'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    b'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
    b"<w:p><w:r><w:drawing><wp:inline>"
    b'<wp:docPr id="6" name="Picture 6" '
    b'descr="C:\\Users\\Elaine.Scott\\Documents\\LaTex\\Templates\\logo1.jpg"/>'
    b'<pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="Picture 1" '
    b'descr="Journal masthead, C:\\Users\\Elaine.Scott\\Documents\\logo1.jpg"/>'
    b"</pic:nvPicPr></pic:pic>"
    b"</wp:inline></w:drawing></w:r></w:p></w:hdr>"
)


def test_sanitize_strips_file_paths_from_image_alt_text(tmp_path: Path) -> None:
    source = tmp_path / "Journal.docx"
    publisher_template(source)
    with zipfile.ZipFile(source, "a") as archive:
        archive.writestr("word/header3.xml", LOGO_HEADER)
    target = tmp_path / "reference.local.docx"

    result = sanitise_reference_docx(source=source, target=target)

    assert "file paths in image alt text" in result.removed
    assert result.remaining == ()
    with zipfile.ZipFile(target) as archive:
        header = archive.read("word/header3.xml")
    assert b"Elaine.Scott" not in header
    assert b'name="Picture 6"' in header
    # A real description next to the path survives; only the path is taken out.
    assert b'descr="Journal masthead"' in header
    assert b'descr=""' in header


def test_sanitize_keeps_alt_text_that_carries_no_path(tmp_path: Path) -> None:
    source = tmp_path / "Journal.docx"
    publisher_template(source)
    with zipfile.ZipFile(source, "a") as archive:
        archive.writestr(
            "word/header4.xml",
            b'<w:hdr xmlns:w="w"><wp:docPr descr="Frontiers journal logo"/></w:hdr>',
        )
    target = tmp_path / "reference.local.docx"

    sanitise_reference_docx(source=source, target=target)

    with zipfile.ZipFile(target) as archive:
        assert b'descr="Frontiers journal logo"' in archive.read("word/header4.xml")


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


def test_template_styles_separates_pandoc_styles_from_custom_style_names(
    tmp_path: Path,
) -> None:
    docx = tmp_path / "journal.docx"
    publisher_template(docx)
    with zipfile.ZipFile(docx, "a") as archive:
        archive.writestr("word/styles.xml", STYLES)

    styles = {style.name: style for style in reference_docx_styles(docx)}

    assert styles["Author"].applied_by_pandoc
    assert styles["Author"].kind == "paragraph"
    # Word stores the built-in heading under a lower-case name; it is not a custom style,
    # but Paperflow reports the name as written so it can be used verbatim.
    assert not styles["heading 1"].applied_by_pandoc
    assert not styles["Frontiers Affiliation"].applied_by_pandoc
    assert styles["Frontiers Marker"].kind == "character"
    assert styles["Legacy Thing"].hidden
    assert not styles["Frontiers Affiliation"].hidden
    # Table styles cannot be requested with custom-style and are left out.
    assert "Table Grid" not in styles


BODY = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    b"<w:body>"
    b'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
    b"<w:r><w:t>Article Title</w:t></w:r></w:p>"
    b'<w:p><w:pPr><w:pStyle w:val="FrontiersAuthor"/></w:pPr>'
    b"<w:r><w:t>First Author</w:t></w:r>"
    b'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>1</w:t></w:r>'
    b"<w:r><w:t>, Second Author</w:t></w:r>"
    b'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r>'
    b"<w:r><w:t>*</w:t></w:r></w:p>"
    b'<w:p><w:pPr><w:pStyle w:val="FrontiersAffiliation"/></w:pPr>'
    b"<w:r><w:t>Laboratory X</w:t></w:r><w:r><w:br/><w:t>City X</w:t></w:r></w:p>"
    b'<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
    b"<w:r><w:t>Plain paragraph</w:t></w:r></w:p>"
    b"<w:p></w:p>"
    b'<w:p><w:r><w:drawing/></w:r><w:r><w:t>Logo caption</w:t></w:r></w:p>'
    b"<w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    b"</w:body></w:document>"
)


def template_with_body(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")
        archive.writestr("word/document.xml", BODY)
        archive.writestr("word/styles.xml", STYLES)


def test_front_matter_extraction_reproduces_styles_and_superscripts(tmp_path: Path) -> None:
    docx = tmp_path / "journal.docx"
    template_with_body(docx)

    extracted = extract_template_body(docx)

    assert extracted.markdown == (
        "# Article Title\n"
        "\n"
        '::: {custom-style="Frontiers Author"}\n'
        "First Author^1^, Second Author^2^\\*\n"
        ":::\n"
        "\n"
        '::: {custom-style="Frontiers Affiliation"}\n'
        "Laboratory X\n"
        "City X\n"
        ":::\n"
        "\n"
        "Plain paragraph\n"
        "\n"
        "Logo caption\n"
    )
    assert extracted.styles == ("Frontiers Author", "Frontiers Affiliation")
    assert extracted.skipped_tables == 1
    assert extracted.skipped_drawings == 1


# Shapes taken from a real Frontiers template: a hyperlink mid-sentence, and an
# affiliation marker immediately followed by a superscript asterisk.
LINKED_BODY = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    b"<w:body>"
    b"<w:p><w:r><w:t>Please refer to </w:t></w:r>"
    b"<w:hyperlink><w:r><w:t>the author guidelines</w:t></w:r></w:hyperlink>"
    b"<w:r><w:t> for details.</w:t></w:r></w:p>"
    b'<w:p><w:pPr><w:pStyle w:val="FrontiersAuthor"/></w:pPr>'
    b"<w:r><w:t>Second Author</w:t></w:r>"
    b'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r>'
    b'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>*</w:t></w:r>'
    b"</w:p>"
    b"</w:body></w:document>"
)


def test_extraction_keeps_hyperlink_text_and_merges_adjacent_superscripts(
    tmp_path: Path,
) -> None:
    docx = tmp_path / "journal.docx"
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")
        archive.writestr("word/document.xml", LINKED_BODY)
        archive.writestr("word/styles.xml", STYLES)

    markdown = extract_template_body(docx).markdown

    # Runs inside w:hyperlink are not direct children of the paragraph; collecting only
    # direct children silently dropped the link text.
    assert "Please refer to the author guidelines for details." in markdown
    # One superscript group, not '^2^^\\*^'.
    assert "Second Author^2\\*^" in markdown


SPLIT_BODY = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    b"<w:body>"
    b'<w:p><w:pPr><w:pStyle w:val="FrontiersAuthor"/></w:pPr>'
    b"<w:r><w:t>First Author</w:t></w:r></w:p>"
    b'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
    b"<w:r><w:t>Introduction</w:t></w:r></w:p>"
    b"<w:p><w:r><w:t>Intro body</w:t></w:r></w:p>"
    b'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
    b"<w:r><w:t>Conflict of Interest / Funding!</w:t></w:r></w:p>"
    b"<w:p><w:r><w:t>Statement body</w:t></w:r></w:p>"
    b"</w:body></w:document>"
)


def test_splitting_writes_one_file_per_top_level_heading(tmp_path: Path) -> None:
    docx = tmp_path / "journal.docx"
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")
        archive.writestr("word/document.xml", SPLIT_BODY)
        archive.writestr("word/styles.xml", STYLES)

    extracted = extract_template_body(docx)
    sections = template_sections(extracted)

    assert extracted.top_level_headings == 2
    assert [section.filename for section in sections] == [
        "00-front-matter.md",
        "01-introduction.md",
        "02-conflict-of-interest-funding.md",
    ]
    # Everything before the first heading has no heading of its own and would be lost.
    assert sections[0].markdown == (
        '::: {custom-style="Frontiers Author"}\nFirst Author\n:::\n'
    )
    assert sections[1].markdown == "# Introduction\n\nIntro body\n"
    assert sections[2].markdown == "# Conflict of Interest / Funding!\n\nStatement body\n"


def test_splitting_a_body_without_headings_yields_one_file(tmp_path: Path) -> None:
    docx = tmp_path / "journal.docx"
    template_with_body(docx)

    extracted = extract_template_body(docx)
    extracted_without_headings = ExtractedTemplateBody(
        blocks=tuple(block for block in extracted.blocks if block.heading_level is None),
        styles=extracted.styles,
        skipped_tables=0,
        skipped_drawings=0,
    )
    sections = template_sections(extracted_without_headings)

    assert extracted_without_headings.top_level_headings == 0
    assert [section.filename for section in sections] == ["00-front-matter.md"]


def test_front_matter_extraction_rejects_a_styles_only_reference(tmp_path: Path) -> None:
    docx = tmp_path / "journal.docx"
    publisher_template(docx)
    with zipfile.ZipFile(docx, "a") as archive:
        archive.writestr("word/styles.xml", STYLES)

    assert extract_template_body(docx).markdown == ""


def test_template_styles_rejects_a_missing_reference(tmp_path: Path) -> None:
    with pytest.raises(PaperflowError, match="does not exist") as error:
        reference_docx_styles(tmp_path / "absent.docx")

    assert error.value.code == "template_styles.missing"


def test_template_styles_rejects_a_file_without_styles(tmp_path: Path) -> None:
    docx = tmp_path / "journal.docx"
    publisher_template(docx)

    with pytest.raises(PaperflowError, match="Could not read the styles") as error:
        reference_docx_styles(docx)

    assert error.value.code == "template_styles.unreadable"
    assert "saved as .docx" in " ".join(error.value.remediation)


def test_sanitize_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PaperflowError, match="does not exist") as error:
        sanitise_reference_docx(source=tmp_path / "absent.docx", target=tmp_path / "out.docx")

    assert error.value.code == "sanitize_template.source_missing"
