from unittest.mock import patch

import pytest

from src.synthesis import build_deep_research_prompt, parse_next_topics, run_topic_synthesis


def test_build_deep_research_prompt_includes_topic_and_next_topics_instruction():
    prompt = build_deep_research_prompt("world model")
    assert "world model" in prompt
    assert "NEXT_TOPICS:" in prompt


def test_parse_next_topics_extracts_json_array():
    text = 'Some report text.\nNEXT_TOPICS: ["embodied AI", "video prediction", "action-conditioned models"]'
    assert parse_next_topics(text) == ["embodied AI", "video prediction", "action-conditioned models"]


def test_parse_next_topics_returns_empty_list_when_missing():
    assert parse_next_topics("Some report with no marker.") == []


def test_parse_next_topics_returns_empty_list_when_malformed():
    text = "NEXT_TOPICS: [not valid json"
    assert parse_next_topics(text) == []


def test_run_topic_synthesis_combines_both_calls():
    with patch("src.synthesis.liner_client.search_agent") as mock_search_agent, \
         patch("src.synthesis.liner_client.deep_research") as mock_deep_research:
        mock_search_agent.return_value = {"status_code": 200, "summary": {"text": "scholar synthesis text", "references": [{"url": "x"}]}}
        mock_deep_research.return_value = {"status_code": 200, "summary": {"text": 'report body\nNEXT_TOPICS: ["topic a"]', "references": [{"url": "y"}]}}

        result = run_topic_synthesis("world model")

    mock_search_agent.assert_called_once_with("world model", mode="scholar")
    assert result["search_agent_scholar"]["text"] == "scholar synthesis text"
    assert result["deep_research"]["next_topics"] == ["topic a"]
    assert result["deep_research"]["references"] == [{"url": "y"}]


def test_run_topic_synthesis_raises_on_non_2xx_search_agent():
    with patch("src.synthesis.liner_client.search_agent") as mock_search_agent:
        mock_search_agent.return_value = {"status_code": 401, "summary": {"text": "", "references": []}}
        with pytest.raises(RuntimeError):
            run_topic_synthesis("world model")


def test_run_topic_synthesis_raises_on_non_2xx_deep_research():
    with patch("src.synthesis.liner_client.search_agent") as mock_search_agent, \
         patch("src.synthesis.liner_client.deep_research") as mock_deep_research:
        mock_search_agent.return_value = {"status_code": 200, "summary": {"text": "ok", "references": []}}
        mock_deep_research.return_value = {"status_code": 500, "summary": {"text": "", "references": []}}
        with pytest.raises(RuntimeError):
            run_topic_synthesis("world model")
