# Contributing

Paperflow uses a controlled contribution model. After the repository is made public, issues are
welcome. Discuss a change in an issue and wait for maintainer agreement before opening a pull
request. Uncoordinated pull requests may be closed so that manuscript safety and workflow scope
remain reviewable.

By submitting a contribution, you confirm that you have the right to provide it and agree that the
Paperflow-authored contribution may be distributed under the repository's MIT License. Do not
submit third-party material unless its provenance and compatible license are documented.

## Before opening an issue

- Search existing issues and documentation first.
- Describe the expected behavior, actual behavior, operating system, and relevant command output.
- Reduce examples to neutral, non-confidential content.
- Never attach manuscripts, returned Word reviews, credentials, private templates, unpublished
  data, or other confidential material.
- Use the private security-reporting process in `SECURITY.md` for suspected vulnerabilities.

## Proposing a change

After agreement in an issue, create a focused branch from the current `main` branch. Keep technical
workflow changes separate from manuscript or scientific-content changes. Do not edit generated
files in `build/`, local configuration, Word review artifacts, or `.venv/`.

Paperflow supports Python 3.11 and newer. Install uv and Quarto separately, then prepare and check a
development checkout with:

```bash
uv sync --frozen --extra dev
uv run paperflow doctor
uv run ruff check .
uv run pytest
uv run paperflow build
```

## Pull-request expectations

A pull request should link the agreed issue, explain the user-visible effect, list the checks that
were run, and include focused tests for behavioral changes. Keep commits understandable and do not
include generated DOCX files, private paths, credentials, reviewer material, or research data.

Maintainers may request changes before merge. Accepted pull requests are squash-merged, and the
source branch is deleted automatically after merge.
