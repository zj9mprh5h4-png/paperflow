# Migrating an existing Word manuscript

This guide moves a manuscript that already exists as a DOCX into Paperflow, so that Markdown and
QMD become the authoritative sources from then on. It covers the full path: deriving Markdown from
the DOCX, reviewing what was derived, promoting it into the manuscript, restoring the section
structure, and comparing the rebuilt document against the original.

Start from a working project. Complete [Setup](setup.md) and steps 1 to 3 of the
[First manuscript guide](first-manuscript.md) first, so that `paperflow doctor` passes before any
Word content is imported.

## What the migration does and does not change

Paperflow never edits `manuscript/index.qmd` while deriving Markdown. The DOCX is copied into the
review area, converted, and compared. Only the separate promotion step writes to the manuscript,
and only when you ask for it.

The imported DOCX and everything derived from it stay under
`reviews/preworkflow-word-baseline/`, which is ignored by Git. Unpublished manuscript text does not
enter version control as a side effect of the migration.

## 1. Derive Markdown from the existing DOCX

```bash
uv run paperflow word-baseline --docx "path/to/manuscript.docx"
```

Use `--name` when a project migrates more than one document; the name becomes the slug used for the
derived files. Add `--force` to replace an earlier import of the same name.

The command archives the DOCX and writes, for the default name `article`:

| File | Contents |
| --- | --- |
| `reviews/preworkflow-word-baseline/article/incoming/<original>.docx` | The unchanged DOCX as imported |
| `.../derived/qmd.current.md` | The current QMD source rendered to Markdown, for comparison |
| `.../derived/article.accepted.md` | The DOCX with all tracked changes accepted |
| `.../derived/article.all-changes.md` | The DOCX with tracked changes preserved as markup |
| `.../derived/article.accepted.diff.md` | Unified diff between the two Markdown versions |
| `.../derived/media/` | Images extracted from the DOCX |
| `.../manifest.json` | Source hash, Git commit, and the derived paths |

## 2. Read what was derived before promoting anything

Open `article.accepted.md` and check that headings, paragraphs, lists, tables, figures, and
equations arrived in a usable shape. Use `article.all-changes.md` when the DOCX still carried
tracked changes and you need to see what was accepted.

Conversion is a structural translation, not a faithful reproduction of a Word document. Expect to
repair the following by hand:

- **Citations.** Word citation fields and formatted reference lists arrive as literal text. Move
  each source into `references/references.bib` and replace the text with a `@citation-key`.
- **Cross-references.** Figure, table, and equation numbers arrive as the literal numbers that Word
  had rendered. Replace them with Quarto CrossRef identifiers so numbering becomes automatic again.
- **Styles and layout.** Word styles, page geometry, headers, and footers do not travel through
  Markdown. They come from the reference DOCX instead; see the
  [Word-template guide](word-template.md).
- **Footnotes, comments, and hidden content.** Review these individually; comments are not
  manuscript text.

Paperflow normalizes three things automatically. Fenced ` ```math ` blocks become `$$ … $$` display
equations, Word highlight spans are unwrapped to their plain text, and the doubled brackets of
`[[OPEN: … ]]` placeholders are unescaped. The converter writes them as `\[\[OPEN: … \]\]`, which
would no longer match `open_items.marker_pattern`; without that repair every placeholder carried in
from Word would silently disappear from the OPEN-items report.

## 3. Promote the derived Markdown

```bash
uv run paperflow word-promote
```

Promotion replaces the body of `manuscript/index.qmd` with the derived text, keeps the existing
YAML front matter, and copies the extracted images to `manuscript/media/article/`.

The template ships an `index.qmd` that pulls its text in through Quarto include shortcodes:

```text
{{< include sections/front-matter.md >}}
{{< include sections/abstract.md >}}
{{< include sections/main-text.md >}}
```

Because the promoted text is written as one body, those include lines are replaced. Paperflow
refuses the promotion while they are still present and names the files that would be left
unreferenced:

```text
paperflow: Promotion would replace the include structure of manuscript/index.qmd and leave these
files unreferenced: manuscript/sections/front-matter.md, manuscript/sections/abstract.md,
manuscript/sections/main-text.md
```

Confirm the derived text is what you want, then promote explicitly:

```bash
uv run paperflow word-promote --force
```

The listed files are kept on disk. Paperflow does not delete them, and the command prints them
again as `unreferenced:` so the result is visible. `--force` is also required when
`manuscript/media/article/` already exists from an earlier promotion.

Promotion requires that `manuscript/index.qmd` starts with a closed YAML front matter block. Keep
the `---` block even when replacing everything below it.

## 4. Restore the section structure

After promotion the manuscript is a single file. Splitting it back into sections keeps later
editing, reviewing, and OPEN-item grouping manageable, because Paperflow groups OPEN items by
source file and heading.

1. Cut each top-level part of the promoted body into its own file under `manuscript/sections/`.
   Reuse the files that were reported as unreferenced instead of creating new ones where the
   content matches.
2. Reduce `manuscript/index.qmd` to the front matter plus one include per section, in reading
   order.
3. Delete any section file that the migration made obsolete, deliberately and in its own commit.

Step 3 is not optional tidying. A section file that is no longer included is still matched by
`open_items.source_globs` and therefore still scanned, so its `[[OPEN: … ]]` placeholders keep
appearing in `build/open_items.md` and in the Word checklist even though the text is no longer part
of the manuscript. Until the leftovers are removed, the OPEN-items report describes a document that
is no longer being built.

Confirm the result before continuing:

```bash
uv run paperflow build
```

The reported `open_items_count` must match what the manuscript actually still contains.

Section files are ordinary Markdown. Their names are free; only the include lines in
`manuscript/index.qmd` decide what is rendered and in which order.

## 5. Record what is still missing

While reading the promoted text, mark every open question in place rather than in a separate list:

```text
[[OPEN: Restore the citation for the 2019 cohort figure.]]
```

`paperflow build` collects these into `build/open_items.md` and a separate Word checklist, grouped
by file and heading.

## 6. Rebuild and compare against the original

```bash
uv run paperflow build
```

Open `build/paper_current.docx` next to the original DOCX and compare structure, headings, tables,
figures, equations, and reference formatting. A successful build proves that generation works, not
that the migration is scientifically complete.

Repeat step 4 to step 6 until the rebuilt document is an acceptable replacement. From that point
on, the QMD and Markdown sources are authoritative and the original DOCX is history: use
[review rounds](commands.md#word-review-rounds) for further Word feedback rather than editing a
generated document.

## Repeating or abandoning a migration

Every promotion writes `promotion-manifest.json` next to the derived files, recording the accepted
Markdown, its hash, and the Git commit. To redo a migration, commit or stash the current manuscript
first, then rerun `word-baseline --force` and `word-promote --force`. Because the manuscript is
version-controlled, `git checkout -- manuscript/` restores the previous state at any point.
