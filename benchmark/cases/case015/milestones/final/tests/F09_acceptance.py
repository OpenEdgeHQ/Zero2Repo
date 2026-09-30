# feature: F09
"""Acceptance: archive dump and Ogg page listing."""

from __future__ import annotations

import secrets

from F01_helpers import (
    place_non_ogg,
    place_placeholder,
    place_vorbis,
    require_bytes_unchanged,
    require_file_access,
    require_refusal,
    require_stderr_identifies_path_failure,
    run_expect_usage_no_archive,
    run_product,
    unique_name,
)
from F02_helpers import parse_ogg_pages, place_vorbis_without_ogg_suffix
from F03_helpers import (
    dump_stdout,
    place_opus_classified,
    require_codec_mode_field,
    strip_paths_and_sizes,
)
from F04_helpers import (
    _SCALE_FILES,
    _prove_family0,
    _read_fixture,
    _vorbis_comment_variant,
    archive_bytes,
    vorbis_with_runtime_comment,
)
from F05_helpers import (
    generation_candidates_across,
    place_bytes_without_codec_suffix,
    with_generation_value,
)
from F06_helpers import concat_bitstreams
from F09_helpers import (
    dedicated_reconstruction_mismatch_field,
    dedicated_reconstruction_success_field,
    dedicated_stored_stage_field,
    lossless_compress,
    pages_stdout,
    per_page_listing_tokens,
    require_every_page_reconstructs,
    still_parseable_one_page_checksum_sibling,
)
from _harness import workspace


# ---------------------------------------------------------------------------
# A. Codec-mode field: two classified Opus kinds share; Vorbis differs
# ---------------------------------------------------------------------------


def test_dump_codec_mode_field_two_opus_share_vorbis_differs():
    with workspace() as ws:
        require_codec_mode_field(ws, "-1", what="F09 A effort 1")


# ---------------------------------------------------------------------------
# B. Stored-stage field: Vorbis effort 1 versus effort 3
# ---------------------------------------------------------------------------


def test_dump_stored_stage_field_vorbis_effort1_vs_effort3():
    with workspace() as ws:
        src_x = vorbis_with_runtime_comment(ws)
        y_bytes = _vorbis_comment_variant(_read_fixture(_SCALE_FILES[2]))
        src_y = unique_name("vorbis-y") + ".ogg"
        ws.write(src_y, y_bytes)
        assert ws.read_bytes(src_x) != y_bytes, (
            "stored-stage inputs X and Y are not distinct Vorbis files"
        )
        arc_1x = unique_name("e1-x")
        arc_1y = unique_name("e1-y")
        arc_3x = unique_name("e3-x")
        arc_3y = unique_name("e3-y")
        lossless_compress(ws, src_x, arc_1x, "-1")
        lossless_compress(ws, src_y, arc_1y, "-1")
        lossless_compress(ws, src_x, arc_3x, "-3")
        lossless_compress(ws, src_y, arc_3y, "-3")
        text_1x = dump_stdout(ws, arc_1x)
        text_1y = dump_stdout(ws, arc_1y)
        text_3x = dump_stdout(ws, arc_3x)
        text_3y = dump_stdout(ws, arc_3y)
        paths = [
            src_x,
            src_y,
            arc_1x,
            arc_1y,
            arc_3x,
            arc_3y,
            str(ws.path),
        ]
        sizes = (
            len(ws.read_bytes(src_x)),
            len(ws.read_bytes(src_y)),
            len(ws.read_bytes(arc_1x)),
            len(ws.read_bytes(arc_1y)),
            len(ws.read_bytes(arc_3x)),
            len(ws.read_bytes(arc_3y)),
        )
        stage_1 = dedicated_stored_stage_field(
            text_1x, text_1y, text_3x, paths, sizes
        )
        stage_3 = dedicated_stored_stage_field(
            text_3x, text_3y, text_1x, paths, sizes
        )
        left_1x = strip_paths_and_sizes(text_1x, paths, sizes)
        left_3x = strip_paths_and_sizes(text_3x, paths, sizes)
        print(
            f"[F09] B stage_1={sorted(stage_1)!r} stage_3={sorted(stage_3)!r} "
            f"left_1x_len={len(left_1x)} left_3x_len={len(left_3x)}",
            flush=True,
        )
        assert stage_1, (
            "On dump standard output, a dedicated stored-stage field — not "
            "the archive path, not a byte size, not a leftover that varies "
            "with the file — answers the encoding stage stored for a Vorbis "
            "archive: two effort-1 dumps share a payload that dump of an "
            "effort-3 archive of the same input lacks, independent of path "
            "and size. The payload may be a number or a hex value"
        )
        assert stage_3, (
            "On dump standard output, a dedicated stored-stage field — not "
            "the archive path, not a byte size, not a leftover that varies "
            "with the file — answers the encoding stage stored for a Vorbis "
            "archive: two effort-3 dumps share a payload that dump of an "
            "effort-1 archive of the same input lacks, independent of path "
            "and size. The payload may be a number or a hex value"
        )
        assert stage_1 != stage_3, (
            "effort 1 and effort 3 of Vorbis inputs must write distinguishable "
            "payloads of the dedicated stored-stage field, not the same token set"
        )
        assert left_1x != left_3x, (
            "dump of a Vorbis archive made at effort 1 and dump of an archive "
            "of the same input made at effort 3 must differ after path and "
            "size strip"
        )


# ---------------------------------------------------------------------------
# C. pages of valid Vorbis, no codec suffix: countable, unmodified
# ---------------------------------------------------------------------------


def test_pages_lists_valid_vorbis_countable_unmodified():
    with workspace() as ws:
        path_a = place_vorbis_without_ogg_suffix(ws, "a")
        path_b = place_vorbis_without_ogg_suffix(ws, "b")
        bytes_a = ws.read_bytes(path_a)
        bytes_b = ws.read_bytes(path_b)
        n_a = len(parse_ogg_pages(bytes_a))
        n_b = len(parse_ogg_pages(bytes_b))
        if n_a == n_b:
            chained = concat_bitstreams([bytes_a, bytes_b])
            path_n, path_m = path_a, place_bytes_without_codec_suffix(
                ws, chained, "vorbis-m"
            )
            n_pages, m_pages = n_a, len(parse_ogg_pages(chained))
        elif n_a < n_b:
            path_n, path_m = path_a, path_b
            n_pages, m_pages = n_a, n_b
        else:
            path_n, path_m = path_b, path_a
            n_pages, m_pages = n_b, n_a
        assert n_pages < m_pages, (
            f"Vorbis page-count pair is not N < M: N={n_pages} M={m_pages}"
        )
        snap_n = ws.read_bytes(path_n)
        snap_m = ws.read_bytes(path_m)
        require_every_page_reconstructs(snap_n)
        require_every_page_reconstructs(snap_m)
        text_n = pages_stdout(ws, path_n)
        text_m = pages_stdout(ws, path_m)
        require_bytes_unchanged(ws, path_n, snap_n)
        require_bytes_unchanged(ws, path_m, snap_m)
        probe = unique_name("probe")
        ws.write(probe, snap_n)
        ws.write(probe, snap_n + b"\x00")
        assert ws.read_bytes(probe) != snap_n, (
            "the outside observer did not report a one-byte write to a copy"
        )
        flip_n = still_parseable_one_page_checksum_sibling(snap_n)
        flip_m = still_parseable_one_page_checksum_sibling(snap_m)
        path_flip_n = place_bytes_without_codec_suffix(ws, flip_n, "vorbis-flip-n")
        path_flip_m = place_bytes_without_codec_suffix(ws, flip_m, "vorbis-flip-m")
        text_flip_n = pages_stdout(ws, path_flip_n)
        text_flip_m = pages_stdout(ws, path_flip_m)
        paths = [path_n, path_m, path_flip_n, path_flip_m, str(ws.path)]
        sizes = (len(snap_n), len(snap_m), len(flip_n), len(flip_m))
        left_n = strip_paths_and_sizes(text_n, paths, sizes)
        left_m = strip_paths_and_sizes(text_m, paths, sizes)
        listing_n = per_page_listing_tokens(text_n, n_pages, paths, sizes)
        listing_m = per_page_listing_tokens(text_m, m_pages, paths, sizes)
        success = dedicated_reconstruction_success_field(
            text_n,
            n_pages,
            text_m,
            m_pages,
            text_flip_n,
            text_flip_m,
            paths,
            sizes,
        )
        mismatch = dedicated_reconstruction_mismatch_field(
            text_flip_n, text_flip_m, text_n, paths, sizes
        )
        print(
            f"[F09] C pages N={n_pages} M={m_pages} "
            f"left_n={len(left_n)} left_m={len(left_m)} "
            f"listing_n={sorted(listing_n)!r} listing_m={sorted(listing_m)!r} "
            f"success={sorted(success)!r} mismatch={sorted(mismatch)!r}",
            flush=True,
        )
        assert left_n != left_m, (
            "pages of two valid Ogg Vorbis files whose page counts differ "
            "must differ on standard output after path and size strip"
        )
        assert listing_n and listing_m, (
            "pages on a valid Ogg Vorbis file lists every page: after "
            "stripping paths and per-file byte sizes, a leftover token "
            "occurs once per independently counted page"
        )
        assert success, (
            "pages of a well-formed Vorbis file writes a dedicated "
            "reconstruction-status field on each listed page whose payload "
            "is success, independent of path and size: two well-formed "
            "listings share a per-page leftover that a still-parseable "
            "sibling differing only by one page's stored RFC 3533 checksum "
            "does not share at that multiplicity"
        )
        assert mismatch, (
            "pages of a still-parseable sibling that differs only by one "
            "page's stored RFC 3533 checksum not matching the CRC computed "
            "with the checksum field treated as zero still exits 0 and that "
            "page carries the mismatch payload of the dedicated "
            "reconstruction-status field, independent of path and size"
        )
        assert success != mismatch, (
            "the dedicated reconstruction-status field has two payloads, "
            "success and mismatch, that are distinguishable from each other"
        )


# ---------------------------------------------------------------------------
# D. pages of valid family-0 Opus, no codec suffix: countable, unmodified
# ---------------------------------------------------------------------------


def test_pages_lists_valid_opus_countable_unmodified():
    with workspace() as ws:
        path_a = place_opus_classified(ws, "silk", suffix="")
        path_b = place_opus_classified(ws, "celt", suffix="")
        _prove_family0(ws.read_bytes(path_a), what="silk pages host")
        _prove_family0(ws.read_bytes(path_b), what="celt pages host")
        bytes_a = ws.read_bytes(path_a)
        bytes_b = ws.read_bytes(path_b)
        n_a = len(parse_ogg_pages(bytes_a))
        n_b = len(parse_ogg_pages(bytes_b))
        if n_a == n_b:
            chained = concat_bitstreams([bytes_a, bytes_b])
            path_n, path_m = path_a, place_bytes_without_codec_suffix(
                ws, chained, "opus-m"
            )
            n_pages, m_pages = n_a, len(parse_ogg_pages(chained))
        elif n_a < n_b:
            path_n, path_m = path_a, path_b
            n_pages, m_pages = n_a, n_b
        else:
            path_n, path_m = path_b, path_a
            n_pages, m_pages = n_b, n_a
        assert n_pages < m_pages, (
            f"Opus page-count pair is not N < M: N={n_pages} M={m_pages}"
        )
        snap_n = ws.read_bytes(path_n)
        snap_m = ws.read_bytes(path_m)
        require_every_page_reconstructs(snap_n)
        require_every_page_reconstructs(snap_m)
        text_n = pages_stdout(ws, path_n)
        text_m = pages_stdout(ws, path_m)
        require_bytes_unchanged(ws, path_n, snap_n)
        require_bytes_unchanged(ws, path_m, snap_m)
        probe = unique_name("probe")
        ws.write(probe, snap_n)
        ws.write(probe, snap_n + b"\x00")
        assert ws.read_bytes(probe) != snap_n, (
            "the outside observer did not report a one-byte write to a copy"
        )
        flip_n = still_parseable_one_page_checksum_sibling(snap_n)
        flip_m = still_parseable_one_page_checksum_sibling(snap_m)
        path_flip_n = place_bytes_without_codec_suffix(ws, flip_n, "opus-flip-n")
        path_flip_m = place_bytes_without_codec_suffix(ws, flip_m, "opus-flip-m")
        text_flip_n = pages_stdout(ws, path_flip_n)
        text_flip_m = pages_stdout(ws, path_flip_m)
        paths = [path_n, path_m, path_flip_n, path_flip_m, str(ws.path)]
        sizes = (len(snap_n), len(snap_m), len(flip_n), len(flip_m))
        left_n = strip_paths_and_sizes(text_n, paths, sizes)
        left_m = strip_paths_and_sizes(text_m, paths, sizes)
        listing_n = per_page_listing_tokens(text_n, n_pages, paths, sizes)
        listing_m = per_page_listing_tokens(text_m, m_pages, paths, sizes)
        success = dedicated_reconstruction_success_field(
            text_n,
            n_pages,
            text_m,
            m_pages,
            text_flip_n,
            text_flip_m,
            paths,
            sizes,
        )
        mismatch = dedicated_reconstruction_mismatch_field(
            text_flip_n, text_flip_m, text_n, paths, sizes
        )
        print(
            f"[F09] D pages N={n_pages} M={m_pages} "
            f"left_n={len(left_n)} left_m={len(left_m)} "
            f"listing_n={sorted(listing_n)!r} listing_m={sorted(listing_m)!r} "
            f"success={sorted(success)!r} mismatch={sorted(mismatch)!r}",
            flush=True,
        )
        assert left_n != left_m, (
            "pages of two valid Ogg Opus files whose page counts differ "
            "must differ on standard output after path and size strip"
        )
        assert listing_n and listing_m, (
            "pages on a valid Ogg Opus file lists every page: after "
            "stripping paths and per-file byte sizes, a leftover token "
            "occurs once per independently counted page"
        )
        assert success, (
            "pages of a well-formed Opus file writes a dedicated "
            "reconstruction-status field on each listed page whose payload "
            "is success, independent of path and size: two well-formed "
            "listings share a per-page leftover that a still-parseable "
            "sibling differing only by one page's stored RFC 3533 checksum "
            "does not share at that multiplicity"
        )
        assert mismatch, (
            "pages of a still-parseable sibling that differs only by one "
            "page's stored RFC 3533 checksum not matching the CRC computed "
            "with the checksum field treated as zero still exits 0 and that "
            "page carries the mismatch payload of the dedicated "
            "reconstruction-status field, independent of path and size"
        )
        assert success != mismatch, (
            "the dedicated reconstruction-status field has two payloads, "
            "success and mismatch, that are distinguishable from each other"
        )


# ---------------------------------------------------------------------------
# E. dump / pages of a missing path is a file-access error
# ---------------------------------------------------------------------------


def test_dump_and_pages_missing_path_is_file_access():
    with workspace() as ws:
        src = vorbis_with_runtime_comment(ws)
        arc = unique_name("ok-arc")
        lossless_compress(ws, src, arc, "-1")
        dump_stdout(ws, arc)
        pages_stdout(ws, src)
        missing_dump = unique_name("missing-dump")
        missing_pages = unique_name("missing-pages")
        dump_miss = run_product(ws, ["dump", missing_dump])
        require_file_access(dump_miss)
        require_stderr_identifies_path_failure(dump_miss, missing_dump)
        pages_miss = run_product(ws, ["pages", missing_pages])
        require_file_access(pages_miss)
        require_stderr_identifies_path_failure(pages_miss, missing_pages)
        print(
            f"[F09] E dump_missing exit={dump_miss.returncode} "
            f"pages_missing exit={pages_miss.returncode}",
            flush=True,
        )


# ---------------------------------------------------------------------------
# F. pages of a non-Ogg file (including an archive) is refused
# ---------------------------------------------------------------------------


def test_pages_of_non_ogg_is_refused():
    with workspace() as ws:
        src = vorbis_with_runtime_comment(ws)
        baseline = pages_stdout(ws, src)
        assert baseline, (
            "pages of a well-formed Ogg file writes a listing to standard "
            "output (live baseline: the product is not always refuse)"
        )
        arc = unique_name("arc-not-ogg")
        lossless_compress(ws, src, arc, "-1")
        of_archive = run_product(ws, ["pages", arc])
        require_refusal(of_archive)
        assert of_archive.returncode == 1, (
            "pages of an archive file (not Ogg) exits 1; "
            f"got {of_archive.returncode}; stderr={of_archive.stderr!r}"
        )
        assert of_archive.stderr, (
            "a refusal writes a diagnostic to standard error; "
            f"stdout={of_archive.stdout!r}"
        )
        non_ogg = place_non_ogg(ws)
        of_random = run_product(ws, ["pages", non_ogg])
        require_refusal(of_random)
        assert of_random.returncode == 1, (
            "pages on a file that is not Ogg is refused (exit 1); "
            f"got {of_random.returncode}; stderr={of_random.stderr!r}"
        )
        assert of_random.stderr, (
            "a refusal writes a diagnostic to standard error; "
            f"stdout={of_random.stdout!r}"
        )
        print(
            f"[F09] F pages-archive exit={of_archive.returncode} "
            f"pages-nonogg exit={of_random.returncode}",
            flush=True,
        )


# ---------------------------------------------------------------------------
# G. dump of a non-archive and of a foreign generation is refused
# ---------------------------------------------------------------------------


def test_dump_of_non_archive_and_foreign_generation_is_refused():
    with workspace() as ws:
        src_a = vorbis_with_runtime_comment(ws)
        y_bytes = _vorbis_comment_variant(_read_fixture(_SCALE_FILES[1]))
        src_b = unique_name("vorbis-b") + ".ogg"
        ws.write(src_b, y_bytes)
        arc_a = unique_name("gen-a")
        arc_b = unique_name("gen-b")
        lossless_compress(ws, src_a, arc_a, "-1")
        lossless_compress(ws, src_b, arc_b, "-1")
        dump_stdout(ws, arc_a)
        ogg = place_vorbis(ws, "a")
        of_ogg = run_product(ws, ["dump", ogg])
        require_refusal(of_ogg)
        non_ogg = place_non_ogg(ws)
        of_random = run_product(ws, ["dump", non_ogg])
        require_refusal(of_random)
        bytes_a = archive_bytes(ws, arc_a)
        bytes_b = archive_bytes(ws, arc_b)
        candidates = generation_candidates_across(ws, src_a, bytes_a, bytes_b)
        non_dest = unique_name("gen-nonarc-out")
        non_expand = run_product(ws, ["d", ogg, non_dest])
        require_refusal(non_expand)
        non_left = strip_paths_and_sizes(non_expand.stderr_text, (ogg, non_dest), ())
        matched = None
        older_run = None
        newer_run = None
        for field in candidates:
            offset, width, written, endian = field
            max_val = (1 << (8 * width)) - 1
            older_val = secrets.choice(range(0, written))
            newer_val = secrets.choice(range(written + 1, max_val + 1))
            assert older_val < written < newer_val, (
                f"relative order failed: {older_val} < {written} < {newer_val}"
            )
            older_bytes = with_generation_value(bytes_a, field, older_val)
            newer_bytes = with_generation_value(bytes_a, field, newer_val)
            older_path = unique_name("gen-older")
            newer_path = unique_name("gen-newer")
            ws.write(older_path, older_bytes)
            ws.write(newer_path, newer_bytes)
            generation_refused = True
            for path in (older_path, newer_path):
                out = unique_name("gen-exp-out")
                expanded = run_product(ws, ["d", path, out])
                left = strip_paths_and_sizes(expanded.stderr_text, (path, out), ())
                if expanded.returncode != 1 or left.split() == non_left.split():
                    generation_refused = False
            if not generation_refused:
                continue
            older_try = run_product(ws, ["dump", older_path])
            newer_try = run_product(ws, ["dump", newer_path])
            print(
                f"[F09] G field off={offset} width={width} endian={endian} "
                f"written={written} older={older_val} newer={newer_val} "
                f"older_exit={older_try.returncode} "
                f"newer_exit={newer_try.returncode}",
                flush=True,
            )
            if older_try.returncode != 1 or newer_try.returncode != 1:
                continue
            matched = field
            older_run, newer_run = older_try, newer_try
            break
        assert matched is not None, (
            "no generation-identifier candidate (constant across inputs, "
            "codecs, and efforts; expand of its older and newer rewrites "
            "refused distinguishably from a non-archive), when rewritten to "
            "a strictly smaller and a strictly larger value, was refused by dump"
        )
        require_refusal(older_run)
        require_refusal(newer_run)
        print(
            f"[F09] G dump-ogg exit={of_ogg.returncode} "
            f"dump-nonogg exit={of_random.returncode} "
            f"dump-older exit={older_run.returncode} "
            f"dump-newer exit={newer_run.returncode}",
            flush=True,
        )


# ---------------------------------------------------------------------------
# H. Extra operand beyond one path is a usage error; no new archive
# ---------------------------------------------------------------------------


def test_dump_and_pages_extra_operand_is_usage():
    with workspace() as ws:
        src = vorbis_with_runtime_comment(ws)
        arc = unique_name("ok-arc")
        lossless_compress(ws, src, arc, "-1")
        dump_stdout(ws, arc)
        pages_stdout(ws, src)
        extra = place_placeholder(ws)
        dump_extra = run_expect_usage_no_archive(ws, ["dump", arc, extra])
        pages_extra = run_expect_usage_no_archive(ws, ["pages", src, extra])
        print(
            f"[F09] H dump-extra exit={dump_extra.returncode} "
            f"pages-extra exit={pages_extra.returncode}",
            flush=True,
        )
