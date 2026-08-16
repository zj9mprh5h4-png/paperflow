from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class PaperflowError(RuntimeError):
    """Raised for expected workflow errors with user-facing messages."""


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def find_project_root(start: Path | None = None) -> Path:
    """Find the repository root from the current directory or installed package path."""
    candidates: list[Path] = []
    if start is not None:
        candidates.append(start.resolve())
    candidates.append(Path.cwd().resolve())
    candidates.append(Path(__file__).resolve().parents[2])

    for candidate in candidates:
        for path in [candidate, *candidate.parents]:
            if (path / "_quarto.yml").exists() and (path / "pyproject.toml").exists():
                return path
    raise PaperflowError("Could not find project root containing _quarto.yml and pyproject.toml.")


def relpath(path: Path, root: Path | None = None) -> str:
    base = root or find_project_root()
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return str(path)


def executable(name: str, *, root: Path | None = None) -> str | None:
    project_root = root
    if project_root is None:
        try:
            project_root = find_project_root()
        except PaperflowError:
            project_root = Path.cwd()

    try:
        from .config import load_config

        configured = load_config(project_root).executables.get(name)
    except PaperflowError:
        configured = None
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_absolute() or any(separator in configured for separator in ["/", "\\"]):
            resolved = candidate if candidate.is_absolute() else project_root / candidate
            if resolved.is_file():
                return str(resolved.resolve())
        else:
            path = shutil.which(configured)
            if path:
                return path

    path = shutil.which(name)
    if path:
        return path
    if name == "quarto":
        candidates = sorted(
            (project_root / ".tools").glob("quarto-*/bin/quarto.cmd"),
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
    return None


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> CommandResult:
    root = cwd or find_project_root()
    resolved_args = list(args)
    if args and not any(separator in args[0] for separator in ["/", "\\"]):
        resolved = executable(args[0], root=root)
        if resolved is not None:
            resolved_args[0] = resolved

    command_env = {**os.environ, **(env or {})}
    command_name = Path(resolved_args[0]).name.lower() if resolved_args else ""
    if command_name in {"quarto", "quarto.cmd", "quarto.exe"}:
        local_appdata = root / ".tools" / "appdata" / "local"
        roaming_appdata = root / ".tools" / "appdata" / "roaming"
        ipython_dir = root / ".tools" / "appdata" / "ipython"
        jupyter_config = root / ".tools" / "appdata" / "jupyter" / "config"
        jupyter_data = root / ".tools" / "appdata" / "jupyter" / "data"
        jupyter_runtime = root / ".tools" / "appdata" / "jupyter" / "runtime"
        mpl_config = root / ".tools" / "appdata" / "matplotlib"
        local_appdata.mkdir(parents=True, exist_ok=True)
        roaming_appdata.mkdir(parents=True, exist_ok=True)
        ipython_dir.mkdir(parents=True, exist_ok=True)
        jupyter_config.mkdir(parents=True, exist_ok=True)
        jupyter_data.mkdir(parents=True, exist_ok=True)
        jupyter_runtime.mkdir(parents=True, exist_ok=True)
        mpl_config.mkdir(parents=True, exist_ok=True)
        command_env["LOCALAPPDATA"] = str(local_appdata)
        command_env["APPDATA"] = str(roaming_appdata)
        command_env["IPYTHONDIR"] = str(ipython_dir)
        command_env["JUPYTER_CONFIG_DIR"] = str(jupyter_config)
        command_env["JUPYTER_DATA_DIR"] = str(jupyter_data)
        command_env["JUPYTER_RUNTIME_DIR"] = str(jupyter_runtime)
        command_env["MPLCONFIGDIR"] = str(mpl_config)

    completed = subprocess.run(
        resolved_args,
        cwd=root,
        env=command_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    result = CommandResult(
        args=args,
        returncode=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
    )
    if check and result.returncode != 0:
        command = " ".join(args)
        message = result.stderr or result.stdout or "no output"
        raise PaperflowError(f"Command failed ({result.returncode}): {command}\n{message}")
    return result


def git(args: list[str], *, cwd: Path | None = None, check: bool = True) -> CommandResult:
    return run_command(["git", *args], cwd=cwd, check=check)


def require_tool(name: str, *, root: Path | None = None) -> str:
    path = executable(name, root=root)
    if path is None:
        raise PaperflowError(
            f"Required tool '{name}' was not found on PATH. Install it as a system tool "
            "and rerun the command."
        )
    return path


def ensure_inside_project(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise PaperflowError(f"Path is outside the project root: {path}") from exc
    return resolved


def python_is_venv(root: Path) -> bool:
    exe = Path(sys.executable).resolve()
    try:
        exe.relative_to((root / ".venv").resolve())
    except ValueError:
        return False
    return True
