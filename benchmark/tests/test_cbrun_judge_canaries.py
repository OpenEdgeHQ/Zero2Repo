"""Unit tests for isolated-judge canary helpers (no live docker)."""

from __future__ import annotations

import sys
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun.judge import JudgeOutcome  # noqa: E402
from cbrun.judge_canaries import _total  # noqa: E402


def test_total_requires_positive_parseable_count() -> None:
    assert _total(JudgeOutcome(1.0, None, 0, 1.0, {"final": {"total_count": 4}})) == 4
    assert _total(JudgeOutcome(1.0, None, 0, 1.0, {"final": {"total_count": 0}})) is None
    assert _total(JudgeOutcome(1.0, None, 0, 1.0, {"final": {}})) is None
    assert _total(JudgeOutcome(0.0, "x", 1, 1.0, {})) is None
