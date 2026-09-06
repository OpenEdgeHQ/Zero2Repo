"""recipe.lock schema and lean benchmark-bundle staging.

Public cases ship a frozen environment recipe (base image + install command)
instead of a per-case Docker tarball. This module is the docker-free half:
load / validate the lock, merge runner fields, and stage the GT-free bundle
that the image builder copies into ``:deliverable``.

The full authoring replay (seed repo at ``/opt/cb-warm`` + ``build_command``)
belongs to the internal pipeline. Clone-and-eval rebuilds are
**env-install-only**: toolchain from ``install_command``, empty ``/app``.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

__all__ = [
    "RECIPE_LOCK_NAME",
    "SCHEMA_VERSION",
    "RecipeLockError",
    "env_recipe_tag",
    "load_lock",
    "recipe_lock_path",
    "resolve_lock_base_image",
    "resolve_lock_runner",
    "stage_benchmark_bundle",
    "staging_shell_command",
    "validate_lock_env_install",
]

SCHEMA_VERSION = 1
RECIPE_LOCK_NAME = "recipe.lock.json"
ENV_RECIPE_TAG_SUFFIX = "recipe-env"

# Commands that consume a project tree. Invalid during env-only rebuild:
# there is no seed repo on a public case checkout.
_ENV_INSTALL_REPO_PATTERNS = (
    "pip install -e .",
    'pip install -e "',
    "npm ci",
    "yarn install",
    "bundle install",
    "dotnet restore",
    "composer install",
    "tar xzf .",
    "./mvnw",
    "python setup.py install",
)

# Pipeline notes must not enter the hidden-test tree that the judge injects.
_BENCHMARK_EXCLUDED_NAMES = frozenset(
    {
        "run_meta.json",
        "review_verdict.json",
        "prd_review_verdict.json",
        "test_usage.json",
        "D_TEST_RESULTS.md",
        "COVERAGE_NOTES.md",
        "stage_notes",
        "benchmark_verify_meta.json",
    }
)
_BENCHMARK_EXCLUDED_SUFFIXES = (".pid", ".log")


class RecipeLockError(RuntimeError):
    """Raised when a recipe.lock cannot be used to rebuild a deliverable."""


def recipe_lock_path(case_dir: Path) -> Path:
    return Path(case_dir) / "source" / RECIPE_LOCK_NAME


def env_recipe_tag(case_id: str) -> str:
    return f"codingbench-env/{case_id}:{ENV_RECIPE_TAG_SUFFIX}"


def load_lock(case_dir: Path) -> dict[str, Any]:
    path = recipe_lock_path(case_dir)
    if not path.is_file():
        raise RecipeLockError(f"missing {path}")
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecipeLockError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(lock, dict):
        raise RecipeLockError(f"invalid lock document in {path}")
    return lock


def resolve_lock_base_image(lock: dict[str, Any]) -> str:
    raw = lock.get("base_image")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    raise RecipeLockError("recipe.lock is missing base_image")


def resolve_lock_runner(lock: dict[str, Any], manifest_runner: dict[str, Any]) -> dict[str, Any]:
    """Merge runner fields. Manifest wins; lock fills blanks."""
    merged = dict(manifest_runner)
    lock_runner = lock.get("runner")
    if isinstance(lock_runner, dict):
        for key in ("docker_image", "docker_gpus", "install_command", "build_command"):
            val = lock_runner.get(key)
            if isinstance(val, str) and val.strip():
                merged.setdefault(key, val)
    return merged


def validate_lock_env_install(lock: dict[str, Any]) -> None:
    """Validate recipe.lock for env-install-only rebuild (no seed repo)."""
    if lock.get("schema_version") != SCHEMA_VERSION:
        raise RecipeLockError(
            f"unsupported schema_version: {lock.get('schema_version')!r}"
        )
    runner = lock.get("runner")
    if not isinstance(runner, dict):
        raise RecipeLockError("recipe.lock runner block is missing")
    install = str(runner.get("install_command") or "").strip()
    if not install or install.lower() == "true":
        raise RecipeLockError("recipe.lock runner.install_command is empty")
    if "build_command" not in runner:
        raise RecipeLockError("recipe.lock runner.build_command is missing")
    lowered = install.lower()
    for pattern in _ENV_INSTALL_REPO_PATTERNS:
        if pattern.lower() in lowered:
            raise RecipeLockError(
                f"env-only install_command must not reference seed repo "
                f"(found {pattern!r} in install_command)"
            )


def _benchmark_ignore(directory: str, names: list[str]) -> set[str]:  # noqa: ARG001
    ignored: set[str] = set()
    for name in names:
        if name in _BENCHMARK_EXCLUDED_NAMES:
            ignored.add(name)
        elif name.endswith(_BENCHMARK_EXCLUDED_SUFFIXES):
            ignored.add(name)
        elif name.endswith(".md") and "_FOR_" in name:
            ignored.add(name)
    return ignored


def stage_benchmark_bundle(case_dir: Path, final_dir: Path) -> Iterator[Path]:
    """Stage agent-visible specs and hidden final tests (no GT)."""
    case_dir = Path(case_dir).resolve()
    final_dir = Path(final_dir).resolve()
    public = case_dir / "public"
    prd_path = public / "Full_PRD.md"
    contract_path = public / "Interface_Contract.md"
    if not prd_path.is_file():
        raise RecipeLockError(f"missing {prd_path}")
    if not contract_path.is_file():
        raise RecipeLockError(f"missing {contract_path}")
    if not (final_dir / "test_manifest.json").is_file():
        raise RecipeLockError(f"missing {final_dir / 'test_manifest.json'}")

    prd_text = prd_path.read_text(encoding="utf-8").strip()
    contract_text = contract_path.read_text(encoding="utf-8").strip()
    if len(prd_text) < 200:
        raise RecipeLockError("benchmark PRD text is missing or too short")
    if len(contract_text) < 50:
        raise RecipeLockError("Interface_Contract.md is missing or too short")

    tmp = tempfile.mkdtemp(prefix="z2r-benchmark-bundle_")
    bundle = Path(tmp)
    try:
        env_root = bundle / "environment"
        prd_dir = env_root / "prd"
        prd_dir.mkdir(parents=True)
        (prd_dir / "Full_PRD.md").write_text(prd_text + "\n", encoding="utf-8")
        (env_root / "Interface_Contract.md").write_text(
            contract_text + "\n", encoding="utf-8"
        )
        hw_path = public / "Hardware_Requirements.md"
        if hw_path.is_file():
            (env_root / "Hardware_Requirements.md").write_text(
                hw_path.read_text(encoding="utf-8").strip() + "\n", encoding="utf-8"
            )
        shutil.copytree(
            final_dir,
            bundle / "final",
            ignore=_benchmark_ignore,
            dirs_exist_ok=True,
        )
        yield bundle
    finally:
        shutil.rmtree(bundle, ignore_errors=True)


stage_benchmark_bundle = contextmanager(stage_benchmark_bundle)


def staging_shell_command() -> str:
    """In-container copy of the staged bundle. Hardware file is optional."""
    return (
        "set -euo pipefail; "
        "rm -rf /app /opt/codingbench/repo /opt/cb-warm; "
        "mkdir -p /tests/final /app /environment/prd; "
        "cp -a /src/final/. /tests/final/; "
        "cp /src/environment/prd/Full_PRD.md /environment/prd/Full_PRD.md; "
        "cp /src/environment/Interface_Contract.md /environment/Interface_Contract.md; "
        "if [ -f /src/environment/Hardware_Requirements.md ]; then "
        "cp /src/environment/Hardware_Requirements.md "
        "/environment/Hardware_Requirements.md; fi; "
        "test -f /tests/final/test_manifest.json"
    )
