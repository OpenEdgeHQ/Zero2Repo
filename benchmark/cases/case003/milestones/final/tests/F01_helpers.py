# feature: F01
"""Observation helpers for FP-01 parse failure reports.

Line-break count is how many line breaks precede the error site
(a CR/LF pair is one break). The count is not a byte offset, a
column, or a parse-step. Storage, print form, and zero- versus
one-based numbering are not scored.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from _harness import ErrorInfo, HarnessError

_INTS = re.compile(r"-?\d+")


def _presented_ints(error: ErrorInfo, covariates: Sequence[str]) -> set[int]:
    """Integers the report presents in print or in stored mark numbers.

    Uses the product's printed text and any stored mark integers. Does
    not read a stack trace (those line numbers are not the count). Does
    not prefer a field name or a line/row word. A missing report
    raises — an empty integer set is a real observation, not a stand-in
    for count zero.
    """
    if error is None:
        raise HarnessError("failure report is missing")
    if not isinstance(error, ErrorInfo):
        raise HarnessError(
            f"failure report is not ErrorInfo: {type(error).__name__}"
        )
    parts: list[str] = []
    for piece in (error.message, error.text, error.reason):
        if piece:
            parts.append(piece)
    mark = error.mark
    stored: list[int] = []
    if mark is not None:
        for value in (mark.line, mark.column, mark.position):
            if isinstance(value, int):
                stored.append(value)
    if not parts and not stored:
        raise HarnessError("failure report presents no printed text and no stored numbers")
    text = "\n".join(parts)
    for cov in covariates:
        if cov:
            text = text.replace(str(cov), "")
    found = {int(match) for match in _INTS.findall(text)}
    found.update(stored)
    return found


def require_line_break_counts(
    later_error: ErrorInfo,
    earlier_error: ErrorInfo,
    *,
    later_source: str,
    covariates: Sequence[str],
) -> None:
    """Assert later presents count one and earlier presents count zero.

    Count of *n* may appear as *n* (zero-based) or *n* + 1 (one-based).
    The later report must present count one as a number the first-line
    report does not also present; the first-line report must present
    count zero. A byte offset of ``@``, a shared column, or any leftover
    integer that merely grows, is not that count.
    """
    if not later_source:
        raise HarnessError("later-line source is missing")
    later_ints = _presented_ints(later_error, covariates)
    earlier_ints = _presented_ints(earlier_error, covariates)
    later_offset = later_source.find("@")
    if later_offset < 0:
        raise HarnessError(
            f"later-line source has no error site @: {later_source!r}"
        )
    later_unique = later_ints - earlier_ints
    later_unique.discard(later_offset)
    zero_based = 1 in later_unique and 0 in earlier_ints
    one_based = 2 in later_unique and 1 in earlier_ints
    print(
        f"later_ints={later_ints!r} earlier_ints={earlier_ints!r} "
        f"later_unique={later_unique!r} later_offset={later_offset!r} "
        f"zero_based={zero_based!r} one_based={one_based!r}",
        flush=True,
    )
    assert zero_based or one_based, (
        "later-line report must present line-break count one and "
        "first-line report must present line-break count zero "
        "(from zero as 1 vs 0, or from one as 2 vs 1); "
        f"later_ints={later_ints!r} earlier_ints={earlier_ints!r} "
        f"later_unique={later_unique!r} later_offset={later_offset!r}"
    )
