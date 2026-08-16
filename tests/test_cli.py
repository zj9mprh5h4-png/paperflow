from __future__ import annotations

import pytest

from paperflow import __version__, cli
from paperflow.cli import main
from paperflow.commands import PaperflowError


def test_cli_version_uses_installed_package_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"paperflow {__version__}"
    assert __version__ == "0.1.0.dev0"


def test_cli_help_lists_primary_workflows(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    for command in [
        "build",
        "open-items",
        "init-local",
        "review-start",
        "review-import",
        "word-baseline",
    ]:
        assert command in output


def test_doctor_help_lists_machine_readable_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["doctor", "--help"])

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "--format {text,json}" in output


def test_expected_workflow_error_returns_two(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["clean"]) == 2
    assert "without --yes" in capsys.readouterr().err


def test_clean_preserves_archive_unless_explicitly_included(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = tmp_path / "build"
    archive = build / "archived"
    archive.mkdir(parents=True)
    (build / ".gitkeep").write_text("", encoding="utf-8")
    (build / "paper_current.docx").write_bytes(b"current")
    (archive / "paper_20260807T031245Z.docx").write_bytes(b"archive")
    monkeypatch.setattr(cli, "find_project_root", lambda: tmp_path)

    assert cli.clean_build(yes=True) == 0
    assert not (build / "paper_current.docx").exists()
    assert (archive / "paper_20260807T031245Z.docx").is_file()

    assert cli.clean_build(yes=True, include_archive=True) == 0
    assert not archive.exists()


def test_clean_refuses_to_delete_an_archive_directory_holding_other_content(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "paperflow.yml").write_text(
        "schema_version: 1\nbuild:\n  archive_dir: manuscript\n",
        encoding="utf-8",
    )
    build = tmp_path / "build"
    manuscript = tmp_path / "manuscript"
    build.mkdir()
    manuscript.mkdir()
    (build / "paper_current.docx").write_bytes(b"current")
    (manuscript / "index.qmd").write_text("# Manuscript\n", encoding="utf-8")
    monkeypatch.setattr(cli, "find_project_root", lambda: tmp_path)

    with pytest.raises(PaperflowError, match="did not archive") as error:
        cli.clean_build(yes=True, include_archive=True)

    assert error.value.code == "clean.archive_not_dedicated"
    assert (manuscript / "index.qmd").is_file()
    assert (build / "paper_current.docx").is_file()
