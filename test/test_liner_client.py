import json
from unittest.mock import MagicMock, patch

import pytest

from src import liner_client


def test_raise_for_status_is_a_noop_for_2xx():
    liner_client.raise_for_status({"status_code": 200}, "ctx")  # must not raise


@pytest.mark.parametrize("status", [401, 402, 429])
def test_raise_for_status_raises_account_level_error_for_account_codes(status):
    with pytest.raises(liner_client.AccountLevelAPIError) as exc_info:
        liner_client.raise_for_status({"status_code": status}, "search_agent (extraction)")
    assert str(status) in str(exc_info.value)
    assert "search_agent (extraction)" in str(exc_info.value)


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_raise_for_status_raises_plain_runtime_error_for_other_codes(status):
    with pytest.raises(RuntimeError) as exc_info:
        liner_client.raise_for_status({"status_code": status}, "ctx")
    # AccountLevelAPIError is a RuntimeError subclass, so pytest.raises(RuntimeError)
    # alone wouldn't catch a wrong-type regression — assert the exact type too.
    assert type(exc_info.value) is RuntimeError


def test_api_key_read_from_environment(monkeypatch):
    monkeypatch.setenv("LINER_API_KEY", "test" + "-key-123")
    assert liner_client._api_key() == "test-key-123"


def test_search_scholar_posts_expected_payload(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [{"title": "Paper A"}]}
    with patch("src.liner_client.requests.post", return_value=mock_resp) as mock_post:
        monkeypatch.setattr(liner_client, "_api_key", lambda: "k")
        result = liner_client.search_scholar("3D Gaussian Splatting", max_results=5)

    assert result == {"status_code": mock_resp.status_code, "response": {"results": [{"title": "Paper A"}]}}
    called_url = mock_post.call_args.args[0]
    called_json = mock_post.call_args.kwargs["json"]
    assert called_url == "https://platform.liner.com/api/v1/tools/search/scholar"
    assert called_json == {"query": "3D Gaussian Splatting", "max_results": 5}


def test_search_agent_parses_sse_text_and_references(monkeypatch):
    sse_lines = [
        'data: {"type":"text-delta","delta":"Hello "}',
        'data: {"type":"text-delta","delta":"world"}',
        'data: {"type":"data-search-references","data":{"references":[{"url":"https://x"}]}}',
        "data: [DONE]",
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = iter(sse_lines)
    mock_resp.__enter__ = lambda self: mock_resp
    mock_resp.__exit__ = lambda self, *a: None
    with patch("src.liner_client.requests.post", return_value=mock_resp):
        monkeypatch.setattr(liner_client, "_api_key", lambda: "k")
        result = liner_client.search_agent("world model", mode="scholar")

    assert result["summary"]["text"] == "Hello world"
    assert result["summary"]["references"] == [{"url": "https://x"}]
