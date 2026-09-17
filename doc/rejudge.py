#!/usr/bin/env python3
"""Thin wrapper so ``python3 doc/rejudge.py`` stays the documented entry."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))

from cbrun.rejudge import main

if __name__ == "__main__":
    raise SystemExit(main())
