from __future__ import annotations

from pathlib import Path

from paperflow import open_items
from paperflow.config import load_config


def write_sources(root: Path) -> None:
    manuscript = root / "manuscript"
    (manuscript / "archived").mkdir(parents=True)
    (manuscript / "section.md").write_text(
        "# Methods\n\n## Assay\n\n[[OPEN: Add the verified assay duration.]]\n",
        encoding="utf-8",
    )
    (manuscript / "manuscript_formatting_rules.md").write_text(
        "# Rules\n\nExample: [[OPEN: This is syntax documentation only.]]\n",
        encoding="utf-8",
    )
    (manuscript / "archived" / "old.md").write_text(
        "[[OPEN: Archived item.]]\n",
        encoding="utf-8",
    )


def test_open_items_scan_uses_configured_sources_and_exclusions(tmp_path: Path) -> None:
    write_sources(tmp_path)
    config = load_config(tmp_path)

    items = open_items.collect_open_items(config)

    assert len(items) == 1
    assert items[0].text == "Add the verified assay duration."
    assert items[0].group == "Methods / Assay"


def test_open_items_build_writes_markdown_and_docx(
    tmp_path: Path,
    monkeypatch,
) -> None:
    write_sources(tmp_path)
    config = load_config(tmp_path)

    def fake_stage(
        source: Path,
        output: Path,
        *,
        config: object,
        execute: bool,
    ) -> Path:
        del config
        assert execute is False
        assert "Add the verified assay duration" in source.read_text(encoding="utf-8")
        assert "paperflow-project" in source.read_text(encoding="utf-8")
        staged = tmp_path / "staged.docx"
        staged.write_bytes(b"docx")
        return staged

    def fake_publish(staged_outputs: dict[Path, Path], **kwargs: object) -> None:
        del kwargs
        for output, staged in staged_outputs.items():
            output.parent.mkdir(parents=True, exist_ok=True)
            staged.replace(output)

    monkeypatch.setattr(open_items, "stage_qmd_to_docx", fake_stage)
    monkeypatch.setattr(open_items, "publish_docx_outputs", fake_publish)

    result = open_items.build_open_items(config)

    assert result.count == 1
    assert result.markdown.exists()
    assert result.docx.read_bytes() == b"docx"
    assert not (config.paths.work_dir / "open_items.qmd").exists()
