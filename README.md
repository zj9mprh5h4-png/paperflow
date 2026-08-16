# Paperflow

Paperflow is a local-first workflow for writing in Markdown or Quarto, generating editable Word
documents, and importing tracked Word reviews without turning DOCX files into a second source of
truth.

Paperflow is publicly available as an early development release under the MIT License. Interfaces
and workflows may still change before the first stable release.

## Start a manuscript repository

Open the Paperflow GitHub page and choose **Use this template** and then **Create a new
repository**. Give the new repository the manuscript's own name and keep it private whenever it
will contain unpublished or confidential material. Clone that new repository—not the Paperflow
development repository—and follow the [First manuscript guide](docs/first-manuscript.md).

Using the template creates an independent project without Paperflow's development history. It is
not a fork, and later Paperflow changes are not applied to manuscript repositories automatically.

## What works today

- Render `manuscript/index.qmd` to the stable `build/paper_current.docx` path.
- Generate `build/open_items_current.docx` from every current `[[OPEN: ...]]` placeholder.
- Archive superseded DOCX files with their original UTC build timestamp and provenance.
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

- `build/paper_current.docx` — the editable manuscript;
- `build/open_items_current.docx` — a separate checklist from the current placeholders;
- `build/open_items.md` — the same checklist in reviewable text form.

`paperflow render` remains available when only the manuscript DOCX is needed. Quarto uses its
default Word reference document unless a template is configured.

Current paths stay unchanged so Microsoft Word's **Recent** entry remains useful. Before a
successful rebuild replaces a current file, Paperflow moves it to `build/archived/` with its
original UTC build time, for example `paper_20260811T215623Z.docx`. Manuscript and Open Items are
staged and validated before `paperflow build` publishes either current file. If Word locks an
existing document, Paperflow asks the user to close it and explicitly confirms that the existing
document will be archived, not deleted, after the successful retry.

Generated DOCX files contain `PaperflowBuildUTC`, `PaperflowSourceCommit`,
`PaperflowSourceDirty`, `PaperflowVersion`, and `PaperflowQuartoVersion` as custom Word
properties. `paperflow clean --yes` preserves archived versions; deleting them additionally
requires `paperflow clean --yes --include-archive`.

## User configuration

Version-controlled project settings live in `paperflow.yml`. Machine-specific overrides belong in
the ignored `.paperflow.local.yml`. Generate that file from the tools present on the current
machine:

```bash
uv run paperflow init-local
```

Tools on `PATH` need no entry and are recorded as `null`. An installation outside `PATH` is searched
in the locations documented in [`docs/setup.md`](docs/setup.md) and recorded with its absolute path;
`--quarto`, `--git`, and `--uv` record an explicit path instead. `paperflow.local.example.yml`
remains available as a starting point for editing the file by hand.

```yaml
build:
  manuscript_filename: paper_current.docx
  archive_previous: true
  archive_dir: build/archived
  embed_provenance: true

executables:
  quarto: "path/to/quarto"

word:
  reference_docx: "templates/reference.docx"
```

Run `uv run paperflow config-show` to inspect the effective merged configuration and
`uv run paperflow doctor` to validate configured paths and tools.

For machine-readable diagnostics with exact repair steps, use:

```bash
uv run paperflow doctor --format json
```

See the [complete configuration reference](docs/configuration.md) for every supported field. To
start a new project, follow the [First manuscript guide](docs/first-manuscript.md). The
[Word-template guide](docs/word-template.md) explains how to keep publisher or institutional DOCX
templates local and validate them before use.

The [command reference](docs/commands.md) lists every CLI command, safety flag, output, and exit
status.

## Optional AI-agent guidance

[`AGENTS.md`](AGENTS.md) supplies a safe project baseline to Codex-compatible agents and points to
the deterministic [`docs/agent-guide.md`](docs/agent-guide.md) workflow. Both files are copied into
repositories created from this template and may be adapted or removed deliberately. Paperflow
itself does not require Codex or another AI agent.

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

## Existing Word manuscripts

To move a manuscript that already exists as a DOCX into Paperflow, follow the
[Word-migration guide](docs/word-migration.md). Deriving Markdown never touches the QMD source;
only the separate, explicit promotion step writes to the manuscript.

## Repository safety

The initial public-release evidence is recorded in
[`docs/release-audit.md`](docs/release-audit.md). Repeat the checks in
[`docs/release-checklist.md`](docs/release-checklist.md) before a future tagged release.
Word templates are deliberately local and ignored until their metadata, embedded paths, provenance,
and redistribution rights have been checked. Configure a local template through
`.paperflow.local.yml` while that review is pending. When Doctor reports an absolute local path in
a template, it names the DOCX part and the kind of link but never the path itself.

`paperflow sanitize-template --docx <template>` writes a repaired copy without touching the
original, removing the attached document template, hyperlink base, author metadata, and file paths
stored in image alternative text, while leaving styles and layout byte-identical. It reports anything it could not repair;
[`docs/word-template.md`](docs/word-template.md#remove-absolute-local-paths) explains which Word
setting to clear for those.

Public collaboration follows the controlled process in [`CONTRIBUTING.md`](CONTRIBUTING.md).
Report security concerns only through GitHub's private vulnerability-reporting channel described in
[`SECURITY.md`](SECURITY.md).

## License

Paperflow-authored software, automation, documentation, tests, and neutral examples are licensed
under the [MIT License](LICENSE), Copyright (c) 2026 Sam Bleker. See
[`LICENSE-SCOPE.md`](LICENSE-SCOPE.md) for the template boundary.

Original manuscripts, bibliographies, research data, figures, Word reviews, and private templates
added by users are not automatically licensed under MIT. Their respective rights holders decide
whether and how those materials are licensed.
