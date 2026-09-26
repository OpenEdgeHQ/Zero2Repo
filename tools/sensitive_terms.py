#!/usr/bin/env python3
"""Identity-leakage types and verdict parsing for semantic sensitive-term gates.

The blacklist in ``source/manifest.json`` is produced at Init; this module provides
structured types and JSON parsing for the Claude semantic leakage judge. Substring
matching is intentionally NOT used for leakage decisions.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IdentityLeakFinding:
    term: str
    path: str
    quote: str
    reason: str


def parse_leak_verdict(data: dict[str, Any] | None) -> tuple[bool, list[IdentityLeakFinding]]:
    """Parse ``identity_leak_verdict.json`` from the semantic judge."""
    if not isinstance(data, dict):
        return False, []
    leaked = bool(data.get("leaked"))
    raw_findings = data.get("findings")
    if not isinstance(raw_findings, list):
        return leaked, []
    findings: list[IdentityLeakFinding] = []
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        path = str(item.get("path") or "").strip()
        quote = str(item.get("quote") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not term:
            continue
        findings.append(IdentityLeakFinding(term=term, path=path, quote=quote, reason=reason))
    if findings:
        leaked = True
    return leaked, findings


def load_leak_verdict(path: Path) -> tuple[bool, list[IdentityLeakFinding], str | None]:
    if not path.is_file():
        return False, [], f"Missing {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [], f"Invalid JSON in {path}: {exc}"
    leaked, findings = parse_leak_verdict(data)
    return leaked, findings, None


def findings_to_violation_dicts(findings: list[IdentityLeakFinding]) -> list[dict]:
    """Legacy ``validate_output``-shaped dicts for warn-only call sites."""
    counts: Counter[tuple[str, str]] = Counter()
    for finding in findings:
        counts[(finding.term, finding.path)] += 1
    return [
        {"term": term, "occurrences": count, "path": path}
        for (term, path), count in sorted(counts.items())
    ]


def validate_output(text: str, blacklist: list[str]) -> list[dict]:
    """Deprecated substring matcher — do not use for leakage gates.

    Raises ``RuntimeError`` to prevent accidental reintroduction of deterministic
    substring matching. Call ``identity_leak_judge.judge_identity_leakage`` instead.
    """
    raise RuntimeError(
        "validate_output() substring matching is removed; use judge_identity_leakage() "
        "for semantic identity-leak checks.",
    )
