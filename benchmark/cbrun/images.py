"""Per-case ``:agent`` image derivation and hidden-test extraction.

For each case cbrun derives an ``:agent`` image from the published GT-free
``:deliverable`` image by (1) extracting ``/tests/final`` to a host-side cache,
(2) installing the agent CLIs (pinned where configured), and (3) physically
removing ``/tests/final`` in a new image layer. The solve container is started
from this ``:agent`` image, so the hidden tests are absent from the solve
filesystem entirely (not merely deleted at runtime), and are re-injected only
for the judge phase.

Note on a shared CLI base: the published ``:deliverable`` images have
heterogeneous bases (e.g. ``python:3.13-slim`` vs ``cuda:13.0-devel-ubuntu24.04``),
so a single shared ``FROM`` base cannot be overlaid onto all of them. cbrun
instead installs pinned CLI versions per case with idempotent caching (skip when
the ``:agent`` image already exists), which gives the same reproducibility goal
without an impossible image merge.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import agents
from .denylist import write_shim_assets
from .docker_env import image_exists

# Defense in depth when :deliverable was built before workspace sanitization existed.
_AGENT_APP_SANITIZE = (
    "rm -rf /app /opt/codingbench/repo /opt/cb-warm && mkdir -p /app"
)

__all__ = [
    "AgentImage",
    "deliverable_tag",
    "agent_tag",
    "extract_hidden_tests",
    "ensure_agent_image",
]

CONTAINER_TESTS_FINAL = "/tests/final"


def deliverable_tag(case_id: str) -> str:
    return f"codingbench-benchmark/{case_id}:deliverable"


def agent_tag(case_id: str) -> str:
    return f"codingbench-benchmark/{case_id}:agent"


@dataclass(frozen=True)
class AgentImage:
    case_id: str
    deliverable_image: str
    agent_image: str
    tests_cache_dir: Path  # host dir holding the extracted /tests/final


def extract_hidden_tests(deliverable_image: str, dest_dir: Path) -> Path:
    """Copy ``/tests/final`` out of the deliverable image into ``dest_dir``.

    Returns the path to the extracted ``final`` directory. Raises if the
    deliverable image has no hidden tests (an invalid benchmark image).
    """
    dest_dir = Path(dest_dir)
    if dest_dir.exists():
        _rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    create = subprocess.run(
        ["docker", "create", deliverable_image],
        capture_output=True,
        text=True,
    )
    if create.returncode != 0:
        raise RuntimeError(f"docker create {deliverable_image} failed: {create.stderr.strip()}")
    container_id = create.stdout.strip()
    try:
        cp = subprocess.run(
            ["docker", "cp", f"{container_id}:{CONTAINER_TESTS_FINAL}", str(dest_dir / "final")],
            capture_output=True,
            text=True,
        )
        if cp.returncode != 0:
            raise RuntimeError(
                f"deliverable image {deliverable_image} is missing {CONTAINER_TESTS_FINAL}: "
                f"{cp.stderr.strip()}"
            )
    finally:
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, text=True)

    final_dir = dest_dir / "final"
    if not (final_dir / "test_manifest.json").is_file():
        raise RuntimeError(
            f"extracted hidden tests for {deliverable_image} lack test_manifest.json"
        )
    return final_dir


def _node_install_snippet() -> str:
    return (
        "if ! command -v npm >/dev/null 2>&1; then "
        "  if command -v apt-get >/dev/null 2>&1; then "
        "    apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && "
        "    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && "
        "    apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*; "
        "  elif command -v apk >/dev/null 2>&1; then "
        "    apk add --no-cache nodejs npm curl bash; "
        "  else echo 'cbrun: no supported package manager to install Node.js' >&2; exit 1; fi; "
        "fi"
    )


def _cli_install_snippet(environ: dict[str, str] | None) -> str:
    pkgs = []
    for backend, (pkg, _env_key) in agents._CLI_PACKAGES.items():
        pkgs.append(pkg + agents.cli_version_spec(backend, environ))
    pkg_args = " ".join(pkgs)
    return (
        f"npm install -g {pkg_args} && "
        "codex --version && opencode --version && claude --version && "
        f"{agents.cli_install_command('cursor', environ)}"
    )


def _agent_user_snippet() -> str:
    """Create fixed non-root user for agents that reject root bypass (e.g. Claude Code)."""
    return (
        "if ! id -u cbagent >/dev/null 2>&1; then "
        "  command -v useradd >/dev/null 2>&1 || { "
        "echo 'cbrun: useradd not found; cannot create cbagent for non-root agents' >&2; exit 1; "
        "}; "
        "useradd -m -s /bin/bash -u 1001 cbagent 2>/dev/null || "
        "useradd -m -s /bin/bash cbagent; "
        "fi"
    )


def _build_dockerfile(
    deliverable_image: str,
    environ: dict[str, str] | None,
    *,
    denylist_snippet: str = "",
) -> str:
    denylist_block = ""
    if denylist_snippet:
        denylist_block = f"RUN mkdir -p /opt/cbrun/bin\n{denylist_snippet}"
    return (
        f"FROM {deliverable_image}\n"
        "USER root\n"
        f"RUN set -eux; {_node_install_snippet()}; {_cli_install_snippet(environ)}; "
        f"{_agent_user_snippet()}\n"
        f"{denylist_block}"
        f"RUN set -eux; {_AGENT_APP_SANITIZE}; rm -rf {CONTAINER_TESTS_FINAL}\n"
    )


def ensure_agent_image(
    case_id: str,
    *,
    cache_root: Path,
    case_dir: Path | None = None,
    deliverable_image: str | None = None,
    force: bool = False,
    environ: dict[str, str] | None = None,
) -> AgentImage:
    """Build (or reuse) the ``:agent`` image and extract hidden tests.

    Idempotent: when the ``:agent`` image and the tests cache already exist and
    ``force`` is False, returns immediately.
    """
    deliverable = deliverable_image or deliverable_tag(case_id)
    if not image_exists(deliverable):
        raise RuntimeError(
            f"deliverable image not found: {deliverable}. Build or pull the "
            "GT-free :deliverable image first."
        )

    tag = agent_tag(case_id)
    tests_cache = Path(cache_root) / case_id / "tests"
    final_dir = tests_cache / "final"

    cached_ready = (final_dir / "test_manifest.json").is_file()
    if image_exists(tag) and cached_ready and not force:
        return AgentImage(case_id, deliverable, tag, tests_cache)

    # Always (re)extract hidden tests so the host cache matches the deliverable.
    extract_hidden_tests(deliverable, tests_cache)

    with tempfile.TemporaryDirectory() as ctx:
        build_ctx = Path(ctx)
        denylist_snippet = ""
        if case_dir is not None:
            denylist_snippet = write_shim_assets(build_ctx, case_dir / "source" / "denylist.json")
        dockerfile = _build_dockerfile(deliverable, environ, denylist_snippet=denylist_snippet)
        df_path = build_ctx / "Dockerfile"
        df_path.write_text(dockerfile, encoding="utf-8")
        build = subprocess.run(
            ["docker", "build", "-t", tag, "-f", str(df_path), ctx],
            capture_output=True,
            text=True,
        )
        if build.returncode != 0:
            raise RuntimeError(
                f"docker build of {tag} failed:\n{build.stdout[-2000:]}\n{build.stderr[-2000:]}"
            )
    return AgentImage(case_id, deliverable, tag, tests_cache)


def _rmtree(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)
