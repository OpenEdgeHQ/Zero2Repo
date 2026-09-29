# feature: F02
"""Observation helpers for twenty-format extraction, size caps, and the window.

New names for this slice only. Sealed F01 helpers are imported, not copied.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from _harness import HarnessError, RunResult, invoke, invoke_hook, workspace
from F01_helpers import (
    switch_from_usage,
    _is_usage_synopsis_line,
    _strip_usage_flags,
    _usage_line_flags,
    metrics_from_report,
    parse_structured_mapping,
    strip_error_covariates,
    strip_paths_from_stderr,
    unicode_len,
    usage_from_help,
)

PLAIN_EXTS: tuple[str, ...] = (
    ".md",
    ".mdx",
    ".markdown",
    ".txt",
    ".text",
    ".rst",
    ".tex",
    ".org",
    ".adoc",
)
ZIP_EXTS: tuple[str, ...] = (
    ".docx",
    ".docm",
    ".pptx",
    ".pptm",
    ".xlsx",
    ".xlsm",
    ".odt",
    ".odp",
    ".ods",
    ".epub",
)
NOTEBOOK_EXT = ".ipynb"

PLAIN_CAP = 512 * 1024
ARCHIVE_CAP = 4 * 1024 * 1024

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_ODF_T = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_ODF_O = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"

_CLEANUP_FLAG: str | None = None


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def runtime_token(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(5)}"


def _runtime_token(prefix: str) -> str:
    return runtime_token(prefix)


def slop_extract_body() -> str:
    """English slop that contains “delve” and “game-changer”, with runtime filler.

    Under 120 words it carries three or more score-moving families that L108
    names as constructable fires (AI vocabulary; “it's worth noting that”;
    “stands as a testament”), so the L103 floor of 45 puts it at 40 or more.
    """
    stamp = _runtime_token("batch")
    n = 40 + secrets.randbelow(80)
    return (
        "In today's fast-paced digital landscape, it is crucial to delve into the "
        f"multifaceted tapestry of pivotal solutions across {n} workshops. "
        f"This comprehensive guide will showcase a robust, seamless framework "
        f"that empowers teams to unlock their full potential in {stamp}. "
        "It is not just a tool, it is a game-changer. "
        "It's worth noting that this guide stands as a testament to the craft."
    )


def slop_extract_twin() -> str:
    stamp = _runtime_token("twin")
    n = 40 + secrets.randbelow(80)
    return (
        "In this shifting digital landscape, it is crucial to delve into the "
        f"multifaceted tapestry of pivotal ideas across {n} studios. "
        f"This field guide will showcase a robust, seamless path "
        f"that empowers groups to unlock their full potential in {stamp}. "
        "It is not just a service, it is a game-changer. "
        "It's worth noting that this path stands as a testament to the trade."
    )


def stone_bridge_body() -> str:
    year = 1900 + secrets.randbelow(50)
    miles = 2 + secrets.randbelow(6)
    return (
        f"The bridge carried coal until {year + 58}. Its six arches were built from "
        f"stone quarried {miles} miles upstream, and the mortar has been repointed "
        f"twice, once in {year} and again after the flood. Nobody has found the "
        "original drawings. What survives is a contractor's invoice and a "
        "photograph of the opening, taken from the far bank."
    )


def write_plain(
    ws,
    relpath: str,
    text: str | bytes,
    *,
    encoding: str = "utf-8",
) -> Path:
    if isinstance(text, bytes):
        return ws.write(relpath, text)
    return ws.write(relpath, text.encode(encoding))


def _zip_write(path: Path, members: Sequence[tuple[str, str | bytes]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, payload in members:
            zf.writestr(name, payload)
    return path


def write_docx(ws, relpath: str, text: str) -> Path:
    body = f"<w:p><w:r><w:t>{_xml(text)}</w:t></w:r></w:p>"
    xml = (
        f'<?xml version="1.0"?><w:document xmlns:w="{_W}">'
        f"<w:body>{body}</w:body></w:document>"
    )
    return _zip_write(
        ws.resolve(relpath),
        (
            ("[Content_Types].xml", '<?xml version="1.0"?><Types/>'),
            ("word/document.xml", xml),
        ),
    )


def write_docm(ws, relpath: str, text: str) -> Path:
    return write_docx(ws, relpath, text)


def write_pptx(ws, relpath: str, text: str) -> Path:
    return write_pptx_slides(ws, relpath, (("slide1.xml", text),))


def write_pptx_slides(
    ws,
    relpath: str,
    slides: Sequence[tuple[str, str]],
    *,
    later_numbered_first: bool = False,
) -> Path:
    ordered = list(slides)
    if later_numbered_first:
        ordered = list(reversed(list(slides)))
    members: list[tuple[str, str | bytes]] = [
        ("[Content_Types].xml", '<?xml version="1.0"?><Types/>'),
    ]
    for name, payload in ordered:
        xml = (
            f'<?xml version="1.0"?><sld xmlns:a="{_A}">'
            f"<a:p><a:r><a:t>{_xml(payload)}</a:t></a:r></a:p></sld>"
        )
        members.append((f"ppt/slides/{name}", xml))
    return _zip_write(ws.resolve(relpath), members)


def write_pptm(ws, relpath: str, text: str) -> Path:
    return write_pptx(ws, relpath, text)


def write_xlsx(
    ws,
    relpath: str,
    text: str | None = None,
    *,
    shared_strings: Sequence[str] | None = None,
    sheets: Sequence[tuple[str, str]] | None = None,
    sheet_xml: str | None = None,
    later_numbered_first: bool = False,
) -> Path:
    members: list[tuple[str, str | bytes]] = [
        ("[Content_Types].xml", '<?xml version="1.0"?><Types/>'),
    ]
    if shared_strings is not None:
        items = "".join(f"<si><t>{_xml(s)}</t></si>" for s in shared_strings)
        members.append(
            (
                "xl/sharedStrings.xml",
                f'<?xml version="1.0"?><sst xmlns="{_P}">{items}</sst>',
            )
        )
    elif text is not None:
        members.append(
            (
                "xl/sharedStrings.xml",
                f'<?xml version="1.0"?><sst xmlns="{_P}">'
                f"<si><t>{_xml(text)}</t></si></sst>",
            )
        )
        sheet_xml = (
            f'<?xml version="1.0"?><worksheet xmlns="{_P}"><sheetData>'
            f'<row><c t="s"><v>0</v></c></row>'
            f"</sheetData></worksheet>"
        )
    if sheets is not None:
        ordered = list(sheets)
        if later_numbered_first:
            ordered = list(reversed(list(sheets)))
        for name, xml in ordered:
            members.append((f"xl/worksheets/{name}", xml))
    elif sheet_xml is not None:
        members.append(("xl/worksheets/sheet1.xml", sheet_xml))
    return _zip_write(ws.resolve(relpath), members)


def write_xlsm(
    ws,
    relpath: str,
    text: str | None = None,
    **kwargs: Any,
) -> Path:
    return write_xlsx(ws, relpath, text, **kwargs)


def write_odt(ws, relpath: str, xml_body: str | None = None, *, text: str | None = None) -> Path:
    if xml_body is None:
        if text is None:
            raise HarnessError("write_odt needs xml_body or text")
        xml_body = f"<text:p>{_xml(text)}</text:p>"
    content = (
        '<?xml version="1.0"?>'
        f'<office:document-content xmlns:office="{_ODF_O}" xmlns:text="{_ODF_T}">'
        f"<office:body><office:text>{xml_body}</office:text></office:body>"
        "</office:document-content>"
    )
    return _zip_write(
        ws.resolve(relpath),
        (("mimetype", "application/vnd.oasis.opendocument.text"), ("content.xml", content)),
    )


def write_odp(ws, relpath: str, xml_body: str | None = None, *, text: str | None = None) -> Path:
    return write_odt(ws, relpath, xml_body, text=text)


def write_ods(ws, relpath: str, xml_body: str | None = None, *, text: str | None = None) -> Path:
    return write_odt(ws, relpath, xml_body, text=text)


def write_epub(
    ws,
    relpath: str,
    body: str | None = None,
    *,
    chapters: Sequence[tuple[str, str]] | None = None,
    later_numbered_first: bool = False,
) -> Path:
    members: list[tuple[str, str | bytes]] = []
    if chapters is not None:
        ordered = list(chapters)
        if later_numbered_first:
            ordered = list(reversed(list(chapters)))
        for name, inner in ordered:
            members.append(
                (
                    name,
                    '<?xml version="1.0"?>'
                    '<html xmlns="http://www.w3.org/1999/xhtml">'
                    f"<body>{inner}</body></html>",
                )
            )
    else:
        if body is None:
            raise HarnessError("write_epub needs body or chapters")
        members.append(
            (
                "chapter.xhtml",
                '<?xml version="1.0"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml">'
                f"<body><p>{_xml(body)}</p></body></html>",
            )
        )
    return _zip_write(ws.resolve(relpath), members)


def write_notebook(
    ws,
    relpath: str,
    *,
    markdown: str | Sequence[str] | None = None,
    code_source: str | Sequence[str] | None = None,
    output_text: str | None = None,
    cells: Sequence[Mapping[str, Any]] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> Path:
    if cells is not None:
        nb_cells: list[Any] = list(cells)
    else:
        nb_cells = []
        if markdown is not None:
            nb_cells.append(
                {"cell_type": "markdown", "source": markdown, "metadata": {}}
            )
        if code_source is not None:
            cell: dict[str, Any] = {
                "cell_type": "code",
                "source": code_source,
                "metadata": {},
            }
            if output_text is not None:
                cell["outputs"] = [
                    {
                        "output_type": "stream",
                        "name": "stdout",
                        "text": output_text,
                    }
                ]
            else:
                cell["outputs"] = []
            nb_cells.append(cell)
    obj: dict[str, Any] = {
        "cells": nb_cells,
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2,
    }
    if extra:
        obj.update(extra)
    return ws.write(relpath, json.dumps(obj))


def write_zip_slop(ws, relpath: str, text: str) -> Path:
    ext = Path(relpath).suffix.lower()
    writers = {
        ".docx": write_docx,
        ".docm": write_docm,
        ".pptx": write_pptx,
        ".pptm": write_pptm,
        ".xlsx": write_xlsx,
        ".xlsm": write_xlsm,
        ".odt": lambda w, r, t: write_odt(w, r, text=t),
        ".odp": lambda w, r, t: write_odp(w, r, text=t),
        ".ods": lambda w, r, t: write_ods(w, r, text=t),
        ".epub": write_epub,
    }
    writer = writers.get(ext)
    if writer is None:
        raise HarnessError(f"no zip writer for extension {ext!r}")
    return writer(ws, relpath, text)


def _talks_clean_or_scrub(text: str) -> bool:
    low = text.lower()
    return "clean" in low or "scrub" in low


def cleanup_flag_from_usage(usage: str) -> str:
    """Discover the cleanup switch from usage (L170 / L177).

    Association is a usage line that talks about clean/scrub, not a
    required ``--clean`` spelling. Aliases on one usage line are one switch.
    """
    return switch_from_usage(usage, _talks_clean_or_scrub, "cleanup / scrub")


def _cleanup_flag() -> str:
    global _CLEANUP_FLAG
    if _CLEANUP_FLAG is None:
        _CLEANUP_FLAG = cleanup_flag_from_usage(usage_from_help())
        print(f"[F02] cleanup switch from usage: {_CLEANUP_FLAG!r}", flush=True)
    return _CLEANUP_FLAG


def _stdout_is_report(text: str) -> bool:
    try:
        obj = parse_structured_mapping(text, source="cleanup stdout")
    except HarnessError:
        return False
    try:
        metrics_from_report(obj)
    except HarnessError:
        return False
    return True


def extract_via_cleanup(ws, relpath: str) -> str:
    """Observe extracted plain text via the cleanup switch (L170, L177).

    Success status; stdout is text, not a structured report. Non-success
    or report-shaped stdout raises.
    """
    flag = _cleanup_flag()
    dest = ws.resolve(relpath)
    result = ws.invoke([flag, str(dest)])
    if result.returncode != 0:
        raise HarnessError(
            f"cleanup extract failed: exit={result.returncode} "
            f"stderr={result.stderr_text!r} stdout={result.stdout_text[:500]!r}"
        )
    text = result.stdout_text
    if _stdout_is_report(text):
        raise HarnessError(
            "cleanup printed a structured report instead of extracted text; "
            f"stdout={text[:500]!r}"
        )
    print(
        f"[F02] cleanup extract path={relpath!r} chars={unicode_len(text)}",
        flush=True,
    )
    return text


def assert_extract_has_words(text: str, *words: str) -> None:
    missing = [w for w in words if w not in text]
    assert not missing, f"extract is missing {missing!r}; excerpt={text[:400]!r}"


def assert_no_markup(text: str) -> None:
    assert "<" not in text, f"extract leaked markup: excerpt={text[:400]!r}"


def tokens_in_relative_order(text: str, first: str, second: str) -> None:
    i1 = text.find(first)
    i2 = text.find(second)
    assert i1 != -1, f"first token {first!r} missing; excerpt={text[:400]!r}"
    assert i2 != -1, f"second token {second!r} missing; excerpt={text[:400]!r}"
    assert i1 < i2, (
        f"expected {first!r} before {second!r}; "
        f"indexes {i1} and {i2}; excerpt={text[:400]!r}"
    )


def pad_file_to_size(path: str | Path, n: int) -> Path:
    """Grow on-disk size without changing extractable prose.

    Zip archives get an extra stored member. Plain text and notebooks
    get trailing bytes that the extractors do not treat as extra prose
    (spaces after a JSON object; trailing spaces after a ZIP EOCD are
    not members; plain text padding sits past the named body as
    trailing whitespace that does not add distinctive words).
    """
    dest = Path(path)
    try:
        size = dest.stat().st_size
    except OSError as exc:
        raise HarnessError(f"cannot stat {dest} to pad: {exc}") from exc
    if size > n:
        raise HarnessError(f"{dest} is {size} bytes, larger than pad target {n}")
    if size == n:
        return dest
    extra = n - size
    suffix = dest.suffix.lower()
    if suffix in ZIP_EXTS:
        _pad_zip_exact(dest, n)
        return dest
    with dest.open("ab") as fh:
        fh.write(b" " * extra)
    got = dest.stat().st_size
    if got != n:
        raise HarnessError(f"padded {dest} to {got}, wanted {n}")
    return dest


def _pad_zip_exact(path: Path, n: int) -> None:
    """Rebuild a zip so on-disk size is exactly *n* via a stored pad member."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            kept = [
                (info, zf.read(info.filename))
                for info in zf.infolist()
                if not info.filename.startswith("padding/")
            ]
    except zipfile.BadZipFile as exc:
        raise HarnessError(f"cannot rebuild zip {path}: {exc}") from exc
    empty = _zip_bytes_with_pad(kept, 0)
    overhead = len(empty)
    if overhead > n:
        raise HarnessError(
            f"zip {path} without padding is {overhead} bytes, larger than {n}"
        )
    blob = _zip_bytes_with_pad(kept, n - overhead)
    if len(blob) != n:
        raise HarnessError(
            f"stored pad is not linear: overhead={overhead} "
            f"got={len(blob)} wanted={n}"
        )
    path.write_bytes(blob)
    if path.stat().st_size != n:
        raise HarnessError(
            f"zip pad wrote {path.stat().st_size} bytes, wanted {n}"
        )


def _zip_bytes_with_pad(
    kept: Sequence[tuple[zipfile.ZipInfo, bytes]], pad_len: int
) -> bytes:
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for info, data in kept:
            zf.writestr(info, data)
        zf.writestr(
            "padding/blob.bin",
            b"\x00" * pad_len,
            compress_type=zipfile.ZIP_STORED,
        )
    return buf.getvalue()


def _hook_strings(result: RunResult) -> list[str]:
    if result.returncode != 0:
        raise HarnessError(
            f"plugin hook failed: exit={result.returncode} "
            f"stderr={result.stderr_text!r} stdout={result.stdout_text[:500]!r}"
        )
    text = result.stdout_text
    if text == "":
        return []
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            f"hook stdout is not JSON: {exc}; text={text[:500]!r}"
        ) from exc
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(obj)
    return found


def plugin_prompt(ws, prompt: str) -> tuple[RunResult, str]:
    """Fire the prompt-submit hook with a slash-command prompt.

    Walks string values in the structured stdout. Non-success on this
    hook is unexpected (hooks exit successfully).
    """
    result = ws.invoke_hook(
        "prompt-submit",
        payload={"prompt": prompt},
    )
    strings = _hook_strings(result)
    blob = "\n".join(strings)
    print(
        f"[F02] prompt {prompt[:80]!r} exit={result.returncode} "
        f"n_strings={len(strings)} blob_len={len(blob)}",
        flush=True,
    )
    return result, blob


def check_file(ws, relpath: str) -> tuple[RunResult, str]:
    dest = ws.resolve(relpath)
    return plugin_prompt(ws, "/prosecheck check " + str(dest))


def show_session(ws) -> tuple[RunResult, str]:
    """Read the session ledger through the public show command (L241, L248)."""
    return plugin_prompt(ws, "/prosecheck show")


def guard_write(ws, relpath: str) -> tuple[RunResult, str]:
    dest = ws.resolve(relpath)
    result = ws.invoke_hook(
        "post-tool-use",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(dest),
                "content": dest.read_text(encoding="utf-8", errors="replace")
                if dest.suffix.lower() not in ZIP_EXTS
                else "document",
            },
            "cwd": str(ws.path),
        },
    )
    strings = _hook_strings(result)
    blob = "\n".join(strings)
    print(
        f"[F02] guard write {relpath!r} exit={result.returncode} "
        f"n_strings={len(strings)} blob_len={len(blob)}",
        flush=True,
    )
    return result, blob


def _ints_0_100(text: str) -> list[int]:
    """0–100 integers a caller reads as numbers.

    Digits that end a word (``python3``, ``utf8``, ``x14``) are part of that
    word, not a free-standing integer.
    """
    found: list[int] = []
    for match in re.finditer(r"(?<![\dA-Za-z_])(\d{1,3})(?!\d)", text):
        value = int(match.group(1))
        if 0 <= value <= 100:
            found.append(value)
    return found


def readable_scores_0_100(text: str) -> list[int]:
    """0–100 integers a caller can read. Empty means none were present."""
    return list(dict.fromkeys(_ints_0_100(text)))


def score_in_check_reply(text: str, *, expected: int | None = None) -> int:
    """Locate a 0–100 score a caller can read. Do not require /100 or a field name.

    When *expected* is given (the detector score of the same file), that
    integer must appear among the readable 0–100 values. Hit counts and a
    scale of 100 may also be present; they are not a substitute for the
    detector score.
    """
    if not str(text).strip():
        raise HarnessError("check reply is empty; no 0-100 score to read")
    uniq = readable_scores_0_100(text)
    if not uniq:
        raise HarnessError(
            f"check reply has no 0-100 integer a caller can read; text={text[:400]!r}"
        )
    if expected is not None:
        if expected not in uniq:
            raise HarnessError(
                f"check reply 0-100 integers {uniq} do not include detector "
                f"score {expected}; text={text[:400]!r}"
            )
        return expected
    if len(uniq) == 1:
        return uniq[0]
    if 100 in uniq and len(uniq) == 2:
        other = [n for n in uniq if n != 100]
        return other[0]
    raise HarnessError(
        "check reply has several 0-100 integers; pass expected=detector score "
        f"to classify: {uniq!r}; text={text[:400]!r}"
    )


def strip_size_and_paths(text: str, *paths: str, sizes: Sequence[int] = ()) -> str:
    out = text
    for path in paths:
        if not path:
            continue
        out = out.replace(path, "")
        out = out.replace(os.path.basename(path), "")
    for size in sizes:
        out = re.sub(rf"(?<!\d){size}(?!\d)", "", out)
    return re.sub(r"\s+", " ", out).strip()


def empty_input_kind(record: str, *paths: str) -> str:
    """Identifying empty-input kind after path covariates (L115, L150–L152).

    Empty-extracted-prose arms share empty standard input's kind. That kind
    is not a required phrase. Extra strings such as a file path are not the
    kind and are not a mismatch. Do not compare unstripped raw records.
    """
    tokens: list[str] = []
    for path in paths:
        if not path:
            continue
        for token in (path, str(path).replace("\\", "/"), os.path.basename(path)):
            if token and token not in tokens:
                tokens.append(token)
    return strip_error_covariates(
        strip_paths_from_stderr(record, *tokens), *tokens
    )


def kilobyte_figure(cap_bytes: int) -> int:
    """Named on-disk cap expressed in kilobytes (512 KB, 4 MB → 4096 KB)."""
    if cap_bytes < 1024 or cap_bytes % 1024 != 0:
        raise HarnessError(
            f"cap {cap_bytes} is not a whole number of kilobytes"
        )
    return cap_bytes // 1024


def standalone_int_present(text: str, value: int) -> bool:
    return re.search(rf"(?<!\d){value}(?!\d)", str(text)) is not None


def require_binary_ledger_record(blob: str, basename: str) -> None:
    """L77 / L150 / L265: show records the file and it was not re-scored.

    The ledger holds the base name. A binary row is not a scored 0–100
    row and not a skip-for-size kilobyte report. Do not require the
    letters “binary” or this checkout’s sentence.
    """
    if not str(blob).strip():
        raise HarnessError("show reply is empty; ledger was not read")
    if basename not in blob:
        raise HarnessError(
            f"show does not record {basename!r} on the session ledger; "
            f"text={blob[:400]!r}"
        )
    scores = readable_scores_0_100(blob)
    if scores:
        raise HarnessError(
            f"ledger row for {basename!r} still carried a 0-100 score "
            f"{scores}; text={blob[:400]!r}"
        )
    kb = kilobyte_figure(PLAIN_CAP)
    if standalone_int_present(blob, kb):
        raise HarnessError(
            f"ledger row names the {kb} kilobyte cap; that is skip-for-size, "
            f"not binary; text={blob[:400]!r}"
        )
    stripped = strip_size_and_paths(blob, basename)
    if not stripped:
        raise HarnessError(
            "after stripping the base name, show has no remaining marker "
            f"that the file was not re-scored; text={blob[:400]!r}"
        )
    print(
        f"[F02] ledger records {basename!r} without a 0-100 score "
        f"(not skip-for-size)",
        flush=True,
    )


def require_over_cap_kilobyte_report(
    blob: str,
    *,
    cap_bytes: int,
    unlike: str | None = None,
    absent_score: int | None = None,
) -> None:
    """L241 / L271: over-cap is reported as over that cap, in kilobytes.

    The kilobyte figure of the named cap must appear (512 for plain text,
    4096 for the 4 MB archive/notebook cap). Do not require the letters
    “over” or “KB”. A generic cannot-read / not-a-file skip is not this
    report: pass that skip as *unlike* so the kilobyte figure must be
    present here and absent there.

    When *absent_score* is the detector 0–100 score of that same oversize
    file, that integer must not appear as a readable 0–100 value. Other
    0–100 digits (for example 4 from a report that names 4 MB alongside
    4096 KB) are not forbidden. When *absent_score* is omitted, a 0–100
    integer is still refused — the 512 KB plain-text figure does not
    collide with that range.
    """
    if not str(blob).strip():
        raise HarnessError("over-cap reply is empty")
    kb = kilobyte_figure(cap_bytes)
    # Contract: the 4 MB cap is named in kilobytes as 4000 or 4096, or both.
    figures = (4000, 4096) if kb == 4096 else (kb,)
    if not any(standalone_int_present(blob, figure) for figure in figures):
        raise HarnessError(
            f"over-cap reply does not report the {kb} kilobyte cap "
            f"(as one of {figures}); text={blob[:400]!r}"
        )
    scores = readable_scores_0_100(blob)
    if absent_score is not None:
        if not 0 <= absent_score <= 100:
            raise HarnessError(
                f"absent_score {absent_score} is not a 0-100 detector score"
            )
        if absent_score in scores:
            raise HarnessError(
                "over-cap reply still carried that file's detector "
                f"score {absent_score}; text={blob[:400]!r}"
            )
    elif scores:
        raise HarnessError(
            f"over-cap reply printed a 0-100 score {scores}; text={blob[:400]!r}"
        )
    if unlike is not None:
        if not str(unlike).strip():
            raise HarnessError(
                "cannot-read / not-a-file contrast reply is empty"
            )
        if standalone_int_present(unlike, kb):
            raise HarnessError(
                "cannot-read / not-a-file reply also names the kilobyte cap, "
                f"so over-cap is not a distinct class; unlike={unlike[:400]!r}"
            )
    print(
        f"[F02] over-cap report names {kb} KB "
        f"(absent_score={absent_score!r})",
        flush=True,
    )


def window_body(n: int) -> str:
    """Exactly *n* characters of extractable padding with no leading/trailing space."""
    if n < 1:
        raise HarnessError("window body length must be positive")
    return ("bridge" * (n // 6 + 2))[:n]


def spreadsheet_sheet_xml(
    *,
    shared_indices: Sequence[str] = (),
    inline: Sequence[str] = (),
    string_typed: Sequence[str] = (),
    formula_cache: Sequence[tuple[str, str]] = (),
    extra_cells: str = "",
) -> str:
    cells: list[str] = []
    for index in shared_indices:
        cells.append(f'<c t="s"><v>{_xml(index)}</v></c>')
    for token in inline:
        cells.append(f'<c t="inlineStr"><is><t>{_xml(token)}</t></is></c>')
    for token in string_typed:
        cells.append(f'<c t="str"><v>{_xml(token)}</v></c>')
    for formula, cached in formula_cache:
        cells.append(
            f'<c t="str"><f>{_xml(formula)}</f><v>{_xml(cached)}</v></c>'
        )
    row = "<row>" + "".join(cells) + extra_cells + "</row>"
    return (
        f'<?xml version="1.0"?><worksheet xmlns="{_P}">'
        f"<sheetData>{row}</sheetData></worksheet>"
    )
