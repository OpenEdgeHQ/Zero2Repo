"""Tests for Harbor cost enrichment CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from coding_bench_harbor.cost_report import enrich_trial_result_json  # noqa: E402


def test_enrich_trial_result_json_sets_cost(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial"
    agent_dir = trial_dir / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "opencode.txt").write_text(
        json.dumps({
            "type": "result",
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 100,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            "total_cost_usd": 0.05,
        }) + "\n",
        encoding="utf-8",
    )
    (trial_dir / "result.json").write_text(
        json.dumps({
            "agent_result": {
                "n_input_tokens": 1000,
                "n_output_tokens": 100,
                "cost_usd": None,
            },
            "config": {"agent": {"model_name": "anthropic/claude-sonnet-4.6"}},
        }),
        encoding="utf-8",
    )

    enriched = enrich_trial_result_json(trial_dir, backend="opencode")
    assert enriched.get("cost_usd") is not None
    assert enriched["cost_usd"] > 0

    saved = json.loads((trial_dir / "result.json").read_text(encoding="utf-8"))
    assert saved["agent_result"]["cost_usd"] == enriched["cost_usd"]
