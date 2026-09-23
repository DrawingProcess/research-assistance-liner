"""v2 research-gap pipeline entrypoint.

Run from the repository root after loading `.env`:

    python src/daily_pipeline.py

Topic collection runs every day (up to 3 pending topics). Gap validation
(comparisons/) runs Thursday and Sunday. Coverage scout runs Monday.
Paths (raw/, entities/, concepts/, comparisons/, index.md, log.md) are
relative to the current working directory.

Optional Discord: set DISCORD_CHANNEL_ID. If unset, extra notices are skipped.
Do not put a real channel id in this file.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src import backlog as backlog_mod
from src import canonical_pages
from src.backlog import slugify
from src import coverage_scout
from src import extraction
from src import hub
from src import liner_client
from src import paper_filter
from src import paper_identity
from src import raw_paper
from src import report
from src import synthesis
from src import taxonomy as taxonomy_mod
from src import wiki_gap_detector

ROOT = Path("research-gap")
BACKLOG_PATH = ROOT / "backlog.json"
COMPARISONS_DIR = Path("comparisons")
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "").strip()

COST_PER_SEARCH_AGENT = 0.02
COST_PER_DEEP_RESEARCH = 0.20
COST_PER_SCHOLAR_SEARCH = 0.001

FIELD_TO_PAGE_TYPE = {
    "method": "entity", "dataset": "entity",
    "problem": "concept", "task": "concept",
}

# SCHEMA.md: pipeline pages wait for >=2 raw sources. Hub pages are the
# exception (created empty, then backfilled). MAX_NEW_PAGES_PER_TOPIC still
# bounds label-page fan-out after the 2-source rule.
MAX_NEW_PAGES_PER_TOPIC = 15

# Topic collection (search/extract/capture papers, create canonical pages)
# runs every day; gap detection scans the whole accumulated corpus and is
# comparatively expensive to reason about (O(n^2) candidate pairs before the
# MAX_NEW_COMPARISONS_PER_RUN cap), so it only runs twice a week — matches
# date.weekday(): Mon=0 .. Sun=6, so Thursday=3, Sunday=6.
GAP_DETECTION_WEEKDAYS = {3, 6}


def _run_id(now: datetime) -> str:
    return now.strftime("%Y%m%d_%H%M%S")


def _paper_summary(structured: dict) -> str:
    """One-line Korean summary — extraction.py's extraction prompt asks for
    this directly (field "summary_ko") in the same Search Agent call used
    for method/problem/etc., so this never triggers a fresh LLM call: it
    just reads what was already written during structured extraction."""
    return structured.get("summary_ko") or "(요약 없음)"


def _send_discord_message(text: str) -> None:
    if not DISCORD_CHANNEL_ID:
        return
    subprocess.run(
        ["hermes", "send", "--to", f"discord:{DISCORD_CHANNEL_ID}", "--quiet", text],
        check=False,
    )


def process_topic(topic_entry: dict, run_dir: Path, today: date) -> dict:
    topic = topic_entry["topic"]
    hub_slug = topic_entry["id"]

    scholar_raw = liner_client.search_scholar(topic, max_results=20)
    (run_dir / f"{hub_slug}_scholar_search.json").write_text(
        json.dumps(scholar_raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    liner_client.raise_for_status(scholar_raw, f"search_scholar for topic {topic!r}")
    raw_papers = scholar_raw["response"].get("results", [])
    filtered = paper_filter.filter_papers(raw_papers, today)

    hub.ensure_hub(topic, today)

    captured = 0
    already_known = 0
    extracted = 0
    failed_extractions = 0
    failed_extraction_errors: list[str] = []
    new_page_count = 0
    pages_touched: set[tuple[str, str]] = set()
    papers_found: list[dict] = []
    pending_sources: dict[tuple[str, str], list[str]] = {}
    challenges: list[str] = []
    themes: dict[str, list[str]] = {}

    for paper in filtered["kept"]:
        try:
            existing_path = paper_identity.lookup_path(
                paper["url"], paper.get("title") or "", Path("raw/paper")
            )
            if existing_path is not None:
                already_known += 1
                source_path = str(existing_path)
                papers_found.append({
                    "title": paper["title"], "url": paper["url"],
                    "summary": "(이미 수집된 논문)", "path": source_path,
                    "problem": [], "method": [],
                })
                continue

            extracted += 1
            structured = extraction.extract_paper(paper)
            if structured is None:
                continue

            path, is_new = raw_paper.write_paper(paper, structured, topic, today)
            captured += int(is_new)
            already_known += int(not is_new)
            source_path = str(path)
            papers_found.append({
                "title": paper["title"], "url": paper["url"],
                "summary": _paper_summary(structured), "path": source_path,
                "problem": structured.get("problem") or [], "method": structured.get("method") or [],
            })

            paper_labels: list[tuple[str, str]] = []
            for field, page_type in FIELD_TO_PAGE_TYPE.items():
                for label in structured.get(field) or []:
                    paper_labels.append((page_type, label))
                    bucket = pending_sources.setdefault((page_type, label), [])
                    if source_path not in bucket:
                        bucket.append(source_path)
                    themes.setdefault(label, []).append(source_path)

            writable = []
            projected = new_page_count
            for page_type, label in paper_labels:
                exists = canonical_pages.read_page(page_type, label) is not None
                combined = pending_sources[(page_type, label)]
                would_create = (not exists) and len(combined) >= canonical_pages.MIN_SOURCES_TO_CREATE
                if not exists and not would_create:
                    continue
                if would_create and projected >= MAX_NEW_PAGES_PER_TOPIC:
                    continue
                projected += int(would_create)
                writable.append((page_type, label, would_create))

            paper_slugs = {slugify(label) for _, label, _ in writable}

            for page_type, label, is_new_page in writable:
                sibling_slugs = sorted(paper_slugs - {slugify(label)})
                action = canonical_pages.stage_or_write_page(
                    page_type, label, today, source_path,
                    wikilinks=[hub_slug] + sibling_slugs,
                    summary=f"{label} (from {topic} research).",
                    pending_sources=pending_sources[(page_type, label)],
                )
                if action == "create":
                    new_page_count += 1
                if action != "staged":
                    pages_touched.add((page_type, label))

            for limitation in structured.get("limitations") or []:
                challenges.append(limitation)
                target_problem = next(iter(structured.get("problem") or []), None)
                if target_problem is None:
                    continue
                exists = canonical_pages.read_page("concept", target_problem) is not None
                combined = pending_sources.get(("concept", target_problem), [source_path])
                would_create = (not exists) and len(combined) >= canonical_pages.MIN_SOURCES_TO_CREATE
                if not exists and not would_create:
                    continue
                if would_create and new_page_count >= MAX_NEW_PAGES_PER_TOPIC:
                    continue
                action = canonical_pages.stage_or_write_page(
                    "concept", target_problem, today, source_path,
                    wikilinks=[hub_slug], summary=f"{target_problem} (from {topic} research).",
                    pending_sources=combined,
                    body_section=("Open challenges", limitation),
                )
                if action == "create":
                    new_page_count += 1
                if action != "staged":
                    pages_touched.add(("concept", target_problem))
        except liner_client.AccountLevelAPIError:
            raise
        except Exception as exc:
            failed_extractions += 1
            failed_extraction_errors.append(str(exc))
            continue

    definition = ""
    try:
        synthesis_result = synthesis.run_topic_synthesis(topic, deep_research=False)
        (run_dir / f"{hub_slug}_synthesis.json").write_text(
            json.dumps(synthesis_result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        next_topics = synthesis_result["deep_research"]["next_topics"]
        definition = (synthesis_result.get("search_agent_scholar") or {}).get("text") or ""
        synthesis_error = None
    except Exception as exc:
        next_topics = []
        synthesis_error = str(exc)

    taxonomy_slug = None
    if extracted > 0 and len(papers_found) >= taxonomy_mod.MIN_PAPERS_FOR_TAXONOMY:
        try:
            taxonomy_result = taxonomy_mod.generate_taxonomy(topic, papers_found)
            if taxonomy_result:
                sources_by_title = {p["title"]: p["path"] for p in papers_found}
                related_slugs = [hub_slug] + sorted({slugify(label) for _, label in pages_touched})[
                    :taxonomy_mod.MAX_RELATED_LINKS - 1
                ]
                written_path = taxonomy_mod.write_taxonomy_page(
                    topic, taxonomy_result, sources_by_title, related_slugs, today
                )
                if written_path is not None:
                    taxonomy_slug = slugify(f"{topic}: paper taxonomy")
                    _send_discord_message(report.format_taxonomy_message(topic, taxonomy_result))
        except Exception:
            pass

    try:
        hub.update_hub(
            topic, today,
            sources=[p["path"] for p in papers_found],
            definition=definition[:800],
            challenges=challenges,
            papers=papers_found,
            themes=themes,
            adjacent=next_topics,
            related=[taxonomy_slug] if taxonomy_slug else [],
        )
    except Exception:
        pass

    return {
        "topic": topic, "fetched": len(raw_papers), "kept": len(filtered["kept"]),
        "dropped_year": filtered["dropped_year"], "captured": captured,
        "already_known": already_known, "extracted": extracted,
        "failed_extractions": failed_extractions,
        "failed_extraction_errors": failed_extraction_errors,
        "pages_touched": sorted(pages_touched),
        "next_topics": next_topics, "synthesis_error": synthesis_error,
        "papers": papers_found, "taxonomy_slug": taxonomy_slug,
    }


def _run_pipeline(now: datetime, today: date) -> None:
    run_dir = ROOT / "runs" / _run_id(now)
    run_dir.mkdir(parents=True, exist_ok=True)

    backlog = backlog_mod.load_backlog(BACKLOG_PATH)
    pending = backlog_mod.pop_pending_topics(backlog, n=3)

    topic_results = []
    new_backlog_topics: list[str] = []
    for entry in pending:
        try:
            result = process_topic(entry, run_dir, today)
        except liner_client.AccountLevelAPIError as exc:
            # No credits / invalid key / rate-limited — every remaining
            # pending topic in this run would fail identically, so stop
            # here rather than burning through each one on calls guaranteed
            # to fail. This topic (and every other still-pending one) stays
            # "pending" — mark_done is never reached for any of them — so
            # the next scheduled run retries once the underlying issue is
            # resolved, instead of the topic being silently discarded.
            topic_results.append({
                "topic": entry["topic"], "fetched": 0, "kept": 0, "dropped_year": 0,
                "captured": 0, "already_known": 0, "failed_extractions": 0,
                "failed_extraction_errors": [], "pages_touched": [], "next_topics": [],
                "synthesis_error": None, "taxonomy_slug": None,
                "error": f"API 계정 문제로 이번 실행 중단(예: 잔액/인증/rate limit) — {exc}. "
                         f"이 topic과 남은 pending topic은 그대로 pending 상태로 남아 다음 실행에서 재시도됩니다.",
            })
            break
        except Exception as exc:
            topic_results.append({
                "topic": entry["topic"], "fetched": 0, "kept": 0, "dropped_year": 0,
                "captured": 0, "already_known": 0, "failed_extractions": 0,
                "failed_extraction_errors": [], "pages_touched": [], "next_topics": [],
                "synthesis_error": None, "taxonomy_slug": None, "error": str(exc),
            })
            continue
        topic_results.append(result)
        backlog_mod.mark_done(backlog, entry["id"])
        # Adjacent topics stay on the hub; they are not auto-enqueued.
        if result.get("papers"):
            _send_discord_message(report.format_paper_list(result["topic"], result["papers"]))
        backlog_mod.save_backlog(BACKLOG_PATH, backlog)

    # Redundant with the per-iteration save above in the common case, but
    # harmless (saving an unchanged backlog is a no-op write) and it keeps
    # the "backlog is always durable before gap detection runs" guarantee
    # true even if every topic took the exception path above.
    backlog_mod.save_backlog(BACKLOG_PATH, backlog)

    hub_slugs = {t["id"] for t in backlog["topics"]}
    new_gap_pages: list[str] = []
    if today.weekday() in GAP_DETECTION_WEEKDAYS:
        try:
            new_gap_pages = wiki_gap_detector.run_and_create_comparisons(today, hub_slugs)
        except Exception as exc:
            # A gap-detection failure (e.g. a malformed pre-existing wiki page)
            # must surface in the report, not crash the run and hide the
            # already-completed topics' results (Finding 1 + Finding 2).
            topic_results.append({
                # "synthetic" marks this as not a real topic result, so
                # report.format_run_report can exclude it from the "오늘 조사한
                # topic (N개)" count (it's not one of the day's topics).
                "topic": "(gap detection)", "synthetic": True, "fetched": 0, "kept": 0, "dropped_year": 0,
                "captured": 0, "already_known": 0, "failed_extractions": 0,
                "failed_extraction_errors": [], "pages_touched": [], "next_topics": [],
                "synthesis_error": None, "taxonomy_slug": None, "error": f"gap detection failed: {exc}",
            })

        if new_gap_pages:
            try:
                gap_details = []
                for slug in new_gap_pages:
                    path = COMPARISONS_DIR / f"{slug}.md"
                    if not path.exists():
                        continue
                    fm, _ = canonical_pages.parse_frontmatter(path.read_text(encoding="utf-8"))
                    gap_details.append({"title": fm.get("title", slug), "sources": fm.get("sources", [])})
                if gap_details:
                    _send_discord_message(report.format_gap_candidates_message(gap_details))
            except Exception:
                pass

        human_path = ROOT / "gap_needs_human.json"
        if human_path.exists():
            try:
                queued = json.loads(human_path.read_text(encoding="utf-8"))
                if queued.get("candidates"):
                    _send_discord_message(
                        "Gap needs human (" + str(len(queued["candidates"])) + "): "
                        + ", ".join(
                            f"{c['page_a']} vs {c['page_b']}" for c in queued["candidates"][:8]
                        )
                    )
            except Exception:
                pass

    if today.weekday() in coverage_scout.SCOUT_WEEKDAYS:
        try:
            coverage_scout.scout_and_notify(today, _send_discord_message, backlog)
        except Exception as exc:
            topic_results.append({
                "topic": "(coverage scout)", "synthetic": True, "fetched": 0, "kept": 0,
                "dropped_year": 0, "captured": 0, "already_known": 0, "extracted": 0,
                "failed_extractions": 0, "failed_extraction_errors": [],
                "pages_touched": [], "next_topics": [], "synthesis_error": None,
                "taxonomy_slug": None, "error": f"coverage scout failed: {exc}",
            })

    cost_estimate = sum(
        COST_PER_SCHOLAR_SEARCH
        + r.get("extracted", 0) * COST_PER_SEARCH_AGENT
        + COST_PER_SEARCH_AGENT
        + (COST_PER_SEARCH_AGENT if r.get("taxonomy_slug") or (
            r.get("extracted", 0) > 0 and r["kept"] >= taxonomy_mod.MIN_PAPERS_FOR_TAXONOMY
        ) else 0)
        for r in topic_results if not r.get("error")
    )

    print(report.format_run_report(
        today.isoformat(), topic_results, new_gap_pages, cost_estimate, new_backlog_topics
    ))


def main() -> None:
    now = datetime.now(timezone.utc).astimezone()
    today = now.date()
    try:
        _run_pipeline(now, today)
    except Exception as exc:
        print(
            f"[Liner Research Gap Discovery] {today.isoformat()}\n\n"
            f"파이프라인 실행 중 예상치 못한 오류로 중단되었습니다: {exc}"
        )


if __name__ == "__main__":
    main()
