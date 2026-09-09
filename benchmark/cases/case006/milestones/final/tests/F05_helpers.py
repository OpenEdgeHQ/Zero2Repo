# feature: F05
"""F05 helpers. Names here are F05-only.

Sealed F10 already exports ``_cmd``, ``_dispatch``, ``_greeting``,
``_stderr``, ``_stdout``, and ``_word``. Sealed F13 already exports
``_runtime_int``. Those modules are not on disk, so F05 scaffolding uses
new names instead of a predecessor import.
"""

from __future__ import annotations

import uuid
from typing import Any

from optlyn import ParamType, command

from _harness import invoke

_TYPE_PROG = "app"


class _Tagged:
    """Author-built converted value. Identity is *via* plus *payload*."""

    def __init__(self, payload: str, via: str) -> None:
        self.payload = payload
        self.via = via


class _MarkedType(ParamType):
    name = "marked"

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def convert(self, value, param=None, ctx=None):
        if isinstance(value, _Tagged):
            return value
        return _Tagged(str(value), f"STRCONV:{self.prefix}")


def _type_ident() -> str:
    return "k" + uuid.uuid4().hex[:8]


def _type_hi() -> str:
    return f"GREET:{uuid.uuid4().hex}:"


def _type_int() -> int:
    return 14 + uuid.uuid4().int % 80


def _runtime_bounds() -> tuple[int, int]:
    lo = 12 + uuid.uuid4().int % 40
    hi = lo + 10 + uuid.uuid4().int % 15
    return lo, hi


def _date_parts() -> tuple[int, int, int, int, int, int]:
    year = 1995 + uuid.uuid4().int % 30
    month = 1 + uuid.uuid4().int % 12
    day = 1 + uuid.uuid4().int % 28
    hour = uuid.uuid4().int % 24
    minute = uuid.uuid4().int % 60
    second = uuid.uuid4().int % 60
    return year, month, day, hour, minute, second


def _type_run(cli: Any, args: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("prog_name", _TYPE_PROG)
    return invoke(cli, args, **kwargs)


def _type_leaf(callback: Any, *param_decs: Any, **command_kwargs: Any) -> Any:
    decorated = callback
    for deco in reversed(param_decs):
        decorated = deco(decorated)
    return command(**command_kwargs)(decorated)


def _type_stdout(result: Any) -> str:
    text = result.stdout_text
    if text is None:
        raise RuntimeError("stdout is None; cannot observe")
    return text


def _type_stderr(result: Any) -> str:
    text = result.stderr_text
    if text is None:
        raise RuntimeError("stderr is None; cannot observe")
    return text


def _emit_arith(value: object) -> None:
    if isinstance(value, int) and not isinstance(value, bool):
        print(f"T:{value * 3 + 7}", flush=True)
        return
    print(f"S:{value}", flush=True)


def _emit_float(value: object) -> None:
    try:
        doubled = value * 2  # type: ignore[operator]
    except TypeError:
        print(f"S:{value}", flush=True)
        return
    if isinstance(value, str):
        print(f"S:{value}", flush=True)
        return
    print(f"F:{doubled!r}", flush=True)


def _emit_bool(value: object) -> None:
    if value is True:
        print("BOOL:YES", flush=True)
        return
    if value is False:
        print("BOOL:NO", flush=True)
        return
    print(f"S:{value}", flush=True)


def _emit_uuid(value: object) -> None:
    hex_id = getattr(value, "hex", None)
    int_id = getattr(value, "int", None)
    if hex_id is not None and int_id is not None and not isinstance(value, str):
        print(f"UID:{hex_id}", flush=True)
        return
    print(f"S:{value}", flush=True)


def _emit_calendar(value: object) -> None:
    try:
        year = value.year
        month = value.month
        day = value.day
    except AttributeError:
        print(f"S:{value}", flush=True)
        return
    print(f"CAL:{year:04d}-{month:02d}-{day:02d}", flush=True)
    hour = getattr(value, "hour", None)
    minute = getattr(value, "minute", None)
    second = getattr(value, "second", None)
    if hour is not None and minute is not None and second is not None:
        print(f"CLK:{hour:02d}:{minute:02d}:{second:02d}", flush=True)
    aware = getattr(value, "tzinfo", None) is not None
    print(f"NAIVE:{0 if aware else 1}", flush=True)


def _emit_choice(value: object) -> None:
    name = getattr(value, "name", None)
    member_val = getattr(value, "value", None)
    if name is not None and member_val is not None and not isinstance(value, str):
        print(f"MEM:{name}|{member_val}", flush=True)
        return
    print(f"ORIG:{value}", flush=True)


def _emit_tagged(value: object) -> None:
    via = getattr(value, "via", None)
    payload = getattr(value, "payload", None)
    if via is not None and payload is not None and not isinstance(value, str):
        print(f"TAG:{via}", flush=True)
        print(f"PAY:{payload}", flush=True)
        return
    print(f"S:{value}", flush=True)


def _emit_seq_choice(value: object) -> None:
    try:
        items = list(value)  # type: ignore[arg-type]
    except TypeError:
        print("N:SCALAR", flush=True)
        _emit_choice(value)
        return
    print(f"N:{len(items)}", flush=True)
    for i, item in enumerate(items):
        name = getattr(item, "name", None)
        member_val = getattr(item, "value", None)
        if name is not None and member_val is not None and not isinstance(item, str):
            print(f"C:{i}:MEM:{name}|{member_val}", flush=True)
        else:
            print(f"C:{i}:ORIG:{item}", flush=True)
