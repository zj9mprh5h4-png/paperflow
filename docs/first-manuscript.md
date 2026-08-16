# First manuscript

This guide starts with a clean Paperflow template and ends with an editable manuscript DOCX plus a
separate OPEN-items DOCX. The QMD and Markdown files remain the authoritative sources.

## 1. Create a project copy

On Paperflow's GitHub page, choose **Use this template** and then **Create a new repository**. Select
the owner, give the repository the manuscript's own name, and use private visibility for
unpublished or confidential work. Do not create a fork: a template produces an independent project
without Paperflow's development history.

Clone the newly created manuscript repository and enter it:

```bash
git clone https://github.com/OWNER/MANUSCRIPT-REPOSITORY.git
cd MANUSCRIPT-REPOSITORY
```

Paperflow updates are not applied to an existing manuscript repository automatically. Adopt later
workflow changes only after reviewing them against the manuscript's configuration and local files.

`AGENTS.md` provides optional instructions for Codex-compatible agents and is copied with the
template. Review and adapt it together with `docs/agent-guide.md`, or remove it if the project does
not use an agent. Paperflow itself does not require Codex.

Keep `LICENSE` and `LICENSE-SCOPE.md` for the inherited Paperflow workflow. The MIT License does not
automatically apply to original manuscript text, bibliographies, research data, figures, reviews,
or templates that you add. Document the rights status of that project content separately before
sharing the repository.

Open a terminal in the new repository and confirm that Git points to the intended project:

```bash
git rev-parse --show-toplevel
git status --short
```

## 2. Install and validate prerequisites

Install Git, `uv`, and Quarto yourself as described in [Setup](setup.md). Then create the locked
Python environment and the machine-specific configuration:

```bash
uv sync --frozen --extra dev
uv run paperflow init-local
uv run paperflow doctor
```

`init-local` writes the ignored `.paperflow.local.yml`. It records only what this machine actually
needs: tools on `PATH` stay `null`, an installation outside `PATH` is recorded with its absolute
path. Because the file is ignored by Git, repeat this step on every machine that clones the
manuscript repository.

Resolve every blocking Doctor result before editing manuscript content.

## 3. Set the shared project configuration

Edit `paperflow.yml` first:

```yaml
project:
  name: my-manuscript
  language: en
  manuscript: manuscript/index.qmd
  formatting_rules: manuscript/manuscript_formatting_rules.md

build:
  manuscript_filename: manuscript_current.docx
  archive_previous: true
  archive_dir: build/archived
  embed_provenance: true
```

Keep shared settings version-controlled. See the [configuration reference](configuration.md) before
changing paths, marker expressions, safety options, or review behavior.

## 4. Replace the neutral manuscript

`manuscript/index.qmd` is the authoritative entry point. The baseline includes three Markdown
sections:

- `manuscript/sections/front-matter.md`;
- `manuscript/sections/abstract.md`;
- `manuscript/sections/main-text.md`.

Replace their neutral text with the new manuscript. You may add or remove section files, but update
the include statements in `manuscript/index.qmd` deliberately. Do not edit a generated DOCX as the
manuscript source.

If the manuscript already exists as a Word document, do not retype it. Follow the
[Word-migration guide](word-migration.md) instead, which derives Markdown from the DOCX, compares
it with the current source, and promotes it only after an explicit confirmation.

Keep citations in `references/references.bib` and use stable citation keys. Use TeX syntax for
equations and Quarto CrossRef identifiers instead of manual figure, table, or equation numbering.

## 5. Adapt the formatting rules

Review `manuscript/manuscript_formatting_rules.md`. Shorten, extend, or replace rules to match the
project, publisher, language, terminology, units, and scientific review requirements. Keep this
file version-controlled so humans and AI assistants use the same constraints.

Formatting rules are instructions only. They are excluded from manuscript rendering and from the
default OPEN-items scan.

## 6. Record unresolved work

Place precise markers in manuscript Markdown or QMD:

```text
[[OPEN: Verify the sample size against the final analysis dataset.]]
```

Do not use OPEN markers for information that has already been resolved. Paperflow groups the
markers by manuscript headings and records their source file and line number.

## 7. Configure an optional Word template

The first build can use Quarto's default Word formatting. For publisher or institutional
formatting, follow the [Word-template guide](word-template.md). Keep private or unreviewed DOCX files
under `templates/` and configure them only through the ignored `.paperflow.local.yml`.

A prepared template usually needs one repair step, because it tends to carry a link to the machine
it was built on:

```bash
uv run paperflow sanitize-template --docx "path/to/your-template.docx"
uv run paperflow init-local --reference-docx templates/reference.local.docx --force
```

The original file stays untouched; the repaired copy is what Paperflow uses.

Run Doctor again after changing the template:

```bash
uv run paperflow doctor
```

## 8. Build and inspect the outputs

```bash
uv run paperflow build
```

The baseline configuration creates:

- `build/paper_current.docx` — editable manuscript output at a stable path;
- `build/open_items.md` — reviewable task checklist;
- `build/open_items_current.docx` — separate Word task checklist at a stable path.

On the next successful build, Paperflow moves the previous current DOCX files to
`build/archived/` and names them with their embedded UTC build time. If Word has a current file
open, close it and rerun the build; the existing file will be archived, not deleted, after the
successful retry.

Inspect the Word documents for page layout, styles, figures, tables, equations, citations, headers,
footers, and OPEN-item completeness. A successful command proves structural generation, not final
scientific or typographic approval.

## 9. Check source-control boundaries

Before the first project commit:

```bash
git status --short
git check-ignore .paperflow.local.yml templates/reference.local.docx build/paper_current.docx
```

Only project sources, shared configuration, documentation, and intentionally public assets should
be committed. Never commit credentials, returned review files, private templates, generated Word
documents, `.venv`, or raw confidential data.
