import json
from datetime import date
from unittest.mock import patch

from src.coverage_scout import covered_topics, format_scout_message, scout_coverage


def test_covered_topics_lists_done_only():
    backlog = {"topics": [
        {"topic": "world model", "status": "done"},
        {"topic": "pending one", "status": "pending"},
    ]}
    assert covered_topics(backlog) == ["world model"]


def test_scout_coverage_writes_candidates_without_enqueueing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backlog = {"topics": [{"topic": "world model", "status": "done"}]}
    dr = {"status_code": 200, "summary": {"text": 'report\nNEXT_TOPICS: ["robotics evaluation"]', "references": []}}
    web = {"status_code": 200, "response": {"results": [{"title": "Workshop"}]}}
    qa = {"status_code": 200, "summary": {"text": "Yes, it is a distinct evaluation area.", "references": []}}

    with patch("src.coverage_scout.liner_client.deep_research", return_value=dr), \
         patch("src.coverage_scout.liner_client.search_web", return_value=web), \
         patch("src.coverage_scout.liner_client.quick_answer", return_value=qa):
        payload = scout_coverage(backlog, date(2026, 9, 21))

    assert payload["candidates"][0]["topic"] == "robotics evaluation"
    assert payload["candidates"][0]["source"] == "coverage-gap"
    saved = json.loads((tmp_path / "research-gap" / "coverage_candidates.json").read_text(encoding="utf-8"))
    assert saved["candidates"][0]["topic"] == "robotics evaluation"
    assert "고르면" in format_scout_message(payload)


def test_scout_coverage_skips_liner_when_nothing_is_covered(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("src.coverage_scout.liner_client.deep_research") as mock_dr:
        payload = scout_coverage({"topics": []}, date(2026, 9, 21))
    mock_dr.assert_not_called()
    assert payload["candidates"] == []
