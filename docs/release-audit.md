# Local release audit

Audit date: 2026-08-16

Final pre-publication baseline: commit `e9e6656` (`main`)

Remote validation: GitHub Actions run `31940502181` for commit `e9e6656` (`main`)

This report records the checks performed for Paperflow's initial public release and the repository
controls enabled immediately afterward.

## Result

The repository boundary is clean at the audited baseline:

- all 63 tracked files are small text, SVG, license, placeholder, or lock files;
- no DOCX, returned review file, review manifest, virtual environment, build output, local
  configuration, archive, Parquet file, or other large binary is tracked;
- the largest object across the 18-commit history is `uv.lock` at 39,216 bytes;
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

GitHub ran the complete validation workflow successfully for the final pre-publication commit
`e9e6656`. Both `ubuntu-latest` and `windows-latest` passed environment setup, Doctor, CLI checks,
lint, 32 tests, and the neutral-example Word build.

## Template smoke test

On 2026-08-16, a temporary private repository was generated with GitHub's **Use this template**
workflow and then cloned locally. The generated repository:

- identified Paperflow as its template source but contained only one new initial commit;
- completed `uv sync --frozen --extra dev` without a local configuration or Word template;
- passed Doctor, Ruff, all 29 tests, and the neutral manuscript plus Open Items Word build;
- passed the complete GitHub Actions matrix on both its initial commit and an explicit test commit;
- kept `.venv`, `.uv-cache`, `.work`, and generated build outputs outside Git tracking.

The temporary GitHub repository and local test checkout were deleted after verification.

## License decision

Paperflow-authored software, automation, documentation, tests, and neutral examples use the MIT
License, Copyright (c) 2026 Sam Bleker. `LICENSE-SCOPE.md` preserves that license for inherited
Paperflow materials while expressly distinguishing independently authored manuscripts,
bibliographies, data, figures, reviews, templates, and generated documents.

## GitHub publication controls

On 2026-08-16, the repository was deliberately made public after the final history and content
audit. GitHub identifies the repository as an MIT-licensed template, and private vulnerability
reporting is enabled.

The `main` branch protection applies to administrators and requires:

- a pull request, with zero mandatory approvals while Paperflow has one maintainer;
- successful, up-to-date `ubuntu-latest` and `windows-latest` checks;
- linear history and resolution of all review conversations;
- no force pushes and no branch deletion.

The initial public-release checklist is complete. Paperflow remains an early development release;
repeat the checklist before publishing a tagged version.
