# feature: F01
"""Feature-local helpers for command invocation, verbs, help, version, and exit status."""

from __future__ import annotations

import os
import re
import secrets
import stat
from pathlib import Path
from typing import Mapping, Sequence

from _harness import (
    MEMCAP_ENV,
    SIMD_ENV,
    HarnessError,
    RunResult,
    Workspace,
    files_identical,
    path_is_file,
    read_bytes,
    read_bytes_if_present,
    same_existing_file,
    token as _harness_token,
    workspace,
)

PRODUCT_NAME = "oggrepack"

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
_VORBIS_FILES = {
    "a": _FIXTURE_DIR / "vorbis_a.ogg",
    "b": _FIXTURE_DIR / "vorbis_b.ogg",
}
_OPUS_FILE = _FIXTURE_DIR / "opus_a.opus"

_SPLIT_TOKENS = re.compile(r"[\s|,]+")
_SIDE_PUNCT = "()[]{}<>\"'`"
# One effort-range pair on a line: -1, then later -9. Separator form is open.
_RANGE_PAIR = re.compile(r"(?<![\d])-1(?!\d).{0,80}?(?<![\d])-9(?!\d)")
_EFFORT_NINE = re.compile(r"(?<![\d])-9(?!\d)")
_YEAR_OR_RANGE = re.compile(r"^\d{4}(?:-\d{4})?$")
_COPYRIGHT_MARK = re.compile(r"\(C\)|\u00a9", re.IGNORECASE)
# License/warranty covariates — detected by those marks, not by line length.
_LICENSE_MARK = re.compile(
    r"warranty|\bgpl\b|free software|redistribute",
    re.IGNORECASE,
)
# PRD: on Unix/Linux, batch compress names the archive by appending `.orp`.
BATCH_ARCHIVE_SUFFIX = ".orp"

REQUIRED_HELP_NAMES = (
    "e",
    "d",
    "dump",
    "pages",
    "batch",
    "jobs",
    "progress",
    "progress-lines",
    "no-mmap",
    "0",
    "1",
    "2",
    "3",
    "4",
)

_KNOWN_SHORT = frozenset("hvbpj123456789")
_LEGAL_SIMD = frozenset({"scalar", "sse2", "avx2"})


def token(nbytes: int = 6) -> str:
    """Fresh lowercase hex token for runtime-unique fixtures.

    Downstream suites import this name. The byte-count default matches the
    shared harness. Does not contact the product.
    """
    return _harness_token(nbytes)


def unique_name(prefix: str) -> str:
    """Return a runtime-unique relative name. Does not create a file."""
    return f"{prefix}-{token()}"


def run_product(
    ws: Workspace,
    args: Sequence[str],
    env_updates: Mapping[str, str | None] | None = None,
) -> RunResult:
    """Invoke the product in *ws*. A non-zero exit is a result, not an exception."""
    result = ws.invoke(args, env_updates=env_updates)
    print(
        f"[F01] argv={list(args)!r} exit={result.returncode} "
        f"stdout_len={len(result.stdout)} stderr_len={len(result.stderr)}",
        flush=True,
    )
    return result


def require_status(result: RunResult, code: int, *, stderr_required: bool) -> None:
    """Assert *result* has *code*. When required, stderr must be non-empty."""
    assert result.returncode == code, (
        f"expected exit {code}, got {result.returncode}; "
        f"stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    if stderr_required:
        assert result.stderr, (
            f"expected non-empty stderr for exit {code}; stdout={result.stdout!r}"
        )


def require_ok(result: RunResult) -> None:
    require_status(result, 0, stderr_required=False)


def require_refusal(result: RunResult) -> None:
    require_status(result, 1, stderr_required=True)


def require_usage(result: RunResult) -> None:
    require_status(result, 2, stderr_required=True)


def require_file_access(result: RunResult) -> None:
    require_status(result, 3, stderr_required=True)


def require_stdout_text(result: RunResult) -> str:
    """Return decoded stdout. Empty stdout is an assertion failure, not a sentinel."""
    text = result.stdout_text
    assert text, f"expected non-empty stdout; stderr={result.stderr!r}"
    return text


def cli_tokens(text: str) -> set[str]:
    """Split *text* on whitespace, `|`, and `,`; keep hyphenated option names.

    Surrounding bracket punctuation is stripped. A token that begins with `--`
    also contributes its option stem (leading dashes removed, text after `=`
    dropped). Split failure raises rather than returning an empty set that
    could pass for "names are absent".
    """
    if not isinstance(text, str):
        raise HarnessError(f"cli_tokens expected str, got {type(text)!r}")
    pieces: set[str] = set()
    for raw in _SPLIT_TOKENS.split(text):
        piece = raw.strip().strip(_SIDE_PUNCT)
        if not piece:
            continue
        pieces.add(piece)
        if piece.startswith("--"):
            stem = piece.lstrip("-")
            if "=" in stem:
                stem = stem.split("=", 1)[0]
            if stem:
                pieces.add(stem)
    return pieces


def help_has_required_names(text: str) -> None:
    """Assert help stdout names the verbs, option stems, and status-class digits."""
    tokens = cli_tokens(text)
    missing = [name for name in REQUIRED_HELP_NAMES if name not in tokens]
    assert not missing, (
        f"help stdout missing required whole tokens {missing}; "
        f"have={sorted(tokens)}"
    )


def _strip_effort_range_pairs(text: str) -> str:
    """Remove ``-1``…``-9`` range pairs per line. A leftover ``-9`` is the default.

    The characters between the endpoints are not pinned: a usage summary may
    write the range with dots, dashes, or a word. A lone ``-9`` that is not
    the second half of such a pair is left in place.
    """
    if not isinstance(text, str):
        raise HarnessError(f"usage text expected str, got {type(text)!r}")
    return "".join(
        _RANGE_PAIR.sub(" ", line) for line in text.splitlines(keepends=True)
    )


def require_help_usage(text: str) -> None:
    """Assert help names usage elements, including that default effort is -9.

    Already-cleared arms: four verbs, effort endpoints ``-1`` and ``-9``,
    option stems, and the five status-class digits. Default effort is a
    second naming of the option ``-9`` after each line's range pair is
    removed. No language word is required.
    """
    help_has_required_names(text)
    for mark in ("-1", "-9"):
        assert mark in text, f"help stdout does not name effort option {mark!r}"
    remainder = _strip_effort_range_pairs(text)
    assert _EFFORT_NINE.search(remainder), (
        "help stdout does not name that the default effort is -9"
    )


def workspace_regular_files(ws: Workspace) -> frozenset[str]:
    """Relative POSIX paths of regular files under the workspace.

    Walk or stat failure raises. An empty set means a successful listing of
    no regular files — never a disguised I/O failure.
    """
    root = ws.path.resolve()
    found: set[str] = set()
    try:
        for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
            for name in filenames:
                path = Path(dirpath) / name
                try:
                    info = path.lstat()
                except OSError as exc:
                    raise HarnessError(f"cannot stat {path}: {exc}") from exc
                if stat.S_ISREG(info.st_mode):
                    found.add(path.relative_to(root).as_posix())
    except HarnessError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot walk workspace {root}: {exc}") from exc
    return frozenset(found)


def named_archive_files(ws: Workspace) -> frozenset[str]:
    """Regular files whose names use the PRD batch-archive suffix ``.orp``."""
    return frozenset(
        rel
        for rel in workspace_regular_files(ws)
        if rel.endswith(BATCH_ARCHIVE_SUFFIX)
    )


def derived_batch_archive(input_rel: str) -> str:
    """Return the Unix/Linux batch compress destination for *input_rel*."""
    return f"{input_rel}{BATCH_ARCHIVE_SUFFIX}"


def require_no_new_archives(before: frozenset[str], after: frozenset[str]) -> None:
    """Assert no new PRD-named archive files appeared."""
    added = after - before
    assert not added, f"archive written after usage error: {sorted(added)}"


def run_expect_usage(
    ws: Workspace,
    args: Sequence[str],
    env_updates: Mapping[str, str | None] | None = None,
) -> RunResult:
    """Run *args* and require a usage error (exit 2 and non-empty stderr)."""
    result = run_product(ws, args, env_updates=env_updates)
    require_usage(result)
    return result


def run_expect_usage_no_archive(
    ws: Workspace,
    args: Sequence[str],
    env_updates: Mapping[str, str | None] | None = None,
) -> RunResult:
    """Usage error with no new PRD-named archive file in the workspace."""
    before = named_archive_files(ws)
    result = run_expect_usage(ws, args, env_updates=env_updates)
    require_no_new_archives(before, named_archive_files(ws))
    return result


def _vorbis_bytes(which: str) -> bytes:
    try:
        path = _VORBIS_FILES[which]
    except KeyError as exc:
        raise HarnessError(f"unknown Vorbis fixture id {which!r}") from exc
    if not path.is_file():
        raise HarnessError(f"suite fixture missing: {path}")
    try:
        return read_bytes(path)
    except FileNotFoundError as exc:
        raise HarnessError(f"suite fixture missing: {path}") from exc


def place_vorbis(ws: Workspace, which: str) -> str:
    """Copy a suite-owned short Ogg Vorbis file to a unique workspace path."""
    data = _vorbis_bytes(which)
    other = "b" if which == "a" else "a"
    other_data = _vorbis_bytes(other)
    if data == other_data:
        raise HarnessError("suite Vorbis fixtures must differ in bytes")
    rel = f"{unique_name('vorbis-' + which)}.ogg"
    ws.write(rel, data)
    return rel


def _opus_bytes() -> bytes:
    path = _OPUS_FILE
    if not path.is_file():
        raise HarnessError(f"suite fixture missing: {path}")
    try:
        return read_bytes(path)
    except FileNotFoundError as exc:
        raise HarnessError(f"suite fixture missing: {path}") from exc


def place_opus(ws: Workspace) -> str:
    """Copy a suite-owned short Ogg Opus file to a unique workspace path."""
    data = _opus_bytes()
    if not data.startswith(b"OggS"):
        raise HarnessError("suite Opus fixture is not an Ogg bitstream")
    rel = f"{unique_name('opus')}.opus"
    ws.write(rel, data)
    return rel


def place_non_ogg(ws: Workspace) -> str:
    """Write a runtime-random non-Ogg regular file and return its relative path."""
    rel = f"{unique_name('notogg')}.bin"
    data = secrets.token_bytes(64)
    if data.startswith(b"OggS"):
        data = b"X" + data[1:]
    ws.write(rel, data)
    return rel


def place_placeholder(ws: Workspace) -> str:
    """Write a small existing regular file used only as a path operand."""
    rel = unique_name("hold")
    ws.write(rel, secrets.token_bytes(16))
    return rel


def unknown_verb() -> str:
    """Runtime token that is not a published verb."""
    while True:
        word = token()
        if word not in {"e", "d", "dump", "pages"}:
            return word


def unknown_long_option() -> str:
    """Runtime unknown long option (``--`` plus a fresh token)."""
    return f"--{token()}"


def unknown_short_option() -> str:
    """Runtime unknown short option, excluding published shorts and ``-0``…``-9``."""
    letters = [c for c in "abcdefghijklmnopqrstuvwxyz" if c not in _KNOWN_SHORT]
    if not letters:
        raise HarnessError("no unused short-option letters remain")
    return f"-{secrets.choice(letters)}"


def jobs_trailing_value() -> str:
    """``--jobs`` value: a digit prefix plus runtime letters (not a bare integer).

    ``token()`` is lowercase hex and can be all digits. A digits-only value is
    a legal positive jobs count (PRD: no sign and no trailing text), so the
    trailing portion must include a letter.
    """
    letters = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(4))
    value = f"1{letters}"
    if value.isdigit():
        raise HarnessError(
            f"jobs trailing value collapsed to a bare integer: {value!r}"
        )
    return value


def malformed_memcap_runtime() -> str:
    """Non-empty value that is not a non-negative integer."""
    return f"{token()[:4]}q"


def invalid_simd_token() -> str:
    """Runtime mixer-kernel token outside the published legal set."""
    while True:
        word = token()
        if word not in _LEGAL_SIMD:
            return word


def require_path_absent(ws: Workspace, relpath: str) -> None:
    """Assert *relpath* is classified absent. Other I/O failures raise."""
    found = ws.read_bytes_if_present(relpath)
    assert found is None, f"path {relpath!r} exists after a usage or access failure"


def require_bytes_unchanged(ws: Workspace, relpath: str, before: bytes) -> None:
    after = ws.read_bytes(relpath)
    assert after == before, f"bytes of {relpath!r} changed"


def mixer_kernel_names(text: str) -> set[str]:
    """PRD-named mixer kernels that appear as whole tokens in *text*."""
    return cli_tokens(text) & _LEGAL_SIMD


def _build_host_facts() -> tuple[str, ...]:
    """Independent names of this build host. Empty facts are an observation failure."""
    try:
        info = os.uname()
    except OSError as exc:
        raise HarnessError(f"cannot observe the build host: {exc}") from exc
    facts: list[str] = []
    for raw in (info.sysname, info.nodename, info.machine):
        piece = str(raw or "").strip()
        if len(piece) >= 3:
            facts.append(piece)
    if not facts:
        raise HarnessError("cannot observe the build host: uname fields empty")
    return tuple(facts)


def _token_names_host(tok: str, host_facts: tuple[str, ...]) -> bool:
    low = tok.lower()
    for fact in host_facts:
        fl = fact.lower()
        if low == fl or fl in low:
            return True
    return False


def _is_release_identifier(tok: str, host_facts: tuple[str, ...]) -> bool:
    """True when *tok* can name a version. Dotted numeric form is not required."""
    if tok in {PRODUCT_NAME} | _LEGAL_SIMD:
        return False
    if tok in {f"-{i}" for i in range(1, 10)} or tok in set("01234"):
        return False
    if _YEAR_OR_RANGE.fullmatch(tok):
        return False
    if _token_names_host(tok, host_facts):
        return False
    return any(ch.isdigit() for ch in tok)


def _names_a_version(tokens: set[str], host_facts: tuple[str, ...]) -> bool:
    return any(_is_release_identifier(tok, host_facts) for tok in tokens)


def _names_build_host(text: str, host_facts: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(fact.lower() in lowered for fact in host_facts)


def _line_is_copyright_covariate(line: str) -> bool:
    if _COPYRIGHT_MARK.search(line):
        return True
    for tok in cli_tokens(line):
        if _YEAR_OR_RANGE.fullmatch(tok):
            return True
    return False


def _line_is_license_covariate(line: str) -> bool:
    """True when *line* is license/warranty/copyright prose, not identity.

    Detected by those marks. Line length is not used: a sentence-form
    identity field may be long. A four-digit number is not treated as
    copyright on its own (an RFC number is not a license line).
    """
    return bool(_LICENSE_MARK.search(line) or _COPYRIGHT_MARK.search(line))


def _nonempty_lines(text: str) -> list[str]:
    """Stripped non-empty lines. Type errors raise; empty input is no lines."""
    if not isinstance(text, str):
        raise HarnessError(f"expected str, got {type(text)!r}")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _identity_kinds(line: str, host_facts: tuple[str, ...]) -> frozenset[str]:
    """Other L95 identity a line may already name: product, host, kernels."""
    kinds: set[str] = set()
    tokens = cli_tokens(line)
    if PRODUCT_NAME in tokens:
        kinds.add("product")
    if _names_build_host(line, host_facts):
        kinds.add("host")
    if mixer_kernel_names(line):
        kinds.add("kernels")
    return frozenset(kinds)


def _version_only_non_license_lines(
    version_text: str, help_text: str
) -> list[str]:
    """Version lines that are not usage, not the shared banner, not license.

    Shared product banner and duplicated usage are exact lines that also
    appear on help. License and copyright prose are detected by those
    marks, not by line length. A codec-name substring in the excluded
    regions is not kept.
    """
    help_lines = set(_nonempty_lines(help_text))
    kept: list[str] = []
    for line in _nonempty_lines(version_text):
        if line in help_lines:
            continue
        if _line_is_license_covariate(line) or _line_is_copyright_covariate(line):
            continue
        kept.append(line)
    return kept


def _strip_other_identity_covariates(
    line: str, host_facts: tuple[str, ...]
) -> str:
    """Remove product, host facts, mixer-kernel tokens, and release identifiers.

    Used only when identity is packed onto a line that already names two
    or more of those other L95 items. Does not treat a codec-name
    letter-run as the compiled-in answer, and does not pin field labels.
    """
    remainder = line
    for fact in sorted(host_facts, key=len, reverse=True):
        remainder = re.sub(re.escape(fact), " ", remainder, flags=re.IGNORECASE)
    pieces: list[str] = []
    for raw in remainder.split():
        trimmed = raw.strip().strip(_SIDE_PUNCT).rstrip(":=")
        if not trimmed:
            continue
        if trimmed == PRODUCT_NAME:
            continue
        if trimmed.lower() in {name.lower() for name in _LEGAL_SIMD}:
            continue
        if _is_release_identifier(trimmed, host_facts):
            continue
        pieces.append(trimmed)
    return " ".join(pieces)


def dedicated_compiled_in_field(
    version_text: str, help_text: str
) -> tuple[str, ...]:
    """Dedicated version-identity field for compiled-in Ogg Opus encode/decode.

    PRD L95 / L111: the field is on version stdout, not usage text, not
    the shared product banner, not license or copyright prose. Present
    and absent are payloads of that same field; this helper returns the
    version-side payloads (this recipe's binary is compiled-in). A
    codec-name substring in usage, banner, or license is not the field.

    Other named identity (product, build host, mixer kernels) is
    subtracted so host or kernel lines alone cannot stand in for the
    field. A packed line that names two or more of those items keeps
    the remainder after the strip. Empty means the field was silent.
    Observation type errors raise; they are not returned as silence.
    """
    host_facts = _build_host_facts()
    lines = _version_only_non_license_lines(version_text, help_text)
    dedicated = [line for line in lines if not _identity_kinds(line, host_facts)]
    if dedicated:
        return tuple(dedicated)
    remainders: list[str] = []
    for line in lines:
        if len(_identity_kinds(line, host_facts)) < 2:
            continue
        leftover = _strip_other_identity_covariates(line, host_facts).strip()
        if leftover:
            remainders.append(leftover)
    return tuple(remainders)


def require_compiled_in_identity_field(
    version_text: str, help_text: str
) -> tuple[str, ...]:
    """Assert version has a dedicated compiled-in field that help does not.

    Present arm: version-only payloads after stripping usage, shared
    banner, and license/copyright. Absent arm on this recipe: those
    payloads are not help lines (an observer of usage, banner, or
    license text alone cannot see the field). Does not pin a codec-name
    letter-run, a polarity-word list, or this checkout's field label.
    """
    payloads = dedicated_compiled_in_field(version_text, help_text)
    assert payloads, (
        "version identity is silent on whether Ogg Opus encode and decode "
        "are compiled in, or answers that only by a codec-name substring "
        "in usage, banner, or license text"
    )
    help_lines = set(_nonempty_lines(help_text))
    for payload in payloads:
        assert payload not in help_lines, (
            "dedicated compiled-in field is not distinguishable from help "
            "usage or the shared product banner"
        )
    return payloads


def require_version_identity(version_text: str, help_text: str) -> None:
    """Assert version stdout names version, host, compiled-in field, kernels.

    Kernel names are the PRD-fixed tokens ``scalar``, ``sse2``, and ``avx2``.
    A version is a release identifier; dotted numeric form is not required.
    The build host is this machine as observed outside the product (uname
    facts), not leftover tokens after subtracting help. Compiled-in Ogg
    Opus encode/decode is a dedicated identity field on version stdout:
    not usage, not the shared product banner, not license or copyright
    prose, and not a codec-name substring in those regions. *help_text*
    is the usage stream from the same workspace.
    """
    version_tokens = cli_tokens(version_text)
    host_facts = _build_host_facts()
    assert PRODUCT_NAME in version_tokens, (
        f"version stdout does not name the product as a whole token; "
        f"tokens={sorted(version_tokens)}"
    )
    assert _names_a_version(version_tokens, host_facts), (
        "version identity does not name a version"
    )
    assert _names_build_host(version_text, host_facts), (
        "version identity does not name the build host"
    )
    require_compiled_in_identity_field(version_text, help_text)
    kernels = mixer_kernel_names(version_text)
    assert kernels, (
        f"version stdout does not name a mixer kernel; "
        f"tokens={sorted(version_tokens)}"
    )


def require_stderr_identifies_path_failure(result: RunResult, path: str) -> None:
    """Assert stderr identifies a path-open or path-create failure.

    After stripping the named path, a remainder must remain. Does not pin
    wording, and does not require open vs create remnants to differ.
    """
    text = result.stderr_text
    assert text, f"expected non-empty stderr; stdout={result.stdout!r}"
    stripped = text.replace(path, "")
    base = Path(path).name
    if base and base != path:
        stripped = stripped.replace(base, "")
    assert stripped.strip(), (
        f"stderr does not identify that the path could not be opened or "
        f"could not be created beyond echoing the path; stderr={text!r}"
    )


__all__ = (
    "BATCH_ARCHIVE_SUFFIX",
    "MEMCAP_ENV",
    "PRODUCT_NAME",
    "REQUIRED_HELP_NAMES",
    "SIMD_ENV",
    "HarnessError",
    "cli_tokens",
    "dedicated_compiled_in_field",
    "derived_batch_archive",
    "files_identical",
    "help_has_required_names",
    "invalid_simd_token",
    "jobs_trailing_value",
    "malformed_memcap_runtime",
    "mixer_kernel_names",
    "named_archive_files",
    "path_is_file",
    "place_non_ogg",
    "place_opus",
    "place_placeholder",
    "place_vorbis",
    "read_bytes",
    "read_bytes_if_present",
    "require_bytes_unchanged",
    "require_compiled_in_identity_field",
    "require_file_access",
    "require_help_usage",
    "require_no_new_archives",
    "require_ok",
    "require_path_absent",
    "require_refusal",
    "require_status",
    "require_stderr_identifies_path_failure",
    "require_stdout_text",
    "require_usage",
    "require_version_identity",
    "run_expect_usage",
    "run_expect_usage_no_archive",
    "run_product",
    "same_existing_file",
    "token",
    "unique_name",
    "unknown_long_option",
    "unknown_short_option",
    "unknown_verb",
    "workspace",
    "workspace_regular_files",
)
