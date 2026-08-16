# Word review workflow

Each review round is tied to a Git baseline commit and an exact outgoing DOCX.

## Start a round

```bash
uv run paperflow review-start --round 1 --reviewer reviewer-name
```

The command refuses a dirty Git state unless `--allow-dirty` is explicitly passed.

Send the generated file from `reviews/round-XX/outgoing/` to the named reviewer. In Word, the
reviewer should enable **Track Changes**, make the requested edits, save a new DOCX, and return that
file without replacing the archived baseline.

## Import a returned DOCX

```bash
uv run paperflow review-import --round 1 --reviewer reviewer-name --docx returned.docx
```

The import archives the DOCX locally and creates accepted Markdown, all-changes Markdown, and a diff.
It does not change the authoritative QMD source.

The import also verifies the original baseline DOCX against the SHA-256 hash and Git commit stored
when the round started. Its manifest records the original baseline commit, the current import
commit, the incoming hash, and counts of tracked insertions and deletions. A file with already
accepted changes can still produce an accepted diff, but its tracked-change counts will be zero and
the all-changes Markdown cannot preserve reviewer attribution for those accepted edits.

Inspect these files under `reviews/round-XX/derived/<reviewer>/`:

- `baseline.accepted.md` — baseline converted with changes accepted;
- `<reviewer>.accepted.md` — returned Word document with changes accepted;
- `<reviewer>.all-changes.md` — insertions and deletions with available Word metadata;
- `<reviewer>.accepted.diff.md` — unified baseline-to-accepted diff;
- `import-manifest.json` — provenance, hashes, commits, and tracked-change counts.

Review artifacts are ignored because they may contain names, comments, unpublished material, or
other confidential information. Do not force-add them to Git without an explicit release decision.
