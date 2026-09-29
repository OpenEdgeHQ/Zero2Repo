# feature: F07
"""Feature-local helpers for batch compress and expand.

Derived destination names implement the PRD append/strip rules so tests
can compute expected paths. Destinations themselves must be written by
the product. These helpers are not a substitute public entry.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Sequence

from F01_helpers import (
    BATCH_ARCHIVE_SUFFIX,
    _vorbis_bytes,
    derived_batch_archive,
    require_ok,
    run_product,
    token,
    unique_name,
)
from F02_helpers import replace_vorbis_comment
from F03_helpers import shared_remainder_lacking_in, strip_paths_and_sizes
from F04_helpers import archive_bytes, expand_to
from _harness import HarnessError, RunResult, Workspace


def derived_batch_expand(input_rel: str) -> str:
    """Unix/Linux batch-expand destination for *input_rel* (PRD trailing rule)."""
    if not isinstance(input_rel, str):
        raise HarnessError(f"derived_batch_expand expected str, got {type(input_rel)!r}")
    if input_rel.endswith(BATCH_ARCHIVE_SUFFIX):
        return input_rel[: -len(BATCH_ARCHIVE_SUFFIX)]
    return f"{input_rel}.out"


def place_non_ogg_sized(ws: Workspace, n: int, rel: str | None = None) -> str:
    """Write exactly *n* non-Ogg bytes. *n* < 1 or a write failure raises."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise HarnessError(f"place_non_ogg_sized expected int n, got {type(n)!r}")
    if n < 1:
        raise HarnessError(f"place_non_ogg_sized n must be >= 1, got {n}")
    if rel is None:
        dest_rel = f"{unique_name('notogg')}.bin"
    else:
        if not isinstance(rel, str):
            raise HarnessError(f"rel expected str, got {type(rel)!r}")
        dest_rel = rel
    data = secrets.token_bytes(n)
    if data.startswith(b"OggS"):
        data = b"X" + data[1:]
    if len(data) != n:
        raise HarnessError(f"non-Ogg payload length {len(data)} != {n}")
    if data.startswith(b"OggS"):
        raise HarnessError("non-Ogg payload still starts with OggS")
    ws.write(dest_rel, data)
    written = ws.read_bytes(dest_rel)
    if written != data:
        raise HarnessError(f"write of {dest_rel!r} did not persist the payload")
    return dest_rel


def place_vorbis_in_subdir(ws: Workspace, which: str) -> str:
    """Write a sealed Vorbis fixture under a unique subdirectory."""
    data = _vorbis_bytes(which)
    dirname = unique_name("dir")
    ws.mkdir(dirname)
    name = unique_name("src")
    rel = f"{dirname}/{name}"
    ws.write(rel, data)
    written = ws.read_bytes(rel)
    if written != data:
        raise HarnessError(f"write of subdir Vorbis {rel!r} failed")
    return rel


def place_runtime_vorbis(ws: Workspace) -> str:
    """Vorbis whose comment packet carries a runtime token (bytes not public)."""
    data = _vorbis_bytes("a")
    mark = token().encode("ascii")
    # The constructed comment must be strictly larger than the fixture's
    # (replace_vorbis_comment enforces that). A short token-only field is
    # not enough on the sealed short Vorbis fixtures.
    pad = secrets.token_hex(512).encode("ascii")
    variant = replace_vorbis_comment(
        data,
        vendor=b"suite-vendor-" + mark,
        fields=(b"NOTE=" + mark, b"PAD=" + pad),
    )
    if variant == data:
        raise HarnessError("runtime Vorbis comment equals the unmodified fixture")
    rel = unique_name("vorbis-rt") + ".ogg"
    ws.write(rel, variant)
    return rel


def stderr_path_index(text: str, path: str) -> int:
    """First index of *path* or its basename in *text*. Absence asserts."""
    if not isinstance(text, str):
        raise HarnessError(f"stderr_path_index expected str text, got {type(text)!r}")
    if not isinstance(path, str):
        raise HarnessError(f"stderr_path_index expected str path, got {type(path)!r}")
    name = Path(path).name
    found: list[int] = []
    if path:
        at = text.find(path)
        if at >= 0:
            found.append(at)
    if name and name != path:
        at = text.find(name)
        if at >= 0:
            found.append(at)
    assert found, (
        f"stderr does not name the caller-typed path {path!r}; stderr={text!r}"
    )
    return min(found)


def failure_leftover(text: str, paths: Sequence[str], sizes: Sequence[int]) -> str:
    """Strip paths and sizes via the sealed helper. Empty leftover is a real value."""
    if not isinstance(text, str):
        raise HarnessError(f"failure_leftover expected str, got {type(text)!r}")
    return strip_paths_and_sizes(text, paths, sizes)


def existing_sizes(ws: Workspace, rels: Sequence[str]) -> list[int]:
    """Sizes of regular files that exist. Absence is skipped; other I/O raises."""
    sizes: list[int] = []
    for rel in rels:
        if not isinstance(rel, str):
            raise HarnessError(f"existing_sizes expected str path, got {type(rel)!r}")
        found = ws.read_bytes_if_present(rel)
        if found is not None:
            sizes.append(len(found))
    return sizes


def arm_leftover(ws: Workspace, result: RunResult, paths: Sequence[str]) -> str:
    """Leftover stderr after stripping *paths* and sizes of those that exist."""
    sizes = existing_sizes(ws, paths)
    leftover = failure_leftover(result.stderr_text, paths, sizes)
    print(
        f"[F07] leftover paths={list(paths)!r} sizes={sizes!r} leftover={leftover!r}",
        flush=True,
    )
    return leftover


def batch_member_name_paths(*members: str) -> list[str]:
    """Caller paths plus derived compress and expand destinations (PRD names)."""
    paths: list[str] = []
    for rel in members:
        if not isinstance(rel, str):
            raise HarnessError(
                f"batch_member_name_paths expected str, got {type(rel)!r}"
            )
        paths.append(rel)
        paths.append(derived_batch_archive(rel))
        paths.append(derived_batch_expand(rel))
    return paths


def mixed_failure_extra_remainder(
    ws: Workspace,
    mixed: RunResult,
    success: RunResult,
    paths: Sequence[str],
) -> str:
    """Mixed-stderr lines absent from same-shape all-success, after path/size strip.

    This is the dedicated mixed-failure summary field plus per-file diagnostics
    that all-success does not write. The two count payloads are isolated by
    shared_remainder_lacking_in across mixed arms, not by leftover of the whole
    stream or by mixed-to-mixed full-text. Empty extra is a real observation.
    Type errors raise.
    """
    if not isinstance(mixed, RunResult):
        raise HarnessError(
            f"mixed_failure_extra_remainder expected RunResult mixed, "
            f"got {type(mixed)!r}"
        )
    if not isinstance(success, RunResult):
        raise HarnessError(
            f"mixed_failure_extra_remainder expected RunResult success, "
            f"got {type(success)!r}"
        )
    sizes = existing_sizes(ws, paths)
    mix_left = strip_paths_and_sizes(mixed.stderr_text, paths, sizes)
    ok_left = strip_paths_and_sizes(success.stderr_text, paths, sizes)
    ok_lines = {ln.strip() for ln in ok_left.splitlines() if ln.strip()}
    extra_lines = [
        ln.strip()
        for ln in mix_left.splitlines()
        if ln.strip() and ln.strip() not in ok_lines
    ]
    extra = "\n".join(extra_lines)
    print(
        f"[F07] mixed extra paths={list(paths)!r} extra={extra!r}",
        flush=True,
    )
    return extra


def dedicated_mixed_failure_count_payloads(
    extra_1_of_2: str,
    extra_2_of_2: str,
    extra_1_of_3: str,
) -> tuple[frozenset[str], frozenset[str]]:
    """Failed-count and attempted-count halves of the mixed-failure summary field.

    Failed-count half: tokens two 1-fail extras share that the 2-fail extra
    lacks. Attempted-count half: tokens two N=2 extras share that the N=3
    extra lacks. A numeric token is a valid payload. Empty means that half
    was silent or answered only by whole-stream leftover, leftover integers,
    mixed-versus-all-success full-text, or mixed-to-mixed full-text.
    """
    for name, value in (
        ("extra_1_of_2", extra_1_of_2),
        ("extra_2_of_2", extra_2_of_2),
        ("extra_1_of_3", extra_1_of_3),
    ):
        if not isinstance(value, str):
            raise HarnessError(
                f"dedicated_mixed_failure_count_payloads expected str "
                f"{name}, got {type(value)!r}"
            )
    failed = shared_remainder_lacking_in(extra_1_of_2, extra_1_of_3, extra_2_of_2)
    attempted = shared_remainder_lacking_in(extra_1_of_2, extra_2_of_2, extra_1_of_3)
    print(
        f"[F07] dedicated failed-count={sorted(failed)!r} "
        f"attempted-count={sorted(attempted)!r}",
        flush=True,
    )
    return failed, attempted


def scramble_or_remove(ws: Workspace, rel: str, saved: bytes) -> None:
    """Overwrite *rel* with runtime bytes different from *saved*. Equality raises."""
    if not isinstance(rel, str):
        raise HarnessError(f"scramble_or_remove expected str rel, got {type(rel)!r}")
    if not isinstance(saved, bytes):
        raise HarnessError(
            f"scramble_or_remove expected bytes saved, got {type(saved)!r}"
        )
    junk = secrets.token_bytes(max(32, len(saved) + 8))
    if junk == saved:
        raise HarnessError("runtime overwrite equalled the saved original")
    ws.write(rel, junk)
    after = ws.read_bytes(rel)
    if after == saved:
        raise HarnessError(f"after overwrite {rel!r} still equals the saved original")


def unrelated_pair(prefix_a: str, prefix_b: str) -> tuple[str, str]:
    """Two unique names, neither a substring of the other."""
    for _ in range(32):
        left = unique_name(prefix_a)
        right = unique_name(prefix_b)
        if left not in right and right not in left:
            return left, right
    raise HarnessError("could not generate mutually non-substring names")


def require_compress_member(ws: Workspace, src: str) -> str:
    """Derived compress dest exists, dest≠src, single-file expand restores *src*."""
    dest = derived_batch_archive(src)
    if not ws.path_is_file(dest):
        raise HarnessError(f"batch compress did not write a regular file at {dest}")
    src_bytes = ws.read_bytes(src)
    dest_bytes = archive_bytes(ws, dest)
    assert dest_bytes != src_bytes, (
        f"compress dest {dest!r} bytes equal the source (copy stub)"
    )
    recovered = unique_name("probe-rec")
    expand_to(ws, dest, recovered)
    rec = ws.read_bytes(recovered)
    assert rec == src_bytes, (
        f"single-file expand of {dest!r} did not restore the original bytes"
    )
    print(
        f"[F07] compress member {src!r} -> {dest!r} "
        f"src={len(src_bytes)} dest={len(dest_bytes)}",
        flush=True,
    )
    return dest


def require_expand_restored(ws: Workspace, dest: str, saved: bytes) -> None:
    """*dest* is a regular file whose bytes equal *saved*. Missing dest raises."""
    if not isinstance(saved, bytes):
        raise HarnessError(f"saved original expected bytes, got {type(saved)!r}")
    if not ws.path_is_file(dest):
        raise HarnessError(f"batch expand did not write a regular file at {dest}")
    got = ws.read_bytes(dest)
    assert got == saved, (
        f"batch expand dest {dest!r} does not match the saved original"
    )
    print(f"[F07] expand dest {dest!r} restored {len(got)} bytes", flush=True)


def prepare_batch_archive(ws: Workspace, src: str | None = None) -> tuple[str, bytes, str]:
    """Batch-compress one Vorbis input. Return (src, saved bytes, archive path)."""
    if src is None:
        src = place_runtime_vorbis(ws)
    saved = ws.read_bytes(src)
    result = run_product(ws, ["-1", "-b", "e", src])
    require_ok(result)
    arc = derived_batch_archive(src)
    if not ws.path_is_file(arc):
        raise HarnessError(f"batch compress did not write {arc}")
    return src, saved, arc
