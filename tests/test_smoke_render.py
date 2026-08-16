from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from paperflow.commands import executable, run_command
from paperflow.docx_math import docx_inline_math_protection, protect_docx_inline_math
from paperflow.validation import (
    docx_contains_absolute_paths,
    docx_contains_omml,
    docx_core_files_present,
)

QUARTO = executable("quarto")


@pytest.mark.skipif(QUARTO is None, reason="Quarto CLI is not installed")
def test_smoke_qmd_renders_to_docx(tmp_path: Path) -> None:
    fixtures = Path(__file__).parent / "fixtures"
    work = tmp_path / "smoke"
    work.mkdir()
    (work / "_quarto.yml").write_text("project:\n  type: default\n", encoding="utf-8")
    for name in ["smoke.qmd", "references.bib", "figure-smoke.svg"]:
        shutil.copy2(fixtures / name, work / name)
    completed = run_command(
        [
            QUARTO or "quarto",
            "render",
            "smoke.qmd",
            "--to",
            "docx",
            "--output",
            "smoke.docx",
        ],
        cwd=work,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    docx = work / "smoke.docx"
    assert docx.exists()
    assert docx.stat().st_size > 5000
    assert docx_core_files_present(docx)
    assert docx_contains_omml(docx)
    assert not docx_contains_absolute_paths(docx)
    inline_math, protected_math = docx_inline_math_protection(docx)
    assert inline_math > 0
    assert protect_docx_inline_math(docx) == inline_math - protected_math
    assert docx_inline_math_protection(docx) == (inline_math, inline_math)
