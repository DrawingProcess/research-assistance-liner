# Research Assistance Liner

A data-free, evidence-first template for collecting research papers with Liner, preserving source records, and curating a local Markdown wiki. It ships with synthetic examples only—no research corpus, credentials, runtime state, or personal editor configuration.

## What this template does

- Uses the Liner API client to search scholarly literature and request structured extraction.
- Keeps captured evidence under `raw/`; after capture, a raw body is immutable and has a SHA-256 checksum.
- Curates supported knowledge into canonical pages under `entities/`, `concepts/`, `comparisons/`, and `queries/`.
- Flags possible missing connections as research-gap candidates. A candidate is not verified knowledge: a human must inspect the cited evidence before promotion or publication.

Read [SCHEMA.md](SCHEMA.md) before adding evidence or canonical pages. See [docs/architecture.md](docs/architecture.md) and [docs/workflow.md](docs/workflow.md) for the operating model.

## Quick start

Requirements: Git and Python 3.11 or newer.

```bash
git clone git@github.com:DrawingProcess/research-assistance-liner.git
cd research-assistance-liner
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
cp .env.example .env
python -m pytest
```

If `python3.11` is not the name of your local interpreter, use the command that selects Python 3.11+ (for example, `python3`). On Windows PowerShell, activate with `.venv\\Scripts\\Activate.ps1` and copy the environment file with `Copy-Item .env.example .env`.

`.env.example` contains the only required service setting:

```dotenv
LINER_API_KEY=<replace-with-your-liner-api-key>
```

Set `LINER_API_KEY` to an API key issued for your Liner account. It is required only for live Liner calls; the test suite and synthetic dry run do not contact Liner. Keep the real value only in your local `.env`. Never commit `.env`, API responses, Discord identifiers, logs, or generated runtime output.

Before a live command in a POSIX shell, load your local environment file:

```bash
set -a
. ./.env
set +a
```

## First topic: synthetic dry run and manual research

Start without a key by inspecting the intentionally fictional records in `examples/` and exercising the project checks:

```bash
python -m pytest
python scripts/validate_public_template.py --repo .
```

For a first live topic, create a local backlog outside version control, then query Liner manually. Replace the topic text with your own.

```bash
python -c 'from pathlib import Path; from src.backlog import add_curiosity_topics, load_backlog, save_backlog; p = Path("research-gap/backlog.json"); b = load_backlog(p); add_curiosity_topics(b, ["your research topic"], "2026-09-09"); save_backlog(p, b)'
python -c 'import json; from src.liner_client import search_scholar, raise_for_status; r = search_scholar("your research topic"); raise_for_status(r, "scholar search"); print(json.dumps(r["response"], ensure_ascii=False, indent=2))'
```

The template intentionally has no enabled scheduler, webhook, Discord delivery, or all-in-one command-line pipeline. Review the returned papers yourself, then use the library functions and copyable [templates](templates/) to capture only selected records. Compute the raw record's checksum from its exact post-frontmatter body, preserve that raw body, and update `index.md` plus append `log.md` whenever you create or update canonical knowledge.

Do not treat a Liner result, extraction, taxonomy, or gap result as a conclusion. Verify bibliographic details and source support, compare relevant raw records, and only then create or revise a canonical page. In particular, an automated gap is a candidate, not verified knowledge.

## Data layout

| Location | Purpose | Git policy |
| --- | --- | --- |
| `inbox/` | Temporary intake awaiting capture | Local content ignored |
| `raw/` | Immutable source evidence | Local content ignored; placeholders tracked |
| `entities/`, `concepts/`, `comparisons/`, `queries/` | Curated canonical wiki | Local content ignored; placeholders tracked |
| `research-gap/` | Local backlog and watcher state | Ignored |
| `examples/` | Fictional format examples | Tracked |
| `templates/` | Copy-before-use Markdown templates | Tracked |

The clean-clone state deliberately has zero canonical pages. A real canonical page needs valid frontmatter, resolving raw sources, claim-level markers where needed, `index.md`/`log.md` synchronization, and at least two distinct links to other active canonical pages. See [SCHEMA.md](SCHEMA.md) for the complete contract.

## Security and publication checks

The repository ignores credentials, evidence, canonical data, runtime state, output, reports, logs, and personal editor state. Check this before sharing changes:

```bash
git status --ignored --short
python scripts/validate_public_template.py --repo .
```

The validator is a guardrail, not a replacement for review. Inspect `git diff --cached` before every commit and remove private information before it enters Git.

## Contributing locally

Run the full suite after changes:

```bash
python -m pytest
```

This template defaults to local, manual execution. Add automation or outbound integrations only after deciding how credentials, evidence retention, review, and access controls will be handled.
