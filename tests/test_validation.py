from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from paperflow import validation
from paperflow.commands import CommandResult


def configure_doctor_environment(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
) -> None:
    monkeypatch.setattr(validation, "find_project_root", lambda: root)
    monkeypatch.setattr(validation, "python_is_venv", lambda _root: True)
    monkeypatch.setattr(
        validation,
        "executable",
        lambda name, root=None: f"/tools/{name}",
    )
    monkeypatch.setattr(
        validation,
        "git",
        lambda *args, **kwargs: CommandResult(
            args=["git", "rev-parse", "--show-toplevel"],
            returncode=0,
            stdout=str(root),
            stderr="",
        ),
    )

    def fake_run(args: list[str], **kwargs: object) -> CommandResult:
        output = "1.10.0" if args == ["quarto", "--version"] else "pandoc 3.8"
        return CommandResult(args=args, returncode=0, stdout=output, stderr="")

    monkeypatch.setattr(validation, "run_command", fake_run)


def test_doctor_json_reports_configuration_error_and_remediation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_doctor_environment(monkeypatch, tmp_path)
    (tmp_path / "paperflow.yml").write_text(
        "schema_version: 1\nproject:\n  unknown: value\n",
        encoding="utf-8",
    )

    assert validation.doctor(output_format="json") == 1

    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == 1
    assert report["ok"] is False
    configuration = next(check for check in report["checks"] if check["id"] == "configuration")
    assert configuration["status"] == "fail"
    assert configuration["error_code"] == "config.unknown_keys"
    assert configuration["remediation"] == [
        "Correct or remove the listed key(s) in paperflow.yml.",
        "Use docs/configuration.md for the supported schema_version 1 keys.",
    ]


def test_doctor_text_explains_how_to_restore_missing_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_doctor_environment(monkeypatch, tmp_path)

    assert validation.doctor() == 1

    output = capsys.readouterr().out
    assert "[FAIL] paperflow configuration file" in output
    assert "Fix: Restore paperflow.yml from the Paperflow template" in output
    assert "[FAIL] manuscript source" in output
    assert "Fix: Create the configured manuscript file" in output
    assert "[FAIL] formatting rules" in output


STYLES_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    b'<w:style w:type="paragraph" w:styleId="FrontiersAuthor">'
    b'<w:name w:val="Frontiers Author"/></w:style>'
    b'<w:style w:type="paragraph" w:styleId="FrontiersKeywords">'
    b'<w:name w:val="Frontiers Keywords"/></w:style>'
    b"</w:styles>"
)


def reference_project(tmp_path: Path, front_matter: str) -> None:
    """A project with a reference DOCX that defines two publisher styles."""
    reference = tmp_path / "templates" / "reference.local.docx"
    reference.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(reference, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")
        archive.writestr("word/document.xml", b'<w:document xmlns:w="w"><w:body/></w:document>')
        archive.writestr("word/styles.xml", STYLES_XML)
    (tmp_path / "paperflow.yml").write_text(
        "schema_version: 1\nword:\n  reference_docx: templates/reference.local.docx\n",
        encoding="utf-8",
    )
    manuscript = tmp_path / "manuscript"
    manuscript.mkdir(exist_ok=True)
    (manuscript / "manuscript_formatting_rules.md").write_text("Rules\n", encoding="utf-8")
    (manuscript / "index.qmd").write_text(
        "---\ntitle: T\n---\n\n{{< include sections/front-matter.md >}}\n",
        encoding="utf-8",
    )
    sections = manuscript / "sections"
    sections.mkdir(exist_ok=True)
    (sections / "front-matter.md").write_text(front_matter, encoding="utf-8")


def test_doctor_accepts_styles_the_reference_defines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_doctor_environment(monkeypatch, tmp_path)
    reference_project(
        tmp_path,
        '::: {custom-style="Frontiers Author"}\nFirst Author\n:::\n'
        '\n::: {custom-style="Frontiers Keywords"}\nKeywords: a, b\n:::\n',
    )

    validation.doctor(output_format="json")

    report = json.loads(capsys.readouterr().out)
    check = next(item for item in report["checks"] if item["id"] == "word.custom_styles")
    assert check["status"] == "ok"
    assert check["detail"] == "2 requested style(s) exist"


def test_doctor_reports_a_misspelled_style_with_the_nearest_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_doctor_environment(monkeypatch, tmp_path)
    reference_project(
        tmp_path,
        '::: {custom-style="Frontiers Authour"}\nFirst Author\n:::\n',
    )

    assert validation.doctor(output_format="json") == 1

    report = json.loads(capsys.readouterr().out)
    check = next(item for item in report["checks"] if item["id"] == "word.custom_styles")
    assert check["status"] == "fail"
    assert check["error_code"] == "word.custom_style_missing"
    assert "'Frontiers Authour'" in check["detail"]
    assert "manuscript/sections/front-matter.md:1" in check["detail"]
    assert "Did you mean 'Frontiers Author'?" in check["remediation"][0]
    assert "template-styles" in " ".join(check["remediation"])


def test_doctor_names_the_environment_that_is_active_instead(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_doctor_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(validation, "python_is_venv", lambda _root: False)
    other = tmp_path / "other-project" / ".venv"
    monkeypatch.setattr(validation.sys, "prefix", str(other))
    monkeypatch.setattr(validation.sys, "base_prefix", str(tmp_path / "python"))

    validation.doctor(output_format="json")

    report = json.loads(capsys.readouterr().out)
    check = next(item for item in report["checks"] if item["id"] == "python.venv")
    assert check["status"] == "fail"
    assert str(other.resolve()) in check["detail"]
    assert str((tmp_path / ".venv").resolve()) in check["detail"]
    assert "uv run" in check["remediation"][0]


def test_doctor_distinguishes_no_environment_from_the_wrong_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_doctor_environment(monkeypatch, tmp_path)
    monkeypatch.setattr(validation, "python_is_venv", lambda _root: False)
    monkeypatch.setattr(validation.sys, "prefix", str(tmp_path / "python"))
    monkeypatch.setattr(validation.sys, "base_prefix", str(tmp_path / "python"))

    validation.doctor(output_format="json")

    report = json.loads(capsys.readouterr().out)
    check = next(item for item in report["checks"] if item["id"] == "python.venv")
    assert check["detail"].startswith("no virtual environment is active")
    assert "uv sync --frozen --extra dev" in check["remediation"][0]


def test_doctor_reports_the_active_environment_when_it_is_correct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_doctor_environment(monkeypatch, tmp_path)

    validation.doctor(output_format="json")

    report = json.loads(capsys.readouterr().out)
    check = next(item for item in report["checks"] if item["id"] == "python.venv")
    assert check["status"] == "ok"
    assert check["detail"] == str((tmp_path / ".venv").resolve())
