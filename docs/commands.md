# Command reference

Run commands from the repository root through the locked environment:

```bash
uv run paperflow --version
uv run paperflow --help
uv run paperflow <command> --help
```

A file passed with `--docx` is resolved against the current working directory, like any other
command-line tool, and `~` is expanded. Configured paths in `paperflow.yml` behave differently:
they always resolve from the repository root.

## Build and configuration

| Command | Purpose |
| --- | --- |
| `paperflow doctor` | Validate configuration, sources, reference DOCX, environment, external tools, Git, Quarto, Pandoc, and required Python packages. |
| `paperflow doctor --format json` | Emit the same checks as schema-versioned JSON with stable IDs, error codes, and ordered remediation steps for agents and other tools. |
| `paperflow doctor --allow-missing-tools` | Print all Doctor results but return success even when checks fail. Intended only for diagnostics. |
| `paperflow config-show` | Print the effective merge of defaults, `paperflow.yml`, and `.paperflow.local.yml`. The output can contain private machine paths. |
| `paperflow init-local` | Create the ignored `.paperflow.local.yml` from the tools found on this machine. Tools on `PATH` are recorded as `null`; a Git, `uv`, or Quarto installation outside `PATH` is searched in the locations documented in [Setup](setup.md) and recorded with its absolute path. Refuses to replace an existing file without `--force`. |
| `paperflow init-local --quarto PATH` | Record an explicit executable instead of searching for it. `--git` and `--uv` work the same way. A path that does not exist is rejected before the file is written. |
| `paperflow init-local --reference-docx PATH` | Additionally record a local Word reference DOCX in the generated file. |
| `paperflow render` | Render only the configured manuscript DOCX. |
| `paperflow open-items` | Scan configured sources and create the separate OPEN-items Markdown and DOCX reports. |
| `paperflow build` | Render the manuscript and, when enabled, both OPEN-items reports. |
| `paperflow clean --yes` | Remove current generated files from `paths.output_dir` while preserving `.gitkeep` and `build.archive_dir`. Without `--yes`, the command refuses to run. |
| `paperflow clean --yes --include-archive` | Also remove the archived DOCX history. This explicit extra flag prevents accidental loss of prior generated versions. The command refuses, before deleting anything, when `build.archive_dir` holds content other than archived DOCX files. |

## Word review rounds

| Command | Purpose |
| --- | --- |
| `paperflow review-start --round N --reviewer NAME` | Render and archive an exact baseline, create the outgoing reviewer DOCX, and record hashes, Git commit, and tool versions. Requires clean Git by default. |
| `paperflow review-start ... --allow-dirty` | Explicitly permit a dirty baseline. Use only when the exception is understood and documented. |
| `paperflow review-start ... --force` | Replace an existing local round directory. This can overwrite ignored review artifacts. |
| `paperflow review-import --round N --reviewer NAME --docx FILE` | Verify the round baseline and returned DOCX, archive the return, and create baseline, accepted, all-changes, diff, and import-manifest files. Never edits QMD automatically. |
| `paperflow review-import ... --force` | Replace an existing archived import for the same reviewer. |
| `paperflow review-diff --round N --reviewer NAME` | Deterministically regenerate the accepted baseline-to-review diff. |

## Existing Word manuscripts

The [Word-migration guide](word-migration.md) walks through the complete path from an existing DOCX
to authoritative Markdown sources.

| Command | Purpose |
| --- | --- |
| `paperflow word-baseline --docx FILE [--name NAME]` | Archive an existing DOCX, derive accepted and all-changes Markdown, and compare it with the configured QMD source. Does not change QMD. |
| `paperflow word-promote [--name NAME]` | Explicitly promote a previously derived accepted baseline into the configured QMD while preserving QMD front matter and copying extracted media. This is the only intentional Word-to-QMD promotion command. |

Both Word-baseline commands require `--force` before replacing existing derived or promoted
artifacts. `word-promote` additionally refuses without `--force` when the configured QMD still
pulls its text in through Quarto include shortcodes, because promotion replaces them; the error
names the section files that would be left unreferenced. Those files are never deleted, and a
forced promotion prints them again as `unreferenced:`.

## Exit status

| Status | Meaning |
| --- | --- |
| `0` | Command completed successfully. |
| `1` | Doctor found one or more blocking checks. |
| `2` | Invalid CLI usage or an expected Paperflow workflow error. |

Unexpected Python, operating-system, Quarto, or Git failures may return another non-zero status.
