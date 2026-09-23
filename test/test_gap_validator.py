from src.gap_validator import validate_gap_pair


def _scholar(n):
    return {
        "status_code": 200,
        "response": {"results": [{"title": f"P{i}", "url": f"https://arxiv.org/abs/{i}"} for i in range(n)]},
    }


def test_validate_gap_pair_already_done_when_many_hits(monkeypatch):
    from unittest.mock import patch
    with patch("src.gap_validator.liner_client.search_scholar", return_value=_scholar(5)):
        out = validate_gap_pair("Area A", "Area B")
    assert out["verdict"] == "already_done"
    assert out["count"] == 5


def test_validate_gap_pair_underexplored_when_few_hits(monkeypatch):
    from unittest.mock import patch
    with patch("src.gap_validator.liner_client.search_scholar", return_value=_scholar(2)):
        out = validate_gap_pair("Area A", "Area B")
    assert out["verdict"] == "underexplored"


def test_validate_gap_pair_needs_human_when_zero_hits(monkeypatch):
    from unittest.mock import patch
    with patch("src.gap_validator.liner_client.search_scholar", return_value=_scholar(0)):
        out = validate_gap_pair("Area A", "Area B")
    assert out["verdict"] == "needs_human"
