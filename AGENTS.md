# Agent Rules

- `manuscript/index.qmd` is the authoritative manuscript entry point.
- Follow `manuscript/manuscript_formatting_rules.md`; users may adapt those rules deliberately.
- Never edit `build/` as a manuscript source.
- Never copy, edit, or commit `.venv/`.
- Change Python dependencies only in `pyproject.toml`, then update `uv.lock` with `uv`.
- Do not run ad-hoc `pip install` into the project environment.
- Prefer `uv run ...` for Python, tests, render, and CLI commands.
- Do not automatically apply Word review edits to QMD.
- Preserve citation keys unless a deliberate migration is documented.
- Use TeX syntax for equations.
- Keep CrossRef IDs lowercase with `fig-`, `tbl-`, `eq-`, or `sec-` prefixes.
- Avoid manual numbering of figures, tables, and equations.
- Do not commit returned reviewer files or confidential content.
- Preserve `[[OPEN: ...]]` placeholders until the missing information has been verified.

Before changing manuscript content, inspect the relevant source context and run the narrowest
useful checks. After changing QMD or render code, run `uv run paperflow build` when Quarto is
available.
