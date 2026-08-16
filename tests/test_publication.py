from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

from paperflow import publication
from paperflow.commands import PaperflowError
from paperflow.config import load_config


def minimal_docx(path: Path, marker: str = "document") -> None:
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships '
        'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{marker}</w:t></w:r></w:p></w:body></w:document>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document)


def custom_properties(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("docProps/custom.xml"))
    return {
        prop.get("name", ""): prop[0].text or ""
        for prop in root
        if prop.get("name", "").startswith("Paperflow")
    }


def test_publish_embeds_shared_provenance_and_archives_original_build_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_config(tmp_path)
    manuscript = config.manuscript_output
    open_items = config.open_items.output_docx
    for current in (manuscript, open_items):
        minimal_docx(current, "old")
        publication.embed_docx_build_metadata(
            current,
            {"PaperflowBuildUTC": "2026-08-07T03:12:45Z"},
        )

    staged_manuscript = tmp_path / ".work" / "manuscript.docx"
    staged_open_items = tmp_path / ".work" / "open-items.docx"
    minimal_docx(staged_manuscript, "new manuscript")
    minimal_docx(staged_open_items, "new open items")
    metadata = {
        "PaperflowBuildUTC": "2026-08-08T04:13:46Z",
        "PaperflowSourceCommit": "abc123",
        "PaperflowSourceDirty": "false",
        "PaperflowVersion": "0.1.0.dev0",
        "PaperflowQuartoVersion": "1.10.18",
    }
    monkeypatch.setattr(publication, "build_metadata", lambda *_args: metadata)

    publication.publish_docx_outputs(
        {
            manuscript: staged_manuscript,
            open_items: staged_open_items,
        },
        config=config,
    )

    assert custom_properties(manuscript) == metadata
    assert custom_properties(open_items) == metadata
    assert (config.build.archive_dir / "paper_20260807T031245Z.docx").is_file()
    assert (config.build.archive_dir / "open_items_20260807T031245Z.docx").is_file()
    with zipfile.ZipFile(manuscript) as archive:
        assert b"new manuscript" in archive.read("word/document.xml")


def test_archive_collision_uses_sequence_suffix(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    current = config.manuscript_output
    minimal_docx(current, "old")
    publication.embed_docx_build_metadata(
        current,
        {"PaperflowBuildUTC": "2026-08-07T03:12:45Z"},
    )
    config.build.archive_dir.mkdir(parents=True)
    existing = config.build.archive_dir / "paper_20260807T031245Z.docx"
    existing.write_bytes(b"existing archive")

    candidate = publication._available_archive_path(current, config.build.archive_dir, set())

    assert candidate == config.build.archive_dir / "paper_20260807T031245Z_01.docx"


def test_legacy_default_outputs_are_migrated_to_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_config(tmp_path)
    legacy_manuscript = config.paths.output_dir / "paper.docx"
    legacy_open_items = config.paths.output_dir / "open_items.docx"
    for legacy in (legacy_manuscript, legacy_open_items):
        minimal_docx(legacy, "legacy")
        publication.embed_docx_build_metadata(
            legacy,
            {"PaperflowBuildUTC": "2026-08-06T02:11:34Z"},
        )
    staged_manuscript = tmp_path / ".work" / "paper.docx"
    staged_open_items = tmp_path / ".work" / "open.docx"
    minimal_docx(staged_manuscript, "new")
    minimal_docx(staged_open_items, "new")
    monkeypatch.setattr(
        publication,
        "build_metadata",
        lambda *_args: {"PaperflowBuildUTC": "2026-08-08T04:13:46Z"},
    )

    publication.publish_docx_outputs(
        {
            config.manuscript_output: staged_manuscript,
            config.open_items.output_docx: staged_open_items,
        },
        config=config,
    )

    assert not legacy_manuscript.exists()
    assert not legacy_open_items.exists()
    assert (config.build.archive_dir / "paper_20260806T021134Z.docx").is_file()
    assert (config.build.archive_dir / "open_items_20260806T021134Z.docx").is_file()


def test_locked_output_says_existing_document_will_be_archived(tmp_path: Path) -> None:
    locked = tmp_path / "paper_current.docx"
    locked.mkdir()

    with pytest.raises(PaperflowError) as error:
        publication._assert_outputs_replaceable([locked], archive_previous=True)

    message = str(error.value)
    assert "Close the document in Microsoft Word" in message
    assert "will be archived" in message
    assert "will not be deleted" in message


def test_failed_group_publication_restores_every_current_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "paperflow.yml").write_text(
        "schema_version: 1\nbuild:\n  embed_provenance: false\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    destinations = (config.manuscript_output, config.open_items.output_docx)
    staged = (tmp_path / ".work" / "paper.docx", tmp_path / ".work" / "open.docx")
    for index, path in enumerate(destinations):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"old-{index}".encode())
    for index, path in enumerate(staged):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"new-{index}".encode())

    original_replace = Path.replace

    def fail_second_promotion(source: Path, target: Path) -> Path:
        if Path(target) == destinations[1] and source.name.startswith(
            f".{destinations[1].name}."
        ):
            raise PermissionError("simulated Word lock")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_second_promotion)

    with pytest.raises(PaperflowError, match="will not be deleted"):
        publication.publish_docx_outputs(
            dict(zip(destinations, staged, strict=True)),
            config=config,
        )

    assert destinations[0].read_bytes() == b"old-0"
    assert destinations[1].read_bytes() == b"old-1"
    assert not list(config.build.archive_dir.glob("*.docx"))
