from __future__ import annotations

from pathlib import Path

from paperflow.sources import custom_style_requests, rendered_sources


def test_rendered_sources_follows_includes_transitively(tmp_path: Path) -> None:
    entry = tmp_path / "index.qmd"
    entry.write_text(
        "---\ntitle: T\n---\n\n{{< include sections/front-matter.md >}}\n"
        "{{< include sections/main-text.md >}}\n"
        "{{< include sections/absent.md >}}\n",
        encoding="utf-8",
    )
    sections = tmp_path / "sections"
    sections.mkdir()
    (sections / "front-matter.md").write_text("# Front\n", encoding="utf-8")
    (sections / "main-text.md").write_text("{{< include nested.md >}}\n", encoding="utf-8")
    (sections / "nested.md").write_text("Nested body\n", encoding="utf-8")

    found = rendered_sources(entry)

    assert found == (
        entry.resolve(),
        (sections / "front-matter.md").resolve(),
        (sections / "main-text.md").resolve(),
        (sections / "nested.md").resolve(),
    )


def test_rendered_sources_survives_an_include_cycle(tmp_path: Path) -> None:
    first = tmp_path / "a.qmd"
    second = tmp_path / "b.md"
    first.write_text("{{< include b.md >}}\n", encoding="utf-8")
    second.write_text("{{< include a.qmd >}}\n", encoding="utf-8")

    assert rendered_sources(first) == (first.resolve(), second.resolve())


def test_custom_style_requests_report_name_and_location(tmp_path: Path) -> None:
    source = tmp_path / "front-matter.md"
    source.write_text(
        '::: {custom-style="Frontiers Author"}\n'
        "First Author\n"
        ":::\n"
        "\n"
        "Inline [marker]{custom-style='Frontiers Marker'} in a paragraph.\n",
        encoding="utf-8",
    )

    requests = custom_style_requests((source,))

    assert [(item.name, item.line) for item in requests] == [
        ("Frontiers Author", 1),
        ("Frontiers Marker", 5),
    ]
    assert all(item.source == source for item in requests)
