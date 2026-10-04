"""Usage collection, including Cursor lines written during the solve."""

from __future__ import annotations

import json
from pathlib import Path

from cbrun.agent_spec import resolve_agent
from cbrun.pricing import lookup_model, trial_cost
from cbrun.usage import collect_trial_usage


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_cursor_hook_lines_sum_when_the_result_line_is_missing(tmp_path: Path):
    _write(tmp_path / "agent.log", '{"type":"thinking","text":"still going"}\n')
    rows = [
        {"generation_id": "g1", "input_tokens": 10, "output_tokens": 4, "cache_read_tokens": 100, "cache_write_tokens": 0},
        {"generation_id": "g1", "input_tokens": 12, "output_tokens": 5, "cache_read_tokens": 100, "cache_write_tokens": 1},
        {"generation_id": "g2", "input_tokens": 8, "output_tokens": 3, "cache_read_tokens": 40, "cache_write_tokens": 2},
        {"input_tokens": 1, "output_tokens": 1, "cache_read_tokens": 0, "cache_write_tokens": 0},
    ]
    _write(
        tmp_path / "container_logs" / "cursor_usage.jsonl",
        "".join(json.dumps(row) + "\n" for row in rows),
    )
    usage = collect_trial_usage(tmp_path)
    assert usage["input_tokens"] == 21
    assert usage["output_tokens"] == 9
    assert usage["cache_read_tokens"] == 140
    assert usage["cache_write_tokens"] == 3
    assert usage["total_tokens"] == 173
    assert usage["sources"] == ["cursor_response_hooks"]
    assert usage["complete"] is True
    assert usage["missing"] == []


def test_cursor_result_is_kept_when_hook_lines_also_exist(tmp_path: Path):
    _write(
        tmp_path / "agent.log",
        json.dumps(
            {
                "type": "result",
                "usage": {
                    "inputTokens": 100,
                    "outputTokens": 20,
                    "cacheReadTokens": 400,
                    "cacheWriteTokens": 0,
                },
            }
        )
        + "\n",
    )
    _write(
        tmp_path / "container_logs" / "cursor_usage.jsonl",
        json.dumps({"generation_id": "g1", "input_tokens": 1, "output_tokens": 1}) + "\n",
    )
    usage = collect_trial_usage(tmp_path)
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 20
    assert usage["cache_read_tokens"] == 400
    assert usage["sources"] == ["cursor_result"]
    assert usage["complete"] is True


def test_cursor_setup_writes_turn_ended_usage():
    invocation = resolve_agent(backend="cursor", model="grok-4.7")
    script = invocation.setup_script or ""
    assert 'case"turnEnded"' in script
    assert "/logs/agent/cursor_usage.jsonl" in script
    assert "/app" not in script


def test_openhands_jsonl_sums_completed_calls(tmp_path: Path):
    _write(tmp_path / "agent.log", "no usage here\n")
    rows = [
        {
            "model": "openai/gpt-6-sol",
            "prompt_tokens": 100,
            "completion_tokens": 7,
            "cache_read_tokens": 40,
            "cache_write_tokens": 10,
            "reasoning_tokens": 3,
            "response_id": "r1",
        },
        {
            "model": "openai/gpt-6-sol",
            "prompt_tokens": 20,
            "completion_tokens": 4,
            "cache_read_tokens": 5,
            "cache_write_tokens": 0,
            "reasoning_tokens": 1,
            "response_id": "r1",
        },
        {
            "model": "openai/gpt-6-sol",
            "prompt_tokens": 30,
            "completion_tokens": 2,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "response_id": "",
        },
    ]
    _write(
        tmp_path / "container_logs" / "openhands_usage.jsonl",
        "".join(json.dumps(row) + "\n" for row in rows),
    )
    usage = collect_trial_usage(tmp_path)
    # r1 keeps the later line (15 uncached + 5 cache + 4 output); the blank id adds 30 + 2.
    assert usage["input_tokens"] == 45
    assert usage["cache_read_tokens"] == 5
    assert usage["cache_write_tokens"] == 0
    assert usage["output_tokens"] == 6
    assert usage["reasoning_tokens"] == 1
    assert usage["sources"] == ["openhands_usage_log"]
    assert usage["complete"] is True
    assert usage["missing"] == []


def test_openhands_state_snapshot_fills_in_when_the_log_is_smaller(tmp_path: Path):
    _write(tmp_path / "agent.log", "killed\n")
    _write(
        tmp_path / "container_logs" / "openhands_usage.jsonl",
        json.dumps(
            {
                "prompt_tokens": 10,
                "completion_tokens": 1,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "response_id": "early",
            }
        )
        + "\n",
    )
    state = {
        "stats": {
            "usage_to_metrics": {
                "agent": {
                    "accumulated_token_usage": {
                        "prompt_tokens": 80,
                        "completion_tokens": 20,
                        "cache_read_tokens": 30,
                        "cache_write_tokens": 0,
                        "reasoning_tokens": 4,
                    }
                }
            }
        }
    }
    _write(
        tmp_path / "container_logs" / "usage" / "0" / "conversations" / "abc" / "base_state.json",
        json.dumps(state),
    )
    usage = collect_trial_usage(tmp_path)
    assert usage["input_tokens"] == 50
    assert usage["cache_read_tokens"] == 30
    assert usage["output_tokens"] == 20
    assert usage["sources"] == ["openhands_base_state"]


def test_openhands_setup_appends_each_completion():
    invocation = resolve_agent(
        backend="openhands",
        model="openai/gpt-6-sol",
        environ={"LLM_API_KEY": "test-key", "LLM_BASE_URL": "https://example.invalid/v1"},
    )
    script = invocation.setup_script or ""
    assert "self.token_usages.append(usage)" in script
    assert "/logs/agent/openhands_usage.jsonl" in script
    assert "/app" not in script


def test_prices_cover_sol_deepseek_and_kimi():
    sol_id, sol = lookup_model("openai/gpt-6-sol")
    assert sol_id == "openai/gpt-6-sol"
    assert sol["input_per_m"] == 2.0
    assert sol["cache_read_per_m"] == 0.2
    assert sol["output_per_m"] == 10.0
    assert lookup_model("deepseek-v4-pro-0813")[1]["currency"] == "CNY"
    buckets = {
        "input_tokens": 1_000_000,
        "cache_read_tokens": 1_000_000,
        "cache_write_tokens": 0,
        "output_tokens": 1_000_000,
    }
    kimi = trial_cost(buckets, "openai/kimi-k3")
    assert kimi["cost_usd"] is None
    assert kimi["cost_cny"] == 122.0
    assert kimi["unpriced_models"] == []
    deepseek = trial_cost(buckets, "openai/deepseek-v4-pro-0813")
    assert deepseek["cost_cny"] == 37.0
