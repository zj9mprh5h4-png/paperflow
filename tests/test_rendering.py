from __future__ import annotations

from pathlib import Path

import pytest

from paperflow import rendering
from paperflow.commands import PaperflowError
from paperflow.config import load_config


def test_render_finds_quarto_output_in_project_output_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "manuscript" / "index.qmd"
    source.parent.mkdir()
    source.write_text("# Test\n", encoding="utf-8")
    output = tmp_path / "build" / "paper.docx"
    config = load_config(tmp_path)
    calls: list[list[str]] = []

    monkeypatch.setattr(rendering, "require_tool", lambda *args, **kwargs: "quarto")
    monkeypatch.setattr(rendering, "docx_core_files_present", lambda path: True)
    monkeypatch.setattr(rendering, "docx_absolute_path_locations", lambda path: ())
    monkeypatch.setattr(rendering, "protect_docx_inline_math", lambda path: 0)

    def fake_publish(staged_outputs: dict[Path, Path], **kwargs: object) -> None:
        del kwargs
        for destination, staged in staged_outputs.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged.replace(destination)

    monkeypatch.setattr(rendering, "publish_docx_outputs", fake_publish)

    def fake_run_command(args: list[str], **kwargs) -> object:
        calls.append(args)
        name = args[args.index("--output") + 1]
        target = tmp_path / "quarto-output" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x" * 1001)
        return object()

    monkeypatch.setattr(rendering, "run_command", fake_run_command)

    assert rendering.render_qmd_to_docx(source, output, config=config) == output
    assert output.read_bytes() == b"x" * 1001
    assert "--output-dir" not in calls[0]
    metadata = calls[0].index("--metadata")
    assert calls[0][metadata + 1] == "lang:en"


def test_render_refuses_before_quarto_when_an_include_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(rendering, "require_tool", lambda *args, **kwargs: "quarto")
    source = tmp_path / "manuscript" / "index.qmd"
    source.parent.mkdir()
    (source.parent / "sections").mkdir()
    (source.parent / "sections" / "present.md").write_text("Body\n", encoding="utf-8")
    source.write_text(
        "---\ntitle: T\n---\n\n"
        "{{< include sections/present.md >}}\n"
        "{{< include sections/deleted.md >}}\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)

    # Quarto reports this as an uncaught JavaScript error with a stack trace, so the
    # check has to happen before the renderer is ever called.
    with pytest.raises(PaperflowError, match="includes files that do not exist") as error:
        rendering.stage_qmd_to_docx(source, tmp_path / "build" / "paper.docx", config=config)

    assert error.value.code == "render.missing_include"
    assert "manuscript/sections/deleted.md" in str(error.value)
    assert "manuscript/sections/present.md" not in str(error.value)
    assert "sections-sync" in " ".join(error.value.remediation)


def test_invalid_render_does_not_replace_previous_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "manuscript" / "index.qmd"
    source.parent.mkdir()
    source.write_text("# Test\n", encoding="utf-8")
    output = tmp_path / "build" / "paper.docx"
    output.parent.mkdir()
    output.write_bytes(b"previous valid output")
    config = load_config(tmp_path)

    monkeypatch.setattr(rendering, "require_tool", lambda *args, **kwargs: "quarto")
    monkeypatch.setattr(rendering, "docx_core_files_present", lambda path: True)
    monkeypatch.setattr(
        rendering,
        "docx_absolute_path_locations",
        lambda path: ("word/header3.xml (embedded path)",),
    )
    monkeypatch.setattr(rendering, "protect_docx_inline_math", lambda path: 0)

    def fake_run_command(args: list[str], **kwargs) -> object:
        name = args[args.index("--output") + 1]
        rendered = tmp_path / "quarto-output" / name
        rendered.parent.mkdir(parents=True)
        rendered.write_bytes(b"unsafe" * 201)
        return object()

    monkeypatch.setattr(rendering, "run_command", fake_run_command)

    with pytest.raises(PaperflowError, match="absolute local path") as error:
        rendering.render_qmd_to_docx(source, output, config=config)

    assert output.read_bytes() == b"previous valid output"
    # The rejection has to name the offending part; the previous message named only the
    # output file, which says nothing about where the path came from.
    assert "word/header3.xml (embedded path)" in str(error.value)
    assert error.value.code == "render.absolute_path"
    assert "sanitize-template" in " ".join(error.value.remediation)
