"""Content identities and atomic run records shared by builds and trials."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import fcntl
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

FINGERPRINT_LABEL = "ai.zero2repo.inputs-sha256"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def platform_name() -> str:
    value = os.environ.get("CBRUN_PLATFORM") or os.environ.get("DOCKER_DEFAULT_PLATFORM") or "linux/amd64"
    if value not in {"linux/amd64", "linux/arm64"}:
        raise ValueError(f"unsupported benchmark platform: {value!r}")
    return value


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_manifest(root: Path) -> dict[str, str]:
    """Hash regular files; record links without following them outside the tree."""
    root = Path(root)
    result = {}
    if not root.exists():
        return result
    paths = [root] if root.is_file() else sorted(root.rglob("*"))
    for path in paths:
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        key = path.name if root.is_file() else path.relative_to(root).as_posix()
        if path.is_symlink():
            result[key] = "symlink:" + os.readlink(path)
        elif path.is_file():
            with path.open("rb") as stream:
                hasher = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
            result[key] = hasher.hexdigest()
    return result


def case_manifest(case_dir: Path) -> dict[str, dict[str, str]]:
    return {name: file_manifest(Path(case_dir) / name)
            for name in ("public", "source", "milestones/final")}


def runtime_manifest(root: Path) -> dict[str, str]:
    return {name: value for name, value in file_manifest(root).items() if name.endswith(".py")}


def atomic_json(path: Path, value: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def cache_lock(path: Path, timeout: float = 120):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"cache is busy: {path}")
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def image_identity(reference: str) -> dict:
    # Select metadata explicitly: never export image environment variables.
    template = ('{"id":{{json .Id}},"os":{{json .Os}},'
                '"architecture":{{json .Architecture}},'
                '"digests":{{json .RepoDigests}},"labels":{{json (index .Config "Labels")}},'
                '"layers":{{json .RootFS.Layers}}}')
    argv = ["docker", "image", "inspect", "--platform", platform_name(), "--format", template, reference]
    proc = subprocess.run(argv,
                          capture_output=True, text=True, timeout=30)
    if proc.returncode and ("unknown flag" in proc.stderr or "requires API" in proc.stderr):
        # Older single-platform Docker engines can still verify the actual arch.
        proc = subprocess.run(argv[:3] + argv[5:], capture_output=True, text=True, timeout=30)
    if proc.returncode:
        raise RuntimeError(f"cannot inspect image {reference}: {proc.stderr.strip()}")
    result = json.loads(proc.stdout)
    # containerd-backed Docker distinguishes an index ID (runnable by ID)
    # from the selected platform manifest ID (not a local image reference).
    result["platform_id"] = result["id"]
    identity = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", reference],
                              capture_output=True, text=True, timeout=30)
    if identity.returncode:
        raise RuntimeError(f"cannot resolve runnable image ID: {reference}")
    result["id"] = identity.stdout.strip()
    result["labels"] = result.get("labels") or {}
    actual = f"{result['os']}/{result['architecture']}"
    if actual != platform_name():
        raise RuntimeError(f"image {reference} is {actual}; requested {platform_name()}")
    return result


def versioned_tag(reference: str, fingerprint: str) -> str:
    return reference + "-" + fingerprint[:20]


def image_matches(reference: str, fingerprint: str) -> bool:
    try:
        return image_identity(reference)["labels"].get(FINGERPRINT_LABEL) == fingerprint
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
        return False


def source_identity(case_dir: Path) -> dict:
    result = {"case_files": case_manifest(case_dir)}
    for key, args in (("git_commit", ["rev-parse", "HEAD"]),
                      ("git_status", ["status", "--porcelain"])):
        proc = subprocess.run(["git", "-C", str(case_dir), *args], capture_output=True,
                              text=True, timeout=15)
        result[key] = proc.stdout.strip() if proc.returncode == 0 else None
    harness = Path(__file__).resolve().parent
    result["runner_files"] = runtime_manifest(harness)
    result["judge_files"] = runtime_manifest(harness.parent / "coding_bench_harbor")
    return result
