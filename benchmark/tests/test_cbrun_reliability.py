"""Fast tests for leakage boundaries, import probes, side-effect bans, docker argv."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from coding_bench_harbor._leakage import scan_leakage  # noqa: E402
from coding_bench_harbor import pytest_launcher as launcher  # noqa: E402
from cbrun.denylist import (  # noqa: E402
    import_root_from_ban_token,
    is_command_like_token,
    probe_banned_imports,
    probe_spec_from_payload,
    render_pip_module_hook,
    render_pip_shim,
    render_strip_script,
)
from cbrun.docker_env import Container, _exec_hit_wall  # noqa: E402
from cbrun.case_checks import check_case_assets  # noqa: E402
from cbrun.judge import JudgeOutcome, export_app, validate_judge_report  # noqa: E402
from cbrun.recipe import RecipeLockError  # noqa: E402
from cbrun.recipe_image import resource_fetch_command  # noqa: E402
from cbrun.infra_signals import invalid_reason, scan_log_text  # noqa: E402
from cbrun.rejudge import (  # noqa: E402
    check_must_fail_tests,
    iter_controls,
    parse_expect_reward,
    reward_matches,
)
from cbrun.state import atomic_json, digest, file_manifest, platform_name  # noqa: E402


def test_scan_leakage_uses_identifier_boundaries() -> None:
    hits = scan_leakage("the adapter loads data", ["ada"])
    assert hits == []
    hits = scan_leakage("use ada as a token", ["ada"])
    assert len(hits) == 1 and hits[0].occurrences == 1


def test_import_root_from_ban_token() -> None:
    assert import_root_from_ban_token("tomllib") == "tomllib"
    assert import_root_from_ban_token("tomli/") == "tomli"
    assert import_root_from_ban_token("@scope/pkg/extra") == "@scope/pkg"


def test_probe_skips_stdlib_and_fails_on_importable(tmp_path: Path) -> None:
    denylist = tmp_path / "denylist.json"
    denylist.write_text(
        '{"ecosystem":"pip","import_ban":["tomllib","definitely_missing_pkg_xyz"]}',
        encoding="utf-8",
    )

    class Fake:
        tail = "definitely_missing_pkg_xyz\t__ABSENT__"

    result = probe_banned_imports("img", denylist, runner=lambda _cmd: Fake())
    assert result.errors == []

    denylist.write_text(
        '{"ecosystem":"pip","import_ban":["click"]}',
        encoding="utf-8",
    )

    class Present:
        tail = "click\t/opt/conda/lib/python3.13/site-packages/click/__init__.py"

    result = probe_banned_imports("img", denylist, runner=lambda _cmd: Present())
    assert result.errors and "click" in result.errors[0] and "origin=" in result.errors[0]


def test_probe_flags_warm_tree_and_warns_on_runtime_equivalent(tmp_path: Path) -> None:
    denylist = tmp_path / "denylist.json"
    denylist.write_text(
        json.dumps(
            {
                "ecosystem": "source",
                "import_ban": ["ada.h", "ada/"],
                "install_ban": ["ada"],
                "runtime_equivalents": [
                    {
                        "import_root": "ada",
                        "runtime": "node",
                        "evidence": "builtin",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class Fake:
        tail = "warm\t/opt/cb-warm\tPRESENT\nrtver\tada\t2.9.0\t/opt/cbrun/runtime/node/bin/node\n"

    result = probe_banned_imports("img", denylist, runner=lambda _cmd: Fake())
    assert any("cb-warm" in err for err in result.errors)
    assert result.warnings and "process.versions.ada" in result.warnings[0]


def test_probe_spec_skips_header_tokens_for_command_v() -> None:
    spec = probe_spec_from_payload(
        {
            "import_ban": ["ada.h", "ada::", "tomli/"],
            "install_ban": ["ada"],
            "runtime_equivalents": [
                {"import_root": "ada", "runtime": "node", "evidence": "builtin"}
            ],
        }
    )
    assert "ada.h" not in spec.commands
    assert not is_command_like_token("ada.h")
    assert "ada" in spec.commands
    assert [row.import_root for row in spec.runtime_equivalents] == ["ada"]
    assert not hasattr(spec, "watch_ada")


def test_strip_script_has_no_plaintext_product_names() -> None:
    script = render_strip_script().lower()
    for token in ("click", "tomli", "dotenv", "h11", "typer", "js-yaml"):
        assert token not in script


def test_strip_script_removes_only_hashed_layout(tmp_path: Path) -> None:
    import hashlib
    import subprocess

    from cbrun.denylist import normalize_pkg_name

    site = tmp_path / "site"
    (site / "click").mkdir(parents=True)
    (site / "safe_pkg").mkdir()
    hashes = tmp_path / "denylist.hashes"
    digest = hashlib.sha256(normalize_pkg_name("click").encode()).hexdigest()
    hashes.write_text(digest + "\n", encoding="utf-8")
    script = tmp_path / "strip_banned.py"
    script.write_text(render_strip_script(), encoding="utf-8")
    env = {
        **dict(**__import__("os").environ),
        "CBRUN_DENYLIST_HASHES": str(hashes),
        "CBRUN_STRIP_SCAN_DIRS": str(site),
    }
    proc = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert not (site / "click").exists()
    assert (site / "safe_pkg").is_dir()
    assert proc.returncode == 0


def test_pip_shim_blocks_download_and_module_hook(tmp_path: Path) -> None:
    import hashlib

    from cbrun.denylist import normalize_pkg_name

    shim = render_pip_shim()
    assert "download" in shim and "wheel" in shim
    hook = tmp_path / "cbrun_denylist_hook.py"
    hook.write_text(render_pip_module_hook(), encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    try:
        import importlib

        mod = importlib.import_module("cbrun_denylist_hook")
        hashes = tmp_path / "denylist.hashes"
        hashes.write_text(
            hashlib.sha256(normalize_pkg_name("click").encode()).hexdigest() + "\n",
            encoding="utf-8",
        )
        with pytest.raises(SystemExit):
            mod.check_orig_argv(
                ["python3", "-m", "pip", "install", "click"],
                hashes_path=str(hashes),
            )
        mod.check_orig_argv(
            ["python3", "-m", "pip", "install", "pytest"],
            hashes_path=str(hashes),
        )
    finally:
        sys.path.pop(0)
        sys.modules.pop("cbrun_denylist_hook", None)


def test_ensure_agent_image_reuses_only_when_probe_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cbrun import images

    case_dir = tmp_path / "case006"
    (case_dir / "source").mkdir(parents=True)
    (case_dir / "source" / "denylist.json").write_text(
        '{"install_ban":["click"],"import_ban":["click"]}',
        encoding="utf-8",
    )
    calls = {"probe": 0, "rebuild": 0}

    class Clean:
        errors: list[str] = []
        warnings: list[str] = []

    class Dirty:
        errors = ["banned import root 'click' is importable"]
        warnings: list[str] = []

    def fake_probe(tag, path, **_k):
        calls["probe"] += 1
        return Dirty() if calls["probe"] == 1 else Clean()

    monkeypatch.setattr(images, "image_exists", lambda *_a, **_k: True)
    monkeypatch.setattr(images, "image_matches", lambda *_a, **_k: True)
    monkeypatch.setattr(images, "image_identity", lambda *_a, **_k: {"id": "sha256:abc"})
    monkeypatch.setattr(images, "write_shim_assets", lambda *_a, **_k: "")
    monkeypatch.setattr(images, "probe_banned_imports", fake_probe)
    monkeypatch.setattr(
        images,
        "probe_agent_runtime_leak",
        lambda *_a, **_k: Clean(),
    )
    monkeypatch.setattr(images, "log_probe_result", lambda *_a, **_k: None)
    monkeypatch.setattr(images, "extract_hidden_tests", lambda *_a, **_k: tmp_path)
    monkeypatch.setattr(
        images.subprocess,
        "run",
        lambda *_a, **_k: type("P", (), {"returncode": 0})(),
    )

    def fake_deliverable(case_dir, **_k):
        return "codingbench-benchmark/case006:deliverable"

    import cbrun.recipe_image as recipe_image

    monkeypatch.setattr(recipe_image, "ensure_deliverable_image", fake_deliverable)

    cache = tmp_path / "cache" / "case006" / "abc" / "tests" / "final"
    cache.mkdir(parents=True)
    (cache / "test_manifest.json").write_text("{}", encoding="utf-8")

    real = images.ensure_agent_image

    def wrapped(*args, **kwargs):
        if kwargs.get("force"):
            calls["rebuild"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(images, "ensure_agent_image", wrapped)
    monkeypatch.setenv("CBRUN_ALLOW_UNPINNED_CLI", "1")
    result = wrapped(
        "case006",
        cache_root=tmp_path / "cache",
        case_dir=case_dir,
        deliverable_image="codingbench-benchmark/case006:deliverable",
        environ={"CBRUN_ALLOW_UNPINNED_CLI": "1"},
    )
    assert calls["probe"] >= 1
    assert calls["rebuild"] == 1
    assert result.agent_image.endswith(":agent")


def test_build_env_image_reuses_only_when_probe_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cbrun import recipe_image

    case_dir = tmp_path / "case006"
    (case_dir / "source").mkdir(parents=True)
    (case_dir / "source" / "denylist.json").write_text(
        '{"install_ban":["click"],"import_ban":["click"]}',
        encoding="utf-8",
    )
    probes = {"n": 0}

    class Clean:
        errors: list[str] = []
        warnings: list[str] = []

    def fake_probe(*_a, **_k):
        probes["n"] += 1
        return Clean()

    monkeypatch.setattr(recipe_image, "docker_available", lambda: True)
    monkeypatch.setattr(recipe_image, "image_exists", lambda *_a, **_k: True)
    monkeypatch.setattr(recipe_image, "probe_banned_imports", fake_probe)
    monkeypatch.setattr(recipe_image, "log_probe_result", lambda *_a, **_k: None)
    monkeypatch.setattr(recipe_image, "env_recipe_tag", lambda cid: f"codingbench-env/{cid}:recipe-env")
    tag = recipe_image._build_env_image(
        case_dir, {}, {"install_command": "true"}, force=False
    )
    assert tag.endswith(":recipe-env")
    assert probes["n"] == 1


def test_side_effect_ban_blocks_workspace_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    monkeypatch.setattr(launcher, "_importer_under_workspace", lambda _ws: True)
    with pytest.raises(RuntimeError, match="JUDGE_BANS"):
        launcher._side_effect_hook("socket.connect", ("x",), workspace, {"socket"})


def test_exec_hit_wall_requires_137_at_budget() -> None:
    assert _exec_hit_wall(60.0, 137, 60.0) is True
    assert _exec_hit_wall(60.0, 137, 60.5) is True
    assert _exec_hit_wall(60.0, 137, 4.0) is False
    assert _exec_hit_wall(60.0, 1, 60.0) is False
    assert _exec_hit_wall(None, 137, 60.0) is False


def test_apply_judge_outcome_marks_incomplete_invalid() -> None:
    from cbrun.results import TrialResult
    from cbrun.run_case import _apply_judge_outcome

    def _result() -> TrialResult:
        return TrialResult("c", "codex", "m", reward=0.0, terminal_status="completed")

    timeout = _result()
    _apply_judge_outcome(
        timeout,
        JudgeOutcome(
            0.0, "judge timed out", 137, 60.0, completed=False, incomplete_reason="judge:timeout"
        ),
    )
    assert timeout.run_valid is False
    assert timeout.invalid_reason == "judge:timeout"

    killed = _result()
    _apply_judge_outcome(
        killed,
        JudgeOutcome(
            0.0, "no report", 137, 4.0, completed=False, incomplete_reason="judge:killed"
        ),
    )
    assert killed.run_valid is False
    assert killed.invalid_reason == "judge:killed"

    missing = _result()
    _apply_judge_outcome(
        missing,
        JudgeOutcome(
            0.0, "no report", 2, 1.0, completed=False, incomplete_reason="judge:no_report"
        ),
    )
    assert missing.run_valid is False
    assert missing.invalid_reason == "judge:no_report"

    internal = _result()
    _apply_judge_outcome(
        internal,
        JudgeOutcome(0.0, "shadowed pytest", 0, 1.0, report={"judge_error": "shadowed pytest"}),
    )
    assert internal.run_valid is True
    assert internal.invalid_reason is None
    assert internal.judge_error == "shadowed pytest"


def test_exec_argv_uses_pipefail_and_env_keys_only() -> None:
    c = Container("cid")
    argv = c._exec_argv("false | true", env={"OPENAI_API_KEY": "secret"})
    assert "bash" in argv and "-o" in argv and "pipefail" in argv
    assert "-e" in argv
    assert "OPENAI_API_KEY" in argv
    assert "OPENAI_API_KEY=secret" not in argv


def test_run_argv_does_not_inline_env_values() -> None:
    argv = Container.build_run_argv("img", env={"OPENAI_API_KEY": "secret"})
    assert "--platform" in argv
    assert "OPENAI_API_KEY" in argv
    assert "OPENAI_API_KEY=secret" not in " ".join(argv)


def test_export_app_refuses_empty_replacement(tmp_path: Path) -> None:
    class Fake:
        def cp_from(self, src, dst):
            return False

    with pytest.raises(RuntimeError, match="refusing to judge"):
        export_app(Fake(), tmp_path / "dest")  # type: ignore[arg-type]


def test_side_effect_ban_allows_hidden_tests(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    launcher._side_effect_hook("socket.connect", ("x",), workspace, {"socket"})


def test_side_effect_ban_off_when_undeclared(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    launcher._side_effect_hook("socket.connect", ("x",), workspace, set())


def test_side_effect_ban_lets_workspace_do_allowed_things(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A workspace caller doing something *not* banned must fall through silently."""
    workspace = tmp_path / "app"
    workspace.mkdir()
    monkeypatch.setattr(launcher, "_importer_under_workspace", lambda _ws: True)
    bans = {"socket", "subprocess", "filesystem_outside_workspace"}
    launcher._side_effect_hook("open", (str(workspace / "x.txt"), "r", 0), workspace, bans)
    launcher._side_effect_hook("open", (str(workspace / "x.txt"), "w", 0), workspace, bans)
    launcher._side_effect_hook("import", ("json", None, None, None, None), workspace, bans)
    launcher._side_effect_hook("os.listdir", (str(workspace),), workspace, bans)
    with pytest.raises(RuntimeError, match="outside /app"):
        launcher._side_effect_hook("open", (str(tmp_path / "leak.txt"), "w", 0), workspace, bans)
    with pytest.raises(RuntimeError, match="subprocess"):
        launcher._side_effect_hook("subprocess.Popen", (), workspace, bans)


def test_validate_judge_report_binary_and_counts() -> None:
    ok = {
        "reward": 1.0,
        "final": {"counts_parsed": True, "total_count": 3, "passed_count": 3, "failed_count": 0, "error_count": 0},
    }
    assert validate_judge_report(ok) == (1.0, None)
    reward, err = validate_judge_report({"reward": 0.5, "final": {"counts_parsed": True, "total_count": 1}})
    assert reward == 0.0 and err and "non-binary" in err
    reward, err = validate_judge_report({"reward": 1.0})
    assert reward == 0.0 and err and "counts" in err
    reward, err = validate_judge_report(
        {
            "reward": 1.0,
            "final": {
                "counts_parsed": True,
                "total_count": 2,
                "passed_count": 1,
                "failed_count": 1,
                "error_count": 0,
            },
        }
    )
    assert reward == 0.0 and err and "contradicts" in err
    assert validate_judge_report(None)[0] == 0.0


def test_atomic_json_and_file_manifest(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    atomic_json(path, {"schema_version": 1, "n": 2})
    assert path.read_text(encoding="utf-8").startswith("{")
    (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
    manifest = file_manifest(tmp_path)
    assert "a.txt" in manifest and len(manifest["a.txt"]) == 64
    assert digest({"x": 1}) == digest({"x": 1})
    assert digest({"x": 1}) != digest({"x": 2})


def test_platform_name_default_and_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CBRUN_PLATFORM", raising=False)
    monkeypatch.delenv("DOCKER_DEFAULT_PLATFORM", raising=False)
    assert platform_name() == "linux/amd64"
    monkeypatch.setenv("CBRUN_PLATFORM", "windows/amd64")
    with pytest.raises(ValueError, match="unsupported"):
        platform_name()


def test_resource_fetch_command_validates_manifest(tmp_path: Path) -> None:
    env = tmp_path / "source" / "env"
    env.mkdir(parents=True)
    assert resource_fetch_command(tmp_path) == ""
    (env / "resources.json").write_text(
        json.dumps(
            {
                "destination": "/opt/models",
                "resources": [
                    {
                        "id": "demo",
                        "url": "https://example.test/a.zip",
                        "sha256": "a" * 64,
                        "size": 4,
                        "license": "MIT",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    cmd = resource_fetch_command(tmp_path)
    assert "/opt/cbrun/fetch_resources.py" in cmd
    assert "/opt/models" in cmd
    (env / "resources.json").write_text(
        json.dumps({"destination": "relative", "resources": [{"id": "x", "url": "https://x", "sha256": "a", "size": 1, "license": "MIT"}]}),
        encoding="utf-8",
    )
    with pytest.raises(RecipeLockError, match="absolute"):
        resource_fetch_command(tmp_path)


def test_expect_reward_and_control_discovery(tmp_path: Path) -> None:
    assert parse_expect_reward("0") == 0.0
    assert parse_expect_reward("1") == 1.0
    assert parse_expect_reward(None) is None
    with pytest.raises(ValueError):
        parse_expect_reward("2")
    assert reward_matches(0.0, 0.0)
    assert not reward_matches(1.0, 0.0)
    assert reward_matches(1.0, None)
    control = tmp_path / "case004" / "controls" / "weak_concat"
    (control / "app").mkdir(parents=True)
    (control / "expect.json").write_text('{"reward": 0}\n', encoding="utf-8")
    rows = list(iter_controls(tmp_path))
    assert rows == [("case004", "weak_concat", control, 0.0)]


def _case003_line_break_helper():
    """Load the rewritten FP-01 line-break oracle without importing _harness."""
    import importlib.util
    import sys
    import types

    harness = types.ModuleType("_harness")

    class ErrorInfo:
        def __init__(self, message=None, text=None, reason=None, mark=None):
            self.message = message
            self.text = text
            self.reason = reason
            self.mark = mark

    harness.ErrorInfo = ErrorInfo
    harness.HarnessError = RuntimeError
    sys.modules["_harness"] = harness
    path = (
        BENCHMARK_ROOT
        / "cases"
        / "case003"
        / "milestones"
        / "final"
        / "tests"
        / "F01_helpers.py"
    )
    spec = importlib.util.spec_from_file_location("case003_f01_helpers", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_case003_line_break_count_oracle() -> None:
    """Later-line `@` must present count 1 (or 2 if one-based); first-line count 0."""
    helper = _case003_line_break_helper()
    ErrorInfo = helper.require_line_break_counts.__globals__["ErrorInfo"]

    later = ErrorInfo(message="parse failed at line-break 1")
    earlier = ErrorInfo(message="parse failed at line-break 0")
    helper.require_line_break_counts(
        later,
        earlier,
        later_source="a: 1\r\n@",
        covariates=("a: 1", "@", "\r\n"),
    )
    # A shared clock-style pair is not a line-break count.
    clock_later = ErrorInfo(message="failed at 10:30")
    clock_earlier = ErrorInfo(message="failed at 10:30")
    try:
        helper.require_line_break_counts(
            clock_later,
            clock_earlier,
            later_source="a: 1\r\n@",
            covariates=(),
        )
    except AssertionError:
        pass
    else:
        raise AssertionError("clock-style shared integers must not pass")


def test_independent_hmac_vector() -> None:
    import base64
    import hashlib
    import hmac

    secret = b"frozen-secret-key"
    payload = b"frozen-payload"
    expected = hmac.new(secret, payload, hashlib.sha1).digest()
    encoded = base64.urlsafe_b64encode(expected).rstrip(b"=")
    pad = b"=" * ((4 - len(encoded) % 4) % 4)
    assert base64.urlsafe_b64decode(encoded + pad) == expected
    weak = hashlib.sha1(secret).digest() + hashlib.sha1(payload).digest()
    assert weak != expected


def test_check_case_assets_imported() -> None:
    assert callable(check_case_assets)


class _ArchiveContainer:
    """Behaves like Docker: exec is refused once paused, cp still works."""

    def __init__(self) -> None:
        self.paused = False
        self.removed = False
        self.probed_while_paused: bool | None = None

    def path_exists(self, path: str) -> bool:
        self.probed_while_paused = self.paused
        return not self.paused and path == "/logs/agent"

    def pause(self) -> None:
        self.paused = True

    def cp_from(self, src: str, dst: Path) -> bool:
        dst.mkdir(parents=True, exist_ok=True)
        return True

    def remove(self) -> None:
        self.removed = True


def test_archive_probes_agent_logs_before_pause(tmp_path: Path) -> None:
    from cbrun.results import TrialResult
    from cbrun.run_case import _archive_trial

    container = _ArchiveContainer()
    result = TrialResult(case_id="c", backend="b", model="m", reward=0.0, terminal_status="error")
    _archive_trial(container, out_dir=tmp_path, result=result)  # type: ignore[arg-type]
    assert container.probed_while_paused is False
    assert container.paused and container.removed
    assert result.artifact_errors == []
    assert result.logs["workspace"] == str(tmp_path / "workspace")
    assert result.logs["container_logs"] == str(tmp_path / "container_logs")


def test_cli_build_images_does_not_require_cli_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cbrun import cli, recipe_image

    for key in list(__import__("os").environ):
        if key.startswith("CBRUN_"):
            monkeypatch.delenv(key, raising=False)
    (tmp_path / "caseX" / "source").mkdir(parents=True)
    (tmp_path / "caseX" / "source" / "manifest.json").write_text("{}", encoding="utf-8")
    built: list[str] = []
    monkeypatch.setattr(
        recipe_image, "ensure_deliverable_image", lambda case_dir, force=False: built.append(case_dir.name) or "tag"
    )
    code = cli.main(["--build-images", "--cases-root", str(tmp_path), "--case", "caseX"])
    assert code == 0 and built == ["caseX"]
    # Trial runs still refuse an unpinned CLI.
    code = cli.main(["--cases-root", str(tmp_path), "--case", "caseX", "--model", "x"])
    assert code == 2


def test_rejudge_passes_denylist_to_judge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from cbrun import rejudge

    seen: dict[str, object] = {}
    case = SimpleNamespace(case_id="caseX", judge_bans=("socket",))
    spec = SimpleNamespace(ecosystem="pip", import_ban=("yaml",))

    class _Ctr:
        def remove(self) -> None:
            seen["removed"] = True

    monkeypatch.setattr(rejudge, "load_case", lambda d: case)
    monkeypatch.setattr(rejudge, "require_denylist", lambda d: spec)
    monkeypatch.setattr(
        rejudge,
        "ensure_agent_image",
        lambda *a, **k: SimpleNamespace(agent_image="img", tests_cache_dir=tmp_path),
    )
    monkeypatch.setattr(rejudge, "discover_steps", lambda c: [object()])
    monkeypatch.setattr(rejudge, "synthesize_task_toml", lambda c, s: b"")
    monkeypatch.setattr(rejudge.Container, "start", staticmethod(lambda *a, **k: _Ctr()))
    monkeypatch.setattr(rejudge, "import_app", lambda c, w: None)

    def fake_run_judge(container, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(reward=0.0, judge_error=None)

    monkeypatch.setattr(rejudge, "run_judge", fake_run_judge)
    reward = rejudge.rejudge_workspace(
        case_dir=tmp_path, workspace=tmp_path, out_dir=tmp_path / "out", cache_root=tmp_path
    )
    assert reward == 0.0
    assert seen["denylist"] is spec
    assert seen["judge_bans"] == ("socket",)
    assert seen["removed"] is True


def _rejudge_stubs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spec) -> dict[str, object]:
    from types import SimpleNamespace

    from cbrun import rejudge

    seen: dict[str, object] = {"judged": False}
    case = SimpleNamespace(case_id="caseX", judge_bans=())
    monkeypatch.setattr(rejudge, "load_case", lambda d: case)
    monkeypatch.setattr(rejudge, "require_denylist", lambda d: spec)
    monkeypatch.setattr(
        rejudge,
        "ensure_agent_image",
        lambda *a, **k: SimpleNamespace(agent_image="img", tests_cache_dir=tmp_path),
    )
    monkeypatch.setattr(rejudge, "discover_steps", lambda c: [object()])
    monkeypatch.setattr(rejudge, "synthesize_task_toml", lambda c, s: b"")

    def _start(*a, **k):
        seen["judged"] = True
        raise AssertionError("judge container must not start")

    monkeypatch.setattr(rejudge.Container, "start", staticmethod(_start))
    return seen


def test_rejudge_static_scan_preempts_judge_like_a_trial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A trial scores a workspace that still imports a banned root 0 without
    judging; rejudge must apply the same gate, not judge it more leniently."""
    from types import SimpleNamespace

    from cbrun import rejudge

    spec = SimpleNamespace(ecosystem="npm", import_ban=("js-yaml", "js-yaml/"))
    seen = _rejudge_stubs(monkeypatch, tmp_path, spec)
    workspace = tmp_path / "control" / "app" / "src"
    workspace.mkdir(parents=True)
    (workspace / "index.ts").write_text('import yaml from "js-yaml";\nexport const load = yaml.load;\n')

    out = tmp_path / "out"
    reward = rejudge.rejudge_workspace(
        case_dir=tmp_path, workspace=tmp_path / "control", out_dir=out, cache_root=tmp_path
    )
    assert reward == 0.0
    assert seen["judged"] is False
    payload = json.loads((out / "rejudge.json").read_text())
    assert "js-yaml@" in payload["denylist_violation"]
    scan = json.loads((out / rejudge.DENYLIST_SCAN_REPORT).read_text())
    assert scan["import_hits"][0]["token"] == "js-yaml"
    assert scan["import_hits"][0]["line"] == 1


def test_rejudge_static_scan_skipped_when_denylist_not_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from cbrun import rejudge

    spec = SimpleNamespace(ecosystem="npm", import_ban=("js-yaml",))
    _rejudge_stubs(monkeypatch, tmp_path, spec)
    (tmp_path / "ws").mkdir()
    (tmp_path / "ws" / "a.js").write_text('require("js-yaml")\n')

    class _Ctr:
        def remove(self) -> None:
            pass

    monkeypatch.setattr(rejudge.Container, "start", staticmethod(lambda *a, **k: _Ctr()))
    monkeypatch.setattr(rejudge, "import_app", lambda c, w: None)
    monkeypatch.setattr(
        rejudge, "run_judge", lambda c, **k: SimpleNamespace(reward=1.0, judge_error=None, report={})
    )
    reward = rejudge.rejudge_workspace(
        case_dir=tmp_path,
        workspace=tmp_path / "ws",
        out_dir=tmp_path / "out",
        cache_root=tmp_path,
        enforce_denylist=False,
    )
    assert reward == 1.0
    assert not (tmp_path / "out" / rejudge.DENYLIST_SCAN_REPORT).exists()


def test_rejudge_main_rejects_must_fail_tests_when_scan_preempted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from types import SimpleNamespace

    from cbrun import rejudge

    spec = SimpleNamespace(ecosystem="pip", import_ban=("tomllib",))
    _rejudge_stubs(monkeypatch, tmp_path, spec)
    cases_root = tmp_path / "cases"
    (cases_root / "caseX" / "source").mkdir(parents=True)
    (cases_root / "caseX" / "source" / "manifest.json").write_text("{}", encoding="utf-8")
    control = tmp_path / "ctl"
    (control / "app").mkdir(parents=True)
    (control / "app" / "p.py").write_text("import tomllib\n", encoding="utf-8")
    (control / "expect.json").write_text(
        json.dumps({"reward": 0, "must_fail_tests": ["test_named"]}), encoding="utf-8"
    )
    code = rejudge.main(
        [
            "--case", "caseX",
            "--workspace", str(control),
            "--cases-root", str(cases_root),
            "--cache-root", str(tmp_path / "cache"),
            "--out", str(tmp_path / "out"),
            "--expect-reward", "0",
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "denylist_violation: upstream import/symbol present" in out
    assert "static denylist scan preempted the judge" in out
    # Reward-only controls (no must_fail_tests) are satisfied by the gate alone.
    (control / "expect.json").write_text(json.dumps({"reward": 0}), encoding="utf-8")
    code = rejudge.main(
        [
            "--case", "caseX",
            "--workspace", str(control),
            "--cases-root", str(cases_root),
            "--cache-root", str(tmp_path / "cache"),
            "--out", str(tmp_path / "out2"),
            "--expect-reward", "0",
        ]
    )
    assert code == 0


def test_rejudge_image_and_tests_dir_must_be_paired(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from cbrun import rejudge

    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "manifest.json").write_text("{}", encoding="utf-8")
    cases_root = tmp_path
    case_id = "caseX"
    (cases_root / case_id / "source").mkdir(parents=True)
    (cases_root / case_id / "source" / "manifest.json").write_text("{}", encoding="utf-8")
    code = rejudge.main(
        [
            "--case",
            case_id,
            "--workspace",
            str(tmp_path),
            "--cases-root",
            str(cases_root),
            "--out",
            str(tmp_path / "out"),
            "--image",
            "img:tag",
        ]
    )
    assert code == 2
    assert "--image and --tests-dir must be given together" in capsys.readouterr().out


def test_check_must_fail_tests_reward_only_warns_on_collection() -> None:
    errors, warnings = check_must_fail_tests(
        must_fail_tests=[],
        failed_tests=[],
        error_tests=["tests/F01_acceptance.py"],
        failed_count=0,
        error_count=19,
    )
    assert errors == []
    assert warnings


def test_check_must_fail_tests_requires_failed_not_error() -> None:
    errors, _warnings = check_must_fail_tests(
        must_fail_tests=["test_named"],
        failed_tests=[],
        error_tests=["tests/F12_acceptance.py::test_named"],
        failed_count=0,
        error_count=1,
    )
    assert errors and "ERROR" in errors[0]


def test_check_must_fail_tests_suffix_hit() -> None:
    errors, warnings = check_must_fail_tests(
        must_fail_tests=["test_named"],
        failed_tests=["tests/F12_acceptance.py::test_named"],
        error_tests=[],
        failed_count=1,
        error_count=0,
    )
    assert errors == []
    assert warnings == []


def test_infra_signals_ignore_bare_401_and_recovered_filter() -> None:
    counts = scan_log_text("===== 401 passed in 1.00s =====\ncontent_filter once\n")
    assert "auth" not in counts
    assert counts["content_filter"] == 1
    assert (
        invalid_reason(
            submitted=True,
            log_text="Incomplete response returned, reason: content_filter\n",
        )
        is None
    )
    assert (
        invalid_reason(submitted=False, log_text="HTTP 401 invalid_api_key\n")
        == "infra:auth"
    )


def test_infra_signals_ignore_documentation_rate_limit_wording() -> None:
    prose = (
        "implements rate limiting per RFC 6585\n"
        "returns Unauthorized on missing token\n"
    )
    assert scan_log_text(prose) == {}
    counts = scan_log_text("HTTP 429 from the gateway\n")
    assert counts["rate_limit"] == 1


def test_denylist_module_has_no_product_ada_special_case() -> None:
    text = (BENCHMARK_ROOT / "cbrun" / "denylist.py").read_text(encoding="utf-8")
    assert "watch_ada" not in text
    assert "adaver" not in text


def test_probe_agent_runtime_leak_flags_new_login_path() -> None:
    from cbrun.denylist import probe_agent_runtime_leak

    class Box:
        def __init__(self, tail: str):
            self.tail = tail

    seen = {"n": 0}

    def runner(_cmd: str):
        seen["n"] += 1
        return Box("/usr/bin/node" if seen["n"] == 2 else "")

    result = probe_agent_runtime_leak("agent", "deliv", ["node"], runner=runner)
    assert result.errors and "node" in result.errors[0]


def test_cow_fstype_covering_matches_helper_visible_mounts() -> None:
    from cbrun.substrates import cow_fstype_covering, helper_visible_cow_mounts

    text = (
        "overlay / overlay rw 0 0\n"
        "/dev/loop0 /mnt/cb-substrate/cow_fs xfs rw,relatime 0 0\n"
        "/dev/sda1 /var/tmp ext4 rw 0 0\n"
    )
    assert helper_visible_cow_mounts(text) == ["/mnt/cb-substrate/cow_fs"]
    assert cow_fstype_covering(Path("/mnt/cb-substrate/cow_fs"), text) == "xfs"
    assert cow_fstype_covering(Path("/var/tmp"), text) is None


def test_substrate_unknown_provider_raises() -> None:
    from cbrun.substrates import SubstrateUnavailable, mounted_substrates

    with pytest.raises(SubstrateUnavailable, match="unknown provider"):
        with mounted_substrates({"judge_substrates": ["nope"]}, Path("/tmp")):
            pass


def test_substrates_module_has_no_posix_only_import_at_load() -> None:
    """Windows hosts import cbrun.substrates for every judge; fcntl must be lazy."""
    import ast

    from cbrun import substrates

    tree = ast.parse(Path(substrates.__file__).read_text(encoding="utf-8"))
    top_level = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module for node in tree.body if isinstance(node, ast.ImportFrom)
    }
    assert "fcntl" not in top_level


def test_cow_fs_refuses_explicitly_on_non_linux_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from cbrun import substrates

    monkeypatch.setattr(substrates.sys, "platform", "win32")
    assert substrates.supports_ficlone(tmp_path) is False
    with pytest.raises(substrates.SubstrateUnavailable, match="Linux host"):
        with substrates.mounted_substrates({"judge_substrates": ["cow_fs"]}, tmp_path):
            pass
    # Cases that declare no substrate never touch the FICLONE path.
    with substrates.mounted_substrates({}, tmp_path) as mounts:
        assert mounts == []


def test_cow_fs_refuses_explicitly_without_fcntl_module(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from cbrun import substrates

    monkeypatch.setitem(sys.modules, "fcntl", None)
    assert substrates.supports_ficlone(tmp_path) is False
    if sys.platform == "linux":
        with pytest.raises(substrates.SubstrateUnavailable, match="fcntl"):
            with substrates.mounted_substrates({"judge_substrates": ["cow_fs"]}, tmp_path):
                pass


def test_builtin_codex_spec_declares_node_runtime() -> None:
    from cbrun.agent_spec import builtin_spec

    assert builtin_spec("codex").runtime == "node"
    assert builtin_spec("cursor").runtime is None
