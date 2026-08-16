# Paperflow Agent Instructions

This optional file provides repository instructions for Codex-compatible agents. Paperflow itself
does not depend on Codex. A template user may adapt or remove this file deliberately.

## Resolve project state first

- Before diagnosing configuration or changing project files, read `docs/agent-guide.md`.
- Run `uv run paperflow doctor --format json` from the repository root.
- Treat every failed Doctor check as unresolved. Use its `id`, `error_code`, `detail`, and
  `remediation` fields; do not guess a replacement value.
- After Doctor accepts the configuration, run `uv run paperflow config-show` when effective merged
  values are relevant. Its output may contain private local paths and must not be pasted into public
  issues without review.
- Treat the effective `project.manuscript` path as the authoritative manuscript entry point and the
  effective `project.formatting_rules` path as the editing-rules source. Do not assume their default
  paths after a user changes `paperflow.yml`.
- Do not set `lang` or an output filename in `_quarto.yml`. Paperflow passes both from
  `paperflow.yml` on the Quarto command line, so an entry there looks effective but is ignored.

## Manuscript and review safety

- Read the configured formatting-rules file before changing manuscript content.
- Never invent references, author details, figure numbers, data, or quantitative results.
- Do not silently strengthen, weaken, or otherwise alter a scientific claim.
- Preserve `[[OPEN: ...]]` markers until the missing information has been supplied or verified.
- Never edit generated files under the configured output directory as manuscript sources.
- Do not automatically apply Word review edits to QMD. Reference the review round, reviewer, and
  baseline commit when applying an accepted change.
- Preserve citation keys and raw-data paths unless a deliberate migration is documented.
- Keep technical workflow changes separate from scientific or manuscript-content changes.

## Repository and confidentiality boundaries

- Never copy, edit, or commit `.venv/`.
- Do not force-add generated output, `.paperflow.local.yml`, private Word templates, returned review
  files, review-round artifacts, credentials, unpublished data, or other confidential content.
- Do not upload or forward confidential project material to web searches, connectors, external
  services, or third-party tools. Use neutral minimal examples for external diagnostics.
- Preserve existing data paths unless a deliberate migration is documented, and never overwrite
  raw data.

## Dependencies and commands

- Change Python dependencies only in `pyproject.toml`, then update `uv.lock` with `uv`.
- Do not run ad-hoc `pip install` commands into the project environment.
- Prefer `uv run ...` for Python, tests, rendering, and Paperflow CLI commands.
- Keep Git, uv, and Quarto as explicit external prerequisites; do not add automatic installers.

## Verification

- Run the narrowest relevant tests after each change.
- After Python, CLI, configuration-validation, or workflow changes, run `uv run pytest` and
  `uv run ruff check .`.
- After configuration changes, rerun `uv run paperflow doctor --format json` and confirm `ok: true`.
- After QMD or render-code changes, run `uv run paperflow build` when Quarto is available and confirm
  both the manuscript and Open Items DOCX outputs.
- Report failed checks and concrete remediation to the user; never describe an unverified repair as
  successful.
