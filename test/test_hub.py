from datetime import date

from src.canonical_pages import parse_frontmatter
from src.hub import ensure_hub, update_hub

_INDEX = "# Wiki Index\n\n> Total pages: 0\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n"


def test_update_hub_writes_sections_and_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "index.md").write_text(_INDEX, encoding="utf-8")
    (tmp_path / "log.md").write_text("# Wiki Log\n\n", encoding="utf-8")
    ensure_hub("self evolving agent", date(2026, 9, 23))
    update_hub(
        "self evolving agent", date(2026, 9, 23),
        sources=["raw/paper/a.md", "raw/paper/b.md"],
        definition="Agents that keep changing after deployment.",
        challenges=["feedback reliability"],
        papers=[{"title": "Paper A", "path": "raw/paper/a.md", "url": "https://arxiv.org/abs/1"}],
        themes={"Static coding agents": ["raw/paper/a.md", "raw/paper/b.md"]},
        adjacent=["safety evaluation"],
        related=["self-evolving-agent-paper-taxonomy"],
    )
    text = (tmp_path / "concepts" / "self-evolving-agent.md").read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    assert fm["sources"] == ["raw/paper/a.md", "raw/paper/b.md"]
    assert fm["confidence"] == "high"
    assert "## Definition" in body
    assert "Agents that keep changing" in body
    assert "## Papers" in body
    assert "raw/paper/a.md" in body
    assert "Static coding agents (2)" in body
    assert "safety evaluation" in body
    assert "[[self-evolving-agent-paper-taxonomy]]" in body
