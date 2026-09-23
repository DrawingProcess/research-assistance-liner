#!/usr/bin/env python3
"""Backfill v2 hub sections from existing raw/paper records. No Liner calls."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backfill_hubs import main

if __name__ == "__main__":
    main()
