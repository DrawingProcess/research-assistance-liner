# Architecture

This template is a local Markdown knowledge system with Python helpers. It has no database, hosted service, enabled scheduler, or bundled corpus.

```text
Liner API (optional, local key)
        |
        v
  v2 helpers: scholar search, extract-after-dedup, hub compile,
              coverage scout, Scholar gap validation
        |
        v
 raw/ immutable source evidence
        |
        v
 canonical wiki: topic hubs in concepts/, plus entities/ comparisons/ queries/
        |
        +--> index.md (active catalog) and log.md (append-only history)
        |
        +--> research-gap candidate detection + Scholar check --> human review
```

`src/liner_client.py` reads `LINER_API_KEY` only from the process environment. `src/daily_pipeline.py` is an optional batch runner (no scheduler in this template). `src/raw_paper.py` writes a raw paper record with a checksum. `src/hub.py` and `src/canonical_pages.py` compile hubs and two-source pages. `src/wiki_gap_detector.py` plus `src/gap_validator.py` maintain missing-connection candidates after a Scholar check.

The schema is the boundary between the layers. Raw captures are evidence, not conclusions; their bodies are immutable after capture. Canonical pages contain interpretation, must cite resolving raw paths, and must stay synchronized with `index.md` and `log.md`. The repository starts with zero canonical pages by design.

Only `.gitkeep` placeholders in evidence, canonical, inbox, and research-gap directories are tracked. Your local corpus and state remain excluded by `.gitignore`; synthetic records in `examples/` are format demonstrations, never evidence.
