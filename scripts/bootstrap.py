from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args))
    return subprocess.run(args, cwd=ROOT, text=True, check=check)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the local Paperflow environment.")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    missing = [tool for tool in ("git", "uv") if shutil.which(tool) is None]
    if missing:
        print("Missing required tools: " + ", ".join(missing))
        return 1

    run(["uv", "sync", "--frozen", "--extra", "dev"])
    run(["uv", "run", "paperflow", "doctor"])
    if not args.skip_tests:
        run(["uv", "run", "pytest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
