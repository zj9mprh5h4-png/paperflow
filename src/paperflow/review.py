from __future__ import annotations

import difflib
import re
import shutil
import sys
import zipfile
from pathlib import Path

from .commands import (
    PaperflowError,
    ensure_inside_project,
    find_project_root,
    git,
    relpath,
    require_tool,
    run_command,
)
from .config import PaperflowConfig, load_config
from .manifest import command_version, git_commit, read_manifest, sha256_file, write_manifest
from .rendering import render_qmd_to_docx
from .validation import docx_core_files_present, docx_revision_counts


def reviewer_slug(reviewer: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", reviewer.strip()).strip("-").lower()
    if not slug:
        raise PaperflowError("Reviewer identifier must contain at least one letter or number.")
    return slug


def round_name(round_number: int) -> str:
    if round_number < 1:
        raise PaperflowError("Review round must be a positive integer.")
    return f"round-{round_number:02d}"


def git_dirty(root: Path) -> bool:
    result = git(["status", "--porcelain"], cwd=root, check=False)
    if result.returncode != 0:
        raise PaperflowError(result.stderr or "Not a git repository.")
    return bool(result.stdout.strip())


def render_docx(
    root: Path | None = None,
    *,
    config: PaperflowConfig | None = None,
) -> Path:
    resolved = config or load_config(root or find_project_root())
    run_pre_render_hook(resolved.root, resolved)
    return render_qmd_to_docx(
        resolved.project.manuscript,
        resolved.manuscript_output,
        config=resolved,
    )


def run_pre_render_hook(root: Path, config: PaperflowConfig) -> None:
    if not config.build.run_pre_render_hook:
        return
    hook = root / "scripts" / "pre_render.py"
    if hook.exists():
        run_command([sys.executable, str(hook)], cwd=root)


def docx_to_markdown(docx: Path, output: Path, *, track_changes: str, root: Path) -> None:
    require_tool("quarto", root=root)
    output.parent.mkdir(parents=True, exist_ok=True)
    media_extract_dir = relpath(output.parent, root)
    run_command(
        [
            "quarto",
            "pandoc",
            f"--track-changes={track_changes}",
            str(docx),
            "-t",
            "gfm",
            "--wrap=none",
            f"--extract-media={media_extract_dir}",
            "-o",
            str(output),
        ],
        cwd=root,
    )


def qmd_to_markdown(qmd: Path, output: Path, *, root: Path) -> None:
    require_tool("quarto", root=root)
    output.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "quarto",
            "pandoc",
            str(qmd),
            "-t",
            "gfm",
            "--wrap=none",
            "-o",
            str(output),
        ],
        cwd=root,
    )


def split_qmd_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise PaperflowError("Existing QMD does not start with YAML front matter.")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise PaperflowError("Existing QMD front matter is not closed.")
    split_at = end + len("\n---\n")
    return text[:split_at].rstrip() + "\n", text[split_at:].lstrip()


def normalise_word_markdown_for_qmd(markdown: str, *, media_prefix: str) -> str:
    body = markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
    body = re.sub(
        r"```[ \t]*math[ \t]*\n(.*?)\n```",
        lambda match: "$$\n" + match.group(1).strip() + "\n$$",
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r'<span class="mark">(.*?)</span>',
        lambda match: match.group(1).replace(r"\[", "[").replace(r"\]", "]"),
        body,
        flags=re.DOTALL,
    )
    if media_prefix:
        body = body.replace('src="media/', f'src="{media_prefix}/')
        body = body.replace("](media/", f"]({media_prefix}/")
        body = re.sub(
            r'src="[^"]*[/\\]media[/\\]([^"]+)"',
            f'src="{media_prefix}/' + r'\1"',
            body,
        )
        body = re.sub(
            r"\]\([^)]*[/\\]media[/\\]([^)]+)\)",
            f"]({media_prefix}/" + r"\1)",
            body,
        )
    return body + "\n"


def import_preworkflow_word_baseline(
    *,
    docx: Path,
    name: str = "article",
    root: Path | None = None,
    force: bool = False,
) -> dict[str, Path]:
    project_root = root or find_project_root()
    config = load_config(project_root)
    source_docx = docx.expanduser()
    if not source_docx.is_absolute():
        source_docx = (project_root / source_docx).resolve()
    if not source_docx.exists():
        raise PaperflowError(f"Word baseline DOCX does not exist: {docx}")

    slug = reviewer_slug(name)
    baseline_root = config.paths.review_dir / "preworkflow-word-baseline" / slug
    incoming_dir = baseline_root / "incoming"
    derived_dir = baseline_root / "derived"
    incoming_dir.mkdir(parents=True, exist_ok=True)
    derived_dir.mkdir(parents=True, exist_ok=True)

    archived_docx = incoming_dir / source_docx.name
    if archived_docx.exists() and not force:
        raise PaperflowError(f"Word baseline archive already exists: {archived_docx}")
    shutil.copy2(source_docx, archived_docx)

    qmd_source = config.project.manuscript
    qmd_markdown = derived_dir / "qmd.current.md"
    accepted_markdown = derived_dir / f"{slug}.accepted.md"
    all_changes_markdown = derived_dir / f"{slug}.all-changes.md"
    diff = derived_dir / f"{slug}.accepted.diff.md"

    qmd_to_markdown(qmd_source, qmd_markdown, root=project_root)
    docx_to_markdown(archived_docx, accepted_markdown, track_changes="accept", root=project_root)
    docx_to_markdown(archived_docx, all_changes_markdown, track_changes="all", root=project_root)
    write_diff(qmd_markdown, accepted_markdown, diff)

    write_manifest(
        baseline_root / "manifest.json",
        {
            "kind": "preworkflow-word-baseline",
            "name": name,
            "slug": slug,
            "git_commit": git_commit(project_root),
            "source_docx": archived_docx.relative_to(project_root).as_posix(),
            "source_docx_sha256": sha256_file(archived_docx),
            "qmd_markdown": qmd_markdown.relative_to(project_root).as_posix(),
            "accepted_markdown": accepted_markdown.relative_to(project_root).as_posix(),
            "all_changes_markdown": all_changes_markdown.relative_to(project_root).as_posix(),
            "diff": diff.relative_to(project_root).as_posix(),
        },
    )
    return {
        "incoming": archived_docx,
        "qmd": qmd_markdown,
        "accepted": accepted_markdown,
        "all_changes": all_changes_markdown,
        "diff": diff,
    }


def promote_word_baseline_to_qmd(
    *,
    name: str = "article",
    root: Path | None = None,
    force: bool = False,
) -> dict[str, Path]:
    project_root = root or find_project_root()
    config = load_config(project_root)
    slug = reviewer_slug(name)
    baseline_root = config.paths.review_dir / "preworkflow-word-baseline" / slug
    derived_dir = baseline_root / "derived"
    accepted_markdown = derived_dir / f"{slug}.accepted.md"
    if not accepted_markdown.exists():
        raise PaperflowError(
            f"Missing accepted Word-derived Markdown: {accepted_markdown}. "
            "Run paperflow word-baseline first."
        )

    qmd_path = config.project.manuscript
    existing = qmd_path.read_text(encoding="utf-8")
    frontmatter, _ = split_qmd_frontmatter(existing)

    media_source = derived_dir / "media"
    media_prefix = ""
    media_destination = qmd_path.parent / "media" / slug
    if media_source.exists():
        if media_destination.exists():
            if not force:
                raise PaperflowError(
                    f"Manuscript media directory already exists: {media_destination}"
                )
            shutil.rmtree(media_destination)
        shutil.copytree(media_source, media_destination)
        media_prefix = f"media/{slug}"

    body = normalise_word_markdown_for_qmd(
        accepted_markdown.read_text(encoding="utf-8"),
        media_prefix=media_prefix,
    )
    qmd_path.write_text(frontmatter + "\n" + body, encoding="utf-8")

    write_manifest(
        baseline_root / "promotion-manifest.json",
        {
            "kind": "word-baseline-promotion",
            "name": name,
            "slug": slug,
            "git_commit": git_commit(project_root),
            "accepted_markdown": accepted_markdown.relative_to(project_root).as_posix(),
            "accepted_markdown_sha256": sha256_file(accepted_markdown),
            "promoted_qmd": qmd_path.relative_to(project_root).as_posix(),
            "media_source": (
                media_source.relative_to(project_root).as_posix() if media_source.exists() else None
            ),
            "media_destination": (
                media_destination.relative_to(project_root).as_posix()
                if media_destination.exists()
                else None
            ),
            "auto_applied_to_qmd": True,
            "source_docx_remains_archived": True,
        },
    )
    return {
        "qmd": qmd_path,
        "accepted": accepted_markdown,
        "media": media_destination,
        "manifest": baseline_root / "promotion-manifest.json",
    }


def start_review(
    *,
    round_number: int,
    reviewer: str,
    root: Path | None = None,
    allow_dirty: bool = False,
    force: bool = False,
) -> Path:
    project_root = root or find_project_root()
    config = load_config(project_root)
    if config.review.require_clean_git and git_dirty(project_root) and not allow_dirty:
        raise PaperflowError(
            "Refusing to start a review round from a dirty git state. Commit or stash "
            "changes, or pass --allow-dirty for an explicitly documented exception."
        )

    baseline_commit = git_commit(project_root)
    if baseline_commit is None:
        raise PaperflowError(
            "Cannot start review round before the repository has an initial commit."
        )

    review_root = config.paths.review_dir / round_name(round_number)
    if review_root.exists() and not force:
        raise PaperflowError(f"Review round already exists: {review_root}")

    rendered = render_docx(config=config)
    slug = reviewer_slug(reviewer)
    baseline_dir = review_root / "baseline"
    outgoing_dir = review_root / "outgoing"
    incoming_dir = review_root / "incoming" / slug
    derived_dir = review_root / "derived" / slug
    for directory in [baseline_dir, outgoing_dir, incoming_dir, derived_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    baseline_docx = baseline_dir / "paper.docx"
    outgoing_docx = outgoing_dir / f"{slug}.docx"
    shutil.copy2(rendered, baseline_docx)
    shutil.copy2(rendered, outgoing_docx)

    write_manifest(
        review_root / "manifest.json",
        {
            "round": round_number,
            "reviewer": reviewer,
            "reviewer_slug": slug,
            "baseline_commit": baseline_commit,
            "baseline_docx": baseline_docx.relative_to(project_root).as_posix(),
            "baseline_docx_sha256": sha256_file(baseline_docx),
            "outgoing_docx": outgoing_docx.relative_to(project_root).as_posix(),
            "outgoing_docx_sha256": sha256_file(outgoing_docx),
            "tools": {
                "git": command_version(["git", "--version"], project_root),
                "quarto": command_version(["quarto", "--version"], project_root),
                "pandoc": command_version(["quarto", "pandoc", "--version"], project_root),
            },
        },
    )
    return outgoing_docx


def import_review(
    *,
    round_number: int,
    reviewer: str,
    incoming_docx: Path,
    root: Path | None = None,
    force: bool = False,
) -> dict[str, Path]:
    project_root = root or find_project_root()
    config = load_config(project_root)
    slug = reviewer_slug(reviewer)
    review_root = config.paths.review_dir / round_name(round_number)
    baseline_docx = review_root / "baseline" / "paper.docx"
    if not baseline_docx.exists():
        raise PaperflowError(f"Missing review baseline DOCX: {baseline_docx}")

    round_manifest_path = review_root / "manifest.json"
    try:
        round_manifest = read_manifest(round_manifest_path)
    except ValueError as exc:
        raise PaperflowError(str(exc)) from exc
    if round_manifest.get("round") != round_number:
        raise PaperflowError(f"Review manifest round does not match round {round_number}.")
    if round_manifest.get("reviewer_slug") != slug:
        raise PaperflowError(
            f"Review manifest belongs to reviewer {round_manifest.get('reviewer_slug')!r}, "
            f"not {slug!r}."
        )
    baseline_commit = round_manifest.get("baseline_commit")
    expected_baseline_hash = round_manifest.get("baseline_docx_sha256")
    if not isinstance(baseline_commit, str) or not isinstance(expected_baseline_hash, str):
        raise PaperflowError(
            f"Review manifest is missing baseline integrity data: {round_manifest_path}"
        )
    actual_baseline_hash = sha256_file(baseline_docx)
    if actual_baseline_hash != expected_baseline_hash:
        raise PaperflowError(
            "Review baseline DOCX no longer matches its manifest; refusing import."
        )

    source_docx = incoming_docx.expanduser()
    if not source_docx.is_absolute():
        source_docx = (Path.cwd() / source_docx).resolve()
    if not source_docx.exists():
        raise PaperflowError(f"Incoming DOCX does not exist: {incoming_docx}")
    try:
        valid_incoming = docx_core_files_present(source_docx)
    except (OSError, zipfile.BadZipFile):
        valid_incoming = False
    if not valid_incoming:
        raise PaperflowError(f"Incoming review file is not a valid DOCX: {source_docx}")
    tracked_insertions, tracked_deletions = docx_revision_counts(source_docx)

    incoming_dir = review_root / "incoming" / slug
    incoming_dir.mkdir(parents=True, exist_ok=True)
    archived_docx = incoming_dir / source_docx.name
    if archived_docx.exists() and not force:
        raise PaperflowError(f"Incoming DOCX archive already exists: {archived_docx}")
    shutil.copy2(source_docx, archived_docx)

    derived_dir = review_root / "derived" / slug
    baseline_md = derived_dir / "baseline.accepted.md"
    accepted_md = derived_dir / f"{slug}.accepted.md"
    all_changes_md = derived_dir / f"{slug}.all-changes.md"
    diff_md = derived_dir / f"{slug}.accepted.diff.md"

    docx_to_markdown(baseline_docx, baseline_md, track_changes="accept", root=project_root)
    docx_to_markdown(archived_docx, accepted_md, track_changes="accept", root=project_root)
    docx_to_markdown(archived_docx, all_changes_md, track_changes="all", root=project_root)
    write_diff(baseline_md, accepted_md, diff_md)

    write_manifest(
        derived_dir / "import-manifest.json",
        {
            "round": round_number,
            "reviewer": reviewer,
            "reviewer_slug": slug,
            "baseline_commit": baseline_commit,
            "baseline_docx_sha256": actual_baseline_hash,
            "import_commit": git_commit(project_root),
            "incoming_docx": archived_docx.relative_to(project_root).as_posix(),
            "incoming_docx_sha256": sha256_file(archived_docx),
            "tracked_insertions": tracked_insertions,
            "tracked_deletions": tracked_deletions,
            "accepted_markdown": accepted_md.relative_to(project_root).as_posix(),
            "all_changes_markdown": all_changes_md.relative_to(project_root).as_posix(),
            "diff": diff_md.relative_to(project_root).as_posix(),
        },
    )
    ensure_inside_project(config.project.manuscript, project_root)
    return {
        "incoming": archived_docx,
        "baseline": baseline_md,
        "accepted": accepted_md,
        "all_changes": all_changes_md,
        "diff": diff_md,
    }


def write_diff(before: Path, after: Path, output: Path) -> None:
    before_lines = before.read_text(encoding="utf-8").splitlines(keepends=True)
    after_lines = after.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=before.name,
        tofile=after.name,
    )
    output.write_text("".join(diff), encoding="utf-8")


def regenerate_diff(*, round_number: int, reviewer: str, root: Path | None = None) -> Path:
    project_root = root or find_project_root()
    config = load_config(project_root)
    slug = reviewer_slug(reviewer)
    derived_dir = config.paths.review_dir / round_name(round_number) / "derived" / slug
    baseline_md = derived_dir / "baseline.accepted.md"
    accepted_md = derived_dir / f"{slug}.accepted.md"
    diff_md = derived_dir / f"{slug}.accepted.diff.md"
    if not baseline_md.exists() or not accepted_md.exists():
        raise PaperflowError("Missing baseline or accepted Markdown; run review-import first.")
    write_diff(baseline_md, accepted_md, diff_md)
    return diff_md
