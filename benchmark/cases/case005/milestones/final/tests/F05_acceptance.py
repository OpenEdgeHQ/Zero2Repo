# feature: F05
"""FP-05: variable expansion (${NAME} / ${NAME:-default}).

Assertions stay at the PRD's precision: only braced forms expand; expansion
on (the default) versus off (every dollar-brace sequence stays literal);
surrounding text and reuse; quotes do not suppress expansion; unset versus
present no-value versus empty string versus process-environment empty string;
override-on order (values-mapping, and load with override on) versus
override-off order (load's default); self-reference; a no-value binding is
not expanded. Success/failure booleans, None, log wording, and exception
types are not pinned.
"""

from __future__ import annotations

from io import StringIO

from envfile import envfile_values, load_envfile

from _harness import call
from _helpers import (
    environ_value,
    require_binding,
    require_call_completed,
    require_empty_string,
    require_environ_absent,
    require_mapping,
    require_no_value,
    unique_token,
)

_EXPANSION_OFF = False
_OVERRIDE_ON = True


def _brace(name: str) -> str:
    return "${" + name + "}"


def _brace_default(name: str, default: str) -> str:
    return "${" + name + ":-" + default + "}"


def _mapping(text: str, *, env=None, interpolate=None):
    kwargs = {}
    if env is not None:
        kwargs["env"] = env
    if interpolate is not None:
        kwargs["interpolate"] = interpolate
    result = call(envfile_values, stream=StringIO(text), **kwargs)
    print(
        f"mapping source={text!r} interpolate={interpolate}",
        flush=True,
    )
    return result


def _load(text: str, *, env=None, interpolate=None, override=None):
    kwargs = {}
    if env is not None:
        kwargs["env"] = env
    if interpolate is not None:
        kwargs["interpolate"] = interpolate
    if override is not None:
        kwargs["override"] = override
    result = call(load_envfile, stream=StringIO(text), **kwargs)
    print(
        f"load source={text!r} interpolate={interpolate} override={override}",
        flush=True,
    )
    return result


def _mapped(result, *, origin: str):
    require_call_completed(result, origin=origin)
    return require_mapping(result, origin=origin)


def _loaded(result, *, origin: str):
    return require_call_completed(result, origin=origin)


# ---------------------------------------------------------------------------
# A. Only braced forms expand; bare $NAME is left unchanged
# ---------------------------------------------------------------------------


def test_mapping_bare_dollar_stays_literal_when_braced_expands():
    token, val = unique_token(), unique_token()
    bare = _mapping("a=$b\n", env={"b": "c"})
    braced = _mapping(f"a={_brace('b')}\n", env={"b": "c"})
    rt_bare = _mapping(f"a=${token}\n", env={token: val})
    rt_braced = _mapping(f"a={_brace(token)}\n", env={token: val})
    print("mapping bare $b vs ${b}; runtime $TOKEN vs ${TOKEN}", flush=True)
    bare_map = _mapped(bare, origin="mapping bare $b")
    assert require_binding(bare_map, "a") == "$b"
    braced_map = _mapped(braced, origin="mapping ${b}")
    recorded = require_binding(braced_map, "a")
    assert recorded == "c"
    assert recorded != "$b"
    assert recorded != _brace("b")
    rt_bare_map = _mapped(rt_bare, origin="mapping bare $TOKEN")
    assert require_binding(rt_bare_map, "a") == f"${token}"
    rt_braced_map = _mapped(rt_braced, origin="mapping ${TOKEN}")
    rt_recorded = require_binding(rt_braced_map, "a")
    assert rt_recorded == val
    assert rt_recorded != f"${token}"
    assert rt_recorded != _brace(token)


def test_load_bare_dollar_stays_literal_when_braced_expands():
    token, val = unique_token(), unique_token()
    bare = _load("a=$b\n", env={"b": "c"})
    braced = _load(f"a={_brace('b')}\n", env={"b": "c"})
    rt_bare = _load(f"a=${token}\n", env={token: val})
    rt_braced = _load(f"a={_brace(token)}\n", env={token: val})
    print("load bare $b vs ${b}; runtime $TOKEN vs ${TOKEN}", flush=True)
    _loaded(bare, origin="load bare $b")
    assert environ_value(bare, "a") == "$b"
    _loaded(braced, origin="load ${b}")
    recorded = environ_value(braced, "a")
    assert recorded == "c"
    assert recorded != "$b"
    assert recorded != _brace("b")
    _loaded(rt_bare, origin="load bare $TOKEN")
    assert environ_value(rt_bare, "a") == f"${token}"
    _loaded(rt_braced, origin="load ${TOKEN}")
    rt_recorded = environ_value(rt_braced, "a")
    assert rt_recorded == val
    assert rt_recorded != f"${token}"
    assert rt_recorded != _brace(token)


def test_mapping_bare_dollar_unchanged_with_expansion_off():
    token, val = unique_token(), unique_token()
    public = _mapping("a=$b\n", env={"b": "c"}, interpolate=_EXPANSION_OFF)
    runtime = _mapping(
        f"a=${token}\n", env={token: val}, interpolate=_EXPANSION_OFF
    )
    print("mapping expansion off still leaves $b / $TOKEN", flush=True)
    public_map = _mapped(public, origin="mapping off $b")
    assert require_binding(public_map, "a") == "$b"
    runtime_map = _mapped(runtime, origin="mapping off $TOKEN")
    assert require_binding(runtime_map, "a") == f"${token}"


def test_load_bare_dollar_unchanged_with_expansion_on_and_off():
    token, val = unique_token(), unique_token()
    public_text = "a=$b\n"
    runtime_text = f"a=${token}\n"
    public_on = _load(public_text, env={"b": "c"})
    public_off = _load(public_text, env={"b": "c"}, interpolate=_EXPANSION_OFF)
    runtime_on = _load(runtime_text, env={token: val})
    runtime_off = _load(
        runtime_text, env={token: val}, interpolate=_EXPANSION_OFF
    )
    print(
        "load a=$b with env b=c writes a as $b with expansion on and off",
        flush=True,
    )
    _loaded(public_on, origin="load on $b")
    assert environ_value(public_on, "a") == "$b"
    _loaded(public_off, origin="load off $b")
    assert environ_value(public_off, "a") == "$b"
    _loaded(runtime_on, origin="load on $TOKEN")
    assert environ_value(runtime_on, "a") == f"${token}"
    _loaded(runtime_off, origin="load off $TOKEN")
    assert environ_value(runtime_off, "a") == f"${token}"


# ---------------------------------------------------------------------------
# B. Default expansion on; off leaves the dollar-brace characters
# ---------------------------------------------------------------------------


def test_mapping_brace_on_vs_off():
    token, val = unique_token(), unique_token()
    public_text = f"a={_brace('b')}\n"
    runtime_text = f"a={_brace(token)}\n"
    public_on = _mapping(public_text, env={"b": "c"})
    public_off = _mapping(
        public_text, env={"b": "c"}, interpolate=_EXPANSION_OFF
    )
    runtime_on = _mapping(runtime_text, env={token: val})
    runtime_off = _mapping(
        runtime_text, env={token: val}, interpolate=_EXPANSION_OFF
    )
    print("mapping ${b} / ${TOKEN} on vs off", flush=True)
    on_map = _mapped(public_on, origin="mapping ${b} on")
    on_val = require_binding(on_map, "a")
    assert on_val == "c"
    assert on_val != _brace("b")
    off_map = _mapped(public_off, origin="mapping ${b} off")
    off_val = require_binding(off_map, "a")
    assert off_val == _brace("b")
    assert on_val != off_val
    rt_on_map = _mapped(runtime_on, origin="mapping ${TOKEN} on")
    rt_on = require_binding(rt_on_map, "a")
    assert rt_on == val
    rt_off_map = _mapped(runtime_off, origin="mapping ${TOKEN} off")
    rt_off = require_binding(rt_off_map, "a")
    assert rt_off == _brace(token)
    assert rt_on != rt_off


def test_load_brace_on_vs_off():
    token, val = unique_token(), unique_token()
    public_text = f"a={_brace('b')}\n"
    runtime_text = f"a={_brace(token)}\n"
    public_on = _load(public_text, env={"b": "c"})
    public_off = _load(public_text, env={"b": "c"}, interpolate=_EXPANSION_OFF)
    runtime_on = _load(runtime_text, env={token: val})
    runtime_off = _load(
        runtime_text, env={token: val}, interpolate=_EXPANSION_OFF
    )
    print("load ${b} / ${TOKEN} on vs off", flush=True)
    _loaded(public_on, origin="load ${b} on")
    on_val = environ_value(public_on, "a")
    assert on_val == "c"
    assert on_val != _brace("b")
    _loaded(public_off, origin="load ${b} off")
    off_val = environ_value(public_off, "a")
    assert off_val == _brace("b")
    assert on_val != off_val
    _loaded(runtime_on, origin="load ${TOKEN} on")
    rt_on = environ_value(runtime_on, "a")
    assert rt_on == val
    _loaded(runtime_off, origin="load ${TOKEN} off")
    rt_off = environ_value(runtime_off, "a")
    assert rt_off == _brace(token)
    assert rt_on != rt_off


def test_mapping_brace_default_on_vs_off_even_when_set():
    token, val, default = unique_token(), unique_token(), unique_token()
    public_text = f"a={_brace_default('b', 'd')}\n"
    runtime_text = f"a={_brace_default(token, default)}\n"
    public_on = _mapping(public_text, env={"b": "c"})
    public_off = _mapping(
        public_text, env={"b": "c"}, interpolate=_EXPANSION_OFF
    )
    runtime_on = _mapping(runtime_text, env={token: val})
    runtime_off = _mapping(
        runtime_text, env={token: val}, interpolate=_EXPANSION_OFF
    )
    print("mapping ${b:-d} / ${TOKEN:-DEF} on vs off with name set", flush=True)
    on_map = _mapped(public_on, origin="mapping ${b:-d} on")
    on_val = require_binding(on_map, "a")
    assert on_val == "c"
    assert on_val != "d"
    assert on_val != _brace_default("b", "d")
    off_map = _mapped(public_off, origin="mapping ${b:-d} off")
    off_val = require_binding(off_map, "a")
    assert off_val == _brace_default("b", "d")
    assert on_val != off_val
    rt_on_map = _mapped(runtime_on, origin="mapping ${TOKEN:-DEF} on")
    rt_on = require_binding(rt_on_map, "a")
    assert rt_on == val
    assert rt_on != default
    rt_off_map = _mapped(runtime_off, origin="mapping ${TOKEN:-DEF} off")
    rt_off = require_binding(rt_off_map, "a")
    assert rt_off == _brace_default(token, default)
    assert rt_on != rt_off


def test_load_brace_default_on_vs_off_even_when_set():
    token, val, default = unique_token(), unique_token(), unique_token()
    public_text = f"a={_brace_default('b', 'd')}\n"
    runtime_text = f"a={_brace_default(token, default)}\n"
    public_on = _load(public_text, env={"b": "c"})
    public_off = _load(
        public_text, env={"b": "c"}, interpolate=_EXPANSION_OFF
    )
    runtime_on = _load(runtime_text, env={token: val})
    runtime_off = _load(
        runtime_text, env={token: val}, interpolate=_EXPANSION_OFF
    )
    print("load ${b:-d} / ${TOKEN:-DEF} on vs off with name set", flush=True)
    _loaded(public_on, origin="load ${b:-d} on")
    on_val = environ_value(public_on, "a")
    assert on_val == "c"
    assert on_val != "d"
    assert on_val != _brace_default("b", "d")
    _loaded(public_off, origin="load ${b:-d} off")
    off_val = environ_value(public_off, "a")
    assert off_val == _brace_default("b", "d")
    assert on_val != off_val
    _loaded(runtime_on, origin="load ${TOKEN:-DEF} on")
    rt_on = environ_value(runtime_on, "a")
    assert rt_on == val
    assert rt_on != default
    _loaded(runtime_off, origin="load ${TOKEN:-DEF} off")
    rt_off = environ_value(runtime_off, "a")
    assert rt_off == _brace_default(token, default)
    assert rt_on != rt_off


# ---------------------------------------------------------------------------
# C. Surrounding text kept; reuse; off keeps every interior sequence literal
# ---------------------------------------------------------------------------


def test_mapping_keeps_surrounding_text():
    result = _mapping(f"a=x{_brace('b')}y\n", env={"b": "c"})
    print("mapping a=x${b}y with b=c", flush=True)
    mapping = _mapped(result, origin="mapping x${b}y")
    recorded = require_binding(mapping, "a")
    assert recorded == "xcy"
    assert recorded != f"x{_brace('b')}y"


def test_mapping_reuses_name():
    result = _mapping(f"a={_brace('b')}{_brace('b')}\n", env={"b": "c"})
    print("mapping a=${b}${b} with b=c", flush=True)
    mapping = _mapped(result, origin="mapping ${b}${b}")
    recorded = require_binding(mapping, "a")
    assert recorded == "cc"
    assert recorded != f"{_brace('b')}{_brace('b')}"
    assert recorded != f"c{_brace('b')}"


def test_load_keeps_surrounding_text():
    result = _load(f"a=x{_brace('b')}y\n", env={"b": "c"})
    print("load a=x${b}y with b=c", flush=True)
    _loaded(result, origin="load x${b}y")
    recorded = environ_value(result, "a")
    assert recorded == "xcy"
    assert recorded != f"x{_brace('b')}y"


def test_load_reuses_name():
    result = _load(f"a={_brace('b')}{_brace('b')}\n", env={"b": "c"})
    print("load a=${b}${b} with b=c", flush=True)
    _loaded(result, origin="load ${b}${b}")
    recorded = environ_value(result, "a")
    assert recorded == "cc"
    assert recorded != f"{_brace('b')}{_brace('b')}"
    assert recorded != f"c{_brace('b')}"


def test_runtime_surrounding_and_reuse_mapping():
    token, val = unique_token(), unique_token()
    pre, post = unique_token(), unique_token()
    surrounding = _mapping(
        f"a={pre}{_brace(token)}{post}\n", env={token: val}
    )
    reuse = _mapping(
        f"a={_brace(token)}{_brace(token)}\n", env={token: val}
    )
    print(
        f"runtime surrounding {pre}${{{token}}}{post}; reuse twice",
        flush=True,
    )
    surrounding_map = _mapped(surrounding, origin="runtime surrounding")
    recorded = require_binding(surrounding_map, "a")
    assert recorded == f"{pre}{val}{post}"
    reuse_map = _mapped(reuse, origin="runtime reuse")
    reused = require_binding(reuse_map, "a")
    assert reused == f"{val}{val}"


def test_mapping_interior_sequences_literal_when_expansion_off():
    token, val, default = unique_token(), unique_token(), unique_token()
    pre, post = unique_token(), unique_token()
    public_surround = f"a=x{_brace('b')}y\n"
    public_default = f"a=x{_brace_default('b', 'd')}y\n"
    public_absent = f"a={_brace_default('b', 'd')}\n"
    runtime_surround = f"a={pre}{_brace(token)}{post}\n"
    runtime_default = f"a=x{_brace_default(token, default)}y\n"
    runtime_absent = f"a={_brace_default(token, default)}\n"

    surround_on = _mapping(public_surround, env={"b": "c"})
    surround_off = _mapping(
        public_surround, env={"b": "c"}, interpolate=_EXPANSION_OFF
    )
    default_on = _mapping(public_default, env={"b": "c"})
    default_off = _mapping(
        public_default, env={"b": "c"}, interpolate=_EXPANSION_OFF
    )
    absent_on = _mapping(public_absent)
    absent_off = _mapping(public_absent, interpolate=_EXPANSION_OFF)
    rt_surround_on = _mapping(runtime_surround, env={token: val})
    rt_surround_off = _mapping(
        runtime_surround, env={token: val}, interpolate=_EXPANSION_OFF
    )
    rt_default_on = _mapping(runtime_default, env={token: val})
    rt_default_off = _mapping(
        runtime_default, env={token: val}, interpolate=_EXPANSION_OFF
    )
    rt_absent_on = _mapping(runtime_absent)
    rt_absent_off = _mapping(runtime_absent, interpolate=_EXPANSION_OFF)
    print(
        "mapping off keeps interior ${b}, ${b:-d} in surrounding text, "
        "and absent ${b:-d} / ${TOKEN:-DEF} literal",
        flush=True,
    )

    surround_on_val = require_binding(
        _mapped(surround_on, origin="mapping interior ${b} on"), "a"
    )
    assert surround_on_val == "xcy"
    surround_off_val = require_binding(
        _mapped(surround_off, origin="mapping interior ${b} off"), "a"
    )
    assert surround_off_val == f"x{_brace('b')}y"
    assert surround_on_val != surround_off_val

    default_on_val = require_binding(
        _mapped(default_on, origin="mapping interior ${b:-d} on"), "a"
    )
    assert default_on_val == "xcy"
    assert default_on_val != "xdy"
    default_off_val = require_binding(
        _mapped(default_off, origin="mapping interior ${b:-d} off"), "a"
    )
    assert default_off_val == f"x{_brace_default('b', 'd')}y"
    assert default_on_val != default_off_val

    absent_on_val = require_binding(
        _mapped(absent_on, origin="mapping absent ${b:-d} on"), "a"
    )
    assert absent_on_val == "d"
    absent_off_val = require_binding(
        _mapped(absent_off, origin="mapping absent ${b:-d} off"), "a"
    )
    assert absent_off_val == _brace_default("b", "d")
    assert absent_on_val != absent_off_val

    rt_surround_on_val = require_binding(
        _mapped(rt_surround_on, origin="runtime interior on"), "a"
    )
    assert rt_surround_on_val == f"{pre}{val}{post}"
    rt_surround_off_val = require_binding(
        _mapped(rt_surround_off, origin="runtime interior off"), "a"
    )
    assert rt_surround_off_val == f"{pre}{_brace(token)}{post}"
    assert rt_surround_on_val != rt_surround_off_val

    rt_default_on_val = require_binding(
        _mapped(rt_default_on, origin="runtime interior :- on"), "a"
    )
    assert rt_default_on_val == f"x{val}y"
    assert rt_default_on_val != f"x{default}y"
    rt_default_off_val = require_binding(
        _mapped(rt_default_off, origin="runtime interior :- off"), "a"
    )
    assert rt_default_off_val == f"x{_brace_default(token, default)}y"
    assert rt_default_on_val != rt_default_off_val

    rt_absent_on_val = require_binding(
        _mapped(rt_absent_on, origin="runtime absent :- on"), "a"
    )
    assert rt_absent_on_val == default
    rt_absent_off_val = require_binding(
        _mapped(rt_absent_off, origin="runtime absent :- off"), "a"
    )
    assert rt_absent_off_val == _brace_default(token, default)
    assert rt_absent_on_val != rt_absent_off_val


def test_load_interior_sequences_literal_when_expansion_off():
    token, val, default = unique_token(), unique_token(), unique_token()
    pre, post = unique_token(), unique_token()
    public_surround = f"a=x{_brace('b')}y\n"
    public_default = f"a=x{_brace_default('b', 'd')}y\n"
    public_absent = f"a={_brace_default('b', 'd')}\n"
    runtime_surround = f"a={pre}{_brace(token)}{post}\n"
    runtime_default = f"a=x{_brace_default(token, default)}y\n"
    runtime_absent = f"a={_brace_default(token, default)}\n"

    surround_on = _load(public_surround, env={"b": "c"})
    surround_off = _load(
        public_surround, env={"b": "c"}, interpolate=_EXPANSION_OFF
    )
    default_on = _load(public_default, env={"b": "c"})
    default_off = _load(
        public_default, env={"b": "c"}, interpolate=_EXPANSION_OFF
    )
    absent_on = _load(public_absent)
    absent_off = _load(public_absent, interpolate=_EXPANSION_OFF)
    rt_surround_on = _load(runtime_surround, env={token: val})
    rt_surround_off = _load(
        runtime_surround, env={token: val}, interpolate=_EXPANSION_OFF
    )
    rt_default_on = _load(runtime_default, env={token: val})
    rt_default_off = _load(
        runtime_default, env={token: val}, interpolate=_EXPANSION_OFF
    )
    rt_absent_on = _load(runtime_absent)
    rt_absent_off = _load(runtime_absent, interpolate=_EXPANSION_OFF)
    print(
        "load off keeps interior ${b}, ${b:-d} in surrounding text, "
        "and absent ${b:-d} / ${TOKEN:-DEF} literal",
        flush=True,
    )

    _loaded(surround_on, origin="load interior ${b} on")
    surround_on_val = environ_value(surround_on, "a")
    assert surround_on_val == "xcy"
    _loaded(surround_off, origin="load interior ${b} off")
    surround_off_val = environ_value(surround_off, "a")
    assert surround_off_val == f"x{_brace('b')}y"
    assert surround_on_val != surround_off_val

    _loaded(default_on, origin="load interior ${b:-d} on")
    default_on_val = environ_value(default_on, "a")
    assert default_on_val == "xcy"
    assert default_on_val != "xdy"
    _loaded(default_off, origin="load interior ${b:-d} off")
    default_off_val = environ_value(default_off, "a")
    assert default_off_val == f"x{_brace_default('b', 'd')}y"
    assert default_on_val != default_off_val

    _loaded(absent_on, origin="load absent ${b:-d} on")
    absent_on_val = environ_value(absent_on, "a")
    assert absent_on_val == "d"
    _loaded(absent_off, origin="load absent ${b:-d} off")
    absent_off_val = environ_value(absent_off, "a")
    assert absent_off_val == _brace_default("b", "d")
    assert absent_on_val != absent_off_val

    _loaded(rt_surround_on, origin="load runtime interior on")
    rt_surround_on_val = environ_value(rt_surround_on, "a")
    assert rt_surround_on_val == f"{pre}{val}{post}"
    _loaded(rt_surround_off, origin="load runtime interior off")
    rt_surround_off_val = environ_value(rt_surround_off, "a")
    assert rt_surround_off_val == f"{pre}{_brace(token)}{post}"
    assert rt_surround_on_val != rt_surround_off_val

    _loaded(rt_default_on, origin="load runtime interior :- on")
    rt_default_on_val = environ_value(rt_default_on, "a")
    assert rt_default_on_val == f"x{val}y"
    _loaded(rt_default_off, origin="load runtime interior :- off")
    rt_default_off_val = environ_value(rt_default_off, "a")
    assert rt_default_off_val == f"x{_brace_default(token, default)}y"
    assert rt_default_on_val != rt_default_off_val

    _loaded(rt_absent_on, origin="load runtime absent :- on")
    rt_absent_on_val = environ_value(rt_absent_on, "a")
    assert rt_absent_on_val == default
    _loaded(rt_absent_off, origin="load runtime absent :- off")
    rt_absent_off_val = environ_value(rt_absent_off, "a")
    assert rt_absent_off_val == _brace_default(token, default)
    assert rt_absent_on_val != rt_absent_off_val


# ---------------------------------------------------------------------------
# D. Quotes do not suppress expansion
# ---------------------------------------------------------------------------


def test_mapping_double_and_single_quotes_expand():
    double = _mapping(f'a="{_brace("b")}"\n', env={"b": "c"})
    single = _mapping(f"a='{_brace('b')}'\n", env={"b": "c"})
    print('mapping a="${b}" and a=\'${b}\'', flush=True)
    double_map = _mapped(double, origin='mapping "${b}"')
    double_val = require_binding(double_map, "a")
    assert double_val == "c"
    assert double_val != _brace("b")
    single_map = _mapped(single, origin="mapping '${b}'")
    single_val = require_binding(single_map, "a")
    assert single_val == "c"
    assert single_val != _brace("b")


def test_load_double_and_single_quotes_expand():
    double = _load(f'a="{_brace("b")}"\n', env={"b": "c"})
    single = _load(f"a='{_brace('b')}'\n", env={"b": "c"})
    print('load a="${b}" and a=\'${b}\'', flush=True)
    _loaded(double, origin='load "${b}"')
    double_val = environ_value(double, "a")
    assert double_val == "c"
    assert double_val != _brace("b")
    _loaded(single, origin="load '${b}'")
    single_val = environ_value(single, "a")
    assert single_val == "c"
    assert single_val != _brace("b")


def test_runtime_quoted_brace_expands_mapping():
    token, val = unique_token(), unique_token()
    double = _mapping(f'a="{_brace(token)}"\n', env={token: val})
    single = _mapping(f"a='{_brace(token)}'\n", env={token: val})
    print(f"runtime quoted ${{{token}}}", flush=True)
    double_map = _mapped(double, origin="runtime double quote")
    double_val = require_binding(double_map, "a")
    assert double_val == val
    assert double_val != _brace(token)
    single_map = _mapped(single, origin="runtime single quote")
    single_val = require_binding(single_map, "a")
    assert single_val == val
    assert single_val != _brace(token)


# ---------------------------------------------------------------------------
# E. Absent / default / present no-value / present empty (file and env)
# ---------------------------------------------------------------------------


def test_mapping_unset_without_default_is_empty_not_failure():
    token = unique_token()
    public = _mapping(f"a={_brace('b')}\n")
    runtime = _mapping(f"a={_brace(token)}\n")
    print("mapping ${b} / ${TOKEN} absent without default", flush=True)
    public_map = _mapped(public, origin="mapping unset ${b}")
    public_val = require_empty_string(public_map, "a")
    assert public_val != _brace("b")
    runtime_map = _mapped(runtime, origin="mapping unset ${TOKEN}")
    runtime_val = require_empty_string(runtime_map, "a")
    assert runtime_val != _brace(token)


def test_load_unset_without_default_writes_empty():
    token = unique_token()
    public = _load(f"a={_brace('b')}\n")
    runtime = _load(f"a={_brace(token)}\n")
    print("load ${b} / ${TOKEN} absent without default writes empty", flush=True)
    _loaded(public, origin="load unset ${b}")
    public_val = environ_value(public, "a")
    assert public_val == ""
    assert public_val != _brace("b")
    _loaded(runtime, origin="load unset ${TOKEN}")
    runtime_val = environ_value(runtime, "a")
    assert runtime_val == ""
    assert runtime_val != _brace(token)


def test_mapping_unset_with_default_uses_default():
    token, val, default = unique_token(), unique_token(), unique_token()
    text = f"a={_brace_default('b', 'd')}\n"
    runtime_text = f"a={_brace_default(token, default)}\n"
    absent = _mapping(text)
    present = _mapping(text, env={"b": "c"})
    runtime_absent = _mapping(runtime_text)
    runtime_present = _mapping(runtime_text, env={token: val})
    print(
        "mapping ${b:-d} / ${TOKEN:-DEF} absent uses default; "
        "present value is not the default",
        flush=True,
    )
    absent_map = _mapped(absent, origin="mapping ${b:-d} absent")
    absent_val = require_binding(absent_map, "a")
    assert absent_val == "d"
    assert absent_val != _brace_default("b", "d")
    present_map = _mapped(present, origin="mapping ${b:-d} present")
    present_val = require_binding(present_map, "a")
    assert present_val == "c"
    assert present_val != "d"
    assert present_val != absent_val
    runtime_absent_map = _mapped(
        runtime_absent, origin="mapping ${TOKEN:-DEF} absent"
    )
    runtime_absent_val = require_binding(runtime_absent_map, "a")
    assert runtime_absent_val == default
    assert runtime_absent_val != _brace_default(token, default)
    runtime_present_map = _mapped(
        runtime_present, origin="mapping ${TOKEN:-DEF} present"
    )
    runtime_present_val = require_binding(runtime_present_map, "a")
    assert runtime_present_val == val
    assert runtime_present_val != default
    assert runtime_present_val != runtime_absent_val


def test_load_unset_with_default_uses_default():
    token, val, default = unique_token(), unique_token(), unique_token()
    text = f"a={_brace_default('b', 'd')}\n"
    runtime_text = f"a={_brace_default(token, default)}\n"
    absent = _load(text)
    present = _load(text, env={"b": "c"})
    runtime_absent = _load(runtime_text)
    runtime_present = _load(runtime_text, env={token: val})
    print(
        "load ${b:-d} / ${TOKEN:-DEF} absent uses default; "
        "present value is not the default",
        flush=True,
    )
    _loaded(absent, origin="load ${b:-d} absent")
    absent_val = environ_value(absent, "a")
    assert absent_val == "d"
    assert absent_val != _brace_default("b", "d")
    _loaded(present, origin="load ${b:-d} present")
    present_val = environ_value(present, "a")
    assert present_val == "c"
    assert present_val != "d"
    assert present_val != absent_val
    _loaded(runtime_absent, origin="load ${TOKEN:-DEF} absent")
    runtime_absent_val = environ_value(runtime_absent, "a")
    assert runtime_absent_val == default
    assert runtime_absent_val != _brace_default(token, default)
    _loaded(runtime_present, origin="load ${TOKEN:-DEF} present")
    runtime_present_val = environ_value(runtime_present, "a")
    assert runtime_present_val == val
    assert runtime_present_val != default
    assert runtime_present_val != runtime_absent_val


def test_mapping_present_no_value_does_not_use_default():
    token, default = unique_token(), unique_token()
    public = _mapping(f"b\na={_brace_default('b', 'd')}\n")
    runtime = _mapping(f"{token}\na={_brace_default(token, default)}\n")
    print("mapping present no-value b / TOKEN does not use default", flush=True)
    public_map = _mapped(public, origin="mapping no-value ${b:-d}")
    require_no_value(public_map, "b")
    public_a = require_empty_string(public_map, "a")
    assert public_a != "d"
    runtime_map = _mapped(runtime, origin="mapping no-value ${TOKEN:-DEF}")
    require_no_value(runtime_map, token)
    runtime_a = require_empty_string(runtime_map, "a")
    assert runtime_a != default


def test_load_present_no_value_does_not_use_default():
    token, default = unique_token(), unique_token()
    public = _load(f"b\na={_brace_default('b', 'd')}\n")
    runtime = _load(f"{token}\na={_brace_default(token, default)}\n")
    print("load present no-value b / TOKEN does not use default", flush=True)
    _loaded(public, origin="load no-value ${b:-d}")
    require_environ_absent(public, "b")
    public_a = environ_value(public, "a")
    assert public_a == ""
    assert public_a != "d"
    _loaded(runtime, origin="load no-value ${TOKEN:-DEF}")
    require_environ_absent(runtime, token)
    runtime_a = environ_value(runtime, "a")
    assert runtime_a == ""
    assert runtime_a != default


def test_mapping_present_empty_string_does_not_use_default():
    token, default = unique_token(), unique_token()
    public = _mapping(f"b=\na={_brace_default('b', 'd')}\n")
    runtime = _mapping(f"{token}=\na={_brace_default(token, default)}\n")
    print("mapping file empty string is present, default unused", flush=True)
    public_map = _mapped(public, origin="mapping empty ${b:-d}")
    require_empty_string(public_map, "b")
    public_a = require_empty_string(public_map, "a")
    assert public_a != "d"
    runtime_map = _mapped(runtime, origin="mapping empty ${TOKEN:-DEF}")
    require_empty_string(runtime_map, token)
    runtime_a = require_empty_string(runtime_map, "a")
    assert runtime_a != default


def test_load_present_empty_string_does_not_use_default():
    token, default = unique_token(), unique_token()
    public = _load(f"b=\na={_brace_default('b', 'd')}\n")
    runtime = _load(f"{token}=\na={_brace_default(token, default)}\n")
    print("load file empty string is present, default unused", flush=True)
    _loaded(public, origin="load empty ${b:-d}")
    assert environ_value(public, "b") == ""
    public_a = environ_value(public, "a")
    assert public_a == ""
    assert public_a != "d"
    _loaded(runtime, origin="load empty ${TOKEN:-DEF}")
    assert environ_value(runtime, token) == ""
    runtime_a = environ_value(runtime, "a")
    assert runtime_a == ""
    assert runtime_a != default


def test_mapping_env_empty_string_does_not_use_default():
    token, default = unique_token(), unique_token()
    public_text = f"a={_brace_default('b', 'd')}\n"
    runtime_text = f"a={_brace_default(token, default)}\n"
    present = _mapping(public_text, env={"b": ""})
    absent = _mapping(public_text)
    rt_present = _mapping(runtime_text, env={token: ""})
    rt_absent = _mapping(runtime_text)
    print(
        "mapping env empty string is present; absent arm uses default",
        flush=True,
    )
    present_map = _mapped(present, origin="mapping env empty ${b:-d}")
    present_a = require_empty_string(present_map, "a")
    assert present_a != "d"
    assert "b" not in present_map
    absent_map = _mapped(absent, origin="mapping env absent ${b:-d}")
    absent_a = require_binding(absent_map, "a")
    assert absent_a == "d"
    assert present_a != absent_a
    rt_present_map = _mapped(rt_present, origin="mapping env empty ${TOKEN:-DEF}")
    rt_present_a = require_empty_string(rt_present_map, "a")
    assert rt_present_a != default
    assert token not in rt_present_map
    rt_absent_map = _mapped(rt_absent, origin="mapping env absent ${TOKEN:-DEF}")
    rt_absent_a = require_binding(rt_absent_map, "a")
    assert rt_absent_a == default
    assert rt_present_a != rt_absent_a


def test_load_env_empty_string_does_not_use_default():
    token, default = unique_token(), unique_token()
    public_text = f"a={_brace_default('b', 'd')}\n"
    runtime_text = f"a={_brace_default(token, default)}\n"
    present = _load(public_text, env={"b": ""})
    absent = _load(public_text)
    rt_present = _load(runtime_text, env={token: ""})
    rt_absent = _load(runtime_text)
    print("load env empty string is present; absent arm uses default", flush=True)
    _loaded(present, origin="load env empty ${b:-d}")
    present_a = environ_value(present, "a")
    assert present_a == ""
    assert present_a != "d"
    assert environ_value(present, "b") == ""
    _loaded(absent, origin="load env absent ${b:-d}")
    absent_a = environ_value(absent, "a")
    assert absent_a == "d"
    assert present_a != absent_a
    _loaded(rt_present, origin="load env empty ${TOKEN:-DEF}")
    rt_present_a = environ_value(rt_present, "a")
    assert rt_present_a == ""
    assert rt_present_a != default
    assert environ_value(rt_present, token) == ""
    _loaded(rt_absent, origin="load env absent ${TOKEN:-DEF}")
    rt_absent_a = environ_value(rt_absent, "a")
    assert rt_absent_a == default
    assert rt_present_a != rt_absent_a


def test_runtime_three_way_default_vs_present_mapping():
    token, default = unique_token(), unique_token()
    absent = _mapping(f"a={_brace_default(token, default)}\n")
    no_value = _mapping(f"{token}\na={_brace_default(token, default)}\n")
    file_empty = _mapping(f"{token}=\na={_brace_default(token, default)}\n")
    env_empty = _mapping(
        f"a={_brace_default(token, default)}\n", env={token: ""}
    )
    print(
        "runtime four-way: absent default, no-value, file empty, env empty",
        flush=True,
    )
    absent_map = _mapped(absent, origin="runtime absent default")
    absent_a = require_binding(absent_map, "a")
    assert absent_a == default
    assert token not in absent_map

    no_value_map = _mapped(no_value, origin="runtime no-value default")
    require_no_value(no_value_map, token)
    no_value_a = require_empty_string(no_value_map, "a")
    assert no_value_a != default
    assert absent_a != no_value_a

    file_empty_map = _mapped(file_empty, origin="runtime file empty default")
    require_empty_string(file_empty_map, token)
    file_empty_a = require_empty_string(file_empty_map, "a")
    assert file_empty_a != default

    env_empty_map = _mapped(env_empty, origin="runtime env empty default")
    env_empty_a = require_empty_string(env_empty_map, "a")
    assert env_empty_a != default
    assert token not in env_empty_map
    assert token in no_value_map
    assert token in file_empty_map
    assert no_value_map[token] != file_empty_map[token]


# ---------------------------------------------------------------------------
# F. Override-on order: earlier source binding before process environment
# ---------------------------------------------------------------------------


def test_mapping_earlier_binding_beats_process_environment():
    result = _mapping(f"b=d\na={_brace('b')}\n", env={"b": "c"})
    print("mapping b=d then a=${b} with env b=c", flush=True)
    mapping = _mapped(result, origin="mapping earlier b=d")
    assert require_binding(mapping, "b") == "d"
    recorded = require_binding(mapping, "a")
    assert recorded == "d"
    assert recorded != "c"


def test_load_override_on_earlier_binding_beats_process_environment():
    result = _load(
        f"b=d\na={_brace('b')}\n", env={"b": "c"}, override=_OVERRIDE_ON
    )
    print("load override on b=d then a=${b} with env b=c", flush=True)
    _loaded(result, origin="load override-on earlier")
    assert environ_value(result, "b") == "d"
    recorded = environ_value(result, "a")
    assert recorded == "d"
    assert recorded != "c"


def test_mapping_latest_assignment_used():
    name, first, second, env_val, ref = (
        unique_token(),
        unique_token(),
        unique_token(),
        unique_token(),
        unique_token(),
    )
    public = _mapping(f"a=b\na=c\nd={_brace('a')}\n", env={"a": "x"})
    runtime = _mapping(
        f"{name}={first}\n{name}={second}\n{ref}={_brace(name)}\n",
        env={name: env_val},
    )
    print(
        "mapping a=b then a=c then d=${a} uses latest c, not first b and not env x; "
        "runtime NAME=first then NAME=second then REF=${NAME}",
        flush=True,
    )
    public_map = _mapped(public, origin="mapping latest assignment")
    assert require_binding(public_map, "a") == "c"
    recorded = require_binding(public_map, "d")
    assert recorded == "c"
    assert recorded != "b"
    assert recorded != "x"
    runtime_map = _mapped(runtime, origin="runtime mapping latest assignment")
    assert require_binding(runtime_map, name) == second
    runtime_ref = require_binding(runtime_map, ref)
    assert runtime_ref == second
    assert runtime_ref != first
    assert runtime_ref != env_val


def test_load_override_on_latest_assignment_used():
    result = _load(f"a=b\na=c\nd={_brace('a')}\n", override=_OVERRIDE_ON)
    print("load override on a=b then a=c then d=${a}", flush=True)
    _loaded(result, origin="load override-on latest")
    assert environ_value(result, "a") == "c"
    recorded = environ_value(result, "d")
    assert recorded == "c"
    assert recorded != "b"


def test_runtime_source_beats_env_mapping_and_load_override_on():
    name, file_val, env_val = unique_token(), unique_token(), unique_token()
    ref = unique_token()
    text = f"{name}={file_val}\n{ref}={_brace(name)}\n"
    mapped = _mapping(text, env={name: env_val})
    loaded = _load(text, env={name: env_val}, override=_OVERRIDE_ON)
    print(f"runtime source {name}={file_val} beats env {env_val}", flush=True)
    mapping = _mapped(mapped, origin="runtime mapping source beats env")
    mapped_ref = require_binding(mapping, ref)
    assert mapped_ref == file_val
    assert mapped_ref != env_val
    _loaded(loaded, origin="runtime load override-on source beats env")
    loaded_ref = environ_value(loaded, ref)
    assert loaded_ref == file_val
    assert loaded_ref != env_val
    assert environ_value(loaded, name) == file_val


def test_mapping_default_form_earlier_binding_beats_env():
    name, file_val, env_val, default = (
        unique_token(),
        unique_token(),
        unique_token(),
        unique_token(),
    )
    public = _mapping(
        f"b=d\na={_brace_default('b', 'x')}\n", env={"b": "c"}
    )
    runtime = _mapping(
        f"{name}={file_val}\nREF={_brace_default(name, default)}\n",
        env={name: env_val},
    )
    print("mapping ${b:-x} / ${NAME:-DEF} earlier binding beats env", flush=True)
    public_map = _mapped(public, origin="mapping ${b:-x} earlier")
    public_a = require_binding(public_map, "a")
    assert public_a == "d"
    assert public_a != "c"
    assert public_a != "x"
    runtime_map = _mapped(runtime, origin="mapping ${NAME:-DEF} earlier")
    runtime_ref = require_binding(runtime_map, "REF")
    assert runtime_ref == file_val
    assert runtime_ref != env_val
    assert runtime_ref != default


def test_load_override_on_default_form_earlier_binding_beats_env():
    name, file_val, env_val, default = (
        unique_token(),
        unique_token(),
        unique_token(),
        unique_token(),
    )
    public = _load(
        f"b=d\na={_brace_default('b', 'x')}\n",
        env={"b": "c"},
        override=_OVERRIDE_ON,
    )
    runtime = _load(
        f"{name}={file_val}\nREF={_brace_default(name, default)}\n",
        env={name: env_val},
        override=_OVERRIDE_ON,
    )
    print(
        "load override on ${b:-x} / ${NAME:-DEF} earlier binding beats env",
        flush=True,
    )
    _loaded(public, origin="load override-on ${b:-x} earlier")
    public_a = environ_value(public, "a")
    assert public_a == "d"
    assert public_a != "c"
    assert public_a != "x"
    _loaded(runtime, origin="load override-on ${NAME:-DEF} earlier")
    runtime_ref = environ_value(runtime, "REF")
    assert runtime_ref == file_val
    assert runtime_ref != env_val
    assert runtime_ref != default


def test_mapping_later_binding_is_not_earlier():
    name, later, env_val = unique_token(), unique_token(), unique_token()
    ref = unique_token()
    public_text = f"a={_brace('b')}\nb=d\n"
    runtime_text = f"{ref}={_brace(name)}\n{name}={later}\n"
    absent = _mapping(public_text)
    present = _mapping(public_text, env={"b": "c"})
    rt_absent = _mapping(runtime_text)
    rt_present = _mapping(runtime_text, env={name: env_val})
    print("mapping later b=d is not an earlier binding for a=${b}", flush=True)
    absent_map = _mapped(absent, origin="mapping later absent env")
    require_empty_string(absent_map, "a")
    assert require_binding(absent_map, "b") == "d"
    present_map = _mapped(present, origin="mapping later with env b=c")
    present_a = require_binding(present_map, "a")
    assert present_a == "c"
    assert present_a != "d"
    assert require_binding(present_map, "b") == "d"
    rt_absent_map = _mapped(rt_absent, origin="runtime later absent env")
    require_empty_string(rt_absent_map, ref)
    assert require_binding(rt_absent_map, name) == later
    rt_present_map = _mapped(rt_present, origin="runtime later with env")
    rt_ref = require_binding(rt_present_map, ref)
    assert rt_ref == env_val
    assert rt_ref != later
    assert require_binding(rt_present_map, name) == later


def test_load_override_on_later_binding_is_not_earlier():
    name, later, env_val = unique_token(), unique_token(), unique_token()
    ref = unique_token()
    public_text = f"a={_brace('b')}\nb=d\n"
    runtime_text = f"{ref}={_brace(name)}\n{name}={later}\n"
    absent = _load(public_text, override=_OVERRIDE_ON)
    present = _load(public_text, env={"b": "c"}, override=_OVERRIDE_ON)
    rt_absent = _load(runtime_text, override=_OVERRIDE_ON)
    rt_present = _load(
        runtime_text, env={name: env_val}, override=_OVERRIDE_ON
    )
    print("load override on later b=d is not earlier for a=${b}", flush=True)
    _loaded(absent, origin="load override-on later absent env")
    assert environ_value(absent, "a") == ""
    assert environ_value(absent, "b") == "d"
    _loaded(present, origin="load override-on later with env")
    present_a = environ_value(present, "a")
    assert present_a == "c"
    assert present_a != "d"
    assert environ_value(present, "b") == "d"
    _loaded(rt_absent, origin="runtime load later absent env")
    assert environ_value(rt_absent, ref) == ""
    assert environ_value(rt_absent, name) == later
    _loaded(rt_present, origin="runtime load later with env")
    rt_ref = environ_value(rt_present, ref)
    assert rt_ref == env_val
    assert rt_ref != later
    assert environ_value(rt_present, name) == later


def test_mapping_uses_computed_earlier_value():
    c_name, b_name, a_name, x_val = (
        unique_token(),
        unique_token(),
        unique_token(),
        unique_token(),
    )
    public = _mapping(f"c=x\nb={_brace('c')}\na={_brace('b')}\n")
    runtime = _mapping(
        f"{c_name}={x_val}\n{b_name}={_brace(c_name)}\n{a_name}={_brace(b_name)}\n"
    )
    print("mapping chain uses computed earlier value, not raw ${c}", flush=True)
    public_map = _mapped(public, origin="mapping computed chain")
    public_b = require_binding(public_map, "b")
    public_a = require_binding(public_map, "a")
    assert public_b == "x"
    assert public_a == "x"
    assert public_a != _brace("c")
    assert public_b != _brace("c")
    runtime_map = _mapped(runtime, origin="runtime computed chain")
    runtime_b = require_binding(runtime_map, b_name)
    runtime_a = require_binding(runtime_map, a_name)
    assert runtime_b == x_val
    assert runtime_a == x_val
    assert runtime_a != _brace(c_name)


def test_load_override_on_uses_computed_earlier_value():
    c_name, b_name, a_name, x_val = (
        unique_token(),
        unique_token(),
        unique_token(),
        unique_token(),
    )
    public = _load(
        f"c=x\nb={_brace('c')}\na={_brace('b')}\n", override=_OVERRIDE_ON
    )
    runtime = _load(
        f"{c_name}={x_val}\n{b_name}={_brace(c_name)}\n{a_name}={_brace(b_name)}\n",
        override=_OVERRIDE_ON,
    )
    print("load override on chain uses computed earlier value", flush=True)
    _loaded(public, origin="load override-on computed chain")
    public_b = environ_value(public, "b")
    public_a = environ_value(public, "a")
    assert public_b == "x"
    assert public_a == "x"
    assert public_a != _brace("c")
    _loaded(runtime, origin="runtime load override-on computed chain")
    runtime_b = environ_value(runtime, b_name)
    runtime_a = environ_value(runtime, a_name)
    assert runtime_b == x_val
    assert runtime_a == x_val
    assert runtime_a != _brace(c_name)


# ---------------------------------------------------------------------------
# G. Override-off order: process environment before earlier source binding
# ---------------------------------------------------------------------------


def test_load_override_off_env_wins_write_and_expansion():
    result = _load(f'a=b\nd="{_brace("a")}"\n', env={"a": "c"})
    print('load default a=b then d="${a}" with env a=c', flush=True)
    _loaded(result, origin="load override-off env wins")
    assert environ_value(result, "a") == "c"
    recorded = environ_value(result, "d")
    assert recorded == "c"
    assert recorded != "b"


def test_load_override_on_same_source_file_wins():
    text = f'a=b\nd="{_brace("a")}"\n'
    env = {"a": "c"}
    off = _load(text, env=env)
    on = _load(text, env=env, override=_OVERRIDE_ON)
    print("same source a=b then d=\"${a}\": override off vs on", flush=True)
    _loaded(off, origin="same source override off")
    assert environ_value(off, "a") == "c"
    assert environ_value(off, "d") == "c"
    _loaded(on, origin="same source override on")
    on_a = environ_value(on, "a")
    on_d = environ_value(on, "d")
    assert on_a == "b"
    assert on_d == "b"
    assert on_a != environ_value(off, "a")
    assert on_d != environ_value(off, "d")


def test_load_override_off_uses_file_when_env_absent():
    result = _load(f'a=b\nd="{_brace("a")}"\n')
    print('load default a=b then d="${a}" with a absent from env', flush=True)
    _loaded(result, origin="load override-off env absent")
    assert environ_value(result, "a") == "b"
    recorded = environ_value(result, "d")
    assert recorded == "b"
    assert recorded != ""


def test_runtime_load_override_off_env_beats_source():
    name, file_val, env_val = unique_token(), unique_token(), unique_token()
    ref = unique_token()
    text = f"{name}={file_val}\n{ref}={_brace(name)}\n"
    env = {name: env_val}
    off = _load(text, env=env)
    on = _load(text, env=env, override=_OVERRIDE_ON)
    print(f"runtime load override off {name} env beats source", flush=True)
    _loaded(off, origin="runtime load override-off env beats")
    assert environ_value(off, name) == env_val
    off_ref = environ_value(off, ref)
    assert off_ref == env_val
    assert off_ref != file_val
    _loaded(on, origin="runtime load override-on contrast")
    on_name = environ_value(on, name)
    on_ref = environ_value(on, ref)
    assert on_name == file_val
    assert on_ref == file_val
    assert on_ref != off_ref


def test_load_override_off_default_form_env_beats_source():
    name, file_val, env_val, default = (
        unique_token(),
        unique_token(),
        unique_token(),
        unique_token(),
    )
    public_text = f"b=d\na={_brace_default('b', 'x')}\n"
    runtime_text = f"{name}={file_val}\nREF={_brace_default(name, default)}\n"
    public_env = {"b": "c"}
    runtime_env = {name: env_val}
    public_off = _load(public_text, env=public_env)
    public_on = _load(public_text, env=public_env, override=_OVERRIDE_ON)
    runtime_off = _load(runtime_text, env=runtime_env)
    runtime_on = _load(
        runtime_text, env=runtime_env, override=_OVERRIDE_ON
    )
    print("load ${b:-x} / ${NAME:-DEF} override off env beats source", flush=True)
    _loaded(public_off, origin="load override-off ${b:-x}")
    assert environ_value(public_off, "b") == "c"
    public_off_a = environ_value(public_off, "a")
    assert public_off_a == "c"
    assert public_off_a != "d"
    assert public_off_a != "x"
    _loaded(public_on, origin="load override-on ${b:-x} contrast")
    public_on_a = environ_value(public_on, "a")
    assert public_on_a == "d"
    assert public_on_a != public_off_a
    _loaded(runtime_off, origin="load override-off ${NAME:-DEF}")
    assert environ_value(runtime_off, name) == env_val
    runtime_off_ref = environ_value(runtime_off, "REF")
    assert runtime_off_ref == env_val
    assert runtime_off_ref != file_val
    assert runtime_off_ref != default
    _loaded(runtime_on, origin="load override-on ${NAME:-DEF} contrast")
    runtime_on_ref = environ_value(runtime_on, "REF")
    assert runtime_on_ref == file_val
    assert runtime_on_ref != runtime_off_ref


# ---------------------------------------------------------------------------
# H. Self-reference
# ---------------------------------------------------------------------------


def test_mapping_self_reference_uses_env():
    name, old = unique_token(), unique_token()
    public = _mapping(f"a={_brace('a')}\n", env={"a": "b"})
    runtime = _mapping(f"{name}={_brace(name)}\n", env={name: old})
    print("mapping a=${a} with env a=b; runtime NAME=${NAME}", flush=True)
    public_map = _mapped(public, origin="mapping self ${a} env")
    public_a = require_binding(public_map, "a")
    assert public_a == "b"
    assert public_a != _brace("a")
    runtime_map = _mapped(runtime, origin="mapping self ${NAME} env")
    runtime_a = require_binding(runtime_map, name)
    assert runtime_a == old
    assert runtime_a != _brace(name)


def test_load_self_reference_uses_env():
    name, old = unique_token(), unique_token()
    public_witness, runtime_witness = unique_token(), unique_token()
    public = _load(
        f"a={_brace('a')}\n{public_witness}={_brace('a')}\n",
        env={"a": "b"},
        override=_OVERRIDE_ON,
    )
    runtime = _load(
        f"{name}={_brace(name)}\n{runtime_witness}={_brace(name)}\n",
        env={name: old},
        override=_OVERRIDE_ON,
    )
    print(
        "load override-on a=${a} with env a=b writes a as b and expands onto "
        "a witness that was not already b",
        flush=True,
    )
    _loaded(public, origin="load self ${a} env")
    public_a = environ_value(public, "a")
    assert public_a == "b"
    assert public_a != _brace("a")
    public_w = environ_value(public, public_witness)
    assert public_w == "b"
    assert public_w != _brace("a")
    _loaded(runtime, origin="load self ${NAME} env")
    runtime_a = environ_value(runtime, name)
    assert runtime_a == old
    assert runtime_a != _brace(name)
    runtime_w = environ_value(runtime, runtime_witness)
    assert runtime_w == old
    assert runtime_w != _brace(name)


def test_mapping_self_reference_absent_empty():
    name = unique_token()
    public = _mapping(f"a={_brace('a')}\n")
    runtime = _mapping(f"{name}={_brace(name)}\n")
    print("mapping a=${a} / NAME=${NAME} absent is empty", flush=True)
    public_map = _mapped(public, origin="mapping self ${a} absent")
    public_a = require_empty_string(public_map, "a")
    assert public_a != _brace("a")
    runtime_map = _mapped(runtime, origin="mapping self ${NAME} absent")
    runtime_a = require_empty_string(runtime_map, name)
    assert runtime_a != _brace(name)


def test_load_self_reference_absent_writes_empty():
    name = unique_token()
    public = _load(f"a={_brace('a')}\n")
    runtime = _load(f"{name}={_brace(name)}\n")
    print("load a=${a} / NAME=${NAME} absent writes empty", flush=True)
    _loaded(public, origin="load self ${a} absent")
    public_a = environ_value(public, "a")
    assert public_a == ""
    assert public_a != _brace("a")
    _loaded(runtime, origin="load self ${NAME} absent")
    runtime_a = environ_value(runtime, name)
    assert runtime_a == ""
    assert runtime_a != _brace(name)


def test_mapping_self_reference_default():
    name, old, default = unique_token(), unique_token(), unique_token()
    absent = _mapping(f"a={_brace_default('a', 'c')}\n")
    present = _mapping(f"a={_brace_default('a', 'c')}\n", env={"a": "b"})
    rt_absent = _mapping(f"{name}={_brace_default(name, default)}\n")
    rt_present = _mapping(
        f"{name}={_brace_default(name, default)}\n", env={name: old}
    )
    print("mapping a=${a:-c} absent vs env a=b; runtime NAME=${NAME:-DEF}", flush=True)
    absent_map = _mapped(absent, origin="mapping self ${a:-c} absent")
    absent_a = require_binding(absent_map, "a")
    assert absent_a == "c"
    present_map = _mapped(present, origin="mapping self ${a:-c} env")
    present_a = require_binding(present_map, "a")
    assert present_a == "b"
    assert present_a != "c"
    rt_absent_map = _mapped(rt_absent, origin="mapping self ${NAME:-DEF} absent")
    rt_absent_a = require_binding(rt_absent_map, name)
    assert rt_absent_a == default
    rt_present_map = _mapped(rt_present, origin="mapping self ${NAME:-DEF} env")
    rt_present_a = require_binding(rt_present_map, name)
    assert rt_present_a == old
    assert rt_present_a != default


def test_load_self_reference_default():
    name, old, default = unique_token(), unique_token(), unique_token()
    present_witness, rt_present_witness = unique_token(), unique_token()
    absent = _load(f"a={_brace_default('a', 'c')}\n")
    present = _load(
        f"a={_brace_default('a', 'c')}\n"
        f"{present_witness}={_brace_default('a', 'c')}\n",
        env={"a": "b"},
        override=_OVERRIDE_ON,
    )
    rt_absent = _load(f"{name}={_brace_default(name, default)}\n")
    rt_present = _load(
        f"{name}={_brace_default(name, default)}\n"
        f"{rt_present_witness}={_brace_default(name, default)}\n",
        env={name: old},
        override=_OVERRIDE_ON,
    )
    print(
        "load a=${a:-c} absent writes c; override-on env a=b writes a as b "
        "and expands onto a witness that was not already b",
        flush=True,
    )
    _loaded(absent, origin="load self ${a:-c} absent")
    absent_a = environ_value(absent, "a")
    assert absent_a == "c"
    _loaded(present, origin="load self ${a:-c} env")
    present_a = environ_value(present, "a")
    assert present_a == "b"
    assert present_a != "c"
    present_w = environ_value(present, present_witness)
    assert present_w == "b"
    assert present_w != "c"
    _loaded(rt_absent, origin="load self ${NAME:-DEF} absent")
    rt_absent_a = environ_value(rt_absent, name)
    assert rt_absent_a == default
    _loaded(rt_present, origin="load self ${NAME:-DEF} env")
    rt_present_a = environ_value(rt_present, name)
    assert rt_present_a == old
    assert rt_present_a != default
    rt_present_w = environ_value(rt_present, rt_present_witness)
    assert rt_present_w == old
    assert rt_present_w != default


# ---------------------------------------------------------------------------
# I. A no-value binding is not expanded
# ---------------------------------------------------------------------------


def test_mapping_no_value_binding_stays_no_value():
    token, val, foo = unique_token(), unique_token(), unique_token()
    public = _mapping(f"FOO\nNAME={_brace(token)}\n", env={token: val})
    runtime = _mapping(f"{foo}\nNAME={_brace(token)}\n", env={token: val})
    print("mapping no-value FOO / runtime name stays no-value while NAME expands", flush=True)
    public_map = _mapped(public, origin="mapping no-value FOO")
    require_no_value(public_map, "FOO")
    public_name = require_binding(public_map, "NAME")
    assert public_name == val
    assert public_name != _brace(token)
    runtime_map = _mapped(runtime, origin="mapping no-value runtime")
    require_no_value(runtime_map, foo)
    runtime_name = require_binding(runtime_map, "NAME")
    assert runtime_name == val


def test_load_no_value_binding_not_written():
    token, val, foo = unique_token(), unique_token(), unique_token()
    public = _load(f"FOO\nNAME={_brace(token)}\n", env={token: val})
    runtime = _load(f"{foo}\nNAME={_brace(token)}\n", env={token: val})
    print("load no-value FOO / runtime name is not written; NAME expands", flush=True)
    _loaded(public, origin="load no-value FOO")
    require_environ_absent(public, "FOO")
    public_name = environ_value(public, "NAME")
    assert public_name == val
    assert public_name != _brace(token)
    _loaded(runtime, origin="load no-value runtime")
    require_environ_absent(runtime, foo)
    runtime_name = environ_value(runtime, "NAME")
    assert runtime_name == val


def test_no_value_versus_expanded_unset_empty_both_entries():
    unset = unique_token()
    foo = unique_token()
    no_value_text = f"{foo}\n"
    empty_text = f"{foo}={_brace(unset)}\n"
    mapped_no_value = _mapping(no_value_text)
    mapped_empty = _mapping(empty_text)
    loaded_no_value = _load(no_value_text)
    loaded_empty = _load(empty_text)
    print(
        "no-value FOO vs FOO=${UNSET} empty, mapping and load",
        flush=True,
    )
    no_value_map = _mapped(mapped_no_value, origin="mapping no-value contrast")
    require_no_value(no_value_map, foo)
    empty_map = _mapped(mapped_empty, origin="mapping ${UNSET} empty")
    empty_val = require_empty_string(empty_map, foo)
    assert empty_val != no_value_map[foo]
    _loaded(loaded_no_value, origin="load no-value contrast")
    require_environ_absent(loaded_no_value, foo)
    _loaded(loaded_empty, origin="load ${UNSET} empty")
    loaded_empty_val = environ_value(loaded_empty, foo)
    assert loaded_empty_val == ""
    assert foo not in loaded_no_value.environ
    assert foo in loaded_empty.environ
