"""Judge-process import ban: workspace importers only, ecosystem-routed."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from coding_bench_harbor import pytest_launcher as launcher  # noqa: E402
from cbrun.judge import _import_ban_env  # noqa: E402


def test_workspace_importer_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    product = workspace / "product.py"
    product.write_text("import yaml\n", encoding="utf-8")
    monkeypatch.setenv("CODING_BENCH_IMPORT_BAN", "yaml")
    monkeypatch.chdir(workspace)
    finder = launcher._WorkspaceImportBan(["yaml"], workspace)

    monkeypatch.setattr(
        launcher,
        "_importer_under_workspace",
        lambda _ws: True,
    )
    with pytest.raises(ImportError, match="CODING_BENCH_IMPORT_BAN"):
        finder.find_spec("yaml", None)


def test_hidden_tests_may_import_banned_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    hidden = tmp_path / "tests" / "final" / "test_x.py"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("import yaml\n", encoding="utf-8")
    monkeypatch.setattr(
        launcher,
        "_importer_under_workspace",
        lambda _ws: False,
    )
    finder = launcher._WorkspaceImportBan(["yaml"], workspace)
    assert finder.find_spec("yaml", None) is None


def test_python_ecosystem_does_not_set_node_options() -> None:
    spec = SimpleNamespace(ecosystem="pip", import_ban=("yaml",))
    env = _import_ban_env(spec)
    assert env["CODING_BENCH_IMPORT_BAN"] == "yaml"
    assert "NODE_OPTIONS" not in env


def test_npm_ecosystem_preloads_cjs_and_esm_hooks() -> None:
    spec = SimpleNamespace(ecosystem="npm", import_ban=("js-yaml",))
    env = _import_ban_env(spec)
    assert env["CODING_BENCH_IMPORT_BAN"] == "js-yaml"
    assert "--require /tests/_cb_import_block.cjs" in env["NODE_OPTIONS"]
    # Products shipped as ESM never pass through the CJS resolver.
    assert "--import /tests/_cb_import_block_esm.mjs" in env["NODE_OPTIONS"]


def test_launcher_prepends_node_shim_dir_to_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """runuser resets PATH; the launcher re-applies the judge's node shim dir."""
    monkeypatch.setenv("CODING_BENCH_NODE_SHIM_DIR", "/tests/bin")
    monkeypatch.setenv("PATH", "/usr/local/bin:/tests/bin:/usr/bin")
    monkeypatch.setenv("CODING_BENCH_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("CODING_BENCH_TESTS_FINAL", str(tmp_path))
    seen: dict[str, str] = {}

    def fake_main(args):
        seen["path"] = launcher.os.environ["PATH"]
        return 0

    monkeypatch.setattr(pytest, "main", fake_main)
    assert launcher.main([]) == 0
    assert seen["path"] == "/tests/bin:/usr/local/bin:/usr/bin"


_HARBOR = BENCHMARK_ROOT / "coding_bench_harbor"
_NODE = shutil.which("node")


def _node_gate(tmp_path: Path, script: str, *, name: str, judge_bans: str = "") -> str:
    """Run *script* under both hooks with a fake banned package vendored in /app."""
    app = tmp_path / "app"
    pkg = app / "node_modules" / "fakeyaml"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "package.json").write_text(
        '{"name":"fakeyaml","type":"module","exports":{".":{"import":"./index.mjs","require":"./index.cjs"}}}'
    )
    (pkg / "index.mjs").write_text("export const load = () => 1;\n")
    (pkg / "index.cjs").write_text("exports.load = () => 1;\n")
    (app / name).write_text(script)
    env = {
        **os.environ,
        "NODE_OPTIONS": "",
        "CODING_BENCH_WORKSPACE": str(app),
        "CODING_BENCH_IMPORT_BAN": "fakeyaml,fakeyaml/",
        "CODING_BENCH_JUDGE_BANS": judge_bans,
    }
    proc = subprocess.run(
        [
            _NODE,
            "--require", str(_HARBOR / "_cb_import_block.cjs"),
            "--import", str(_HARBOR / "_cb_import_block_esm.mjs"),
            str(app / name),
        ],
        cwd=app, env=env, capture_output=True, text=True, timeout=60,
    )
    return proc.stdout + proc.stderr


@pytest.mark.skipif(_NODE is None, reason="node not installed")
@pytest.mark.parametrize(
    ("name", "script", "expect"),
    [
        ("esm_root.mjs", 'import "fakeyaml"; console.log("PASSED");', "CODING_BENCH_IMPORT_BAN"),
        ("esm_deep.mjs", 'import "./node_modules/fakeyaml/index.mjs"; console.log("PASSED");', "CODING_BENCH_IMPORT_BAN"),
        ("cjs_root.cjs", 'require("fakeyaml"); console.log("PASSED");', "CODING_BENCH_IMPORT_BAN"),
        ("cjs_deep.cjs", 'require("./node_modules/fakeyaml/index.cjs"); console.log("PASSED");', "CODING_BENCH_IMPORT_BAN"),
        ("esm_ok.mjs", 'import "node:fs"; console.log("PASSED");', "PASSED"),
        ("cjs_ok.cjs", 'require("fs"); console.log("PASSED");', "PASSED"),
    ],
)
def test_node_hooks_block_workspace_imports_of_banned_root(
    tmp_path: Path, name: str, script: str, expect: str
) -> None:
    out = _node_gate(tmp_path, script, name=name)
    assert expect in out, out


@pytest.mark.skipif(_NODE is None, reason="node not installed")
@pytest.mark.parametrize(
    ("name", "script"),
    [
        ("esm_net.mjs", 'import "node:net"; console.log("PASSED");'),
        ("cjs_net.cjs", 'require("node:net"); console.log("PASSED");'),
        ("cjs_net_bare.cjs", 'require("net"); console.log("PASSED");'),
    ],
)
def test_node_hooks_apply_judge_bans_to_builtins(tmp_path: Path, name: str, script: str) -> None:
    out = _node_gate(tmp_path, script, name=name, judge_bans="socket")
    assert "CODING_BENCH_JUDGE_BANS" in out, out


@pytest.mark.skipif(_NODE is None, reason="node not installed")
def test_node_hooks_leave_non_workspace_importers_alone(tmp_path: Path) -> None:
    _node_gate(tmp_path, "", name="seed.mjs")  # vendors fakeyaml under /app
    outside = tmp_path / "outside" / "t.mjs"
    outside.parent.mkdir()
    outside.write_text(
        f'import "{(tmp_path / "app" / "node_modules" / "fakeyaml" / "index.mjs").as_posix()}"; console.log("PASSED");'
    )
    env = {**os.environ, "NODE_OPTIONS": "", "CODING_BENCH_WORKSPACE": str(tmp_path / "app"), "CODING_BENCH_IMPORT_BAN": "fakeyaml"}
    proc = subprocess.run(
        [_NODE, "--require", str(_HARBOR / "_cb_import_block.cjs"), "--import", str(_HARBOR / "_cb_import_block_esm.mjs"), str(outside)],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert "PASSED" in proc.stdout, proc.stdout + proc.stderr


def test_unknown_ecosystem_does_not_double_enable() -> None:
    spec = SimpleNamespace(ecosystem="cargo", import_ban=("demo",))
    env = _import_ban_env(spec)
    assert env == {"CODING_BENCH_IMPORT_BAN": "demo"}
    assert "NODE_OPTIONS" not in env
