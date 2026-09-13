"""Self-contained leakage scan for source-identity terms.

Vendored into the benchmark package so the public harness does not depend on
internal authoring tools. The optional blacklist lives in each case's
``source/manifest.json`` under ``sensitive_terms``.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class LeakageHit:
    term: str
    occurrences: int


def scan_leakage(text: str, blacklist: list[str]) -> list[LeakageHit]:
    """Match identities at identifier boundaries, not inside unrelated words.

    Qualified names and URLs still match verbatim; punctuation is preserved.
    Case authors must list identifiers they intend to prohibit explicitly.
    """
    hits: list[LeakageHit] = []
    for term in blacklist:
        if not term:
            continue
        count = len(re.findall(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.IGNORECASE))
        if count:
            hits.append(LeakageHit(term=term, occurrences=count))
    return hits
