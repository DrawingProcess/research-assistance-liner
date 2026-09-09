"""Test-wide safety net: every wiki write in this project resolves paths
relative to the current working directory (index.md, log.md, entities/,
concepts/, comparisons/, raw/paper/). A test that forgets to chdir would
therefore append to the *real* wiki in the repo root — which actually
happened once while adding the raw/paper ingest-logging fix (Finding M2).

Chdir every test into its own tmp_path by default. Tests that chdir
themselves via monkeypatch.chdir are unaffected (they just move again).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
