# Manuscript Formatting Rules

This file is part of the project and defines the editing conventions for humans and AI assistants.
Every user may extend, shorten, or replace these rules for their own publication. It is not included
in the rendered manuscript and is excluded from the Open Items scan by default.

## 1. Source of truth

- Treat the configured QMD manuscript and its included Markdown files as authoritative.
- Treat generated Word files as outputs for reading, review, and delivery.
- Never copy edited Word text back into QMD without an explicit, reviewed change.
- Never edit generated files under `build/` as manuscript sources.

## 2. Scientific and technical integrity

- Do not invent references, author details, figure numbers, data, or quantitative results.
- Do not silently strengthen, weaken, or otherwise alter a scientific claim.
- Keep scientific changes separate from technical formatting changes whenever practical.
- Preserve raw-data paths and identifiers unless a deliberate migration is documented.
- Preserve citation keys unless a deliberate reference migration is documented.

## 3. Open placeholders

- Mark unresolved content as `[[OPEN: concise description of what is missing]]`.
- Keep each marker specific enough that another person can resolve it without guessing.
- Do not remove a marker merely to make the Open Items report empty.
- Resolve a marker only when the missing information has been supplied or verified.
- `paperflow build` collects current markers into a separate Markdown and Word report.

## 4. Markdown structure

- Use headings to express document hierarchy, not visual size.
- Keep paragraphs as continuous Markdown lines unless a deliberate hard line break is required.
- Use semantic lists and tables rather than manually aligned text.
- Keep reusable or independently reviewed sections in separate Markdown files.
- Avoid raw Word-specific formatting in manuscript text unless the selected template requires it.

## 5. Equations and variables

- Write equations in TeX syntax.
- Use `$...$` for inline mathematics and `$$...$$` for display mathematics.
- Keep mathematical variables italic through math mode.
- Keep descriptive labels upright with `\mathrm{...}` or `\text{...}` where appropriate.
- Do not replace editable equations with screenshots.

## 6. Figures, tables, and cross-references

- Keep CrossRef IDs lowercase and use `fig-`, `tbl-`, `eq-`, or `sec-` prefixes.
- Do not type figure, table, or equation numbers manually when cross-references can generate them.
- Keep captions and legends in manuscript sources, not only inside image files.
- Prefer reproducibly generated figures and tables when source data and code are available.
- Do not overwrite raw input data when generating presentation tables or figures.

## 7. Citations and references

- Use citation keys such as `[@example2026]` instead of manually numbered citations.
- Maintain bibliographic data in the configured bibliography file.
- Do not add a reference that has not been verified against a reliable source.
- Keep citation-style decisions in CSL or the selected publication profile.

## 8. Numbers, units, and symbols

- Apply one consistent convention for decimal separators and thousands separators.
- Keep a nonbreaking space between a value and its unit when required by the target style.
- Use the multiplication sign for dimensions and multiplication where typographically appropriate.
- Define abbreviations at first use unless the target publication explicitly exempts them.
- Preserve the reported precision of validated quantitative results.

## 9. Word review

- Start review rounds from a clean, committed Git baseline.
- Ask reviewers to use Track Changes and comments rather than replacing document structure.
- Archive returned Word files locally as confidential artifacts by default.
- Import reviews as derived Markdown and diffs; never auto-apply them to the source.
- Record the review round, reviewer identifier, and baseline commit for accepted changes.

## 10. User-specific additions

Add project-, discipline-, institution-, or journal-specific rules below this heading. When a rule
conflicts with a publisher requirement or an explicit user instruction, document which rule takes
precedence.

- Add custom rules here.
