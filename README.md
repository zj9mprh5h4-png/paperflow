# Paperflow

Paperflow is a local-first workflow for writing in Markdown or Quarto, generating editable Word
documents, and importing tracked Word reviews without turning DOCX files into a second source of
truth.

This repository is an early local development version. A public license has not been selected yet,
so it is not ready for public distribution.

## What works today

- Render `manuscript/index.qmd` to `build/paper.docx` with Quarto and Pandoc.
- Generate `build/open_items.docx` from every current `[[OPEN: ...]]` placeholder.
- Preserve editable Word equations and protect inline equations from line breaks.
- Start a Word review round from a clean Git commit.
- Archive the exact outgoing review baseline and record hashes and tool versions.
- Import a returned DOCX as accepted Markdown, all-changes Markdown, and a unified diff.
- Compare an existing Word manuscript with the QMD source before a controlled migration.
- Keep generated outputs, private review files, local templates, and tool caches out of Git.

The schema-validated [`paperflow.yml`](paperflow.yml) controls manuscript, output, review, Word, and
Open Items settings. Publisher-specific submission profiles remain a later development stage. The
neutral example intentionally contains no journal template or research data.

## Requirements

- Git, `uv`, and the Quarto CLI are external prerequisites that users must install themselves.
- Paperflow does not download, install, or update these tools automatically.
- Quarto already includes Pandoc; do not install a separate Pandoc copy for Paperflow.
- Python 3.11 or newer is required. `uv` creates the project environment and can provision a
  compatible Python version when necessary.
- Microsoft Word is optional and is needed only for real Word review rounds.

A no-administrator Windows setup has been verified for both `uv` and portable Quarto. Paperflow
still leaves both installations under the user's explicit control; see
[`docs/setup.md`](docs/setup.md#verified-windows-setup-without-administrator-rights).

Python packages are declared in `pyproject.toml` and reproducibly locked in `uv.lock`. Paperflow
deliberately has no hand-maintained `requirements.in` or `requirements.txt`, because that would
create a second dependency source that can drift out of sync. See the complete, platform-neutral
instructions in [`docs/setup.md`](docs/setup.md).

## Setup

```bash
uv sync --frozen --extra dev
uv run paperflow doctor
uv run pytest
```

## Build the neutral example

```bash
uv run paperflow build
```

The results are:

- `build/paper.docx` — the editable manuscript;
- `build/open_items.docx` — a separate checklist generated from the current placeholders;
- `build/open_items.md` — the same checklist in reviewable text form.

`paperflow render` remains available when only the manuscript DOCX is needed. Quarto uses its
default Word reference document unless a template is configured.

## User configuration

Version-controlled project settings live in `paperflow.yml`. Machine-specific overrides belong in
the ignored `.paperflow.local.yml`; copy `paperflow.local.example.yml` as a starting point.

```yaml
executables:
  quarto: "path/to/quarto"

word:
  reference_docx: "templates/reference.docx"
```

Run `uv run paperflow config-show` to inspect the effective merged configuration and
`uv run paperflow doctor` to validate configured paths and tools.

See the [complete configuration reference](docs/configuration.md) for every supported field. To
start a new project, follow the [First manuscript guide](docs/first-manuscript.md). The
[Word-template guide](docs/word-template.md) explains how to keep publisher or institutional DOCX
templates local and validate them before use.

## Open placeholders

Use the following syntax anywhere in the configured manuscript sources:

```text
[[OPEN: Describe the missing information precisely.]]
```

The source files and exclusions are configurable. The formatting-rules file and archived sections
are excluded by default, so examples inside those files do not become real open items.

## Formatting rules

[`manuscript/manuscript_formatting_rules.md`](manuscript/manuscript_formatting_rules.md) is a stable,
version-controlled instruction file for humans and AI assistants. Each project may shorten, extend,
or replace it. It is not rendered into the manuscript.

## Word review round

Commit the manuscript before starting a round:

```bash
uv run paperflow review-start --round 1 --reviewer reviewer-name
uv run paperflow review-import --round 1 --reviewer reviewer-name --docx returned.docx
```

Importing a review never changes `manuscript/index.qmd` automatically. See
[`reviews/README.md`](reviews/README.md).

## Repository safety

Before any future public release, run the checklist in [`docs/release-checklist.md`](docs/release-checklist.md).
Word templates are deliberately local and ignored until their metadata, embedded paths, provenance,
and redistribution rights have been checked. Configure a local template through
`.paperflow.local.yml` while that review is pending.

## License

No license has been selected. Keep the repository local until that decision has been made.
