# feature: F06
"""F06 helpers. Names here are F06-only.

Sealed F10 already exports ``_desc``, ``_dispatch``, ``_greeting``,
``_leaf``, ``_root``, ``_visible``, and ``_word``. ``F10_helpers.py`` is
not on disk, so F06 scaffolding uses new names instead of a predecessor
import.
"""

from __future__ import annotations

import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from optlyn import Group, command, group

from _harness import invoke
from _helpers import labeled_stdout_field

_GROUP_PROG = "app"


def _group_ident() -> str:
    return "k" + uuid.uuid4().hex[:8]


def _group_hi() -> str:
    return f"GREET:{uuid.uuid4().hex}:"


def _group_desc(prefix: str = "D") -> str:
    return f"{prefix}{uuid.uuid4().hex}path."


def _group_run(cli: Any, args: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("prog_name", _GROUP_PROG)
    return invoke(cli, args, **kwargs)


def _group_visible(result: Any) -> str:
    stdout = result.stdout_text
    stderr = result.stderr_text
    if stdout is None or stderr is None:
        raise RuntimeError("invocation streams are None; cannot observe")
    return stdout + stderr


def _emit_pending_subcommand(ctx: Any, label: str) -> None:
    """Print the invocation-context pending-subcommand report.

    The form of the report is the implementer's. A read failure raises;
    it is not mapped to a sentinel. An empty or absent group-only
    report versus the child's name is a distinguishable pair.
    """
    if not label:
        raise ValueError("pending-report label must be non-empty")
    if ctx is None:
        raise RuntimeError(
            "callback received no invocation context; cannot observe "
            "whether a subcommand is about to run"
        )
    try:
        report = ctx.invoked_subcommand
    except Exception as exc:
        raise RuntimeError(
            "invocation context did not report whether a subcommand "
            f"is about to run: {exc}"
        ) from exc
    print(f"{label}{report!r}", flush=True)


def _require_invocation_reports_unlike(
    empty_result: Any, named_result: Any, label: str
) -> None:
    """Group-only and group-then-child pending reports must differ.

    Line 261 requires the callback to see two different reports. An
    empty or absent group-only report versus the child's name is a
    valid pair. Does not strip the child name or demand a leftover
    after that strip.
    """
    if not label:
        raise ValueError("pending-report label must be non-empty")
    empty_report = labeled_stdout_field(empty_result, label)
    named_report = labeled_stdout_field(named_result, label)
    assert empty_report != named_report, (
        "group-only and group-then-child invocation reports are not "
        f"distinguishable; empty={empty_report!r} named={named_report!r}"
    )


def _require_before(text: str, earlier: str, later: str) -> None:
    pos_a = text.find(earlier)
    pos_b = text.find(later)
    assert pos_a >= 0, f"{earlier!r} missing; text={text!r}"
    assert pos_b >= 0, f"{later!r} missing; text={text!r}"
    assert pos_a < pos_b, (
        f"{earlier!r} did not appear before {later!r}; text={text!r}"
    )


def _line_starting(text: str, prefix: str) -> str:
    if text is None:
        raise RuntimeError("stdout is None; cannot observe a value line")
    for line in text.splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(
        f"no line starting with {prefix!r}; stdout={text!r}"
    )


def _group_leaf(greeting: str, *, doc: str | None = None, **command_kwargs: Any) -> Any:
    def callback() -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_group_ident()}_{_group_ident()}"
    if doc is not None:
        callback.__doc__ = doc
    return command(**command_kwargs)(callback)


def _group_root(greeting: str, *, doc: str | None = None, **group_kwargs: Any) -> Any:
    def callback(**kwargs: Any) -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_group_ident()}_{_group_ident()}"
    if doc is not None:
        callback.__doc__ = doc
    return group(**group_kwargs)(callback)


class _LookupGroup(Group):
    """Author custom group: list names and resolve by name, with a recorder."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._listed_names: list[str] = []
        self._resolver: Callable[[str], Any] | None = None
        self.looked_up: list[str] = []
        self.listed: list[str] = []

    def configure(
        self,
        names: list[str],
        resolver: Callable[[str], Any],
    ) -> None:
        self._listed_names = list(names)
        self._resolver = resolver

    def list_commands(self, ctx) -> list[str]:
        rec = self.listed
        if rec is None:
            raise RuntimeError("listing recorder is None; cannot observe")
        rec.append("list")
        names = self._listed_names
        if names is None:
            raise RuntimeError("listed names not configured")
        return list(names)

    def get_command(self, ctx, cmd_name: str):
        rec = self.looked_up
        if rec is None:
            raise RuntimeError("lookup recorder is None; cannot observe")
        rec.append(cmd_name)
        resolver = self._resolver
        if resolver is None:
            raise RuntimeError("resolver not configured")
        return resolver(cmd_name)


@contextmanager
def _on_path(root: Path, *mod_names: str) -> Iterator[None]:
    inserted = str(root)
    sys.path.insert(0, inserted)
    try:
        yield
    finally:
        while inserted in sys.path:
            sys.path.remove(inserted)
        for name in mod_names:
            sys.modules.pop(name, None)


def _trace_loaded(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError as exc:
        raise RuntimeError(f"cannot observe import trace {path}: {exc}") from exc


def _read_order(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise AssertionError(f"load-order log missing: {path}")
    except OSError as exc:
        raise RuntimeError(f"cannot read load-order log {path}: {exc}") from exc
    return [line for line in text.splitlines() if line]


def _write_leaf_module(
    ws: Any,
    mod_name: str,
    greeting: str,
    cmd_name: str,
    trace: Path,
    order: Path | None = None,
    order_tag: str | None = None,
) -> None:
    extra = ""
    if order is not None and order_tag is not None:
        extra = (
            "from pathlib import Path as _P\n"
            f"_op = _P({str(order)!r})\n"
            f"_prev = _op.read_text(encoding='utf-8') if _op.is_file() else ''\n"
            f"_op.write_text(_prev + {order_tag!r} + '\\n', encoding='utf-8')\n"
        )
    body = (
        "from pathlib import Path as _Trace\n"
        "from optlyn import command\n"
        f"_Trace({str(trace)!r}).write_text('loaded', encoding='utf-8')\n"
        f"{extra}"
        f"def _cb():\n"
        f"    print({greeting!r}, flush=True)\n"
        f"_cb.__name__ = {_group_ident()!r}\n"
        f"cli = command(name={cmd_name!r})(_cb)\n"
    )
    dest = ws.write(f"{mod_name}.py", body)
    if not dest.is_file():
        raise RuntimeError(f"failed to write leaf module {mod_name!r} at {dest}")


def _three_layer() -> tuple[Any, dict[str, str]]:
    outer_hi = _group_hi()
    mid_hi = _group_hi()
    leaf_hi = _group_hi()
    mid_name = f"m-{_group_ident()}"
    leaf_name = f"l-{_group_ident()}"
    outer_desc = _group_desc("O")
    mid_desc = _group_desc("M")

    def outer() -> None:
        print(outer_hi, flush=True)

    outer.__name__ = f"{_group_ident()}_{_group_ident()}"
    outer.__doc__ = outer_desc
    cli = group()(outer)

    def middle() -> None:
        print(mid_hi, flush=True)

    middle.__name__ = f"{_group_ident()}_{_group_ident()}"
    middle.__doc__ = mid_desc
    mid = group(name=mid_name)(middle)
    mid.add_command(_group_leaf(leaf_hi, name=leaf_name))
    cli.add_command(mid)
    return cli, {
        "outer_hi": outer_hi,
        "mid_hi": mid_hi,
        "leaf_hi": leaf_hi,
        "mid_name": mid_name,
        "leaf_name": leaf_name,
        "outer_desc": outer_desc,
        "mid_desc": mid_desc,
    }
