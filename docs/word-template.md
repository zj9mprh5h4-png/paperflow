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

`paperflow init-local` can record the entry while creating that file:

```bash
uv run paperflow init-local --reference-docx templates/reference.local.docx
```

Add `--force` when `.paperflow.local.yml` already exists.

Absolute paths are supported for templates stored elsewhere, but a repository-relative path is
easier to move between machines when each user supplies the file locally.

## Create a neutral starting reference

One practical starting point is a manuscript generated without a custom reference:

1. leave `word.reference_docx` as `null`;
2. run `uv run paperflow build`;
3. copy `build/paper_current.docx` to `templates/reference.local.docx`;
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

When it finds a path, it names the DOCX part and the kind of link that carries it:

```text
[FAIL] Word reference local paths: absolute local path in word/_rels/settings.xml.rels
       (attached document template); docProps/app.xml (hyperlink base)
```

The path itself is never printed. It normally contains the account name of whoever produced the
template, and Doctor output should stay safe to paste into an issue. The part and the kind are
enough to find the setting in Word.

## Repair a template automatically

`paperflow sanitize-template` writes a repaired copy and removes the machine-specific entries
Doctor rejects. This is the fast path; the manual route below stays available for whatever the
command cannot fix.

```bash
uv run paperflow sanitize-template --docx "path/to/publisher-template.docx"
uv run paperflow init-local --reference-docx templates/reference.local.docx --force
uv run paperflow doctor
```

The template you point at is never modified. The repaired copy goes to
`templates/reference.local.docx` unless `--out` says otherwise, and replacing an existing copy
requires `--force`.

The command removes the attached document template, the hyperlink base, the company and manager
entries, and clears the author and last-modified-by names. Styles, page geometry, headers, footers,
numbering, and every other part of the package are left byte-identical, because those are exactly
what a reference document is for.

It reports what it did and what is left:

```text
template: /path/to/project/templates/reference.local.docx
removed: attached document template
removed: hyperlink base
removed: author name
remaining: word/_rels/document.xml.rels (external relationship)
fix: clear the remaining parts in Word; see the table in docs/word-template.md.
next: uv run paperflow init-local --reference-docx templates/reference.local.docx --force
next: uv run paperflow doctor
```

A `remaining:` line means the path sits in a link that cannot be removed without breaking the
document, such as an image inserted as a link rather than embedded. Deleting that relationship
would leave a dangling reference, so the command reports it instead and the next section explains
how to clear it in Word. Doctor stays the deciding check either way.

If the file is a `.dotx` or `.dot`, open it in Word once and save it as `.docx` first; the command
rejects anything that is not a readable DOCX package.

## Remove absolute local paths

Use this route for whatever `sanitize-template` reported as `remaining`, or when you prefer to
repair the template in Word yourself. Do not disable `word.reject_absolute_paths` to make the
build pass. Rerun `uv run paperflow doctor` after each change, because one template can carry
several.

| Reported kind | Where it comes from | How to clear it in Word |
| --- | --- | --- |
| attached document template | The DOTX or DOTM the file was created from | Developer tab, **Document Template**, set the template back to `Normal.dotm`. Without the Developer tab: File, Options, Add-ins, set **Manage** to *Templates*, then **Go**. |
| hyperlink base | A base folder prepended to every relative hyperlink | File, Info, Properties, **Advanced Properties**, *Summary* tab, clear **Hyperlink base**. |
| external relationship | Linked images or objects that were inserted as a link instead of embedded | File, Info, **Edit Links to Files**, then break each link. Reinsert the image with **Insert** instead of **Insert and Link** if it must stay. |
| subdocument link | A master document that still references subdocuments | Switch to Outline view, **Show Document**, then **Unlink** each subdocument. |
| embedded path | A path inside field codes or an embedded object | Press `Alt+F9` to show field codes, then find and remove the path. |

Word menu labels depend on the interface language; the paths above use the English interface.

Then run the Document Inspector to remove leftover personal information: File, Info, **Check for
Issues**, **Inspect Document**. The inspector removes document properties and personal data, but it
does not remove every kind of link, so treat Doctor and not the inspector as the deciding check.
Save the repaired file under `templates/` as a new local copy and keep the untouched original
outside version control.

Then build both Word outputs:

```bash
uv run paperflow build
```

The same reference formats `build/paper_current.docx` and `build/open_items_current.docx`. With
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

Keep `word.reject_absolute_paths` enabled. If Doctor reports an absolute local path, follow
[Remove absolute local paths](#remove-absolute-local-paths) instead of disabling the check merely
to make the build pass.

## Troubleshooting

If Doctor reports a missing template, check the merged value with:

```bash
uv run paperflow config-show
```

A build that stops with `Generated DOCX contains an absolute local path in …` almost always points
back at the reference document, because Quarto copies its headers, footers, and styles into every
output. The message names the part of the generated file; the same part usually carries the path in
the template. Repair the template and rebuild rather than looking for the path in the manuscript
sources.

If the DOCX is invalid or unreadable, open and resave a clean copy in Word or start from a newly
generated neutral reference. If the build succeeds but formatting is incomplete, compare the Word
style names expected by Pandoc with the styles present in the reference document. Keep formatting
adjustments separate from scientific manuscript changes.
