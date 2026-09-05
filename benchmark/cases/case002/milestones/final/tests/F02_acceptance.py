# feature: F02
"""Install, uninstall, and repository hook update acceptance tests.

PRD: FP-02. Assertions stay at the PRD's precision: chosen Git config
scope, four named hook types, skip-smudge / skip-repo contrasts, foreign
filter and foreign-hook conflict outcomes, and form-open hook-integration
guidance. Filter argv, hook-script goldens, banner wording, and exit
codes are not pinned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from _harness import token, workspace
from _helpers import (
    FILTER_KEYS,
    HOOK_TYPES,
    caller_visible,
    foreign_filter_command,
    foreign_hook_body,
    git_version_at_least,
    hooks_dir,
    isolated_system_scope,
    lookup_git_config,
    path_without_product_bin,
    read_git_orbulk_hook_bodies,
    read_hook,
    require_filters_point_at_git_orbulk,
    require_filters_unset,
    require_git_config_set,
    require_guidance_remainder_unlike_option_covariates,
    require_guidance_remainder_unlike_runs,
    require_hook_absent,
    require_hook_equals_standard,
    require_hook_integration_guidance,
    require_hooks_absent,
    require_rejected_unlike_clean,
    require_success,
    write_hook,
)


def _seed_filters(ws, value, **scope) -> None:
    """Write the three lfs filter keys in *scope*. A failed write is not absence."""
    file = scope.get("file")
    worktree = scope.get("worktree", False)
    system = scope.get("system", False)
    env_updates = scope.get("env_updates")
    cwd = scope.get("cwd")
    for key in FILTER_KEYS:
        if file is not None:
            result = ws.git_config_set(key, value, file=file)
        elif worktree:
            result = ws.git(
                ["config", "--worktree", key, value],
                env_updates=env_updates,
                cwd=cwd,
            )
        elif system:
            result = ws.git(
                ["config", "--system", key, value],
                env_updates=env_updates,
                cwd=cwd,
            )
        else:
            require_git_config_set(
                ws,
                key,
                value,
                local=bool(scope.get("local")),
                global_=bool(scope.get("global_")),
            )
            continue
        assert result.returncode == 0, (
            f"git config {key!r} failed (exit {result.returncode}): "
            f"{result.stderr_text}"
        )


def _same_filters(ws, value, **scope) -> None:
    for key in FILTER_KEYS:
        observed = lookup_git_config(ws, key, **scope)
        assert observed == value, (
            f"{key} changed from the seeded value {value!r} to {observed!r}"
        )


def _enable_worktree_config(ws) -> None:
    require_git_config_set(
        ws, "core.repositoryformatversion", "1", local=True
    )
    require_git_config_set(ws, "extensions.worktreeConfig", "true", local=True)


def _remove_hook(ws, hook_type, *, hooks_relpath=None) -> None:
    path = hooks_dir(ws, hooks_relpath) / hook_type
    assert path.is_file(), f"cannot remove missing hook file {path}"
    path.unlink()


def _installed_standard_hooks(ws) -> dict[str, str]:
    ws.init_repo()
    require_success(ws.invoke_via_git(["install"]))
    return read_git_orbulk_hook_bodies(ws)


def _strip_paths(*paths: Path | str) -> list[str]:
    tokens: list[str] = []
    for path in paths:
        text = str(path)
        if text:
            tokens.append(text)
        resolved = str(Path(path).resolve()) if not isinstance(path, str) else text
        if resolved and resolved not in tokens:
            tokens.append(resolved)
    return tokens


def _assert_filter_keys_written(values: dict[str, str]) -> dict[str, str]:
    """PRD: the chosen scope holds lfs clean, smudge, and process."""
    assert set(values) == set(FILTER_KEYS), (
        "expected filter.lfs.clean, filter.lfs.smudge, and filter.lfs.process, "
        f"got {sorted(values)!r}"
    )
    return values


def _assert_four_hook_types(bodies: dict[str, str]) -> dict[str, str]:
    """PRD: pre-push, post-checkout, post-commit, and post-merge are present."""
    assert set(bodies) == set(HOOK_TYPES), (
        "expected pre-push, post-checkout, post-commit, and post-merge, "
        f"got {sorted(bodies)!r}"
    )
    return bodies


def _assert_hook_file_absent(ws, hook_type, *, hooks_relpath=None) -> None:
    path = hooks_dir(ws, hooks_relpath) / hook_type
    assert not path.is_file(), (
        f"expected {hook_type} hook to be absent, found {path}"
    )


# ---------------------------------------------------------------------------
# A. Filter installation and overwrite rules
# ---------------------------------------------------------------------------


def test_install_default_writes_global_lfs_filters(isolated_ws):
    """In-repo default install writes global lfs filters, not local."""
    isolated_ws.init_repo()
    result = isolated_ws.invoke_via_git(["install"])
    require_success(result)
    values = _assert_filter_keys_written(
        require_filters_point_at_git_orbulk(isolated_ws, global_=True)
    )
    require_filters_unset(isolated_ws, local=True)
    print(f"global filters={values!r}")
    print(f"install stdout={result.stdout_text!r}")
    assert result.returncode == 0, (
        "default in-repo install must succeed"
    )
    for key in FILTER_KEYS:
        assert lookup_git_config(isolated_ws, key, local=True) is None, (
            f"default install wrote {key} into local scope"
        )


def test_install_outside_repo_writes_global_filters_only(isolated_ws):
    """Outside a repository, install writes global filters and no hook dir."""
    result = isolated_ws.invoke_via_git(["install"])
    require_success(result)
    values = require_filters_point_at_git_orbulk(isolated_ws, global_=True)
    print(f"outside-repo global filters={values!r}")
    assert not (isolated_ws.path / ".git" / "hooks").exists(), (
        "install outside a repository created a hooks directory"
    )
    require_hooks_absent(isolated_ws)


def test_install_via_direct_binary_writes_filters(isolated_ws):
    """Direct binary install writes the same global lfs filter trio."""
    result = isolated_ws.invoke(["install", "--skip-repo"])
    require_success(result)
    values = _assert_filter_keys_written(
        require_filters_point_at_git_orbulk(isolated_ws, global_=True)
    )
    print(f"direct-binary filters={values!r}")
    assert result.returncode == 0, (
        "direct-binary install must succeed"
    )


def test_install_leaves_non_git_orbulk_filters_intact_and_fails():
    """Non-force install leaves a pre-existing non-Orbulk filter and fails."""
    foreign = foreign_filter_command()
    with workspace() as ws:
        _seed_filters(ws, foreign, global_=True)
        result = ws.invoke_via_git(["install", "--skip-repo"])
        print(f"non-force foreign-filter exit={result.returncode}")
        print(f"stderr={result.stderr_text!r}")
        assert result.returncode != 0, (
            "non-force install overwrote or accepted a non-Orbulk filter"
        )
        _same_filters(ws, foreign, global_=True)


def test_install_force_replaces_non_git_orbulk_filters():
    """Force is the only difference from the non-force foreign-filter arm."""
    foreign = foreign_filter_command()
    with workspace() as blocked:
        _seed_filters(blocked, foreign, global_=True)
        blocked_run = blocked.invoke_via_git(["install", "--skip-repo"])
        assert blocked_run.returncode != 0, (
            "live baseline: non-force install must fail on a non-Orbulk filter"
        )
        _same_filters(blocked, foreign, global_=True)
    with workspace() as forced:
        _seed_filters(forced, foreign, global_=True)
        result = forced.invoke_via_git(["install", "--skip-repo", "--force"])
        require_success(result)
        values = require_filters_point_at_git_orbulk(forced, global_=True)
        for key, value in values.items():
            assert value != foreign, (
                f"{key} still equals the foreign command after --force"
            )
        print(f"force-replaced filters={values!r}")


def test_install_own_skip_smudge_replaced_without_force():
    """VCS Orbulk's own skip-smudge values are not a protected non-Orbulk filter."""
    with workspace() as skip_only:
        skip_only.init_repo()
        require_success(
            skip_only.invoke_via_git(["install", "--skip-smudge", "--skip-repo"])
        )
        skip_values = require_filters_point_at_git_orbulk(skip_only, global_=True)
    with workspace() as then_ordinary:
        then_ordinary.init_repo()
        require_success(
            then_ordinary.invoke_via_git(
                ["install", "--skip-smudge", "--skip-repo"]
            )
        )
        second = then_ordinary.invoke_via_git(["install", "--skip-repo"])
        require_success(second)
        ordinary = require_filters_point_at_git_orbulk(then_ordinary, global_=True)
    print(f"skip-only={skip_values!r}")
    print(f"after-ordinary={ordinary!r}")
    assert ordinary["filter.lfs.smudge"] != skip_values["filter.lfs.smudge"], (
        "ordinary install did not replace skip-smudge smudge without --force"
    )
    assert ordinary["filter.lfs.process"] != skip_values["filter.lfs.process"], (
        "ordinary install did not replace skip-smudge process without --force"
    )


def test_install_own_ordinary_replaced_by_skip_smudge_without_force():
    """Skip-smudge replaces VCS Orbulk's own ordinary smudge/process without force."""
    with workspace() as ordinary_only:
        ordinary_only.init_repo()
        require_success(
            ordinary_only.invoke_via_git(["install", "--skip-repo"])
        )
        ordinary = require_filters_point_at_git_orbulk(ordinary_only, global_=True)
    with workspace() as then_skip:
        then_skip.init_repo()
        require_success(then_skip.invoke_via_git(["install", "--skip-repo"]))
        second = then_skip.invoke_via_git(
            ["install", "--skip-smudge", "--skip-repo"]
        )
        require_success(second)
        skipped = require_filters_point_at_git_orbulk(then_skip, global_=True)
    print(f"ordinary={ordinary!r}")
    print(f"after-skip={skipped!r}")
    assert skipped["filter.lfs.smudge"] != ordinary["filter.lfs.smudge"], (
        "skip-smudge did not replace ordinary smudge without --force"
    )
    assert skipped["filter.lfs.process"] != ordinary["filter.lfs.process"], (
        "skip-smudge did not replace ordinary process without --force"
    )


# ---------------------------------------------------------------------------
# B. Repository hooks and shared hooks-path
# ---------------------------------------------------------------------------


def test_install_in_repo_installs_four_hooks(isolated_ws):
    """In-repo install (not skip-repo) writes all four VCS Orbulk hook types."""
    isolated_ws.init_repo()
    result = isolated_ws.invoke_via_git(["install"])
    require_success(result)
    require_filters_point_at_git_orbulk(isolated_ws, global_=True)
    bodies = _assert_four_hook_types(read_git_orbulk_hook_bodies(isolated_ws))
    print(f"hook types installed={list(bodies)}")
    for hook_type, body in bodies.items():
        print(f"{hook_type} bytes={len(body)}")
    assert result.returncode == 0, (
        "in-repo install must succeed"
    )


def test_install_outside_repo_does_not_write_hooks(isolated_ws):
    """Non-repository cwd does not receive the four hook files."""
    result = isolated_ws.invoke_via_git(["install"])
    require_success(result)
    print(f"outside-repo install cwd={isolated_ws.path}")
    require_hooks_absent(isolated_ws)
    assert not (isolated_ws.path / ".git" / "hooks").exists(), (
        "install outside a repository created .git/hooks"
    )


def test_install_honors_shared_hooks_path(isolated_ws):
    """When Git is new enough, hooks go to core.hooksPath, not .git/hooks."""
    isolated_ws.init_repo()
    rel = f"hk_{token()}"
    require_git_config_set(
        isolated_ws, "core.hooksPath", rel, local=True
    )
    result = isolated_ws.invoke_via_git(["install"])
    require_success(result)
    assert result.returncode == 0, (
        "install with core.hooksPath set must succeed"
    )
    if git_version_at_least(isolated_ws, 2, 9):
        bodies = _assert_four_hook_types(
            read_git_orbulk_hook_bodies(isolated_ws, hooks_relpath=rel)
        )
        print(f"hooks-path {rel} bodies={list(bodies)}")
        require_hooks_absent(isolated_ws)
        for hook_type in HOOK_TYPES:
            _assert_hook_file_absent(isolated_ws, hook_type)
    else:
        print("Git < 2.9.0: shared hooks-path obligation does not apply")
        bodies = _assert_four_hook_types(
            read_git_orbulk_hook_bodies(isolated_ws)
        )
        require_hooks_absent(isolated_ws, hooks_relpath=rel)
        for hook_type in HOOK_TYPES:
            _assert_hook_file_absent(
                isolated_ws, hook_type, hooks_relpath=rel
            )
        print(f"default-hooks bodies={list(bodies)}")


# ---------------------------------------------------------------------------
# C. Scopes, skip-smudge, skip-repo, manual
# ---------------------------------------------------------------------------


def test_install_local_scope_spares_global():
    """--local writes repository filters; a seeded global foreign value stays."""
    with workspace() as baseline:
        baseline.init_repo()
        require_success(baseline.invoke_via_git(["install"]))
        require_filters_point_at_git_orbulk(baseline, global_=True)
        require_filters_unset(baseline, local=True)
        print("live baseline: default install wrote global, not local")
    foreign = foreign_filter_command()
    with workspace() as local_ws:
        local_ws.init_repo()
        _seed_filters(local_ws, foreign, global_=True)
        result = local_ws.invoke_via_git(["install", "--local"])
        require_success(result)
        require_filters_point_at_git_orbulk(local_ws, local=True)
        _same_filters(local_ws, foreign, global_=True)
        print("local install spared the seeded global foreign filter")


def test_install_file_scope_spares_global_and_local(isolated_ws):
    """--file writes only that file; hooks still install inside a repository."""
    global_foreign = foreign_filter_command()
    local_foreign = foreign_filter_command()
    isolated_ws.init_repo()
    _seed_filters(isolated_ws, global_foreign, global_=True)
    _seed_filters(isolated_ws, local_foreign, local=True)
    cfg = isolated_ws.path / f"cfg_{token()}"
    result = isolated_ws.invoke_via_git(["install", f"--file={cfg}"])
    require_success(result)
    require_filters_point_at_git_orbulk(isolated_ws, file=cfg)
    _same_filters(isolated_ws, global_foreign, global_=True)
    _same_filters(isolated_ws, local_foreign, local=True)
    read_git_orbulk_hook_bodies(isolated_ws)
    print(f"file-scope config={cfg}")


def test_install_worktree_scope_or_unavailable():
    """Worktree scope writes worktree config when supported; else it is refused."""
    with workspace() as local_ok:
        local_ok.init_repo()
        ok = local_ok.invoke_via_git(["install", "--local"])
        require_success(ok)
        require_filters_point_at_git_orbulk(local_ok, local=True)
        print("live baseline: --local succeeded")
    foreign_global = foreign_filter_command()
    foreign_local = foreign_filter_command()
    with workspace() as ws:
        ws.init_repo()
        if git_version_at_least(ws, 2, 20):
            _enable_worktree_config(ws)
            _seed_filters(ws, foreign_global, global_=True)
            _seed_filters(ws, foreign_local, local=True)
            result = ws.invoke_via_git(["install", "--worktree"])
            require_success(result)
            require_filters_point_at_git_orbulk(ws, worktree=True)
            _same_filters(ws, foreign_global, global_=True)
            _same_filters(ws, foreign_local, local=True)
            print("worktree scope wrote worktree filters; local/global spared")
        else:
            _seed_filters(ws, foreign_global, global_=True)
            result = ws.invoke_via_git(["install", "--worktree"])
            print(f"worktree unavailable exit={result.returncode}")
            assert result.returncode != 0, (
                "worktree scope succeeded on Git lacking worktree config"
            )
            _same_filters(ws, foreign_global, global_=True)
            assert caller_visible(result) != caller_visible(ok), (
                "unavailable worktree was not distinguishable from --local success"
            )


def test_install_worktree_outside_repository_fails(isolated_ws):
    """--worktree outside a repository fails and does not rewrite global filters."""
    foreign = foreign_filter_command()
    _seed_filters(isolated_ws, foreign, global_=True)
    result = isolated_ws.invoke_via_git(["install", "--worktree"])
    print(f"worktree outside repo exit={result.returncode}")
    assert result.returncode != 0, (
        "--worktree outside a repository succeeded"
    )
    _same_filters(isolated_ws, foreign, global_=True)
    require_hooks_absent(isolated_ws)


def test_install_system_scope_spares_global():
    """--system writes an isolated system file when Git honors GIT_CONFIG_SYSTEM."""
    foreign = foreign_filter_command()
    with workspace() as ws:
        _seed_filters(ws, foreign, global_=True)
        env_updates, sys_file = isolated_system_scope(ws)
        probe_key = "cbprobe.check"
        probe_val = f"v{token()}"
        probe = ws.git(
            ["config", "--system", probe_key, probe_val],
            env_updates=env_updates,
        )
        sys_text = sys_file.read_text(encoding="utf-8")
        print(
            f"system probe exit={probe.returncode} "
            f"wrote_isolated={probe_val in sys_text}"
        )
        if probe.returncode == 0 and probe_val not in sys_text:
            raise AssertionError(
                "git config --system succeeded without writing "
                "GIT_CONFIG_SYSTEM; refusing to mutate a non-isolated "
                "system file"
            )
        if probe.returncode == 0 and probe_val in sys_text:
            result = ws.invoke_via_git(
                ["install", "--system", "--skip-repo"],
                env_updates=env_updates,
            )
            require_success(result)
            values = require_filters_point_at_git_orbulk(
                ws, system=True, env_updates=env_updates
            )
            _same_filters(ws, foreign, global_=True)
            print(f"system filters={values!r}")
        else:
            result = ws.invoke_via_git(
                ["install", "--system", "--skip-repo"],
                env_updates=env_updates,
            )
            print(f"unwritable system install exit={result.returncode}")
            _same_filters(ws, foreign, global_=True)
            assert result.returncode != 0, (
                "system install succeeded without an isolated system file"
            )


def test_install_combining_scopes_is_invalid():
    """Combining local/system/file/worktree is invalid; a sole --local succeeds."""
    with workspace() as ok_ws:
        ok_ws.init_repo()
        ok = ok_ws.invoke_via_git(["install", "--local"])
        require_success(ok)
        require_filters_point_at_git_orbulk(ok_ws, local=True)
        supports_worktree = git_version_at_least(ok_ws, 2, 20)
    with workspace() as local_system:
        local_system.init_repo()
        dirty = local_system.invoke_via_git(["install", "--local", "--system"])
        print(f"--local --system exit={dirty.returncode}")
        assert dirty.returncode != 0, (
            "combining --local and --system succeeded"
        )
        require_filters_unset(local_system, local=True)
        assert caller_visible(dirty) != caller_visible(ok)
    with workspace() as local_file:
        local_file.init_repo()
        cfg = local_file.path / f"cfg_{token()}"
        dirty = local_file.invoke_via_git(
            ["install", "--local", f"--file={cfg}"]
        )
        print(f"--local --file exit={dirty.returncode}")
        assert dirty.returncode != 0, (
            "combining --local and --file succeeded"
        )
        require_filters_unset(local_file, local=True)
        if cfg.exists():
            require_filters_unset(local_file, file=cfg)
        assert caller_visible(dirty) != caller_visible(ok)
    if supports_worktree:
        with workspace() as system_worktree:
            system_worktree.init_repo()
            _enable_worktree_config(system_worktree)
            dirty = system_worktree.invoke_via_git(
                ["install", "--system", "--worktree"]
            )
            print(f"--system --worktree exit={dirty.returncode}")
            assert dirty.returncode != 0, (
                "combining --system and --worktree succeeded"
            )
            require_filters_unset(system_worktree, worktree=True)
            require_filters_unset(system_worktree, local=True)


def test_install_skip_smudge_differs_from_ordinary():
    """Skip-smudge changes smudge and process relative to an ordinary install."""
    with workspace() as ordinary:
        ordinary.init_repo()
        require_success(
            ordinary.invoke_via_git(["install", "--skip-repo"])
        )
        ordinary_vals = require_filters_point_at_git_orbulk(ordinary, global_=True)
    with workspace() as skipped:
        skipped.init_repo()
        require_success(
            skipped.invoke_via_git(["install", "--skip-smudge", "--skip-repo"])
        )
        skip_vals = require_filters_point_at_git_orbulk(skipped, global_=True)
    print(f"ordinary={ordinary_vals!r}")
    print(f"skip-smudge={skip_vals!r}")
    assert skip_vals["filter.lfs.smudge"] != ordinary_vals["filter.lfs.smudge"], (
        "skip-smudge smudge matched the ordinary (would-download) smudge"
    )
    assert (
        skip_vals["filter.lfs.process"] != ordinary_vals["filter.lfs.process"]
    ), "skip-smudge process matched the ordinary process"


def test_install_skip_repo_writes_filters_not_hooks():
    """Skip-repo writes filters and, unlike the live baseline, installs no hooks."""
    with workspace() as with_hooks:
        with_hooks.init_repo()
        require_success(with_hooks.invoke_via_git(["install"]))
        baseline = _assert_four_hook_types(
            read_git_orbulk_hook_bodies(with_hooks)
        )
        require_filters_point_at_git_orbulk(with_hooks, global_=True)
        print(f"live baseline hook types={list(baseline)}")
    with workspace() as skipped:
        skipped.init_repo()
        result = skipped.invoke_via_git(["install", "--skip-repo"])
        require_success(result)
        values = _assert_filter_keys_written(
            require_filters_point_at_git_orbulk(skipped, global_=True)
        )
        require_hooks_absent(skipped)
        print(f"skip-repo filters={values!r}")
        assert result.returncode == 0, (
            "skip-repo install must succeed"
        )
        for hook_type in HOOK_TYPES:
            _assert_hook_file_absent(skipped, hook_type)


def test_install_local_outside_repository_fails(isolated_ws):
    """--local outside a repository fails and does not write global VCS Orbulk filters."""
    result = isolated_ws.invoke_via_git(["install", "--local"])
    print(f"--local outside repo exit={result.returncode}")
    assert result.returncode != 0, (
        "--local outside a repository succeeded"
    )
    require_filters_unset(isolated_ws, global_=True)
    require_hooks_absent(isolated_ws)


def test_install_nonforce_foreign_hook_fails_unchanged(isolated_ws):
    """Non-force install leaves a foreign hook body untouched and fails."""
    _installed_standard_hooks(isolated_ws)
    body = foreign_hook_body()
    write_hook(isolated_ws, "pre-push", body)
    result = isolated_ws.invoke_via_git(["install"])
    print(f"non-force foreign-hook exit={result.returncode}")
    assert result.returncode != 0, (
        "non-force install succeeded despite a foreign hook body"
    )
    assert read_hook(isolated_ws, "pre-push") == body, (
        "non-force install rewrote the foreign hook body"
    )


def test_install_force_overwrites_foreign_hook(isolated_ws):
    """Force overwrites a foreign hook with the captured current standard body."""
    standard = _installed_standard_hooks(isolated_ws)
    body = foreign_hook_body()
    write_hook(isolated_ws, "post-checkout", body)
    result = isolated_ws.invoke_via_git(["install", "--force"])
    require_success(result)
    require_hook_equals_standard(isolated_ws, "post-checkout", standard)
    replaced = read_hook(isolated_ws, "post-checkout")
    print("force install replaced the foreign post-checkout hook")
    assert result.returncode == 0, (
        "force install must succeed on a foreign hook"
    )
    assert replaced != body, (
        "force install left the foreign post-checkout body unchanged"
    )
    assert replaced == standard["post-checkout"], (
        "force install did not write the captured current standard body"
    )


def test_install_manual_foreign_hook_preserves_and_guides(isolated_ws):
    """Manual mode on a blocking foreign hook preserves the body and guides."""
    _installed_standard_hooks(isolated_ws)
    body = foreign_hook_body()
    write_hook(isolated_ws, "pre-push", body)
    skip_repo = isolated_ws.invoke_via_git(["install", "--skip-repo"])
    require_success(skip_repo)
    unknown = isolated_ws.invoke_via_git(
        ["install", "--skip-repo", f"--zxq-{token()}"]
    )
    nonforce = isolated_ws.invoke_via_git(["install"])
    print(f"non-force foreign-hook exit={nonforce.returncode}")
    assert nonforce.returncode != 0, (
        "live non-force install must fail on the same foreign hook"
    )
    assert read_hook(isolated_ws, "pre-push") == body, (
        "non-force install rewrote the foreign hook body"
    )
    manual = isolated_ws.invoke_via_git(["install", "--manual"])
    print(f"manual exit={manual.returncode} visible={caller_visible(manual)!r}")
    assert read_hook(isolated_ws, "pre-push") == body, (
        "manual install rewrote the foreign hook body"
    )
    strip = [body, *_strip_paths(isolated_ws.path, isolated_ws.home,
                                 hooks_dir(isolated_ws))]
    require_hook_integration_guidance(
        manual, unlike=(nonforce, unknown), strip_tokens=strip
    )
    remainder = require_guidance_remainder_unlike_runs(
        manual, unlike=(skip_repo,), strip_tokens=strip
    )
    guided = require_guidance_remainder_unlike_option_covariates(
        manual, unlike=(nonforce, unknown), strip_tokens=strip
    )
    print(f"guidance remainder={remainder!r} option_stripped={guided!r}")


def test_install_manual_guidance_unlike_skip_repo_and_unknown_option(isolated_ws):
    """Manual conflict remainder differs from same-workspace skip-repo success."""
    _installed_standard_hooks(isolated_ws)
    body = foreign_hook_body()
    write_hook(isolated_ws, "post-commit", body)
    skip_repo = isolated_ws.invoke_via_git(["install", "--skip-repo"])
    require_success(skip_repo)
    unknown = isolated_ws.invoke_via_git(
        ["install", "--skip-repo", f"--zxq-{token()}"]
    )
    assert unknown.returncode != 0
    nonforce = isolated_ws.invoke_via_git(["install"])
    print(f"non-force foreign-hook exit={nonforce.returncode}")
    assert nonforce.returncode != 0, (
        "live non-force install must fail on the same foreign hook"
    )
    assert read_hook(isolated_ws, "post-commit") == body
    manual = isolated_ws.invoke_via_git(["install", "--manual"])
    assert read_hook(isolated_ws, "post-commit") == body
    strip = [
        body,
        *_strip_paths(
            isolated_ws.path, isolated_ws.home, hooks_dir(isolated_ws)
        ),
    ]
    require_hook_integration_guidance(
        manual, unlike=(nonforce, unknown), strip_tokens=strip
    )
    remainder = require_guidance_remainder_unlike_runs(
        manual, unlike=(skip_repo,), strip_tokens=strip
    )
    guided = require_guidance_remainder_unlike_option_covariates(
        manual, unlike=(nonforce, unknown), strip_tokens=strip
    )
    print(f"guidance remainder={remainder!r} option_stripped={guided!r}")


def test_install_manual_guidance_identifies_blocked_hook():
    """Manual conflict preserves each foreign body and unlike non-force on that body."""
    body_a = foreign_hook_body()
    body_b = foreign_hook_body()
    with workspace() as ws_a:
        ws_a.init_repo()
        require_success(ws_a.invoke_via_git(["install"]))
        write_hook(ws_a, "pre-push", body_a)
        nonforce_a = ws_a.invoke_via_git(["install"])
        print(f"non-force pre-push exit={nonforce_a.returncode}")
        assert nonforce_a.returncode != 0, (
            "live non-force install must fail on the foreign pre-push hook"
        )
        assert read_hook(ws_a, "pre-push") == body_a
        unknown_a = ws_a.invoke_via_git(["install", f"--zxq-{token()}"])
        print(f"unknown-option pre-push exit={unknown_a.returncode}")
        assert unknown_a.returncode != 0
        assert read_hook(ws_a, "pre-push") == body_a
        result_a = ws_a.invoke_via_git(["install", "--manual"])
        assert read_hook(ws_a, "pre-push") == body_a
    with workspace() as ws_b:
        ws_b.init_repo()
        require_success(ws_b.invoke_via_git(["install"]))
        write_hook(ws_b, "post-merge", body_b)
        nonforce_b = ws_b.invoke_via_git(["install"])
        print(f"non-force post-merge exit={nonforce_b.returncode}")
        assert nonforce_b.returncode != 0, (
            "live non-force install must fail on the foreign post-merge hook"
        )
        assert read_hook(ws_b, "post-merge") == body_b
        unknown_b = ws_b.invoke_via_git(["install", f"--zxq-{token()}"])
        print(f"unknown-option post-merge exit={unknown_b.returncode}")
        assert unknown_b.returncode != 0
        assert read_hook(ws_b, "post-merge") == body_b
        result_b = ws_b.invoke_via_git(["install", "--manual"])
        assert read_hook(ws_b, "post-merge") == body_b
    strip = [
        body_a,
        body_b,
        *_strip_paths(
            ws_a.path, ws_a.home, hooks_dir(ws_a),
            ws_b.path, ws_b.home, hooks_dir(ws_b),
        ),
    ]
    strip_a = [
        body_a,
        *_strip_paths(ws_a.path, ws_a.home, hooks_dir(ws_a)),
    ]
    strip_b = [
        body_b,
        *_strip_paths(ws_b.path, ws_b.home, hooks_dir(ws_b)),
    ]
    require_hook_integration_guidance(
        result_a, unlike=(nonforce_a, unknown_a), strip_tokens=strip
    )
    require_hook_integration_guidance(
        result_b, unlike=(nonforce_b, unknown_b), strip_tokens=strip
    )
    guided_a = require_guidance_remainder_unlike_option_covariates(
        result_a, unlike=(nonforce_a, unknown_a), strip_tokens=strip_a
    )
    guided_b = require_guidance_remainder_unlike_option_covariates(
        result_b, unlike=(nonforce_b, unknown_b), strip_tokens=strip_b
    )
    print(
        "blocked-hook remainders after stripping "
        f"len_a={len(caller_visible(result_a))} "
        f"len_b={len(caller_visible(result_b))} "
        f"option_stripped_a={guided_a!r} option_stripped_b={guided_b!r}"
    )


# ---------------------------------------------------------------------------
# D. Uninstall
# ---------------------------------------------------------------------------


def test_uninstall_removes_global_filters(isolated_ws):
    """Global uninstall unsets the three lfs filter keys in global scope."""
    require_success(isolated_ws.invoke_via_git(["install", "--skip-repo"]))
    require_filters_point_at_git_orbulk(isolated_ws, global_=True)
    result = isolated_ws.invoke_via_git(["uninstall", "--skip-repo"])
    require_success(result)
    require_filters_unset(isolated_ws, global_=True)
    print("global uninstall unset clean/smudge/process")
    assert result.returncode == 0, (
        "global uninstall must succeed"
    )
    for key in FILTER_KEYS:
        assert lookup_git_config(isolated_ws, key, global_=True) is None, (
            f"uninstall left {key} set in global scope"
        )


def test_uninstall_in_repo_removes_four_hooks(isolated_ws):
    """In-repo uninstall removes the four VCS Orbulk hook files."""
    _installed_standard_hooks(isolated_ws)
    result = isolated_ws.invoke_via_git(["uninstall"])
    require_success(result)
    require_filters_unset(isolated_ws, global_=True)
    require_hooks_absent(isolated_ws)
    print("uninstall removed filters and the four hook files")
    assert result.returncode == 0, (
        "in-repo uninstall must succeed"
    )
    for key in FILTER_KEYS:
        assert lookup_git_config(isolated_ws, key, global_=True) is None, (
            f"uninstall left {key} set in global scope"
        )
    for hook_type in HOOK_TYPES:
        _assert_hook_file_absent(isolated_ws, hook_type)


def test_uninstall_skip_repo_leaves_hooks():
    """Skip-repo uninstall reverses filters and, unlike full uninstall, leaves hooks."""
    with workspace() as full:
        full.init_repo()
        require_success(full.invoke_via_git(["install"]))
        require_success(full.invoke_via_git(["uninstall"]))
        require_hooks_absent(full)
        require_filters_unset(full, global_=True)
        for hook_type in HOOK_TYPES:
            _assert_hook_file_absent(full, hook_type)
    with workspace() as skipped:
        skipped.init_repo()
        require_success(skipped.invoke_via_git(["install"]))
        before = _assert_four_hook_types(read_git_orbulk_hook_bodies(skipped))
        result = skipped.invoke_via_git(["uninstall", "--skip-repo"])
        require_success(result)
        require_filters_unset(skipped, global_=True)
        for hook_type in HOOK_TYPES:
            require_hook_equals_standard(skipped, hook_type, before)
        after = {hook_type: read_hook(skipped, hook_type) for hook_type in HOOK_TYPES}
        print("skip-repo uninstall left the four VCS Orbulk hooks in place")
        assert result.returncode == 0, (
            "skip-repo uninstall must succeed"
        )
        assert after == before, (
            "skip-repo uninstall changed VCS Orbulk hook bodies"
        )


def test_uninstall_outside_repo_reverses_global_filters_only(isolated_ws):
    """Outside a repository, uninstall still reverses claimed global filters."""
    require_success(isolated_ws.invoke_via_git(["install", "--skip-repo"]))
    require_filters_point_at_git_orbulk(isolated_ws, global_=True)
    result = isolated_ws.invoke_via_git(["uninstall"])
    require_success(result)
    require_filters_unset(isolated_ws, global_=True)
    assert not (isolated_ws.path / ".git" / "hooks").exists(), (
        "uninstall outside a repository created a hooks directory"
    )
    require_hooks_absent(isolated_ws)


def test_uninstall_local_scope_spares_global(isolated_ws):
    """Local uninstall unsets local filters and leaves seeded global VCS Orbulk values."""
    isolated_ws.init_repo()
    require_success(
        isolated_ws.invoke_via_git(["install", "--skip-repo"])
    )
    global_vals = require_filters_point_at_git_orbulk(isolated_ws, global_=True)
    require_success(
        isolated_ws.invoke_via_git(["install", "--local", "--skip-repo"])
    )
    require_filters_point_at_git_orbulk(isolated_ws, local=True)
    result = isolated_ws.invoke_via_git(
        ["uninstall", "--local", "--skip-repo"]
    )
    require_success(result)
    require_filters_unset(isolated_ws, local=True)
    for key, value in global_vals.items():
        observed = lookup_git_config(isolated_ws, key, global_=True)
        assert observed == value, (
            f"local uninstall changed global {key}: {observed!r}"
        )
    print("local uninstall spared global VCS Orbulk filter values")


def test_uninstall_file_scope(isolated_ws):
    """--file uninstall clears filters only in that file."""
    foreign = foreign_filter_command()
    _seed_filters(isolated_ws, foreign, global_=True)
    cfg = isolated_ws.path / f"cfg_{token()}"
    require_success(
        isolated_ws.invoke_via_git(
            ["install", f"--file={cfg}", "--skip-repo"]
        )
    )
    require_filters_point_at_git_orbulk(isolated_ws, file=cfg)
    result = isolated_ws.invoke_via_git(
        ["uninstall", f"--file={cfg}", "--skip-repo"]
    )
    require_success(result)
    require_filters_unset(isolated_ws, file=cfg)
    _same_filters(isolated_ws, foreign, global_=True)
    print(f"file uninstall cleared {cfg}")


def test_uninstall_honors_shared_hooks_path(isolated_ws):
    """Uninstall removes VCS Orbulk hooks from core.hooksPath when that path is used."""
    isolated_ws.init_repo()
    rel = f"hk_{token()}"
    require_git_config_set(
        isolated_ws, "core.hooksPath", rel, local=True
    )
    require_success(isolated_ws.invoke_via_git(["install"]))
    if git_version_at_least(isolated_ws, 2, 9):
        _assert_four_hook_types(
            read_git_orbulk_hook_bodies(isolated_ws, hooks_relpath=rel)
        )
        result = isolated_ws.invoke_via_git(["uninstall"])
        require_success(result)
        require_hooks_absent(isolated_ws, hooks_relpath=rel)
        require_hooks_absent(isolated_ws)
        print(f"uninstall removed hooks from {rel}")
        assert result.returncode == 0, (
            "uninstall with core.hooksPath set must succeed"
        )
        for hook_type in HOOK_TYPES:
            _assert_hook_file_absent(
                isolated_ws, hook_type, hooks_relpath=rel
            )
            _assert_hook_file_absent(isolated_ws, hook_type)
    else:
        _assert_four_hook_types(read_git_orbulk_hook_bodies(isolated_ws))
        result = isolated_ws.invoke_via_git(["uninstall"])
        require_success(result)
        require_hooks_absent(isolated_ws)
        print("Git < 2.9.0: uninstalled default .git/hooks")
        assert result.returncode == 0, (
            "uninstall must succeed on the default hooks directory"
        )
        for hook_type in HOOK_TYPES:
            _assert_hook_file_absent(isolated_ws, hook_type)


# ---------------------------------------------------------------------------
# E. Update
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hook_type", HOOK_TYPES)
def test_update_reinstalls_missing_hooks(isolated_ws, hook_type):
    """Non-force update installs a missing hook as the captured current standard."""
    standard = _installed_standard_hooks(isolated_ws)
    _remove_hook(isolated_ws, hook_type)
    require_hook_absent(isolated_ws, hook_type)
    remaining = {
        other: read_hook(isolated_ws, other)
        for other in HOOK_TYPES
        if other != hook_type
    }
    result = isolated_ws.invoke_via_git(["update"])
    require_success(result)
    restored = require_hook_equals_standard(isolated_ws, hook_type, standard)
    assert restored, f"missing {hook_type} was not reinstalled"
    for other, before in remaining.items():
        after = read_hook(isolated_ws, other)
        assert after == before, (
            f"update of missing {hook_type} changed already-present {other}"
        )
        require_hook_equals_standard(isolated_ws, other, standard)
    print(f"update restored missing {hook_type}")


@pytest.mark.parametrize("hook_type", HOOK_TYPES)
def test_update_replaces_empty_hook_with_current_standard(isolated_ws, hook_type):
    """Non-force update replaces an empty hook file with the current standard body."""
    standard = _installed_standard_hooks(isolated_ws)
    write_hook(isolated_ws, hook_type, "")
    assert read_hook(isolated_ws, hook_type) == ""
    remaining = {
        other: read_hook(isolated_ws, other)
        for other in HOOK_TYPES
        if other != hook_type
    }
    result = isolated_ws.invoke_via_git(["update"])
    require_success(result)
    body = require_hook_equals_standard(isolated_ws, hook_type, standard)
    assert body, f"{hook_type} was still empty after update"
    for other, before in remaining.items():
        after = read_hook(isolated_ws, other)
        assert after == before, (
            f"empty-{hook_type} replacement changed already-current {other}"
        )
        require_hook_equals_standard(isolated_ws, other, standard)
    print(f"update replaced empty {hook_type}")


def test_update_leaves_current_standard_unchanged(isolated_ws):
    """Non-force update leaves an already-current standard body byte-identical."""
    standard = _installed_standard_hooks(isolated_ws)
    before = {hook: read_hook(isolated_ws, hook) for hook in HOOK_TYPES}
    result = isolated_ws.invoke_via_git(["update"])
    require_success(result)
    for hook_type in HOOK_TYPES:
        after = read_hook(isolated_ws, hook_type)
        assert after == before[hook_type], (
            f"{hook_type} changed on a no-op current-standard update"
        )
        assert after == standard[hook_type]
    print("update left current-standard hook bodies unchanged")


def test_update_nonforce_foreign_hook_fails_unchanged(isolated_ws):
    """Non-force update leaves a foreign hook untouched and fails."""
    _installed_standard_hooks(isolated_ws)
    body = foreign_hook_body()
    write_hook(isolated_ws, "pre-push", body)
    result = isolated_ws.invoke_via_git(["update"])
    print(f"non-force update foreign-hook exit={result.returncode}")
    assert result.returncode != 0, (
        "non-force update succeeded despite a foreign hook body"
    )
    assert read_hook(isolated_ws, "pre-push") == body, (
        "non-force update rewrote the foreign hook body"
    )


def test_update_force_overwrites_foreign_hook(isolated_ws):
    """Force update overwrites a foreign hook with the captured current standard."""
    standard = _installed_standard_hooks(isolated_ws)
    body = foreign_hook_body()
    write_hook(isolated_ws, "post-merge", body)
    result = isolated_ws.invoke_via_git(["update", "--force"])
    require_success(result)
    require_hook_equals_standard(isolated_ws, "post-merge", standard)
    replaced = read_hook(isolated_ws, "post-merge")
    print("force update replaced the foreign post-merge hook")
    assert result.returncode == 0, (
        "force update must succeed on a foreign hook"
    )
    assert replaced != body, (
        "force update left the foreign post-merge body unchanged"
    )
    assert replaced == standard["post-merge"], (
        "force update did not write the captured current standard body"
    )


def test_update_manual_foreign_hook_preserves_and_guides(isolated_ws):
    """Manual update on a foreign hook preserves the body and emits guidance."""
    _installed_standard_hooks(isolated_ws)
    no_conflict = isolated_ws.invoke_via_git(["update"])
    require_success(no_conflict)
    print(
        "no-conflict already-current update "
        f"visible={caller_visible(no_conflict)!r}"
    )
    body = foreign_hook_body()
    write_hook(isolated_ws, "post-checkout", body)
    skip_repo = isolated_ws.invoke_via_git(["install", "--skip-repo"])
    require_success(skip_repo)
    unknown = isolated_ws.invoke_via_git(["update", f"--zxq-{token()}"])
    nonforce = isolated_ws.invoke_via_git(["update"])
    print(f"non-force update foreign-hook exit={nonforce.returncode}")
    assert nonforce.returncode != 0, (
        "live non-force update must fail on the same foreign hook"
    )
    assert read_hook(isolated_ws, "post-checkout") == body, (
        "non-force update rewrote the foreign hook body"
    )
    manual = isolated_ws.invoke_via_git(["update", "--manual"])
    print(f"update --manual exit={manual.returncode}")
    assert read_hook(isolated_ws, "post-checkout") == body, (
        "manual update rewrote the foreign hook body"
    )
    strip = [body, *_strip_paths(isolated_ws.path, isolated_ws.home,
                                 hooks_dir(isolated_ws))]
    require_hook_integration_guidance(
        manual, unlike=(nonforce, unknown), strip_tokens=strip
    )
    remainder = require_guidance_remainder_unlike_runs(
        manual, unlike=(no_conflict, skip_repo), strip_tokens=strip
    )
    guided = require_guidance_remainder_unlike_option_covariates(
        manual, unlike=(nonforce, unknown), strip_tokens=strip
    )
    print(f"guidance remainder={remainder!r} option_stripped={guided!r}")


def test_update_outside_repository_fails_without_modifying(isolated_ws):
    """Update outside a repository fails and does not modify filters or hooks."""
    foreign = foreign_filter_command()
    _seed_filters(isolated_ws, foreign, global_=True)
    result = isolated_ws.invoke_via_git(["update"])
    print(f"update outside repo exit={result.returncode}")
    assert result.returncode != 0, (
        "update outside a repository succeeded"
    )
    _same_filters(isolated_ws, foreign, global_=True)
    assert not (isolated_ws.path / ".git" / "hooks").exists(), (
        "update outside a repository created a hooks directory"
    )
    require_hooks_absent(isolated_ws)


def test_update_does_not_write_filters():
    """Install writes global filters; in-repo update installs missing hooks.

    Live baseline: filter installation belongs to install. Update in a
    repository still installs the four VCS Orbulk hooks when they are
    missing. An in-repository update is not forbidden from also writing
    filter.lfs.* keys.
    """
    with workspace() as baseline:
        baseline.init_repo()
        require_success(baseline.invoke_via_git(["install"]))
        written = require_filters_point_at_git_orbulk(baseline, global_=True)
        print(f"live baseline: install wrote global filters={written!r}")

    with workspace() as missing:
        missing.init_repo()
        require_hooks_absent(missing)
        result = missing.invoke_via_git(["update"])
        require_success(result)
        bodies = _assert_four_hook_types(read_git_orbulk_hook_bodies(missing))
        print(f"update installed missing hooks={list(bodies)}")
        assert result.returncode == 0, (
            "in-repository update must succeed when hooks are missing"
        )
        for hook_type, body in bodies.items():
            assert body, f"update left {hook_type} empty"


# ---------------------------------------------------------------------------
# F. Undefined option and negative control
# ---------------------------------------------------------------------------


def test_install_undefined_option_fails_unlike_clean(isolated_ws):
    """An undefined option after install fails unlike a clean skip-repo install."""
    clean = isolated_ws.invoke_via_git(["install", "--skip-repo"])
    dirty = isolated_ws.invoke_via_git(
        ["install", "--skip-repo", f"--zxq-{token()}"]
    )
    print(f"clean exit={clean.returncode} dirty exit={dirty.returncode}")
    require_rejected_unlike_clean(clean, dirty)
    values = _assert_filter_keys_written(
        require_filters_point_at_git_orbulk(isolated_ws, global_=True)
    )
    print(f"clean-install filters={values!r}")
    assert clean.returncode == 0, (
        "live baseline skip-repo install must succeed"
    )
    assert dirty.returncode != 0, (
        "undefined option after install must fail"
    )
    assert dirty.stderr_text.strip(), (
        "undefined option must report a clear error on standard error"
    )


def test_git_orbulk_install_fails_when_binary_absent_from_path(
    isolated_ws, product_binary
):
    """Negative control: git orbulk install fails when the binary is not on PATH."""
    present = isolated_ws.invoke_via_git(["install", "--skip-repo"])
    require_success(present)
    require_filters_point_at_git_orbulk(isolated_ws, global_=True)
    hidden_path = path_without_product_bin(isolated_ws.env)
    print(f"product_binary={product_binary} hidden_path={hidden_path!r}")
    result = isolated_ws.invoke_via_git(
        ["install", "--skip-repo"],
        env_updates={"PATH": hidden_path},
    )
    print(f"absent-binary install exit={result.returncode}")
    assert result.returncode != 0, (
        "git orbulk install succeeded after the product binary was removed from PATH"
    )
    assert (result.returncode, result.stdout, result.stderr) != (
        present.returncode,
        present.stdout,
        present.stderr,
    ), "absent-binary install was not distinguishable from install with the binary"
