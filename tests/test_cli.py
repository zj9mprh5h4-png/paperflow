from __future__ import annotations

import pytest

from paperflow import __version__
from paperflow.cli import main


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
    for command in ["build", "open-items", "review-start", "review-import", "word-baseline"]:
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
