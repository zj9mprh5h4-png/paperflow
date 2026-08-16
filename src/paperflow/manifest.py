from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .commands import CommandResult, git, run_command


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def command_version(args: list[str], root: Path) -> dict[str, Any]:
    result = run_command(args, cwd=root, check=False)
    return {
        "command": args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def git_commit(root: Path) -> str | None:
    result: CommandResult = git(["rev-parse", "HEAD"], cwd=root, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"created_utc": utc_timestamp(), **data}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
