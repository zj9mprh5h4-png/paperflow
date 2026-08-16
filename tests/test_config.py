from __future__ import annotations

from pathlib import Path

import pytest

from paperflow.commands import PaperflowError, executable, python_is_venv
from paperflow.config import load_config


def test_project_and_local_configuration_are_merged(tmp_path: Path) -> None:
    (tmp_path / "paperflow.yml").write_text(
        """
schema_version: 1
project:
  name: configured-project
paths:
  output_dir: output
word:
  protect_inline_math: false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".paperflow.local.yml").write_text(
        """
executables:
  quarto: tools/quarto.exe
word:
  reference_docx: templates/local.docx
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.project.name == "configured-project"
    assert config.paths.output_dir == (tmp_path / "output").resolve()
    assert config.word.protect_inline_math is False
    assert config.word.reference_docx == (tmp_path / "templates" / "local.docx").resolve()
    assert config.executables.quarto == "tools/quarto.exe"


def test_unknown_configuration_key_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "paperflow.yml").write_text(
        "schema_version: 1\nproject:\n  unknown: value\n",
        encoding="utf-8",
    )

    with pytest.raises(PaperflowError, match="Unknown project") as error:
        load_config(tmp_path)

    assert error.value.code == "config.unknown_keys"
    assert "paperflow.yml" in error.value.remediation[0]


def test_output_path_cannot_escape_project(tmp_path: Path) -> None:
    (tmp_path / "paperflow.yml").write_text(
        "schema_version: 1\npaths:\n  output_dir: ../outside\n",
        encoding="utf-8",
    )

    with pytest.raises(PaperflowError, match="must stay inside") as error:
        load_config(tmp_path)

    assert error.value.code == "config.path_outside_project"
    assert "project-relative path" in error.value.remediation[0]


def test_word_review_auto_apply_cannot_be_enabled(tmp_path: Path) -> None:
    (tmp_path / "paperflow.yml").write_text(
        "schema_version: 1\nreview:\n  auto_apply_word_changes: true\n",
        encoding="utf-8",
    )

    with pytest.raises(PaperflowError, match="must remain false") as error:
        load_config(tmp_path)

    assert error.value.code == "config.review_auto_apply"
    assert "review.auto_apply_word_changes: false" in error.value.remediation[0]


def test_local_executable_override_is_resolved(tmp_path: Path) -> None:
    tool = tmp_path / "tools" / "quarto.exe"
    tool.parent.mkdir()
    tool.write_bytes(b"tool")
    (tmp_path / ".paperflow.local.yml").write_text(
        "executables:\n  quarto: tools/quarto.exe\n",
        encoding="utf-8",
    )

    assert executable("quarto", root=tmp_path) == str(tool.resolve())


def test_python_is_venv_uses_the_environment_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("paperflow.commands.sys.prefix", str(tmp_path / ".venv"))
    monkeypatch.setattr("paperflow.commands.sys.base_prefix", str(tmp_path / "python"))

    assert python_is_venv(tmp_path)


def test_python_is_venv_rejects_the_base_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = str(tmp_path / ".venv")
    monkeypatch.setattr("paperflow.commands.sys.prefix", prefix)
    monkeypatch.setattr("paperflow.commands.sys.base_prefix", prefix)

    assert not python_is_venv(tmp_path)
