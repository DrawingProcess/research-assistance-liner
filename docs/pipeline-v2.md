# Pipeline v2

Optional local runner: `python src/daily_pipeline.py` from the repository root after `set -a; . ./.env; set +a`.

Requires `LINER_API_KEY`. Discord is optional (`DISCORD_CHANNEL_ID`). This template does not enable a scheduler.

```text
Monday     coverage scout → research-gap/coverage_candidates.json (not auto-enqueued)
Daily      up to 3 pending topics → Scholar → extract new URLs only → topic hub
Thu / Sun  missing wikilink → Scholar validation → comparison or human queue
```

Hub pages use sections Definition, Open challenges, Papers, Themes, Adjacent, Related.
The pipeline creates a label page only at the second raw source.
`NEXT_TOPICS` stay on Adjacent; they do not enter the backlog by themselves.
A missing wiki link is a gap *candidate* until Scholar says the pair is underexplored.

See `SCHEMA.md` (Research-gap pipeline v2) and `src/daily_pipeline.py`.
