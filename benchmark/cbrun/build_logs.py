"""Keep build diagnostics with the owning trial, including failed builds."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import subprocess
from .state import utc_now

_log: ContextVar[Path | None] = ContextVar("cbrun_build_log", default=None)


@contextmanager
def capture_builds(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{utc_now()} image provisioning\n")
    token = _log.set(path)
    try:
        yield
    finally:
        _log.reset(token)


def run_build(argv: list[str], *, timeout: float):
    path = _log.get()
    if path is None:
        return subprocess.run(argv, timeout=timeout)
    with path.open("a", encoding="utf-8") as stream:
        # Do not echo argument values that may contain registry credentials.
        stream.write(f"{utc_now()} {' '.join(argv[:2])}\n")
        stream.flush()
        return subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
