from datetime import date

from src.backfill_hubs import backfill_hub, parse_raw_paper, papers_for_topic
from src.canonical_pages import parse_frontmatter


def _write_raw(root, name, topic, title, url, method, limitation):
    path = root / "raw" / "paper" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\nurl: "{url}"\nliner_query: "{topic}"\n'
        'tags: ["research"]\n---\n\n# x\n\n## Method\n\n'
        f"- {method}\n\n## Limitations\n\n- {limitation}\n",
        encoding="utf-8",
    )
    return path


def test_parse_raw_paper_reads_liner_query_and_sections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _write_raw(tmp_path, "a.md", "self evolving agent", "Paper A",
                      "https://arxiv.org/abs/1", "survey", "safety")
    parsed = parse_raw_paper(path)
    assert parsed["liner_query"] == "self evolving agent"
    assert parsed["method"] == ["survey"]
    assert parsed["limitations"] == ["safety"]


def test_backfill_hub_fills_papers_and_themes_from_raw(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "index.md").write_text(
        "# Wiki Index\n\n> Total pages: 0\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n",
        encoding="utf-8",
    )
    (tmp_path / "log.md").write_text("# Wiki Log\n\n", encoding="utf-8")
    _write_raw(tmp_path, "a.md", "self evolving agent", "Paper A",
               "https://arxiv.org/abs/1", "survey", "safety")
    _write_raw(tmp_path, "b.md", "self evolving agent", "Paper B",
               "https://arxiv.org/abs/2", "survey", "cost")
    (tmp_path / "raw" / "paper" / "other.md").write_text(
        '---\ntitle: "Other"\nurl: "https://arxiv.org/abs/9"\nliner_query: "other topic"\n'
        'tags: ["research"]\n---\n\n# x\n',
        encoding="utf-8",
    )

    result = backfill_hub("self evolving agent", date(2026, 9, 23))
    assert result["papers"] == 2
    text = (tmp_path / "concepts" / "self-evolving-agent.md").read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    assert len(fm["sources"]) == 2
    assert fm["confidence"] == "high"
    assert "Paper A" in body
    assert "survey (2)" in body
    assert "safety" in body
    assert papers_for_topic("self evolving agent")[0]["title"] == "Paper A"
