"""Host-side judge substrates. Containers stay unprivileged.

A case declares ``judge_substrates`` on ``test_manifest.json``. cbrun prepares
each named provider on the host and bind-mounts it at
``/mnt/cb-substrate/<name>``. The judge container is not given extra
capabilities.
"""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

__all__ = [
    "CONTAINER_SUBSTRATE_ROOT",
    "COW_FSTYPES",
    "HostMount",
    "KNOWN_PROVIDERS",
    "SubstrateUnavailable",
    "ficlone_host_unsupported_reason",
    "names_from_manifest",
    "mounted_substrates",
    "supports_ficlone",
    "cow_fstype_covering",
    "helper_visible_cow_mounts",
]

CONTAINER_SUBSTRATE_ROOT = "/mnt/cb-substrate"
COW_FSTYPES = frozenset({"xfs", "btrfs", "bcachefs", "ocfs2", "btrfs.zstd"})
# Linux: _IOW(0x94, 9, int)
_FICLONE = 0x40049409


def ficlone_host_unsupported_reason() -> str | None:
    """Why this host cannot issue FICLONE, or None on a capable host.

    The ``fcntl`` ioctl interface is POSIX-only. Importing it at module load
    would make every judge and asset check crash on Windows even for cases
    that never declare a substrate, so it is resolved here, on demand.
    """
    if sys.platform != "linux":
        return f"FICLONE needs a Linux host; this host is {sys.platform}"
    try:
        import fcntl  # noqa: F401
    except ImportError:
        return "FICLONE needs the fcntl module, which this Python lacks"
    return None


class SubstrateUnavailable(Exception):
    """The requested substrate could not be prepared on this host."""

    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason
        super().__init__(f"substrate {name} unavailable: {reason}")


@dataclass(frozen=True)
class HostMount:
    host: Path
    container: str
    name: str
    cleanup: Callable[[], None] | None = None


def names_from_manifest(manifest: dict | None) -> list[str]:
    if not isinstance(manifest, dict):
        return []
    raw = manifest.get("judge_substrates") or []
    if not isinstance(raw, list):
        raise ValueError("judge_substrates must be a list of names")
    names: list[str] = []
    for item in raw:
        name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def cow_fstype_covering(path: Path, mounts_text: str | None = None) -> str | None:
    """Return the /proc/mounts CoW fstype that covers *path*, if any.

    Uses the same fstype set as case hidden-test helpers that scan
    ``/proc/mounts`` (xfs / btrfs / bcachefs / ocfs2). A Docker bind of an
    overlay or ext4 directory will not match, even if FICLONE happens to
    work on the host.
    """
    if mounts_text is None:
        try:
            mounts_text = Path("/proc/mounts").read_text(encoding="utf-8")
        except OSError:
            return None
    try:
        resolved = str(Path(path).resolve())
    except OSError:
        resolved = str(path)
    best: str | None = None
    best_len = -1
    for line in mounts_text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        mountpoint, fstype = parts[1], parts[2]
        if fstype not in COW_FSTYPES:
            continue
        if resolved == mountpoint or resolved.startswith(
            mountpoint.rstrip("/") + "/"
        ):
            if len(mountpoint) > best_len:
                best = fstype
                best_len = len(mountpoint)
    return best


def helper_visible_cow_mounts(mounts_text: str) -> list[str]:
    """Mount points a 009-style ``_existing_cow_parents`` scan would consider.

    FICLONE is not applied here; this is the /proc/mounts half of that helper.
    """
    found: list[str] = []
    seen: set[str] = set()
    for line in mounts_text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        mountpoint, fstype = parts[1], parts[2]
        if fstype not in COW_FSTYPES or mountpoint in seen:
            continue
        seen.add(mountpoint)
        found.append(mountpoint)
    return found


def supports_ficlone(directory: Path) -> bool:
    """True when *directory* can clone a regular file with FICLONE."""
    if ficlone_host_unsupported_reason() is not None:
        return False
    import fcntl

    directory = Path(directory)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if not os.access(directory, os.W_OK):
            return False
    except OSError:
        return False
    src = directory / ".cb-ficlone-src"
    dst = directory / ".cb-ficlone-dst"
    try:
        src.write_bytes(b"x" * 4096)
        dst.write_bytes(b"")
        with open(dst, "rb+") as out, open(src, "rb") as inp:
            fcntl.ioctl(out.fileno(), _FICLONE, inp.fileno())
        return True
    except OSError:
        return False
    finally:
        src.unlink(missing_ok=True)
        dst.unlink(missing_ok=True)


def _existing_ficlone_dir() -> Path | None:
    """Host directory that both FICLONE and a helper-visible CoW fstype."""
    for raw in (os.environ.get("CBRUN_COW_SCRATCH"), "/var/tmp", "/tmp"):
        if not raw:
            continue
        path = Path(raw)
        if cow_fstype_covering(path) is None:
            continue
        if supports_ficlone(path):
            return path
    return None


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True)


def _host_nsenter(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run *argv* in the host mount namespace via a privileged helper container.

    The judge container itself stays unprivileged. Docker-group users who
    cannot ``mount`` directly still get a host-visible xfs loop this way.
    """
    helper = os.environ.get("CBRUN_HOST_HELPER_IMAGE", "ubuntu:24.04")
    return _run(
        [
            "docker",
            "run",
            "--rm",
            "--privileged",
            "--pid=host",
            "-v",
            "/:/host",
            "--entrypoint",
            "nsenter",
            helper,
            "--mount=/host/proc/1/ns/mnt",
            "--",
            *argv,
        ]
    )


def _loop_mount(image: Path, mountpoint: Path) -> subprocess.CompletedProcess[str]:
    direct = _run(["mount", "-o", "loop", str(image), str(mountpoint)])
    if direct.returncode == 0:
        return direct
    via = _host_nsenter(
        ["mount", "-o", "loop", str(image.resolve()), str(mountpoint.resolve())]
    )
    if via.returncode == 0:
        return via
    reason = (via.stderr or direct.stderr).strip() or "loop mount failed"
    return subprocess.CompletedProcess(via.args, via.returncode, "", reason)


def _loop_umount(mountpoint: Path) -> None:
    if _run(["umount", str(mountpoint)]).returncode == 0:
        return
    _host_nsenter(["umount", str(mountpoint.resolve())])


def _prepare_cow_fs(scratch_dir: Path) -> HostMount:
    unsupported = ficlone_host_unsupported_reason()
    if unsupported is not None:
        raise SubstrateUnavailable("cow_fs", unsupported)
    existing = _existing_ficlone_dir()
    if existing is not None:
        dest = existing / f"cb-cow-{os.getpid()}"
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError:
            dest = existing
        if cow_fstype_covering(dest) is None or not supports_ficlone(dest):
            if dest != existing:
                try:
                    dest.rmdir()
                except OSError:
                    pass
            dest = existing
            if cow_fstype_covering(dest) is None or not supports_ficlone(dest):
                raise SubstrateUnavailable("cow_fs", f"FICLONE failed at {existing}")
        return HostMount(
            host=dest,
            container=f"{CONTAINER_SUBSTRATE_ROOT}/cow_fs",
            name="cow_fs",
        )

    scratch_dir.mkdir(parents=True, exist_ok=True)
    image = scratch_dir / "cow.img"
    mountpoint = scratch_dir / "mnt"
    mountpoint.mkdir(exist_ok=True)
    made = _run(
        ["dd", "if=/dev/zero", f"of={image}", "bs=1M", "count=384", "status=none"]
    )
    if made.returncode != 0:
        raise SubstrateUnavailable("cow_fs", made.stderr.strip() or "dd failed")
    mkfs = _run(["mkfs.xfs", "-m", "reflink=1", "-f", str(image)])
    if mkfs.returncode != 0:
        raise SubstrateUnavailable(
            "cow_fs", mkfs.stderr.strip() or "mkfs.xfs failed (install xfsprogs)"
        )
    mounted = _loop_mount(image, mountpoint)
    if mounted.returncode != 0:
        raise SubstrateUnavailable(
            "cow_fs", mounted.stderr.strip() or "loop mount failed"
        )
    if _run(["chmod", "1777", str(mountpoint)]).returncode != 0:
        _host_nsenter(["chmod", "1777", str(mountpoint.resolve())])
    if not supports_ficlone(mountpoint):
        _loop_umount(mountpoint)
        raise SubstrateUnavailable("cow_fs", "mounted xfs has no FICLONE")

    def _cleanup() -> None:
        _loop_umount(mountpoint)

    return HostMount(
        host=mountpoint,
        container=f"{CONTAINER_SUBSTRATE_ROOT}/cow_fs",
        name="cow_fs",
        cleanup=_cleanup,
    )


KNOWN_PROVIDERS: dict[str, Callable[[Path], HostMount]] = {
    "cow_fs": _prepare_cow_fs,
}


@contextmanager
def mounted_substrates(
    manifest: dict | None, scratch_dir: Path | str
) -> Iterator[list[HostMount]]:
    names = names_from_manifest(manifest)
    mounts: list[HostMount] = []
    scratch = Path(scratch_dir)
    try:
        for name in names:
            prepare = KNOWN_PROVIDERS.get(name)
            if prepare is None:
                raise SubstrateUnavailable(name, f"unknown provider {name!r}")
            mounts.append(prepare(scratch / name))
        yield mounts
    finally:
        for mount in reversed(mounts):
            if mount.cleanup is not None:
                try:
                    mount.cleanup()
                except Exception:
                    pass
