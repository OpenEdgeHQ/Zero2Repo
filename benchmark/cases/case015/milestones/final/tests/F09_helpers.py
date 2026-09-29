# feature: F09
"""Feature-local helpers for archive dump and Ogg page listing.

These helpers drive the public ``dump`` / ``pages`` verbs and read
standard output. They are not a substitute public entry. A dedicated
stored-stage field is the leftover token set two effort-1 dumps share
and an effort-3 dump lacks, after paths and byte sizes are stripped.
A leftover token that occurs once per independently counted page is
the listing-completeness observer. A dedicated reconstruction-status
field is the leftover that two well-formed listings share on every
listed page and a one-page checksum-flipped sibling does not share at
that multiplicity (success), and that two such siblings share and a
well-formed listing lacks (mismatch). Numbers and hex-like runs are
kept. An empty set is a real observation (the field was silent), not a
lookup failure.
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from F01_helpers import require_ok, require_stdout_text, run_product, unique_name
from F02_helpers import (
    OGG_CAPTURE,
    OGG_HDRMIN,
    OggPage,
    ogg_crc_page,
    parse_ogg_pages,
)
from F03_helpers import shared_remainder_lacking_in, strip_paths_and_sizes
from F04_helpers import (
    archive_bytes,
    compress_to,
    expand_to,
    require_lossless_archive,
)
from F05_helpers import corrupt_stored_page_checksum, prove_checksum_mismatch
from _harness import HarnessError, Workspace


def lossless_compress(ws: Workspace, src: str, dest: str, *effort_tokens: str) -> bytes:
    """Compress *src* to *dest*, expand, and require dest≠src and recovered==src."""
    src_bytes = ws.read_bytes(src)
    compress_to(ws, src, dest, *effort_tokens)
    dest_bytes = archive_bytes(ws, dest)
    recovered = unique_name("rec")
    expand_to(ws, dest, recovered)
    rec_bytes = ws.read_bytes(recovered)
    require_lossless_archive(dest_bytes, rec_bytes, src_bytes, what=dest)
    assert dest_bytes != src_bytes, (
        f"{dest}: compress destination bytes equal the source (copy stub)"
    )
    assert rec_bytes == src_bytes, (
        f"{dest}: expand did not restore the original bytes"
    )
    return dest_bytes


def pages_stdout(ws: Workspace, path: str) -> str:
    """Run ``pages`` on *path*. Non-zero exit or empty stdout raises/asserts."""
    result = run_product(ws, ["pages", path])
    require_ok(result)
    text = require_stdout_text(result)
    assert result.returncode == 0, (
        f"pages expected exit 0, got {result.returncode}; "
        f"stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    assert text, f"pages expected non-empty stdout; stderr={result.stderr!r}"
    return text


def dedicated_stored_stage_field(
    e1_a: str,
    e1_b: str,
    e3: str,
    paths: Sequence[str],
    sizes: Sequence[int],
) -> frozenset[str]:
    """Dedicated dump-stdout stored-stage payloads shared by two effort-1 dumps.

    After stripping archive paths and per-file byte sizes, two effort-1
    Vorbis dumps share a dedicated stored-stage field payload that an
    effort-3 dump lacks. A number or a hex value is a valid payload.
    Exact wording is the implementer's. Empty means the field was silent
    or answered only by path or size. Type errors raise.
    """
    for name, value in (("e1_a", e1_a), ("e1_b", e1_b), ("e3", e3)):
        if not isinstance(value, str):
            raise HarnessError(f"{name} expected str, got {type(value)!r}")
    left_a = strip_paths_and_sizes(e1_a, paths, sizes)
    left_b = strip_paths_and_sizes(e1_b, paths, sizes)
    left_3 = strip_paths_and_sizes(e3, paths, sizes)
    return shared_remainder_lacking_in(left_a, left_b, left_3)


def reconstructed_from_parsed_header_and_body(page: OggPage) -> bytes:
    """RFC 3533 serialize of one page's parsed header fields and body."""
    if not isinstance(page, OggPage):
        raise HarnessError(
            f"page expected OggPage, got {type(page)!r}"
        )
    laces = bytes(page.laces)
    body = bytes(page.body)
    header_len = OGG_HDRMIN + len(laces)
    out = bytearray(header_len + len(body))
    out[0:4] = OGG_CAPTURE
    out[4] = 0
    out[5] = int(page.header_type) & 0xFF
    out[6:14] = int(page.granule).to_bytes(8, "little")
    out[14:18] = int(page.serial).to_bytes(4, "little")
    out[18:22] = int(page.sequence).to_bytes(4, "little")
    out[26] = len(laces)
    out[OGG_HDRMIN : header_len] = laces
    out[header_len:] = body
    crc = ogg_crc_page(bytes(out))
    out[22:26] = crc.to_bytes(4, "little")
    return bytes(out)


def require_every_page_reconstructs(data: bytes) -> None:
    """Every stored page equals reconstruction from its parsed header and body."""
    if not isinstance(data, (bytes, bytearray)):
        raise HarnessError(
            f"require_every_page_reconstructs expected bytes, got {type(data)!r}"
        )
    pages = parse_ogg_pages(bytes(data))
    for page in pages:
        rebuilt = reconstructed_from_parsed_header_and_body(page)
        if rebuilt != page.raw:
            raise HarnessError(
                f"page at {page.offset} does not reconstruct from parsed "
                "header and body"
            )


def per_page_listing_tokens(
    text: str,
    n_pages: int,
    paths: Sequence[str],
    sizes: Sequence[int],
) -> frozenset[str]:
    """Leftover tokens that occur once per independently counted page.

    After stripping paths and per-file byte sizes, a leftover token whose
    multiplicity equals the independent RFC 3533 page count is the
    listing-completeness observer: the listing is per-page. Exact wording
    is the implementer's. Empty means the listing did not mark every page.
    Type errors raise. Page counts that are not positive integers raise.
    """
    if not isinstance(text, str):
        raise HarnessError(f"text expected str, got {type(text)!r}")
    if isinstance(n_pages, bool) or not isinstance(n_pages, int) or n_pages < 1:
        raise HarnessError(
            f"n_pages expected a positive int, got {n_pages!r}"
        )
    leftover = strip_paths_and_sizes(text, paths, sizes)
    return frozenset(
        tok for tok, count in Counter(leftover.split()).items() if count == n_pages
    )


def still_parseable_one_page_checksum_sibling(data: bytes) -> bytes:
    """Same-codec sibling that differs only by one page's stored RFC 3533 checksum.

    The stored checksum of page 0 is flipped so it no longer matches the
    CRC computed with that field treated as zero. The file stays a
    parseable Ogg sequence with the same page count. Type errors raise.
    A lookup that cannot classify the pages raises; it does not return
    the original bytes.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise HarnessError(
            "still_parseable_one_page_checksum_sibling expected bytes, "
            f"got {type(data)!r}"
        )
    host = bytes(data)
    out = corrupt_stored_page_checksum(host, 0)
    prove_checksum_mismatch(out, 0)
    return out


def dedicated_reconstruction_success_field(
    well_a: str,
    n_a: int,
    well_b: str,
    n_b: int,
    sibling_a: str,
    sibling_b: str,
    paths: Sequence[str],
    sizes: Sequence[int],
) -> frozenset[str]:
    """Dedicated pages-stdout reconstruction-status success payload.

    After stripping paths and per-file byte sizes, a leftover token that
    occurs once per independently counted page on two well-formed listings
    and does not occur once per page on either one-page checksum-flipped
    sibling is the success payload of the dedicated reconstruction-status
    field. Exact wording is the implementer's. Empty means the field was
    silent, answered only by path or size, or was not carried on every
    listed well-formed page. Type errors raise.
    """
    for name, value in (
        ("well_a", well_a),
        ("well_b", well_b),
        ("sibling_a", sibling_a),
        ("sibling_b", sibling_b),
    ):
        if not isinstance(value, str):
            raise HarnessError(f"{name} expected str, got {type(value)!r}")
    per_a = per_page_listing_tokens(well_a, n_a, paths, sizes)
    per_b = per_page_listing_tokens(well_b, n_b, paths, sizes)
    per_sa = per_page_listing_tokens(sibling_a, n_a, paths, sizes)
    per_sb = per_page_listing_tokens(sibling_b, n_b, paths, sizes)
    return (per_a & per_b) - per_sa - per_sb


def dedicated_reconstruction_mismatch_field(
    sibling_a: str,
    sibling_b: str,
    well: str,
    paths: Sequence[str],
    sizes: Sequence[int],
) -> frozenset[str]:
    """Dedicated pages-stdout reconstruction-status mismatch payload.

    After stripping paths and per-file byte sizes, two one-page
    checksum-flipped siblings share a leftover that a well-formed listing
    lacks. That remainder is the mismatch payload of the same dedicated
    reconstruction-status field. Exact wording is the implementer's.
    Empty means the field was silent or answered only by path or size.
    Type errors raise.
    """
    for name, value in (
        ("sibling_a", sibling_a),
        ("sibling_b", sibling_b),
        ("well", well),
    ):
        if not isinstance(value, str):
            raise HarnessError(f"{name} expected str, got {type(value)!r}")
    left_a = strip_paths_and_sizes(sibling_a, paths, sizes)
    left_b = strip_paths_and_sizes(sibling_b, paths, sizes)
    left_w = strip_paths_and_sizes(well, paths, sizes)
    return shared_remainder_lacking_in(left_a, left_b, left_w)
