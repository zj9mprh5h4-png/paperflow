# Word review workflow

Each review round is tied to a Git baseline commit and an exact outgoing DOCX.

## Start a round

```bash
uv run paperflow review-start --round 1 --reviewer reviewer-name
```

The command refuses a dirty Git state unless `--allow-dirty` is explicitly passed.

## Import a returned DOCX

```bash
uv run paperflow review-import --round 1 --reviewer reviewer-name --docx returned.docx
```

The import archives the DOCX locally and creates accepted Markdown, all-changes Markdown, and a diff.
It does not change the authoritative QMD source.

Review artifacts are ignored because they may contain names, comments, unpublished material, or
other confidential information. Do not force-add them to Git without an explicit release decision.
