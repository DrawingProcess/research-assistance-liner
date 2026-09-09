import json
from unittest.mock import patch

import pytest

from src.extraction import build_extraction_prompt, extract_paper, parse_extraction_response, _split_items

VALID_JSON = json.dumps({
    "problem": "open-vocabulary understanding",
    "method": "semantic gaussian representation | diffusion prior",
    "dataset": "ScanNet",
    "task": "scene segmentation",
    "evaluation": "mIoU",
    "limitations": "weak relational reasoning",
    "future_work": "explicit scene graphs",
    "summary_ko": "개방형 어휘 3D 장면 이해를 위해 시맨틱 가우시안 표현과 디퓨전 프라이어를 결합한 방법을 제안한다.",
})


def test_build_extraction_prompt_includes_title_and_abstract():
    prompt = build_extraction_prompt("Semantic Gaussians", "We propose a method.")
    assert "Semantic Gaussians" in prompt
    assert "We propose a method." in prompt


def test_parse_extraction_response_handles_clean_json():
    result = parse_extraction_response(VALID_JSON)
    assert result["method"] == ["semantic gaussian representation", "diffusion prior"]
    assert result["limitations"] == ["weak relational reasoning"]
    assert result["summary_ko"] == "개방형 어휘 3D 장면 이해를 위해 시맨틱 가우시안 표현과 디퓨전 프라이어를 결합한 방법을 제안한다."
    assert "venue" not in result


def test_parse_extraction_response_summary_ko_defaults_to_empty_string_when_missing():
    without_summary = json.dumps({k: v for k, v in json.loads(VALID_JSON).items() if k != "summary_ko"})
    assert parse_extraction_response(without_summary)["summary_ko"] == ""


def test_parse_extraction_response_summary_ko_ignores_non_string_value():
    bad_type = json.dumps({**json.loads(VALID_JSON), "summary_ko": ["not", "a", "string"]})
    assert parse_extraction_response(bad_type)["summary_ko"] == ""


def test_parse_extraction_response_truncates_overlong_summary_ko():
    long_summary = "가" * 300
    raw = json.dumps({**json.loads(VALID_JSON), "summary_ko": long_summary})
    result = parse_extraction_response(raw)
    assert len(result["summary_ko"]) <= 153  # MAX_SUMMARY_LENGTH + "..."
    assert result["summary_ko"].endswith("...")


def test_parse_extraction_response_handles_json_wrapped_in_prose():
    wrapped = f"Sure, here is the JSON:\n{VALID_JSON}\nLet me know if you need more."
    assert parse_extraction_response(wrapped)["problem"] == ["open-vocabulary understanding"]


def test_parse_extraction_response_returns_none_for_malformed_json():
    assert parse_extraction_response("not json at all") is None


def test_parse_extraction_response_returns_none_for_the_real_malformed_pattern_search_agent_produced():
    malformed = '{"problem":,"method":,"dataset":,"task":,"evaluation":,"limitations":,"future_work":}'
    assert parse_extraction_response(malformed) is None


def test_parse_extraction_response_returns_none_when_missing_required_field():
    assert parse_extraction_response(json.dumps({"problem": "x"})) is None


def test_parse_extraction_response_returns_none_when_field_is_not_a_string():
    list_valued = json.dumps({**json.loads(VALID_JSON), "method": ["NeRF"]})
    assert parse_extraction_response(list_valued) is None


def test_extract_paper_raises_account_level_error_on_account_status(monkeypatch):
    """429/402/401 mean every remaining paper's extraction call would also
    fail — daily_pipeline relies on this specific exception type to stop
    the topic (and the run) instead of treating it as one paper's problem."""
    from src import liner_client
    paper = {"title": "Semantic Gaussians", "description": "We propose a method."}
    with patch("src.extraction.liner_client.search_agent") as mock_agent:
        mock_agent.return_value = {"status_code": 429, "summary": {"text": "", "references": []}}
        with pytest.raises(liner_client.AccountLevelAPIError):
            extract_paper(paper)


def test_extract_paper_raises_plain_runtime_error_on_other_failures():
    paper = {"title": "Semantic Gaussians", "description": "We propose a method."}
    with patch("src.extraction.liner_client.search_agent") as mock_agent:
        mock_agent.return_value = {"status_code": 500, "summary": {"text": "", "references": []}}
        try:
            extract_paper(paper)
            assert False, "expected RuntimeError"
        except Exception as exc:
            from src import liner_client
            assert type(exc) is RuntimeError
            assert not isinstance(exc, liner_client.AccountLevelAPIError)


def test_split_items_drops_items_over_the_length_limit():
    sentence = "a " * 60  # well over MAX_ITEM_LENGTH
    assert _split_items(f"ScanNet | {sentence}") == ["ScanNet"]


def test_split_items_drops_non_answer_placeholders():
    for placeholder in ["Not specified in abstract", "N/A", "none mentioned", "Unknown", "not applicable"]:
        assert _split_items(f"ScanNet | {placeholder}") == ["ScanNet"]


def test_split_items_keeps_short_real_labels():
    assert _split_items("ScanNet | requires ground-truth camera poses") == [
        "ScanNet", "requires ground-truth camera poses",
    ]


def test_parse_extraction_response_filters_sentence_paraphrase_and_non_answer():
    raw = json.dumps({
        **json.loads(VALID_JSON),
        "method": "OpenGS-SLAM: a 3D Gaussian splatting based dense semantic SLAM that attaches "
                   "explicit semantic labels from 2D foundation models to Gaussians and uses "
                   "Gaussian Voting Splatting for fast 2D label map rendering",
        "dataset": "Not specified in abstract",
    })
    result = parse_extraction_response(raw)
    assert result["method"] == []
    assert result["dataset"] == []


def test_extract_paper_calls_search_agent_and_parses_result():
    paper = {"title": "Semantic Gaussians", "description": "We propose a method."}
    with patch("src.extraction.liner_client.search_agent") as mock_agent:
        mock_agent.return_value = {"status_code": 200, "summary": {"text": VALID_JSON, "references": []}}
        result = extract_paper(paper)
    mock_agent.assert_called_once()
    assert mock_agent.call_args.kwargs["mode"] == "general"
    assert result["method"] == ["semantic gaussian representation", "diffusion prior"]
