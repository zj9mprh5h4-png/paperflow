# Public release checklist

The repository is not ready for public distribution until every applicable item is complete.
The latest documented local findings are in the [local release audit](release-audit.md). Check each
item again against the exact commit intended for publication.

## Content and privacy

- [ ] The repository contains only the neutral example, not a private manuscript or research data.
- [ ] Git history contains no removed private manuscript, reviewer file, or sensitive binary.
- [ ] Names, email addresses, local usernames, and absolute paths are intentional or removed.
- [ ] No returned reviewer DOCX, comments, or review manifests are tracked.
- [ ] No credentials, access tokens, private URLs, or local configuration files are tracked.

## Word files

- [ ] Every tracked DOCX has passed the metadata and absolute-path audit.
- [ ] Comments, tracked changes, custom XML, and hidden content have been reviewed.
- [ ] Redistribution rights and provenance are documented for every template.

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
- [ ] Contribution and security guidance reflect the intended collaboration model.
- [x] The GitHub template setting and repository-creation instructions match the tested workflow.
- [ ] README claims match the implemented commands and tested behavior.
