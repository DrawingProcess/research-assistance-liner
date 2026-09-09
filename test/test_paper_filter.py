from datetime import date

from src.paper_filter import filter_papers, paper_year

TODAY = date(2026, 8, 3)  # 5-year window: 2021+


def test_paper_year_parses_leading_year_from_date_string():
    assert paper_year({"date": "2024-03-22"}) == 2024
    assert paper_year({"date": ""}) is None
    assert paper_year({}) is None


def test_filter_keeps_all_papers_within_year_window():
    papers = [
        {"title": "Old", "date": "2019-01-01"},
        {"title": "New", "date": "2024-01-01"},
    ]
    result = filter_papers(papers, TODAY)
    assert [p["title"] for p in result["kept"]] == ["New"]
    assert result["dropped_year"] == 1


def test_filter_keeps_paper_missing_journal_or_description():
    papers = [{"title": "A", "date": "2024-01-01"}]
    result = filter_papers(papers, TODAY)
    assert len(result["kept"]) == 1
