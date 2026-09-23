import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import daily_pipeline, liner_client
from src.canonical_pages import read_page

SCHOLAR_RESPONSE = {
    "status_code": 200,
    "response": {"results": [
        {"title": "Semantic Gaussians", "url": "https://arxiv.org/abs/1", "date": "2024-01-01",
         "journal": "CVPR 2024", "description": "abstract A", "authors": ["A. One"]},
    ]},
}
TWO_PAPERS_RESPONSE = {
    "status_code": 200,
    "response": {"results": [
        {"title": "Semantic Gaussians", "url": "https://arxiv.org/abs/1", "date": "2024-01-01",
         "journal": "CVPR 2024", "description": "abstract A", "authors": ["A. One"]},
        {"title": "Semantic Gaussians Two", "url": "https://arxiv.org/abs/2", "date": "2024-01-01",
         "journal": "CVPR 2024", "description": "abstract B", "authors": ["B. Two"]},
    ]},
}
EXTRACTED = {
    "problem": ["open-vocabulary understanding"], "method": ["semantic gaussian representation"],
    "dataset": ["ScanNet"], "task": [], "evaluation": [], "limitations": ["weak relational reasoning"],
    "future_work": [], "summary_ko": "개방형 어휘 3D 장면 이해를 위한 시맨틱 가우시안 표현 방법을 제안한다.",
}
SYNTHESIS_RESULT = {
    "search_agent_scholar": {"text": "synthesis", "references": []},
    "deep_research": {"text": "report", "references": [], "next_topics": ["derived topic"]},
}


def _seed_wiki(root):
    (root / "index.md").write_text(
        "# Wiki Index\n\n> Total pages: 0\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n",
        encoding="utf-8",
    )
    (root / "log.md").write_text("# Wiki Log\n\n", encoding="utf-8")


def test_process_topic_captures_paper_and_creates_canonical_pages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=SCHOLAR_RESPONSE), \
         patch("src.daily_pipeline.extraction.extract_paper", return_value=EXTRACTED), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT):
        result = daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    assert result["fetched"] == 1
    assert result["kept"] == 1
    assert result["captured"] == 1
    assert result["already_known"] == 0
    assert result["next_topics"] == ["derived topic"]

    assert (tmp_path / "raw" / "paper" / "semantic-gaussians.md").exists()
    assert read_page("entity", "semantic gaussian representation") is None  # 1 source: staged
    assert read_page("entity", "ScanNet") is None
    assert read_page("concept", "open-vocabulary understanding") is None
    assert read_page("concept", "world model") is not None  # hub
    hub_fm, hub_body = read_page("concept", "world model")
    assert "Semantic Gaussians" in hub_body
    assert "derived topic" in hub_body
    assert "weak relational reasoning" in hub_body
    assert result["extracted"] == 1

    assert result["papers"] == [{
        "title": "Semantic Gaussians", "url": "https://arxiv.org/abs/1",
        "summary": "개방형 어휘 3D 장면 이해를 위한 시맨틱 가우시안 표현 방법을 제안한다.",
        "path": "raw/paper/semantic-gaussians.md",
        "problem": ["open-vocabulary understanding"], "method": ["semantic gaussian representation"],
    }]
    assert result["taxonomy_slug"] is None  # only 1 paper, below MIN_PAPERS_FOR_TAXONOMY


def test_process_topic_creates_label_pages_on_the_second_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=TWO_PAPERS_RESPONSE), \
         patch("src.daily_pipeline.extraction.extract_paper", return_value=EXTRACTED), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT):
        daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    fm, _ = read_page("entity", "ScanNet")
    assert fm["sources"] == ["raw/paper/semantic-gaussians.md", "raw/paper/semantic-gaussians-two.md"]
    assert fm["confidence"] == "high"
    assert read_page("entity", "semantic gaussian representation") is not None
    assert read_page("concept", "open-vocabulary understanding") is not None


def test_paper_summary_uses_the_extracted_korean_summary():
    assert daily_pipeline._paper_summary({"summary_ko": "한국어 한줄 요약."}) == "한국어 한줄 요약."


def test_paper_summary_falls_back_when_summary_ko_missing_or_empty():
    assert daily_pipeline._paper_summary({"summary_ko": ""}) == "(요약 없음)"
    assert daily_pipeline._paper_summary({}) == "(요약 없음)"


def test_process_topic_second_run_marks_paper_already_known(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=SCHOLAR_RESPONSE), \
         patch("src.daily_pipeline.extraction.extract_paper", return_value=EXTRACTED) as mock_extract, \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT):
        daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))
        result = daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 7))

    assert result["captured"] == 0
    assert result["already_known"] == 1
    assert result["extracted"] == 0
    mock_extract.assert_called_once()


def test_process_topic_raises_on_non_2xx_scholar_response(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value={"status_code": 429, "response": {}}):
        with pytest.raises(RuntimeError):
            daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))


def test_process_topic_skips_single_failed_paper_extraction(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    two_papers_response = {
        "status_code": 200,
        "response": {"results": [
            {"title": "Paper A", "url": "https://arxiv.org/abs/1", "date": "2024-01-01", "description": "a", "authors": []},
            {"title": "Paper B", "url": "https://arxiv.org/abs/2", "date": "2024-01-01", "description": "b", "authors": []},
        ]},
    }
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=two_papers_response), \
         patch("src.daily_pipeline.extraction.extract_paper", side_effect=[RuntimeError("429"), EXTRACTED]), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT):
        result = daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    assert result["kept"] == 2
    assert result["captured"] == 1
    assert result["failed_extractions"] == 1


def test_process_topic_propagates_account_level_error_immediately(tmp_path, monkeypatch):
    """A 402/401/429 is never paper-specific — every remaining paper (and
    every remaining topic) would fail identically, so process_topic must
    stop immediately rather than absorbing it into failed_extractions and
    burning through the rest of filtered["kept"] on calls guaranteed to
    fail, then still returning normally (which used to let _run_pipeline
    mark_done() the topic with essentially no real work accomplished)."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    two_papers_response = {
        "status_code": 200,
        "response": {"results": [
            {"title": "Paper A", "url": "https://arxiv.org/abs/1", "date": "2024-01-01", "description": "a", "authors": []},
            {"title": "Paper B", "url": "https://arxiv.org/abs/2", "date": "2024-01-01", "description": "b", "authors": []},
        ]},
    }
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    extract_mock = MagicMock(side_effect=liner_client.AccountLevelAPIError(
        "search_agent (extraction) failed with status 402"
    ))
    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=two_papers_response), \
         patch("src.daily_pipeline.extraction.extract_paper", extract_mock), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis") as mock_synthesis:
        with pytest.raises(liner_client.AccountLevelAPIError):
            daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    # Stopped after the first paper — never tried Paper B on a call
    # guaranteed to fail identically, and never reached synthesis either.
    extract_mock.assert_called_once()
    mock_synthesis.assert_not_called()


def test_process_topic_isolates_page_write_failure_to_one_paper(tmp_path, monkeypatch):
    """Finding 4: a failure in raw_paper.write_paper (or a canonical page
    write) for one paper must not abort the whole topic — only that paper
    is skipped, still counted via failed_extractions, while the other
    paper (whose extraction was already paid for) is still captured."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    two_papers_response = {
        "status_code": 200,
        "response": {"results": [
            {"title": "Paper A", "url": "https://arxiv.org/abs/1", "date": "2024-01-01", "description": "a", "authors": []},
            {"title": "Paper B", "url": "https://arxiv.org/abs/2", "date": "2024-01-01", "description": "b", "authors": []},
        ]},
    }
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=two_papers_response), \
         patch("src.daily_pipeline.extraction.extract_paper", return_value=EXTRACTED), \
         patch("src.daily_pipeline.raw_paper.write_paper",
               side_effect=[RuntimeError("disk full"), (Path("raw/paper/paper-b.md"), True)]), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT):
        result = daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    assert result["kept"] == 2
    assert result["captured"] == 1
    assert result["failed_extractions"] == 1
    assert "disk full" in result["failed_extraction_errors"][0]


def test_process_topic_caps_new_canonical_pages_per_topic(tmp_path, monkeypatch):
    """Finding 5: a topic with many kept papers must not fan out into
    unbounded new canonical pages in one run — MAX_NEW_PAGES_PER_TOPIC caps
    *new* page creation (updates to already-existing pages are unaffected)."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    many_papers_response = {
        "status_code": 200,
        "response": {"results": [
            {"title": f"Paper {i}", "url": f"https://arxiv.org/abs/{i}", "date": "2024-01-01",
             "description": "x", "authors": []}
            for i in range(20)
        ]},
    }

    def fake_extract(paper):
        i = paper["url"].rsplit("/", 1)[-1]
        return {
            "problem": [f"problem-{i}"], "method": [f"method-{i}"], "dataset": [], "task": [],
            "evaluation": [], "limitations": ["weak relational reasoning"], "future_work": [],
        }

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=many_papers_response), \
         patch("src.daily_pipeline.extraction.extract_paper", side_effect=fake_extract), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT), \
         patch("src.daily_pipeline.taxonomy_mod.generate_taxonomy", return_value=None):
        daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    new_entity_pages = list((tmp_path / "entities").glob("*.md"))
    new_concept_pages = [p for p in (tmp_path / "concepts").glob("*.md") if p.stem != "world-model"]
    total_new = len(new_entity_pages) + len(new_concept_pages)
    assert total_new <= daily_pipeline.MAX_NEW_PAGES_PER_TOPIC


def test_process_topic_generates_taxonomy_once_enough_papers_are_captured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(daily_pipeline, "DISCORD_CHANNEL_ID", "test-channel")
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    n = daily_pipeline.taxonomy_mod.MIN_PAPERS_FOR_TAXONOMY
    many_papers_response = {
        "status_code": 200,
        "response": {"results": [
            {"title": f"Paper {i}", "url": f"https://arxiv.org/abs/{i}", "date": "2024-01-01",
             "description": "x", "authors": []}
            for i in range(n)
        ]},
    }

    def fake_extract(paper):
        i = paper["url"].rsplit("/", 1)[-1]
        return {
            "problem": [f"problem-{i}"], "method": [f"method-{i}"], "dataset": [], "task": [],
            "evaluation": [], "limitations": [], "future_work": [], "summary_ko": "",
        }

    fake_taxonomy = {
        "axis": "axis", "clusters": [
            {"name": "C1", "description": "d", "papers": ["Paper 0"]},
            {"name": "C2", "description": "d", "papers": ["Paper 1"]},
        ], "off_axis": [], "insight": "",
    }

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=many_papers_response), \
         patch("src.daily_pipeline.extraction.extract_paper", side_effect=fake_extract), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT), \
         patch("src.daily_pipeline.taxonomy_mod.generate_taxonomy", return_value=fake_taxonomy) as mock_gen, \
         patch("src.daily_pipeline.subprocess.run") as mock_run:
        result = daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    mock_gen.assert_called_once()
    assert mock_gen.call_args.args[0] == "world model"
    assert len(mock_gen.call_args.args[1]) == n

    # Full taxonomy content sent to Discord, not just the [[link]] the main
    # report carries.
    mock_run.assert_called_once()
    sent_text = mock_run.call_args.args[0][-1]
    assert "world model" in sent_text
    assert "C1" in sent_text and "Paper 0" in sent_text
    assert "C2" in sent_text and "Paper 1" in sent_text
    assert result["taxonomy_slug"] == "world-model-paper-taxonomy"
    assert (tmp_path / "queries" / "world-model-paper-taxonomy.md").exists()


def test_process_topic_skips_taxonomy_below_minimum_papers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=SCHOLAR_RESPONSE), \
         patch("src.daily_pipeline.extraction.extract_paper", return_value=EXTRACTED), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT), \
         patch("src.daily_pipeline.taxonomy_mod.generate_taxonomy") as mock_gen:
        result = daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    mock_gen.assert_not_called()
    assert result["taxonomy_slug"] is None


def test_process_topic_taxonomy_failure_does_not_affect_topic_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    n = daily_pipeline.taxonomy_mod.MIN_PAPERS_FOR_TAXONOMY
    many_papers_response = {
        "status_code": 200,
        "response": {"results": [
            {"title": f"Paper {i}", "url": f"https://arxiv.org/abs/{i}", "date": "2024-01-01",
             "description": "x", "authors": []}
            for i in range(n)
        ]},
    }

    def fake_extract(paper):
        i = paper["url"].rsplit("/", 1)[-1]
        return {
            "problem": [f"problem-{i}"], "method": [f"method-{i}"], "dataset": [], "task": [],
            "evaluation": [], "limitations": [], "future_work": [], "summary_ko": "",
        }

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=many_papers_response), \
         patch("src.daily_pipeline.extraction.extract_paper", side_effect=fake_extract), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT), \
         patch("src.daily_pipeline.taxonomy_mod.generate_taxonomy", side_effect=RuntimeError("search_agent 500")):
        result = daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    assert result["taxonomy_slug"] is None
    assert result["captured"] == n  # paper capture work is unaffected by the taxonomy failure


def test_process_topic_cross_links_sibling_pages_from_the_same_paper(tmp_path, monkeypatch):
    """Finding I2: every pipeline-authored page used to get exactly one
    wikilink ([[hub]]), making SCHEMA.md's ">=2 wikilinks" rule structurally
    impossible to satisfy. Labels from the same paper now cross-link."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=TWO_PAPERS_RESPONSE), \
         patch("src.daily_pipeline.extraction.extract_paper", return_value=EXTRACTED), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT):
        daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    # EXTRACTED yields method=semantic gaussian representation, dataset=ScanNet,
    # problem=open-vocabulary understanding — three sibling labels.
    _, method_body = read_page("entity", "semantic gaussian representation")
    _, dataset_body = read_page("entity", "ScanNet")
    _, problem_body = read_page("concept", "open-vocabulary understanding")

    assert "[[scannet]]" in method_body
    assert "[[open-vocabulary-understanding]]" in method_body
    assert "[[semantic-gaussian-representation]]" in dataset_body
    assert "[[world-model]]" in dataset_body  # hub link is still there
    assert "[[scannet]]" in problem_body
    # No page links to itself.
    assert "[[semantic-gaussian-representation]]" not in method_body.split("# ", 1)[-1].split("## Related")[0]
    assert method_body.count("[[semantic-gaussian-representation]]") == 0
    for body in (method_body, dataset_body, problem_body):
        assert body.count("- [[") >= 2  # SCHEMA.md's >=2 wikilinks rule


def test_process_topic_never_links_to_a_page_the_cap_suppressed(tmp_path, monkeypatch):
    """Re-review regression on Finding I2: sibling wikilinks were derived
    from *all* of a paper's labels, but MAX_NEW_PAGES_PER_TOPIC suppresses
    some of them — so written pages linked to pages that were never created
    (dangling links, violating SCHEMA.md's link-resolution rule)."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    # 20 papers x 4 distinct labels each, far past the 15-page cap, so the
    # cap necessarily fires part-way through a paper's own label list.
    many_papers_response = {
        "status_code": 200,
        "response": {"results": [
            {"title": f"Paper {i}", "url": f"https://arxiv.org/abs/{i}", "date": "2024-01-01",
             "description": "x", "authors": []}
            for i in range(20)
        ]},
    }

    def fake_extract(paper):
        i = paper["url"].rsplit("/", 1)[-1]
        return {
            "problem": [f"problem-{i}"], "method": [f"method-{i}"],
            "dataset": [f"dataset-{i}"], "task": [f"task-{i}"],
            "evaluation": [], "limitations": [], "future_work": [],
        }

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=many_papers_response), \
         patch("src.daily_pipeline.extraction.extract_paper", side_effect=fake_extract), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT), \
         patch("src.daily_pipeline.taxonomy_mod.generate_taxonomy", return_value=None):
        daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    written = list((tmp_path / "entities").glob("*.md")) + list((tmp_path / "concepts").glob("*.md"))
    existing_slugs = {p.stem for p in written}
    # The cap really did fire (otherwise this test proves nothing).
    assert len(existing_slugs) <= daily_pipeline.MAX_NEW_PAGES_PER_TOPIC + 1  # +1 for the hub page
    assert len(existing_slugs) < 20 * 4

    dangling = []
    for path in written:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("- [["):
                target = line.split("[[", 1)[1].split("]]", 1)[0]
                if target not in existing_slugs:
                    dangling.append((path.stem, target))
    assert dangling == []


def test_process_topic_does_not_duplicate_hub_link_when_label_equals_topic(tmp_path, monkeypatch):
    """Re-review Minor 1: an extracted label identical to the topic makes
    hub_slug appear among the sibling slugs, which used to emit two
    identical `- [[world-model]]` lines on a newly created page."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    extracted = {
        "problem": ["world model"],  # identical to the topic itself
        "method": ["semantic gaussian representation"],
        "dataset": [], "task": [], "evaluation": [], "limitations": [], "future_work": [],
    }

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=TWO_PAPERS_RESPONSE), \
         patch("src.daily_pipeline.extraction.extract_paper", return_value=extracted), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT):
        daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    _, method_body = read_page("entity", "semantic gaussian representation")
    assert method_body.count("- [[world-model]]") == 1


def test_process_topic_survives_synthesis_failure_without_losing_paper_work(tmp_path, monkeypatch):
    """Finding I1: a synthesis failure used to propagate out of
    process_topic, recording the topic as a total failure (captured 0, cost
    excluded, no mark_done) even though its papers were already captured and
    written to disk — forcing the next run to re-pay for identical work."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=SCHOLAR_RESPONSE), \
         patch("src.daily_pipeline.extraction.extract_paper", return_value=EXTRACTED), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis",
               side_effect=RuntimeError("deep_research 500")):
        result = daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    assert result["captured"] > 0
    assert result["next_topics"] == []
    assert "deep_research 500" in result["synthesis_error"]
    assert "error" not in result  # not a total topic failure
    assert (tmp_path / "raw" / "paper" / "semantic-gaussians.md").exists()


def test_process_topic_skips_paper_whose_existing_page_is_malformed(tmp_path, monkeypatch):
    """Finding I5 part A + the Task 7 per-paper try/except: a pre-existing
    hand-edited block-YAML page now raises on read, and that must skip only
    the affected paper, not abort the whole topic."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    (tmp_path / "entities").mkdir()
    (tmp_path / "entities" / "scannet.md").write_text(
        '---\ntitle: "ScanNet"\ntype: "entity"\ntags:\n  - research\n  - research-gap\n'
        'sources: ["raw/paper/old.md"]\ncontested: false\ncontradictions: []\n---\n\n# ScanNet\n',
        encoding="utf-8",
    )
    two_papers_response = {
        "status_code": 200,
        "response": {"results": [
            {"title": "Paper A", "url": "https://arxiv.org/abs/1", "date": "2024-01-01", "description": "a", "authors": []},
            {"title": "Paper B", "url": "https://arxiv.org/abs/2", "date": "2024-01-01", "description": "b", "authors": []},
        ]},
    }
    # Only the first paper mentions ScanNet, so only it hits the bad page.
    extractions = [
        dict(EXTRACTED),
        {"problem": ["другой problem"], "method": ["clean method"], "dataset": [], "task": [],
         "evaluation": [], "limitations": [], "future_work": []},
    ]
    topic_entry = {"id": "world-model", "topic": "world model"}
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with patch("src.daily_pipeline.liner_client.search_scholar", return_value=two_papers_response), \
         patch("src.daily_pipeline.extraction.extract_paper", side_effect=extractions), \
         patch("src.daily_pipeline.synthesis.run_topic_synthesis", return_value=SYNTHESIS_RESULT):
        result = daily_pipeline.process_topic(topic_entry, run_dir, date(2026, 8, 4))

    assert result["failed_extractions"] == 1
    assert "tags" in result["failed_extraction_errors"][0]
    assert result["captured"] == 2  # raw writes finished before the ScanNet page raise
    assert read_page("entity", "clean method") is None  # 1 source: staged
    assert "- research-gap" in (tmp_path / "entities" / "scannet.md").read_text(encoding="utf-8")


def _seed_backlog(cwd, topics):
    backlog_path = cwd / "research-gap" / "backlog.json"
    backlog_path.parent.mkdir(parents=True, exist_ok=True)
    backlog_path.write_text(json.dumps({"topics": topics}), encoding="utf-8")


def test_main_happy_path_marks_topics_done_and_writes_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "world-model", "topic": "world model", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    def fake_process_topic(entry, run_dir, today):
        return {
            "topic": entry["topic"], "fetched": 5, "kept": 3, "dropped_year": 1,
            "captured": 3, "already_known": 0, "failed_extractions": 0, "pages_touched": [],
            "next_topics": [],
        }

    with patch("src.daily_pipeline.process_topic", side_effect=fake_process_topic), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons", return_value=[]):
        daily_pipeline.main()

    out = capsys.readouterr().out
    assert "world model" in out
    saved_backlog = json.loads((tmp_path / "research-gap" / "backlog.json").read_text(encoding="utf-8"))
    assert saved_backlog["topics"][0]["status"] == "done"


def test_run_pipeline_sends_one_discord_message_per_topic_with_papers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(daily_pipeline, "DISCORD_CHANNEL_ID", "test-channel")
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "world-model", "topic": "world model", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
        {"id": "no-papers", "topic": "no papers topic", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    def fake_process_topic(entry, run_dir, today):
        papers = [{"title": "Paper A", "url": "https://arxiv.org/abs/1", "summary": "s"}] \
            if entry["id"] == "world-model" else []
        return {
            "topic": entry["topic"], "fetched": 1, "kept": 1, "dropped_year": 0,
            "captured": 1, "already_known": 0, "failed_extractions": 0,
            "failed_extraction_errors": [], "pages_touched": [],
            "next_topics": [], "synthesis_error": None, "papers": papers,
        }

    with patch("src.daily_pipeline.process_topic", side_effect=fake_process_topic), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons", return_value=[]), \
         patch("src.daily_pipeline.subprocess.run") as mock_run:
        daily_pipeline.main()

    # Exactly one send, for the topic that actually has papers.
    mock_run.assert_called_once()
    sent_text = mock_run.call_args.args[0][-1]
    assert "world model" in sent_text
    assert "Paper A" in sent_text
    assert "https://arxiv.org/abs/1" in sent_text


def test_run_pipeline_does_not_send_discord_message_for_failed_topic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "world-model", "topic": "world model", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    with patch("src.daily_pipeline.process_topic", side_effect=RuntimeError("boom")), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons", return_value=[]), \
         patch("src.daily_pipeline.subprocess.run") as mock_run:
        daily_pipeline.main()

    mock_run.assert_not_called()


def test_main_all_topics_fail_stay_pending_and_report_shows_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "world-model", "topic": "world model", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    with patch("src.daily_pipeline.process_topic", side_effect=RuntimeError("search_scholar failed with status 401")), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons", return_value=[]):
        daily_pipeline.main()

    out = capsys.readouterr().out
    assert "실패" in out
    assert "401" in out
    saved_backlog = json.loads((tmp_path / "research-gap" / "backlog.json").read_text(encoding="utf-8"))
    assert saved_backlog["topics"][0]["status"] == "pending"


def test_run_pipeline_stops_remaining_topics_on_account_level_error(tmp_path, monkeypatch, capsys):
    """No credits / invalid key / rate-limited affects the whole account,
    not just the topic that happened to hit it first — every other pending
    topic in this run would fail identically. Must not mark_done() the
    topic that hit it (so it's retried, not silently discarded after only
    partial/no real work), and must not waste calls trying the remaining
    pending topics too."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "topic-one", "topic": "topic one", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
        {"id": "topic-two", "topic": "topic two", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    process_topic_mock = MagicMock(side_effect=liner_client.AccountLevelAPIError(
        "search_agent (extraction) failed with status 402"
    ))
    with patch("src.daily_pipeline.process_topic", process_topic_mock), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons", return_value=[]):
        daily_pipeline.main()

    # topic-two was never even attempted.
    process_topic_mock.assert_called_once()
    out = capsys.readouterr().out
    assert "402" in out
    assert "pending" in out or "재시도" in out
    saved_backlog = json.loads((tmp_path / "research-gap" / "backlog.json").read_text(encoding="utf-8"))
    by_id = {t["id"]: t for t in saved_backlog["topics"]}
    assert by_id["topic-one"]["status"] == "pending"
    assert by_id["topic-two"]["status"] == "pending"


def test_main_gap_detection_failure_does_not_lose_backlog_progress(tmp_path, monkeypatch, capsys):
    """Findings 1 & 2: a gap-detection failure must not unwind the run and
    discard already-completed topics' backlog progress, and the report must
    still show the successful topic's results (not just a bare error)."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "world-model", "topic": "world model", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    def fake_process_topic(entry, run_dir, today):
        return {
            "topic": entry["topic"], "fetched": 5, "kept": 3, "dropped_year": 1,
            "captured": 3, "already_known": 0, "failed_extractions": 0, "pages_touched": [],
            "next_topics": [],
        }

    with patch("src.daily_pipeline.process_topic", side_effect=fake_process_topic), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons",
               side_effect=RuntimeError("malformed wiki page")):
        # 2026-08-06 is a Thursday: gap detection only runs Thu/Sun
        # (GAP_DETECTION_WEEKDAYS), so this must land on one of those days
        # to actually exercise the failure path, not daily_pipeline.main()'s
        # real "today" (which would silently skip gap detection most days).
        daily_pipeline._run_pipeline(datetime(2026, 8, 6, 1, 0), date(2026, 8, 6))

    out = capsys.readouterr().out
    assert "world model" in out
    assert "gap detection failed" in out
    saved_backlog = json.loads((tmp_path / "research-gap" / "backlog.json").read_text(encoding="utf-8"))
    assert saved_backlog["topics"][0]["status"] == "done"


def test_main_cost_estimate_bills_on_kept_not_captured(tmp_path, monkeypatch, capsys):
    """Finding 3: extraction is attempted once per kept paper regardless of
    whether it's a re-run that finds every paper already-known, so the cost
    estimate must bill on kept, not captured."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "world-model", "topic": "world model", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    def fake_process_topic(entry, run_dir, today):
        return {
            "topic": entry["topic"], "fetched": 5, "kept": 5, "dropped_year": 0,
            "captured": 0, "already_known": 5, "failed_extractions": 0, "pages_touched": [],
            "next_topics": [],
        }

    with patch("src.daily_pipeline.process_topic", side_effect=fake_process_topic), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons", return_value=[]):
        daily_pipeline.main()

    out = capsys.readouterr().out
    # v2 bills extraction on papers actually sent to Search Agent (`extracted`),
    # not on kept. already-known papers are $0. Scholar + scholar-synthesis
    # = 0.001 + 0.02 = $0.02. No per-topic Deep Research.
    assert "$0.02" in out


def test_main_synthesis_failure_still_marks_done_bills_and_reports(tmp_path, monkeypatch, capsys):
    """Finding I1: a topic whose synthesis call failed still completed (and
    paid for) its paper work — it must be marked done, billed normally, and
    reported as a partial failure rather than a total one."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "world-model", "topic": "world model", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    def fake_process_topic(entry, run_dir, today):
        return {
            "topic": entry["topic"], "fetched": 5, "kept": 5, "dropped_year": 0,
            "captured": 5, "already_known": 0, "failed_extractions": 0,
            "failed_extraction_errors": [], "pages_touched": [],
            "next_topics": [], "synthesis_error": "deep_research 500",
            "extracted": 5,
        }

    with patch("src.daily_pipeline.process_topic", side_effect=fake_process_topic), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons", return_value=[]):
        daily_pipeline.main()

    out = capsys.readouterr().out
    assert "신규 raw/paper 5편" in out           # the paper work is still reported
    assert "synthesis 실패" in out
    assert "deep_research 500" in out
    assert "$0.14" in out                        # 0.001 + 5*0.02 + 0.02 + 0.02 taxonomy, no DR
    saved_backlog = json.loads((tmp_path / "research-gap" / "backlog.json").read_text(encoding="utf-8"))
    assert saved_backlog["topics"][0]["status"] == "done"


def test_run_pipeline_skips_gap_detection_on_a_non_thu_sun_day(tmp_path, monkeypatch):
    """Topic collection runs daily, but gap detection (comparisons/) only
    runs Thu/Sun — running it every day would scan the whole corpus and
    create comparison pages far more aggressively than intended."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "world-model", "topic": "world model", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    def fake_process_topic(entry, run_dir, today):
        return {
            "topic": entry["topic"], "fetched": 5, "kept": 3, "dropped_year": 1,
            "captured": 3, "already_known": 0, "failed_extractions": 0,
            "failed_extraction_errors": [], "pages_touched": [],
            "next_topics": [], "synthesis_error": None,
        }

    with patch("src.daily_pipeline.process_topic", side_effect=fake_process_topic), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons") as mock_gap:
        # 2026-08-04 is a Tuesday.
        daily_pipeline._run_pipeline(datetime(2026, 8, 4, 1, 0), date(2026, 8, 4))

    mock_gap.assert_not_called()


def test_run_pipeline_runs_gap_detection_on_thu_and_sun(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [])  # no pending topics needed to exercise gap detection itself

    with patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons", return_value=[]) as mock_gap:
        daily_pipeline._run_pipeline(datetime(2026, 8, 6, 1, 0), date(2026, 8, 6))   # Thursday
        daily_pipeline._run_pipeline(datetime(2026, 8, 9, 1, 0), date(2026, 8, 9))   # Sunday

    assert mock_gap.call_count == 2


def test_run_pipeline_sends_gap_candidate_detail_to_discord(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(daily_pipeline, "DISCORD_CHANNEL_ID", "test-channel")
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [])  # no pending topics needed to exercise gap detection itself

    comparisons_dir = tmp_path / "comparisons"
    comparisons_dir.mkdir()
    (comparisons_dir / "a-vs-b-underexplored-connection.md").write_text(
        '---\ntitle: "A vs B: underexplored connection"\ncreated: "2026-08-06"\nupdated: "2026-08-06"\n'
        'type: "comparison"\ntags: ["research"]\nsources: ["raw/paper/a.md", "raw/paper/b.md"]\n'
        'confidence: "medium"\ncontested: false\ncontradictions: []\n---\n\n# A vs B\n',
        encoding="utf-8",
    )

    with patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons",
               return_value=["a-vs-b-underexplored-connection"]), \
         patch("src.daily_pipeline.subprocess.run") as mock_run:
        daily_pipeline._run_pipeline(datetime(2026, 8, 6, 1, 0), date(2026, 8, 6))   # Thursday

    mock_run.assert_called_once()
    sent_text = mock_run.call_args.args[0][-1]
    assert "A vs B: underexplored connection" in sent_text
    assert "raw/paper/a.md" in sent_text and "raw/paper/b.md" in sent_text


def test_run_pipeline_persists_backlog_after_every_topic(tmp_path, monkeypatch):
    """Finding I4: backlog progress used to be saved only after the whole
    per-topic loop, so a process kill mid-batch discarded already-completed
    topics' progress and forced a costly re-run."""
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "topic-one", "topic": "topic one", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
        {"id": "topic-two", "topic": "topic two", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    def fake_process_topic(entry, run_dir, today):
        if entry["id"] == "topic-two":
            raise KeyboardInterrupt("simulated process kill")  # BaseException: not swallowed
        return {
            "topic": entry["topic"], "fetched": 5, "kept": 3, "dropped_year": 1,
            "captured": 3, "already_known": 0, "failed_extractions": 0,
            "failed_extraction_errors": [], "pages_touched": [],
            "next_topics": ["derived from one"], "synthesis_error": None,
        }

    with patch("src.daily_pipeline.process_topic", side_effect=fake_process_topic), \
         patch("src.daily_pipeline.wiki_gap_detector.run_and_create_comparisons", return_value=[]):
        with pytest.raises(KeyboardInterrupt):
            daily_pipeline._run_pipeline(datetime(2026, 8, 4, 1, 0), date(2026, 8, 4))

    # The crash happened before the end of the loop, yet topic one's
    # progress (and its derived curiosity topic) is already durable on disk.
    saved = json.loads((tmp_path / "research-gap" / "backlog.json").read_text(encoding="utf-8"))
    by_id = {t["id"]: t for t in saved["topics"]}
    assert by_id["topic-one"]["status"] == "done"
    assert by_id["topic-two"]["status"] == "pending"
    assert all(t["topic"] != "derived from one" for t in saved["topics"])


def test_main_survives_unexpected_top_level_failure_and_still_reports(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _seed_wiki(tmp_path)
    _seed_backlog(tmp_path, [
        {"id": "world-model", "topic": "world model", "status": "pending", "source": "seed", "added_date": "2026-08-03"},
    ])

    with patch("src.daily_pipeline.backlog_mod.load_backlog", side_effect=RuntimeError("corrupt backlog.json")):
        daily_pipeline.main()  # must not raise

    out = capsys.readouterr().out
    assert "예상치 못한 오류" in out
    assert "corrupt backlog.json" in out
