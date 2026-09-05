"""OpenRouter live pricing sync (mocked HTTP + optional live checks)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from calllmcost import (
    dump_pricing_table,
    fetch_pricing_table_from_openrouter,
    load_pricing_table,
    model_pricing_from_openrouter_record,
)


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_model_pricing_cache_write_fallback_matches_input() -> None:
    row = {
        "id": "deepseek/deepseek-v3.2",
        "pricing": {
            "prompt": "0.000000252",
            "completion": "0.000000378",
            "input_cache_read": "0.0000000252",
        },
    }
    mp = model_pricing_from_openrouter_record("deepseek/deepseek-v3.2", row)
    assert mp.cache_write_per_m == pytest.approx(mp.input_per_m)
    assert mp.cache_read_per_m == pytest.approx(0.0252)


def test_fetch_pricing_table_from_openrouter_mocked() -> None:
    sample = {
        "data": [
            {
                "id": "vendor/test-model",
                "pricing": {
                    "prompt": "0.000002",
                    "completion": "0.000004",
                    "input_cache_read": "0.0000005",
                    "input_cache_write": "0.000003",
                },
            }
        ]
    }

    def fake_urlopen(req, timeout=0):  # noqa: ARG001
        return _FakeResp(json.dumps(sample).encode("utf-8"))

    with patch("calllmcost.openrouter_sync.urlopen", fake_urlopen):
        table = fetch_pricing_table_from_openrouter(
            ["vendor/test-model"],
            base_url="https://openrouter.ai/api/v1",
        )
    mp = table.get("vendor/test-model")
    assert mp.input_per_m == pytest.approx(2.0)
    assert mp.output_per_m == pytest.approx(4.0)
    assert mp.cache_read_per_m == pytest.approx(0.5)
    assert mp.cache_write_per_m == pytest.approx(3.0)


def test_dump_and_load_roundtrip(tmp_path) -> None:
    sample = {
        "data": [
            {
                "id": "vendor/test-model",
                "pricing": {"prompt": "0.000001", "completion": "0.000002"},
            }
        ]
    }

    def fake_urlopen(req, timeout=0):  # noqa: ARG001
        return _FakeResp(json.dumps(sample).encode("utf-8"))

    with patch("calllmcost.openrouter_sync.urlopen", fake_urlopen):
        table = fetch_pricing_table_from_openrouter(["vendor/test-model"])
    path = tmp_path / "live.json"
    dump_pricing_table(table, path, notes="test snapshot")
    loaded = load_pricing_table(path)
    assert loaded.get("vendor/test-model").input_per_m == pytest.approx(1.0)


def test_live_openrouter_opus_prices_near_snapshot() -> None:
    """Set OPENROUTER_LIVE_TEST=1 to run (network + live catalog)."""

    import os

    if os.environ.get("OPENROUTER_LIVE_TEST", "").strip() != "1":
        pytest.skip("set OPENROUTER_LIVE_TEST=1 to enable network integration test")

    from calllmcost.openrouter_sync import fetch_openrouter_models_payload

    doc = fetch_openrouter_models_payload(timeout_sec=60.0)
    by_id = {m["id"]: m for m in doc["data"] if isinstance(m, dict) and "id" in m}
    row = by_id.get("anthropic/claude-opus-4.6")
    if row is None:
        pytest.skip("anthropic/claude-opus-4.6 not in OpenRouter catalog")
    mp = model_pricing_from_openrouter_record("anthropic/claude-opus-4.6", row)
    assert mp.input_per_m == pytest.approx(5.0, rel=0.05)
    assert mp.output_per_m == pytest.approx(25.0, rel=0.05)
