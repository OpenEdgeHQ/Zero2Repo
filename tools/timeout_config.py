#!/usr/bin/env python3
"""Stall-watchdog configuration for subprocess monitoring.

No per-stage wall-clock budgets — only ``stall_window`` (silence threshold) and
``max_stall_retries`` (self-heal attempts after a stall kill) are resolved here.
"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_STALL_WINDOW = 900
MIN_STALL_WINDOW = 600
DEFAULT_MAX_STALL_RETRIES = 1
DEFAULT_MAX_API_ERROR_RETRIES = 1


def _positive_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _non_negative_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _runner_timeouts(runner: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(runner, dict):
        return {}
    timeouts = runner.get("timeouts")
    if not isinstance(timeouts, dict):
        return {}
    return timeouts


def resolve_stall_window(runner: dict[str, Any] | None = None) -> int:
    """Resolve stall window seconds: env > manifest.runner.timeouts > default.

    ``MILESTONE_TEST_RUN_TIMEOUT`` is kept as a backward-compatible alias for
    ``PIPELINE_STALL_WINDOW``.
    """
    for env_key in ("PIPELINE_STALL_WINDOW", "MILESTONE_TEST_RUN_TIMEOUT"):
        raw = os.environ.get(env_key)
        if raw is not None and raw.strip():
            return int(raw.strip())

    manifest_val = _runner_timeouts(runner).get("stall_window")
    if manifest_val is not None:
        parsed = _positive_int(manifest_val, "runner.timeouts.stall_window")
        assert parsed is not None
        return parsed

    return DEFAULT_STALL_WINDOW


def resolve_max_stall_retries(runner: dict[str, Any] | None = None) -> int:
    """Resolve self-heal retries after a stall kill: env > manifest > default."""
    raw = os.environ.get("PIPELINE_MAX_STALL_RETRIES")
    if raw is not None and raw.strip():
        return int(raw.strip())

    manifest_val = _runner_timeouts(runner).get("max_stall_retries")
    if manifest_val is not None:
        parsed = _non_negative_int(manifest_val, "runner.timeouts.max_stall_retries")
        assert parsed is not None
        return parsed

    return DEFAULT_MAX_STALL_RETRIES


def resolve_max_api_error_retries(runner: dict[str, Any] | None = None) -> int:
    """Resolve self-heal retries after a retryable API error: env > manifest > default."""
    raw = os.environ.get("PIPELINE_MAX_API_ERROR_RETRIES")
    if raw is not None and raw.strip():
        return int(raw.strip())

    manifest_val = _runner_timeouts(runner).get("max_api_error_retries")
    if manifest_val is not None:
        parsed = _non_negative_int(manifest_val, "runner.timeouts.max_api_error_retries")
        assert parsed is not None
        return parsed

    return DEFAULT_MAX_API_ERROR_RETRIES


def validate_runner_timeouts(runner: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (rule, message) pairs for invalid runner.timeouts entries."""
    errors: list[tuple[str, str]] = []
    timeouts = runner.get("timeouts")
    if timeouts is None:
        return errors
    if not isinstance(timeouts, dict):
        return [("invalid-field", "runner.timeouts must be a JSON object")]

    allowed = frozenset({"stall_window", "max_stall_retries", "max_api_error_retries"})
    for key, value in timeouts.items():
        if key not in allowed:
            errors.append(("unknown-timeout-key", f"runner.timeouts.{key} is not allowed"))
            continue
        if key == "stall_window":
            try:
                parsed = _positive_int(value, "runner.timeouts.stall_window")
            except ValueError as exc:
                errors.append(("invalid-field", str(exc)))
                continue
            if parsed is not None and parsed < MIN_STALL_WINDOW:
                errors.append((
                    "stall-window-too-small",
                    f"runner.timeouts.stall_window must be >= {MIN_STALL_WINDOW}",
                ))
        elif key == "max_stall_retries":
            try:
                _non_negative_int(value, "runner.timeouts.max_stall_retries")
            except ValueError as exc:
                errors.append(("invalid-field", str(exc)))
        elif key == "max_api_error_retries":
            try:
                _non_negative_int(value, "runner.timeouts.max_api_error_retries")
            except ValueError as exc:
                errors.append(("invalid-field", str(exc)))
    return errors
