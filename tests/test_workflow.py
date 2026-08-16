from __future__ import annotations

from pathlib import Path

from paperflow import workflow
from paperflow.config import load_config
from paperflow.open_items import StagedOpenItems


def test_build_stages_all_docx_outputs_before_one_publication(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manuscript_source = tmp_path / "manuscript" / "index.qmd"
    manuscript_source.parent.mkdir()
    manuscript_source.write_text("# Manuscript\n", encoding="utf-8")
    config = load_config(tmp_path)
    staged_manuscript = tmp_path / ".work" / "staged-manuscript.docx"
    staged_open_items = tmp_path / ".work" / "staged-open-items.docx"
    staged_manuscript.parent.mkdir()
    staged_manuscript.write_bytes(b"manuscript")
    staged_open_items.write_bytes(b"open items")
    calls: list[dict[Path, Path]] = []

    monkeypatch.setattr(workflow, "run_pre_render_hook", lambda *_args: None)
    monkeypatch.setattr(
        workflow,
        "stage_qmd_to_docx",
        lambda *_args, **_kwargs: staged_manuscript,
    )
    monkeypatch.setattr(
        workflow,
        "stage_open_items",
        lambda _config: StagedOpenItems(
            count=2,
            markdown=config.open_items.output_markdown,
            docx=staged_open_items,
        ),
    )

    def fake_publish(staged_outputs: dict[Path, Path], **kwargs: object) -> None:
        del kwargs
        calls.append(dict(staged_outputs))
        for output, staged in staged_outputs.items():
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(staged.read_bytes())

    monkeypatch.setattr(workflow, "publish_docx_outputs", fake_publish)

    result = workflow.build_project(config)

    assert calls == [
        {
            config.manuscript_output: staged_manuscript,
            config.open_items.output_docx: staged_open_items,
        }
    ]
    assert result.manuscript.read_bytes() == b"manuscript"
    assert result.open_items is not None
    assert result.open_items.docx.read_bytes() == b"open items"
    assert not staged_manuscript.exists()
    assert not staged_open_items.exists()
