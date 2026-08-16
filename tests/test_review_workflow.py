from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from paperflow import review
from paperflow.commands import PaperflowError
from paperflow.manifest import sha256_file, write_manifest


def write_project(root: Path) -> None:
    (root / "manuscript").mkdir(parents=True)
    (root / "reviews" / "round-01" / "baseline").mkdir(parents=True)
    (root / "manuscript" / "index.qmd").write_text("authoritative source\n", encoding="utf-8")
    baseline = root / "reviews" / "round-01" / "baseline" / "paper.docx"
    baseline.write_bytes(b"baseline docx")
    write_manifest(
        root / "reviews" / "round-01" / "manifest.json",
        {
            "round": 1,
            "reviewer": "Dr. Reviewer",
            "reviewer_slug": "dr.-reviewer",
            "baseline_commit": "baseline123",
            "baseline_docx_sha256": sha256_file(baseline),
        },
    )


def write_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("_rels/.rels", b"<Relationships/>")
        archive.writestr(
            "word/document.xml",
            (
                b'<w:document xmlns:w="w"><w:body>'
                b'<w:ins w:id="1"><w:r/></w:ins></w:body></w:document>'
            ),
        )


def test_review_import_outputs_and_preserves_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo with spaces"
    root.mkdir()
    write_project(root)
    incoming = tmp_path / "returned review.docx"
    write_minimal_docx(incoming)
    source_before = (root / "manuscript" / "index.qmd").read_text(encoding="utf-8")

    def fake_docx_to_markdown(docx: Path, output: Path, *, track_changes: str, root: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        if "baseline" in docx.parts:
            output.write_text("baseline text\n", encoding="utf-8")
        elif track_changes == "all":
            output.write_text("baseline text\n{+review comment/change+}\n", encoding="utf-8")
        else:
            output.write_text("baseline text\naccepted edit\n", encoding="utf-8")

    monkeypatch.setattr(review, "docx_to_markdown", fake_docx_to_markdown)
    monkeypatch.setattr(review, "git_commit", lambda root: "abc123")

    outputs = review.import_review(
        round_number=1,
        reviewer="Dr. Reviewer",
        incoming_docx=incoming,
        root=root,
    )

    assert outputs["incoming"].exists()
    assert outputs["accepted"].read_text(encoding="utf-8").endswith("accepted edit\n")
    assert "{+review comment/change+}" in outputs["all_changes"].read_text(encoding="utf-8")
    assert "accepted edit" in outputs["diff"].read_text(encoding="utf-8")
    assert (root / "manuscript" / "index.qmd").read_text(encoding="utf-8") == source_before
    manifest = root / "reviews" / "round-01" / "derived" / "dr.-reviewer"
    assert (manifest / "import-manifest.json").exists()
    manifest_text = (manifest / "import-manifest.json").read_text(encoding="utf-8")
    assert '"baseline_commit": "baseline123"' in manifest_text
    assert '"import_commit": "abc123"' in manifest_text
    assert '"tracked_insertions": 1' in manifest_text

    with pytest.raises(PaperflowError):
        review.import_review(
            round_number=1,
            reviewer="Dr. Reviewer",
            incoming_docx=incoming,
            root=root,
        )


def test_review_import_rejects_tampered_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    write_project(root)
    incoming = tmp_path / "returned.docx"
    write_minimal_docx(incoming)
    (root / "reviews" / "round-01" / "baseline" / "paper.docx").write_bytes(b"tampered")
    monkeypatch.setattr(review, "git_commit", lambda root: "abc123")

    with pytest.raises(PaperflowError, match="no longer matches its manifest"):
        review.import_review(
            round_number=1,
            reviewer="Dr. Reviewer",
            incoming_docx=incoming,
            root=root,
        )


def test_review_start_refuses_dirty_git_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "dirty repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    (root / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    monkeypatch.setattr(review, "render_docx", lambda root: root / "build" / "paper.docx")

    with pytest.raises(PaperflowError, match="dirty git state"):
        review.start_review(round_number=1, reviewer="test", root=root)


def test_docx_to_markdown_extracts_media_next_to_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    docx = root / "paper.docx"
    docx.write_bytes(b"docx")
    output = root / "derived" / "paper.md"
    calls: list[list[str]] = []

    monkeypatch.setattr(review, "require_tool", lambda name, **kwargs: name)

    def fake_run_command(args: list[str], *, cwd: Path, **kwargs: object) -> object:
        calls.append(args)
        return object()

    monkeypatch.setattr(review, "run_command", fake_run_command)

    review.docx_to_markdown(docx, output, track_changes="accept", root=root)

    assert output.parent.exists()
    assert "--extract-media=derived" in calls[0]


def test_render_docx_runs_pre_render_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "scripts").mkdir()
    hook = root / "scripts" / "pre_render.py"
    hook.write_text("print('hook')\n", encoding="utf-8")
    (root / "manuscript").mkdir()
    (root / "manuscript" / "index.qmd").write_text("# Test\n", encoding="utf-8")
    (root / "build").mkdir()
    calls: list[list[str]] = []

    def fake_run_command(args: list[str], *, cwd: Path, **kwargs: object) -> object:
        calls.append(args)
        return object()

    def fake_render(
        source: Path,
        output: Path,
        *,
        config: object,
        execute: bool = True,
    ) -> Path:
        del config, execute
        assert source == root / "manuscript" / "index.qmd"
        output.write_bytes(b"x" * 1001)
        return output

    monkeypatch.setattr(review, "run_command", fake_run_command)
    monkeypatch.setattr(review, "render_qmd_to_docx", fake_render)

    rendered = review.render_docx(root)

    assert rendered == root / "build" / "paper_current.docx"
    assert calls[0] == [sys.executable, str(hook)]
    assert len(calls) == 1


def test_preworkflow_word_baseline_outputs_diff_without_changing_qmd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "_quarto.yml").write_text("project:\n  type: default\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "manuscript").mkdir()
    qmd = root / "manuscript" / "index.qmd"
    qmd.write_text("authoritative qmd\n", encoding="utf-8")
    docx = root / "Article.docx"
    docx.write_bytes(b"word")

    def fake_qmd_to_markdown(source: Path, output: Path, *, root: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    def fake_docx_to_markdown(docx: Path, output: Path, *, track_changes: str, root: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"word {track_changes}\n", encoding="utf-8")

    monkeypatch.setattr(review, "qmd_to_markdown", fake_qmd_to_markdown)
    monkeypatch.setattr(review, "docx_to_markdown", fake_docx_to_markdown)
    monkeypatch.setattr(review, "git_commit", lambda root: None)

    outputs = review.import_preworkflow_word_baseline(docx=docx, root=root, force=True)

    assert outputs["incoming"].exists()
    assert outputs["accepted"].read_text(encoding="utf-8") == "word accept\n"
    assert outputs["all_changes"].read_text(encoding="utf-8") == "word all\n"
    assert "authoritative qmd" in outputs["diff"].read_text(encoding="utf-8")
    assert qmd.read_text(encoding="utf-8") == "authoritative qmd\n"


def test_word_baseline_promotion_preserves_frontmatter_and_copies_media(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "manuscript").mkdir()
    qmd = root / "manuscript" / "index.qmd"
    qmd.write_text("---\ntitle: Test\n---\n\nold body\n", encoding="utf-8")

    derived = root / "reviews" / "preworkflow-word-baseline" / "article" / "derived"
    media = derived / "media"
    media.mkdir(parents=True)
    (derived / "article.accepted.md").write_text(
        (
            '<span class="mark">\\[\\[PLACEHOLDER\\]\\]</span>\n\n'
            "``` math\nx = 1\n```\n\n"
            '<img src="media/image1.png" />\n'
        ),
        encoding="utf-8",
    )
    (media / "image1.png").write_bytes(b"png")

    promotion = review.promote_word_baseline_to_qmd(name="article", root=root, force=True)

    promoted = qmd.read_text(encoding="utf-8")
    assert promoted.startswith("---\ntitle: Test\n---\n\n")
    assert "[[PLACEHOLDER]]" in promoted
    assert "$$\nx = 1\n$$" in promoted
    assert 'src="media/article/image1.png"' in promoted
    assert (root / "manuscript" / "media" / "article" / "image1.png").exists()
    assert promotion.outputs["qmd"] == qmd
    assert promotion.unreferenced == ()


def test_relative_docx_arguments_resolve_against_the_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "_quarto.yml").write_text("project:\n  type: default\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "manuscript").mkdir()
    (root / "manuscript" / "index.qmd").write_text("authoritative qmd\n", encoding="utf-8")
    inbox = root / "inbox"
    inbox.mkdir()
    (inbox / "Article.docx").write_bytes(b"the file the user meant")
    # Resolving against the project root instead of the working directory would silently
    # pick this file up instead of the one next to the user.
    (root / "Article.docx").write_bytes(b"decoy at the project root")

    def fake_qmd_to_markdown(source: Path, output: Path, *, root: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    def fake_docx_to_markdown(docx: Path, output: Path, *, track_changes: str, root: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(docx.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(review, "qmd_to_markdown", fake_qmd_to_markdown)
    monkeypatch.setattr(review, "docx_to_markdown", fake_docx_to_markdown)
    monkeypatch.setattr(review, "git_commit", lambda root: None)
    monkeypatch.chdir(inbox)

    outputs = review.import_preworkflow_word_baseline(
        docx=Path("Article.docx"),
        root=root,
        force=True,
    )

    assert outputs["incoming"].read_bytes() == b"the file the user meant"


def test_word_promotion_restores_open_markers_escaped_by_the_converter(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "manuscript").mkdir()
    qmd = root / "manuscript" / "index.qmd"
    qmd.write_text("---\ntitle: Test\n---\n\nold body\n", encoding="utf-8")
    derived = root / "reviews" / "preworkflow-word-baseline" / "article" / "derived"
    derived.mkdir(parents=True)
    (derived / "article.accepted.md").write_text(
        "Intro text.\n\n\\[\\[OPEN: Restore the 2019 cohort citation.\\]\\]\n",
        encoding="utf-8",
    )

    review.promote_word_baseline_to_qmd(name="article", root=root, force=True)

    promoted = qmd.read_text(encoding="utf-8")
    assert "[[OPEN: Restore the 2019 cohort citation.]]" in promoted
    assert "\\[\\[" not in promoted


def _promotable_project(root: Path) -> Path:
    """Create a template-shaped manuscript that pulls its text in through includes."""
    sections = root / "manuscript" / "sections"
    sections.mkdir(parents=True)
    qmd = root / "manuscript" / "index.qmd"
    qmd.write_text(
        "---\ntitle: Test\n---\n\n"
        "{{< include sections/abstract.md >}}\n\n"
        "{{< include sections/main-text.md >}}\n\n"
        "{{< include sections/removed.md >}}\n",
        encoding="utf-8",
    )
    (sections / "abstract.md").write_text("# Abstract\n", encoding="utf-8")
    (sections / "main-text.md").write_text("# Main text\n", encoding="utf-8")
    derived = root / "reviews" / "preworkflow-word-baseline" / "article" / "derived"
    derived.mkdir(parents=True)
    (derived / "article.accepted.md").write_text("promoted body\n", encoding="utf-8")
    return qmd


def test_word_promotion_refuses_to_silently_replace_include_structure(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    qmd = _promotable_project(root)
    original = qmd.read_text(encoding="utf-8")

    with pytest.raises(PaperflowError, match="unreferenced") as error:
        review.promote_word_baseline_to_qmd(name="article", root=root)

    assert error.value.code == "word_promote.includes_present"
    message = str(error.value)
    assert "manuscript/sections/abstract.md" in message
    assert "manuscript/sections/main-text.md" in message
    assert "removed.md" not in message
    assert qmd.read_text(encoding="utf-8") == original
    assert (root / "manuscript" / "sections" / "abstract.md").is_file()


def test_forced_word_promotion_reports_the_files_it_leaves_unreferenced(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    qmd = _promotable_project(root)

    promotion = review.promote_word_baseline_to_qmd(name="article", root=root, force=True)

    assert "promoted body" in qmd.read_text(encoding="utf-8")
    assert "{{< include" not in qmd.read_text(encoding="utf-8")
    assert promotion.unreferenced == (
        (root / "manuscript" / "sections" / "abstract.md").resolve(),
        (root / "manuscript" / "sections" / "main-text.md").resolve(),
    )
    for orphan in promotion.unreferenced:
        assert orphan.is_file()
    assert promotion.outputs["manifest"].exists()
