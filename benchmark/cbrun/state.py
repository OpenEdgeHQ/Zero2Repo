"""Content identities and atomic run records shared by builds and trials."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
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


def host_arch() -> str:
    """Normalize ``uname -m`` to the arch token used by ``platform_name()``."""
    import platform as py_platform

    machine = (os.environ.get("CBRUN_HOST_ARCH") or py_platform.machine() or "").lower()
    if machine in {"x86_64", "amd64"}:
        return "amd64"
    if machine in {"aarch64", "arm64"}:
        return "arm64"
    return machine or "unknown"


def is_emulated(target: str | None = None) -> bool:
    chosen = (target or platform_name()).rsplit("/", 1)[-1]
    return bool(chosen) and chosen != host_arch()


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_manifest(root: Path) -> dict[str, str]:
    """Hash regular files; record links without following them outside the tree."""
    root = Path(root)
    result: dict[str, str] = {}
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
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
            result[key] = hasher.hexdigest()
    return result


def atomic_json(path: Path, value: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def image_identity(reference: str) -> dict:
    template = (
        '{"id":{{json .Id}},"os":{{json .Os}},'
        '"architecture":{{json .Architecture}},'
        '"digests":{{json .RepoDigests}},"labels":{{json (index .Config "Labels")}},'
        '"layers":{{json .RootFS.Layers}}}'
    )
    argv = [
        "docker", "image", "inspect", "--platform", platform_name(),
        "--format", template, reference,
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    if proc.returncode and ("unknown flag" in proc.stderr or "requires API" in proc.stderr):
        proc = subprocess.run(argv[:3] + argv[5:], capture_output=True, text=True, timeout=30)
    if proc.returncode:
        raise RuntimeError(f"cannot inspect image {reference}: {proc.stderr.strip()}")
    result = json.loads(proc.stdout)
    identity = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", reference],
        capture_output=True, text=True, timeout=30,
    )
    if identity.returncode:
        raise RuntimeError(f"cannot resolve runnable image ID: {reference}")
    result["id"] = identity.stdout.strip()
    result["labels"] = result.get("labels") or {}
    return result


def image_matches(reference: str, fingerprint: str) -> bool:
    try:
        return image_identity(reference)["labels"].get(FINGERPRINT_LABEL) == fingerprint
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError):
        return False


def source_identity(case_dir: Path) -> dict:
    case_dir = Path(case_dir)
    result: dict = {
        "case_files": {
            name: file_manifest(case_dir / name)
            for name in ("public", "source", "milestones/final")
        }
    }
    for key, args in (
        ("git_commit", ["rev-parse", "HEAD"]),
        ("git_status", ["status", "--porcelain"]),
    ):
        proc = subprocess.run(
            ["git", "-C", str(case_dir), *args],
            capture_output=True, text=True, timeout=15,
        )
        result[key] = proc.stdout.strip() if proc.returncode == 0 else None
    return result
