"""Self-contained leakage scan for source-identity terms.

Vendored into the benchmark package so the public harness does not depend on
internal authoring tools. The optional blacklist lives in each case's
``source/manifest.json`` under ``sensitive_terms``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeakageHit:
    term: str
    occurrences: int


def scan_leakage(text: str, blacklist: list[str]) -> list[LeakageHit]:
    """Return blacklisted terms found in *text* (case-insensitive substring)."""
    text_lower = text.lower()
    hits: list[LeakageHit] = []
    for term in blacklist:
        if not term:
            continue
        needle = term.lower()
        count = text_lower.count(needle)
        if count:
            hits.append(LeakageHit(term=term, occurrences=count))
    return hits
