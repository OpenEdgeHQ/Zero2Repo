"""Judge-process import ban: workspace importers only, ecosystem-routed."""

from __future__ import annotations

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


def test_npm_ecosystem_requires_node_block() -> None:
    spec = SimpleNamespace(ecosystem="npm", import_ban=("js-yaml",))
    env = _import_ban_env(spec)
    assert env["CODING_BENCH_IMPORT_BAN"] == "js-yaml"
    assert "--require" in env["NODE_OPTIONS"]
    assert "_cb_import_block.cjs" in env["NODE_OPTIONS"]


def test_unknown_ecosystem_does_not_double_enable() -> None:
    spec = SimpleNamespace(ecosystem="cargo", import_ban=("demo",))
    env = _import_ban_env(spec)
    assert env == {"CODING_BENCH_IMPORT_BAN": "demo"}
    assert "NODE_OPTIONS" not in env
