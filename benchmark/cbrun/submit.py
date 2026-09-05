"""Explicit submit signal for cbrun.

The agent submits by writing a one-line file at a harness path outside
``/app``. CLI exit 0 is not a submission.
"""

from __future__ import annotations

__all__ = [
    "CONTAINER_SUBMIT_PATH",
    "SUBMIT_TOKEN",
    "NO_SUBMIT_ERROR",
    "is_valid_submit",
]

CONTAINER_SUBMIT_PATH = "/logs/agent/submit"
SUBMIT_TOKEN = "CODINGBENCH_SUBMIT"
NO_SUBMIT_ERROR = f"no submit file at {CONTAINER_SUBMIT_PATH}"


def is_valid_submit(text: str | None) -> bool:
    """True when *text* is exactly the submit token (blank lines ignored)."""
    if text is None:
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines == [SUBMIT_TOKEN]
