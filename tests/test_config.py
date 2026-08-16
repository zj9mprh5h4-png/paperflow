from __future__ import annotations

from pathlib import Path

import pytest

from paperflow import config as config_module
from paperflow.commands import PaperflowError, executable, python_is_venv
from paperflow.config import load_config, write_local_config


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
    assert config.build.archive_previous is True
    assert config.build.archive_dir == (tmp_path / "build" / "archived").resolve()
    assert config.build.embed_provenance is True
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


def test_archive_directory_must_be_dedicated(tmp_path: Path) -> None:
    (tmp_path / "paperflow.yml").write_text(
        "schema_version: 1\nbuild:\n  archive_dir: build\n",
        encoding="utf-8",
    )

    with pytest.raises(PaperflowError, match="dedicated directory") as error:
        load_config(tmp_path)

    assert error.value.code == "config.archive_dir"


def test_current_docx_outputs_must_be_unique(tmp_path: Path) -> None:
    (tmp_path / "paperflow.yml").write_text(
        "schema_version: 1\n"
        "build:\n"
        "  manuscript_filename: paper_current.docx\n"
        "open_items:\n"
        "  output_docx: build/paper_current.docx\n",
        encoding="utf-8",
    )

    with pytest.raises(PaperflowError, match="must use different paths") as error:
        load_config(tmp_path)

    assert error.value.code == "config.duplicate_docx_output"


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


def test_init_local_records_only_executables_missing_from_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quarto = tmp_path / "tools" / "quarto.exe"
    quarto.parent.mkdir()
    quarto.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        config_module.shutil,
        "which",
        lambda name: None if name == "quarto" else f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        config_module,
        "executable",
        lambda name, *, root=None: str(quarto) if name == "quarto" else None,
    )

    result = write_local_config(
        tmp_path,
        reference_docx="templates/reference.local.docx",
    )

    assert result.path == tmp_path / ".paperflow.local.yml"
    assert result.executables == {
        "git": config_module.ON_PATH,
        "uv": config_module.ON_PATH,
        "quarto": quarto.resolve().as_posix(),
    }
    config = load_config(tmp_path)
    assert config.executables.quarto == quarto.resolve().as_posix()
    assert config.executables.git is None
    assert config.executables.uv is None
    assert config.word.reference_docx == (
        tmp_path / "templates" / "reference.local.docx"
    ).resolve()


def test_init_local_finds_a_quarto_installed_outside_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quarto = tmp_path / "Programs" / "Quarto" / "1.10.18" / "bin" / "quarto.exe"
    quarto.parent.mkdir(parents=True)
    quarto.write_text("", encoding="utf-8")
    monkeypatch.setattr(config_module.shutil, "which", lambda name: None)
    monkeypatch.setattr(config_module, "executable", lambda name, *, root=None: None)
    monkeypatch.setattr(
        config_module,
        "WELL_KNOWN_EXECUTABLES",
        {
            "git": (),
            "uv": (),
            "quarto": (str(tmp_path / "Programs" / "Quarto" / "*" / "bin" / "quarto.exe"),),
        },
    )

    result = write_local_config(tmp_path)

    assert result.executables["quarto"] == quarto.resolve().as_posix()
    assert result.executables["git"] == config_module.NOT_FOUND
    assert load_config(tmp_path).executables.quarto == quarto.resolve().as_posix()


def test_init_local_rejects_an_explicit_executable_that_does_not_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config_module.shutil, "which", lambda name: f"/usr/bin/{name}")

    with pytest.raises(PaperflowError, match="does not exist") as error:
        write_local_config(tmp_path, executables={"quarto": "tools/missing-quarto.exe"})

    assert error.value.code == "init_local.executable_missing"
    assert not (tmp_path / ".paperflow.local.yml").exists()


def test_init_local_refuses_to_replace_an_existing_file_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = tmp_path / ".paperflow.local.yml"
    original = "executables:\n  quarto: tools/quarto.exe\n"
    existing.write_text(original, encoding="utf-8")
    monkeypatch.setattr(config_module.shutil, "which", lambda name: f"/usr/bin/{name}")

    with pytest.raises(PaperflowError, match="already exists") as error:
        write_local_config(tmp_path)

    assert error.value.code == "init_local.exists"
    assert existing.read_text(encoding="utf-8") == original

    assert write_local_config(tmp_path, force=True).path == existing
    assert "paperflow init-local" in existing.read_text(encoding="utf-8")
    assert load_config(tmp_path).executables.quarto is None
