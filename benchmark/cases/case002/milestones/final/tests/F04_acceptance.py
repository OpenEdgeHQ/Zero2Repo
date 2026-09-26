# feature: F04
"""FP-04: read `.env` bindings as a mapping without mutating the process environment.

Assertions stay at the PRD's precision: one source's mapping; absent names
stay absent and present names keep their previous values; no-value versus
empty string versus missing; empty or missing file completes with an empty
mapping; path / stream / FIFO / no-arg source selection as in FP-03;
PYTHON_ENVFILE_DISABLED does not gate this entry; default expansion uses
override-on order (source values beat the process environment) and can be
turned off. Success/failure booleans, None, log wording, and exception
types are not pinned.
"""

from __future__ import annotations

from io import StringIO

from envfile import envfile_values, load_envfile

from _harness import call, product_package_name, workspace
from _helpers import (
    environ_value,
    require_absent,
    require_binding,
    require_call_completed,
    require_empty_mapping,
    require_empty_string,
    require_environ_absent,
    require_labeled_line,
    require_mapping,
    require_no_value,
    require_script_success,
    unique_token,
)

DISABLE_SWITCH = "PYTHON_ENVFILE_DISABLED"


def _no_arg_has_mapping_source(pkg: str, name: str) -> str:
    return (
        f"from {pkg} import envfile_values\n"
        "mapping = envfile_values()\n"
        f"print('HAS=' + ('1' if {name!r} in mapping else '0'))\n"
        f"print('MAP=' + ('' if {name!r} not in mapping else str(mapping[{name!r}])))\n"
    )


def _no_arg_mapping_source(pkg: str, name: str, runtime_name: str) -> str:
    return (
        f"from {pkg} import envfile_values\n"
        "import os\n"
        "mapping = envfile_values()\n"
        f"print('HAS=' + ('1' if {name!r} in mapping else '0'))\n"
        f"print('MAP=' + ('' if {name!r} not in mapping else str(mapping[{name!r}])))\n"
        f"print('RT_HAS=' + ('1' if {runtime_name!r} in mapping else '0'))\n"
        f"print('RT_MAP=' + ('' if {runtime_name!r} not in mapping else str(mapping[{runtime_name!r}])))\n"
        f"print('ENV_HAS=' + ('1' if {name!r} in os.environ else '0'))\n"
        f"print('RT_ENV_HAS=' + ('1' if {runtime_name!r} in os.environ else '0'))\n"
    )


def _no_arg_present_source(pkg: str, name: str) -> str:
    return (
        f"from {pkg} import envfile_values\n"
        "import os\n"
        "mapping = envfile_values()\n"
        f"print('HAS=' + ('1' if {name!r} in mapping else '0'))\n"
        f"print('MAP=' + ('' if {name!r} not in mapping else str(mapping[{name!r}])))\n"
        f"print('ENV_HAS=' + ('1' if {name!r} in os.environ else '0'))\n"
        f"print('ENV=' + (os.environ[{name!r}] if {name!r} in os.environ else ''))\n"
    )


def _require_locatable_mapping(
    ws, pkg: str, name: str, value: str, *, label: str
) -> None:
    baseline = ws.run_script(
        _no_arg_has_mapping_source(pkg, name),
        relpath="baseline.py",
        cwd=ws.path,
    )
    stdout = require_script_success(baseline, label=label)
    has = require_labeled_line(stdout, "HAS", origin=label)
    mapped = require_labeled_line(stdout, "MAP", origin=label)
    assert has == "1", f"no-arg mapping missed locatable {name!r}"
    assert mapped == value, (
        f"no-arg mapping recorded {mapped!r}, not locatable {value!r}"
    )


def _brace(name: str) -> str:
    return "${" + name + "}"


# ---------------------------------------------------------------------------
# A. One source's mapping; process environment unchanged
# ---------------------------------------------------------------------------


def test_file_a_equals_b_mapping_does_not_write():
    with workspace() as ws:
        path = ws.write("public.env", "a=b\n")
        mapped = call(envfile_values, envfile_path=str(path))
        loaded = call(load_envfile, envfile_path=str(path))
    print("file a=b mapping does not write; load baseline writes", flush=True)
    mapping = require_mapping(mapped, origin="file a=b")
    assert require_binding(mapping, "a") == "b"
    require_environ_absent(mapped, "a")
    require_call_completed(loaded, origin="load live baseline a=b")
    assert environ_value(loaded, "a") == "b"


def test_runtime_file_mapping_absent_stays_absent():
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        path = ws.write("runtime.env", f"{name}={value}\n")
        mapped = call(envfile_values, envfile_path=str(path))
        loaded = call(load_envfile, envfile_path=str(path))
    print(f"runtime file {name}={value} mapping; load baseline writes", flush=True)
    mapping = require_mapping(mapped, origin="runtime file")
    assert require_binding(mapping, name) == value
    require_environ_absent(mapped, name)
    require_call_completed(loaded, origin="load live baseline runtime")
    assert environ_value(loaded, name) == value


def test_present_env_name_unchanged_mapping_has_file_value():
    name, old, new = unique_token(), unique_token(), unique_token()
    with workspace() as ws:
        public_path = ws.write("public.env", "a=b\n")
        runtime_path = ws.write("runtime.env", f"{name}={new}\n")
        public = call(envfile_values, envfile_path=str(public_path), env={"a": "c"})
        runtime = call(
            envfile_values, envfile_path=str(runtime_path), env={name: old}
        )
    print("present a=c vs file a=b; runtime OLD vs NEW", flush=True)
    public_mapping = require_mapping(public, origin="present public")
    assert require_binding(public_mapping, "a") == "b"
    assert environ_value(public, "a") == "c"
    runtime_mapping = require_mapping(runtime, origin="present runtime")
    assert require_binding(runtime_mapping, name) == new
    assert environ_value(runtime, name) == old


def test_env_only_name_not_in_mapping():
    name, value = unique_token(), unique_token()
    other, other_val = unique_token(), unique_token()
    with workspace() as ws:
        path = ws.write("one.env", f"{name}={value}\n")
        result = call(
            envfile_values,
            envfile_path=str(path),
            env={other: other_val},
        )
    print(f"env-only {other!r} must not enter mapping", flush=True)
    mapping = require_mapping(result, origin="env-only name")
    assert require_binding(mapping, name) == value
    require_absent(mapping, other)
    assert environ_value(result, other) == other_val
    require_environ_absent(result, name)


def test_two_bindings_one_source_neither_written():
    n1, v1 = unique_token(), unique_token()
    n2, v2 = unique_token(), unique_token()
    with workspace() as ws:
        path = ws.write("two.env", f"{n1}={v1}\n{n2}={v2}\n")
        result = call(envfile_values, envfile_path=str(path))
    print(f"two bindings {n1!r} {n2!r}", flush=True)
    mapping = require_mapping(result, origin="two bindings")
    assert require_binding(mapping, n1) == v1
    assert require_binding(mapping, n2) == v2
    require_environ_absent(result, n1)
    require_environ_absent(result, n2)


def test_sibling_file_not_merged():
    name_a, val_a = unique_token(), unique_token()
    name_b, val_b = unique_token(), unique_token()
    with workspace() as ws:
        path_a = ws.write("a.env", f"{name_a}={val_a}\n")
        ws.write("b.env", f"{name_b}={val_b}\n")
        result = call(envfile_values, envfile_path=str(path_a))
    print(f"sibling {name_b!r} must not merge into {name_a!r}", flush=True)
    mapping = require_mapping(result, origin="sibling file")
    assert require_binding(mapping, name_a) == val_a
    require_absent(mapping, name_b)
    require_environ_absent(result, name_a)
    require_environ_absent(result, name_b)


# ---------------------------------------------------------------------------
# B. No-value is present-with-no-value; empty string; neither is copied
# ---------------------------------------------------------------------------


def test_foo_no_value_in_mapping_not_in_environ():
    with workspace() as ws:
        path = ws.write("novalue.env", "FOO\n")
        result = call(envfile_values, envfile_path=str(path))
    print("no-value line FOO in mapping, not in environ", flush=True)
    mapping = require_mapping(result, origin="FOO no-value")
    recorded = require_no_value(mapping, "FOO")
    require_environ_absent(result, "FOO")
    assert "FOO" in mapping, (
        f"name-only FOO is absent (not a no-value binding); keys={list(mapping)!r}"
    )
    assert recorded != "", (
        f"name-only FOO recorded {recorded!r}, not no-value"
    )
    assert "FOO" not in result.environ, (
        f"no-value FOO was written {result.environ.get('FOO')!r}; "
        f"keys={sorted(result.environ)!r}"
    )


def test_foo_empty_string_in_mapping_not_in_environ():
    with workspace() as ws:
        path = ws.write("empty-string.env", "FOO=\n")
        mapped = call(envfile_values, envfile_path=str(path))
        loaded = call(load_envfile, envfile_path=str(path))
    print("FOO= empty string in mapping; load baseline writes empty", flush=True)
    mapping = require_mapping(mapped, origin="FOO=")
    require_empty_string(mapping, "FOO")
    require_environ_absent(mapped, "FOO")
    require_call_completed(loaded, origin="load live baseline FOO=")
    assert environ_value(loaded, "FOO") == ""


def test_runtime_three_way_mapping_and_no_copy():
    name = unique_token()
    other, other_val = unique_token(), unique_token()
    with workspace() as ws:
        no_value = call(
            envfile_values,
            envfile_path=str(ws.write("nv.env", f"{name}\n")),
        )
        empty = call(
            envfile_values,
            envfile_path=str(ws.write("es.env", f"{name}=\n")),
        )
        absent = call(
            envfile_values,
            envfile_path=str(
                ws.write("other.env", f"{other}={other_val}\n")
            ),
        )
    print(f"runtime three-way name={name!r}", flush=True)
    nv_mapping = require_mapping(no_value, origin="runtime no-value")
    recorded_nv = require_no_value(nv_mapping, name)
    require_environ_absent(no_value, name)
    es_mapping = require_mapping(empty, origin="runtime empty-string")
    recorded_es = require_empty_string(es_mapping, name)
    require_environ_absent(empty, name)
    assert recorded_nv != recorded_es, (
        f"no-value and empty-string collapsed to {recorded_nv!r}"
    )
    absent_mapping = require_mapping(absent, origin="runtime absent")
    require_absent(absent_mapping, name)
    assert require_binding(absent_mapping, other) == other_val
    require_environ_absent(absent, name)
    require_environ_absent(absent, other)


# ---------------------------------------------------------------------------
# C. Path, stream, FIFO, no-arg locate; source selection as FP-03
# ---------------------------------------------------------------------------


def test_stream_a_equals_b_no_write():
    result = call(envfile_values, stream=StringIO("a=b\n"))
    print("stream a=b mapping does not write", flush=True)
    mapping = require_mapping(result, origin="stream a=b")
    assert require_binding(mapping, "a") == "b"
    require_environ_absent(result, "a")


def test_runtime_stream_no_write():
    n1, v1 = unique_token(), unique_token()
    n2, v2 = unique_token(), unique_token()
    text = f"{n1}={v1}\n{n2}={v2}\n"
    result = call(envfile_values, stream=StringIO(text))
    print(f"runtime stream {n1!r} {n2!r}", flush=True)
    mapping = require_mapping(result, origin="runtime stream")
    assert require_binding(mapping, n1) == v1
    assert require_binding(mapping, n2) == v2
    require_environ_absent(result, n1)
    require_environ_absent(result, n2)


def test_stream_present_env_name_unchanged_mapping_has_source_value():
    name, old, new = unique_token(), unique_token(), unique_token()
    result = call(
        envfile_values,
        stream=StringIO(f"{name}={new}\n"),
        env={name: old},
    )
    print(f"stream present {name!r} OLD vs NEW", flush=True)
    mapping = require_mapping(result, origin="stream present")
    assert require_binding(mapping, name) == new
    assert environ_value(result, name) == old


def test_readable_path_preferred_over_stream():
    other = unique_token()
    runtime_file, runtime_file_val = unique_token(), unique_token()
    runtime_stream, runtime_stream_val = unique_token(), unique_token()
    with workspace() as ws:
        path = ws.write(
            "fromfile.env",
            f"TOKEN=fromfile\n{runtime_file}={runtime_file_val}\n",
        )
        result = call(
            envfile_values,
            envfile_path=str(path),
            stream=StringIO(
                f"TOKEN=fromstream\nOTHER=fromstream\n"
                f"{other}=fromstream\n{runtime_stream}={runtime_stream_val}\n"
            ),
        )
    print("readable path preferred over stream", flush=True)
    mapping = require_mapping(result, origin="path over stream")
    assert require_binding(mapping, "TOKEN") == "fromfile"
    assert require_binding(mapping, runtime_file) == runtime_file_val
    require_absent(mapping, "OTHER")
    require_absent(mapping, other)
    require_absent(mapping, runtime_stream)
    require_environ_absent(result, "TOKEN")
    require_environ_absent(result, runtime_file)
    require_environ_absent(result, "OTHER")
    require_environ_absent(result, other)
    require_environ_absent(result, runtime_stream)


def test_readable_fifo_preferred_over_stream():
    fromfifo, fifo_val, stream_val = unique_token(), unique_token(), unique_token()
    fromstream, fromstream_val = unique_token(), unique_token()
    old = unique_token()
    with workspace() as ws:
        with ws.fifo("pipe.env", f"{fromfifo}={fifo_val}\n") as fifo:
            result = call(
                envfile_values,
                envfile_path=str(fifo),
                stream=StringIO(
                    f"{fromfifo}={stream_val}\n{fromstream}={fromstream_val}\n"
                ),
                env={fromfifo: old},
            )
    print(f"FIFO preferred over stream {fromfifo!r}", flush=True)
    mapping = require_mapping(result, origin="fifo over stream")
    recorded = require_binding(mapping, fromfifo)
    assert recorded == fifo_val
    assert recorded != old
    assert recorded != stream_val
    require_absent(mapping, fromstream)
    assert environ_value(result, fromfifo) == old
    require_environ_absent(result, fromstream)


def test_empty_readable_file_does_not_fall_through_to_stream():
    fromstream, value = unique_token(), unique_token()
    other, other_val = unique_token(), unique_token()
    stream_text = f"{fromstream}={value}\n"
    shared_env = {other: other_val}
    with workspace() as ws:
        empty = ws.write("empty.env", "")
        missing = ws.resolve(f"{unique_token()}.env")
        baseline = call(
            envfile_values,
            envfile_path=str(missing),
            stream=StringIO(stream_text),
            env=shared_env,
        )
        result = call(
            envfile_values,
            envfile_path=str(empty),
            stream=StringIO(stream_text),
            env=shared_env,
        )
    print(f"empty file must not read stream {fromstream!r}", flush=True)
    baseline_mapping = require_mapping(
        baseline, origin="same stream when path is not a readable file"
    )
    assert require_binding(baseline_mapping, fromstream) == value
    mapping = require_empty_mapping(result, origin="empty file + stream")
    require_absent(mapping, fromstream)
    require_environ_absent(result, fromstream)
    assert environ_value(result, other) == other_val
    assert dict(mapping) != dict(baseline_mapping), (
        f"empty readable path mapping {dict(mapping)!r} is not distinguishable "
        f"from that same stream when the path is not a readable file "
        f"({dict(baseline_mapping)!r})"
    )


def test_missing_path_falls_back_to_stream():
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        missing = ws.resolve(f"{unique_token()}.env")
        result = call(
            envfile_values,
            envfile_path=str(missing),
            stream=StringIO(f"{name}={value}\n"),
        )
    print(f"missing path falls back to stream {name!r}", flush=True)
    mapping = require_mapping(result, origin="missing path + stream")
    assert require_binding(mapping, name) == value
    require_environ_absent(result, name)


def test_directory_path_falls_back_to_stream():
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        directory = ws.mkdir(unique_token())
        result = call(
            envfile_values,
            envfile_path=str(directory),
            stream=StringIO(f"{name}={value}\n"),
        )
    print(f"directory path falls back to stream {name!r}", flush=True)
    mapping = require_mapping(result, origin="directory path + stream")
    assert require_binding(mapping, name) == value
    require_environ_absent(result, name)


def test_stream_outranks_locatable_env():
    fromfile, fromfile_val = unique_token(), unique_token()
    fromstream, fromstream_val = unique_token(), unique_token()
    pkg = product_package_name()
    with workspace() as ws:
        ws.write(".env", f"{fromfile}={fromfile_val}\n")
        _require_locatable_mapping(
            ws, pkg, fromfile, fromfile_val, label="stream-outranks-baseline"
        )
        result = call(
            envfile_values,
            stream=StringIO(f"{fromstream}={fromstream_val}\n"),
            cwd=str(ws.path),
            isolate=False,
            env=ws.env,
        )
    print(
        f"stream {fromstream!r} outranks locatable {fromfile!r}",
        flush=True,
    )
    mapping = require_mapping(result, origin="stream vs locate")
    assert require_binding(mapping, fromstream) == fromstream_val
    require_absent(mapping, fromfile)
    require_environ_absent(result, fromstream)
    require_environ_absent(result, fromfile)


def test_empty_stream_does_not_locate():
    fromfile, fromfile_val = unique_token(), unique_token()
    pkg = product_package_name()
    with workspace() as ws:
        ws.write(".env", f"{fromfile}={fromfile_val}\n")
        _require_locatable_mapping(
            ws, pkg, fromfile, fromfile_val, label="empty-stream-baseline"
        )
        result = call(
            envfile_values,
            stream=StringIO(""),
            cwd=str(ws.path),
            isolate=False,
            env=ws.env,
        )
    print(f"empty stream must not locate {fromfile!r}", flush=True)
    mapping = require_empty_mapping(result, origin="empty stream")
    require_absent(mapping, fromfile)
    require_environ_absent(result, fromfile)


def test_no_arg_mapping_adjacent_script_no_write():
    pkg = product_package_name()
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        folder = unique_token()
        ws.write(f"{folder}/.env", f"a=b\n{name}={value}\n")
        work = ws.resolve(folder)
        result = ws.run_script(
            _no_arg_mapping_source(pkg, "a", name),
            relpath=f"{folder}/caller.py",
            cwd=work,
        )
        stdout = require_script_success(result, label="no-arg-adjacent")
        has = require_labeled_line(stdout, "HAS", origin="no-arg-adjacent")
        mapped = require_labeled_line(stdout, "MAP", origin="no-arg-adjacent")
        rt_has = require_labeled_line(stdout, "RT_HAS", origin="no-arg-adjacent")
        rt_map = require_labeled_line(stdout, "RT_MAP", origin="no-arg-adjacent")
        env_has = require_labeled_line(stdout, "ENV_HAS", origin="no-arg-adjacent")
        rt_env_has = require_labeled_line(
            stdout, "RT_ENV_HAS", origin="no-arg-adjacent"
        )
    print("no-arg mapping adjacent script a=b + runtime", flush=True)
    assert has == "1", "no-arg mapping missed a"
    assert mapped == "b"
    assert rt_has == "1", f"no-arg mapping missed {name!r}"
    assert rt_map == value
    assert env_has == "0", f"no-arg mapping wrote a into the process environment"
    assert rt_env_has == "0", (
        f"no-arg mapping wrote {name!r} into the process environment"
    )


def test_no_arg_present_env_name_unchanged_mapping_has_file_value():
    pkg = product_package_name()
    name, old, new = unique_token(), unique_token(), unique_token()
    with workspace() as ws:
        folder = unique_token()
        ws.write(f"{folder}/.env", f"{name}={new}\n")
        work = ws.resolve(folder)
        result = ws.run_script(
            _no_arg_present_source(pkg, name),
            relpath=f"{folder}/caller.py",
            cwd=work,
            env={name: old},
        )
        stdout = require_script_success(result, label="no-arg-present")
        has = require_labeled_line(stdout, "HAS", origin="no-arg-present")
        mapped = require_labeled_line(stdout, "MAP", origin="no-arg-present")
        env_has = require_labeled_line(stdout, "ENV_HAS", origin="no-arg-present")
        env = require_labeled_line(stdout, "ENV", origin="no-arg-present")
    print(f"no-arg present {name!r} OLD vs NEW", flush=True)
    assert has == "1", f"no-arg mapping missed {name!r}"
    assert mapped == new
    assert env_has == "1", f"seeded {name!r} missing from child environ"
    assert env == old, f"no-arg mapping overwrote environ {env!r}, not {old!r}"


# ---------------------------------------------------------------------------
# D. Empty / missing path: empty mapping, completes, environment unchanged
# ---------------------------------------------------------------------------


def test_empty_file_empty_mapping_completes():
    other, other_val = unique_token(), unique_token()
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        empty = ws.write("empty.env", "")
        filled = ws.write("filled.env", f"{name}={value}\n")
        empty_result = call(
            envfile_values,
            envfile_path=str(empty),
            env={other: other_val},
        )
        filled_result = call(
            envfile_values,
            envfile_path=str(filled),
            env={other: other_val},
        )
    print("empty file empty mapping; filled live baseline", flush=True)
    require_empty_mapping(empty_result, origin="empty file")
    assert empty_result.exception is None
    assert environ_value(empty_result, other) == other_val
    require_environ_absent(empty_result, name)
    filled_mapping = require_mapping(filled_result, origin="filled live baseline")
    assert require_binding(filled_mapping, name) == value


def test_missing_path_empty_mapping_completes():
    other, other_val = unique_token(), unique_token()
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        missing = ws.resolve(f"{unique_token()}.env")
        filled = ws.write("filled.env", f"{name}={value}\n")
        missing_result = call(
            envfile_values,
            envfile_path=str(missing),
            env={other: other_val},
        )
        filled_result = call(
            envfile_values,
            envfile_path=str(filled),
            env={other: other_val},
        )
    print(f"missing path {missing} empty mapping", flush=True)
    require_empty_mapping(missing_result, origin="missing path")
    assert missing_result.exception is None
    assert environ_value(missing_result, other) == other_val
    require_environ_absent(missing_result, name)
    filled_mapping = require_mapping(filled_result, origin="filled live baseline")
    assert require_binding(filled_mapping, name) == value


def test_explicit_missing_path_does_not_locate():
    fromfile, fromfile_val = unique_token(), unique_token()
    other, other_val = unique_token(), unique_token()
    pkg = product_package_name()
    with workspace() as ws:
        ws.write(".env", f"{fromfile}={fromfile_val}\n")
        missing = ws.resolve(f"{unique_token()}.env")
        _require_locatable_mapping(
            ws, pkg, fromfile, fromfile_val, label="missing-no-locate-baseline"
        )
        env = dict(ws.env)
        env[other] = other_val
        result = call(
            envfile_values,
            envfile_path=str(missing),
            cwd=str(ws.path),
            isolate=False,
            env=env,
        )
    print(f"explicit missing path must not locate {fromfile!r}", flush=True)
    mapping = require_empty_mapping(result, origin="explicit missing")
    require_absent(mapping, fromfile)
    assert result.exception is None
    assert environ_value(result, other) == other_val
    require_environ_absent(result, fromfile)


# ---------------------------------------------------------------------------
# E. PYTHON_ENVFILE_DISABLED does not gate this entry
# ---------------------------------------------------------------------------


def test_disable_true_still_returns_file_bindings():
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        path = ws.write("disabled.env", f"a=b\n{name}={value}\n")
        mapped = call(
            envfile_values,
            envfile_path=str(path),
            env={DISABLE_SWITCH: "true"},
        )
        loaded = call(
            load_envfile,
            envfile_path=str(path),
            env={DISABLE_SWITCH: "true"},
        )
        enabled_load = call(load_envfile, envfile_path=str(path))
    print("disable true still returns file bindings and does not write", flush=True)
    mapping = require_mapping(mapped, origin="disable true")
    assert require_binding(mapping, "a") == "b"
    assert require_binding(mapping, name) == value
    require_environ_absent(mapped, "a")
    require_environ_absent(mapped, name)
    assert environ_value(mapped, DISABLE_SWITCH) == "true"
    require_environ_absent(loaded, "a")
    require_environ_absent(loaded, name)
    require_call_completed(enabled_load, origin="disable load baseline")
    assert environ_value(enabled_load, name) == value


def test_disable_one_still_returns_and_does_not_write():
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        path = ws.write("disabled-one.env", f"{name}={value}\n")
        mapped = call(
            envfile_values,
            envfile_path=str(path),
            env={DISABLE_SWITCH: "1"},
        )
        loaded = call(
            load_envfile,
            envfile_path=str(path),
            env={DISABLE_SWITCH: "1"},
        )
    print("disable 1 still returns runtime pair and does not write", flush=True)
    mapping = require_mapping(mapped, origin="disable 1")
    assert require_binding(mapping, name) == value
    require_environ_absent(mapped, name)
    assert environ_value(mapped, DISABLE_SWITCH) == "1"
    require_environ_absent(loaded, name)


def test_disable_still_returns_stream_bindings():
    name, value = unique_token(), unique_token()
    result = call(
        envfile_values,
        stream=StringIO(f"{name}={value}\n"),
        env={DISABLE_SWITCH: "true"},
    )
    print(f"disable true still returns stream {name!r}", flush=True)
    mapping = require_mapping(result, origin="disable stream")
    assert require_binding(mapping, name) == value
    require_environ_absent(result, name)
    assert environ_value(result, DISABLE_SWITCH) == "true"


def test_disable_does_not_strip_default_expansion():
    token_name, token_val = unique_token(), unique_token()
    literal = _brace(token_name)
    with workspace() as ws:
        path = ws.write("expand.env", f"a={literal}\n")
        result = call(
            envfile_values,
            envfile_path=str(path),
            env={DISABLE_SWITCH: "true", token_name: token_val},
        )
    print(
        f"disable true still expands a={literal} using {token_name!r}",
        flush=True,
    )
    mapping = require_mapping(result, origin="disable expansion")
    recorded = require_binding(mapping, "a")
    assert recorded == token_val
    assert recorded != literal
    require_environ_absent(result, "a")
    assert environ_value(result, token_name) == token_val
    assert environ_value(result, DISABLE_SWITCH) == "true"


# ---------------------------------------------------------------------------
# F. Default expansion on; off leaves literal; source value beats environment
# ---------------------------------------------------------------------------


def test_expansion_on_by_default_uses_env():
    token_name, token_val = unique_token(), unique_token()
    with workspace() as ws:
        public_path = ws.write("public.env", "a=${b}\n")
        runtime_path = ws.write("runtime.env", f"a={_brace(token_name)}\n")
        public = call(envfile_values, envfile_path=str(public_path), env={"b": "c"})
        runtime = call(
            envfile_values,
            envfile_path=str(runtime_path),
            env={token_name: token_val},
        )
    print(
        f"default expansion on: a=${{b}} with b=c; a={_brace(token_name)}",
        flush=True,
    )
    public_mapping = require_mapping(public, origin="expansion default public")
    recorded_public = require_binding(public_mapping, "a")
    assert recorded_public == "c"
    assert recorded_public != "${b}"
    require_environ_absent(public, "a")
    assert environ_value(public, "b") == "c"
    runtime_mapping = require_mapping(runtime, origin="expansion default runtime")
    recorded_runtime = require_binding(runtime_mapping, "a")
    assert recorded_runtime == token_val
    assert recorded_runtime != _brace(token_name)
    require_environ_absent(runtime, "a")


def test_expansion_off_leaves_dollar_brace_literal():
    token_name, token_val = unique_token(), unique_token()
    with workspace() as ws:
        public_path = ws.write("public.env", "a=${b}\n")
        runtime_path = ws.write("runtime.env", f"a={_brace(token_name)}\n")
        public_off = call(
            envfile_values,
            envfile_path=str(public_path),
            env={"b": "c"},
            interpolate=False,
        )
        runtime_off = call(
            envfile_values,
            envfile_path=str(runtime_path),
            env={token_name: token_val},
            interpolate=False,
        )
        public_on = call(
            envfile_values, envfile_path=str(public_path), env={"b": "c"}
        )
    print(
        f"expansion off: public ${{b}}; runtime {_brace(token_name)}",
        flush=True,
    )
    public_off_mapping = require_mapping(public_off, origin="expansion off public")
    recorded_off = require_binding(public_off_mapping, "a")
    assert recorded_off == "${b}"
    require_environ_absent(public_off, "a")
    runtime_off_mapping = require_mapping(
        runtime_off, origin="expansion off runtime"
    )
    assert require_binding(runtime_off_mapping, "a") == _brace(token_name)
    require_environ_absent(runtime_off, "a")
    public_on_mapping = require_mapping(public_on, origin="expansion on baseline")
    recorded_on = require_binding(public_on_mapping, "a")
    assert recorded_on == "c"
    assert recorded_on != recorded_off


def test_expansion_file_value_beats_process_environment():
    name, file_val, env_val = unique_token(), unique_token(), unique_token()
    ref = unique_token()
    with workspace() as ws:
        public_path = ws.write("public.env", "b=d\na=${b}\n")
        runtime_path = ws.write(
            "runtime.env",
            f"{name}={file_val}\n{ref}={_brace(name)}\n",
        )
        public = call(envfile_values, envfile_path=str(public_path), env={"b": "c"})
        runtime = call(
            envfile_values,
            envfile_path=str(runtime_path),
            env={name: env_val},
        )
    print(
        f"file value beats env: b=d then a=${{b}}; {name}={file_val} then {ref}",
        flush=True,
    )
    public_mapping = require_mapping(public, origin="file beats env public")
    assert require_binding(public_mapping, "b") == "d"
    recorded_a = require_binding(public_mapping, "a")
    assert recorded_a == "d"
    assert recorded_a != "c"
    assert environ_value(public, "b") == "c"
    require_environ_absent(public, "a")
    runtime_mapping = require_mapping(runtime, origin="file beats env runtime")
    recorded_ref = require_binding(runtime_mapping, ref)
    assert recorded_ref == file_val
    assert recorded_ref != env_val
    assert environ_value(runtime, name) == env_val
    require_environ_absent(runtime, ref)


def test_stream_expansion_on_by_default_uses_env():
    token_name, token_val = unique_token(), unique_token()
    result = call(
        envfile_values,
        stream=StringIO(f"a={_brace(token_name)}\n"),
        env={token_name: token_val},
    )
    print(f"stream default expansion a={_brace(token_name)}", flush=True)
    mapping = require_mapping(result, origin="stream expansion on")
    recorded = require_binding(mapping, "a")
    assert recorded == token_val
    assert recorded != _brace(token_name)
    require_environ_absent(result, "a")
    assert environ_value(result, token_name) == token_val


def test_stream_expansion_off_leaves_dollar_brace_literal():
    token_name, token_val = unique_token(), unique_token()
    text = f"a={_brace(token_name)}\n"
    off = call(
        envfile_values,
        stream=StringIO(text),
        env={token_name: token_val},
        interpolate=False,
    )
    on = call(
        envfile_values,
        stream=StringIO(text),
        env={token_name: token_val},
    )
    print(f"stream expansion off {_brace(token_name)}", flush=True)
    off_mapping = require_mapping(off, origin="stream expansion off")
    recorded_off = require_binding(off_mapping, "a")
    assert recorded_off == _brace(token_name)
    require_environ_absent(off, "a")
    on_mapping = require_mapping(on, origin="stream expansion on baseline")
    recorded_on = require_binding(on_mapping, "a")
    assert recorded_on == token_val
    assert recorded_on != recorded_off
    require_environ_absent(on, "a")


def test_stream_expansion_source_value_beats_process_environment():
    name, file_val, env_val = unique_token(), unique_token(), unique_token()
    ref = unique_token()
    result = call(
        envfile_values,
        stream=StringIO(f"{name}={file_val}\n{ref}={_brace(name)}\n"),
        env={name: env_val},
    )
    print(f"stream source value beats env {name!r} then {ref!r}", flush=True)
    mapping = require_mapping(result, origin="stream beats env")
    recorded_ref = require_binding(mapping, ref)
    assert recorded_ref == file_val
    assert recorded_ref != env_val
    assert require_binding(mapping, name) == file_val
    assert environ_value(result, name) == env_val
    require_environ_absent(result, ref)
