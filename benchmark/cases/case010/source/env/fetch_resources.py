"""Install the pinned, public model data needed by Lingora's offline tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import time
from urllib.request import urlopen
import zipfile


def extract(archive: Path, destination: Path, unpacked_limit: int) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if sum(m.file_size for m in members) > unpacked_limit:
            raise ValueError("archive exceeds declared unpacked size")
        for member in members:
            target = (root / member.filename).resolve()
            if not target.is_relative_to(root) or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("unsafe archive member")
        bundle.extractall(root)


def install(manifest_path: Path, destination: Path) -> None:
    manifest = json.loads(manifest_path.read_text())
    destination.mkdir(parents=True, exist_ok=True)
    for item in manifest["resources"]:
        if not item["url"].startswith("https://"):
            raise ValueError("resource URLs must use HTTPS")
        target = (destination / item["directory"]).resolve()
        if not target.is_relative_to(destination.resolve()):
            raise ValueError("resource directory escapes destination")
        with tempfile.TemporaryDirectory(prefix="cbrun-model-") as temporary:
            archive = Path(temporary) / "resource.zip"
            for attempt in range(3):
                try:
                    count = 0
                    with urlopen(item["url"], timeout=60) as response, archive.open("wb") as output:
                        while chunk := response.read(1024 * 1024):
                            count += len(chunk)
                            if count > item["size"]:
                                raise ValueError("download exceeds declared size")
                            output.write(chunk)
                    if count != item["size"] or hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
                        raise ValueError("resource checksum/size mismatch")
                    break
                except (OSError, TimeoutError):
                    if attempt == 2:
                        raise
                    time.sleep(2)
            extract(archive, target, item["unpacked_size"])
        print(f"installed verified model data: {item['id']}", flush=True)
    # Preserve source/license metadata alongside the unmodified archives' notices.
    shutil.copyfile(manifest_path, destination / "resources.json")


if __name__ == "__main__":
    install(Path(sys.argv[1]), Path(sys.argv[2]))
