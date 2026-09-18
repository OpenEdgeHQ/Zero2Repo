"""Fixtures for case009 dedicated_server_url pushurl-echo filtering."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HELPERS = (
    Path(__file__).resolve().parents[1]
    / "cases"
    / "case009"
    / "milestones"
    / "final"
    / "tests"
)
sys.path.insert(0, str(HELPERS))

from _helpers import dedicated_server_url  # noqa: E402

ENDPOINT = "https://endpoint.example/objects"
GIT_REMOTE = "https://git.example/repo.git"
PUSHURL = "https://push.example/objects"
OTHER = "https://other.example/objects"


def test_origin_endpoint_plus_lfs_pushurl_keeps_endpoint():
    report = (
        f"Endpoint={ENDPOINT}\n"
        f"lfs.pushurl={PUSHURL}\n"
        f"Remote={GIT_REMOTE}\n"
    )
    got = dedicated_server_url(
        report, remote_name="origin", git_remote_url=GIT_REMOTE
    )
    assert got.rstrip("/") == ENDPOINT.rstrip("/")


def test_two_distinct_non_git_http_urls_still_hard_fail():
    report = f"A={ENDPOINT}\nB={OTHER}\nRemote={GIT_REMOTE}\n"
    with pytest.raises(AssertionError, match="multiple distinct"):
        dedicated_server_url(
            report, remote_name="origin", git_remote_url=GIT_REMOTE
        )


def test_only_pushurl_without_dedicated_endpoint_still_fails():
    report = f"lfs.pushurl={PUSHURL}\nRemote={GIT_REMOTE}\n"
    with pytest.raises(AssertionError, match="no dedicated"):
        dedicated_server_url(
            report, remote_name="origin", git_remote_url=GIT_REMOTE
        )


def test_named_remote_pushurl_echo_is_also_dropped():
    remote = "upstream"
    report = (
        f"{remote} Endpoint={ENDPOINT}\n"
        f"remote.{remote}.lfs.pushurl={PUSHURL}\n"
        f"{remote} git={GIT_REMOTE}\n"
    )
    got = dedicated_server_url(
        report, remote_name=remote, git_remote_url=GIT_REMOTE
    )
    assert got.rstrip("/") == ENDPOINT.rstrip("/")
