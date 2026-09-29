# feature: F07
"""Observation helpers for the membundle relate command and membundle_relate tool (FP-07).

Helpers raise ``HarnessError`` when a query cannot be classified, and
``AssertionError`` when a classified observation misses a carrier the
tests require. They never return ``None`` / ``{}`` / ``""`` / ``[]`` to
mean "could not look".
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from _harness import (
    HarnessError,
    McpBatchResult,
    RunResult,
    Workspace,
    path_is_file,
    read_bytes,
    read_file,
    rpc_request,
)
from F01_helpers import (
    _ATX,
    _SETEXT_UNDER,
    combined_report,
    split_yaml_frontmatter,
)
from F03_helpers import (
    mcp_is_protocol_error,
    mcp_is_tool_error,
    mcp_payload_and_text,
    mcp_reply_for_id,
)
from F05_helpers import (
    SEED_LOG_DATE,
    _INLINE_LINK,
    _class_remainder,
    _list_item_texts,
    _whole_token_present,
    concept_file,
    concept_filename,
    generated_by_and_at,
    seed_bundle,
)
from F06_helpers import (
    SEED_GENERATED_AT,
    SEED_GENERATED_BY,
    _ISO_DATE,
    assert_extra_keys_survive,
    assert_update_absent,
)

PUBLIC_SAMPLE_SOURCE = "architecture/tooling"
PUBLIC_SAMPLE_TARGET = "architecture/layers"
PUBLIC_SAMPLE_PROSE = "implements the 5-layer architecture"

_LEVEL1_RELATED = frozenset({"Related Concepts", "Related"})

# Recipe artifact name. The binary is built in a writable copy, not the judge cwd.
_BIN_REL = Path("bin") / "membundle"
_BUILD_LOCK = threading.Lock()
_BUILD_DONE = False
_BUILT_BIN: Path | None = None
_NEVER_EXECUTED = (
    "the call was never executed; relate results are missing"
)


def _workdir_has_product_sources(root: Path) -> bool:
    """True when *root* is a product tree whose Makefile writes ``bin/membundle``."""
    makefile = root / "Makefile"
    if not makefile.is_file() or not (root / "go.mod").is_file():
        return False
    text = makefile.read_text(encoding="utf-8")
    return "bin/membundle" in text


def _stage_writable_sources(root: Path) -> Path:
    """Copy *root* to a writable directory, excluding any existing binary.

    The judge cwd may be a read-only filesystem. ``make build`` must not
    run there, and a binary already present under that cwd must not be
    reused.
    """
    stage = Path(tempfile.mkdtemp(prefix="membundle-build-"))
    shutil.copytree(
        root,
        stage,
        symlinks=True,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "bin"),
    )
    # copytree preserves a read-only source mode, including on the stage
    # root, which then rejects mkdir bin. The copy itself must be writable.
    for dirpath, _dirnames, filenames in os.walk(stage):
        os.chmod(dirpath, os.stat(dirpath).st_mode | 0o700)
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            os.chmod(path, path.stat().st_mode | 0o600)
    prebuilt = stage / _BIN_REL
    if prebuilt.is_symlink() or prebuilt.exists():
        prebuilt.unlink()
    return stage


def _run_product_build(root: Path) -> bool:
    """Run ``GOFLAGS=-buildvcs=false make build`` in a writable source copy.

    *root* is not the judge cwd. Returns True only when ``make`` exits 0.
    A non-zero exit is logged and is not the test result. ``make`` itself
    missing is not a successful build. Does not search ``PATH`` or honor
    ``PRODUCT_BIN``.
    """
    env = dict(os.environ)
    env.pop("PRODUCT_BIN", None)
    env["GOFLAGS"] = "-buildvcs=false"
    print(f"[F07] GOFLAGS=-buildvcs=false make build cwd={root}", flush=True)
    try:
        completed = subprocess.run(
            ["make", "build"],
            cwd=str(root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        print(f"[F07] make build could not start: {exc}", flush=True)
        return False
    print(f"[F07] make build exit={completed.returncode}", flush=True)
    if completed.returncode != 0:
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        print(
            f"[F07] make build stdout={stdout[-2000:]!r} "
            f"stderr={stderr[-2000:]!r}",
            flush=True,
        )
        return False
    return True


def _workdir_membundle() -> Path | None:
    """Return the ``bin/membundle`` this build just produced.

    When the pytest cwd contains the product sources, copies them to a
    writable directory and runs ``GOFLAGS=-buildvcs=false make build``
    there. Does not search ``PATH``, does not honor ``PRODUCT_BIN``, does
    not build in the judge cwd, and does not use a binary this build did
    not just produce. An empty cwd, or a build that does not produce an
    executable, returns None so the caller fails because the command
    results are missing.
    """
    global _BUILD_DONE, _BUILT_BIN
    with _BUILD_LOCK:
        if not _BUILD_DONE:
            root = Path.cwd().resolve()
            built: Path | None = None
            if _workdir_has_product_sources(root):
                stage = _stage_writable_sources(root)
                if _run_product_build(stage):
                    candidate = stage / _BIN_REL
                    resolved = candidate.resolve()
                    if (
                        candidate.is_file()
                        and os.access(candidate, os.X_OK)
                        and resolved.is_relative_to(stage.resolve())
                    ):
                        built = resolved
            _BUILT_BIN = built
            _BUILD_DONE = True
            print(f"[F07] resolved built binary={_BUILT_BIN!r}", flush=True)
        return _BUILT_BIN


def resolve_relate_binary() -> Path:
    """Single resolver for every F07 relate-command and relate-tool call.

    When the pytest cwd contains the product sources, copies those sources
    to a writable directory, runs ``GOFLAGS=-buildvcs=false make build``
    there, and returns only that ``bin/membundle``. When that executable
    is absent, fails the test. Does not return a synthetic non-zero
    result or a synthetic tool error: F07 refusal checks accept any
    non-zero exit and any tool error and would then pass on an empty
    workspace.
    """
    binary = _workdir_membundle()
    # TEST-FIX((none)): upstream Makefile:78 shows go build opens bin/membundle in the working directory and fails with "open bin/membundle: read-only file system" when that directory cannot accept the write, so relate never runs and its results are missing.
    assert binary is not None, _NEVER_EXECUTED
    return binary


def _raise_if_relate_binary_missing(binary: Path, exc: FileNotFoundError) -> NoReturn:
    """Turn a vanished workdir binary into the never-executed assertion."""
    if binary.is_file() and os.access(binary, os.X_OK):
        raise exc
    # TEST-FIX(F07): upstream _harness.py:620 shows FileNotFoundError before relate when bin/membundle is absent; Makefile:78 writes that binary only after GOFLAGS=-buildvcs=false make build.
    raise AssertionError(_NEVER_EXECUTED) from None


@dataclass(frozen=True)
class McpRelateOutcome:
    """Classified JSON-RPC reply to one membundle_relate tools/call.

    A missing reply for the requested id raises ``HarnessError`` before
    this object is built. None of the fields is a sentinel for "no reply".
    """

    batch: McpBatchResult
    reply: dict[str, Any]
    payload: Any
    report_text: str


def run_relate(
    ws: Workspace,
    source_id: str | None = None,
    target_id: str | None = None,
    bundle: str | Path | None = None,
    *,
    description: str | None = None,
    actor: str | None = None,
    structured: bool = False,
    extra_args: Sequence[str] = (),
    env_updates: dict[str, str | None] | None = None,
    cwd: str | Path | None = None,
) -> RunResult:
    """Invoke ``membundle relate`` with identities, optional bundle, and caller options."""
    args: list[str] = ["relate"]
    if source_id is not None:
        args.append(str(source_id))
    if target_id is not None:
        args.append(str(target_id))
    if bundle is not None:
        args.append(str(bundle))
    if description is not None:
        args.extend(["--desc", description])
    if actor is not None:
        args.extend(["--actor", actor])
    if structured:
        args.append("--json")
    args.extend(str(item) for item in extra_args)
    print(f"[F07] relate argv={args!r} cwd={cwd!r}", flush=True)
    binary = resolve_relate_binary()
    try:
        return ws.invoke(
            args, env_updates=env_updates, cwd=cwd, binary=binary
        )
    except FileNotFoundError as exc:
        _raise_if_relate_binary_missing(binary, exc)


def require_relate_success(result: RunResult) -> str:
    """CLI success carrier: POSIX success. Files are asserted separately."""
    report = combined_report(result)
    print(
        f"[F07] relate-success exit={result.returncode} report_len={len(report)}",
        flush=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"relate did not end successfully (exit {result.returncode}); "
            f"report={report!r}"
        )
    return report


def require_relate_failure(result: RunResult) -> str:
    """CLI failure carrier: process status is not success."""
    report = combined_report(result)
    print(
        f"[F07] relate-failure exit={result.returncode} report={report!r}",
        flush=True,
    )
    assert result.returncode != 0, (
        f"relate ended successfully when it must not; report={report!r}"
    )
    return report


def require_relate_usage_failure(
    result: RunResult,
    empty_identity_report: str,
    reserved_report: str,
    self_relate_report: str,
    missing_target_report: str,
    success_report: str,
    path_tokens: Sequence[str],
) -> str:
    """Fewer than two identities: non-success, non-empty, unlike live classes."""
    report = combined_report(result)
    print(
        f"[F07] usage-failure exit={result.returncode} report={report!r}",
        flush=True,
    )
    assert result.returncode != 0, (
        f"relate with fewer than two identities succeeded; report={report!r}"
    )
    assert report, (
        "relate with fewer than two identities produced empty combined streams"
    )
    usage_rem = _class_remainder(report, path_tokens)
    empty_rem = _class_remainder(empty_identity_report, path_tokens)
    reserved_rem = _class_remainder(reserved_report, path_tokens)
    self_rem = _class_remainder(self_relate_report, path_tokens)
    missing_rem = _class_remainder(missing_target_report, path_tokens)
    success_rem = _class_remainder(success_report, path_tokens)
    print(
        f"[F07] usage remainder={usage_rem!r} empty={empty_rem!r} "
        f"reserved={reserved_rem!r} self={self_rem!r} missing={missing_rem!r} "
        f"success={success_rem!r}",
        flush=True,
    )
    assert usage_rem != empty_rem, (
        "fewer-than-two-identities report is not distinguishable from "
        f"empty-identity after stripping paths; remainder={usage_rem!r}"
    )
    assert usage_rem != reserved_rem, (
        "fewer-than-two-identities report is not distinguishable from "
        f"reserved-index after stripping paths; remainder={usage_rem!r}"
    )
    assert usage_rem != self_rem, (
        "fewer-than-two-identities report is not distinguishable from "
        f"self-relate after stripping paths; remainder={usage_rem!r}"
    )
    assert usage_rem != missing_rem, (
        "fewer-than-two-identities report is not distinguishable from "
        f"missing-target after stripping paths; remainder={usage_rem!r}"
    )
    assert usage_rem != success_rem, (
        "fewer-than-two-identities report is not distinguishable from a live "
        f"success report after stripping paths; remainder={usage_rem!r}"
    )
    return report


def mcp_membundle_relate(
    ws: Workspace,
    arguments: Mapping[str, Any],
    *,
    request_id: int | str = 10,
    cwd: str | Path | None = None,
    env_updates: dict[str, str | None] | None = None,
) -> McpRelateOutcome:
    """One ``membundle_relate`` tools/call. A missing reply for *request_id* raises."""
    lines = [
        rpc_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "f07-suite", "version": "0"},
            },
            id=1,
        ),
        rpc_request(
            "tools/call",
            {"name": "membundle_relate", "arguments": dict(arguments)},
            id=request_id,
        ),
    ]
    print(
        f"[F07] mcp membundle_relate arguments={dict(arguments)!r} id={request_id!r}",
        flush=True,
    )
    binary = resolve_relate_binary()
    try:
        batch = ws.mcp_batch(
            lines, cwd=cwd, env_updates=env_updates, binary=binary
        )
    except FileNotFoundError as exc:
        _raise_if_relate_binary_missing(binary, exc)
    reply = mcp_reply_for_id(batch, request_id)
    payload, report_text = mcp_payload_and_text(reply)
    print(
        f"[F07] mcp reply protocol_error={mcp_is_protocol_error(reply)} "
        f"tool_error={mcp_is_tool_error(reply)} text={report_text!r}",
        flush=True,
    )
    return McpRelateOutcome(
        batch=batch, reply=reply, payload=payload, report_text=report_text
    )


def mcp_relate(
    ws: Workspace,
    source_id: str,
    target_id: str,
    *,
    description: str | None = None,
    bundle: str | Path | None = None,
    request_id: int | str = 10,
    cwd: str | Path | None = None,
    env_updates: dict[str, str | None] | None = None,
) -> McpRelateOutcome:
    """membundle_relate with required source and target and optional prose/bundle."""
    arguments: dict[str, Any] = {
        "source_id": source_id,
        "target_id": target_id,
    }
    if description is not None:
        arguments["description"] = description
    if bundle is not None:
        arguments["bundle"] = str(bundle)
    return mcp_membundle_relate(
        ws,
        arguments,
        request_id=request_id,
        cwd=cwd,
        env_updates=env_updates,
    )


def require_mcp_relate_success(outcome: McpRelateOutcome) -> str:
    """MCP success: not a tool error and not a protocol error."""
    if not outcome.batch.stdout and not outcome.batch.stderr:
        raise HarnessError("membundle_relate produced a silent empty transcript")
    if mcp_is_protocol_error(outcome.reply):
        raise AssertionError(
            f"membundle_relate returned a protocol error instead of a tool result: "
            f"{outcome.reply!r}"
        )
    if mcp_is_tool_error(outcome.reply):
        raise AssertionError(
            f"membundle_relate marked a tool error on a successful relate: "
            f"{outcome.report_text!r}"
        )
    return outcome.report_text


def require_mcp_relate_tool_error(outcome: McpRelateOutcome) -> str:
    """MCP relate without a source or target key, or MCP NUL identity (L215, L177)."""
    if not outcome.batch.stdout and not outcome.batch.stderr:
        raise HarnessError("membundle_relate produced a silent empty transcript")
    if mcp_is_protocol_error(outcome.reply):
        raise AssertionError(
            "membundle_relate rejected the call as a JSON-RPC protocol error; "
            "L215/L177 require a tool error, not a protocol error; "
            f"reply={outcome.reply!r}"
        )
    assert mcp_is_tool_error(outcome.reply), (
        "membundle_relate is not marked as a tool error; a successful tools/call "
        f"is not this class; reply={outcome.reply!r}"
    )
    return outcome.report_text


def require_mcp_relate_non_success(outcome: McpRelateOutcome) -> str:
    """MCP relate did not succeed. Tool-error vs JSON-RPC channel is not scored."""
    if not outcome.batch.stdout and not outcome.batch.stderr:
        raise HarnessError("membundle_relate produced a silent empty transcript")
    if mcp_is_protocol_error(outcome.reply) or mcp_is_tool_error(outcome.reply):
        return outcome.report_text
    raise AssertionError(
        "membundle_relate succeeded as a tools/call result when the relate must "
        f"not succeed; reply={outcome.reply!r}"
    )


def _render_relatable_markdown(
    *,
    concept_type: str,
    title: str | None,
    body: str,
    generated_by: str,
    generated_at: str,
    extra: Mapping[str, str] | None = None,
) -> str:
    lines = ["---", f"type: {concept_type}"]
    if title is None:
        pass
    elif title == "":
        lines.append('title: ""')
    else:
        lines.append(f"title: {title}")
    lines.append("generated:")
    lines.append(f"  by: {generated_by}")
    lines.append(f"  at: {generated_at}")
    if extra:
        for key, value in extra.items():
            lines.append(f"{key}: {value}")
    lines.append("---")
    body_text = body if body.endswith("\n") else body + "\n"
    return "\n".join(lines) + "\n" + body_text


def seed_relatable_pair(
    ws: Workspace,
    rel: str | Path,
    source_id: str,
    target_id: str,
    *,
    source_type: str,
    source_title: str,
    source_body: str,
    target_type: str,
    target_title: str | None,
    target_body: str,
    extra: Mapping[str, str] | None = None,
    generated_by: str = SEED_GENERATED_BY,
    generated_at: str = SEED_GENERATED_AT,
    extra_concepts: Sequence[Mapping[str, Any]] = (),
    agents: str | None = None,
) -> Path:
    """Seed a bundle plus a relatable source/target pair. Does not call the product."""
    extra_map = dict(extra) if extra is not None else {}
    if extra_map and len(extra_map) < 2:
        raise HarnessError(
            "seed extra keys must be two runtime-unique keys so preserving "
            f"only one fails; got {sorted(extra_map)!r}"
        )
    root = seed_bundle(ws, rel, agents=agents)
    source_path = concept_file(root, source_id)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        _render_relatable_markdown(
            concept_type=source_type,
            title=source_title,
            body=source_body,
            generated_by=generated_by,
            generated_at=generated_at,
            extra=extra_map or None,
        ),
        encoding="utf-8",
    )
    target_path = concept_file(root, target_id)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        _render_relatable_markdown(
            concept_type=target_type,
            title=target_title,
            body=target_body,
            generated_by=generated_by,
            generated_at=generated_at,
        ),
        encoding="utf-8",
    )
    for spec in extra_concepts:
        ident = str(spec["identity"])
        dest = concept_file(root, ident)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            _render_relatable_markdown(
                concept_type=str(spec["type"]),
                title=spec.get("title"),
                body=str(spec["body"]),
                generated_by=str(spec.get("generated_by", generated_by)),
                generated_at=str(spec.get("generated_at", generated_at)),
                extra=spec.get("extra"),
            ),
            encoding="utf-8",
        )
    print(
        f"[F07] seeded pair {rel} source={source_id!r} target={target_id!r} "
        f"extras={len(extra_concepts)}",
        flush=True,
    )
    return root


def write_relatable_concept(
    bundle: str | Path,
    identity: str,
    *,
    concept_type: str,
    title: str | None,
    body: str,
    extra: Mapping[str, str] | None = None,
    generated_by: str = SEED_GENERATED_BY,
    generated_at: str = SEED_GENERATED_AT,
) -> Path:
    """Write one concept file into an existing bundle. Does not call the product."""
    dest = concept_file(bundle, identity)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        _render_relatable_markdown(
            concept_type=concept_type,
            title=title,
            body=body,
            generated_by=generated_by,
            generated_at=generated_at,
            extra=extra,
        ),
        encoding="utf-8",
    )
    return dest


HeadingRecord = tuple[int, int, int, str, str]


def _heading_records_outside_fences(lines: list[str]) -> list[HeadingRecord]:
    """Return ``(marker_line, content_start, level, text, form)`` outside fences.

    *form* is ``atx``, ``setext_equals`` (level 1), or ``setext_hyphen``
    (deeper). Setext ``=`` stays a level-1 heading so a created Related
    Concepts title-plus-equals pair is a related-section heading.
    """
    records: list[HeadingRecord] = []
    in_fence = False
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            index += 1
            continue
        if in_fence:
            index += 1
            continue
        atx = _ATX.match(lines[index])
        if atx is not None and lines[index].lstrip().startswith("#"):
            text = (atx.group(2) or "").strip()
            if text:
                level = len(atx.group(1))
                records.append((index, index + 1, level, text, "atx"))
            index += 1
            continue
        if index + 1 < len(lines) and _SETEXT_UNDER.match(lines[index + 1]):
            text = lines[index].strip()
            if text:
                underline = lines[index + 1].lstrip()
                if underline.startswith("="):
                    records.append((index, index + 2, 1, text, "setext_equals"))
                else:
                    records.append((index, index + 2, 2, text, "setext_hyphen"))
                index += 2
                continue
        index += 1
    return records


def _section_span(
    lines: list[str], records: Sequence[HeadingRecord], chosen: HeadingRecord
) -> tuple[int, int, str]:
    marker, content_start, level, _text, _form = chosen
    end = len(lines)
    for other_marker, _other_start, other_level, _other_text, _other_form in records:
        if other_marker <= marker:
            continue
        if other_level <= level:
            end = other_marker
            break
    return content_start, end, "\n".join(lines[content_start:end])


def _original_setext_equals(
    records: Sequence[HeadingRecord], title: str | None
) -> HeadingRecord | None:
    """First remaining Setext-equals heading whose text is the seeded title."""
    if not title:
        return None
    for record in records:
        _marker, _start, _level, text, form = record
        if form == "setext_equals" and text == title:
            return record
    return None


def level1_headings_outside_fences(
    body: str, *, required: str | None = None
) -> list[tuple[str, int]]:
    """Level-1 heading texts and marker lines outside fenced code blocks.

    Setext ``=`` counts as level-1. If *required* is set, raise when that
    exact heading text is absent.
    """
    records = _heading_records_outside_fences(body.splitlines())
    found = [
        (text, marker)
        for marker, _start, level, text, _form in records
        if level == 1
    ]
    print(f"[F07] level-1 headings={found!r} required={required!r}", flush=True)
    if required is not None:
        if not any(text == required for text, _marker in found):
            raise HarnessError(
                f"required level-1 heading {required!r} is absent; "
                f"headings={found!r}"
            )
    return found


def related_section_items(
    body: str,
    *,
    required: bool = True,
    exclude_setext_title: str | None = None,
) -> tuple[str, list[str]]:
    """List items under the related heading the PRD names.

    Reused heading: first unfenced single-hash Related Concepts or Related.
    Otherwise a created level-1 Related Concepts (ATX or Setext equals).
    *exclude_setext_title* drops the original seeded title-plus-equals pair
    from that fallback so a Setext otherwise-create arm cannot count the
    seed as the created section.

    Raises when *required* and no such heading exists. An empty item list
    with a present heading is a classified look, not a swallowed failure.
    """
    lines = body.splitlines()
    records = _heading_records_outside_fences(lines)
    original = _original_setext_equals(records, exclude_setext_title)
    chosen: HeadingRecord | None = None
    for record in records:
        _marker, _start, level, text, form = record
        if form == "atx" and level == 1 and text in _LEVEL1_RELATED:
            chosen = record
            break
    if chosen is None:
        for record in records:
            if original is not None and record == original:
                continue
            _marker, _start, level, text, form = record
            if (
                level == 1
                and text == "Related Concepts"
                and form in ("atx", "setext_equals")
            ):
                chosen = record
                break
    if chosen is None:
        if required:
            raise HarnessError(
                "source body has no unfenced single-hash Related Concepts or "
                "Related heading, and no created level-1 Related Concepts "
                f"heading outside fences; body={body!r}"
            )
        return "", []
    marker, content_start, level, text, form = chosen
    _start, _end, section = _section_span(lines, records, chosen)
    items = _list_item_texts(section)
    print(
        f"[F07] related heading={text!r} form={form!r} items={len(items)} "
        f"section_len={len(section)} marker={marker} start={content_start} "
        f"level={level}",
        flush=True,
    )
    return text, items


def _href_raw(href: str) -> str:
    target = href.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if not target:
        raise HarnessError(f"inline link href is empty: {href!r}")
    return target.split()[0]


def _posix_resolve_href(source_dir: str, href: str) -> str:
    raw = _href_raw(href)
    if "\\" in raw:
        raise AssertionError(
            f"relationship href uses a backslash separator: {href!r}"
        )
    base = PurePosixPath(source_dir) if source_dir not in ("", ".") else PurePosixPath(".")
    combined = base / raw
    parts: list[str] = []
    for part in combined.parts:
        if part in (".",):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _source_dir_of(identity: str) -> str:
    parent = PurePosixPath(identity).parent
    text = parent.as_posix()
    return "" if text == "." else text


def _inline_links(item: str) -> list[tuple[str, str]]:
    found = _INLINE_LINK.findall(item)
    return [(str(text), str(href)) for text, href in found]


def _items_linking_to_target(
    items: Sequence[str], source_id: str, target_id: str
) -> list[tuple[str, str, str]]:
    """Return ``(item, link_text, href)`` whose POSIX-resolved href is the target file."""
    expected = f"{target_id}.md"
    source_dir = _source_dir_of(source_id)
    hits: list[tuple[str, str, str]] = []
    for item in items:
        for link_text, href in _inline_links(item):
            raw = _href_raw(href)
            if "\\" in raw:
                continue
            resolved = _posix_resolve_href(source_dir, href)
            if resolved == expected:
                hits.append((item, link_text, href))
    return hits


def assert_same_directory_named_href(href: str, target_filename: str) -> str:
    """After at most one leading ``./``, remaining href equals the target filename."""
    raw = _href_raw(href)
    if "\\" in raw:
        raise AssertionError(
            f"same-directory href uses a backslash separator: {href!r}"
        )
    remainder = raw[2:] if raw.startswith("./") else raw
    print(
        f"[F07] named href raw={raw!r} remainder={remainder!r} "
        f"filename={target_filename!r}",
        flush=True,
    )
    if remainder != target_filename:
        raise AssertionError(
            "same-directory href is not the target filename or a single "
            f"leading ./ form; href={href!r} expected {target_filename!r}"
        )
    return remainder


def assert_relative_link_to_target(
    source_path: str | Path,
    source_id: str,
    target_id: str,
    *,
    link_text: str,
    href_mode: str = "resolve",
    exclude_setext_title: str | None = None,
) -> str:
    """A related-section list item has a slash-separated link to the target.

    *href_mode* ``named`` accepts only ``filename.md`` / ``./filename.md``.
    *href_mode* ``resolve`` POSIX-resolves the href against the source directory.
    *exclude_setext_title* is the original Setext-equals heading text to skip
    when locating a newly created Related Concepts section.
    """
    if not path_is_file(source_path):
        raise HarnessError(f"source concept is not a file: {source_path}")
    text = read_file(source_path)
    _mapping, body = split_yaml_frontmatter(text)
    _heading, items = related_section_items(
        body, required=True, exclude_setext_title=exclude_setext_title
    )
    filename = concept_filename(target_id)
    hits = _items_linking_to_target(items, source_id, target_id)
    named_hits: list[tuple[str, str, str]] = []
    for item, visible, href in hits:
        try:
            assert_same_directory_named_href(href, filename)
        except AssertionError:
            continue
        named_hits.append((item, visible, href))
    chosen: tuple[str, str, str] | None = None
    if href_mode == "named":
        if not named_hits:
            raise AssertionError(
                "related section has no same-directory named href "
                f"({filename!r} or ./ form) to {target_id!r}; items={items!r}"
            )
        chosen = named_hits[0]
    elif href_mode == "resolve":
        if not hits:
            raise AssertionError(
                "related section has no slash-separated href that resolves to "
                f"{target_id}.md from {source_id!r}; items={items!r}"
            )
        chosen = hits[0]
        raw = _href_raw(chosen[2])
        if "\\" in raw:
            raise AssertionError(
                f"relationship href uses a backslash separator: {chosen[2]!r}"
            )
    else:
        raise HarnessError(f"unknown href_mode {href_mode!r}")
    item, visible, href = chosen
    print(
        f"[F07] link item={item!r} text={visible!r} href={href!r} "
        f"mode={href_mode}",
        flush=True,
    )
    if visible != link_text:
        raise AssertionError(
            f"link text is {visible!r}, expected the target title or final "
            f"identity segment {link_text!r}; item={item!r}"
        )
    return item


def _href_is_named_filename(href: str, filename: str) -> bool:
    """True when *href* is ``filename`` or a single leading ``./`` form."""
    try:
        raw = _href_raw(href)
    except HarnessError:
        return False
    if "\\" in raw:
        return False
    remainder = raw[2:] if raw.startswith("./") else raw
    return remainder == filename


def first_named_related_item_for_target(
    items: Sequence[str],
    source_id: str,
    target_id: str,
    *,
    link_text: str,
    prose: str | None = None,
) -> tuple[int, str, str]:
    """First related-section list item with a named href to *target_id*.

    The link text must equal *link_text*. When *prose* is given, that unique
    token must follow that target's inline link in the item. Raises if no
    such item exists. Returns ``(index, item, href)`` so callers can tell
    two relates apart by list-item index, not by substring presence.
    """
    filename = concept_filename(target_id)
    for index, item in enumerate(items):
        for match in _INLINE_LINK.finditer(item):
            visible, href = match.group(1), match.group(2)
            if visible != link_text:
                continue
            if not _href_is_named_filename(href, filename):
                continue
            if prose is not None and prose not in item[match.end() :]:
                continue
            print(
                f"[F07] named item index={index} source={source_id!r} "
                f"target={target_id!r} href={href!r} prose={prose!r} "
                f"item={item!r}",
                flush=True,
            )
            return index, item, href
    raise AssertionError(
        "related section has no list item with a same-directory named href "
        f"to {target_id!r} (link text {link_text!r}"
        + (f", prose {prose!r} after that link" if prose is not None else "")
        + f"); items={list(items)!r}"
    )


def assert_distinct_related_list_items(
    index_a: int,
    item_a: str,
    index_b: int,
    item_b: str,
    *,
    what: str,
) -> None:
    """Two relates must occupy two related-section list items, not one collapsed line."""
    print(
        f"[F07] distinct items {what!r} index_a={index_a} index_b={index_b} "
        f"item_a={item_a!r} item_b={item_b!r}",
        flush=True,
    )
    if index_a == index_b:
        raise AssertionError(
            f"{what} sit on the same related-section list item rather than "
            f"distinct list items; item={item_a!r}"
        )


def assert_prose_follows_link(
    item: str, prose: str, *, after_href: str | None = None
) -> None:
    """The unique prose token appears after the inline link in the list item.

    When *after_href* is given, after the first inline link whose href
    matches that href; otherwise after the first inline link.
    """
    chosen = None
    for match in _INLINE_LINK.finditer(item):
        href = match.group(2)
        if after_href is None:
            chosen = match
            break
        try:
            same = _href_raw(href) == _href_raw(after_href)
        except HarnessError:
            same = href == after_href
        if same:
            chosen = match
            break
    if chosen is None:
        raise HarnessError(
            "list item has no inline link"
            + (
                f" matching href {after_href!r}"
                if after_href is not None
                else ""
            )
            + f"; cannot place prose: {item!r}"
        )
    after = item[chosen.end() :]
    print(f"[F07] prose after link={after!r} expected={prose!r}", flush=True)
    if prose not in after:
        raise AssertionError(
            f"relationship prose {prose!r} does not follow the inline link; "
            f"item={item!r}"
        )


def _strip_item_covariates(
    item: str,
    tokens: Sequence[str],
) -> str:
    remainder = item
    ordered = sorted({str(tok) for tok in tokens if tok}, key=len, reverse=True)
    for tok in ordered:
        remainder = remainder.replace(tok, " ")
    remainder = _ISO_DATE.sub(" ", remainder)
    return remainder


def _phrase_tokens_present(text: str, phrase: str) -> bool:
    cleaned = re.sub(r"[\"'`\[\]\(\)\{\}<>*_.,:;]+", " ", text)
    parts = cleaned.split()
    needles = phrase.split()
    if not needles:
        raise HarnessError("empty phrase; cannot test token presence")
    for index in range(len(parts) - len(needles) + 1):
        if parts[index : index + len(needles)] == needles:
            return True
    return False


def assert_related_to_item(
    item: str,
    *,
    unused_prose: str,
    identities: Sequence[str],
    filenames: Sequence[str],
    titles: Sequence[str],
    path_tokens: Sequence[str],
    href: str,
) -> None:
    """After covariate strip, the whole phrase Related to remains; unused prose is absent."""
    tokens = [
        *identities,
        *filenames,
        *titles,
        *path_tokens,
        href,
        _href_raw(href),
    ]
    remainder = _strip_item_covariates(item, tokens)
    print(
        f"[F07] related-to remainder={remainder!r} item={item!r}",
        flush=True,
    )
    if not _phrase_tokens_present(remainder, "Related to"):
        raise AssertionError(
            "omit/empty/whitespace-prose list item does not retain the "
            f"Related to token after covariate strip; item={item!r} "
            f"remainder={remainder!r}"
        )
    if unused_prose and unused_prose in item:
        raise AssertionError(
            f"unused prose token {unused_prose!r} appeared on a Related to "
            f"item; item={item!r}"
        )


def assert_new_related_concepts_heading(body: str) -> None:
    """A newly created heading's text is exactly Related Concepts."""
    headings = level1_headings_outside_fences(body, required="Related Concepts")
    texts = [text for text, _marker in headings]
    if "Related Concepts" not in texts:
        raise AssertionError(
            "a new level-1 Related Concepts heading was not created; "
            f"headings={texts!r}"
        )


def assert_existing_related_heading_reused(
    body: str,
    heading_text: str,
    following_token: str,
    *,
    forbid_related_concepts: bool = False,
) -> None:
    """Existing unfenced single-hash related heading remains; following token remains."""
    lines = body.splitlines()
    records = _heading_records_outside_fences(lines)
    reused = [
        rec
        for rec in records
        if rec[4] == "atx" and rec[2] == 1 and rec[3] == heading_text
    ]
    if len(reused) != 1:
        raise AssertionError(
            f"existing single-hash {heading_text!r} heading was not reused as "
            f"exactly one heading; found={[(t, form, lv) for _m, _s, lv, t, form in records]!r}"
        )
    if forbid_related_concepts:
        extras = [
            rec
            for rec in records
            if rec[2] == 1 and rec[3] == "Related Concepts"
        ]
        if extras:
            raise AssertionError(
                "a new level-1 Related Concepts heading was created when "
                f"Related already existed; headings={[(t, form) for _m, _s, _lv, t, form in extras]!r}"
            )
    section_heading, items = related_section_items(body, required=True)
    if section_heading != heading_text:
        raise AssertionError(
            f"list items sit under {section_heading!r}, not the reused "
            f"{heading_text!r} heading"
        )
    section_blob = "\n".join(items)
    _start, _end, section_text = _section_span(lines, records, reused[0])
    print(
        f"[F07] reused heading={heading_text!r} following={following_token!r} "
        f"in_section={following_token in section_text}",
        flush=True,
    )
    if following_token not in section_text:
        raise AssertionError(
            f"unique token {following_token!r} that already sat under the "
            f"reused heading is gone; section={section_text!r} items={section_blob!r}"
        )


def assert_deeper_heading_not_reused(
    body: str,
    deeper_text: str,
    deeper_token: str,
    *,
    require_form: str | None = None,
    source_id: str | None = None,
    target_id: str | None = None,
) -> None:
    """A deeper related heading is not reused; a new level-1 Related Concepts exists."""
    assert_new_related_concepts_heading(body)
    lines = body.splitlines()
    records = _heading_records_outside_fences(lines)
    deeper = [
        rec
        for rec in records
        if rec[2] >= 2
        and rec[3] == deeper_text
        and (require_form is None or rec[4] == require_form)
    ]
    if not deeper:
        raise AssertionError(
            f"deeper heading {deeper_text!r} disappeared after relate"
            + (f" (form {require_form!r} required)" if require_form else "")
            + f"; headings={[(t, lv, form) for _m, _s, lv, t, form in records]!r}"
        )
    if deeper_token not in body:
        raise AssertionError(
            f"deeper-heading token {deeper_token!r} disappeared after relate"
        )
    heading, items = related_section_items(body, required=True)
    if heading != "Related Concepts":
        raise AssertionError(
            "new list items are not under a level-1 Related Concepts heading; "
            f"heading={heading!r}"
        )
    if source_id is not None and target_id is not None:
        _start, _end, deeper_span = _section_span(lines, records, deeper[0])
        span_items = _list_item_texts(deeper_span)
        span_hits = _items_linking_to_target(span_items, source_id, target_id)
        if span_hits:
            raise AssertionError(
                "new list item sits under the deeper related heading rather "
                f"than the new level-1 Related Concepts; span={deeper_span!r}"
            )
    print(
        f"[F07] deeper heading kept text={deeper_text!r} token={deeper_token!r} "
        f"level1={heading!r} items={len(items)} form={deeper[0][4]!r}",
        flush=True,
    )


def assert_setext_related_heading_not_reused(
    body: str,
    original_title: str,
    following_token: str,
    source_id: str,
    target_id: str,
) -> None:
    """Setext equals is otherwise-create: item sits under a different Related Concepts heading.

    Compares against the original title-plus-equals pair. Does not pin ``#``
    versus underline for the created heading, and does not require the
    original underline to remain if that pair was converted.
    """
    lines = body.splitlines()
    records = _heading_records_outside_fences(lines)
    original = _original_setext_equals(records, original_title)
    created = [
        rec
        for rec in records
        if rec != original
        and rec[2] == 1
        and rec[3] == "Related Concepts"
        and rec[4] in ("atx", "setext_equals")
    ]
    if not created:
        raise AssertionError(
            "a level-1 Related Concepts heading different from the original "
            f"Setext {original_title!r} pair was not created; "
            f"headings={[(t, form, lv) for _m, _s, lv, t, form in records]!r}"
        )
    heading, items = related_section_items(
        body, required=True, exclude_setext_title=original_title
    )
    if heading != "Related Concepts":
        raise AssertionError(
            "new list item is not under a created Related Concepts heading; "
            f"heading={heading!r}"
        )
    hits = _items_linking_to_target(items, source_id, target_id)
    if not hits:
        raise AssertionError(
            "created Related Concepts heading has no resolvable link to the "
            f"target {target_id!r}; items={items!r}"
        )
    if original is not None:
        _start, _end, span = _section_span(lines, records, original)
        if following_token not in span:
            raise AssertionError(
                f"following-section token {following_token!r} is gone from the "
                f"remaining original Setext span; span={span!r}"
            )
        span_items = _list_item_texts(span)
        span_hits = _items_linking_to_target(span_items, source_id, target_id)
        if span_hits:
            raise AssertionError(
                "new list item sits under the original Setext block rather "
                f"than the created Related Concepts heading; span={span!r}"
            )
    print(
        f"[F07] setext otherwise-create original={original_title!r} "
        f"created_form={created[0][4]!r} original_remaining={original is not None}",
        flush=True,
    )


def assert_fenced_heading_not_reused(body: str, fenced_token: str) -> None:
    """A fenced Related Concepts heading is not reused; a new unfenced one exists."""
    assert_new_related_concepts_heading(body)
    if fenced_token not in body:
        raise AssertionError(
            f"fenced-block token {fenced_token!r} disappeared after relate"
        )
    if "```" not in body:
        raise AssertionError("fenced block disappeared after relate")
    heading, items = related_section_items(body, required=True)
    if heading != "Related Concepts":
        raise AssertionError(
            f"new list item is not under unfenced Related Concepts; heading={heading!r}"
        )
    if not items:
        raise AssertionError(
            "unfenced Related Concepts heading has no list item; the item "
            "must sit outside the fence"
        )
    print(
        f"[F07] fenced heading not reused; unfenced items={len(items)}",
        flush=True,
    )


def assert_no_reciprocal_on_target(
    target_path: str | Path,
    target_id: str,
    source_id: str,
) -> None:
    """Target split body has no resolvable relative link to the source file."""
    if not path_is_file(target_path):
        raise HarnessError(f"target concept is not a file: {target_path}")
    text = read_file(target_path)
    _mapping, body = split_yaml_frontmatter(text)
    expected = f"{source_id}.md"
    target_dir = _source_dir_of(target_id)
    hits: list[tuple[str, str]] = []
    for link_text, href in _inline_links(body):
        try:
            raw = _href_raw(href)
        except HarnessError:
            continue
        if "\\" in raw:
            continue
        resolved = _posix_resolve_href(target_dir, href)
        if resolved == expected:
            hits.append((link_text, href))
    print(
        f"[F07] no-reciprocal target={target_id!r} source={source_id!r} "
        f"hits={hits!r}",
        flush=True,
    )
    if hits:
        raise AssertionError(
            "target body has a resolvable relative link to the source file; "
            f"target={target_id!r} source={source_id!r} hits={hits!r}"
        )


def assert_relate_log_bullet(
    log_path: str | Path,
    *,
    source_id: str,
    target_id: str,
    titles: Sequence[str] = (),
    path_tokens: Sequence[str] = (),
) -> str:
    """A log.md list item names both files and retains the Update token after strip."""
    if not path_is_file(log_path):
        raise HarnessError(f"log.md is not a file: {log_path}")
    text = read_file(log_path)
    items = _list_item_texts(text)
    source_file = concept_filename(source_id)
    target_file = concept_filename(target_id)
    matching: list[str] = []
    for item in items:
        names_source = (
            source_file in item
            or f"{source_id}.md" in item
            or source_id in item
        )
        names_target = (
            target_file in item
            or f"{target_id}.md" in item
            or target_id in item
        )
        if names_source and names_target:
            matching.append(item)
    if not matching:
        raise AssertionError(
            "log.md has no list item naming both the source and target files; "
            f"source={source_id!r} target={target_id!r} items={items!r}"
        )
    tokens = [
        source_file,
        target_file,
        f"{source_id}.md",
        f"{target_id}.md",
        source_id,
        target_id,
        *titles,
        *path_tokens,
        SEED_LOG_DATE,
    ]
    for item in matching:
        remainder = _strip_item_covariates(item, tokens)
        print(
            f"[F07] log item={item!r} remainder={remainder!r}",
            flush=True,
        )
        if _whole_token_present(remainder, "Update"):
            return item
    raise AssertionError(
        "log.md list item names both files but does not retain the Update "
        f"token after covariate strip; items={matching!r}"
    )


def assert_writing_relate_bookkeeping(
    bundle: str | Path,
    source_id: str,
    target_id: str,
    *,
    generated_by: str,
    seed_generated_at: str,
    extra: Mapping[str, str],
    seed_body_token: str,
    titles: Sequence[str] = (),
    path_tokens: Sequence[str] = (),
) -> tuple[str, str]:
    """Writing relate: refreshed generated, extras, Update naming both, body token remains."""
    root = Path(bundle)
    source_path = concept_file(root, source_id)
    if not path_is_file(source_path):
        raise HarnessError(f"source concept is not a file after relate: {source_path}")
    text = read_file(source_path)
    mapping, body = split_yaml_frontmatter(text)
    by, at = generated_by_and_at(mapping)
    print(
        f"[F07] generated.by={by!r} generated.at={at!r} seed_at={seed_generated_at!r}",
        flush=True,
    )
    if by != generated_by:
        raise AssertionError(
            f"source generated.by is {by!r}, expected {generated_by!r}"
        )
    if at == seed_generated_at:
        raise AssertionError(
            "source generated.at was not refreshed; still the seed value "
            f"{seed_generated_at!r}"
        )
    assert_extra_keys_survive(mapping, extra)
    if seed_body_token not in body:
        raise AssertionError(
            f"seed body token {seed_body_token!r} disappeared from the source"
        )
    assert_relate_log_bullet(
        root / "log.md",
        source_id=source_id,
        target_id=target_id,
        titles=titles,
        path_tokens=path_tokens,
    )
    return mapping, body


def assert_named_path_relate_landing(
    named_root: str | Path,
    nested_root: str | Path,
    source_id: str,
    target_id: str,
    *,
    generated_by: str,
    extra: Mapping[str, str],
    seed_generated_at: str,
    seed_body_token: str,
    link_text: str,
    prose: str | None,
    unused_prose: str | None,
    nested_source_before: bytes,
    nested_target_before: bytes,
    nested_log_before: bytes,
    titles: Sequence[str],
    path_tokens: Sequence[str],
) -> None:
    """Rewritten source and Update log land under the named path; nested stays."""
    named = Path(named_root)
    nested = Path(nested_root)
    written = concept_file(named, source_id)
    if not path_is_file(written):
        raise AssertionError(
            f"named-path relate did not write the source under the named path: "
            f"{written}"
        )
    item = assert_relative_link_to_target(
        written,
        source_id,
        target_id,
        link_text=link_text,
        href_mode="named",
    )
    if prose:
        assert_prose_follows_link(item, prose)
    else:
        assert_related_to_item(
            item,
            unused_prose=unused_prose or "",
            identities=(source_id, target_id),
            filenames=(concept_filename(source_id), concept_filename(target_id)),
            titles=titles,
            path_tokens=path_tokens,
            href=_inline_links(item)[0][1] if _inline_links(item) else "",
        )
    assert_writing_relate_bookkeeping(
        named,
        source_id,
        target_id,
        generated_by=generated_by,
        seed_generated_at=seed_generated_at,
        extra=extra,
        seed_body_token=seed_body_token,
        titles=titles,
        path_tokens=path_tokens,
    )
    nested_source = concept_file(nested, source_id)
    nested_target = concept_file(nested, target_id)
    if read_bytes(nested_source) != nested_source_before:
        raise AssertionError(
            "named-path relate changed the nested knowledge/ source; nested "
            "files must remain as they were"
        )
    if read_bytes(nested_target) != nested_target_before:
        raise AssertionError(
            "named-path relate changed the nested knowledge/ target; nested "
            "files must remain as they were"
        )
    if read_bytes(nested / "log.md") != nested_log_before:
        raise AssertionError(
            "named-path relate changed the nested knowledge/ log.md; nested "
            "files must remain as they were"
        )
    print(
        f"[F07] named-path landing source={source_id!r} named={named} "
        f"nested_untouched=1",
        flush=True,
    )


def assert_no_successful_relate(
    bundle: str | Path,
    source_id: str,
    target_id: str,
    *,
    seed_body_token: str | None = None,
    seed_generated_at: str = SEED_GENERATED_AT,
    target_before: bytes | None = None,
    path_tokens: Sequence[str] = (),
    source_title: str | None = None,
) -> None:
    """Aimed present source was not rewritten; target unchanged when it existed."""
    root = Path(bundle)
    src_path = concept_file(root, source_id)
    if path_is_file(src_path) and seed_body_token is not None:
        text = read_file(src_path)
        mapping, body = split_yaml_frontmatter(text)
        if seed_body_token not in body:
            raise AssertionError(
                f"refusing relate dropped seed body token {seed_body_token!r}"
            )
        heading, items = related_section_items(body, required=False)
        hits = _items_linking_to_target(items, source_id, target_id) if heading else []
        if hits:
            raise AssertionError(
                "refusing relate wrote a resolvable link to the aimed target; "
                f"items={hits!r}"
            )
        _by, at = generated_by_and_at(mapping)
        if at != seed_generated_at:
            raise AssertionError(
                "refusing relate refreshed generated.at; planted "
                f"{seed_generated_at!r} became {at!r}"
            )
        log_path = root / "log.md"
        if path_is_file(log_path):
            assert_update_absent(
                log_path,
                identity=source_id,
                filename=concept_filename(source_id),
                title=source_title,
                path_tokens=path_tokens,
            )
    tgt_path = concept_file(root, target_id)
    if target_before is not None and path_is_file(tgt_path):
        if read_bytes(tgt_path) != target_before:
            raise AssertionError(
                "refusing relate rewrote the present target file"
            )
    print(
        f"[F07] no successful relate source={source_id!r} target={target_id!r}",
        flush=True,
    )


def count_related_links_to_target(
    source_path: str | Path, source_id: str, target_id: str
) -> int:
    """How many related-section items resolve to the target. Heading must exist."""
    if not path_is_file(source_path):
        raise HarnessError(f"source concept is not a file: {source_path}")
    text = read_file(source_path)
    _mapping, body = split_yaml_frontmatter(text)
    _heading, items = related_section_items(body, required=True)
    hits = _items_linking_to_target(items, source_id, target_id)
    print(
        f"[F07] link count to {target_id!r} = {len(hits)}",
        flush=True,
    )
    return len(hits)
