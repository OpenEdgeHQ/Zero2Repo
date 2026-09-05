# feature: F02
"""FP-02: locate a `.env` file by walking ancestors.

Assertions stay at the PRD's precision: first matching regular file or Unix
FIFO on a walk toward the filesystem root; script-directory start versus
working-directory start (asked, interactive with no script path, debugger
attached, frozen packaged executable); custom base names; missing-file empty
text versus fail-if-not-found;
zip-imported callers; CLI default path is not this walk. Exception types,
message wording, and detector attributes are not pinned.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from envfile import envfile_values, find_envfile, load_envfile  # noqa: F401 — public location/load/mapping entries

from _harness import (
    CallResult,
    HarnessError,
    path_is_fifo,
    product_package_name,
    run_python,
    workspace,
)
from _helpers import (
    load_path,
    locate_call,
    located_from_script,
    located_text,
    require_empty_located_text,
    require_labeled_line,
    require_same_path,
    require_script_success,
    run_frozen_packaged_executable,
    unique_token,
)


def _locate_in(ws, cwd: Path, **kwargs) -> CallResult:
    result = locate_call(cwd=str(cwd), isolate=False, env=ws.env, **kwargs)
    print(
        f"locate cwd={cwd} kwargs={kwargs} "
        f"exception={result.exception!r} value={result.value!r}",
        flush=True,
    )
    return result


def _write_env(ws, relpath: str, name: str, value: str) -> Path:
    return ws.write(relpath, f"{name}={value}\n")


def _locate_source(pkg: str, *, usecwd: bool = False, filename: str | None = None) -> str:
    parts: list[str] = []
    if filename is not None:
        parts.append(f"filename={filename!r}")
    if usecwd:
        parts.append("usecwd=True")
    call_text = "find_envfile(" + ", ".join(parts) + ")"
    return (
        f"from {pkg} import find_envfile\n"
        f"found = {call_text}\n"
        "print('FOUND=' + found)\n"
    )


def _load_source(pkg: str, name: str) -> str:
    return (
        f"from {pkg} import load_envfile\n"
        "import os\n"
        "load_envfile(interpolate=False)\n"
        f"print('HAS=' + ('1' if {name!r} in os.environ else '0'))\n"
        f"print('ENV=' + (os.environ[{name!r}] if {name!r} in os.environ else ''))\n"
    )


def _mapping_source(pkg: str, name: str) -> str:
    return (
        f"from {pkg} import envfile_values\n"
        "mapping = envfile_values(interpolate=False)\n"
        f"print('HAS=' + ('1' if {name!r} in mapping else '0'))\n"
        f"print('MAP=' + ('' if {name!r} not in mapping else str(mapping[{name!r}])))\n"
    )


def _split_starts(ws):
    """Script under an ancestor `.env` (A); cwd is a sibling tree with `.env` (B)."""
    tree = unique_token()
    work = unique_token()
    leaf = unique_token()
    name = unique_token()
    val_a = unique_token()
    val_b = unique_token()
    env_a = _write_env(ws, f"{tree}/.env", name, val_a)
    env_b = _write_env(ws, f"{work}/.env", name, val_b)
    script_dir = ws.mkdir(f"{tree}/{leaf}")
    return {
        "script_rel": f"{tree}/{leaf}/caller.py",
        "script_dir": script_dir,
        "work": ws.resolve(work),
        "env_a": env_a,
        "env_b": env_b,
        "name": name,
        "val_a": val_a,
        "val_b": val_b,
    }


def _require_no_path_failure(result: CallResult, *, origin: str) -> None:
    """Fail-if-not-found: a product non-success (an exception), no path delivered.

    Exception type is not pinned. A silent ``None`` or ``False`` return is
    not a non-success and must not pass.
    """
    assert result.exception is not None, (
        f"{origin} returned {result.value!r} without a product exception; "
        "fail-if-not-found must be a product non-success"
    )
    path_delivered = isinstance(result.value, str) and result.value != ""
    assert not path_delivered, (
        f"{origin} delivered path {result.value!r}; no path may be delivered"
    )
    print(
        f"{origin} product non-success exception={result.exception!r} "
        f"value={result.value!r}",
        flush=True,
    )


def _drain_fifo(path: Path) -> None:
    drained = load_path(path)
    print(f"fifo drain exception={drained.exception!r}", flush=True)
    assert drained.exception is None, (
        f"could not consume located FIFO {path}: {drained.exception!r}"
    )


def _write_zip(ws, relpath: str, module: str, source: str) -> Path:
    path = ws.resolve(relpath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr(module + ".py", source)
    return path


# ---------------------------------------------------------------------------
# A. Walk toward the root; first regular-file match
# ---------------------------------------------------------------------------


def test_walk_from_child4_finds_root_env():
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        leaf = ws.mkdir("child1/child2/child3/child4")
        root_env = _write_env(ws, ".env", name, value)
        result = _locate_in(ws, leaf, usecwd=True)
        found = located_text(result, origin="child4-root")
        require_same_path(found, root_env, origin="child4-root")
        assert found, f"child4-root returned empty text; expected {root_env}"
        assert Path(found).resolve() == root_env.resolve(), (
            f"child4-root located {found!r}, not {root_env}"
        )


def test_runtime_deep_tree_walk():
    depth = 6 + (int(unique_token()[1:], 16) % 3)
    parts = [unique_token() for _ in range(depth)]
    name, value = unique_token(), unique_token()
    print(f"deep-tree depth={depth} parts={parts}", flush=True)
    with workspace() as ws:
        leaf = ws.mkdir("/".join(parts))
        root_env = _write_env(ws, ".env", name, value)
        result = _locate_in(ws, leaf, usecwd=True)
        found = located_text(result, origin="deep-tree")
        require_same_path(found, root_env, origin="deep-tree")
        assert found, f"deep-tree returned empty text; expected {root_env}"
        assert Path(found).resolve() == root_env.resolve(), (
            f"deep-tree located {found!r}, not {root_env}"
        )


def test_nearer_env_wins_over_farther():
    name = unique_token()
    near_val, far_val = unique_token(), unique_token()
    with workspace() as ws:
        far_env = _write_env(ws, ".env", name, far_val)
        mid = unique_token()
        leaf_name = unique_token()
        near_env = _write_env(ws, f"{mid}/.env", name, near_val)
        leaf = ws.mkdir(f"{mid}/{leaf_name}")
        result = _locate_in(ws, leaf, usecwd=True)
        found = located_text(result, origin="nearer-wins")
        require_same_path(found, near_env, origin="nearer-wins")
        assert Path(found).resolve() != Path(far_env).resolve()


def test_directory_named_env_is_not_a_match():
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        file_env = _write_env(ws, ".env", name, value)
        mid = unique_token()
        ws.mkdir(f"{mid}/.env")
        ws.write(f"{mid}/.env/dummy", "not-the-file\n")
        leaf = ws.mkdir(f"{mid}/{unique_token()}")
        result = _locate_in(ws, leaf, usecwd=True)
        found = located_text(result, origin="dir-named-env")
        require_same_path(found, file_env, origin="dir-named-env")
        assert not Path(found).is_dir()


# ---------------------------------------------------------------------------
# B. Ancestor Unix FIFO
# ---------------------------------------------------------------------------


def test_walk_finds_ancestor_fifo():
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        leaf = ws.mkdir("anc/leaf")
        with ws.fifo("anc/.env", f"{name}={value}\n") as fifo:
            try:
                result = _locate_in(ws, leaf, usecwd=True)
                found = located_text(result, origin="ancestor-fifo")
                require_same_path(found, fifo, origin="ancestor-fifo")
                assert path_is_fifo(found), f"located path is not a FIFO: {found!r}"
            finally:
                _drain_fifo(fifo)


def test_runtime_named_ancestor_fifo():
    basename = unique_token()
    name, value = unique_token(), unique_token()
    other, other_val = unique_token(), unique_token()
    with workspace() as ws:
        leaf = ws.mkdir("anc/leaf")
        sibling = _write_env(ws, "anc/.env", other, other_val)
        with ws.fifo(f"anc/{basename}", f"{name}={value}\n") as fifo:
            try:
                result = _locate_in(ws, leaf, filename=basename, usecwd=True)
                found = located_text(result, origin="named-ancestor-fifo")
                require_same_path(found, fifo, origin="named-ancestor-fifo")
                assert path_is_fifo(found), f"located path is not a FIFO: {found!r}"
                assert Path(found).resolve() != Path(sibling).resolve()
            finally:
                _drain_fifo(fifo)


# ---------------------------------------------------------------------------
# C. Script start versus working-directory start
# ---------------------------------------------------------------------------


def test_script_mode_ignores_cwd_env_that_is_not_script_ancestor():
    pkg = product_package_name()
    with workspace() as ws:
        layout = _split_starts(ws)
        result = ws.run_script(
            _locate_source(pkg),
            relpath=layout["script_rel"],
            cwd=layout["work"],
        )
        found = located_from_script(result, label="script-mode")
        require_same_path(found, layout["env_a"], origin="script-mode")
        assert Path(found).resolve() != Path(layout["env_b"]).resolve()


def test_usecwd_selects_working_directory_env():
    pkg = product_package_name()
    with workspace() as ws:
        layout = _split_starts(ws)
        asked_rel = str(Path(layout["script_rel"]).with_name("asked.py"))
        baseline = ws.run_script(
            _locate_source(pkg),
            relpath=layout["script_rel"],
            cwd=layout["work"],
        )
        found_script = located_from_script(baseline, label="usecwd-baseline")
        require_same_path(found_script, layout["env_a"], origin="usecwd-baseline")
        asked_run = ws.run_script(
            _locate_source(pkg, usecwd=True),
            relpath=asked_rel,
            cwd=layout["work"],
        )
        found_cwd = located_from_script(asked_run, label="usecwd")
        require_same_path(found_cwd, layout["env_b"], origin="usecwd")
        assert Path(found_cwd).resolve() != Path(found_script).resolve()


def test_interactive_no_script_path_starts_at_cwd():
    pkg = product_package_name()
    with workspace() as ws:
        layout = _split_starts(ws)
        result = ws.run_python(code=_locate_source(pkg), cwd=layout["work"])
        found = located_from_script(result, label="interactive")
        require_same_path(found, layout["env_b"], origin="interactive")
        assert Path(found).resolve() != Path(layout["env_a"]).resolve()


def test_debugger_session_starts_at_cwd():
    pkg = product_package_name()
    source = _locate_source(pkg) + "after_locate = True\n"
    with workspace() as ws:
        layout = _split_starts(ws)
        baseline = ws.run_script(
            source,
            relpath=layout["script_rel"],
            cwd=layout["work"],
        )
        found_script = located_from_script(baseline, label="debugger-baseline")
        require_same_path(found_script, layout["env_a"], origin="debugger-baseline")
        script_path = ws.resolve(layout["script_rel"])
        # pdb's continue disables tracing when there are no breakpoints, so
        # the debugger would not be attached during location. A breakpoint
        # after the locate call keeps the debugger attached through that call
        # without stopping the child on a prompt (second continue + quit).
        debug = ws.run_python(
            argv=[
                "-m",
                "pdb",
                "-c",
                "break 4",
                "-c",
                "continue",
                "-c",
                "continue",
                "-c",
                "quit",
                str(script_path),
            ],
            cwd=layout["work"],
        )
        found_debug = located_from_script(debug, label="debugger")
        require_same_path(found_debug, layout["env_b"], origin="debugger")
        assert Path(found_debug).resolve() != Path(found_script).resolve()


def test_frozen_packaged_executable_starts_at_cwd():
    pkg = product_package_name()
    with workspace() as ws:
        layout = _split_starts(ws)
        cwd_leaf = ws.mkdir(f"{layout['work'].name}/{unique_token()}")
        baseline = ws.run_script(
            _locate_source(pkg),
            relpath=layout["script_rel"],
            cwd=cwd_leaf,
        )
        found_script = located_from_script(baseline, label="frozen-baseline")
        require_same_path(found_script, layout["env_a"], origin="frozen-baseline")
        frozen_run = run_frozen_packaged_executable(
            _locate_source(pkg),
            bundle_dir=layout["script_dir"] / unique_token(),
            cwd=cwd_leaf,
            env=ws.env,
        )
        found_frozen = located_from_script(frozen_run, label="frozen")
        require_same_path(found_frozen, layout["env_b"], origin="frozen")
        assert Path(found_frozen).resolve() != Path(found_script).resolve()


# ---------------------------------------------------------------------------
# D. Custom base name
# ---------------------------------------------------------------------------


def test_custom_name_not_satisfied_by_only_envfile():
    custom = unique_token()
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        leaf = ws.mkdir(unique_token())
        envfile_file = _write_env(ws, f"{leaf.name}/.env", name, value)
        found_default = located_text(
            _locate_in(ws, leaf, usecwd=True), origin="custom-only-envfile-baseline"
        )
        require_same_path(
            found_default, envfile_file, origin="custom-only-envfile-baseline"
        )
        found_custom = located_text(
            _locate_in(ws, leaf, filename=custom, usecwd=True),
            origin="custom-only-envfile",
        )
        require_empty_located_text(found_custom, origin="custom-only-envfile")
        assert Path(found_default).resolve() == envfile_file.resolve()
        assert found_custom == "", (
            f"custom-only-envfile delivered {found_custom!r}; "
            "a tree with only .env does not satisfy a different name"
        )


def test_default_envfile_not_satisfied_by_only_custom_name():
    custom = unique_token()
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        leaf = ws.mkdir(unique_token())
        custom_file = _write_env(ws, f"{leaf.name}/{custom}", name, value)
        found_custom = located_text(
            _locate_in(ws, leaf, filename=custom, usecwd=True),
            origin="default-only-custom-baseline",
        )
        require_same_path(
            found_custom, custom_file, origin="default-only-custom-baseline"
        )
        found_default = located_text(
            _locate_in(ws, leaf, usecwd=True), origin="default-only-custom"
        )
        if found_default:
            resolved = Path(found_default).resolve()
            assert resolved != Path(custom_file).resolve(), (
                "default .env search returned the custom-named file"
            )
            assert Path(found_default).name == ".env", (
                f"default search returned {found_default!r}"
            )
            print(f"default-only-custom walked to {resolved}", flush=True)
        else:
            require_empty_located_text(found_default, origin="default-only-custom")


def test_custom_name_finds_that_file_not_sibling_envfile():
    custom = unique_token()
    name, envfile_val, custom_val = unique_token(), unique_token(), unique_token()
    with workspace() as ws:
        leaf = ws.mkdir(unique_token())
        envfile_file = _write_env(ws, f"{leaf.name}/.env", name, envfile_val)
        custom_file = _write_env(ws, f"{leaf.name}/{custom}", name, custom_val)
        found_custom = located_text(
            _locate_in(ws, leaf, filename=custom, usecwd=True),
            origin="sibling-custom",
        )
        require_same_path(found_custom, custom_file, origin="sibling-custom")
        found_default = located_text(
            _locate_in(ws, leaf, usecwd=True), origin="sibling-envfile"
        )
        require_same_path(found_default, envfile_file, origin="sibling-envfile")
        assert Path(found_custom).resolve() == custom_file.resolve()
        assert Path(found_default).resolve() == envfile_file.resolve()
        assert Path(found_custom).resolve() != Path(found_default).resolve(), (
            "custom-name search returned the sibling .env"
        )


# ---------------------------------------------------------------------------
# E. Missing file: empty text vs fail-if-not-found
# ---------------------------------------------------------------------------


def test_missing_file_empty_text_when_fail_off():
    basename = unique_token()
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        leaf = ws.mkdir("/".join(unique_token() for _ in range(3)))
        missing = located_text(
            _locate_in(ws, leaf, filename=basename, usecwd=True),
            origin="missing-fail-off",
        )
        require_empty_located_text(missing, origin="missing-fail-off")
        assert missing == "", (
            f"missing-fail-off delivered {missing!r}, not empty text"
        )
        placed = leaf / basename
        placed.write_text(f"{name}={value}\n", encoding="utf-8")
        found = located_text(
            _locate_in(ws, leaf, filename=basename, usecwd=True),
            origin="missing-fail-off-baseline",
        )
        require_same_path(found, placed, origin="missing-fail-off-baseline")
        assert found, f"missing-fail-off-baseline returned empty text; expected {placed}"
        assert Path(found).resolve() == placed.resolve(), (
            f"missing-fail-off-baseline located {found!r}, not {placed}"
        )
        assert found != missing


def test_missing_file_fails_when_fail_on():
    basename = unique_token()
    with workspace() as ws:
        leaf = ws.mkdir("/".join(unique_token() for _ in range(3)))
        result = _locate_in(
            ws, leaf, filename=basename, usecwd=True, raise_error_if_not_found=True
        )
        _require_no_path_failure(result, origin="missing-fail-on")


def test_missing_fail_on_and_off_are_distinguishable():
    basename = unique_token()
    with workspace() as ws:
        leaf = ws.mkdir("/".join(unique_token() for _ in range(3)))
        off = _locate_in(ws, leaf, filename=basename, usecwd=True)
        on = _locate_in(
            ws, leaf, filename=basename, usecwd=True, raise_error_if_not_found=True
        )
        off_text = located_text(off, origin="distinguish-off")
        require_empty_located_text(off_text, origin="distinguish-off")
        _require_no_path_failure(on, origin="distinguish-on")
        assert off.exception is None
        assert on.exception is not None


def test_found_file_returned_when_fail_on():
    basename = unique_token()
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        leaf = ws.mkdir(unique_token())
        placed = leaf / basename
        placed.write_text(f"{name}={value}\n", encoding="utf-8")
        off = located_text(
            _locate_in(ws, leaf, filename=basename, usecwd=True),
            origin="found-fail-off",
        )
        on = located_text(
            _locate_in(
                ws,
                leaf,
                filename=basename,
                usecwd=True,
                raise_error_if_not_found=True,
            ),
            origin="found-fail-on",
        )
        require_same_path(off, placed, origin="found-fail-off")
        require_same_path(on, placed, origin="found-fail-on")
        assert Path(off).resolve() == Path(on).resolve()


# ---------------------------------------------------------------------------
# F. Working directory cannot be determined
# ---------------------------------------------------------------------------


def test_missing_working_directory_does_not_succeed():
    pkg = product_package_name()
    code = (
        "import os, tempfile\n"
        f"from {pkg} import find_envfile\n"
        "gone = tempfile.mkdtemp()\n"
        "os.chdir(gone)\n"
        "os.rmdir(gone)\n"
        "raised = None\n"
        "found = None\n"
        "try:\n"
        "    found = find_envfile(usecwd=True)\n"
        "except BaseException as exc:\n"
        "    raised = exc\n"
        "if raised is not None:\n"
        "    print('STATUS=product-fail')\n"
        "    raise SystemExit(1)\n"
        "if not isinstance(found, str):\n"
        "    print('STATUS=non-text')\n"
        "    print('VALUE=' + repr(found))\n"
        "    raise SystemExit(3)\n"
        "print('FOUND=' + found)\n"
        "print('STATUS=ok')\n"
    )
    result = run_python(code=code)
    print(
        f"missing-cwd returncode={result.returncode} "
        f"stdout={result.stdout_text!r} stderr={result.stderr_text[:800]!r}",
        flush=True,
    )
    status = [
        line for line in result.stdout_text.splitlines() if line.startswith("STATUS=")
    ]
    if "STATUS=non-text" in status:
        raise HarnessError(
            "location returned non-text after the working directory was "
            f"removed; stdout={result.stdout_text!r}"
        )
    assert "STATUS=ok" not in status, (
        "location succeeded after the working directory was removed; "
        f"stdout={result.stdout_text!r}"
    )
    assert result.returncode != 0, (
        "location succeeded after the working directory was removed; "
        f"stdout={result.stdout_text!r}"
    )
    assert "STATUS=product-fail" in status, (
        "missing working directory must be a product non-success; "
        f"stdout={result.stdout_text!r}"
    )


# ---------------------------------------------------------------------------
# G. Zip-imported caller
# ---------------------------------------------------------------------------


def test_zip_imported_caller_completes_without_env():
    pkg = product_package_name()
    module = unique_token()
    basename = unique_token()
    with workspace() as ws:
        zip_dir = unique_token()
        zip_path = _write_zip(
            ws,
            f"{zip_dir}/bundle.zip",
            module,
            (
                f"from {pkg} import find_envfile\n"
                f"found = find_envfile(filename={basename!r})\n"
                "print('FOUND=' + found)\n"
                "print('STATUS=ok')\n"
            ),
        )
        work = ws.mkdir(unique_token())
        outer = (
            "import sys\n"
            f"sys.path.insert(0, {str(zip_path)!r})\n"
            f"import {module}\n"
        )
        result = ws.run_script(
            outer,
            relpath=f"{zip_dir}/outer.py",
            cwd=work,
        )
        stdout = require_script_success(result, label="zip-complete")
        require_labeled_line(stdout, "STATUS", origin="zip-complete")
        found = require_labeled_line(stdout, "FOUND", origin="zip-complete")
        print(f"zip-complete found={found!r}", flush=True)
        assert result.returncode == 0, (
            "zip-imported caller did not complete; "
            f"stderr={result.stderr_text!r} stdout={result.stdout_text!r}"
        )
        assert found == "", (
            f"zip-imported caller with no matching file delivered {found!r}; "
            "a missing file with fail-if-not-found off is empty text"
        )


def test_env_beside_zip_found_from_outer_script():
    pkg = product_package_name()
    module = unique_token()
    name = unique_token()
    val_a, val_b = unique_token(), unique_token()
    with workspace() as ws:
        zip_dir = unique_token()
        zip_path = _write_zip(
            ws,
            f"{zip_dir}/bundle.zip",
            module,
            (
                f"from {pkg} import find_envfile\n"
                "found = find_envfile()\n"
                "print('FOUND=' + found)\n"
            ),
        )
        env_a = _write_env(ws, f"{zip_dir}/.env", name, val_a)
        env_b = _write_env(ws, f"{unique_token()}/.env", name, val_b)
        work = env_b.parent
        outer = (
            "import sys\n"
            f"sys.path.insert(0, {str(zip_path)!r})\n"
            f"import {module}\n"
        )
        result = ws.run_script(
            outer,
            relpath=f"{zip_dir}/outer.py",
            cwd=work,
        )
        found = located_from_script(result, label="zip-beside")
        require_same_path(found, env_a, origin="zip-beside")
        assert Path(found).resolve() != Path(env_b).resolve()


# ---------------------------------------------------------------------------
# H. No-arg load / values-mapping use this location
# ---------------------------------------------------------------------------


def test_no_arg_load_walks_from_script():
    pkg = product_package_name()
    with workspace() as ws:
        layout = _split_starts(ws)
        result = ws.run_script(
            _load_source(pkg, layout["name"]),
            relpath=layout["script_rel"],
            cwd=layout["work"],
        )
        stdout = require_script_success(result, label="no-arg-load")
        has = require_labeled_line(stdout, "HAS", origin="no-arg-load")
        env = require_labeled_line(stdout, "ENV", origin="no-arg-load")
        assert has == "1", f"no-arg load did not write {layout['name']!r}"
        assert env == layout["val_a"], (
            f"no-arg load wrote {env!r}, not script-ancestor {layout['val_a']!r}"
        )
        assert env != layout["val_b"]


def test_no_arg_values_mapping_walks_from_script():
    pkg = product_package_name()
    with workspace() as ws:
        layout = _split_starts(ws)
        result = ws.run_script(
            _mapping_source(pkg, layout["name"]),
            relpath=layout["script_rel"],
            cwd=layout["work"],
        )
        stdout = require_script_success(result, label="no-arg-mapping")
        has = require_labeled_line(stdout, "HAS", origin="no-arg-mapping")
        mapped = require_labeled_line(stdout, "MAP", origin="no-arg-mapping")
        assert has == "1", f"no-arg mapping missed {layout['name']!r}"
        assert mapped == layout["val_a"], (
            f"no-arg mapping wrote {mapped!r}, not script-ancestor {layout['val_a']!r}"
        )
        assert mapped != layout["val_b"]


def test_no_arg_load_public_adjacent_env():
    pkg = product_package_name()
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        folder = unique_token()
        ws.write(f"{folder}/.env", f"a=b\n{name}={value}\n")
        work = ws.resolve(folder)
        source = _load_source(pkg, "a") + (
            f"print('RT_HAS=' + ('1' if {name!r} in os.environ else '0'))\n"
            f"print('RT=' + (os.environ[{name!r}] if {name!r} in os.environ else ''))\n"
        )
        result = ws.run_script(
            source,
            relpath=f"{folder}/caller.py",
            cwd=work,
        )
        stdout = require_script_success(result, label="public-adjacent")
        has = require_labeled_line(stdout, "HAS", origin="public-adjacent")
        env = require_labeled_line(stdout, "ENV", origin="public-adjacent")
        assert has == "1"
        assert env == "b"
        rt_has = require_labeled_line(stdout, "RT_HAS", origin="public-adjacent")
        rt = require_labeled_line(stdout, "RT", origin="public-adjacent")
        assert rt_has == "1"
        assert rt == value


# ---------------------------------------------------------------------------
# I. CLI default path is not this walk
# ---------------------------------------------------------------------------


def test_cli_get_reads_cwd_envfile():
    name, value = unique_token(), unique_token()
    with workspace() as ws:
        work = ws.mkdir(unique_token())
        _write_env(ws, f"{work.name}/.env", name, value)
        result = ws.run_module(["get", name], cwd=work)
        print(
            f"cli-get returncode={result.returncode} stdout={result.stdout_text!r}",
            flush=True,
        )
        assert result.returncode == 0, (
            f"cli get exited {result.returncode}; stderr={result.stderr_text!r}"
        )
        assert value in result.stdout_text.splitlines(), (
            f"cli get did not print {value!r}; stdout={result.stdout_text!r}"
        )


def test_cli_get_does_not_walk_ancestors():
    name, value = unique_token(), unique_token()
    other, other_val = unique_token(), unique_token()
    with workspace() as ws:
        leaf = ws.mkdir("anc/leaf")
        ancestor = _write_env(ws, "anc/.env", name, value)
        lib = located_text(
            _locate_in(ws, leaf, usecwd=True), origin="cli-lib-walk"
        )
        require_same_path(lib, ancestor, origin="cli-lib-walk")
        missing_file = ws.run_module(["get", name], cwd=leaf)
        print(
            f"cli-no-walk returncode={missing_file.returncode} "
            f"stdout={missing_file.stdout_text!r} "
            f"stderr={missing_file.stderr_text[:400]!r}",
            flush=True,
        )
        assert value not in missing_file.stdout_text.splitlines(), (
            "CLI get delivered the ancestor binding; default path must not walk"
        )
        assert missing_file.returncode != 0, (
            "CLI get against a missing working-directory .env must not succeed; "
            f"stdout={missing_file.stdout_text!r}"
        )
        file_report = (
            missing_file.stderr_text + missing_file.stdout_text
        ).strip()
        assert file_report, (
            "operator-visible report must identify that the env file "
            "could not be opened; empty output is not that carrier"
        )
        key_cwd = ws.mkdir(unique_token())
        _write_env(ws, f"{key_cwd.name}/.env", other, other_val)
        missing_key = ws.run_module(["get", name], cwd=key_cwd)
        print(
            f"cli-missing-key returncode={missing_key.returncode} "
            f"stdout={missing_key.stdout_text!r} "
            f"stderr={missing_key.stderr_text[:400]!r}",
            flush=True,
        )
        assert missing_key.returncode != 0, (
            "CLI get of a missing name in an existing file must not succeed"
        )
        assert missing_key.stdout_text.strip() == "", (
            "missing-key class must have empty output; "
            f"stdout={missing_key.stdout_text!r}"
        )
        assert missing_file.returncode != missing_key.returncode, (
            "missing-file usage-style exit must not be the missing-key class; "
            f"file={missing_file.returncode} key={missing_key.returncode}"
        )
