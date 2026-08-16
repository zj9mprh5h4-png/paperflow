# Word-template workflow

Paperflow passes an optional reference DOCX to Quarto/Pandoc. The reference document supplies Word
styles, page geometry, headers, footers, and related document defaults; manuscript text continues
to come exclusively from QMD and Markdown sources.

## Keep templates local by default

Place a working reference document under `templates/`, for example:

```text
templates/reference.local.docx
```

`templates/*.docx` is ignored by Git. Configure the file in the ignored
`.paperflow.local.yml`:

```yaml
word:
  reference_docx: "templates/reference.local.docx"
```

Absolute paths are supported for templates stored elsewhere, but a repository-relative path is
easier to move between machines when each user supplies the file locally.

## Create a neutral starting reference

One practical starting point is a manuscript generated without a custom reference:

1. leave `word.reference_docx` as `null`;
2. run `uv run paperflow build`;
3. copy `build/paper.docx` to `templates/reference.local.docx`;
4. open the copy in Word;
5. remove manuscript body text while preserving intentional styles, section settings, headers, and
   footers;
6. remove comments, tracked changes, hidden content, and identifying metadata before saving.

For a publisher template, work on a local copy. Confirm that its license or publisher terms allow
the intended use and redistribution before ever committing it.

## Validate before building

```bash
uv run paperflow doctor
```

Doctor checks that the configured reference:

- exists;
- has the required DOCX package structure;
- contains no common absolute local paths.

Then build both Word outputs:

```bash
uv run paperflow build
```

The same reference formats `build/paper.docx` and `build/open_items.docx`. With
`word.reject_absolute_paths: true`, a generated DOCX containing a detected local path is rejected
without replacing an existing valid output.

## Manual template checklist

Automated structural checks do not replace a deliberate Word inspection. Before relying on or
publishing a template, verify:

- redistribution rights and provenance;
- creator, last-modified-by, company, and custom metadata;
- comments, tracked changes, hidden text, and document protection;
- custom XML and embedded objects;
- attached-template relationships and external links;
- headers, footers, fields, and section breaks;
- required paragraph, character, table, caption, bibliography, and equation styles;
- page size, margins, columns, numbering, and language defaults;
- absence of manuscript, reviewer, patient, participant, or institutional confidential content.

Keep `word.reject_absolute_paths` enabled. If Doctor reports an absolute local path, sanitize a copy
of the template instead of disabling the check merely to make the build pass.

## Troubleshooting

If Doctor reports a missing template, check the merged value with:

```bash
uv run paperflow config-show
```

If the DOCX is invalid or unreadable, open and resave a clean copy in Word or start from a newly
generated neutral reference. If the build succeeds but formatting is incomplete, compare the Word
style names expected by Pandoc with the styles present in the reference document. Keep formatting
adjustments separate from scientific manuscript changes.
