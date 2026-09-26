"""Token usage is recorded for every agent CLI, including killed runs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun.agent_spec import AgentSpec, builtin_spec  # noqa: E402
from cbrun.results import TrialResult, write_summary  # noqa: E402
from cbrun.usage import collect_trial_usage  # noqa: E402


def _jsonl(*events: dict) -> str:
    return "".join(json.dumps(e) + "\n" for e in events)


def _trial(tmp_path: Path, agent_log: str = "", agent_fix_log: str | None = None) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "agent.log").write_text(agent_log, encoding="utf-8")
    if agent_fix_log is not None:
        (tmp_path / "agent_fix.log").write_text(agent_fix_log, encoding="utf-8")
    return tmp_path


CURSOR_RESULT = {
    "type": "result",
    "subtype": "success",
    "result": "ok",
    "usage": {"inputTokens": 12217, "outputTokens": 28, "cacheReadTokens": 3840, "cacheWriteTokens": 0},
}


def test_cursor_stream_json_result(tmp_path: Path) -> None:
    trial = _trial(
        tmp_path,
        agent_log="Connection lost, reconnecting...\n"
        + _jsonl({"type": "system", "subtype": "init"}, {"type": "assistant", "message": {}}, CURSOR_RESULT),
    )
    usage = collect_trial_usage(trial)
    assert usage["complete"] is True
    assert usage["sources"] == ["cursor_result"]
    assert (usage["input_tokens"], usage["cache_read_tokens"], usage["output_tokens"]) == (12217, 3840, 28)
    assert usage["total_tokens"] == 12217 + 3840 + 28


def test_cursor_text_or_killed_run_is_flagged_incomplete(tmp_path: Path) -> None:
    usage = collect_trial_usage(_trial(tmp_path / "text", agent_log="Tomlparse is done.\n"))
    assert usage["complete"] is False
    assert usage["missing"] == ["agent.log"]

    killed = _jsonl({"type": "system", "subtype": "init"}, {"type": "assistant", "message": {}})
    usage = collect_trial_usage(_trial(tmp_path / "killed", agent_log=killed))
    assert usage["complete"] is False
    assert usage["total_tokens"] == 0


def _claude_msg(msg_id: str, inp: int, read: int, write: int, out: int) -> dict:
    return {
        "type": "assistant",
        "message": {
            "id": msg_id,
            "usage": {
                "input_tokens": inp,
                "cache_read_input_tokens": read,
                "cache_creation_input_tokens": write,
                "output_tokens": out,
            },
        },
    }


def test_claude_result_prefers_model_usage(tmp_path: Path) -> None:
    result = {
        "type": "result",
        "usage": {"input_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 1},
        "modelUsage": {
            "claude-opus": {"inputTokens": 100, "outputTokens": 50, "cacheReadInputTokens": 1000, "cacheCreationInputTokens": 200},
            "claude-haiku": {"inputTokens": 10, "outputTokens": 5, "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0},
        },
        "total_cost_usd": 1.25,
    }
    usage = collect_trial_usage(_trial(tmp_path, agent_log=_jsonl(_claude_msg("m1", 1, 1, 1, 1), result)))
    assert usage["complete"] is True
    assert usage["sources"] == ["claude_result"]
    assert (usage["input_tokens"], usage["cache_read_tokens"], usage["cache_write_tokens"], usage["output_tokens"]) == (
        110,
        1000,
        200,
        55,
    )
    assert usage["harness_cost_usd"] == 1.25
    assert set(usage["by_model"]) == {"claude-opus", "claude-haiku"}


def test_claude_killed_run_sums_assistant_messages_once(tmp_path: Path) -> None:
    log = _jsonl(
        _claude_msg("m1", 10, 100, 5, 7),
        _claude_msg("m1", 10, 100, 5, 7),
        _claude_msg("m2", 3, 200, 0, 9),
    )
    usage = collect_trial_usage(_trial(tmp_path, agent_log=log))
    assert usage["complete"] is True
    assert usage["sources"] == ["claude_assistant_messages"]
    assert (usage["input_tokens"], usage["cache_read_tokens"], usage["output_tokens"]) == (13, 300, 16)


def test_codex_turn_completed_splits_cached_input(tmp_path: Path) -> None:
    log = _jsonl(
        {"type": "thread.started"},
        {"type": "turn.completed", "usage": {"input_tokens": 5000, "cached_input_tokens": 4000, "output_tokens": 300, "reasoning_output_tokens": 120}},
    )
    usage = collect_trial_usage(_trial(tmp_path, agent_log=log))
    assert usage["complete"] is True
    assert (usage["input_tokens"], usage["cache_read_tokens"], usage["output_tokens"]) == (1000, 4000, 300)
    assert usage["reasoning_tokens"] == 120


def test_codex_killed_run_recovers_from_session_files(tmp_path: Path) -> None:
    trial = _trial(tmp_path, agent_log=_jsonl({"type": "thread.started"}, {"type": "item.completed"}))
    sessions = trial / "container_logs" / "usage" / "0" / "2026" / "09" / "26"
    sessions.mkdir(parents=True)

    def token_count(inp: int, cached: int, out: int) -> dict:
        return {
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": inp, "cached_input_tokens": cached, "output_tokens": out}}},
        }

    (sessions / "rollout-a.jsonl").write_text(_jsonl(token_count(100, 50, 10), token_count(900, 600, 80)), encoding="utf-8")
    (sessions / "rollout-b.jsonl").write_text(_jsonl(token_count(200, 100, 20)), encoding="utf-8")
    usage = collect_trial_usage(trial)
    assert usage["complete"] is True
    assert usage["sources"] == ["codex_session"]
    assert (usage["input_tokens"], usage["cache_read_tokens"], usage["output_tokens"]) == (400, 700, 100)


def test_opencode_step_finish_is_summed(tmp_path: Path) -> None:
    def step(inp: int, out: int, read: int, cost: float) -> dict:
        return {"type": "step_finish", "part": {"tokens": {"input": inp, "output": out, "reasoning": 0, "cache": {"read": read, "write": 0}}, "cost": cost}}

    usage = collect_trial_usage(_trial(tmp_path, agent_log=_jsonl(step(10, 2, 100, 0.01), step(20, 3, 200, 0.02))))
    assert usage["complete"] is True
    assert (usage["input_tokens"], usage["cache_read_tokens"], usage["output_tokens"]) == (30, 300, 5)
    assert usage["harness_cost_usd"] == 0.03


def test_denylist_fix_log_is_added(tmp_path: Path) -> None:
    trial = _trial(tmp_path, agent_log=_jsonl(CURSOR_RESULT), agent_fix_log=_jsonl(CURSOR_RESULT))
    usage = collect_trial_usage(trial)
    assert usage["complete"] is True
    assert usage["input_tokens"] == 2 * 12217


def test_summary_aggregates_usage_and_counts_incomplete(tmp_path: Path) -> None:
    a = TrialResult(case_id="c1", backend="cursor", model="m", reward=1.0, terminal_status="completed")
    a.token_usage = {"input_tokens": 5, "output_tokens": 1, "total_tokens": 6, "complete": True}
    b = TrialResult(case_id="c2", backend="cursor", model="m", reward=0.0, terminal_status="timeout")
    b.token_usage = {"input_tokens": 0, "total_tokens": 0, "complete": False, "missing": ["agent.log"]}
    summary = json.loads(write_summary([a, b], tmp_path).read_text(encoding="utf-8"))
    agg = summary["aggregate"]["token_usage"]
    assert agg["input_tokens"] == 5
    assert agg["total_tokens"] == 6
    assert agg["incomplete_trials"] == 1
    assert summary["trials"][0]["token_usage"]["complete"] is True


def test_session_paths_are_declared_and_loadable() -> None:
    assert builtin_spec("codex").usage_paths == ("$CODEX_HOME/sessions",)
    assert builtin_spec("claude-code").usage_paths
    spec = AgentSpec.from_dict({"name": "mine", "command": "run", "usage_paths": ["$HOME/.mine/sessions"]})
    assert spec.usage_paths == ("$HOME/.mine/sessions",)
    assert "usage_paths" not in builtin_spec("cursor").to_dict()
