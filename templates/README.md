# Local Word templates

Word templates are intentionally not included in the neutral repository baseline.

During local development, a reference DOCX may be placed in this directory. Before any template is
committed or distributed, verify all of the following:

- redistribution is permitted;
- creator and last-modified-by metadata are intentionally public or removed;
- comments, tracked changes, custom XML, and hidden document content are absent;
- attached-template relationships and absolute local paths are absent;
- the file contains styles and layout only, not manuscript text.

`templates/*.docx` is ignored until the public template policy is implemented.

See [`docs/word-template.md`](../docs/word-template.md) for the complete local setup, validation,
and troubleshooting workflow.
