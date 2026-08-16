"""Reproducible Quarto-to-Word and Word-review workflows."""

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    __version__ = version("paperflow")
except PackageNotFoundError:  # source checkout before installation
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject.is_file():
        __version__ = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    else:  # pragma: no cover - defensive fallback outside a source tree or installation
        __version__ = "0.0.0+unknown"
