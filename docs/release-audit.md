# Local release audit

Audit date: 2026-08-16

Baseline: local commit `4564674` (`main`)

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

The repository defines equivalent validation jobs for Windows and Linux. Remote CI has not yet run
because no GitHub repository or remote has been created.

## Remaining publication blockers

Do not publish the repository until these decisions and checks are complete:

1. select and add a license;
2. decide whether the repository accepts contributions and security reports, then align the
   governance documents;
3. create the remote repository and confirm that the Windows and Linux CI jobs pass there;
4. review GitHub repository visibility and template-repository settings;
5. run the final checklist against the exact commit intended for publication.

No remote was created, no branch was pushed, and no license was selected as part of this audit.
