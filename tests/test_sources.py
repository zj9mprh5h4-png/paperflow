from __future__ import annotations

from pathlib import Path

from paperflow.sources import (
    SECTIONS_BEGIN,
    SECTIONS_END,
    custom_style_requests,
    find_section_block,
    include_targets,
    render_section_block,
    rendered_sources,
    replace_section_block,
    section_files,
)


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


def test_section_block_rewrite_leaves_everything_outside_the_markers_alone(
    tmp_path: Path,
) -> None:
    manuscript = tmp_path / "index.qmd"
    manuscript.write_text(
        "---\ntitle: T\n---\n"
        "\n"
        "A hand-written note above the list.\n"
        "\n"
        f"{SECTIONS_BEGIN}\n"
        "{{< include sections/old.md >}}\n"
        f"{SECTIONS_END}\n"
        "\n"
        "A hand-written note below the list.\n",
        encoding="utf-8",
    )
    sections = tmp_path / "sections"
    sections.mkdir()
    for name in ("02-results.md", "00-front-matter.md", "01-methods.md"):
        (sections / name).write_text("body\n", encoding="utf-8")

    files = section_files(sections)
    updated = replace_section_block(
        manuscript.read_text(encoding="utf-8"),
        render_section_block(manuscript, files),
    )

    assert updated is not None
    # Filename order is document order, so the numeric prefix decides.
    assert updated == (
        "---\ntitle: T\n---\n"
        "\n"
        "A hand-written note above the list.\n"
        "\n"
        f"{SECTIONS_BEGIN}\n"
        "{{< include sections/00-front-matter.md >}}\n"
        "{{< include sections/01-methods.md >}}\n"
        "{{< include sections/02-results.md >}}\n"
        f"{SECTIONS_END}\n"
        "\n"
        "A hand-written note below the list.\n"
    )


def test_section_block_rewrite_is_declined_without_markers(tmp_path: Path) -> None:
    manuscript = tmp_path / "index.qmd"
    text = "---\ntitle: T\n---\n\n{{< include sections/only.md >}}\n"
    manuscript.write_text(text, encoding="utf-8")

    assert find_section_block(text) is None
    assert replace_section_block(text, ["{{< include sections/other.md >}}"]) is None


def test_include_targets_reports_paths_that_do_not_exist(tmp_path: Path) -> None:
    manuscript = tmp_path / "index.qmd"
    manuscript.write_text(
        "{{< include sections/present.md >}}\n{{< include sections/absent.md >}}\n",
        encoding="utf-8",
    )
    sections = tmp_path / "sections"
    sections.mkdir()
    (sections / "present.md").write_text("body\n", encoding="utf-8")

    targets = include_targets(manuscript.read_text(encoding="utf-8"), manuscript)

    assert targets == (
        (sections / "present.md").resolve(),
        (sections / "absent.md").resolve(),
    )


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
