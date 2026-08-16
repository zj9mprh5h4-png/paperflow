# Agent guide

Paperflow can be used with or without an AI coding agent. `AGENTS.md` gives compatible agents a
safe project baseline, while this guide defines the deterministic configuration and change
workflow. Users may adapt both files for their project. Paperflow itself has no Codex dependency.

## Source hierarchy

Use the following sources in order instead of inferring project state from filenames:

1. explicit user instructions and documented publisher requirements;
2. the effective configuration produced from defaults, `paperflow.yml`, and
   `.paperflow.local.yml`;
3. the configured manuscript and formatting-rules files;
4. Paperflow's command and configuration documentation;
5. implementation code and tests when behavior is still unclear.

User instructions do not authorize invented scientific content, disclosure of confidential
material, automatic Word-to-QMD edits, or overwriting raw data.

## Deterministic configuration diagnosis

Run the machine-readable Doctor from the repository root:

```bash
uv run paperflow doctor --format json
```

The JSON document has a `schema_version` set to `1`, a top-level `ok` boolean, and a `checks`
array. Every check contains:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier for the component being checked. |
| `label` | Human-readable check name. |
| `status` | `ok` or `fail`. |
| `detail` | Observed value or exact failure message. |
| `error_code` | Structured configuration error code when configuration loading failed. |
| `remediation` | Ordered repair steps for a failed check. |

For every failed check:

1. report its `id`, `error_code` when present, and `detail`;
2. follow the supplied remediation in order;
3. change only the file that owns the setting;
4. rerun Doctor and confirm that the check passes;
5. state what was changed and show the final `ok` result without exposing private paths.

Do not claim that configuration is valid merely because the YAML parses. Doctor also checks source
files, the optional Word template, the active Python environment, external tools, Git, Quarto,
Pandoc, and required Python packages.

If uv itself is missing, the Paperflow command cannot start. Ask the user to install uv using
`docs/setup.md`; do not add an automatic installer or use ad-hoc `pip install`. Quarto may be absent
while basic configuration is being edited, but it is required before a successful render.

## Inspecting effective values

Only after configuration loading succeeds, run:

```bash
uv run paperflow config-show
```

Use the result to locate the authoritative manuscript, formatting rules, output directory, Open
Items sources, review policy, and configured executables. `config-show` may reveal machine-local
paths from `.paperflow.local.yml`; never quote or transmit the complete output without checking it.

Shared project behavior belongs in `paperflow.yml`. Executable locations and private Word-template
paths belong in the ignored `.paperflow.local.yml`. Never solve a local path problem by committing
another user's absolute path.

## Change workflow

Before editing manuscript content, inspect the configured source context and read the configured
formatting rules. Keep unresolved facts as `[[OPEN: ...]]`. Do not use generated Word files as a
second source of truth.

Choose verification by change type:

| Change | Required checks |
| --- | --- |
| Configuration only | `uv run paperflow doctor --format json` and the affected command. |
| Python, CLI, or validation | `uv run pytest` and `uv run ruff check .`. |
| QMD or rendering | The relevant tests plus `uv run paperflow build` when Quarto is available. |
| Documentation only | Markdown-link and repository-hygiene tests. |
| Word review application | Verify round, reviewer, baseline commit, and generated diff first. |

When a check cannot run, explain the missing prerequisite and the exact setup step. Do not convert
a skipped or unavailable check into a successful result.

## Why there is no static code-understanding file

A second YAML or JSON description of Paperflow's code and configuration would duplicate the
validator and drift as the implementation changes. `AGENTS.md` therefore points to this concise
runbook, while `paperflow doctor --format json` supplies current machine-readable facts and repair
steps directly from the running version of Paperflow.
