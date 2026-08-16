from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

from . import __version__
from .commands import PaperflowError, find_project_root
from .config import load_config
from .open_items import build_open_items
from .review import (
    import_preworkflow_word_baseline,
    import_review,
    promote_word_baseline_to_qmd,
    regenerate_diff,
    render_docx,
    start_review,
)
from .validation import doctor
from .workflow import build_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperflow",
        description=(
            "Build configured Quarto manuscripts and manage controlled Word review rounds."
        ),
        epilog="Run 'paperflow <command> --help' for command-specific options.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Check local workflow prerequisites.")
    doctor_parser.add_argument(
        "--allow-missing-tools",
        action="store_true",
        help="Report missing tools but exit successfully.",
    )

    subparsers.add_parser("render", help="Render only the configured manuscript DOCX.")
    subparsers.add_parser(
        "build",
        help="Build the manuscript DOCX and the configured Open Items DOCX.",
    )
    subparsers.add_parser(
        "open-items",
        help="Generate the configured Open Items Markdown and DOCX reports.",
    )
    subparsers.add_parser(
        "config-show",
        help="Print the effective merged Paperflow configuration.",
    )

    start = subparsers.add_parser("review-start", help="Create a Word review round.")
    start.add_argument("--round", required=True, type=int, dest="round_number")
    start.add_argument("--reviewer", required=True, help="Stable reviewer identifier.")
    start.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Explicitly permit a non-clean Git baseline.",
    )
    start.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing local round directory.",
    )

    import_parser = subparsers.add_parser(
        "review-import",
        help="Import a returned reviewer DOCX.",
    )
    import_parser.add_argument("--round", required=True, type=int, dest="round_number")
    import_parser.add_argument("--reviewer", required=True, help="Reviewer identifier from start.")
    import_parser.add_argument("--docx", required=True, type=Path, help="Returned reviewer DOCX.")
    import_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing archived import for this reviewer.",
    )

    diff_parser = subparsers.add_parser("review-diff", help="Regenerate an accepted Markdown diff.")
    diff_parser.add_argument("--round", required=True, type=int, dest="round_number")
    diff_parser.add_argument("--reviewer", required=True)

    word_baseline = subparsers.add_parser(
        "word-baseline",
        help="Convert an existing Word manuscript to derived Markdown and diff it against QMD.",
    )
    word_baseline.add_argument("--docx", required=True, type=Path)
    word_baseline.add_argument("--name", default="article")
    word_baseline.add_argument("--force", action="store_true")

    word_promote = subparsers.add_parser(
        "word-promote",
        help="Promote a Word-derived Markdown baseline to manuscript/index.qmd.",
    )
    word_promote.add_argument("--name", default="article")
    word_promote.add_argument("--force", action="store_true")

    clean = subparsers.add_parser(
        "clean",
        help="Remove files under the configured output directory.",
    )
    clean.add_argument(
        "--yes",
        action="store_true",
        help="Confirm removal of generated build files.",
    )
    return parser


def clean_build(*, yes: bool) -> int:
    if not yes:
        raise PaperflowError("Refusing to clean build/ without --yes.")
    root = find_project_root()
    build = load_config(root).paths.output_dir
    build.mkdir(exist_ok=True)
    for child in build.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    print(f"Cleaned generated files in {build}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor(allow_missing_tools=args.allow_missing_tools)
        if args.command == "render":
            docx = render_docx()
            print(docx)
            return 0
        if args.command == "build":
            result = build_project()
            print(f"manuscript: {result.manuscript}")
            if result.open_items is not None:
                print(f"open_items: {result.open_items.docx}")
                print(f"open_items_count: {result.open_items.count}")
            return 0
        if args.command == "open-items":
            result = build_open_items(load_config())
            print(f"markdown: {result.markdown}")
            print(f"docx: {result.docx}")
            print(f"count: {result.count}")
            return 0
        if args.command == "config-show":
            print(yaml.safe_dump(load_config().raw, sort_keys=False).rstrip())
            return 0
        if args.command == "review-start":
            outgoing = start_review(
                round_number=args.round_number,
                reviewer=args.reviewer,
                allow_dirty=args.allow_dirty,
                force=args.force,
            )
            print(outgoing)
            return 0
        if args.command == "review-import":
            outputs = import_review(
                round_number=args.round_number,
                reviewer=args.reviewer,
                incoming_docx=args.docx,
                force=args.force,
            )
            for name, path in outputs.items():
                print(f"{name}: {path}")
            return 0
        if args.command == "review-diff":
            print(regenerate_diff(round_number=args.round_number, reviewer=args.reviewer))
            return 0
        if args.command == "word-baseline":
            outputs = import_preworkflow_word_baseline(
                docx=args.docx,
                name=args.name,
                force=args.force,
            )
            for label, path in outputs.items():
                print(f"{label}: {path}")
            return 0
        if args.command == "word-promote":
            outputs = promote_word_baseline_to_qmd(
                name=args.name,
                force=args.force,
            )
            for label, path in outputs.items():
                print(f"{label}: {path}")
            return 0
        if args.command == "clean":
            return clean_build(yes=args.yes)
    except PaperflowError as exc:
        print(f"paperflow: {exc}", file=sys.stderr)
        return 2
    parser.error(f"Unhandled command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
