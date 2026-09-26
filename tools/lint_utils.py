#!/usr/bin/env python3
"""Generic lint helpers for artifact quality checks."""

from __future__ import annotations

import re
from pathlib import Path

# Common double UTF-8 mojibake byte patterns when read as text.
_MOJIBAKE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"[\u00c3\u00c2][\u0080-\u00bf]"),
    re.compile(r"\u00e2[\u0080-\u009f]"),
    re.compile(r"\uFFFD"),
)


def check_mojibake(file_path: Path) -> list[str]:
    """Return human-readable warnings if *file_path* likely contains mojibake."""
    path = Path(file_path)
    if not path.is_file():
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: cannot read ({exc})"]

    issues: list[str] = []
    for pattern in _MOJIBAKE_PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            snippet = text[max(0, match.start() - 20): match.end() + 20].replace("\n", " ")
            issues.append(f"{path}:{line}: possible mojibake near {snippet!r}")
            break  # one report per pattern per file
    return issues
