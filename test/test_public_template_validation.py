from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_public_template.py"


def run_validator(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--repo", str(repo)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_validator_accepts_the_sanitized_template() -> None:
    """Removing the public-safety checks must make this test fail."""
    result = run_validator(ROOT)

    assert result.returncode == 0, result.stderr
    assert "PASS" in result.stdout


def test_validator_rejects_a_tracked_raw_record(tmp_path: Path) -> None:
    """Allowing a real raw Markdown record would expose a research corpus."""
    repo = tmp_path / "repo"
    (repo / "raw" / "paper").mkdir(parents=True)
    (repo / "raw" / "paper" / "captured-paper.md").write_text(
        "---\ntitle: Captured paper\n---\nPrivate evidence\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)

    result = run_validator(repo)

    assert result.returncode == 1
    assert "raw/paper/captured-paper.md" in result.stderr


def test_validator_rejects_a_tracked_sensitive_identifier(tmp_path: Path) -> None:
    """Missing secret detection would permit credentials to be published."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "settings.py").write_text(
        'LINER_API_KEY = "live' + '-secret-value"\n', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)

    result = run_validator(repo)

    assert result.returncode == 1
    assert "possible credential" in result.stderr
