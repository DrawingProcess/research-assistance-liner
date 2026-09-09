#!/usr/bin/env python3
"""Reject tracked corpus, runtime state, and likely credentials in this template."""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path, PurePosixPath


PLACEHOLDER_NAMES = {".gitkeep"}
FORBIDDEN_PATH_PARTS = {".claude", ".ua", "test-liner-api", "docs/dev-log"}
CANONICAL_DIRECTORIES = {"entities", "concepts", "comparisons", "queries"}
RAW_PREFIX = PurePosixPath("raw")
RUNTIME_FILENAMES = {"backlog.json", "backlog_watcher_state.json"}
SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(?:LINER_API_KEY|DISCORD_BOT_TOKEN|DISCORD_WEBHOOK)\s*[=:]\s*['\"]?(?!<|replace-|your-|example)[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"\b(?:ghp|github_pat|sk)-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)discord(?:_channel)?_id\s*[=:]\s*['\"]?\d{12,}"),
)


def tracked_paths(repo: str) -> list[PurePosixPath]:
    completed = subprocess.run(
        ["git", "-C", repo, "ls-files", "-z"], capture_output=True, check=True
    )
    return [PurePosixPath(item.decode()) for item in completed.stdout.split(b"\0") if item]


def path_violations(path: PurePosixPath) -> list[str]:
    parts = set(path.parts)
    if parts & FORBIDDEN_PATH_PARTS or str(path).startswith("docs/dev-log/"):
        return [f"forbidden personal/runtime path: {path}"]
    if path.name in RUNTIME_FILENAMES:
        return [f"runtime state must not be tracked: {path}"]
    if path.parts and path.parts[0] in CANONICAL_DIRECTORIES and path.name not in PLACEHOLDER_NAMES:
        return [f"canonical corpus file must not be tracked: {path}"]
    if path == RAW_PREFIX or RAW_PREFIX in path.parents:
        if path.name not in PLACEHOLDER_NAMES:
            return [f"raw evidence file must not be tracked: {path}"]
    if path.parts and path.parts[0] == "research-gap" and path.name not in PLACEHOLDER_NAMES:
        return [f"research-gap runtime state must not be tracked: {path}"]
    return []


def content_violations(repo: str, path: PurePosixPath) -> list[str]:
    if path.suffix not in {".py", ".md", ".toml", ".json", ".yml", ".yaml", ".sh", ".env", ""}:
        return []
    try:
        text = (Path(repo) / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return [f"possible credential or personal identifier in {path}" for pattern in SENSITIVE_PATTERNS if pattern.search(text)]


def validate(repo: str) -> list[str]:
    violations: list[str] = []
    for path in tracked_paths(repo):
        violations.extend(path_violations(path))
        violations.extend(content_violations(repo, path))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Git repository to validate")
    args = parser.parse_args()
    violations = validate(args.repo)
    if violations:
        print("Public-template validation failed:", file=__import__("sys").stderr)
        print(*[f"- {item}" for item in violations], sep="\n", file=__import__("sys").stderr)
        return 1
    print("PASS: tracked files contain only template-safe paths and no detected credentials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
