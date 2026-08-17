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
entries, clears the author and last-modified-by names, and strips file paths out of image
alternative text. Styles, page geometry, headers, footers, numbering, and every other part of the
package are left byte-identical, because those are exactly what a reference document is for.

The alt-text case is the one that catches people out. Word stores the original file path of a
picture in its alternative text, so a journal logo in a header commonly carries something like
`C:\Users\<author>\Documents\Templates\logo1.jpg`. Nothing in the document body shows it, `Alt+F9`
does not reveal it because it is not a field, and the picture itself is embedded and unaffected.
The path still travels with every copy of the template and reaches every generated document.
Paperflow removes only the path; a real description next to it is preserved.

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
| image alt text | The original file path Word stored when the picture was inserted | Right-click the picture, **View Alt Text**, and clear the description. In a header, double-click into the header area first. `sanitize-template` already does this. |
| embedded path | A path inside field codes or an embedded object | Press `Alt+F9` to show field codes, then find and remove the path. Inside a header, double-click into the header area first, or field codes stay hidden. |

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

## Map manuscript content onto template styles

A reference document contributes styles, headers, footers, and page geometry. It does **not**
contribute text. Whatever stands in the body of a publisher template — the author block, the
affiliation lines, the correspondence and keyword paragraphs — is discarded during rendering and
never reaches a generated document. That is deliberate: otherwise every build would carry the
template's placeholder authors.

Such content therefore belongs in the manuscript sources, where it is version-controlled,
diffable, and reviewable like the rest of the text. It still gets the publisher's formatting,
because a Markdown block can request a named Word style.

### What happens without any explicit mapping

Pandoc applies a fixed set of styles on its own when the reference defines them: `Title`,
`Subtitle`, `Author`, `Date`, `Abstract`, `Abstract Title`, `Heading 1` to `Heading 9`,
`Body Text`, `Caption`, `Bibliography`, and a few more.

Structured author metadata in the QMD front matter reaches a DOCX only in part. Rendering a
document with `author`, `affiliations`, `email`, `corresponding`, and `keywords` produces exactly
this:

| Style in the output | Content |
| --- | --- |
| `Title` | the title |
| `Author` | the author names, one paragraph each |
| `Abstract Title`, `Abstract` | the abstract |

Affiliations, e-mail addresses, the corresponding-author flag, and keywords are dropped. Do not
rely on structured metadata for publisher front matter; use the explicit mapping below.

### Find the style names

```bash
uv run paperflow template-styles
```

The command lists the paragraph and character styles of the configured reference document, split
into the ones Pandoc applies on its own and the ones available for an explicit request. Use
`--docx` to inspect a template that is not configured yet, and `--all` to include styles Word
marks as hidden. Names must be used exactly as printed, including capitalisation.

### Start from the template's own boilerplate

The template already contains the block, correctly formatted. Instead of retyping it, convert it:

```bash
uv run paperflow template-front-matter --out manuscript/sections/front-matter.md --force
```

Every paragraph of the template body becomes Markdown that requests the same style, superscript
runs become `^…^`, headings become `#` levels, and unstyled paragraphs stay plain text. Without
`--out` the Markdown goes to standard output, so it can be inspected before anything is written.
Notes about what was skipped go to standard error, which keeps redirected output clean:

```text
note: styles requested: Frontiers Author, Frontiers Affiliation
note: skipped 1 table(s)
note: review the result: it is the template's placeholder text, not yours
```

Tables and images are not converted. What you get is the publisher's placeholder text — "First
Author", "Laboratory X", "keyword1" — as a starting point to overwrite, not as content to keep.

### Request a style

A `custom-style` div formats whole paragraphs, a span formats text inside a paragraph:

```markdown
::: {custom-style="Frontiers Author"}
First Author^1^, Second Author^2^\*, Third Author^1,2^
:::

::: {custom-style="Frontiers Affiliation"}
^1^Laboratory X, Institute X, Department X, Organization X, City X, Country
:::

::: {custom-style="Frontiers Correspondence"}
\* Correspondence:
Corresponding Author
email@uni.edu
:::

::: {custom-style="Frontiers Keywords"}
Keywords: keyword1, keyword2, keyword3, keyword4, keyword5
:::
```

`^1^` produces a superscript marker, and `\*` escapes an asterisk that would otherwise start
emphasis. The neutral example uses the same mechanism in
`manuscript/sections/front-matter.md` for `Title` and `Author`.

### Doctor checks the mapping

A misspelled style name is not an error for Pandoc. It renders as unstyled text, silently, and
swapping the reference for another publisher's template breaks every mapping just as quietly.
Doctor therefore reads the manuscript entry point and everything it includes, collects the
requested names, and compares them with the reference document:

```text
[FAIL] manuscript styles in reference: not defined in the reference:
       'Frontiers Authour' at manuscript/sections/front-matter.md:1
  Fix: Did you mean 'Frontiers Author'? Used at manuscript/sections/front-matter.md:1.
  Fix: Run uv run paperflow template-styles to list the names the reference defines.
  Fix: Correct the custom-style name, or add the style to the reference document.
```

The check runs only when a reference document is configured, because without one there is no
template to check against.

### Documents that need none of this

Nothing in Paperflow requires an author block. A report, a thesis chapter, or an internal note can
delete `manuscript/sections/front-matter.md` and remove its include from `manuscript/index.qmd`.
Paperflow has no opinion about which front matter a document carries; it only renders what the
sources contain.

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
