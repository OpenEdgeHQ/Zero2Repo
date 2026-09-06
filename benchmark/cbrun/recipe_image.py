"""Rebuild ``:deliverable`` from a pipeline base image + recipe.lock.

Clone-and-eval hosts should not download a multi-GB image per case. cbrun
replays the same env-install-only path as CodingBench-1.6
(``build_deliverable_env_install_only``):

1. Start from ``recipe.lock.json`` ``base_image`` (must already be present).
2. Run ``runner.install_command`` (toolchain only; no seed repo).
3. Stage public PRD / Contract / optional hardware + hidden ``milestones/final``.
4. Leave ``/app`` empty. Commit as ``codingbench-benchmark/<case>:deliverable``.

``build_command`` is recorded on the lock but is not replayed here: there is
no upstream tree to compile. The solving agent builds in ``/app``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .docker_env import docker_available, image_exists
from .images import deliverable_tag
from .recipe import (
    RecipeLockError,
    env_recipe_tag,
    load_lock,
    resolve_lock_base_image,
    resolve_lock_runner,
    stage_benchmark_bundle,
    staging_shell_command,
    validate_lock_env_install,
)

__all__ = ["ensure_deliverable_image"]

DEFAULT_ENV_BUILD_RETRIES = 3
DEFAULT_ENV_BUILD_RETRY_DELAY_SEC = 15.0

_REGISTRY_ENV_KEYS = (
    "PIP_INDEX_URL",
    "PIP_EXTRA_INDEX_URL",
    "PIP_TRUSTED_HOST",
    "NPM_CONFIG_REGISTRY",
    "npm_config_registry",
    "MAVEN_OPTS",
    "PNPM_HOME",
)


def _remove_container(name: str) -> None:
    subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)


def _env_build_retries() -> int:
    raw = os.environ.get("CODINGBENCH_RECIPE_ENV_RETRIES", "").strip()
    if not raw:
        return DEFAULT_ENV_BUILD_RETRIES
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_ENV_BUILD_RETRIES


def _env_build_retry_delay_sec() -> float:
    raw = os.environ.get("CODINGBENCH_RECIPE_ENV_RETRY_DELAY_SEC", "").strip()
    if not raw:
        return DEFAULT_ENV_BUILD_RETRY_DELAY_SEC
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_ENV_BUILD_RETRY_DELAY_SEC


def _docker_network() -> str:
    return os.environ.get("CODINGBENCH_DOCKER_NETWORK", "host")


def _registry_docker_env() -> list[str]:
    args: list[str] = []
    for var in _REGISTRY_ENV_KEYS:
        val = os.environ.get(var)
        if val and val.strip():
            args += ["-e", f"{var}={val.strip()}"]
    return args


def _runner_docker_gpus(runner: dict[str, Any]) -> str | None:
    override = os.environ.get("CODINGBENCH_DOCKER_GPUS")
    if override is not None:
        value = override.strip()
        return value or None
    raw = runner.get("docker_gpus")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _volume_mounts(case_dir: Path) -> list[str]:
    """Optional operator-supplied caches. Never invented per case."""
    mounts: list[str] = []
    env_dir = case_dir / "source" / "env"
    if env_dir.is_dir() and any(env_dir.iterdir()):
        mounts.extend(["-v", f"{env_dir.resolve()}:/env-assets:ro"])
    cache_raw = os.environ.get("CODINGBENCH_BUILD_CACHE_DIR", "").strip()
    if cache_raw and cache_raw.lower() not in {"off", "0", "false", "no"}:
        cache_dir = Path(cache_raw).expanduser()
        if cache_dir.is_dir():
            mounts.extend(["-v", f"{cache_dir.resolve()}:/opt/cb-cache"])
    return mounts


def _load_manifest_runner(case_dir: Path) -> dict[str, Any]:
    manifest_path = case_dir / "source" / "manifest.json"
    if not manifest_path.is_file():
        raise RecipeLockError(f"missing {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecipeLockError(f"invalid JSON in {manifest_path}: {exc}") from exc
    runner = manifest.get("runner")
    if not isinstance(runner, dict):
        raise RecipeLockError("manifest.runner missing")
    return runner


def _build_env_image(
    case_dir: Path,
    lock: dict[str, Any],
    runner: dict[str, Any],
    *,
    force: bool,
) -> str:
    if not docker_available():
        raise RecipeLockError("docker is unavailable")

    case_id = case_dir.name
    tag = env_recipe_tag(case_id)
    if not force and image_exists(tag):
        print(f"[cbrun] reusing env image {tag}", flush=True)
        return tag

    base_image = resolve_lock_base_image(lock)
    if not image_exists(base_image):
        raise RecipeLockError(
            f"base image not found: {base_image}. Load the shared pipeline "
            "base (codingbench-base/*) before rebuilding a case deliverable."
        )

    install = str(runner.get("install_command") or "").strip()
    if not install or install.lower() == "true":
        raise RecipeLockError("runner.install_command is empty")

    container_name = f"z2r-recipe-env-{case_id}"
    gpus = _runner_docker_gpus(runner)
    argv = [
        "docker",
        "run",
        "--name",
        container_name,
        "--network",
        _docker_network(),
        *_registry_docker_env(),
    ]
    if gpus:
        argv.extend(["--gpus", gpus])
    argv.extend(_volume_mounts(case_dir))
    argv.extend([base_image, "bash", "-lc", install])

    retries = _env_build_retries()
    delay = _env_build_retry_delay_sec()
    last_output = ""
    for attempt in range(1, retries + 1):
        _remove_container(container_name)
        print(
            f"[cbrun] building env {tag} from {base_image} "
            f"(attempt {attempt}/{retries})",
            flush=True,
        )
        proc = subprocess.run(argv)
        if proc.returncode == 0:
            break
        last_output = f"exit {proc.returncode} (see streamed docker output above)"
        if attempt < retries:
            print(
                f"[cbrun] env install failed (attempt {attempt}); "
                f"retrying in {delay}s",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay)
    else:
        _remove_container(container_name)
        raise RecipeLockError(
            f"env-only install failed after {retries} attempts:\n{last_output}"
        )

    commit = subprocess.run(
        ["docker", "commit", container_name, tag],
        capture_output=True,
        text=True,
    )
    _remove_container(container_name)
    if commit.returncode != 0:
        raise RecipeLockError(f"docker commit failed: {commit.stderr.strip()}")
    print(f"[cbrun] committed env image {tag}", flush=True)
    return tag


def _stage_deliverable(
    case_dir: Path,
    env_tag: str,
    *,
    force: bool,
) -> str:
    case_id = case_dir.name
    tag = deliverable_tag(case_id)
    if not force and image_exists(tag):
        print(f"[cbrun] reusing deliverable image {tag}", flush=True)
        return tag

    final_dir = case_dir / "milestones" / "final"
    container_name = f"z2r-recipe-deliverable-{case_id}"
    with stage_benchmark_bundle(case_dir, final_dir) as bundle:
        _remove_container(container_name)
        argv = [
            "docker",
            "run",
            "--name",
            container_name,
            "--network",
            _docker_network(),
            "-v",
            f"{bundle}:/src:ro",
            env_tag,
            "bash",
            "-lc",
            staging_shell_command(),
        ]
        print(f"[cbrun] staging deliverable {tag} from {env_tag}", flush=True)
        proc = subprocess.run(argv)
        if proc.returncode != 0:
            _remove_container(container_name)
            raise RecipeLockError(
                f"deliverable staging failed (exit {proc.returncode}; "
                "see streamed docker output above)"
            )
        commit = subprocess.run(
            ["docker", "commit", "-c", "WORKDIR /app", container_name, tag],
            capture_output=True,
            text=True,
        )
        _remove_container(container_name)
        if commit.returncode != 0:
            raise RecipeLockError(f"docker commit failed: {commit.stderr.strip()}")
    print(f"[cbrun] committed deliverable image {tag}", flush=True)
    return tag


def ensure_deliverable_image(
    case_dir: Path | str,
    *,
    force: bool = False,
) -> str:
    """Build or reuse ``codingbench-benchmark/<case>:deliverable``.

    Idempotent when ``force`` is false and the tag already exists.
    """
    case_dir = Path(case_dir).resolve()
    tag = deliverable_tag(case_dir.name)
    if not force and image_exists(tag):
        return tag

    lock = load_lock(case_dir)
    validate_lock_env_install(lock)
    runner = resolve_lock_runner(lock, _load_manifest_runner(case_dir))
    env_tag = _build_env_image(case_dir, lock, runner, force=force)
    return _stage_deliverable(case_dir, env_tag, force=True)
