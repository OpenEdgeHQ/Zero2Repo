"""Docker-free tests for recipe.lock load, env-only validation, and bundle staging."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun.recipe import (  # noqa: E402
    PIPELINE_BASE_PREFIX,
    RecipeLockError,
    env_recipe_tag,
    load_lock,
    public_base_pull_ref,
    resolve_lock_base_image,
    resolve_lock_runner,
    stage_benchmark_bundle,
    staging_shell_command,
    validate_lock_env_install,
)


def _case_dir(case_id: str) -> Path:
    return BENCHMARK_ROOT / "cases" / case_id


def test_load_lock_case001_has_base_and_install() -> None:
    lock = load_lock(_case_dir("case001"))
    validate_lock_env_install(lock)
    assert resolve_lock_base_image(lock) == "codingbench-base/ubuntu:24.04"
    assert "cmake" in lock["runner"]["install_command"]
    assert env_recipe_tag("case001") == "codingbench-env/case001:recipe-env"


def test_public_base_pull_ref_strips_pipeline_prefix() -> None:
    assert PIPELINE_BASE_PREFIX == "codingbench-base/"
    assert (
        public_base_pull_ref("codingbench-base/ubuntu:24.04") == "ubuntu:24.04"
    )
    assert public_base_pull_ref("ubuntu:24.04") == "ubuntu:24.04"
    with pytest.raises(RecipeLockError, match="empty"):
        public_base_pull_ref("codingbench-base/")
    with pytest.raises(RecipeLockError, match="empty"):
        public_base_pull_ref("  ")


def test_ensure_base_image_builds_toolchain_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from cbrun import recipe_image

    calls: list[list[str]] = []
    present: set[str] = set()

    def fake_exists(tag: str) -> bool:
        return tag in present

    def fake_run(argv, **kwargs):  # noqa: ANN001, ARG001
        calls.append(list(argv))
        class Result:
            returncode = 0
            stderr = ""
        if argv[:2] == ["docker", "pull"]:
            present.add(argv[2])
        if argv[:2] == ["docker", "build"]:
            tag = argv[argv.index("-t") + 1]
            present.add(tag)
        return Result()

    monkeypatch.setattr(recipe_image, "image_exists", fake_exists)
    monkeypatch.setattr(recipe_image.subprocess, "run", fake_run)
    recipe_image._ensure_base_image("codingbench-base/ubuntu:24.04")
    assert calls[0][:3] == ["docker", "pull", "ubuntu:24.04"]
    assert calls[1][:2] == ["docker", "build"]
    assert "--build-arg" in calls[1]
    assert "FROM_IMAGE=ubuntu:24.04" in calls[1]
    assert "-t" in calls[1]
    assert "codingbench-base/ubuntu:24.04" in calls[1]
    assert str(recipe_image.BASE_IMAGE_DOCKERFILE_DIR) in calls[1]
    assert (recipe_image.BASE_IMAGE_DOCKERFILE_DIR / "Dockerfile").is_file()
    assert "codingbench-base/ubuntu:24.04" in present


def test_ensure_base_image_pulls_public_tag_without_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    from cbrun import recipe_image

    calls: list[list[str]] = []
    present: set[str] = set()

    def fake_exists(tag: str) -> bool:
        return tag in present

    def fake_run(argv, **kwargs):  # noqa: ANN001, ARG001
        calls.append(list(argv))
        class Result:
            returncode = 0
            stderr = ""
        if argv[:2] == ["docker", "pull"]:
            present.add(argv[2])
        return Result()

    monkeypatch.setattr(recipe_image, "image_exists", fake_exists)
    monkeypatch.setattr(recipe_image.subprocess, "run", fake_run)
    recipe_image._ensure_base_image("ubuntu:24.04")
    assert calls == [["docker", "pull", "ubuntu:24.04"]]
    assert not any(c[:2] == ["docker", "build"] for c in calls)


def test_ensure_base_image_skips_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    from cbrun import recipe_image

    def fake_exists(tag: str) -> bool:
        return tag == "codingbench-base/ubuntu:24.04"

    def fake_run(*args, **kwargs):  # noqa: ANN001, ARG001
        raise AssertionError("docker must not run when the base image exists")

    monkeypatch.setattr(recipe_image, "image_exists", fake_exists)
    monkeypatch.setattr(recipe_image.subprocess, "run", fake_run)
    recipe_image._ensure_base_image("codingbench-base/ubuntu:24.04")


def test_ensure_base_image_raises_when_pull_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from cbrun import recipe_image

    monkeypatch.setattr(recipe_image, "image_exists", lambda tag: False)

    class Result:
        returncode = 1
        stderr = "denied"

    monkeypatch.setattr(
        recipe_image.subprocess, "run", lambda *a, **k: Result()  # noqa: ARG005
    )
    with pytest.raises(RecipeLockError, match="docker pull failed"):
        recipe_image._ensure_base_image("codingbench-base/ubuntu:24.04")


def test_base_image_dockerfile_uses_official_sources() -> None:
    from cbrun.recipe_image import BASE_IMAGE_DOCKERFILE_DIR

    text = (BASE_IMAGE_DOCKERFILE_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM ${FROM_IMAGE}" in text
    assert "nodejs.org/dist" in text
    assert "repo.anaconda.com/miniconda" in text
    assert "mirrors.aliyun.com" not in text
    assert "tuna.tsinghua" not in text
    assert "npmmirror.com" not in text
    script = BASE_IMAGE_DOCKERFILE_DIR / "build.sh"
    assert script.is_file()


def test_released_cases_locks_are_env_install_valid() -> None:
    cases = sorted(p for p in (BENCHMARK_ROOT / "cases").iterdir() if p.is_dir())
    assert cases, "expected released cases under benchmark/cases"
    for case_dir in cases:
        if not (case_dir / "source" / "recipe.lock.json").is_file():
            continue
        lock = load_lock(case_dir)
        validate_lock_env_install(lock)
        assert resolve_lock_base_image(lock).startswith("codingbench-base/")


def test_resolve_lock_runner_manifest_wins() -> None:
    lock = {
        "schema_version": 1,
        "base_image": "codingbench-base/ubuntu:24.04",
        "runner": {"install_command": "from-lock", "build_command": "lock-build"},
    }
    merged = resolve_lock_runner(
        lock,
        {"install_command": "from-manifest", "build_command": ""},
    )
    assert merged["install_command"] == "from-manifest"
    assert merged["build_command"] == ""
    filled = resolve_lock_runner(lock, {})
    assert filled["install_command"] == "from-lock"
    assert filled["build_command"] == "lock-build"


def test_validate_rejects_seed_repo_install() -> None:
    lock = {
        "schema_version": 1,
        "base_image": "codingbench-base/ubuntu:24.04",
        "runner": {
            "install_command": "pip install -e .",
            "build_command": "",
        },
    }
    with pytest.raises(RecipeLockError, match="seed repo"):
        validate_lock_env_install(lock)


def test_validate_rejects_missing_install() -> None:
    lock = {
        "schema_version": 1,
        "base_image": "codingbench-base/ubuntu:24.04",
        "runner": {"install_command": "", "build_command": ""},
    }
    with pytest.raises(RecipeLockError, match="install_command is empty"):
        validate_lock_env_install(lock)


def test_stage_bundle_case001_has_public_specs_and_hidden_tests() -> None:
    case_dir = _case_dir("case001")
    final_dir = case_dir / "milestones" / "final"
    with stage_benchmark_bundle(case_dir, final_dir) as bundle:
        assert (bundle / "environment" / "prd" / "Full_PRD.md").is_file()
        assert (bundle / "environment" / "Interface_Contract.md").is_file()
        assert (bundle / "environment" / "Hardware_Requirements.md").is_file()
        assert (bundle / "final" / "test_manifest.json").is_file()
        assert (bundle / "final" / "tests" / "F01_acceptance.py").is_file()
        prd = (bundle / "environment" / "prd" / "Full_PRD.md").read_text(
            encoding="utf-8"
        )
        assert "Hrefparse" in prd


def test_stage_bundle_drops_pipeline_metadata(tmp_path: Path) -> None:
    case_dir = tmp_path / "case999"
    public = case_dir / "public"
    final = case_dir / "milestones" / "final" / "tests"
    public.mkdir(parents=True)
    final.mkdir(parents=True)
    (public / "Full_PRD.md").write_text("P" * 240 + "\n", encoding="utf-8")
    (public / "Interface_Contract.md").write_text("C" * 80 + "\n", encoding="utf-8")
    (case_dir / "milestones" / "final" / "test_manifest.json").write_text(
        '{"test_files":[]}\n', encoding="utf-8"
    )
    (final / "F01_acceptance.py").write_text("assert True\n", encoding="utf-8")
    (case_dir / "milestones" / "final" / "run_meta.json").write_text(
        json.dumps({"image": "secret-tag"}), encoding="utf-8"
    )
    (case_dir / "milestones" / "final" / "notes.log").write_text("x\n", encoding="utf-8")

    with stage_benchmark_bundle(case_dir, case_dir / "milestones" / "final") as bundle:
        assert not (bundle / "final" / "run_meta.json").exists()
        assert not (bundle / "final" / "notes.log").exists()
        assert (bundle / "final" / "tests" / "F01_acceptance.py").is_file()


def test_staging_shell_copies_hardware_when_present() -> None:
    cmd = staging_shell_command()
    assert "/environment/prd/Full_PRD.md" in cmd
    assert "Hardware_Requirements.md" in cmd
    assert "/tests/final/test_manifest.json" in cmd
    assert "rm -rf /app" in cmd


def test_cli_build_images_does_not_require_model() -> None:
    from cbrun.cli import _parse_args

    args = _parse_args(["--case", "case001", "--build-images"])
    assert args.build_images is True
    assert args.model is None


def test_cli_trial_without_model_is_rejected() -> None:
    from cbrun.cli import main

    assert main(["--case", "case001"]) == 2
