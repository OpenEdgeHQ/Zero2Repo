# feature: F03
"""Option-suite observation helpers. Names here are F03-only.

Sealed features already export ``_word``, ``_greeting``, ``_runtime_int``,
``_dispatch``, ``_cmd``, ``_env_name``, ``_emit_arith``, and ``_emit_seq``.
This module must not redefine those names; F01/F04/F05/F07 helper modules
are not on disk, and F04+ would be a forward import once F03 reseals.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from optlyn import command

from _harness import invoke, write_file
from _helpers import (
    _status_and_streams,
    labeled_stdout_field,
    labeled_stdout_fields,
    require_success_marker_present,
    require_usage_class,
    require_usage_names_option,
)

_PROG = "app"
_SHORT_POOL = "abcdefgijkmnpqrstuvwxyz"


def _option_ident() -> str:
    return "k" + uuid.uuid4().hex[:8]


def _option_hi() -> str:
    return f"GREET:{uuid.uuid4().hex}:"


def _option_int() -> int:
    return 14 + uuid.uuid4().int % 80


def _option_env() -> str:
    return f"E{_option_ident().upper()}"


def _shorts(n: int, *forbidden: str) -> list[str]:
    blocked = {item for item in forbidden if item}
    out: list[str] = []
    for ch in _SHORT_POOL:
        if ch in blocked:
            continue
        out.append(ch)
        blocked.add(ch)
        if len(out) == n:
            return out
    raise RuntimeError("could not allocate distinct short option characters")


def _option_run(cli: Any, args: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("prog_name", _PROG)
    return invoke(cli, args, **kwargs)


def _option_leaf(callback: Any, *param_decs: Any, **command_kwargs: Any) -> Any:
    decorated = callback
    for deco in reversed(param_decs):
        decorated = deco(decorated)
    return command(**command_kwargs)(decorated)


def _emit_enc(value: object) -> None:
    print(f"ENC:{value!r}", flush=True)


def _print_arith(value: object) -> None:
    try:
        mark = value * 3 + 7  # type: ignore[operator]
    except TypeError:
        print(f"S:{value!r}", flush=True)
        return
    print(f"T:{mark}", flush=True)


def _print_seq(value: object) -> None:
    try:
        items = list(value)  # type: ignore[arg-type]
    except TypeError:
        print("N:SCALAR", flush=True)
        print(f"V:0:{value}", flush=True)
        return
    print(f"N:{len(items)}", flush=True)
    for i, item in enumerate(items):
        print(f"V:{i}:{item}", flush=True)


def _path_text(item: object) -> str:
    """Public path text of a bound file or path value.

    A file object carries its path on ``name``. A path-typed value is
    already that text. A single file is iterable of lines — callers must
    not ``list()`` it as a sequence of paths.
    """
    name = getattr(item, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(item)


def _emit_path_texts(value: object) -> None:
    """Write ``N:`` / ``V:`` records of bound file or path texts.

    A sequence (repeatable / multi-value) is one record per member. A
    single file-like is one scalar record — it is not listed as lines.
    Any other failed observation raises.
    """
    if isinstance(value, (str, bytes)):
        print("N:SCALAR", flush=True)
        print(f"V:0:{value}", flush=True)
        return
    if isinstance(value, (list, tuple)):
        items = list(value)
    elif hasattr(value, "read"):
        print("N:SCALAR", flush=True)
        print(f"V:0:{_path_text(value)}", flush=True)
        return
    else:
        try:
            items = list(value)  # type: ignore[arg-type]
        except TypeError as exc:
            raise AssertionError(
                f"file/path binding was not a sequence of path texts: {value!r}"
            ) from exc
    print(f"N:{len(items)}", flush=True)
    for i, item in enumerate(items):
        print(f"V:{i}:{_path_text(item)}", flush=True)


def _two_empty_file_paths() -> tuple[str, str]:
    """Two distinct existing files whose paths do not contain ``os.pathsep``."""
    root = Path(tempfile.mkdtemp(prefix="f03-env-files-"))
    left = str(write_file(root / f"{_option_ident()}.txt", ""))
    right = str(write_file(root / f"{_option_ident()}.txt", ""))
    if left == right:
        raise AssertionError("could not allocate two distinct file paths")
    if os.pathsep in left or os.pathsep in right:
        raise AssertionError(
            "temporary path contains the platform path separator; "
            f"left={left!r} right={right!r} sep={os.pathsep!r}"
        )
    return left, right


def _emit_pairs(value: object) -> None:
    try:
        items = list(value)  # type: ignore[arg-type]
    except TypeError:
        print("N:SCALAR", flush=True)
        return
    print(f"N:{len(items)}", flush=True)
    for i, item in enumerate(items):
        try:
            inner = list(item)
        except TypeError:
            print(f"P:{i}:SCALAR:{item}", flush=True)
            continue
        joined = "|".join(str(part) for part in inner)
        print(f"P:{i}:{len(inner)}:{joined}", flush=True)


def _enc_of(result: Any, greeting: str) -> str:
    try:
        return labeled_stdout_field(result, "ENC:")
    except AssertionError as exc:
        raise AssertionError(
            f"no ENC: line on stdout after {greeting!r}; {exc}"
        ) from exc


def _bound_keys(result: Any, greeting: str) -> set[str]:
    try:
        payload = labeled_stdout_field(result, "KEYS:")
    except AssertionError as exc:
        raise AssertionError(
            f"no KEYS: line on stdout after {greeting!r}; {exc}"
        ) from exc
    if not payload:
        return set()
    return set(payload.split(","))


def _require_leftover_extra(result: Any, leftover: str) -> None:
    """Require *leftover* as a collected extra-argument member.

    Observes the ``V:`` records written by ``_print_seq``. A failure to
    read stdout raises. The leftover token itself must appear as a
    collected extra; a bare character anywhere on stdout does not
    satisfy this.
    """
    if not leftover:
        raise ValueError("leftover token must be a non-empty string")
    fields = labeled_stdout_fields(result, "V:")
    members: list[str] = []
    for field in fields:
        sep = field.find(":")
        if sep < 0:
            raise AssertionError(
                f"malformed extra-argument record {field!r}; "
                f"stdout={getattr(result, 'stdout_text', result)!r}"
            )
        members.append(field[sep + 1 :])
    assert leftover in members, (
        f"leftover token {leftover!r} was not collected as an extra "
        f"argument; collected={members!r} "
        f"stdout={getattr(result, 'stdout_text', result)!r}"
    )


def require_parameter_callback_refused(
    result: Any, greeting: str, delivered_mark: str
) -> None:
    """Refusal is a usage-class failure; the refused value was not delivered.

    Uses the same usage-class helper as unknown-option / missing-value
    arms: non-zero usage-class exit, distinguishing nonempty stderr,
    command work absent. Does not pin the refusal sentence. A failure to
    read the streams raises — it is not treated as a skipped callback or
    an undelivered value.
    """
    if not delivered_mark:
        raise ValueError("delivered_mark must be a non-empty string")
    require_usage_class(result, greeting)
    _, stdout, stderr = _status_and_streams(result)
    assert delivered_mark not in stdout, (
        f"refused converted value {delivered_mark!r} was delivered; "
        f"stdout={stdout!r} stderr={stderr!r}"
    )


assert_parameter_callback_refused = require_parameter_callback_refused


def _eager_finish(mark: str):
    """Parameter callback: if the flag is on, emit *mark* and finish."""
    if not mark:
        raise ValueError("mark must be a non-empty string")

    def _cb(ctx: Any, param: Any, value: Any) -> Any:
        if value:
            print(mark, flush=True)
            ctx.exit()
        return value

    return _cb


def require_activation_unlike_omitted(
    on_result: Any, omitted_result: Any, present_result: Any, greeting: str
) -> None:
    """Activation matches a present flag and is not the omitted encoding.

    First proves the omitted flag is not already in the on state, then
    requires *on_result* to match the present-flag encoding. A failure
    to read an encoding raises — it is not treated as omitted or on.
    """
    omitted_enc = _enc_of(omitted_result, greeting)
    present_enc = _enc_of(present_result, greeting)
    on_enc = _enc_of(on_result, greeting)
    assert omitted_enc != present_enc, (
        f"omitted flag already in the on state; omitted={omitted_enc!r} "
        f"present={present_enc!r}"
    )
    assert on_enc == present_enc, (
        f"activation encoding {on_enc!r} != present-flag {present_enc!r}"
    )
    assert on_enc != omitted_enc, (
        f"activation encoding {on_enc!r} matches omitted {omitted_enc!r}"
    )


assert_activation_unlike_omitted = require_activation_unlike_omitted


def require_declared_env_unmatched(
    result: Any,
    greeting: str,
    declared_default: str,
    live_value: str,
) -> None:
    """Declared env name did not fill; the live process key did.

    Reads ``V:`` (the option whose envvar is the author-declared name)
    and ``L:`` (the option whose envvar is the process key that is
    actually set). A failure to read either field raises — it is not
    treated as an unmatched name or as a live fill.
    """
    if not declared_default:
        raise ValueError("declared_default must be a non-empty string")
    if not live_value:
        raise ValueError("live_value must be a non-empty string")
    if declared_default == live_value:
        raise ValueError("declared_default and live_value must differ")
    require_success_marker_present(result, greeting)
    try:
        declared = labeled_stdout_field(result, "V:")
    except AssertionError as exc:
        raise AssertionError(
            f"no V: line on stdout after {greeting!r}; {exc}"
        ) from exc
    try:
        live = labeled_stdout_field(result, "L:")
    except AssertionError as exc:
        raise AssertionError(
            f"no L: line on stdout after {greeting!r}; {exc}"
        ) from exc
    assert declared == declared_default, (
        f"declared env name filled {declared!r}, expected the default "
        f"{declared_default!r}; stdout={getattr(result, 'stdout_text', result)!r}"
    )
    assert live == live_value, (
        f"live process key filled {live!r}, expected {live_value!r}; "
        f"stdout={getattr(result, 'stdout_text', result)!r}"
    )


assert_declared_env_unmatched = require_declared_env_unmatched


def require_omitted_required_names_option(
    result: Any, greeting: str, public_name: str, *sibling_names: str
) -> None:
    """Omitted required option: usage class whose stderr names that public flag.

    Keeps the usage-class carrier (exit 2, greeting absent from both
    streams, nonempty stderr) and also requires *public_name* on stderr.
    Wording is not pinned. Optional sibling public flags that were not
    omitted must not appear on the same report. A failure to read the
    streams raises — it is not treated as an unnamed flag.
    """
    if not public_name:
        raise ValueError("public_name must be a non-empty string")
    for sibling in sibling_names:
        if not sibling:
            raise ValueError("sibling public name must be a non-empty string")
        if sibling == public_name:
            raise ValueError("sibling public name must differ from public_name")
    require_usage_class(result, greeting)
    require_usage_names_option(result, greeting, public_name)
    if not sibling_names:
        return
    _, _, stderr = _status_and_streams(result)
    for sibling in sibling_names:
        assert sibling not in stderr, (
            f"omitted-required report for {public_name!r} named sibling "
            f"{sibling!r}; stderr={stderr!r}"
        )


assert_omitted_required_names_option = require_omitted_required_names_option
