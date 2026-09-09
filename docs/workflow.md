# Workflow

1. Read `SCHEMA.md`, `index.md`, and the newest `log.md` entries.
2. Add a local topic to `research-gap/backlog.json` or query Liner manually. Load `LINER_API_KEY` locally only for live calls.
3. Inspect returned metadata and select records worth preserving. Capture each selected paper in `raw/paper/` with exact source values and a SHA-256 checksum of the post-frontmatter body.
4. Treat extraction and gap output as assistance. A gap candidate is not a finding: a human verifies the raw evidence, bibliographic details, and whether the proposed connection is meaningful.
5. Create or update a canonical page only when the schema threshold is met. Use exact resolving raw paths in `sources`, add claim-level markers where ambiguity requires them, and retain the two-link rule.
6. In the same canonical operation, update `index.md` and append the required entry to `log.md`.
7. Before sharing changes, run `python -m pytest`, run `python scripts/validate_public_template.py --repo .`, and inspect the staged diff for secrets or local data.

The default workflow is local and manual. Do not enable scheduling, send Discord notifications, or publish generated candidates until a human has defined appropriate review and data-handling controls.
