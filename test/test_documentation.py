from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_english_readme_covers_safe_first_run() -> None:
    """Deleting any required first-run instruction must fail this check."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for required in (
        "## Quick start",
        "python3.11 -m venv .venv",
        "python -m pip install -e \".[test]\"",
        "cp .env.example .env",
        "LINER_API_KEY",
        "python -m pytest",
        "## First topic: synthetic dry run and manual research",
        "candidate, not verified knowledge",
        "Never commit `.env`",
    ):
        assert required in readme


def test_korean_readme_covers_safe_first_run() -> None:
    """The Korean guide must retain the same operational safety boundaries."""
    readme = (ROOT / "README.ko.md").read_text(encoding="utf-8")

    for required in (
        "## 빠른 시작",
        "cp .env.example .env",
        "LINER_API_KEY",
        "python -m pytest",
        "## 첫 주제: 합성 드라이 런과 수동 조사",
        "후보일 뿐",
        "`.env`를 커밋하지 마세요",
    ):
        assert required in readme


def test_public_guides_and_templates_explain_evidence_and_human_review() -> None:
    """Public guides must preserve the evidence-first, human-review workflow."""
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    workflow = (ROOT / "docs" / "workflow.md").read_text(encoding="utf-8")
    raw_template = (ROOT / "templates" / "raw-paper.md").read_text(encoding="utf-8")
    canonical_template = (ROOT / "templates" / "canonical-page.md").read_text(encoding="utf-8")

    assert "raw/" in architecture
    assert "canonical" in architecture.lower()
    assert "candidate" in workflow.lower()
    assert "human" in workflow.lower()
    assert "sha256" in raw_template
    assert "sources" in canonical_template
