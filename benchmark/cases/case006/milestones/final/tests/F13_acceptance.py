# feature: F13
"""Usage failures, abort, and exit status (FP-13).

Assertions stay at the PRD's precision: standalone exit classes 0 / 2 /
1-abort, usage messages on stderr without running the callback, abort
indication unlike usage with a nonempty remainder after covariates are
stripped, general file-open errors that are not usage-class, and
disabled standalone mode propagating failures while return values
bubble. Message wording, exception types, and traceback frames are
not pinned.
"""

from __future__ import annotations

import uuid

from optlyn import (
    INT,
    File,
    argument,
    command,
    confirmation_option,
    group,
    option,
    pass_context,
    version_option,
)

from _harness import invoke, workspace
from _helpers import (
    assert_abort_indication_unlike_usage,
    assert_eager_identity,
    assert_failure_propagates,
    assert_general_file_error_names_path,
    assert_intentional_help,
    assert_positional_items,
    assert_process_exit_not_captured_exception,
    assert_remaining_skipped,
    assert_success_marker_present,
    assert_usage_class,
    assert_usage_help,
    assert_usage_names_argument,
    assert_usage_names_option,
    unrelated_dispatch_token,
    usage_stderr_remainder,
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


def _runtime_int() -> int:
    return 14 + uuid.uuid4().int % 80


def _status_outside_classes() -> int:
    return 3 + uuid.uuid4().int % 20


def _unknown(*forbidden: str) -> str:
    return f"--{unrelated_dispatch_token(*forbidden)}"


def _cmd(callback, *param_decs, inject=None, **command_kwargs):
    command_kwargs.setdefault("name", _word())
    decorated = callback
    if inject is not None:
        decorated = inject(decorated)
    for deco in reversed(param_decs):
        decorated = deco(decorated)
    return command(**command_kwargs)(decorated)


def _grp(callback, **group_kwargs):
    group_kwargs.setdefault("name", _word())
    return group(**group_kwargs)(callback)


def _dispatch(cli, args, **kwargs):
    kwargs.setdefault("prog_name", PROG)
    result = invoke(cli, args, **kwargs)
    print(
        f"exit={result.exit_code} stdout={result.stdout_text!r} "
        f"stderr={result.stderr_text!r} return={result.return_value!r}",
        flush=True,
    )
    return result


def _greet_leaf(greeting: str, *param_decs, **command_kwargs):
    def callback(**kwargs) -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_word()}_{_word()}"
    return _cmd(callback, *param_decs, **command_kwargs)


# ---------------------------------------------------------------------------
# A. Success class exit 0
# ---------------------------------------------------------------------------


def test_successful_callback_exits_zero():
    greeting = _greeting()
    leaf = _greet_leaf(greeting)
    result = _dispatch(leaf, [])
    assert_success_marker_present(result, greeting)
    assert result.exit_code == 0, (
        f"successful callback expected exit 0, got {result.exit_code}; "
        f"stdout={result.stdout_text!r} stderr={result.stderr_text!r}"
    )


def test_intentional_help_exits_zero_skips_callback():
    greeting = _greeting()
    desc = _desc("H")

    def callback() -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_word()}_{_word()}"
    callback.__doc__ = desc
    leaf = _cmd(callback)
    baseline = _dispatch(leaf, [])
    helped = _dispatch(leaf, ["--help"])
    print(f"desc={desc!r}", flush=True)
    assert_success_marker_present(baseline, greeting)
    assert_intentional_help(helped, greeting, desc)


def test_intentional_version_exits_zero_skips_callback():
    greeting = _greeting()
    identity = f"ver-{uuid.uuid4().hex}"
    flag = f"--{_word()}"

    def callback(**kwargs) -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_word()}_{_word()}"
    leaf = _cmd(
        callback,
        option(flag, required=True),
        version_option(identity),
    )
    baseline = _dispatch(leaf, [flag, _word()])
    versioned = _dispatch(leaf, ["--version"])
    print(f"identity={identity!r}", flush=True)
    assert_success_marker_present(baseline, greeting)
    assert_eager_identity(versioned, greeting, identity)


def test_author_clean_stop_defaults_to_zero():
    start = _greeting()
    after = f"AFTER:{uuid.uuid4().hex}:"

    def stopping(ctx) -> None:
        print(start, flush=True)
        ctx.exit()
        print(after, flush=True)

    def running(ctx) -> None:
        print(start, flush=True)
        print(after, flush=True)

    stopping.__name__ = f"{_word()}_{_word()}"
    running.__name__ = f"{_word()}_{_word()}"
    stopped = _dispatch(_cmd(stopping, inject=pass_context), [])
    continued = _dispatch(_cmd(running, inject=pass_context), [])
    print(f"start={start!r} after={after!r}", flush=True)
    assert stopped.exit_code == 0, (
        f"clean stop without a supplied status expected exit 0, "
        f"got {stopped.exit_code}; stdout={stopped.stdout_text!r} "
        f"stderr={stopped.stderr_text!r}"
    )
    assert_remaining_skipped(stopped, start, after)
    assert_success_marker_present(continued, start)
    assert_success_marker_present(continued, after)


def test_author_clean_stop_uses_supplied_status():
    start = _greeting()
    after = f"AFTER:{uuid.uuid4().hex}:"
    status = _status_outside_classes()
    assert status not in {0, 1, 2}

    def stopping(ctx) -> None:
        print(start, flush=True)
        ctx.exit(status)
        print(after, flush=True)

    def running(ctx) -> None:
        print(start, flush=True)
        print(after, flush=True)

    stopping.__name__ = f"{_word()}_{_word()}"
    running.__name__ = f"{_word()}_{_word()}"
    stopped = _dispatch(_cmd(stopping, inject=pass_context), [])
    continued = _dispatch(_cmd(running, inject=pass_context), [])
    print(f"status={status} start={start!r} after={after!r}", flush=True)
    assert stopped.exit_code == status, (
        f"clean stop expected supplied status {status}, got "
        f"{stopped.exit_code}; stdout={stopped.stdout_text!r} "
        f"stderr={stopped.stderr_text!r}"
    )
    assert_remaining_skipped(stopped, start, after)
    assert_success_marker_present(continued, after)
    assert continued.exit_code == 0


def test_clean_stop_supplied_status_one():
    start = _greeting()
    after = f"AFTER:{uuid.uuid4().hex}:"

    def stopping(ctx) -> None:
        print(start, flush=True)
        ctx.exit(1)
        print(after, flush=True)

    stopping.__name__ = f"{_word()}_{_word()}"
    stopped = _dispatch(_cmd(stopping, inject=pass_context), [])
    print(f"start={start!r} after={after!r}", flush=True)
    assert_process_exit_not_captured_exception(stopped)
    assert stopped.exit_code == 1, (
        f"clean stop supplied status 1 expected exit 1, got "
        f"{stopped.exit_code}; stdout={stopped.stdout_text!r} "
        f"stderr={stopped.stderr_text!r}"
    )
    assert_remaining_skipped(stopped, start, after)


# ---------------------------------------------------------------------------
# B. Usage class exit 2, stderr report, callback skipped
# ---------------------------------------------------------------------------


def test_unknown_option_is_usage_class_skips_callback():
    greeting = _greeting()
    unknown = _unknown(greeting)
    leaf = _greet_leaf(greeting)
    baseline = _dispatch(leaf, [])
    failed = _dispatch(leaf, [unknown])
    print(f"unknown={unknown!r}", flush=True)
    assert_success_marker_present(baseline, greeting)
    assert_usage_class(failed, greeting)


def test_unknown_subcommand_is_usage_class_skips_callback():
    group_hi = _greeting()
    leaf_hi = _greeting()
    child_name = f"c-{_word()}"
    token = unrelated_dispatch_token(child_name, group_hi, leaf_hi)

    def root() -> None:
        print(group_hi, flush=True)

    root.__name__ = f"{_word()}_{_word()}"
    cli = _grp(root)
    cli.add_command(_greet_leaf(leaf_hi, name=child_name))
    baseline = _dispatch(cli, [child_name])
    unknown = _dispatch(cli, [token])
    print(f"token={token!r} child={child_name!r}", flush=True)
    assert_success_marker_present(baseline, group_hi)
    assert_success_marker_present(baseline, leaf_hi)
    assert_usage_class(unknown, group_hi)
    assert_usage_class(unknown, leaf_hi)


def test_missing_required_is_usage_class_skips_callback():
    greeting = _greeting()
    flag = f"--{_word()}"
    dest = _word()
    value = _word()
    leaf = _greet_leaf(greeting, option(flag, dest, required=True))
    baseline = _dispatch(leaf, [flag, value])
    missing = _dispatch(leaf, [])
    print(f"flag={flag!r}", flush=True)
    assert_success_marker_present(baseline, greeting)
    assert_usage_class(missing, greeting)


def test_conversion_failure_is_usage_class_skips_callback():
    greeting = _greeting()
    flag = f"--{_word()}"
    dest = _word()
    illegal = unrelated_dispatch_token(greeting, flag, dest)
    good = _runtime_int()

    def callback(**kwargs) -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_word()}_{_word()}"
    leaf = _cmd(callback, option(flag, dest, type=INT))
    baseline = _dispatch(leaf, [flag, str(good)])
    failed = _dispatch(leaf, [flag, illegal])
    print(f"illegal={illegal!r} good={good}", flush=True)
    assert_success_marker_present(baseline, greeting)
    assert_usage_class(failed, greeting)


def test_extra_token_is_usage_class_skips_callback():
    greeting = _greeting()
    extra = unrelated_dispatch_token(greeting)
    leaf = _greet_leaf(greeting)
    baseline = _dispatch(leaf, [])
    failed = _dispatch(leaf, [extra])
    print(f"extra={extra!r}", flush=True)
    assert_success_marker_present(baseline, greeting)
    assert_usage_class(failed, greeting)


def test_option_missing_value_is_usage_class_skips_callback():
    greeting = _greeting()
    flag = f"--{_word()}"
    dest = _word()
    value = _word()
    leaf = _greet_leaf(greeting, option(flag, dest))
    baseline = _dispatch(leaf, [flag, value])
    failed = _dispatch(leaf, [flag])
    print(f"flag={flag!r}", flush=True)
    assert_success_marker_present(baseline, greeting)
    assert_usage_class(failed, greeting)


def test_missing_subcommand_help_is_usage_not_intentional_help():
    group_hi = _greeting()
    leaf_hi = _greeting()
    desc = _desc("G")
    child_name = f"c-{_word()}"

    def root() -> None:
        print(group_hi, flush=True)

    root.__name__ = f"{_word()}_{_word()}"
    root.__doc__ = desc
    cli = _grp(root)
    cli.add_command(_greet_leaf(leaf_hi, name=child_name))
    missing = _dispatch(cli, [])
    helped = _dispatch(cli, ["--help"])
    print(f"desc={desc!r}", flush=True)
    assert_usage_help(missing, group_hi, desc)
    assert leaf_hi not in missing.stdout_text
    assert leaf_hi not in missing.stderr_text
    assert missing.stderr_text.strip(), (
        "missing-subcommand help produced empty stderr; "
        f"stdout={missing.stdout_text!r} stderr={missing.stderr_text!r}"
    )
    assert_intentional_help(helped, group_hi, desc)
    assert missing.exit_code != helped.exit_code, (
        "missing-subcommand help and --help share an exit status; "
        f"missing={missing.exit_code} help={helped.exit_code}"
    )


# ---------------------------------------------------------------------------
# C. Parameter usage identifies the offending parameter
# ---------------------------------------------------------------------------


def test_missing_required_option_identifies_the_option():
    greeting = _greeting()
    shared = _word()
    flag_a = f"--{_word()}"
    flag_b = f"--{_word()}"
    dest = _word()
    assert len({flag_a, flag_b, shared, greeting}) == 4

    def cb_a(**kwargs) -> None:
        print(greeting, flush=True)

    def cb_b(**kwargs) -> None:
        print(greeting, flush=True)

    cb_a.__name__ = f"{_word()}_{_word()}"
    cb_b.__name__ = f"{_word()}_{_word()}"
    fail_a = _dispatch(
        _cmd(cb_a, option(flag_a, dest, required=True), name=shared), []
    )
    fail_b = _dispatch(
        _cmd(cb_b, option(flag_b, dest, required=True), name=shared), []
    )
    print(f"a={flag_a!r} b={flag_b!r} shared={shared!r}", flush=True)
    assert_usage_class(fail_a, greeting)
    assert_usage_class(fail_b, greeting)
    assert_usage_names_option(fail_a, greeting, flag_a)
    assert_usage_names_option(fail_b, greeting, flag_b)
    assert flag_b not in fail_a.stderr_text, (
        f"missing-required for {flag_a!r} named sibling {flag_b!r}; "
        f"stderr={fail_a.stderr_text!r}"
    )
    assert flag_a not in fail_b.stderr_text, (
        f"missing-required for {flag_b!r} named sibling {flag_a!r}; "
        f"stderr={fail_b.stderr_text!r}"
    )
    rest_a = usage_stderr_remainder(fail_a, greeting, PROG)
    rest_b = usage_stderr_remainder(fail_b, greeting, PROG)
    assert rest_a != rest_b, (
        "missing-required option remainders are not distinct after "
        f"stripping greeting and prog; a={rest_a!r} b={rest_b!r}"
    )


def test_missing_required_argument_identifies_the_argument():
    greeting = _greeting()
    shared = _word()
    dest_a = _word()
    dest_b = _word()
    assert len({dest_a, dest_b, shared, greeting}) == 4

    def cb_a(**kwargs) -> None:
        print(greeting, flush=True)

    def cb_b(**kwargs) -> None:
        print(greeting, flush=True)

    cb_a.__name__ = f"{_word()}_{_word()}"
    cb_b.__name__ = f"{_word()}_{_word()}"
    fail_a = _dispatch(_cmd(cb_a, argument(dest_a), name=shared), [])
    fail_b = _dispatch(_cmd(cb_b, argument(dest_b), name=shared), [])
    print(f"dest_a={dest_a!r} dest_b={dest_b!r} shared={shared!r}", flush=True)
    assert_usage_names_argument(fail_a, greeting, dest_a)
    assert_usage_names_argument(fail_b, greeting, dest_b)
    assert dest_b.casefold() not in fail_a.stderr_text.casefold(), (
        f"missing-required for {dest_a!r} named sibling {dest_b!r}; "
        f"stderr={fail_a.stderr_text!r}"
    )
    assert dest_a.casefold() not in fail_b.stderr_text.casefold(), (
        f"missing-required for {dest_b!r} named sibling {dest_a!r}; "
        f"stderr={fail_b.stderr_text!r}"
    )


def test_conversion_failure_identifies_the_parameter():
    greeting = _greeting()
    shared = _word()
    flag_a = f"--{_word()}"
    flag_b = f"--{_word()}"
    dest = _word()
    dest_ok = _word()
    dest_bad = _word()
    illegal = unrelated_dispatch_token(greeting, flag_a, flag_b, dest)
    good = _runtime_int()
    assert len({flag_a, flag_b, shared}) == 3

    def typed_a(**kwargs) -> None:
        print(greeting, flush=True)

    def typed_b(**kwargs) -> None:
        print(greeting, flush=True)

    typed_a.__name__ = f"{_word()}_{_word()}"
    typed_b.__name__ = f"{_word()}_{_word()}"
    fail_a = _dispatch(
        _cmd(typed_a, option(flag_a, dest, type=INT), name=shared),
        [flag_a, illegal],
    )
    fail_b = _dispatch(
        _cmd(typed_b, option(flag_b, dest, type=INT), name=shared),
        [flag_b, illegal],
    )
    print(f"a={flag_a!r} b={flag_b!r} illegal={illegal!r}", flush=True)
    assert_usage_class(fail_a, greeting)
    assert_usage_class(fail_b, greeting)
    assert_usage_names_option(fail_a, greeting, flag_a)
    assert_usage_names_option(fail_b, greeting, flag_b)
    assert flag_b not in fail_a.stderr_text
    assert flag_a not in fail_b.stderr_text

    def half(**kwargs) -> None:
        print(greeting, flush=True)

    half.__name__ = f"{_word()}_{_word()}"
    half_cli = _cmd(
        half,
        option(flag_a, dest_ok, type=INT),
        option(flag_b, dest_bad, type=INT),
    )
    half_fail = _dispatch(half_cli, [flag_a, str(good), flag_b, illegal])
    print(f"half={half_fail.stderr_text!r}", flush=True)
    assert_usage_class(half_fail, greeting)


def test_conversion_failure_identifies_the_argument():
    greeting = _greeting()
    shared = _word()
    dest_a = _word()
    dest_b = _word()
    illegal = unrelated_dispatch_token(greeting, dest_a, dest_b, shared)
    assert len({dest_a, dest_b, shared, greeting}) == 4

    def cb_a(**kwargs) -> None:
        print(greeting, flush=True)

    def cb_b(**kwargs) -> None:
        print(greeting, flush=True)

    cb_a.__name__ = f"{_word()}_{_word()}"
    cb_b.__name__ = f"{_word()}_{_word()}"
    fail_a = _dispatch(
        _cmd(cb_a, argument(dest_a, type=INT), name=shared), [illegal]
    )
    fail_b = _dispatch(
        _cmd(cb_b, argument(dest_b, type=INT), name=shared), [illegal]
    )
    print(f"dest_a={dest_a!r} dest_b={dest_b!r} illegal={illegal!r}", flush=True)
    assert_usage_names_argument(fail_a, greeting, dest_a)
    assert_usage_names_argument(fail_b, greeting, dest_b)
    assert dest_b.casefold() not in fail_a.stderr_text.casefold(), (
        f"conversion-failure for {dest_a!r} named sibling {dest_b!r}; "
        f"stderr={fail_a.stderr_text!r}"
    )
    assert dest_a.casefold() not in fail_b.stderr_text.casefold(), (
        f"conversion-failure for {dest_b!r} named sibling {dest_a!r}; "
        f"stderr={fail_b.stderr_text!r}"
    )


def test_unknown_option_need_not_name_a_declared_parameter():
    greeting = _greeting()
    flag = f"--{_word()}"
    dest = _word()
    value = _word()
    unknown = _unknown(greeting, flag, dest)
    leaf = _greet_leaf(greeting, option(flag, dest))
    baseline = _dispatch(leaf, [flag, value])
    failed = _dispatch(leaf, [unknown])
    print(
        f"declared={flag!r} unknown={unknown!r} "
        f"named_declared={flag in failed.stderr_text}",
        flush=True,
    )
    assert_success_marker_present(baseline, greeting)
    assert_usage_class(failed, greeting)


# ---------------------------------------------------------------------------
# D. Abort class exit 1, abort indication, remaining work skipped
# ---------------------------------------------------------------------------


def test_confirm_decline_is_abort_skips_protected_callback():
    greeting = _greeting()
    ask = f"ASK-{uuid.uuid4().hex}"
    decline = "no\n"
    accept = "yes\n"
    unknown = _unknown(greeting, ask)

    def callback() -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_word()}_{_word()}"
    leaf = _cmd(callback, confirmation_option(prompt=ask))
    declined = _dispatch(leaf, [], stdin=decline)
    accepted = _dispatch(leaf, [], stdin=accept)
    usage = _dispatch(leaf, [unknown], stdin=decline)
    print(f"ask={ask!r} unknown={unknown!r}", flush=True)
    assert_success_marker_present(accepted, greeting)
    assert_abort_indication_unlike_usage(
        declined, usage, greeting, ask, decline, decline.strip(), unknown
    )


def test_prompt_eof_is_abort_not_success():
    greeting = _greeting()
    ask = f"ASK-{uuid.uuid4().hex}"
    flag = f"--{_word()}"
    dest = _word()
    value = _word()
    unknown = _unknown(greeting, ask, flag, dest)
    leaf = _greet_leaf(greeting, option(flag, dest, prompt=ask, required=True))
    accepted = _dispatch(leaf, [], stdin=f"{value}\n")
    eof = _dispatch(leaf, [], stdin="")
    usage = _dispatch(leaf, [unknown], stdin="")
    print(f"ask={ask!r} unknown={unknown!r}", flush=True)
    assert_success_marker_present(accepted, greeting)
    assert_abort_indication_unlike_usage(eof, usage, greeting, ask, unknown)


def test_keyboard_interrupt_is_abort_not_success():
    start = _greeting()
    after = f"AFTER:{uuid.uuid4().hex}:"
    unknown = _unknown(start, after)

    def interrupting() -> None:
        print(start, flush=True)
        raise KeyboardInterrupt
        print(after, flush=True)

    def running() -> None:
        print(start, flush=True)
        print(after, flush=True)

    interrupting.__name__ = f"{_word()}_{_word()}"
    running.__name__ = f"{_word()}_{_word()}"
    aborted = _dispatch(_cmd(interrupting), [])
    baseline = _dispatch(_cmd(running), [])
    usage = _dispatch(_cmd(interrupting), [unknown])
    print(f"start={start!r} after={after!r} unknown={unknown!r}", flush=True)
    assert_success_marker_present(baseline, after)
    assert_remaining_skipped(aborted, start, after)
    assert_abort_indication_unlike_usage(
        aborted, usage, after, start, after, unknown
    )


def test_author_abort_skips_remaining_work():
    start = _greeting()
    after = f"AFTER:{uuid.uuid4().hex}:"
    unknown = _unknown(start, after)

    def aborting(ctx) -> None:
        print(start, flush=True)
        ctx.abort()
        print(after, flush=True)

    def running(ctx) -> None:
        print(start, flush=True)
        print(after, flush=True)

    aborting.__name__ = f"{_word()}_{_word()}"
    running.__name__ = f"{_word()}_{_word()}"
    aborted = _dispatch(_cmd(aborting, inject=pass_context), [])
    baseline = _dispatch(_cmd(running, inject=pass_context), [])
    usage = _dispatch(_cmd(aborting, inject=pass_context), [unknown])
    print(f"start={start!r} after={after!r}", flush=True)
    assert_success_marker_present(baseline, after)
    assert_remaining_skipped(aborted, start, after)
    assert_process_exit_not_captured_exception(aborted)
    assert_abort_indication_unlike_usage(
        aborted, usage, after, start, after, unknown
    )


# ---------------------------------------------------------------------------
# E. General error exit 1, not usage 2
# ---------------------------------------------------------------------------


def test_lazy_file_failure_is_general_error_not_usage():
    start = _greeting()
    after = f"AFTER:{uuid.uuid4().hex}:"
    dest = _word()
    dirname = _word()
    filename = f"{_word()}.txt"
    payload = _token()
    unknown = _unknown(start, after, dest, dirname)

    def writing(**kwargs) -> None:
        print(start, flush=True)
        kwargs[dest].write(payload)
        print(after, flush=True)

    writing.__name__ = f"{_word()}_{_word()}"
    cli = _cmd(writing, argument(dest, type=File("w")))

    with workspace() as ws:
        (ws.path / dirname).mkdir()
        if not (ws.path / dirname).is_dir():
            raise RuntimeError(f"failed to create directory {dirname}")
        failed = ws.invoke(cli, [dirname], prog_name=PROG)
        baseline = ws.invoke(cli, [filename], prog_name=PROG)
        usage = ws.invoke(cli, [unknown], prog_name=PROG)
        print(
            f"dir={dirname!r} file={filename!r} "
            f"fail={failed.exit_code}/{failed.stderr_text!r} "
            f"ok={baseline.exit_code} usage={usage.exit_code}",
            flush=True,
        )
    assert_success_marker_present(baseline, start)
    assert_success_marker_present(baseline, after)
    assert_general_file_error_names_path(failed, dirname, start)
    assert after not in failed.stdout_text
    assert after not in failed.stderr_text
    assert_usage_class(usage, start)
    assert failed.exit_code != usage.exit_code, (
        "lazy file failure shared the usage-class exit; "
        f"fail={failed.exit_code} usage={usage.exit_code}"
    )


# ---------------------------------------------------------------------------
# F. Success / usage / abort mutually distinguishable
# ---------------------------------------------------------------------------


def test_success_usage_abort_are_mutually_distinguishable():
    greeting = _greeting()
    ask = f"ASK-{uuid.uuid4().hex}"
    decline = "no\n"
    accept = "yes\n"
    unknown = _unknown(greeting, ask)

    def callback() -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_word()}_{_word()}"
    leaf = _cmd(callback, confirmation_option(prompt=ask))
    success = _dispatch(leaf, [], stdin=accept)
    usage = _dispatch(leaf, [unknown], stdin=decline)
    abort = _dispatch(leaf, [], stdin=decline)
    print(
        f"codes success={success.exit_code} usage={usage.exit_code} "
        f"abort={abort.exit_code}",
        flush=True,
    )
    assert_success_marker_present(success, greeting)
    assert_usage_class(usage, greeting)
    assert_abort_indication_unlike_usage(
        abort, usage, greeting, ask, decline, decline.strip(), unknown
    )
    codes = {success.exit_code, usage.exit_code, abort.exit_code}
    assert codes == {0, 2, 1}, (
        "success/usage/abort exit codes are not the three distinct classes; "
        f"success={success.exit_code} usage={usage.exit_code} "
        f"abort={abort.exit_code}"
    )
    assert success.exit_code != usage.exit_code
    assert success.exit_code != abort.exit_code
    assert usage.exit_code != abort.exit_code


# ---------------------------------------------------------------------------
# G. Standalone mode disabled: failures propagate, return values bubble
# ---------------------------------------------------------------------------


def test_non_standalone_usage_propagates():
    greeting = _greeting()
    unknown = _unknown(greeting)
    leaf = _greet_leaf(greeting)
    standalone = _dispatch(leaf, [unknown], standalone_mode=True)
    assert_usage_class(standalone, greeting)
    exc = assert_failure_propagates(
        lambda: _dispatch(leaf, [unknown], standalone_mode=False)
    )
    print(f"propagated {type(exc).__name__}: {exc}", flush=True)


def test_non_standalone_abort_propagates():
    greeting = _greeting()
    ask = f"ASK-{uuid.uuid4().hex}"
    decline = "no\n"
    unknown = _unknown(greeting, ask)

    def callback() -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_word()}_{_word()}"
    leaf = _cmd(callback, confirmation_option(prompt=ask))
    standalone = _dispatch(leaf, [], stdin=decline, standalone_mode=True)
    usage = _dispatch(leaf, [unknown], stdin=decline, standalone_mode=True)
    assert_abort_indication_unlike_usage(
        standalone, usage, greeting, ask, decline, decline.strip(), unknown
    )
    exc = assert_failure_propagates(
        lambda: _dispatch(
            leaf, [], stdin=decline, standalone_mode=False
        )
    )
    print(f"propagated {type(exc).__name__}: {exc}", flush=True)


def test_non_standalone_general_error_propagates():
    start = _greeting()
    after = f"AFTER:{uuid.uuid4().hex}:"
    dest = _word()
    dirname = _word()
    payload = _token()

    def writing(**kwargs) -> None:
        print(start, flush=True)
        kwargs[dest].write(payload)
        print(after, flush=True)

    writing.__name__ = f"{_word()}_{_word()}"
    cli = _cmd(writing, argument(dest, type=File("w")))

    with workspace() as ws:
        (ws.path / dirname).mkdir()
        if not (ws.path / dirname).is_dir():
            raise RuntimeError(f"failed to create directory {dirname}")
        standalone = ws.invoke(cli, [dirname], prog_name=PROG)
        print(
            f"standalone={standalone.exit_code}/{standalone.stderr_text!r}",
            flush=True,
        )
        assert_general_file_error_names_path(standalone, dirname, start)
        exc = assert_failure_propagates(
            lambda: ws.invoke(
                cli, [dirname], standalone_mode=False, prog_name=PROG
            )
        )
    print(f"propagated {type(exc).__name__}: {exc}", flush=True)


def test_non_standalone_callback_return_bubbles():
    greeting = _greeting()
    unique = _token()

    def callback() -> str:
        print(greeting, flush=True)
        return unique

    callback.__name__ = f"{_word()}_{_word()}"
    leaf = _cmd(callback)
    standalone = _dispatch(leaf, [], standalone_mode=True)
    integrated = _dispatch(leaf, [], standalone_mode=False)
    assert_success_marker_present(standalone, greeting)
    assert standalone.return_value != unique, (
        f"standalone mode leaked the callback return {standalone.return_value!r}"
    )
    assert_success_marker_present(integrated, greeting)
    assert integrated.return_value == unique, (
        f"disabled standalone mode did not return callback value; "
        f"got {integrated.return_value!r}"
    )


def test_non_standalone_clean_stop_bubbles_status():
    start = _greeting()
    after = f"AFTER:{uuid.uuid4().hex}:"
    status = _status_outside_classes()
    assert status not in {0, 1, 2}

    def stop_s(ctx) -> None:
        print(start, flush=True)
        ctx.exit(status)
        print(after, flush=True)

    def stop_one(ctx) -> None:
        print(start, flush=True)
        ctx.exit(1)
        print(after, flush=True)

    def aborting(ctx) -> None:
        print(start, flush=True)
        ctx.abort()
        print(after, flush=True)

    stop_s.__name__ = f"{_word()}_{_word()}"
    stop_one.__name__ = f"{_word()}_{_word()}"
    aborting.__name__ = f"{_word()}_{_word()}"
    bubbled = _dispatch(
        _cmd(stop_s, inject=pass_context), [], standalone_mode=False
    )
    one = _dispatch(
        _cmd(stop_one, inject=pass_context), [], standalone_mode=False
    )
    print(
        f"status={status} bubbled={bubbled.return_value!r} "
        f"one={one.return_value!r} "
        f"bubbled_exc={type(bubbled.exception).__name__ if bubbled.exception else None} "
        f"one_exc={type(one.exception).__name__ if one.exception else None}",
        flush=True,
    )
    assert bubbled.exception is None, (
        "non-standalone clean stop implicitly exited the process; "
        f"exception={type(bubbled.exception).__name__} "
        f"exit={bubbled.exit_code} return={bubbled.return_value!r} "
        f"stdout={bubbled.stdout_text!r} stderr={bubbled.stderr_text!r}"
    )
    assert one.exception is None, (
        "non-standalone clean stop implicitly exited the process; "
        f"exception={type(one.exception).__name__} "
        f"exit={one.exit_code} return={one.return_value!r} "
        f"stdout={one.stdout_text!r} stderr={one.stderr_text!r}"
    )
    assert_remaining_skipped(bubbled, start, after)
    assert_remaining_skipped(one, start, after)
    exc = assert_failure_propagates(
        lambda: _dispatch(
            _cmd(aborting, inject=pass_context), [], standalone_mode=False
        )
    )
    print(f"abort still propagated {type(exc).__name__}: {exc}", flush=True)


def test_non_standalone_chaining_returns_bubble():
    group_hi = _greeting()
    a_hi = _greeting()
    b_hi = _greeting()
    a_name = f"c-{_word()}"
    b_name = f"c-{_word()}"
    t1, t2 = _token(), _token()
    assert t1 != t2

    def root() -> None:
        print(group_hi, flush=True)

    def leaf_a() -> str:
        print(a_hi, flush=True)
        return t1

    def leaf_b() -> str:
        print(b_hi, flush=True)
        return t2

    root.__name__ = f"{_word()}_{_word()}"
    leaf_a.__name__ = f"{_word()}_{_word()}"
    leaf_b.__name__ = f"{_word()}_{_word()}"
    cli = _grp(root, chain=True)
    cli.add_command(_cmd(leaf_a, name=a_name))
    cli.add_command(_cmd(leaf_b, name=b_name))

    standalone = _dispatch(cli, [a_name, b_name], standalone_mode=True)
    ab = _dispatch(cli, [a_name, b_name], standalone_mode=False)
    ba = _dispatch(cli, [b_name, a_name], standalone_mode=False)
    print(
        f"ab={ab.return_value!r} ba={ba.return_value!r} "
        f"standalone={standalone.exit_code}",
        flush=True,
    )
    assert_success_marker_present(standalone, a_hi)
    assert_success_marker_present(standalone, b_hi)
    assert standalone.exit_code == 0
    assert_positional_items(ab.return_value, t1, t2)
    assert_positional_items(ba.return_value, t2, t1)
