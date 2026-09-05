# feature: F08
"""FP-08: envfile run — start a program with .env values in its environment.

Assertions stay at the PRD's precision: child stdout and exit status,
default override-on, --no-override / --override, no-value lines not
exported, --file vs cwd, tokens after run belonging to the child,
--version before run not starting the child, missing-file invalid
--file vs no-command vs command-not-found, run does not create a
.env file, and run does not write delivered names into a surviving
caller's process environment. Exit numbers 1/2, Click types, and
English sentence spellings are not pinned.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from _harness import HarnessError, RunResult, Workspace, product_package_name
from _helpers import (
    child_argv_probe_source,
    child_environ_probe_source,
    cli_invoke,
    cli_streams,
    installed_distribution_version,
    require_cli_success,
    require_cli_unsuccessful,
    require_independent_line,
    require_labeled_line,
    require_script_success,
    require_surviving_caller_unchanged,
    strip_cli_covariates,
    strip_path_covariates,
    unique_token,
)

PROBE_SCRIPT = "probe.py"
ARGV_SCRIPT = "argv_probe.py"
PUBLIC_MISSING_PROGRAM = "i_do_not_exist"


def _require_missing_file(ws: Workspace, relpath: str, *, origin: str) -> None:
    try:
        data = ws.read_bytes(relpath)
    except FileNotFoundError:
        print(f"{origin} still missing {relpath}", flush=True)
        return
    raise AssertionError(f"{origin} created {relpath}: {data!r}")


def _unlink_workspace_file(ws: Workspace, relpath: str) -> None:
    path = ws.resolve(relpath)
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise HarnessError(f"cannot unlink {path}: {exc}") from exc


def _require_nonempty_report(result: RunResult, *, origin: str) -> str:
    text = cli_streams(result)
    assert text, f"{origin} has empty operator-visible report"
    return text


def _printenv_of(ws: Workspace, name: str, value: str) -> str:
    result = ws.run_command(["printenv", name], env={name: value})
    if result.returncode != 0:
        raise HarnessError(
            f"printenv {name!r} of known value exited {result.returncode}; "
            f"stderr={result.stderr_text!r} stdout={result.stdout_text!r}"
        )
    print(f"live printenv {name!r} -> {result.stdout_text!r}", flush=True)
    return result.stdout_text


def _require_printenv_absent(
    ws: Workspace, name: str, forbidden: str, *, origin: str
) -> None:
    result = ws.run_command(["printenv", name])
    print(
        f"{origin} subsequent printenv rc={result.returncode} "
        f"stdout={result.stdout_text!r} stderr={result.stderr_text!r}",
        flush=True,
    )
    assert forbidden not in result.stdout_text.splitlines(), (
        f"{origin} subsequent process printed file value {forbidden!r}"
    )
    if result.returncode == 0:
        raise AssertionError(
            f"{origin} subsequent printenv succeeded; {name!r} should be absent"
        )
    if result.stdout_text != "":
        raise HarnessError(
            f"{origin} printenv non-zero with stdout {result.stdout_text!r}; "
            "not documented absence"
        )


def _require_stdout_is_printenv_value(
    stdout: str, ws: Workspace, name: str, value: str, *, origin: str
) -> None:
    expected = _printenv_of(ws, name, value)
    assert stdout == expected, (
        f"{origin} stdout {stdout!r} is not printenv of {value!r} ({expected!r})"
    )
    print(f"{origin} matched live printenv {name!r}={value!r}", flush=True)


def _require_name_off_child_line(name: str, tokens: Sequence[str], *, origin: str) -> None:
    for token in tokens:
        assert token != name, f"{origin} child argv contains independent {name!r}"
        if len(name) >= 8:
            assert name not in token, (
                f"{origin} child argv token {token!r} contains {name!r}"
            )


def _write_probe(ws: Workspace, names: Sequence[str], *, relpath: str = PROBE_SCRIPT) -> Path:
    source = child_environ_probe_source(names)
    path = ws.write(relpath, source)
    print(f"wrote environ probe {relpath} names={list(names)!r}", flush=True)
    return path


def _write_argv_probe(ws: Workspace, *, relpath: str = ARGV_SCRIPT) -> Path:
    path = ws.write(relpath, child_argv_probe_source())
    print(f"wrote argv probe {relpath}", flush=True)
    return path


def _probe_has(stdout: str, name: str, expected: str, *, origin: str) -> str:
    recorded = require_labeled_line(stdout, f"HAS_{name}", origin=origin)
    assert recorded == expected, (
        f"{origin} HAS_{name}={recorded!r}, expected {expected!r}"
    )
    return recorded


def _probe_val(stdout: str, name: str, expected: str, *, origin: str) -> str:
    recorded = require_labeled_line(stdout, f"VAL_{name}", origin=origin)
    assert recorded == expected, (
        f"{origin} VAL_{name}={recorded!r}, expected {expected!r}"
    )
    return recorded


def _run_environ_probe(
    ws: Workspace,
    names: Sequence[str],
    run_args: Sequence[str],
    *,
    origin: str,
    env: Mapping[str, str] | None = None,
    cwd: str | Path | None = None,
) -> str:
    _write_probe(ws, names)
    interpreter = sys.executable
    for name in names:
        _require_name_off_child_line(
            name, [interpreter, PROBE_SCRIPT, *run_args], origin=origin
        )
    result = cli_invoke(
        ws,
        ["run", *run_args, interpreter, PROBE_SCRIPT],
        env=env,
        cwd=cwd,
    )
    stdout = require_cli_success(result, origin=origin)
    return stdout


def _marker_rel() -> str:
    return f"ran-{unique_token()}.marker"


def _caller_source(
    package: str, name: str, *, extra: Sequence[str] = ()
) -> str:
    extra_list = "[" + ", ".join(repr(item) for item in extra) + "]"
    return (
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        f"_NAME = {name!r}\n"
        "print('BEFORE_HAS=' + ('1' if _NAME in os.environ else '0'))\n"
        f"_cmd = [sys.executable, '-m', {package!r}, *{extra_list}, "
        "'run', '--', 'printenv', _NAME]\n"
        "proc = subprocess.run(\n"
        "    _cmd,\n"
        "    check=False,\n"
        "    stdout=subprocess.PIPE,\n"
        "    stderr=subprocess.PIPE,\n"
        ")\n"
        "out = proc.stdout.decode('utf-8')\n"
        "first = out.splitlines()[0] if out.splitlines() else ''\n"
        "print('CHILD_RC=' + str(proc.returncode))\n"
        "print('CHILD_LINE=' + first)\n"
        "print('SURVIVING_CALLER_HAS=' + ('1' if _NAME in os.environ else '0'))\n"
        "print('SURVIVING_CALLER_VAL=' + (os.environ[_NAME] if _NAME in os.environ else ''))\n"
    )


# ---------------------------------------------------------------------------
# A. child sees .env bindings; stdout and status from the child; no caller write
# ---------------------------------------------------------------------------


def test_run_starts_child_with_env_values_and_forwards_child_status(isolated_ws):
    ws = isolated_ws
    n2, v2 = unique_token(), unique_token()
    ws.write(".env", f"A=x\n{n2}={v2}\n")
    caller_before = dict(os.environ)

    with_sep = require_cli_success(
        cli_invoke(ws, ["run", "--", "printenv", "A"]),
        origin="run -- printenv A",
    )
    _require_stdout_is_printenv_value(with_sep, ws, "A", "x", origin="run -- printenv A")
    require_surviving_caller_unchanged(
        "A", caller_before, origin="run -- printenv A surviving caller"
    )

    without_sep = require_cli_success(
        cli_invoke(ws, ["run", "printenv", "A"]),
        origin="run printenv A",
    )
    _require_stdout_is_printenv_value(
        without_sep, ws, "A", "x", origin="run printenv A"
    )
    require_surviving_caller_unchanged(
        "A", caller_before, origin="run printenv A surviving caller"
    )

    rt = require_cli_success(
        cli_invoke(ws, ["run", "--", "printenv", n2]),
        origin="run -- printenv runtime",
    )
    _require_stdout_is_printenv_value(rt, ws, n2, v2, origin="run -- printenv runtime")
    require_surviving_caller_unchanged(
        n2, caller_before, origin="run -- printenv runtime surviving caller"
    )

    probe_out = _run_environ_probe(
        ws, ["A", n2], [], origin="unnamed runtime binding probe"
    )
    _probe_has(probe_out, "A", "1", origin="unnamed probe A")
    _probe_val(probe_out, "A", "x", origin="unnamed probe A")
    _probe_has(probe_out, n2, "1", origin="unnamed probe runtime")
    _probe_val(probe_out, n2, v2, origin="unnamed probe runtime")

    code7 = cli_invoke(ws, ["run", sys.executable, "-c", "raise SystemExit(7)"])
    print(f"SystemExit(7) rc={code7.returncode}", flush=True)
    assert code7.returncode == 7, (
        f"envfile rc {code7.returncode} is not the child's 7"
    )
    code11 = cli_invoke(ws, ["run", sys.executable, "-c", "raise SystemExit(11)"])
    print(f"SystemExit(11) rc={code11.returncode}", flush=True)
    assert code11.returncode == 11, (
        f"envfile rc {code11.returncode} is not the child's 11"
    )
    success_rc = cli_invoke(ws, ["run", "--", "printenv", "A"])
    assert success_rc.returncode == 0, (
        f"successful printenv A rc={success_rc.returncode}, not 0"
    )

    pkg = product_package_name(root=ws.root)
    wrapped = ws.run_script(_caller_source(pkg, "A"), relpath="wrapper.py")
    wrap_out = require_script_success(wrapped, label="caller wrapper A")
    assert require_labeled_line(wrap_out, "BEFORE_HAS", origin="wrapper A") == "0"
    assert require_labeled_line(wrap_out, "CHILD_RC", origin="wrapper A") == "0"
    assert require_labeled_line(wrap_out, "CHILD_LINE", origin="wrapper A") == "x"
    assert require_labeled_line(wrap_out, "SURVIVING_CALLER_HAS", origin="wrapper A") == "0", (
        "run wrote A into the surviving caller's process environment"
    )

    wrap_rt = ws.run_script(
        _caller_source(pkg, n2), relpath="wrapper_runtime.py"
    )
    wrap_rt_out = require_script_success(wrap_rt, label="caller wrapper runtime")
    assert require_labeled_line(wrap_rt_out, "BEFORE_HAS", origin="wrapper runtime") == "0"
    assert require_labeled_line(wrap_rt_out, "CHILD_RC", origin="wrapper runtime") == "0"
    assert require_labeled_line(wrap_rt_out, "CHILD_LINE", origin="wrapper runtime") == v2
    assert require_labeled_line(
        wrap_rt_out, "SURVIVING_CALLER_HAS", origin="wrapper runtime"
    ) == "0", (
        "run wrote the child-delivered name into the surviving caller's "
        "process environment"
    )

    side_rel = f"caller-file-{unique_token()}.env"
    side_name, side_val = unique_token(), unique_token()
    ws.write(side_rel, f"{side_name}={side_val}\n")
    wrap_file = ws.run_script(
        _caller_source(pkg, side_name, extra=("--file", side_rel)),
        relpath="wrapper_file.py",
    )
    wrap_file_out = require_script_success(wrap_file, label="caller wrapper --file")
    assert require_labeled_line(wrap_file_out, "BEFORE_HAS", origin="wrapper --file") == "0"
    assert require_labeled_line(wrap_file_out, "CHILD_RC", origin="wrapper --file") == "0"
    assert require_labeled_line(wrap_file_out, "CHILD_LINE", origin="wrapper --file") == side_val
    assert require_labeled_line(
        wrap_file_out, "SURVIVING_CALLER_HAS", origin="wrapper --file"
    ) == "0", (
        "run --file wrote the child-delivered name into the surviving "
        "caller's process environment"
    )

    _require_printenv_absent(ws, "A", "x", origin="after run A")
    _require_printenv_absent(ws, n2, v2, origin="after run runtime")
    _require_printenv_absent(ws, side_name, side_val, origin="after run --file")


# ---------------------------------------------------------------------------
# B. default override-on; --no-override inherited wins; --override restores
# ---------------------------------------------------------------------------


def test_run_overrides_inherited_names_by_default_and_honors_no_override(isolated_ws):
    ws = isolated_ws
    n_conflict, file_val, inherited_val = unique_token(), unique_token(), unique_token()
    n_file_only, file_only_val = unique_token(), unique_token()
    n_inherited, inherited_only_val = unique_token(), unique_token()
    ws.write(
        ".env",
        f"A=x\n{n_conflict}={file_val}\n{n_file_only}={file_only_val}\n",
    )
    inherited = {
        "A": "y",
        n_conflict: inherited_val,
        n_inherited: inherited_only_val,
    }

    default_public = require_cli_success(
        cli_invoke(ws, ["run", "--", "printenv", "A"], env=inherited),
        origin="default override printenv A",
    )
    _require_stdout_is_printenv_value(
        default_public, ws, "A", "x", origin="default override printenv A"
    )
    default_rt = require_cli_success(
        cli_invoke(ws, ["run", "--", "printenv", n_conflict], env=inherited),
        origin="default override printenv runtime",
    )
    _require_stdout_is_printenv_value(
        default_rt, ws, n_conflict, file_val, origin="default override printenv runtime"
    )

    names = ["A", n_conflict, n_file_only, n_inherited]
    default_probe = _run_environ_probe(
        ws, names, [], origin="default override probe", env=inherited
    )
    _probe_val(default_probe, "A", "x", origin="default probe A")
    _probe_val(default_probe, n_conflict, file_val, origin="default probe conflict")
    _probe_has(default_probe, n_file_only, "1", origin="default probe file-only")
    _probe_val(default_probe, n_file_only, file_only_val, origin="default probe file-only")
    _probe_has(default_probe, n_inherited, "1", origin="default probe inherited-only")
    _probe_val(
        default_probe, n_inherited, inherited_only_val, origin="default probe inherited-only"
    )

    no_over_public = require_cli_success(
        cli_invoke(
            ws, ["run", "--no-override", "--", "printenv", "A"], env=inherited
        ),
        origin="--no-override printenv A",
    )
    _require_stdout_is_printenv_value(
        no_over_public, ws, "A", "y", origin="--no-override printenv A"
    )
    no_over_rt = require_cli_success(
        cli_invoke(
            ws,
            ["run", "--no-override", "--", "printenv", n_conflict],
            env=inherited,
        ),
        origin="--no-override printenv runtime",
    )
    _require_stdout_is_printenv_value(
        no_over_rt,
        ws,
        n_conflict,
        inherited_val,
        origin="--no-override printenv runtime",
    )

    no_over_probe = _run_environ_probe(
        ws, names, ["--no-override"], origin="--no-override probe", env=inherited
    )
    _probe_val(no_over_probe, "A", "y", origin="--no-override probe A")
    _probe_val(
        no_over_probe, n_conflict, inherited_val, origin="--no-override probe conflict"
    )
    _probe_has(no_over_probe, n_file_only, "1", origin="--no-override probe file-only")
    _probe_val(
        no_over_probe, n_file_only, file_only_val, origin="--no-override probe file-only"
    )
    _probe_val(
        no_over_probe,
        n_inherited,
        inherited_only_val,
        origin="--no-override probe inherited-only",
    )

    over_probe = _run_environ_probe(
        ws, names, ["--override"], origin="--override probe", env=inherited
    )
    _probe_val(over_probe, "A", "x", origin="--override probe A")
    _probe_val(over_probe, n_conflict, file_val, origin="--override probe conflict")
    _probe_has(over_probe, n_file_only, "1", origin="--override probe file-only")
    _probe_has(over_probe, n_inherited, "1", origin="--override probe inherited-only")
    _probe_val(
        over_probe, n_inherited, inherited_only_val, origin="--override probe inherited-only"
    )


# ---------------------------------------------------------------------------
# C. no-value line not exported; --file selects a non-cwd source
# ---------------------------------------------------------------------------


def test_run_skips_no_value_and_file_flag_selects_source(isolated_ws):
    ws = isolated_ws
    nv_rt = unique_token()
    ws.write(".env", f"A=x\nc\n{nv_rt}\n")
    caller_before = dict(os.environ)

    printed = require_cli_success(
        cli_invoke(ws, ["run", "--", "printenv", "A"]),
        origin="no-value file printenv A",
    )
    _require_stdout_is_printenv_value(
        printed, ws, "A", "x", origin="no-value file printenv A"
    )

    probe_out = _run_environ_probe(
        ws, ["A", "c", nv_rt], [], origin="no-value probe"
    )
    _probe_has(probe_out, "A", "1", origin="no-value probe A")
    _probe_val(probe_out, "A", "x", origin="no-value probe A")
    _probe_has(probe_out, "c", "0", origin="no-value probe c")
    _probe_val(probe_out, "c", "", origin="no-value probe c")
    _probe_has(probe_out, nv_rt, "0", origin="no-value probe runtime")
    _probe_val(probe_out, nv_rt, "", origin="no-value probe runtime")

    _unlink_workspace_file(ws, ".env")
    _require_missing_file(ws, ".env", origin="before --file bypass")
    side_rel = f"side-{unique_token()}.env"
    ws.write(side_rel, "A=x\n")
    bypass = require_cli_success(
        cli_invoke(ws, ["--file", side_rel, "run", "--", "printenv", "A"]),
        origin="--file bypass without cwd .env",
    )
    _require_stdout_is_printenv_value(
        bypass, ws, "A", "x", origin="--file bypass without cwd .env"
    )
    require_surviving_caller_unchanged(
        "A", caller_before, origin="--file bypass surviving caller"
    )

    cwd_val, side_rt_val = unique_token(), unique_token()
    file_only, file_only_val = unique_token(), unique_token()
    ws.write(".env", f"A={cwd_val}\n")
    ws.write(side_rel, f"A=x\nN={side_rt_val}\n{file_only}={file_only_val}\n")
    via_file = require_cli_success(
        cli_invoke(ws, ["--file", side_rel, "run", "--", "printenv", "A"]),
        origin="--file vs cwd via --file",
    )
    _require_stdout_is_printenv_value(
        via_file, ws, "A", "x", origin="--file vs cwd via --file"
    )
    require_surviving_caller_unchanged(
        "A", caller_before, origin="--file vs cwd surviving caller"
    )
    omitted = require_cli_success(
        cli_invoke(ws, ["run", "--", "printenv", "A"]),
        origin="--file vs cwd omitted --file",
    )
    _require_stdout_is_printenv_value(
        omitted, ws, "A", cwd_val, origin="--file vs cwd omitted --file"
    )
    via_file_rt = require_cli_success(
        cli_invoke(ws, ["--file", side_rel, "run", "--", "printenv", "N"]),
        origin="--file vs cwd runtime side name",
    )
    _require_stdout_is_printenv_value(
        via_file_rt, ws, "N", side_rt_val, origin="--file vs cwd runtime side name"
    )
    via_file_only = require_cli_success(
        cli_invoke(
            ws, ["--file", side_rel, "run", "--", "printenv", file_only]
        ),
        origin="--file vs cwd unique side name",
    )
    _require_stdout_is_printenv_value(
        via_file_only,
        ws,
        file_only,
        file_only_val,
        origin="--file vs cwd unique side name",
    )
    require_surviving_caller_unchanged(
        file_only,
        caller_before,
        origin="--file unique surviving caller",
    )


# ---------------------------------------------------------------------------
# D. tokens after run belong to the child; --version before run does not start it
# ---------------------------------------------------------------------------


def test_run_passes_child_flags_and_version_before_run_does_not_start_child(isolated_ws):
    ws = isolated_ws
    version = installed_distribution_version()
    file_rel = f"ver-{unique_token()}.env"
    ws.write(file_rel, "A=x\n")
    ws.write(".env", "A=x\n")

    child_ver = require_cli_success(
        cli_invoke(ws, ["--file", file_rel, "run", "printenv", "--version"]),
        origin="run printenv --version",
    )
    direct = ws.run_command(["printenv", "--version"])
    if direct.returncode != 0:
        raise HarnessError(
            f"direct printenv --version exited {direct.returncode}; "
            f"stderr={direct.stderr_text!r} stdout={direct.stdout_text!r}"
        )
    print(f"direct printenv --version {direct.stdout_text!r}", flush=True)
    assert child_ver == direct.stdout_text, (
        "run printenv --version stdout is not the live printenv --version text"
    )
    envfile_ver = require_cli_success(
        cli_invoke(ws, ["--version"]), origin="envfile --version"
    )
    assert child_ver != envfile_ver, (
        "child --version text is indistinguishable from envfile --version"
    )
    assert envfile_ver.rstrip("\n").endswith(version), (
        f"envfile --version {envfile_ver!r} does not end with {version!r}"
    )

    file_token = unique_token()
    _write_argv_probe(ws)
    after_file = require_cli_success(
        cli_invoke(
            ws, ["run", sys.executable, ARGV_SCRIPT, "--file", file_token]
        ),
        origin="child argv --file token",
    )
    require_independent_line(after_file, "ARGV=--file", origin="child argv --file")
    require_independent_line(
        after_file, f"ARGV={file_token}", origin="child argv file token"
    )
    _require_missing_file(ws, file_token, origin="--file token is not a path")

    inherited = {"A": "y"}
    _write_probe(ws, ["A"])
    after_no_over = require_cli_success(
        cli_invoke(
            ws,
            ["run", sys.executable, PROBE_SCRIPT, "--no-override"],
            env=inherited,
        ),
        origin="child argv --no-override environ",
    )
    _probe_val(after_no_over, "A", "x", origin="child --no-override still overrides")
    _write_argv_probe(ws)
    after_no_over_argv = require_cli_success(
        cli_invoke(
            ws,
            ["run", sys.executable, ARGV_SCRIPT, "--no-override"],
            env=inherited,
        ),
        origin="child argv --no-override argv",
    )
    require_independent_line(
        after_no_over_argv,
        "ARGV=--no-override",
        origin="child argv --no-override",
    )

    marker = _marker_rel()
    _require_missing_file(ws, marker, origin="version-before-run marker start")
    before = require_cli_success(
        cli_invoke(ws, ["--version", "run", "touch", marker]),
        origin="--version before run with .env",
    )
    assert before.rstrip("\n").endswith(version), (
        f"--version before run printed {before!r}, not ending with {version!r}"
    )
    _require_missing_file(ws, marker, origin="--version before run must not start child")
    assert before.rstrip("\n") != "x", (
        "--version before run printed the child's A=x value"
    )

    combo = require_cli_success(
        cli_invoke(
            ws,
            ["--version", "--file", file_rel, "run", "printenv", "--version"],
        ),
        origin="--version before run printenv --version",
    )
    assert combo.rstrip("\n").endswith(version), (
        f"--version before run+printenv --version printed {combo!r}, "
        f"not ending with {version!r}"
    )
    assert combo != direct.stdout_text, (
        "--version before run still produced printenv --version text"
    )


# ---------------------------------------------------------------------------
# E. missing file is invalid --file; existing file: no command / not found;
#    empty file still starts; run does not create .env
# ---------------------------------------------------------------------------


def test_run_missing_env_is_invalid_file_without_starting_child(isolated_ws):
    ws = isolated_ws
    ws.write(".env", f"A=x\n{unique_token()}={unique_token()}\n")
    marker_ok = _marker_rel()
    _require_missing_file(ws, marker_ok, origin="baseline marker start")
    require_cli_success(
        cli_invoke(ws, ["run", "touch", marker_ok]),
        origin="baseline run touch",
    )
    ws.read_bytes(marker_ok)
    print(f"baseline touch created {marker_ok}", flush=True)

    found_missing_prog = require_cli_unsuccessful(
        cli_invoke(ws, ["run", PUBLIC_MISSING_PROGRAM]),
        origin="file exists + i_do_not_exist",
    )
    found_missing_report = _require_nonempty_report(
        found_missing_prog, origin="file exists + i_do_not_exist"
    )
    found_no_cmd = require_cli_unsuccessful(
        cli_invoke(ws, ["run"]), origin="file exists + no command"
    )
    found_no_cmd_report = _require_nonempty_report(
        found_no_cmd, origin="file exists + no command"
    )

    _unlink_workspace_file(ws, ".env")
    _require_missing_file(ws, ".env", origin="after unlink cwd .env")

    marker_missing = _marker_rel()
    missing_touch = require_cli_unsuccessful(
        cli_invoke(ws, ["run", "touch", marker_missing]),
        origin="no .env + touch",
    )
    missing_touch_report = _require_nonempty_report(
        missing_touch, origin="no .env + touch"
    )
    _require_missing_file(ws, marker_missing, origin="no .env must not start touch")
    _require_missing_file(ws, ".env", origin="no .env + touch must not create .env")

    missing_prog = require_cli_unsuccessful(
        cli_invoke(ws, ["run", PUBLIC_MISSING_PROGRAM]),
        origin="no .env + i_do_not_exist",
    )
    missing_prog_report = _require_nonempty_report(
        missing_prog, origin="no .env + i_do_not_exist"
    )
    paths = [ws.path, ".env"]
    prog_tokens = (PUBLIC_MISSING_PROGRAM, "run", "touch", marker_missing)
    missing_vs_found = strip_cli_covariates(
        missing_prog_report, paths, prog_tokens
    )
    found_stripped = strip_cli_covariates(
        found_missing_report, paths, prog_tokens
    )
    assert missing_vs_found, "missing-file report is only path/argv echo"
    assert found_stripped, "command-not-found report is only path/argv echo"
    assert missing_vs_found != found_stripped, (
        "missing .env + i_do_not_exist is indistinguishable from "
        f"command-not-found after stripping: {missing_vs_found!r}"
    )
    _require_missing_file(ws, ".env", origin="no .env + missing program must not create")

    missing_no_cmd = require_cli_unsuccessful(
        cli_invoke(ws, ["run"]), origin="no .env + no command"
    )
    missing_no_cmd_report = _require_nonempty_report(
        missing_no_cmd, origin="no .env + no command"
    )
    no_cmd_tokens = ("run",)
    missing_nocmd_stripped = strip_cli_covariates(
        missing_no_cmd_report, paths, no_cmd_tokens
    )
    found_nocmd_stripped = strip_cli_covariates(
        found_no_cmd_report, paths, no_cmd_tokens
    )
    assert missing_nocmd_stripped, "missing-file no-command report is only echo"
    assert found_nocmd_stripped, "no-command report is only echo"
    assert missing_nocmd_stripped != found_nocmd_stripped, (
        "no .env + run is indistinguishable from no-command after stripping: "
        f"{missing_nocmd_stripped!r}"
    )
    _require_missing_file(ws, ".env", origin="no .env + run must not create")

    invalid_remainder = strip_cli_covariates(missing_touch_report, paths, prog_tokens)
    assert invalid_remainder, "invalid --file remainder is empty after stripping"

    ws.write(".env", "A=x\n")
    missing_rel = f"missing-{unique_token()}.env"
    missing_path = ws.resolve(missing_rel)
    marker_file = _marker_rel()
    bypass_miss = require_cli_unsuccessful(
        cli_invoke(
            ws, ["--file", missing_rel, "run", "--", "printenv", "A"]
        ),
        origin="--file missing with cwd .env",
    )
    bypass_report = _require_nonempty_report(
        bypass_miss, origin="--file missing with cwd .env"
    )
    assert "x" not in bypass_miss.stdout_text.splitlines(), (
        f"--file missing still printed x: {bypass_miss.stdout_text!r}"
    )
    require_cli_unsuccessful(
        cli_invoke(ws, ["--file", missing_rel, "run", "touch", marker_file]),
        origin="--file missing touch",
    )
    _require_missing_file(ws, marker_file, origin="--file missing must not start child")
    _require_missing_file(ws, missing_rel, origin="--file missing must not create target")
    bypass_stripped = strip_cli_covariates(
        bypass_report,
        [ws.path, ".env", missing_path, missing_rel],
        ("--file", "-f", "run", "printenv", "A", missing_rel),
    )
    assert bypass_stripped, "--file missing report is only path/argv echo"
    found_vs_bypass = strip_cli_covariates(
        found_missing_report,
        [ws.path, ".env", missing_path, missing_rel],
        ("--file", "-f", "run", PUBLIC_MISSING_PROGRAM, missing_rel),
    )
    assert bypass_stripped != found_vs_bypass, (
        "--file missing report is indistinguishable from command-not-found"
    )

    leaf = f"sub-{unique_token()}"
    ws.mkdir(leaf)
    walk_marker = _marker_rel()
    walk = require_cli_unsuccessful(
        cli_invoke(ws, ["run", "--", "printenv", "A"], cwd=ws.resolve(leaf)),
        origin="no walk-up printenv A",
    )
    assert "x" not in walk.stdout_text.splitlines(), (
        f"subdirectory run printed parent A=x: {walk.stdout_text!r}"
    )
    require_cli_unsuccessful(
        cli_invoke(
            ws, ["run", "touch", walk_marker], cwd=ws.resolve(leaf)
        ),
        origin="no walk-up touch",
    )
    _require_missing_file(
        ws, f"{leaf}/{walk_marker}", origin="no walk-up must not start child"
    )
    _require_missing_file(ws, f"{leaf}/.env", origin="no walk-up must not create .env")
    walk_report = _require_nonempty_report(walk, origin="no walk-up")
    walk_stripped = strip_cli_covariates(
        walk_report,
        [ws.path, ".env", ws.resolve(leaf), leaf],
        ("run", "printenv", "A"),
    )
    assert walk_stripped, "walk-up failure report is only echo"
    assert walk_stripped != found_stripped, (
        "subdirectory missing .env is indistinguishable from command-not-found"
    )

    dir_rel = f"dir-{unique_token()}"
    ws.mkdir(dir_rel)
    dir_marker = _marker_rel()
    dir_fail = require_cli_unsuccessful(
        cli_invoke(ws, ["--file", dir_rel, "run", "touch", dir_marker]),
        origin="--file directory",
    )
    _require_nonempty_report(dir_fail, origin="--file directory")
    _require_missing_file(ws, dir_marker, origin="--file directory must not start child")
    dir_stripped = strip_cli_covariates(
        cli_streams(dir_fail),
        [ws.path, ".env", ws.resolve(dir_rel), dir_rel],
        ("--file", "-f", "run", "touch", dir_marker, dir_rel),
    )
    assert dir_stripped, "directory --file report is only echo"
    assert dir_stripped != found_stripped, (
        "directory --file is indistinguishable from command-not-found"
    )


def test_run_reports_no_command_or_missing_program_when_file_exists(isolated_ws):
    ws = isolated_ws
    empty_marker = _marker_rel()
    ws.write(".env", "")
    _require_missing_file(ws, empty_marker, origin="empty file marker start")
    require_cli_success(
        cli_invoke(ws, ["run", "touch", empty_marker]),
        origin="empty .env run touch",
    )
    ws.read_bytes(empty_marker)
    print(f"empty .env started child; marker {empty_marker}", flush=True)

    ws.write(".env", f"A=x\n{unique_token()}={unique_token()}\n")
    marker_ok = _marker_rel()
    require_cli_success(
        cli_invoke(ws, ["run", "touch", marker_ok]),
        origin="file exists baseline touch",
    )
    ws.read_bytes(marker_ok)

    no_cmd_marker = _marker_rel()
    _require_missing_file(ws, no_cmd_marker, origin="no-command marker start")
    no_cmd = require_cli_unsuccessful(
        cli_invoke(ws, ["run"]), origin="file exists no command"
    )
    no_cmd_report = _require_nonempty_report(no_cmd, origin="file exists no command")
    _require_missing_file(ws, no_cmd_marker, origin="no command must not create marker")

    missing_rel = f"missing-{unique_token()}.env"
    invalid = require_cli_unsuccessful(
        cli_invoke(ws, ["--file", missing_rel, "run"]),
        origin="invalid --file no command",
    )
    invalid_report = _require_nonempty_report(
        invalid, origin="invalid --file no command"
    )
    _require_missing_file(ws, missing_rel, origin="invalid --file must not create")

    not_found = require_cli_unsuccessful(
        cli_invoke(ws, ["run", PUBLIC_MISSING_PROGRAM]),
        origin="file exists i_do_not_exist",
    )
    not_found_report = _require_nonempty_report(
        not_found, origin="file exists i_do_not_exist"
    )

    paths = [ws.path, ".env", ws.resolve(missing_rel), missing_rel]
    tokens = (PUBLIC_MISSING_PROGRAM, "run", "--file", "-f", missing_rel)
    no_cmd_stripped = strip_cli_covariates(no_cmd_report, paths, tokens)
    invalid_stripped = strip_cli_covariates(invalid_report, paths, tokens)
    not_found_stripped = strip_cli_covariates(not_found_report, paths, tokens)
    assert no_cmd_stripped, "no-command report is only echo"
    assert invalid_stripped, "invalid-file report is only echo"
    assert not_found_stripped, "command-not-found report is only echo"
    assert no_cmd_stripped != invalid_stripped, (
        "no-command report matches invalid --file after stripping"
    )
    assert no_cmd_stripped != not_found_stripped, (
        "no-command report matches command-not-found after stripping"
    )
    assert invalid_stripped != not_found_stripped, (
        "invalid --file matches command-not-found after stripping"
    )

    p1 = f"missing-{unique_token()}"
    p2 = f"missing-{unique_token()}"
    r1 = require_cli_unsuccessful(
        cli_invoke(ws, ["run", p1]), origin="missing program p1"
    )
    r2 = require_cli_unsuccessful(
        cli_invoke(ws, ["run", p2]), origin="missing program p2"
    )
    t1 = _require_nonempty_report(r1, origin="missing program p1")
    t2 = _require_nonempty_report(r2, origin="missing program p2")
    assert t1 != t2, (
        "command-not-found reports do not change when the missing program name changes"
    )
    rest1 = strip_cli_covariates(t1, [ws.path, ".env"], (p1, p2, "run"))
    rest2 = strip_cli_covariates(t2, [ws.path, ".env"], (p1, p2, "run"))
    assert rest1, "command-not-found remainder is empty after stripping names"
    assert rest1 == rest2, (
        f"command-not-found remainders differ after stripping names: "
        f"{rest1!r} vs {rest2!r}"
    )
    assert rest1 != invalid_stripped, (
        "command-not-found remainder matches invalid --file"
    )
    assert rest1 != no_cmd_stripped, (
        "command-not-found remainder matches no-command"
    )

    assert PUBLIC_MISSING_PROGRAM in not_found_report, (
        "public missing-program report does not identify i_do_not_exist"
    )
    assert p1 in t1, f"missing-program report does not identify {p1!r}: {t1!r}"
    assert p2 in t2, f"missing-program report does not identify {p2!r}: {t2!r}"
    print(
        f"no-command/not-found/invalid remainders "
        f"{no_cmd_stripped!r} {not_found_stripped!r} {invalid_stripped!r}",
        flush=True,
    )
