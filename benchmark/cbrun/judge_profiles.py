"""Explicit judge-only capabilities; solve containers retain standard isolation."""
from __future__ import annotations

import json
from pathlib import Path
from .docker_env import Container


def start_judge_container(image: str, *, case_dir: Path | None = None, gpus: str | None = None) -> Container:
    profile = "standard"
    if case_dir is not None:
        manifest = json.loads((Path(case_dir) / "source/manifest.json").read_text())
        profile = manifest["runner"].get("judge_profile", "standard")
    if profile == "standard":
        return Container.start(image, gpus=gpus, network="none")
    if profile != "cow":
        raise ValueError(f"unknown judge profile: {profile}")
    # A private filesystem in this container's mount namespace. No host paths,
    # physical block devices, credentials or Docker socket are mounted.
    container = Container.start(image, gpus=gpus, network="none", cap_add=("SYS_ADMIN",),
                                device_cgroup_rules=("b 7:* rwm", "c 10:237 rwm"))
    container.cleanup_command = "umount /cbrun-cow 2>/dev/null || true"
    try:
        setup = container.exec("""set -euo pipefail
command -v mkfs.btrfs >/dev/null
command -v setpriv >/dev/null
test -e /dev/loop-control || mknod /dev/loop-control c 10 237
for n in $(seq 0 255); do test -e /dev/loop$n || mknod /dev/loop$n b 7 "$n"; done
truncate -s 512M /tmp/cbrun-cow.img
mkfs.btrfs -q -f /tmp/cbrun-cow.img
mkdir -p /cbrun-cow
mount -o loop /tmp/cbrun-cow.img /cbrun-cow
chmod 1777 /cbrun-cow
rm -f /dev/loop-control /dev/loop[0-9]*
""", timeout_sec=60)
        if setup.exit_code:
            raise RuntimeError("CoW judge profile could not initialize its private filesystem: " + setup.tail)
        # Candidate and hidden-test commands cannot mount filesystems or create
        # device nodes. Only runner-owned initialization/cleanup uses those caps.
        container.exec_prefix = ["setpriv", "--bounding-set=-sys_admin,-mknod",
                                 "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs"]
        probe = container.exec("""python3 -I - <<'PY'
import fcntl,os,stat,tempfile
with tempfile.TemporaryDirectory(dir='/cbrun-cow') as p:
    with open(p+'/a','w+b') as a,open(p+'/b','w+b') as b:
        a.write(b'copy-on-write readiness'); a.flush()
        fcntl.ioctl(b.fileno(),0x40049409,a.fileno())
        b.seek(0); assert b.read()==b'copy-on-write readiness'
try:
    os.mknod('/tmp/cbrun-device-check',stat.S_IFBLK|0o600,os.makedev(7,0))
except PermissionError:
    pass
else:
    os.unlink('/tmp/cbrun-device-check')
    raise AssertionError('test processes must not create device nodes')
print('copy-on-write filesystem verified')
PY""", timeout_sec=15)
        if probe.exit_code:
            raise RuntimeError("CoW judge readiness failed: " + probe.tail)
        return container
    except BaseException:
        container.remove()
        raise
