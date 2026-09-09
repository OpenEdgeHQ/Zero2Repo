# feature: F10
"""Command chaining and pipelines (FP-10).

Assertions stay at the PRD's precision: several subcommands in one
invocation in command-line order; each child's options before that
child's arguments; result-callback payload shape (positional sequence
versus single value versus group return); empty chain versus usage
help; shared-name transform-then-print; current-subcommand name in
chain mode unlike one child and unlike no subcommand; consume-rest on
a non-last child eating later names; attaching a group under a
chaining group refused at declaration; chained child files closed
after that callback, group files still available to the result
callback. Message wording, exception types, sequence Python types,
and current-subcommand sentinels are not pinned.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from optlyn import (
    File,
    argument,
    command,
    group,
    option,
    pass_context,
    pass_obj,
)

from _harness import invoke, workspace
from _helpers import (
    labeled_stdout_field,
    labeled_stdout_fields,
    require_declaration_refused,
    require_file_no_longer_usable,
    require_file_still_readable,
    require_positional_items,
    require_success_marker_present,
    require_usage_class,
    require_usage_help,
    unrelated_dispatch_token,
)

PROG = "app"


def _word() -> str:
    return "k" + uuid.uuid4().hex[:8]


def _greeting() -> str:
    return f"GREET:{uuid.uuid4().hex}:"


def _desc(prefix: str = "D") -> str:
    return f"{prefix}{uuid.uuid4().hex}path."


def _token() -> str:
    return f"T{uuid.uuid4().hex}"


def _mixed_token() -> str:
    token = f"Ab{_word()}Yz"
    if token == token.lower():
        raise RuntimeError(f"mixed-case token collapsed: {token!r}")
    return token


def _dispatch(cli, args, **kwargs):
    kwargs.setdefault("prog_name", PROG)
    return invoke(cli, args, **kwargs)


def _stdout(result) -> str:
    text = result.stdout_text
    if text is None:
        raise RuntimeError("stdout is None; cannot observe")
    return text


def _stderr(result) -> str:
    text = result.stderr_text
    if text is None:
        raise RuntimeError("stderr is None; cannot observe")
    return text


def _visible(result) -> str:
    return _stdout(result) + _stderr(result)


def _cmd(callback, *param_decs, inject=None, **command_kwargs):
    decorated = callback
    if inject is not None:
        decorated = inject(decorated)
    for deco in reversed(param_decs):
        decorated = deco(decorated)
    return command(**command_kwargs)(decorated)


def _grp(callback, *param_decs, inject=None, **group_kwargs):
    decorated = callback
    if inject is not None:
        decorated = inject(decorated)
    for deco in reversed(param_decs):
        decorated = deco(decorated)
    return group(**group_kwargs)(decorated)


def _require_order(text: str, *markers: str) -> None:
    pos = 0
    for index, marker in enumerate(markers):
        if not marker:
            raise ValueError("order markers must be non-empty")
        found = text.find(marker, pos)
        assert found >= 0, (
            f"marker {marker!r} missing at step {index}; text={text!r}"
        )
        pos = found + len(marker)


def _name_callback(fn: Callable[..., Any]) -> Callable[..., Any]:
    fn.__name__ = f"{_word()}_{_word()}"
    return fn


def _leaf(greeting: str, *, returns: Any = None, **command_kwargs):
    @_name_callback
    def callback(**kwargs: Any) -> Any:
        print(greeting, flush=True)
        return returns

    return _cmd(callback, **command_kwargs)


def _root(greeting: str, *, doc: str | None = None, **group_kwargs):
    @_name_callback
    def callback(**kwargs: Any) -> Any:
        print(greeting, flush=True)

    if doc is not None:
        callback.__doc__ = doc
    return _grp(callback, **group_kwargs)


def _same_successful_binding(
    result: Any,
    pairs: list[tuple[str, str]],
) -> bool:
    """True only when exit 0 and each label maps to exactly that value."""
    if result.exit_code != 0:
        return False
    text = _stdout(result)
    for label, value in pairs:
        matches = [
            line[len(label) :]
            for line in text.splitlines()
            if line.startswith(label)
        ]
        if matches != [value]:
            return False
    return True


def _recorded_payload(box: list[Any]) -> Any:
    if not box:
        raise RuntimeError(
            "result callback did not record a payload; empty box is not "
            "an empty sequence"
        )
    return box[0]


def _recorded_name(box: list[Any]) -> Any:
    if not box:
        raise RuntimeError(
            "group callback did not record a current-subcommand name"
        )
    return box[0]


# ---------------------------------------------------------------------------
# A. Several children in command-line order; options before arguments
# ---------------------------------------------------------------------------


def test_chaining_runs_each_subcommand_in_command_line_order():
    group_hi = _greeting()
    a_hi = _greeting()
    b_hi = _greeting()
    a_name = f"c-{_word()}"
    b_name = f"c-{_word()}"

    cli = _root(group_hi, chain=True)
    cli.add_command(_leaf(a_hi, name=a_name))
    cli.add_command(_leaf(b_hi, name=b_name))

    ab = _dispatch(cli, [a_name, b_name])
    ba = _dispatch(cli, [b_name, a_name])
    aba = _dispatch(cli, [a_name, b_name, a_name])
    print(
        f"ab={ab.stdout_text!r} ba={ba.stdout_text!r} aba={aba.stdout_text!r}",
        flush=True,
    )
    require_success_marker_present(ab, group_hi)
    require_success_marker_present(ab, a_hi)
    require_success_marker_present(ab, b_hi)
    _require_order(_stdout(ab), group_hi, a_hi, b_hi)

    require_success_marker_present(ba, group_hi)
    require_success_marker_present(ba, a_hi)
    require_success_marker_present(ba, b_hi)
    _require_order(_stdout(ba), group_hi, b_hi, a_hi)

    require_success_marker_present(aba, group_hi)
    require_success_marker_present(aba, a_hi)
    require_success_marker_present(aba, b_hi)
    text_aba = _stdout(aba)
    assert text_aba.count(a_hi) == 2, (
        f"repeated child did not run twice; stdout={text_aba!r}"
    )
    assert text_aba.count(b_hi) == 1, (
        f"middle child count is not 1; stdout={text_aba!r}"
    )
    _require_order(text_aba, group_hi, a_hi, b_hi, a_hi)


def test_chaining_options_bind_per_command_before_that_commands_arguments():
    a_hi = _greeting()
    b_hi = _greeting()
    a_name = f"c-{_word()}"
    b_name = f"c-{_word()}"
    opt_flag = f"--{_word()}"
    opt_dest = _word()
    arg_dest = _word()
    v1, v2 = _token(), _token()
    arg1, arg2 = _token(), _token()
    a_opt_l = f"AO:{_word()}:"
    a_arg_l = f"AA:{_word()}:"
    b_opt_l = f"BO:{_word()}:"
    b_arg_l = f"BA:{_word()}:"
    assert len({v1, v2, arg1, arg2}) == 4

    @_name_callback
    def a_cb(**kwargs: Any) -> None:
        print(a_hi, flush=True)
        print(f"{a_opt_l}{kwargs[opt_dest]}", flush=True)
        print(f"{a_arg_l}{kwargs[arg_dest]}", flush=True)

    @_name_callback
    def b_cb(**kwargs: Any) -> None:
        print(b_hi, flush=True)
        print(f"{b_opt_l}{kwargs[opt_dest]}", flush=True)
        print(f"{b_arg_l}{kwargs[arg_dest]}", flush=True)

    cli = _root(_greeting(), chain=True)
    cli.add_command(
        _cmd(
            a_cb,
            option(opt_flag, opt_dest),
            argument(arg_dest),
            name=a_name,
        )
    )
    cli.add_command(
        _cmd(
            b_cb,
            option(opt_flag, opt_dest),
            argument(arg_dest),
            name=b_name,
        )
    )

    legal = _dispatch(
        cli,
        [a_name, opt_flag, v1, arg1, b_name, opt_flag, v2, arg2],
    )
    swapped = _dispatch(
        cli,
        [a_name, arg1, opt_flag, v1, b_name, arg2, opt_flag, v2],
    )
    print(
        f"legal exit={legal.exit_code} stdout={legal.stdout_text!r} "
        f"swapped exit={swapped.exit_code} stdout={swapped.stdout_text!r} "
        f"stderr={swapped.stderr_text!r}",
        flush=True,
    )
    require_success_marker_present(legal, a_hi)
    require_success_marker_present(legal, b_hi)
    assert labeled_stdout_field(legal, a_opt_l) == v1
    assert labeled_stdout_field(legal, a_arg_l) == arg1
    assert labeled_stdout_field(legal, b_opt_l) == v2
    assert labeled_stdout_field(legal, b_arg_l) == arg2
    assert v1 not in labeled_stdout_field(legal, b_opt_l)
    assert v1 not in labeled_stdout_field(legal, b_arg_l)
    pairs = [
        (a_opt_l, v1),
        (a_arg_l, arg1),
        (b_opt_l, v2),
        (b_arg_l, arg2),
    ]
    assert _same_successful_binding(legal, pairs)
    assert not _same_successful_binding(swapped, pairs), (
        "options after that command's arguments still bound as the legal "
        f"order; stdout={swapped.stdout_text!r} stderr={swapped.stderr_text!r}"
    )


def test_non_chaining_group_does_not_run_a_second_child_name():
    a_hi = _greeting()
    b_hi = _greeting()
    a_name = f"c-{_word()}"
    b_name = f"c-{_word()}"

    chained = _root(_greeting(), chain=True)
    chained.add_command(_leaf(a_hi, name=a_name))
    chained.add_command(_leaf(b_hi, name=b_name))
    live = _dispatch(chained, [a_name, b_name])
    print(f"chain-live stdout={live.stdout_text!r}", flush=True)
    require_success_marker_present(live, a_hi)
    require_success_marker_present(live, b_hi)

    plain = _root(_greeting(), chain=False)
    plain.add_command(_leaf(a_hi, name=a_name))
    plain.add_command(_leaf(b_hi, name=b_name))
    leftover = _dispatch(plain, [a_name, b_name])
    print(
        f"nonchain exit={leftover.exit_code} stdout={leftover.stdout_text!r} "
        f"stderr={leftover.stderr_text!r}",
        flush=True,
    )
    vis = _visible(leftover)
    assert b_hi not in vis, (
        "non-chaining group ran the second name as a child; "
        f"visible={vis!r}"
    )
    require_usage_class(leftover, b_hi)


# ---------------------------------------------------------------------------
# B. Result callback payload shape; group parameters; optional callback
# ---------------------------------------------------------------------------


def test_chaining_result_callback_receives_ordered_sequence_of_returns():
    a_hi = _greeting()
    b_hi = _greeting()
    result_hi = _greeting()
    a_name = f"c-{_word()}"
    b_name = f"c-{_word()}"
    t1, t2 = _token(), _token()
    assert t1 != t2

    def _make(register: bool):
        box: list[Any] = []

        @_name_callback
        def on_result(payload: Any, **kwargs: Any) -> None:
            print(result_hi, flush=True)
            box.append(payload)

        cli = _root(_greeting(), chain=True)
        cli.add_command(_leaf(a_hi, returns=t1, name=a_name))
        cli.add_command(_leaf(b_hi, returns=t2, name=b_name))
        if register:
            cli.result_callback()(on_result)
        return cli, box

    with_cb, box_ab = _make(True)
    ab = _dispatch(with_cb, [a_name, b_name])
    payload_ab = _recorded_payload(box_ab)
    print(
        f"ab stdout={ab.stdout_text!r} payload={payload_ab!r}",
        flush=True,
    )
    require_success_marker_present(ab, a_hi)
    require_success_marker_present(ab, b_hi)
    require_success_marker_present(ab, result_hi)
    _require_order(_stdout(ab), a_hi, b_hi, result_hi)
    require_positional_items(payload_ab, t1, t2)

    with_cb_ba, box_ba = _make(True)
    ba = _dispatch(with_cb_ba, [b_name, a_name])
    payload_ba = _recorded_payload(box_ba)
    print(f"ba stdout={ba.stdout_text!r} payload={payload_ba!r}", flush=True)
    require_success_marker_present(ba, result_hi)
    _require_order(_stdout(ba), b_hi, a_hi, result_hi)
    require_positional_items(payload_ba, t2, t1)

    bare, _ = _make(False)
    ignored = _dispatch(bare, [a_name, b_name])
    print(f"no-callback stdout={ignored.stdout_text!r}", flush=True)
    require_success_marker_present(ignored, a_hi)
    require_success_marker_present(ignored, b_hi)
    assert result_hi not in _stdout(ignored), (
        f"unregistered result greeting appeared; stdout={ignored.stdout_text!r}"
    )


def test_non_chain_result_callback_receives_single_value_or_group_return():
    child_hi = _greeting()
    result_hi = _greeting()
    child_name = f"c-{_word()}"
    t1 = _token()
    group_token = _token()
    assert t1 != group_token

    def _make(*, chain: bool, invoke_without_command: bool):
        box: list[Any] = []

        @_name_callback
        def root(**kwargs: Any) -> Any:
            return group_token

        @_name_callback
        def on_result(payload: Any, **kwargs: Any) -> None:
            print(result_hi, flush=True)
            box.append(payload)

        cli = _grp(
            root,
            chain=chain,
            invoke_without_command=invoke_without_command,
        )
        cli.add_command(_leaf(child_hi, returns=t1, name=child_name))
        cli.result_callback()(on_result)
        return cli, box

    named_cli, named_box = _make(chain=False, invoke_without_command=False)
    named = _dispatch(named_cli, [child_name])
    named_payload = _recorded_payload(named_box)
    print(
        f"named stdout={named.stdout_text!r} payload={named_payload!r}",
        flush=True,
    )
    require_success_marker_present(named, child_hi)
    require_success_marker_present(named, result_hi)
    assert named_payload == t1, (
        "non-chain named payload is not the child return; "
        f"payload={named_payload!r} t1={t1!r}"
    )

    empty_cli, empty_box = _make(chain=False, invoke_without_command=True)
    empty = _dispatch(empty_cli, [])
    empty_payload = _recorded_payload(empty_box)
    print(
        f"empty stdout={empty.stdout_text!r} payload={empty_payload!r}",
        flush=True,
    )
    require_success_marker_present(empty, result_hi)
    assert child_hi not in _stdout(empty)
    assert empty_payload == group_token, (
        "non-chain empty payload is not the group return; "
        f"payload={empty_payload!r} group={group_token!r}"
    )
    try:
        length = len(empty_payload)
    except Exception:
        length = None
    assert not (length == 0), (
        f"non-chain empty payload is an empty sequence; payload={empty_payload!r}"
    )

    chain_empty_cli, chain_empty_box = _make(
        chain=True, invoke_without_command=True
    )
    chain_empty = _dispatch(chain_empty_cli, [])
    chain_payload = _recorded_payload(chain_empty_box)
    print(
        f"chain-empty stdout={chain_empty.stdout_text!r} "
        f"payload={chain_payload!r}",
        flush=True,
    )
    require_success_marker_present(chain_empty, result_hi)
    require_positional_items(chain_payload)
    assert chain_payload != group_token


def test_result_callback_receives_group_parameters():
    a_hi = _greeting()
    b_hi = _greeting()
    result_hi = _greeting()
    a_name = f"c-{_word()}"
    b_name = f"c-{_word()}"
    opt_flag = f"--{_word()}"
    opt_dest = _word()
    v1, v2, v3 = _token(), _token(), _token()
    assert len({v1, v2, v3}) == 3
    t1, t2 = _token(), _token()

    def _make():
        payloads: list[Any] = []
        params: list[Any] = []

        @_name_callback
        def root(**kwargs: Any) -> None:
            return None

        @_name_callback
        def on_result(payload: Any, **kwargs: Any) -> None:
            print(result_hi, flush=True)
            payloads.append(payload)
            params.append(kwargs[opt_dest])

        cli = _grp(
            root,
            option(opt_flag, opt_dest, required=True),
            chain=True,
            invoke_without_command=True,
        )
        cli.add_command(_leaf(a_hi, returns=t1, name=a_name))
        cli.add_command(_leaf(b_hi, returns=t2, name=b_name))
        cli.result_callback()(on_result)
        return cli, payloads, params

    cli_a, payloads_a, params_a = _make()
    run_a = _dispatch(cli_a, [opt_flag, v1, a_name, b_name])
    print(f"v1 stdout={run_a.stdout_text!r} param={params_a!r}", flush=True)
    require_success_marker_present(run_a, a_hi)
    require_success_marker_present(run_a, b_hi)
    require_success_marker_present(run_a, result_hi)
    assert _recorded_payload(params_a) == v1
    require_positional_items(_recorded_payload(payloads_a), t1, t2)

    cli_b, _, params_b = _make()
    run_b = _dispatch(cli_b, [opt_flag, v2, a_name, b_name])
    print(f"v2 stdout={run_b.stdout_text!r} param={params_b!r}", flush=True)
    require_success_marker_present(run_b, result_hi)
    assert _recorded_payload(params_b) == v2
    assert _recorded_payload(params_a) != _recorded_payload(params_b)

    cli_e, payloads_e, params_e = _make()
    run_e = _dispatch(cli_e, [opt_flag, v3])
    print(f"empty stdout={run_e.stdout_text!r} param={params_e!r}", flush=True)
    require_success_marker_present(run_e, result_hi)
    assert a_hi not in _stdout(run_e)
    assert _recorded_payload(params_e) == v3
    require_positional_items(_recorded_payload(payloads_e))


# ---------------------------------------------------------------------------
# C. Empty chain with invoke-without-command is not usage help
# ---------------------------------------------------------------------------


def test_empty_chain_with_invoke_without_command_runs_result_callback_not_help():
    group_hi = _greeting()
    child_hi = _greeting()
    result_hi = _greeting()
    child_name = f"c-{_word()}"
    desc = _desc("G")
    group_token = _token()

    def _make(*, invoke_without_command: bool):
        box: list[Any] = []

        @_name_callback
        def root(**kwargs: Any) -> Any:
            print(group_hi, flush=True)
            return group_token

        root.__doc__ = desc

        @_name_callback
        def on_result(payload: Any, **kwargs: Any) -> None:
            print(result_hi, flush=True)
            box.append(payload)

        cli = _grp(
            root,
            chain=True,
            invoke_without_command=invoke_without_command,
        )
        cli.add_command(_leaf(child_hi, name=child_name))
        cli.result_callback()(on_result)
        return cli, box

    baseline_cli, _ = _make(invoke_without_command=False)
    baseline = _dispatch(baseline_cli, [])
    print(
        f"baseline exit={baseline.exit_code} stdout={baseline.stdout_text!r} "
        f"stderr={baseline.stderr_text!r}",
        flush=True,
    )
    require_usage_help(baseline, group_hi, desc)
    vis_base = _visible(baseline)
    assert result_hi not in vis_base
    assert child_hi not in vis_base

    empty_cli, empty_box = _make(invoke_without_command=True)
    empty = _dispatch(empty_cli, [])
    payload = _recorded_payload(empty_box)
    print(
        f"empty stdout={empty.stdout_text!r} payload={payload!r}",
        flush=True,
    )
    require_success_marker_present(empty, result_hi)
    vis = _visible(empty)
    assert desc not in vis, (
        f"empty chain still showed the usage-help description; visible={vis!r}"
    )
    assert child_hi not in vis
    require_positional_items(payload)
    assert payload != group_token


# ---------------------------------------------------------------------------
# D. Shared name: transform then print; interleaved prints keep order
# ---------------------------------------------------------------------------


def test_chained_shared_name_lower_then_show_transforms_then_prints():
    xform_name = f"x-{_word()}"
    show_name = f"p-{_word()}"
    name_dest = _word()
    label = f"NS:{_word()}:"
    token = _mixed_token()
    lowered = token.lower()
    assert lowered != token

    @_name_callback
    def root(ctx, **kwargs: Any) -> None:
        ctx.obj = {"name": kwargs[name_dest]}

    @_name_callback
    def xform(obj) -> None:
        held = obj["name"]
        if held is None:
            raise RuntimeError("shared name is None; cannot transform")
        obj["name"] = held.lower()

    @_name_callback
    def shower(obj) -> None:
        print(f"{label}{obj['name']}", flush=True)

    cli = _grp(
        root,
        argument(name_dest),
        inject=pass_context,
        chain=True,
    )
    cli.add_command(_cmd(xform, inject=pass_obj, name=xform_name))
    cli.add_command(_cmd(shower, inject=pass_obj, name=show_name))

    shown = _dispatch(cli, [token, show_name])
    transformed = _dispatch(cli, [token, xform_name, show_name])
    interleaved = _dispatch(cli, [token, show_name, xform_name, show_name])
    print(
        f"show={shown.stdout_text!r} lower-show={transformed.stdout_text!r} "
        f"interleaved={interleaved.stdout_text!r}",
        flush=True,
    )
    require_success_marker_present(shown, f"{label}{token}")
    assert labeled_stdout_field(shown, label) == token

    require_success_marker_present(transformed, f"{label}{lowered}")
    assert labeled_stdout_field(transformed, label) == lowered
    assert labeled_stdout_field(transformed, label) != token

    fields = labeled_stdout_fields(interleaved, label)
    print(f"interleaved fields={fields!r}", flush=True)
    assert interleaved.exit_code == 0, (
        f"interleaved chain expected exit 0, got {interleaved.exit_code}; "
        f"stderr={interleaved.stderr_text!r}"
    )
    assert fields == [token, lowered], (
        "interleaved prints are not original then lowered; "
        f"fields={fields!r} token={token!r} lowered={lowered!r}"
    )


# ---------------------------------------------------------------------------
# E. Current subcommand name in chain mode is not one child and not absent
# ---------------------------------------------------------------------------


def test_chaining_current_subcommand_name_is_neither_one_child_nor_absent():
    a_hi = _greeting()
    a2_hi = _greeting()
    a_name = f"c-{_word()}"
    a2_name = f"c-{_word()}"
    assert a_name != a2_name

    def _make(*, chain: bool, invoke_without_command: bool = False):
        names: list[Any] = []

        @_name_callback
        def root(ctx, **kwargs: Any) -> None:
            names.append(ctx.invoked_subcommand)

        cli = _grp(
            root,
            inject=pass_context,
            chain=chain,
            invoke_without_command=invoke_without_command,
        )
        cli.add_command(_leaf(a_hi, name=a_name))
        cli.add_command(_leaf(a2_hi, name=a2_name))
        return cli, names

    nc_cli, nc_box = _make(chain=False)
    nc_a = _dispatch(nc_cli, [a_name])
    nc_a2 = _dispatch(nc_cli, [a2_name])
    nc_name = _recorded_name(nc_box)
    if len(nc_box) < 2:
        raise RuntimeError(
            f"non-chain group did not record both names; box={nc_box!r}"
        )
    nc_name_2 = nc_box[1]
    print(
        f"nonchain a={nc_name!r} a2={nc_name_2!r} "
        f"stdout_a={nc_a.stdout_text!r}",
        flush=True,
    )
    require_success_marker_present(nc_a, a_hi)
    require_success_marker_present(nc_a2, a2_hi)
    assert nc_name == a_name, (
        f"non-chain current name is not the child; got={nc_name!r} "
        f"child={a_name!r}"
    )
    assert nc_name_2 == a2_name, (
        f"non-chain current name did not follow the child; "
        f"got={nc_name_2!r} child={a2_name!r}"
    )
    assert nc_name != nc_name_2

    ch_cli, ch_box = _make(chain=True)
    ch_a = _dispatch(ch_cli, [a_name])
    ch_name = _recorded_name(ch_box)
    print(
        f"chain-named name={ch_name!r} stdout={ch_a.stdout_text!r}",
        flush=True,
    )
    require_success_marker_present(ch_a, a_hi)
    assert ch_name != a_name, (
        f"chain-mode current name is the child name {a_name!r}; "
        f"got={ch_name!r}"
    )

    empty_cli, empty_box = _make(chain=True, invoke_without_command=True)
    empty = _dispatch(empty_cli, [])
    empty_name = _recorded_name(empty_box)
    print(
        f"chain-empty name={empty_name!r} stdout={empty.stdout_text!r}",
        flush=True,
    )
    assert empty.exit_code == 0, (
        f"empty chain expected exit 0, got {empty.exit_code}; "
        f"stderr={empty.stderr_text!r}"
    )
    assert a_hi not in _stdout(empty)
    assert empty_name != a_name, (
        f"empty-chain current name is the child name {a_name!r}; "
        f"got={empty_name!r}"
    )
    assert ch_name != empty_name, (
        "chain-named current name is not distinguishable from no-subcommand; "
        f"named={ch_name!r} empty={empty_name!r}"
    )


# ---------------------------------------------------------------------------
# F. Consume-rest: non-last is declared and eats later names; last still chains
# ---------------------------------------------------------------------------


def test_consume_rest_on_non_last_child_is_declared_and_eats_later_names():
    a_hi = _greeting()
    b_hi = _greeting()
    a_name = f"c-{_word()}"
    b_name = f"c-{_word()}"
    rest_dest = _word()
    extra = unrelated_dispatch_token(a_name, b_name)
    held: list[Any] = []

    @_name_callback
    def a_cb(**kwargs: Any) -> None:
        print(a_hi, flush=True)
        held.append(kwargs[rest_dest])

    cli = _root(_greeting(), chain=True)
    cli.add_command(
        _cmd(a_cb, argument(rest_dest, nargs=-1), name=a_name)
    )
    cli.add_command(_leaf(b_hi, name=b_name))

    result = _dispatch(cli, [a_name, extra, b_name])
    rest = _recorded_payload(held)
    print(
        f"exit={result.exit_code} stdout={result.stdout_text!r} rest={rest!r}",
        flush=True,
    )
    vis = _visible(result)
    assert a_hi in _stdout(result), (
        f"non-last consume-rest did not run the first child; visible={vis!r}"
    )
    assert b_hi not in vis, (
        "non-last consume-rest still dispatched the later name; "
        f"visible={vis!r}"
    )
    require_positional_items(rest, extra, b_name)


def test_consume_rest_on_last_child_still_dispatches_earlier_children():
    a_hi = _greeting()
    b_hi = _greeting()
    a_name = f"c-{_word()}"
    b_name = f"c-{_word()}"
    rest_dest = _word()
    extra1 = unrelated_dispatch_token(a_name, b_name)
    extra2 = unrelated_dispatch_token(a_name, b_name, extra1)
    held: list[Any] = []

    @_name_callback
    def b_cb(**kwargs: Any) -> None:
        print(b_hi, flush=True)
        held.append(kwargs[rest_dest])

    cli = _root(_greeting(), chain=True)
    cli.add_command(_leaf(a_hi, name=a_name))
    cli.add_command(
        _cmd(b_cb, argument(rest_dest, nargs=-1), name=b_name)
    )

    result = _dispatch(cli, [a_name, b_name, extra1, extra2])
    rest = _recorded_payload(held)
    print(
        f"exit={result.exit_code} stdout={result.stdout_text!r} rest={rest!r}",
        flush=True,
    )
    require_success_marker_present(result, a_hi)
    require_success_marker_present(result, b_hi)
    _require_order(_stdout(result), a_hi, b_hi)
    require_positional_items(rest, extra1, extra2)


# ---------------------------------------------------------------------------
# G. Attaching a group under a chaining group is refused at declaration
# ---------------------------------------------------------------------------


def test_attaching_a_group_under_a_chaining_group_is_refused_at_declaration():
    chain_hi = _greeting()
    mid_hi = _greeting()
    leaf_hi = _greeting()
    mid_name = f"m-{_word()}"
    leaf_name = f"l-{_word()}"

    chain_leaf = _root(chain_hi, chain=True)
    chain_leaf.add_command(_leaf(leaf_hi, name=leaf_name))
    leaf_ok = _dispatch(chain_leaf, [leaf_name])
    print(f"chain-leaf stdout={leaf_ok.stdout_text!r}", flush=True)
    require_success_marker_present(leaf_ok, leaf_hi)

    nested = _root(chain_hi, chain=False)
    middle = _root(mid_hi, name=mid_name)
    middle.add_command(_leaf(leaf_hi, name=leaf_name))
    nested.add_command(middle)
    nest_ok = _dispatch(nested, [mid_name, leaf_name])
    print(f"nonchain-nest stdout={nest_ok.stdout_text!r}", flush=True)
    require_success_marker_present(nest_ok, chain_hi)
    require_success_marker_present(nest_ok, mid_hi)
    require_success_marker_present(nest_ok, leaf_hi)
    _require_order(_stdout(nest_ok), chain_hi, mid_hi, leaf_hi)

    probe = _root(chain_hi, chain=True)
    probe_mid = _root(mid_hi, name=mid_name)
    probe_mid.add_command(_leaf(leaf_hi, name=leaf_name))
    refused = require_declaration_refused(lambda: probe.add_command(probe_mid))
    print(f"declaration refused: {type(refused).__name__}", flush=True)
    assert refused is not None


# ---------------------------------------------------------------------------
# H. Child file closed after callback; group file stays for result callback
# ---------------------------------------------------------------------------


def test_chained_child_file_closes_after_callback_group_file_stays_for_result_callback():
    child_hi = _greeting()
    result_hi = _greeting()
    child_name = f"c-{_word()}"
    g_dest = _word()
    c_dest = _word()
    g_file = f"g-{_word()}.txt"
    c_file = f"c-{_word()}.txt"
    gbytes = f"G{_token()}"
    cbytes = f"C{_token()}TAIL{_token()}"
    prefix = cbytes[:12]
    assert cbytes.startswith(prefix)
    assert prefix != cbytes
    token = _token()
    held: list[Any] = []
    payloads: list[Any] = []

    @_name_callback
    def root(**kwargs: Any) -> None:
        return None

    @_name_callback
    def child(**kwargs: Any) -> Any:
        print(child_hi, flush=True)
        handle = kwargs[c_dest]
        require_file_still_readable(handle, prefix)
        held.append(handle)
        return token

    @_name_callback
    def on_result(payload: Any, **kwargs: Any) -> None:
        print(result_hi, flush=True)
        if not held:
            raise RuntimeError("child callback did not hold a file object")
        require_file_no_longer_usable(held[0])
        group_file = kwargs[g_dest]
        require_file_still_readable(group_file, gbytes)
        payloads.append(payload)

    cli = _grp(
        root,
        argument(g_dest, type=File()),
        chain=True,
        invoke_without_command=True,
    )
    cli.add_command(_cmd(child, argument(c_dest, type=File()), name=child_name))
    cli.result_callback()(on_result)

    with workspace() as ws:
        ws.write(g_file, gbytes)
        ws.write(c_file, cbytes)
        result = ws.invoke(
            cli,
            [g_file, child_name, c_file],
            prog_name=PROG,
        )
        leftover_c = ws.read(c_file)
        leftover_g = ws.read(g_file)

    payload = _recorded_payload(payloads)
    print(
        f"exit={result.exit_code} stdout={result.stdout_text!r} "
        f"payload={payload!r}",
        flush=True,
    )
    require_success_marker_present(result, child_hi)
    require_success_marker_present(result, result_hi)
    _require_order(_stdout(result), child_hi, result_hi)
    require_positional_items(payload, token)
    assert leftover_c == cbytes
    assert leftover_g == gbytes
