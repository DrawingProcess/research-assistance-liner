import json
from unittest.mock import patch

from src import taxonomy

PAPERS = [
    {"title": "Paper A", "problem": ["problem X"], "method": ["method 1"], "path": "raw/paper/a.md"},
    {"title": "Paper B", "problem": ["problem X"], "method": ["method 2"], "path": "raw/paper/b.md"},
    {"title": "Paper C", "problem": ["problem Y"], "method": ["method 1"], "path": "raw/paper/c.md"},
]
KNOWN_TITLES = {p["title"] for p in PAPERS}

VALID_RESPONSE = json.dumps({
    "axis": "How is the core problem solved?",
    "clusters": [
        {"name": "Cluster 1", "description": "uses method 1", "papers": ["Paper A", "Paper C"]},
        {"name": "Cluster 2", "description": "uses method 2", "papers": ["Paper B"]},
    ],
    "off_axis": [],
    "insight": "No paper combines both methods.",
})


def _seed_wiki(root):
    (root / "index.md").write_text(
        "# Wiki Index\n\n> Total pages: 0\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n",
        encoding="utf-8",
    )
    (root / "log.md").write_text("# Wiki Log\n\n", encoding="utf-8")


def test_build_taxonomy_prompt_includes_topic_and_all_papers():
    prompt = taxonomy.build_taxonomy_prompt("test topic", PAPERS)
    assert "test topic" in prompt
    assert "Paper A" in prompt and "Paper B" in prompt and "Paper C" in prompt
    assert "problem X" in prompt
    assert "method 1" in prompt


def test_parse_taxonomy_response_handles_clean_json():
    result = taxonomy.parse_taxonomy_response(VALID_RESPONSE, KNOWN_TITLES)
    assert result["axis"] == "How is the core problem solved?"
    assert len(result["clusters"]) == 2
    assert result["clusters"][0]["papers"] == ["Paper A", "Paper C"]
    assert result["insight"] == "No paper combines both methods."


def test_parse_taxonomy_response_drops_hallucinated_titles():
    raw = json.dumps({
        "axis": "axis",
        "clusters": [
            {"name": "C1", "description": "d", "papers": ["Paper A", "A Paper That Was Never Given"]},
            {"name": "C2", "description": "d", "papers": ["Paper B"]},
        ],
        "off_axis": [{"title": "Also Not Real", "reason": "r"}],
        "insight": "",
    })
    result = taxonomy.parse_taxonomy_response(raw, KNOWN_TITLES)
    assert result["clusters"][0]["papers"] == ["Paper A"]  # hallucinated title dropped
    assert result["off_axis"] == []  # hallucinated off_axis title dropped entirely


def test_parse_taxonomy_response_rejects_fewer_than_two_usable_clusters():
    raw = json.dumps({
        "axis": "axis",
        "clusters": [{"name": "C1", "description": "d", "papers": ["Paper A"]}],
        "off_axis": [], "insight": "",
    })
    assert taxonomy.parse_taxonomy_response(raw, KNOWN_TITLES) is None


def test_parse_taxonomy_response_rejects_cluster_left_with_no_real_papers():
    raw = json.dumps({
        "axis": "axis",
        "clusters": [
            {"name": "C1", "description": "d", "papers": ["Not Real At All"]},
            {"name": "C2", "description": "d", "papers": ["Paper B"]},
        ],
        "off_axis": [], "insight": "",
    })
    # C1 loses its only (hallucinated) paper and is dropped -> only 1 usable cluster left.
    assert taxonomy.parse_taxonomy_response(raw, KNOWN_TITLES) is None


def test_parse_taxonomy_response_drops_off_axis_entry_already_placed_in_a_cluster():
    """Observed live against the real API: the model sometimes hedges by
    listing the same paper both in a cluster and in off_axis with a
    caveat. The cluster placement should win, not both."""
    raw = json.dumps({
        "axis": "axis",
        "clusters": [
            {"name": "C1", "description": "d", "papers": ["Paper A"]},
            {"name": "C2", "description": "d", "papers": ["Paper B"]},
        ],
        "off_axis": [{"title": "Paper A", "reason": "hedging note"}],
        "insight": "",
    })
    result = taxonomy.parse_taxonomy_response(raw, KNOWN_TITLES)
    assert result["off_axis"] == []
    assert result["clusters"][0]["papers"] == ["Paper A"]


def test_parse_taxonomy_response_returns_none_for_malformed_json():
    assert taxonomy.parse_taxonomy_response("not json", KNOWN_TITLES) is None


def test_parse_taxonomy_response_returns_none_when_axis_missing():
    raw = json.dumps({"clusters": [], "off_axis": [], "insight": ""})
    assert taxonomy.parse_taxonomy_response(raw, KNOWN_TITLES) is None


def test_generate_taxonomy_calls_search_agent_and_parses():
    with patch("src.taxonomy.liner_client.search_agent") as mock_agent:
        mock_agent.return_value = {"status_code": 200, "summary": {"text": VALID_RESPONSE, "references": []}}
        result = taxonomy.generate_taxonomy("test topic", PAPERS)
    mock_agent.assert_called_once()
    assert mock_agent.call_args.kwargs["mode"] == "general"
    assert result["axis"] == "How is the core problem solved?"


def test_generate_taxonomy_raises_on_non_2xx_response():
    with patch("src.taxonomy.liner_client.search_agent") as mock_agent:
        mock_agent.return_value = {"status_code": 500, "summary": {"text": "", "references": []}}
        try:
            taxonomy.generate_taxonomy("test topic", PAPERS)
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass


def test_generate_taxonomy_retries_once_on_malformed_first_response():
    """Only one shot per topic ever (see daily_pipeline.process_topic) — a
    single malformed response (observed live against the real API) must not
    permanently forfeit the taxonomy for that topic."""
    with patch("src.taxonomy.liner_client.search_agent") as mock_agent:
        mock_agent.side_effect = [
            {"status_code": 200, "summary": {"text": "not json at all", "references": []}},
            {"status_code": 200, "summary": {"text": VALID_RESPONSE, "references": []}},
        ]
        result = taxonomy.generate_taxonomy("test topic", PAPERS)
    assert mock_agent.call_count == 2
    assert result["axis"] == "How is the core problem solved?"


def test_generate_taxonomy_returns_none_after_all_attempts_fail_to_parse():
    with patch("src.taxonomy.liner_client.search_agent") as mock_agent:
        mock_agent.return_value = {"status_code": 200, "summary": {"text": "not json", "references": []}}
        result = taxonomy.generate_taxonomy("test topic", PAPERS)
    assert mock_agent.call_count == taxonomy.MAX_ATTEMPTS
    assert result is None


def test_write_taxonomy_page_creates_valid_canonical_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    taxonomy_result = taxonomy.parse_taxonomy_response(VALID_RESPONSE, KNOWN_TITLES)
    sources_by_title = {p["title"]: p["path"] for p in PAPERS}

    path = taxonomy.write_taxonomy_page(
        "test topic", taxonomy_result, sources_by_title, ["hub-slug"], __import__("datetime").date(2026, 8, 8)
    )

    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert 'type: "query"' in text
    assert "Cluster 1" in text
    assert "Paper A" in text
    assert "No paper combines both methods." in text
    assert "[[hub-slug]]" in text
    # sources come from our own known paths, not anything the model could have invented
    assert "raw/paper/a.md" in text and "raw/paper/b.md" in text and "raw/paper/c.md" in text

    index_text = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert "test-topic-paper-taxonomy" in index_text
    log_text = (tmp_path / "log.md").read_text(encoding="utf-8")
    assert "test topic: paper taxonomy" in log_text


def test_write_taxonomy_page_skips_if_already_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    taxonomy_result = taxonomy.parse_taxonomy_response(VALID_RESPONSE, KNOWN_TITLES)
    sources_by_title = {p["title"]: p["path"] for p in PAPERS}
    today = __import__("datetime").date(2026, 8, 8)

    first = taxonomy.write_taxonomy_page("test topic", taxonomy_result, sources_by_title, ["hub-slug"], today)
    assert first is not None
    second = taxonomy.write_taxonomy_page("test topic", taxonomy_result, sources_by_title, ["hub-slug"], today)
    assert second is None
