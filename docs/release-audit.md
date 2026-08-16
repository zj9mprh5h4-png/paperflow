# Local release audit

Audit date: 2026-08-16

Baseline: local commit `4564674` (`main`)

Remote validation: private GitHub commit `2ab2a75` (`main`)

This report records the checks performed before Paperflow is connected to a public remote. It is
evidence for the release checklist, not a declaration that the repository is ready to publish.

## Result

The local repository boundary is clean at the audited baseline:

- all 53 tracked files are small text, SVG, or lock files;
- no DOCX, returned review file, review manifest, virtual environment, build output, local
  configuration, archive, Parquet file, or other large binary is tracked;
- the largest object across the eight-commit history is `uv.lock` at 39,216 bytes;
- the current tree and all commits were searched for common credential patterns, private names,
  email fragments, and the source project's name without a finding;
- the remaining absolute-path examples use the intentional placeholder
  `C:/Users/<username>/...` in setup documentation;
- the local template, local configuration, generated Word files, and review-round artifacts are
  ignored by Git.

Repository hygiene and local Markdown-link checks are also encoded in
`tests/test_repository_hygiene.py` so that future tracked changes are checked automatically.

## Reproducibility evidence

The following workflows have been exercised locally on Windows without administrator rights:

- user-local installation and use of uv and Quarto;
- frozen dependency synchronization;
- `paperflow doctor` with a safe local Word reference document;
- generation of the manuscript and the separate Markdown and Word Open Items reports;
- rejection of an invalid Word template without overwriting an existing valid output;
- creation and import of a Word Track Changes review round;
- verification that review import does not alter QMD or Markdown source files.

The private GitHub repository ran the complete validation workflow successfully for commit
`2ab2a75`. Both `ubuntu-latest` and `windows-latest` passed environment setup, Doctor, CLI checks,
lint, 29 tests, and the neutral-example Word build.

## Remaining publication blockers

Do not publish the repository until these decisions and checks are complete:

1. select and add a license;
2. enable GitHub private vulnerability reporting or document another private security channel;
3. change visibility deliberately and enable `main` protection when the repository becomes public;
4. run the final checklist against the exact commit intended for publication.

A private remote was created, `main` was pushed, and the repository was marked as a GitHub template.
Public visibility was not enabled and no license was selected as part of this audit.
