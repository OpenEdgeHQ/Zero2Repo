# feature: F08
"""F08 helpers. Names here are F08-only.

Sealed F05 already exports ``_emit_arith``, which prints ``T:`` with no
leading newline (and ``S:`` for a non-integer). Option and standalone
prompts write without a trailing newline; ``labeled_stdout_field``
requires ``T:`` as a line prefix, so this module prints a leading
newline before the arithmetic mark.
"""

from __future__ import annotations


def _name_derived_prompt_tokens(this_rest: str, other_rest: str) -> tuple[str, ...]:
    """Alphanumeric runs in *this_rest* that do not appear in *other_rest*.

    Two name-derived prompts share leftover punctuation (colon, delivery
    label). What they do not share is the name-derived prompt text.
    """
    tokens: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        token = "".join(buf)
        buf.clear()
        if token not in other_rest:
            tokens.append(token)

    for ch in this_rest:
        if ch.isalnum():
            buf.append(ch)
        else:
            flush()
    flush()
    return tuple(tokens)


def _print_prompt_arith(value: object) -> None:
    # Leading newline so a prompt that wrote without one cannot glue T: onto
    # the prompt line (labeled_stdout_field requires a line prefix).
    print(f"\nT:{value * 3 + 7}", flush=True)  # type: ignore[operator]
