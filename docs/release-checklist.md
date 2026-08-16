# Public release checklist

This checklist was completed for the initial public release on 2026-08-16. The supporting evidence
is in the [local release audit](release-audit.md). Repeat every applicable item against the exact
commit intended for a future tagged release.

## Content and privacy

- [x] The repository contains only the neutral example, not a private manuscript or research data.
- [x] Git history contains no removed private manuscript, reviewer file, or sensitive binary.
- [x] Names, email addresses, local usernames, and absolute paths are intentional or removed.
- [x] No returned reviewer DOCX, comments, or review manifests are tracked.
- [x] No credentials, access tokens, private URLs, or local configuration files are tracked.

## Word files

- [x] No DOCX is tracked; repository Word metadata and absolute-path checks are not applicable.
- [x] No tracked Word file contains comments, tracked changes, custom XML, or hidden content.
- [x] No redistributable Word template is included; private local templates remain ignored.

## Reproducibility

- [x] A fresh clone can run `uv sync --frozen --extra dev`.
- [x] A fresh clone can run `uv run pytest` without private data.
- [x] A fresh clone can run `uv run paperflow doctor`.
- [x] A fresh clone can run `uv run paperflow build` when Quarto is installed.
- [x] The build creates both the manuscript and Open Items DOCX files.
- [x] A repository created with **Use this template** passes setup, Doctor, tests, and the neutral
  build without Paperflow's development history.
- [x] CI performs the same checks.

## Project governance

- [x] A license has been selected and added, with template-content scope documented.
- [x] Contribution and security guidance reflect the intended collaboration model.
- [x] The GitHub template setting and repository-creation instructions match the tested workflow.
- [x] README claims match the implemented commands and tested behavior.
