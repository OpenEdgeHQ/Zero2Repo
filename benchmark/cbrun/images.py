"""Per-case ``:deliverable`` / ``:agent`` image derivation.

When ``:deliverable`` is missing, cbrun rebuilds it from the recipe base
(``codingbench-base/<public>``, built FROM the matching public image such as
Docker Hub ``ubuntu:24.04`` using ``cbrun/base_image/Dockerfile``) plus
``source/recipe.lock.json`` (env-install-only: toolchain, public specs,
hidden tests, empty ``/app``). If the local base tag is missing, cbrun pulls
the public image and builds the toolchain image once. Callers that clone the
repo therefore do not need a per-case image tarball.

From that ``:deliverable``, cbrun derives an ``:agent`` image by (1) extracting
``/tests/final`` to a host-side cache, (2) installing the requested backend
CLI (or all built-in CLIs when no backend is given), and (3) physically
removing ``/tests/final`` in a new image layer. Per-backend images are tagged
``:agent-<backend>`` so a Cursor trial does not pull unused npm CLIs. The solve container is started from this ``:agent`` image, so the hidden
tests are absent from the solve filesystem entirely (not merely deleted at
runtime), and are re-injected only for the judge phase.

Note on a shared CLI base: the published ``:deliverable`` images have
heterogeneous bases (e.g. ``python:3.13-slim`` vs ``cuda:13.0-devel-ubuntu24.04``),
so a single shared ``FROM`` base cannot be overlaid onto all of them. cbrun
instead installs pinned CLI versions per case with content-validated caching,
which gives the same reproducibility goal
without an impossible image merge.
"""

from __future__ import annotations

import subprocess
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import agents
from .denylist import write_shim_assets
from .docker_env import image_exists
from .build_logs import run_build
from .state import (FINGERPRINT_LABEL, atomic_json, cache_lock, digest, file_manifest,
                    image_identity, image_matches, platform_name, versioned_tag)

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


def agent_tag(case_id: str, backend: str | None = None) -> str:
    if backend:
        return f"codingbench-benchmark/{case_id}:agent-{backend}"
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
        ["docker", "create", "--platform", platform_name(), deliverable_image],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if create.returncode != 0:
        raise RuntimeError(f"docker create {deliverable_image} failed: {create.stderr.strip()}")
    container_id = create.stdout.strip()
    try:
        cp = subprocess.run(
            ["docker", "cp", f"{container_id}:{CONTAINER_TESTS_FINAL}", str(dest_dir / "final")],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if cp.returncode != 0:
            raise RuntimeError(
                f"deliverable image {deliverable_image} is missing {CONTAINER_TESTS_FINAL}: "
                f"{cp.stderr.strip()}"
            )
    finally:
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, text=True, timeout=30)

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


def _cli_install_snippet(environ: dict[str, str] | None, backend: str | None = None) -> str:
    if backend == "custom":
        return "true"
    if backend == "cursor":
        return agents.cli_install_command("cursor", environ)
    if backend is not None:
        return agents.cli_install_command(backend, environ)
    npm_clis = " && ".join(
        agents.cli_install_command(name, environ) for name in agents._CLI_PACKAGES
    )
    return f"{npm_clis} && {agents.cli_install_command('cursor', environ)}"


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
    backend: str | None = None,
) -> str:
    denylist_block = ""
    if denylist_snippet:
        denylist_block = f"RUN mkdir -p /opt/cbrun/bin\n{denylist_snippet}"
    cli = _cli_install_snippet(environ, backend)
    # Custom specs install their own tools; Cursor uses its official script.
    if backend in {"cursor", "custom"}:
        install = f"RUN set -eux; {cli}; {_agent_user_snippet()}\n"
    else:
        install = (
            f"RUN set -eux; {_node_install_snippet()}; {cli}; "
            f"{_agent_user_snippet()}\n"
        )
    return (
        f"FROM {deliverable_image}\n"
        "USER root\n"
        f"{install}"
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
    backend: str | None = None,
) -> AgentImage:
    """Build (or reuse) the ``:agent`` image and extract hidden tests.

    Reuse requires a matching deliverable identity, installer fingerprint,
    platform and intact test cache. Legacy tag existence is insufficient.
    """
    if deliverable_image is None and case_dir is not None:
        from .recipe_image import ensure_deliverable_image
        deliverable = ensure_deliverable_image(case_dir, force=force)
    else:
        # An explicit imported image is an operator override; its actual ID
        # still determines every downstream cache identity.
        deliverable = deliverable_image or deliverable_tag(case_id)
    deliverable_id = image_identity(deliverable)["id"]
    tests_cache = Path(cache_root) / case_id / deliverable_id.removeprefix("sha256:") / "tests"
    record_path = tests_cache.parent / "tests.json"
    with cache_lock(tests_cache.parent / ".lock"):
        try:
            record = json.loads(record_path.read_text())
        except (OSError, ValueError):
            record = {}
        current = file_manifest(tests_cache / "final")
        if (record.get("deliverable_id") != deliverable_id or not current
                or record.get("files") != current
                or not (tests_cache / "final/test_manifest.json").is_file()):
            extract_hidden_tests(deliverable_id, tests_cache)
            atomic_json(record_path, {"deliverable_id": deliverable_id,
                                      "files": file_manifest(tests_cache / "final")})
    with tempfile.TemporaryDirectory() as ctx:
        build_ctx = Path(ctx)
        denylist_snippet = ""
        if case_dir is not None:
            denylist_snippet = write_shim_assets(build_ctx, case_dir / "source" / "denylist.json")
        dockerfile = _build_dockerfile(
            deliverable, environ, denylist_snippet=denylist_snippet, backend=backend
        )
        fingerprint = digest({"deliverable_id": deliverable_id, "dockerfile": dockerfile,
                              "platform": platform_name(), "shim_assets": file_manifest(build_ctx),
                              "images_code": file_manifest(Path(__file__))})
        tag = versioned_tag(agent_tag(case_id, backend), fingerprint)
        if not force and image_matches(tag, fingerprint):
            return AgentImage(case_id, deliverable, tag, tests_cache)
        df_path = build_ctx / "Dockerfile"
        df_path.write_text(dockerfile, encoding="utf-8")
        print(
            f"[cbrun] building agent image {tag} (cli={backend or 'all'})",
            flush=True,
        )
        build = run_build(
            ["docker", "build", "--platform", platform_name(), "--label",
             f"{FINGERPRINT_LABEL}={fingerprint}", "-t", tag, "-f", str(df_path), ctx],
            timeout=1800,
        )
        if build.returncode != 0:
            raise RuntimeError(f"docker build of {tag} failed (exit {build.returncode})")
        if not image_matches(tag, fingerprint):
            raise RuntimeError(f"agent image identity invalid after build: {tag}")
    return AgentImage(case_id, deliverable, tag, tests_cache)


def _rmtree(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)
