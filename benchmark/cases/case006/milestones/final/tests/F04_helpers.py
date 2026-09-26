# feature: F04
"""F04 helpers. Names here are F04-only.

Sealed F10 already exports ``_cmd``, ``_dispatch``, ``_greeting``,
``_stdout``, and ``_word``. Sealed F13 already exports ``_runtime_int``.
Those modules are not on disk, so F04 scaffolding uses new names instead
of a predecessor import.
"""

from __future__ import annotations

import uuid
from typing import Any

from optlyn import command

from _harness import invoke
from _helpers import (
    _status_and_streams,
    require_usage_class,
    require_usage_names_argument,
)

_ARG_PROG = "app"


def _arg_ident() -> str:
    return "k" + uuid.uuid4().hex[:8]


def _arg_hi() -> str:
    return f"GREET:{uuid.uuid4().hex}:"


def _arg_int() -> int:
    return 14 + uuid.uuid4().int % 80


def _env_name() -> str:
    return f"E{_arg_ident().upper()}"


def _arg_run(cli: Any, args: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("prog_name", _ARG_PROG)
    return invoke(cli, args, **kwargs)


def _arg_leaf(callback: Any, *param_decs: Any, **command_kwargs: Any) -> Any:
    decorated = callback
    for deco in reversed(param_decs):
        decorated = deco(decorated)
    return command(**command_kwargs)(decorated)


def _arg_stdout(result: Any) -> str:
    text = result.stdout_text
    if text is None:
        raise RuntimeError("stdout is None; cannot observe")
    return text


def _line_after(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError(f"missing {prefix!r} in {text!r}")


def _emit_bound(value: object, slot: str = "") -> None:
    """Print scalar / sequence / absent marks. A string is never listed."""
    prefix = f"{slot}:" if slot else ""
    if isinstance(value, str):
        print(f"{prefix}N:SCALAR", flush=True)
        print(f"{prefix}V:{value}", flush=True)
        return
    if isinstance(value, (list, tuple)):
        print(f"{prefix}N:{len(value)}", flush=True)
        for i, item in enumerate(value):
            print(f"{prefix}V:{i}:{item}", flush=True)
        return
    if isinstance(value, int) and not isinstance(value, bool):
        print(f"{prefix}T:{value * 3 + 7}", flush=True)
        return
    print(f"{prefix}N:ABSENT", flush=True)


def _kind(result: Any, slot: str = "") -> str:
    prefix = f"{slot}:N:" if slot else "N:"
    return _line_after(_arg_stdout(result), prefix)


def _scalar(result: Any, slot: str = "") -> str:
    kind = _kind(result, slot)
    assert kind == "SCALAR", (
        f"expected a scalar mark, got {kind!r}; stdout={_arg_stdout(result)!r}"
    )
    prefix = f"{slot}:V:" if slot else "V:"
    return _line_after(_arg_stdout(result), prefix)


def _seq_member(result: Any, index: int, slot: str = "") -> str:
    prefix = f"{slot}:V:{index}:" if slot else f"V:{index}:"
    return _line_after(_arg_stdout(result), prefix)


def _is_sequence_kind(kind: str) -> bool:
    return kind.isdigit()


def _enc(result: Any, slot: str = "") -> str:
    """Stable encoding of the bound value for pairwise distinguishability."""
    text = _arg_stdout(result)
    prefix = f"{slot}:" if slot else ""
    kind_line = None
    value_lines: list[str] = []
    arith = None
    for line in text.splitlines():
        if line.startswith(f"{prefix}N:"):
            kind_line = line[len(f"{prefix}N:") :]
        elif line.startswith(f"{prefix}T:"):
            arith = line[len(f"{prefix}T:") :]
        elif line.startswith(f"{prefix}V:"):
            value_lines.append(line[len(f"{prefix}V:") :])
    if arith is not None:
        return f"INT:{arith}"
    if kind_line is None:
        raise AssertionError(
            f"no bound-value mark with prefix {prefix!r}; stdout={text!r}"
        )
    return f"K:{kind_line}|{','.join(value_lines)}"


def require_omitted_required_names_argument(
    result: Any, greeting: str, dest: str, *sibling_dests: str
) -> None:
    """Omitted required argument: usage class whose stderr names that dest.

    Keeps the usage-class carrier (exit 2, greeting absent, nonempty
    stderr) and also requires *dest* on stderr. Dest case is not pinned
    (matching is casefolded). Sentence wording is not pinned. Sibling
    dests that were not omitted must not appear on the same report
    (also casefolded). A failure to read the streams raises — it is
    not treated as an unnamed dest.
    """
    if not dest:
        raise ValueError("dest must be a non-empty string")
    folded_dest = dest.casefold()
    for sibling in sibling_dests:
        if not sibling:
            raise ValueError("sibling dest must be a non-empty string")
        if sibling.casefold() == folded_dest:
            raise ValueError("sibling dest must differ from dest")
    require_usage_class(result, greeting)
    require_usage_names_argument(result, greeting, dest)
    if not sibling_dests:
        return
    _, _, stderr = _status_and_streams(result)
    folded_stderr = stderr.casefold()
    for sibling in sibling_dests:
        assert sibling.casefold() not in folded_stderr, (
            f"omitted-required report for {dest!r} named sibling "
            f"{sibling!r}; stderr={stderr!r}"
        )


assert_omitted_required_names_argument = require_omitted_required_names_argument
