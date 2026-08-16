# Configuration reference

Paperflow loads configuration in three layers:

1. built-in schema-versioned defaults;
2. the version-controlled `paperflow.yml`;
3. the ignored `.paperflow.local.yml` for machine-specific overrides.

Mappings are merged recursively. A value in `.paperflow.local.yml` replaces the corresponding
project value, while omitted fields retain their project or default value. Unknown keys, invalid
types, unsupported schema versions, unsafe project paths, and invalid marker expressions stop the
command with an error.

Use these commands after editing configuration:

```bash
uv run paperflow config-show
uv run paperflow doctor
```

`config-show` may display local executable and template paths. Do not paste its output into public
issues without checking it first.

For agents and scripts, Doctor can return schema-versioned JSON with stable check IDs and ordered
repair steps:

```bash
uv run paperflow doctor --format json
```

Use `docs/agent-guide.md` for the deterministic diagnosis sequence. A parsed YAML file is not by
itself proof of a working configuration; Doctor also checks configured sources, tools, the active
environment, Git, and an optional Word reference document.

## Which file should contain a setting?

Commit settings that define the shared manuscript workflow to `paperflow.yml`. Put paths that vary
between machines, especially executable locations and private Word templates, in
`.paperflow.local.yml`.

| Setting type | `paperflow.yml` | `.paperflow.local.yml` |
| --- | --- | --- |
| Manuscript source and language | Yes | Usually no |
| Output names and directories | Yes | Usually no |
| OPEN marker rules | Yes | Usually no |
| Review safety policy | Yes | No |
| Git, `uv`, or Quarto executable path | No | Yes, when not on `PATH` |
| Private reference DOCX | No | Yes |

## Top-level schema

### `schema_version`

Integer configuration format version. The only supported value is `1`.

### `project`

| Field | Type | Baseline value | Effect |
| --- | --- | --- | --- |
| `name` | non-empty string | `paperflow-demo` | Human-readable project identifier used in the OPEN-items report. |
| `language` | non-empty string | `en` | Passed to Quarto as the `lang` metadata value for manuscript and OPEN-items DOCX rendering. Use a valid language tag such as `en`, `de`, or `en-GB`. |
| `manuscript` | project-relative path | `manuscript/index.qmd` | Authoritative QMD source rendered by `paperflow render` and `paperflow build`. Must remain inside the repository. |
| `formatting_rules` | project-relative path | `manuscript/manuscript_formatting_rules.md` | Version-controlled instructions for humans and AI assistants. Doctor verifies that the file exists; it is not rendered into the manuscript. |

### `paths`

All three paths must remain inside the repository.

| Field | Type | Baseline value | Effect |
| --- | --- | --- | --- |
| `output_dir` | directory path | `build` | Generated manuscript directory and the directory cleaned by `paperflow clean --yes`. |
| `work_dir` | directory path | `.work` | Temporary generated source files, including the transient OPEN-items QMD. |
| `review_dir` | directory path | `reviews` | Review rounds, manifests, imported Markdown, media, and diffs. |

### `build`

| Field | Type | Baseline value | Effect |
| --- | --- | --- | --- |
| `manuscript_filename` | bare `.docx` filename | `paper_current.docx` | Stable manuscript filename created under `paths.output_dir`. Directories and non-DOCX extensions are rejected. |
| `run_pre_render_hook` | boolean | `true` | Runs `scripts/pre_render.py` with the active Python interpreter before manuscript rendering when that file exists. Has no effect when the hook is absent. |
| `archive_previous` | boolean | `true` | Moves each superseded current DOCX into `archive_dir` after all new outputs have rendered and validated successfully. |
| `archive_dir` | project-relative directory | `build/archived` | Stores previous DOCX versions under sortable UTC names such as `paper_20260811T215623Z.docx`. It must be a dedicated directory and cannot contain a current output. |
| `embed_provenance` | boolean | `true` | Adds the build time, source commit and dirty state, Paperflow version, and Quarto version as custom Word properties. |

Paperflow derives an archive filename from the existing document's embedded
`PaperflowBuildUTC`, not from the later time at which it is archived. For documents created before
this metadata existed, the DOCX core creation time and then its filesystem modification time are
used as fallbacks. Filename collisions receive `_01`, `_02`, and so on. When adopting the stable
`*_current.docx` defaults, a matching legacy output without `_current` is migrated into the archive
after the new documents have rendered successfully.

`paperflow build` stages and validates the manuscript and Open Items DOCX before publishing either
one. Current output paths therefore stay stable for Word's **Recent** list. If Microsoft Word locks
a current file, publication stops without changing any current output. The error tells the user to
close Word and confirms that the existing document will be archived, not deleted, after a
successful retry.

### `word`

| Field | Type | Baseline value | Effect |
| --- | --- | --- | --- |
| `reference_docx` | path or `null` | `null` | Optional Quarto/Pandoc reference DOCX. Relative paths resolve from the repository; absolute paths are allowed for private machine-local templates. The same template formats the manuscript and OPEN-items DOCX. |
| `protect_inline_math` | boolean | `true` | Adds Word no-break protection to generated inline OMML equations without changing display equations. |
| `reject_absolute_paths` | boolean | `true` | Rejects generated DOCX files containing common absolute local paths. Keep enabled for portable or public documents. A rejected render does not replace an existing output. |

Doctor verifies that a configured reference DOCX exists, has the required DOCX structure, and does
not contain absolute local paths. Additional metadata and review-state checks remain part of the
[Word-template checklist](word-template.md).

### `open_items`

| Field | Type | Baseline value | Effect |
| --- | --- | --- | --- |
| `enabled` | boolean | `true` | Controls whether `paperflow build` also creates OPEN-items Markdown and DOCX reports. |
| `marker_pattern` | regular-expression string | `\[\[OPEN:\s*(.*?)\]\]` | Finds placeholders and captures their task text. The expression must contain exactly one capture group. |
| `source_globs` | list of strings | Markdown and QMD under `manuscript/` | Selects files to scan, relative to the repository root. |
| `exclude_globs` | list of strings | archived content and formatting rules | Removes matching files from the scan. Keep syntax examples and archived manuscript text excluded. |
| `output_markdown` | project-relative path | `build/open_items.md` | Reviewable text checklist. |
| `output_docx` | project-relative path | `build/open_items_current.docx` | Separate Word checklist at a stable path, formatted with the configured reference DOCX. |

The default placeholder syntax is:

```text
[[OPEN: Describe the unresolved task precisely.]]
```

### `review`

| Field | Type | Baseline value | Effect |
| --- | --- | --- | --- |
| `require_clean_git` | boolean | `true` | Prevents `review-start` from creating a baseline when tracked or untracked repository changes exist, unless `--allow-dirty` is passed explicitly. |
| `auto_apply_word_changes` | boolean | `false` | Source-safety invariant. Configuration loading fails if this is set to `true`; imported Word edits are never written automatically into the authoritative QMD. |

### `executables`

Each value is either `null`, a command name resolvable through `PATH`, or a path to an existing
executable. These are normally machine-local overrides.

| Field | Baseline value | Purpose |
| --- | --- | --- |
| `git` | `null` | Git executable used for status, commits, baselines, and manifests. |
| `uv` | `null` | `uv` executable reported by Doctor. It must already exist before the environment can be created. |
| `quarto` | `null` | Quarto executable used for rendering and Pandoc conversion. |

Example `.paperflow.local.yml`:

```yaml
executables:
  quarto: "C:/Users/<username>/AppData/Local/Programs/Quarto/1.10.18/bin/quarto.exe"

word:
  reference_docx: "templates/reference.local.docx"
```

The local file and `templates/*.docx` are ignored by Git.
