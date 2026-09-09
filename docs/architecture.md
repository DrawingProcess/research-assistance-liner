# Architecture

This template is a local Markdown knowledge system with Python helpers. It has no database, hosted service, enabled scheduler, or bundled corpus.

```text
Liner API (optional, local key)
        |
        v
  search and extraction helpers
        |
        v
 raw/ immutable source evidence
        |
        v
 canonical wiki: entities/ concepts/ comparisons/ queries/
        |
        +--> index.md (active catalog) and log.md (append-only history)
        |
        +--> research-gap candidate detection --> human evidence review
```

`src/liner_client.py` reads `LINER_API_KEY` only from the process environment. `src/raw_paper.py` writes a raw paper record with a checksum. `src/canonical_pages.py`, `src/wiki_index.py`, and `src/wiki_gap_detector.py` maintain canonical pages, navigation, history, and possible missing-connection candidates.

The schema is the boundary between the layers. Raw captures are evidence, not conclusions; their bodies are immutable after capture. Canonical pages contain interpretation, must cite resolving raw paths, and must stay synchronized with `index.md` and `log.md`. The repository starts with zero canonical pages by design.

Only `.gitkeep` placeholders in evidence, canonical, inbox, and research-gap directories are tracked. Your local corpus and state remain excluded by `.gitignore`; synthetic records in `examples/` are format demonstrations, never evidence.
