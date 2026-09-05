# feature: F01
"""CLI entry, help, version, and environment-report acceptance tests.

PRD: FP-01 (command-line entry, help, version, env report). Assertions stay
at the PRD's precision: success vs non-zero, distinguishable streams,
dedicated per-remote server indications, and version-identity agreement
with env related facts. Output wording, labels, and layout are not pinned.
"""

from __future__ import annotations

from _harness import token, workspace
from _helpers import (
    add_git_remote,
    build_identity_token,
    check_env_effective_configuration,
    dedicated_server_url,
    env_report,
    indication_names,
    install_two_remote_layout,
    make_two_remote_layout,
    path_without_product_bin,
    related_facts_without_dedicated,
    require_git_config_set,
    require_identity_agrees_with_env_related_facts,
    require_invocation_guidance_usage,
    require_rejected_unlike_clean,
    require_success,
    require_version_path_identity_token,
    runtime_http_url,
)


def _origin_dedicated(report: str, origin_url: str, sibling_name: str) -> str:
    return dedicated_server_url(
        report,
        remote_name="origin",
        git_remote_url=origin_url,
        other_remote_name=sibling_name,
    )


def _sibling_dedicated(report: str, sibling_name: str, sibling_url: str) -> str:
    return dedicated_server_url(
        report,
        remote_name=sibling_name,
        git_remote_url=sibling_url,
        other_remote_name="origin",
    )


def _dedicated_pair(report: str, layout) -> tuple[str, str]:
    origin = _origin_dedicated(
        report, layout.origin_url, layout.sibling_name
    )
    sibling = _sibling_dedicated(
        report, layout.sibling_name, layout.sibling_url
    )
    return origin, sibling


def _distinct_from_git_remote(observed: str, git_remote_url: str) -> None:
    """Dedicated indication must not be a Git-remote listing related fact."""
    assert observed.rstrip("/") != git_remote_url.rstrip("/"), (
        "dedicated indication of the VCS Orbulk server URL that would be used "
        "must be distinct from a Git-remote listing"
    )


def _require_identity_agreement(
    version_result,
    report: str,
    layout,
    origin: str,
    sibling: str,
    extra_unrelated=(),
) -> str:
    """Version-path token must agree with stripped env related-fact token."""
    _distinct_from_git_remote(origin, layout.origin_url)
    _distinct_from_git_remote(sibling, layout.sibling_url)
    path_token = require_version_path_identity_token(version_result)
    agreed = require_identity_agrees_with_env_related_facts(
        version_result,
        report,
        dedicated_urls=(origin, sibling),
        git_remote_urls=(layout.origin_url, layout.sibling_url),
        extra_unrelated=extra_unrelated,
    )
    assert path_token == agreed, (
        "version-path identity token must be the token that agreed with "
        "env related facts"
    )
    return agreed


def test_version_via_git_extension(isolated_ws):
    """``git orbulk version`` reports this build's identity and agrees with env."""
    layout = make_two_remote_layout()
    install_two_remote_layout(isolated_ws, layout)
    marker = f"flt_{token(8)}"
    require_git_config_set(isolated_ws, "filter.lfs.clean", marker, local=True)
    result = isolated_ws.invoke_via_git(["version"])
    report = env_report(isolated_ws)
    origin, sibling = _dedicated_pair(report, layout)
    print(f"version via git stdout={result.stdout_text!r}")
    print(f"origin dedicated={origin!r} sibling dedicated={sibling!r}")
    identity = require_version_path_identity_token(result)
    agreed = _require_identity_agreement(
        result, report, layout, origin, sibling, extra_unrelated=(marker,)
    )
    assert result.returncode == 0, (
        "git orbulk version must exit successfully"
    )
    assert identity == agreed, (
        "version-path identity token must be the token that agreed with "
        "env related facts"
    )


def test_version_via_direct_binary(isolated_ws):
    """Direct binary ``version`` reports this build's identity and agrees with env."""
    layout = make_two_remote_layout()
    install_two_remote_layout(isolated_ws, layout)
    result = isolated_ws.invoke(["version"])
    report = env_report(isolated_ws)
    origin, sibling = _dedicated_pair(report, layout)
    print(f"version via binary stdout={result.stdout_text!r}")
    identity = require_version_path_identity_token(result)
    agreed = _require_identity_agreement(
        result, report, layout, origin, sibling
    )
    assert result.returncode == 0, (
        "direct binary version must exit successfully"
    )
    assert result.stdout_text.strip(), (
        "direct binary version must report that this build is VCS Orbulk and "
        "include version identity suitable for support and diagnostics"
    )
    assert identity in result.stdout_text, (
        "version identity must be observed on the version path's own stdout"
    )
    assert identity == agreed, (
        "direct-binary identity token must agree with env related facts"
    )


def test_version_stable_across_repos_while_env_varies():
    """Version identity is of the build; env indications follow remotes."""
    layout_a = make_two_remote_layout()
    layout_b = make_two_remote_layout()
    marker_a = f"flt_{token(8)}"
    marker_b = f"flt_{token(8)}"
    with workspace() as repo_a:
        install_two_remote_layout(repo_a, layout_a)
        require_git_config_set(repo_a, "filter.lfs.clean", marker_a, local=True)
        version_a = repo_a.invoke_via_git(["version"])
        report_a = env_report(repo_a)
        origin_a, sibling_a = _dedicated_pair(report_a, layout_a)
        identity_a = _require_identity_agreement(
            version_a,
            report_a,
            layout_a,
            origin_a,
            sibling_a,
            extra_unrelated=(marker_a,),
        )
    with workspace() as repo_b:
        install_two_remote_layout(repo_b, layout_b)
        require_git_config_set(repo_b, "filter.lfs.clean", marker_b, local=True)
        version_b = repo_b.invoke_via_git(["version"])
        report_b = env_report(repo_b)
        origin_b, sibling_b = _dedicated_pair(report_b, layout_b)
        identity_b = _require_identity_agreement(
            version_b,
            report_b,
            layout_b,
            origin_b,
            sibling_b,
            extra_unrelated=(marker_b,),
        )
    print(f"version_a={version_a.stdout_text!r}")
    print(f"version_b={version_b.stdout_text!r}")
    print(f"identity_a={identity_a!r} identity_b={identity_b!r}")
    print(f"origin_a={origin_a!r} origin_b={origin_b!r}")
    assert identity_a == identity_b, (
        "version identity changed across repositories; it is a build fact"
    )
    assert origin_a != origin_b, (
        "environment report did not vary with distinct remotes"
    )
    assert sibling_a != sibling_b, (
        "sibling dedicated indications did not vary with distinct remotes"
    )


def test_version_identity_agrees_across_entry_paths(isolated_ws):
    """Git-extension and direct binary report the same build identity."""
    layout = make_two_remote_layout()
    install_two_remote_layout(isolated_ws, layout)
    marker = f"flt_{token(8)}"
    require_git_config_set(isolated_ws, "filter.lfs.clean", marker, local=True)
    via_git = isolated_ws.invoke_via_git(["version"])
    via_bin = isolated_ws.invoke(["version"])
    report = env_report(isolated_ws)
    origin, sibling = _dedicated_pair(report, layout)
    print(f"via_git={via_git.stdout_text!r}")
    print(f"via_bin={via_bin.stdout_text!r}")
    identity_git = _require_identity_agreement(
        via_git, report, layout, origin, sibling, extra_unrelated=(marker,)
    )
    identity_bin = _require_identity_agreement(
        via_bin, report, layout, origin, sibling, extra_unrelated=(marker,)
    )
    assert identity_git == identity_bin, (
        "git-extension and direct binary reported different identities "
        "for the same build"
    )


def test_no_subcommand_usage_success(isolated_ws):
    """No subcommand yields usage and exits successfully (not an unknown command)."""
    via_git = isolated_ws.invoke_via_git([])
    direct = isolated_ws.invoke([])
    version_git = isolated_ws.invoke_via_git(["version"])
    version_bin = isolated_ws.invoke(["version"])
    print(f"bare git stdout={via_git.stdout_text!r}")
    print(f"bare binary stdout={direct.stdout_text!r}")
    require_success(version_git)
    require_success(version_bin)
    require_invocation_guidance_usage(via_git)
    require_invocation_guidance_usage(direct)
    assert via_git.stdout != version_git.stdout, (
        "no-subcommand git-extension output was only the version identity "
        "presentation, not user-facing usage information"
    )
    assert direct.stdout != version_bin.stdout, (
        "no-subcommand direct-binary output was only the version identity "
        "presentation, not user-facing usage information"
    )
    unknown = isolated_ws.invoke_via_git([f"zxq-{token()}"])
    assert unknown.returncode != 0, (
        "unknown subcommand succeeded; bare invocation must be distinct"
    )
    assert (via_git.returncode, via_git.stdout, via_git.stderr) != (
        unknown.returncode,
        unknown.stdout,
        unknown.stderr,
    ), "bare invocation was not distinguishable from an unknown subcommand"


def test_suite_help_success(isolated_ws):
    """Suite help via git-extension and direct binary exits successfully."""
    probes = [
        isolated_ws.invoke_via_git(["help"]),
        isolated_ws.invoke(["help"]),
    ]
    checked = 0
    for result in probes:
        print(f"suite help argv={list(result.argv)!r} exit={result.returncode}")
        require_invocation_guidance_usage(result)
        assert result.returncode == 0, (
            "suite help must exit successfully when help was requested"
        )
        assert result.stdout_text.strip(), (
            "suite help must yield user-facing usage information"
        )
        checked += 1
    assert checked == len(probes), "not every suite-help entry was checked"


def test_env_porcelain_help_success(isolated_ws):
    """Per-command help for porcelain ``env`` exits successfully with usage."""
    probes = [
        isolated_ws.invoke_via_git(["help", "env"]),
        isolated_ws.invoke(["help", "env"]),
    ]
    for result in probes:
        print(f"env help argv={list(result.argv)!r} exit={result.returncode}")
        require_invocation_guidance_usage(result, topic="env")
    unknown = isolated_ws.invoke_via_git(["env", f"--zxq-{token()}"])
    help_env = probes[0]
    assert unknown.returncode != 0, (
        "undefined option after env succeeded; intentional help must differ"
    )
    assert (help_env.returncode, help_env.stdout, help_env.stderr) != (
        unknown.returncode,
        unknown.stdout,
        unknown.stderr,
    ), "intentional env help was not distinguishable from an undefined option after env"


def test_suite_help_differs_from_env_help(isolated_ws):
    """Suite help and env help are not the same dump."""
    suite = require_success(isolated_ws.invoke_via_git(["help"]))
    env_help = require_success(isolated_ws.invoke_via_git(["help", "env"]))
    print(f"suite help len={len(suite.stdout)} env help len={len(env_help.stdout)}")
    assert suite.stdout != env_help.stdout, (
        "suite help and env help were identical; per-command help is missing"
    )


def test_help_differs_from_version(isolated_ws):
    """Help output is not the version identity banner."""
    help_result = require_success(isolated_ws.invoke_via_git(["help"]))
    version = require_success(isolated_ws.invoke_via_git(["version"]))
    print(f"help={help_result.stdout_text!r}")
    print(f"version={version.stdout_text!r}")
    assert help_result.stdout != version.stdout, (
        "help and version produced identical output"
    )


def test_env_before_any_transfer_names_server_per_remote():
    """Env remains usable before any object transfer; both entry paths succeed."""
    layout = make_two_remote_layout()
    with workspace() as ws:
        install_two_remote_layout(ws, layout)
        via_git = require_success(ws.invoke_via_git(["env"]))
        direct = require_success(ws.invoke(["env"]))
        print(f"env via git:\n{via_git.stdout_text}")
        print(f"env via binary:\n{direct.stdout_text}")
        origin = _origin_dedicated(
            via_git.stdout_text, layout.origin_url, layout.sibling_name
        )
        sibling = _sibling_dedicated(
            via_git.stdout_text, layout.sibling_name, layout.sibling_url
        )
        origin_direct = _origin_dedicated(
            direct.stdout_text, layout.origin_url, layout.sibling_name
        )
        sibling_direct = _sibling_dedicated(
            direct.stdout_text, layout.sibling_name, layout.sibling_url
        )
    print(f"origin={origin!r} sibling={sibling!r}")
    assert origin, "default remote has no dedicated server indication"
    assert sibling, "named remote has no dedicated server indication"
    _distinct_from_git_remote(origin, layout.origin_url)
    _distinct_from_git_remote(sibling, layout.sibling_url)
    assert origin_direct == origin, (
        "direct binary env named a different origin server than git orbulk env"
    )
    assert sibling_direct == sibling, (
        "direct binary env named a different sibling server than git orbulk env"
    )


def test_env_two_remotes_dedicated_indications_distinct():
    """Each remote's dedicated indication names a different would-use server."""
    layout = make_two_remote_layout()
    with workspace() as ws:
        install_two_remote_layout(ws, layout)
        report = env_report(ws)
        origin = _origin_dedicated(report, layout.origin_url, layout.sibling_name)
        sibling = _sibling_dedicated(
            report, layout.sibling_name, layout.sibling_url
        )
    print(f"origin dedicated={origin!r}")
    print(f"sibling dedicated={sibling!r}")
    _distinct_from_git_remote(origin, layout.origin_url)
    _distinct_from_git_remote(sibling, layout.sibling_url)
    assert origin != sibling, (
        "two remotes with distinct Git URLs shared one dedicated indication"
    )


def test_env_repo_lfs_url_override_on_dedicated_indication():
    """A repository LFS URL override replaces the derived URL on both remotes."""
    layout = make_two_remote_layout()
    override = runtime_http_url("ovr")
    with workspace() as baseline:
        install_two_remote_layout(baseline, layout)
        base_report = env_report(baseline)
        base_origin, base_sibling = _dedicated_pair(base_report, layout)
    with workspace() as overridden:
        install_two_remote_layout(overridden, layout)
        require_git_config_set(overridden, "lfs.url", override, local=True)
        report = env_report(overridden)
        origin, sibling = _dedicated_pair(report, layout)
    print(f"base origin={base_origin!r} override origin={origin!r}")
    print(f"base sibling={base_sibling!r} override sibling={sibling!r}")
    print(f"override url={override!r}")
    _distinct_from_git_remote(base_origin, layout.origin_url)
    _distinct_from_git_remote(base_sibling, layout.sibling_url)
    assert indication_names(origin, override), (
        "origin dedicated indication did not name the repository LFS URL override"
    )
    assert indication_names(sibling, override), (
        "sibling dedicated indication did not name the repository LFS URL override"
    )
    assert origin != base_origin, (
        "origin dedicated indication still named the derived URL after override"
    )
    assert sibling != base_sibling, (
        "sibling dedicated indication still named the derived URL after override"
    )


def test_env_global_lfs_url_override_on_dedicated_indication():
    """A global LFS URL override replaces the derived URL on dedicated indications."""
    layout = make_two_remote_layout()
    override = runtime_http_url("govr")
    with workspace() as baseline:
        install_two_remote_layout(baseline, layout)
        base_report = env_report(baseline)
        base_origin, base_sibling = _dedicated_pair(base_report, layout)
    with workspace() as overridden:
        install_two_remote_layout(overridden, layout)
        require_git_config_set(overridden, "lfs.url", override, global_=True)
        report = env_report(overridden)
        origin, sibling = _dedicated_pair(report, layout)
    print(f"global override={override!r} origin={origin!r} sibling={sibling!r}")
    _distinct_from_git_remote(base_origin, layout.origin_url)
    _distinct_from_git_remote(base_sibling, layout.sibling_url)
    assert indication_names(origin, override), (
        "origin dedicated indication did not name the global LFS URL override"
    )
    assert indication_names(sibling, override), (
        "sibling dedicated indication did not name the global LFS URL override"
    )
    assert origin != base_origin
    assert sibling != base_sibling


def test_env_related_facts_echo_is_not_replacement():
    """Override must appear on the dedicated indication, not merely in stdout."""
    layout = make_two_remote_layout()
    override = runtime_http_url("echo")
    with workspace() as baseline:
        install_two_remote_layout(baseline, layout)
        base_report = env_report(baseline)
        base_origin, base_sibling = _dedicated_pair(base_report, layout)
    with workspace() as overridden:
        install_two_remote_layout(overridden, layout)
        require_git_config_set(overridden, "lfs.url", override, local=True)
        report = env_report(overridden)
        origin = dedicated_server_url(
            report,
            remote_name="origin",
            git_remote_url=layout.origin_url,
            other_remote_name=layout.sibling_name,
        )
        sibling = dedicated_server_url(
            report,
            remote_name=layout.sibling_name,
            git_remote_url=layout.sibling_url,
            other_remote_name="origin",
        )
    print(f"stdout contains override={override in report}")
    print(f"origin dedicated={origin!r} sibling dedicated={sibling!r}")
    _distinct_from_git_remote(base_origin, layout.origin_url)
    _distinct_from_git_remote(base_sibling, layout.sibling_url)
    assert indication_names(origin, override), (
        "related-facts echo of the override does not count; origin dedicated "
        "indication must name the override"
    )
    assert indication_names(sibling, override), (
        "related-facts echo of the override does not count; sibling dedicated "
        "indication must name the override"
    )
    assert origin != base_origin, (
        "origin dedicated indication still named the derived URL while the "
        "override may have been echoed among related facts"
    )
    assert sibling != base_sibling, (
        "sibling dedicated indication still named the derived URL while the "
        "override may have been echoed among related facts"
    )


def test_env_per_remote_override_spares_sibling():
    """A per-remote LFS URL override is observed only on that remote."""
    layout = make_two_remote_layout()
    sib_override = runtime_http_url("psib")
    origin_override = runtime_http_url("porig")
    with workspace() as baseline:
        install_two_remote_layout(baseline, layout)
        base_report = env_report(baseline)
        base_origin, base_sibling = _dedicated_pair(base_report, layout)
    with workspace() as sib_only:
        install_two_remote_layout(sib_only, layout)
        require_git_config_set(
            sib_only,
            f"remote.{layout.sibling_name}.lfsurl",
            sib_override,
            local=True,
        )
        report = env_report(sib_only)
        origin, sibling = _dedicated_pair(report, layout)
    print(f"sib override origin={origin!r} sibling={sibling!r}")
    _distinct_from_git_remote(base_origin, layout.origin_url)
    _distinct_from_git_remote(base_sibling, layout.sibling_url)
    assert indication_names(sibling, sib_override), (
        "named remote dedicated indication did not name its per-remote override"
    )
    assert origin == base_origin, (
        "origin dedicated indication changed after a sibling-only override"
    )
    assert not indication_names(origin, sib_override), (
        "sibling per-remote override leaked onto origin's dedicated indication"
    )
    with workspace() as origin_only:
        install_two_remote_layout(origin_only, layout)
        require_git_config_set(
            origin_only,
            "remote.origin.lfsurl",
            origin_override,
            local=True,
        )
        report = env_report(origin_only)
        origin, sibling = _dedicated_pair(report, layout)
    print(f"origin override origin={origin!r} sibling={sibling!r}")
    assert indication_names(origin, origin_override), (
        "origin dedicated indication did not name its per-remote override"
    )
    assert sibling == base_sibling, (
        "sibling dedicated indication changed after an origin-only override"
    )
    assert not indication_names(sibling, origin_override), (
        "origin per-remote override leaked onto the sibling's dedicated indication"
    )


def test_env_filter_summary_tracks_effective_git_config():
    """Filter configuration summary reflects the effective Git config value."""
    marker = f"flt_{token(8)}"
    with workspace() as configured:
        configured.init_repo()
        require_git_config_set(
            configured, "filter.lfs.clean", marker, local=True
        )
        report = env_report(configured)
        print(f"configured env contains marker={marker in report}")
        assert marker in report, (
            "environment report omitted the effective filter.lfs.clean value"
        )
    with workspace() as plain:
        plain.init_repo()
        report = env_report(plain)
        print(f"plain env contains marker={marker in report}")
        assert marker not in report, (
            "environment report mentioned a filter value that was never configured"
        )


def test_env_ok_with_no_remotes(isolated_ws):
    """Environment report remains usable in a repository that has no remotes."""
    isolated_ws.init_repo()
    marker = f"flt_{token(8)}"
    require_git_config_set(isolated_ws, "filter.lfs.clean", marker, local=True)
    version = isolated_ws.invoke_via_git(["version"])
    result = isolated_ws.invoke_via_git(["env"])
    print(f"no-remote env stdout_len={len(result.stdout)}")
    print(f"no-remote env contains filter marker={marker in result.stdout_text}")
    report = check_env_effective_configuration(result)
    identity = require_version_path_identity_token(version)
    related = related_facts_without_dedicated(
        report,
        dedicated_urls=(),
        git_remote_urls=(),
        extra_unrelated=(marker,),
    )
    related_token = build_identity_token(related)
    assert result.returncode == 0, (
        "environment report must remain usable in a repository with no remotes"
    )
    assert result.stdout_text.strip(), (
        "environment report must print effective VCS Orbulk-related configuration, "
        "not empty stdout"
    )
    assert report == result.stdout_text, (
        "configuration report must be the environment-report subcommand stdout"
    )
    assert marker in report, (
        "filter configuration summary still applies with no remotes; "
        "the report must reflect the effective filter value"
    )
    assert related_token == identity, (
        "no-remote environment related facts must present this build's "
        "identity, agreeing with the version path"
    )
    assert result.stdout != version.stdout, (
        "environment report was only the version identity presentation, "
        "not effective VCS Orbulk-related configuration"
    )


def test_unknown_subcommand_fails_unlike_bare_invocation(isolated_ws):
    """An unknown subcommand fails; a bare invocation of the same entry succeeds."""
    unknown_name = f"zxq-{token()}"
    clean = isolated_ws.invoke_via_git([])
    dirty = isolated_ws.invoke_via_git([unknown_name])
    print(f"bare exit={clean.returncode} unknown exit={dirty.returncode}")
    print(f"unknown stderr={dirty.stderr_text!r}")
    require_rejected_unlike_clean(clean, dirty)
    assert dirty.returncode != 0, (
        "unknown subcommand succeeded on the git-extension path"
    )
    assert dirty.stderr_text.strip(), (
        "unknown subcommand produced no error on stderr"
    )
    direct_clean = isolated_ws.invoke([])
    direct_dirty = isolated_ws.invoke([unknown_name])
    require_rejected_unlike_clean(direct_clean, direct_dirty)
    assert direct_dirty.returncode != 0, (
        "unknown subcommand succeeded on the direct binary"
    )
    assert direct_dirty.stderr_text.strip(), (
        "unknown subcommand on the direct binary produced no error on stderr"
    )


def test_undefined_option_top_level(isolated_ws):
    """An undefined option at the top-level entry is refused."""
    flag = f"--zxq-{token()}"
    clean_git = isolated_ws.invoke_via_git([])
    dirty_git = isolated_ws.invoke_via_git([flag])
    print(f"top-level dirty stderr={dirty_git.stderr_text!r}")
    require_rejected_unlike_clean(clean_git, dirty_git)
    assert dirty_git.returncode != 0, (
        "undefined option at the top-level git-extension entry was accepted"
    )
    assert dirty_git.stderr_text.strip(), (
        "undefined option at the top-level git-extension entry produced no stderr error"
    )
    clean_bin = isolated_ws.invoke([])
    dirty_bin = isolated_ws.invoke([flag])
    require_rejected_unlike_clean(clean_bin, dirty_bin)
    assert dirty_bin.returncode != 0, (
        "undefined option at the top-level direct binary was accepted"
    )
    assert dirty_bin.stderr_text.strip(), (
        "undefined option at the top-level direct binary produced no stderr error"
    )


def test_undefined_option_after_env(isolated_ws):
    """An undefined option after the known ``env`` subcommand is refused."""
    isolated_ws.init_repo()
    add_git_remote(isolated_ws, "origin", runtime_http_url("opt"))
    flag = f"--zxq-{token()}"
    clean = isolated_ws.invoke_via_git(["env"])
    dirty = isolated_ws.invoke_via_git(["env", flag])
    print(f"env dirty stderr={dirty.stderr_text!r}")
    require_rejected_unlike_clean(clean, dirty)
    assert dirty.returncode != 0, (
        "undefined option after env was accepted on the git-extension path"
    )
    assert dirty.stderr_text.strip(), (
        "undefined option after env produced no error on stderr"
    )
    dirty_bin = isolated_ws.invoke(["env", flag])
    clean_bin = isolated_ws.invoke(["env"])
    require_rejected_unlike_clean(clean_bin, dirty_bin)
    assert dirty_bin.returncode != 0, (
        "undefined option after env was accepted on the direct binary"
    )
    assert dirty_bin.stderr_text.strip(), (
        "undefined option after env on the direct binary produced no stderr error"
    )


def test_undefined_option_after_version(isolated_ws):
    """An undefined option after the known ``version`` subcommand is refused."""
    flag = f"--zxq-{token()}"
    clean = isolated_ws.invoke_via_git(["version"])
    dirty = isolated_ws.invoke_via_git(["version", flag])
    print(f"version dirty stderr={dirty.stderr_text!r}")
    require_rejected_unlike_clean(clean, dirty)
    assert dirty.returncode != 0, (
        "undefined option after version was accepted on the git-extension path"
    )
    assert dirty.stderr_text.strip(), (
        "undefined option after version produced no error on stderr"
    )
    clean_bin = isolated_ws.invoke(["version"])
    dirty_bin = isolated_ws.invoke(["version", flag])
    require_rejected_unlike_clean(clean_bin, dirty_bin)
    assert dirty_bin.returncode != 0, (
        "undefined option after version was accepted on the direct binary"
    )
    assert dirty_bin.stderr_text.strip(), (
        "undefined option after version on the direct binary produced no stderr error"
    )


def test_git_orbulk_fails_when_binary_absent_from_path(isolated_ws, product_binary):
    """Negative control: Git-extension path fails when the binary is not on PATH."""
    present = isolated_ws.invoke_via_git(["version"])
    require_success(present)
    assert present.stdout_text.strip(), (
        "live baseline: version with the product binary on PATH must report identity"
    )
    hidden_path = path_without_product_bin(isolated_ws.env)
    print(f"product_binary={product_binary} hidden_path={hidden_path!r}")
    result = isolated_ws.invoke_via_git(
        ["version"],
        env_updates={"PATH": hidden_path},
    )
    print(f"absent-binary exit={result.returncode} stderr={result.stderr_text!r}")
    assert result.returncode != 0, (
        "git orbulk version succeeded after the product binary was removed from PATH"
    )
    assert (result.returncode, result.stdout, result.stderr) != (
        present.returncode,
        present.stdout,
        present.stderr,
    ), "absent-binary run was not distinguishable from version with the binary on PATH"
