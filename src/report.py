"""Discord report formatting for the daily research-gap run (gap detection/
comparisons only run twice a week — see daily_pipeline.GAP_DETECTION_WEEKDAYS)."""
from __future__ import annotations

MAX_REPORT_CHARS = 1900
TRUNCATION_NOTICE = "\n...(내용이 길어 생략됨 — index.md/log.md 참고)"


def format_run_report(
    run_date: str, topic_results: list[dict], new_gap_pages: list[str], cost_estimate: float,
    new_backlog_topics: list[str] | None = None,
) -> str:
    lines = [f"[Liner Research Gap Discovery] {run_date}", ""]

    if not topic_results:
        lines.append("오늘은 처리할 pending topic이 backlog에 없습니다. 시드 topic을 추가해주세요.")
        return "\n".join(lines)

    # Exclude synthetic entries (e.g. a gap-detection failure reported
    # alongside real topic results) from the day's topic count — they
    # aren't one of the day's topics, just a surfaced pipeline-stage error.
    real_topic_count = sum(1 for r in topic_results if not r.get("synthetic"))
    lines.append(f"오늘 조사한 topic ({real_topic_count}개):")
    for r in topic_results:
        if r.get("error"):
            lines.append(f"- {r['topic']} — 실패: {r['error']}")
            continue
        failed_note = f", 추출 실패 {r['failed_extractions']}편" if r.get("failed_extractions") else ""
        if r.get("failed_extraction_errors"):
            failed_note += f" (예: {r['failed_extraction_errors'][0]})"
        # A synthesis failure is a partial failure, not a topic failure: the
        # papers were still captured and billed, so the topic keeps its
        # normal line and just gains a note (Final review, Finding I1).
        synthesis_note = (
            f" — synthesis 실패(파생 topic 없음): {r['synthesis_error']}"
            if r.get("synthesis_error") else ""
        )
        taxonomy_note = f" — 분류 문서: [[{r['taxonomy_slug']}]]" if r.get("taxonomy_slug") else ""
        lines.append(
            f"- {r['topic']} — {r['fetched']}편 수집 → 필터 후 {r['kept']}편 "
            f"(연도 탈락 {r['dropped_year']}, 신규 raw/paper {r['captured']}편, "
            f"기존 {r['already_known']}편{failed_note}, "
            f"canonical 페이지 갱신 {len(r.get('pages_touched', []))}개)"
            f"{synthesis_note}{taxonomy_note}"
        )
    lines.append("")

    if new_gap_pages:
        lines.append("신규 Gap 후보 (comparisons/):")
        lines += [f"- [[{slug}]]" for slug in new_gap_pages]
        lines.append("")

    if new_backlog_topics:
        lines.append(f"새로 백로그에 추가된 파생 topic: {', '.join(new_backlog_topics)}")
        lines.append("")

    lines.append(f"API 비용(추정): ${cost_estimate:.2f}")

    text = "\n".join(lines)
    if len(text) > MAX_REPORT_CHARS:
        text = text[: MAX_REPORT_CHARS - len(TRUNCATION_NOTICE)] + TRUNCATION_NOTICE
    return text


def format_paper_list(topic: str, papers: list[dict]) -> str:
    """One extra Discord message per topic: every paper's title, one-line
    summary, and URL — sent separately from format_run_report's single
    aggregate message (see daily_pipeline._send_discord_message)."""
    lines = [f"[{topic}] 수집된 논문 ({len(papers)}편)", ""]
    for p in papers:
        lines.append(f"- {p['title']}: {p['summary']} ({p['url']})")

    text = "\n".join(lines)
    if len(text) > MAX_REPORT_CHARS:
        text = text[: MAX_REPORT_CHARS - len(TRUNCATION_NOTICE)] + TRUNCATION_NOTICE
    return text


def format_taxonomy_message(topic: str, taxonomy: dict) -> str:
    """One extra Discord message per topic (only when a taxonomy was
    actually generated — see taxonomy.MIN_PAPERS_FOR_TAXONOMY): the full
    classification, not just the [[link]] format_run_report already
    includes, sent the same way as format_paper_list."""
    lines = [f"[{topic}] 논문 분류 (taxonomy)", "", taxonomy["axis"], ""]
    for c in taxonomy["clusters"]:
        lines.append(f"**{c['name']}**")
        if c["description"]:
            lines.append(c["description"])
        lines += [f"- {p}" for p in c["papers"]]
        lines.append("")
    if taxonomy["off_axis"]:
        lines.append("축에서 벗어난 논문:")
        lines += [
            f"- {o['title']} — {o['reason']}" if o["reason"] else f"- {o['title']}"
            for o in taxonomy["off_axis"]
        ]
        lines.append("")
    if taxonomy["insight"]:
        lines += ["인사이트:", taxonomy["insight"]]

    text = "\n".join(lines)
    if len(text) > MAX_REPORT_CHARS:
        text = text[: MAX_REPORT_CHARS - len(TRUNCATION_NOTICE)] + TRUNCATION_NOTICE
    return text


def format_gap_candidates_message(gap_details: list[dict]) -> str:
    """One extra Discord message per run when gap detection actually
    created new comparisons/ pages (Thu/Sun only — see
    daily_pipeline.GAP_DETECTION_WEEKDAYS): each candidate's title and
    supporting sources, not just the [[link]] format_run_report already
    includes."""
    lines = [f"신규 Gap 후보 ({len(gap_details)}개)", ""]
    for g in gap_details:
        lines.append(f"**{g['title']}**")
        lines += [f"- {s}" for s in g["sources"]]
        lines.append("")

    text = "\n".join(lines)
    if len(text) > MAX_REPORT_CHARS:
        text = text[: MAX_REPORT_CHARS - len(TRUNCATION_NOTICE)] + TRUNCATION_NOTICE
    return text
