# feature: F03
"""Observation helpers for the membundle show command and membundle_show tool (FP-03).

Helpers raise ``HarnessError`` when a query cannot be classified, and
``AssertionError`` when a classified observation misses a carrier the
tests require. They never return ``None`` / ``{}`` / ``""`` / ``[]`` to
mean "could not look".
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from _harness import (
    HarnessError,
    McpBatchResult,
    RunResult,
    Workspace,
    json_stdout,
    parse_json,
    path_is_dir,
    read_bytes,
    read_file,
    rpc_request,
)
from F01_helpers import (
    combined_report,
    report_remainder_after_stripping_paths,
    split_yaml_frontmatter,
    stage_writable_sources,
    strip_generated_covariates,
    unique_leaf,
)

_WRAP_PUNCT = re.compile(r"[\"'`\[\]\(\)\{\}<>]+")
_WHITESPACE = re.compile(r"\s+")

# Recipe artifact name. The binary is built in a writable copy, not the judge cwd.
_BIN_REL = Path("bin") / "membundle"
_BUILD_LOCK = threading.Lock()
_BUILD_DONE = False
_BUILT_BIN: Path | None = None
_NEVER_EXECUTED = (
    "the call was never executed; show results are missing"
)

INDEX_MARKDOWN = """\
---
membundle_version: 0.2
---

# Bundle
"""

LOG_MARKDOWN = """\
# 2026-01-01

- seed
"""


@dataclass(frozen=True)
class McpShowOutcome:
    """Classified JSON-RPC reply to one membundle_show tools/call.

    ``reply`` is the matching JSON-RPC object. ``payload`` is the parsed
    tool-result structure when the reply carries a ``result`` (JSON text
    content is decoded when it is JSON). ``report_text`` concatenates
    observable text from the reply. None of these fields is ``None`` to
    mean "no reply" — a missing reply raises ``HarnessError``.
    """

    batch: McpBatchResult
    reply: dict[str, Any]
    payload: Any
    report_text: str


def _workdir_has_product_sources(root: Path) -> bool:
    """True when *root* is a product tree whose Makefile writes ``bin/membundle``."""
    makefile = root / "Makefile"
    if not makefile.is_file() or not (root / "go.mod").is_file():
        return False
    text = makefile.read_text(encoding="utf-8")
    return "bin/membundle" in text


def _run_product_build(root: Path) -> None:
    """Run ``GOFLAGS=-buildvcs=false make build`` in a writable copy of the pytest cwd.

    Uses the Go toolchain and module cache already in the environment.
    A build that does not produce the binary is not a substrate exception;
    callers then fail because the show call was never executed.
    """
    env = dict(os.environ)
    env["GOFLAGS"] = "-buildvcs=false"
    print(f"[F03] GOFLAGS=-buildvcs=false make build cwd={root}", flush=True)
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
        print(f"[F03] make build could not start: {exc}", flush=True)
        return
    print(f"[F03] make build exit={completed.returncode}", flush=True)
    if completed.returncode != 0:
        print(
            f"[F03] make build stdout={completed.stdout[-2000:]!r} "
            f"stderr={completed.stderr[-2000:]!r}",
            flush=True,
        )


def _workdir_membundle() -> Path | None:
    """Return the ``bin/membundle`` built from the pytest cwd sources.

    The judge workdir is the pytest process cwd. Its sources are built in a
    writable copy (``stage_writable_sources``). Does not search ``PATH``,
    does not honor ``PRODUCT_BIN``, and does not use a binary this build did
    not just produce. An empty workdir therefore has no executable. The
    build runs once per process when the workdir contains the product sources.
    """
    global _BUILD_DONE, _BUILT_BIN
    with _BUILD_LOCK:
        if not _BUILD_DONE:
            root = Path.cwd().resolve()
            candidate: Path | None = None
            if _workdir_has_product_sources(root):
                stage = stage_writable_sources(root)
                _run_product_build(stage)
                candidate = (stage / _BIN_REL).resolve()
            if (
                candidate is not None
                and candidate.is_file()
                and os.access(candidate, os.X_OK)
            ):
                _BUILT_BIN = candidate
            else:
                _BUILT_BIN = None
            _BUILD_DONE = True
            print(f"[F03] resolved workdir binary={_BUILT_BIN!r}", flush=True)
        return _BUILT_BIN


def resolve_show_binary() -> Path:
    """Single resolver for every F03 show-command and inspect-tool call.

    Builds ``bin/membundle`` from a writable copy of the pytest cwd when it contains
    the product sources, then returns only that executable. When it is
    still absent, fails the test. Does not return a synthetic non-zero
    result: F03 failure assertions accept any non-zero exit and would then
    pass on an empty workspace.
    """
    binary = _workdir_membundle()
    # TEST-FIX(F03): upstream _harness.py:620 shows FileNotFoundError before show when bin/membundle is absent; Makefile:78 writes that binary only after GOFLAGS=-buildvcs=false make build.
    assert binary is not None, _NEVER_EXECUTED
    return binary


def _raise_if_show_binary_missing(binary: Path, exc: FileNotFoundError) -> NoReturn:
    """Turn a vanished workdir binary into the never-executed assertion."""
    if binary.is_file() and os.access(binary, os.X_OK):
        raise exc
    # TEST-FIX(F03): upstream _harness.py:620 shows FileNotFoundError before show when bin/membundle is absent; Makefile:78 writes that binary only after GOFLAGS=-buildvcs=false make build.
    raise AssertionError(_NEVER_EXECUTED) from None


def unique_tokens(*prefixes: str) -> tuple[str, ...]:
    """Runtime-unique tokens that are not substrings of each other."""
    tokens = [unique_leaf(prefix) for prefix in prefixes]
    for index, left in enumerate(tokens):
        for other, right in enumerate(tokens):
            if index == other:
                continue
            if left in right or right in left:
                raise HarnessError(
                    f"generated tokens overlap: {left!r} vs {right!r}"
                )
    return tuple(tokens)


def run_show(
    ws: Workspace,
    concept_id: str,
    bundle: str | Path | None = None,
    *,
    structured: bool = False,
    raw: bool = False,
    extra_args: Sequence[str] = (),
    env_updates: dict[str, str | None] | None = None,
    cwd: str | Path | None = None,
) -> RunResult:
    """Invoke ``membundle show`` with identity, optional bundle path, and modes."""
    args = ["show", str(concept_id)]
    if bundle is not None:
        args.append(str(bundle))
    if structured:
        args.append("--json")
    if raw:
        args.append("--raw")
    args.extend(str(a) for a in extra_args)
    print(
        f"[F03] show argv={args!r} cwd={cwd!r} structured={structured} raw={raw}",
        flush=True,
    )
    binary = resolve_show_binary()
    try:
        return ws.invoke(args, env_updates=env_updates, cwd=cwd, binary=binary)
    except FileNotFoundError as exc:
        _raise_if_show_binary_missing(binary, exc)


def require_show_success(result: RunResult) -> str:
    """Human success carrier: POSIX success plus non-empty combined streams."""
    report = combined_report(result)
    print(
        f"[F03] show-success exit={result.returncode} report_len={len(report)}",
        flush=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"show did not end successfully (exit {result.returncode}); "
            f"report={report!r}"
        )
    if not report:
        raise AssertionError("show succeeded but combined streams were empty")
    return report


def require_show_structured_success(result: RunResult) -> Any:
    """Structured success carrier: POSIX success plus a parsed stdout record."""
    report = combined_report(result)
    print(
        f"[F03] show-structured exit={result.returncode} "
        f"stdout_len={len(result.stdout)}",
        flush=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"structured show did not end successfully "
            f"(exit {result.returncode}); report={report!r}"
        )
    record = json_stdout(result)
    print(f"[F03] structured record type={type(record).__name__}", flush=True)
    return record


def require_show_raw_success(result: RunResult, file_bytes: bytes) -> bytes:
    """Raw success carrier: POSIX success plus stdout equal to on-disk bytes."""
    report = combined_report(result)
    print(
        f"[F03] show-raw exit={result.returncode} "
        f"stdout_len={len(result.stdout)} file_len={len(file_bytes)}",
        flush=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"raw show did not end successfully (exit {result.returncode}); "
            f"report={report!r}"
        )
    if result.stdout != file_bytes:
        raise AssertionError(
            "raw show stdout is not the on-disk file bytes "
            f"(stdout_len={len(result.stdout)} file_len={len(file_bytes)})"
        )
    return result.stdout


def require_show_failure(result: RunResult) -> str:
    """Failure carrier: process status is not success."""
    report = combined_report(result)
    print(
        f"[F03] show-failure exit={result.returncode} report={report!r}",
        flush=True,
    )
    assert result.returncode != 0, (
        f"show ended successfully when it must not; report={report!r}"
    )
    return report


def not_found_class_remainder(
    report: str,
    identity: str,
    path_tokens: Sequence[str],
) -> str:
    """Strip generated covariates, paths, and *identity* from a report."""
    if not report:
        raise HarnessError(
            "empty report; cannot classify a not-found class remainder"
        )
    text = report
    if identity:
        text = text.replace(identity, "")
        text = text.replace(f"{identity}.md", "")
    text = strip_generated_covariates(text)
    text = report_remainder_after_stripping_paths(text, path_tokens)
    return text


def _normalized_remainder(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def require_usage_failure(
    result: RunResult,
    success_report: str,
    nf_class_remainder: str,
    *,
    path_tokens: Sequence[str] = (),
    ghost_identities: Sequence[str] = (),
) -> str:
    """Missing-argument carrier: non-success, non-empty, not the not-found class."""
    report = combined_report(result)
    print(
        f"[F03] usage-failure exit={result.returncode} report={report!r}",
        flush=True,
    )
    assert result.returncode != 0, (
        f"show with a missing identity argument succeeded; report={report!r}"
    )
    assert report, (
        "show with a missing identity argument produced empty combined streams"
    )
    for ghost in ghost_identities:
        assert ghost not in report, (
            f"missing-argument report names live ghost identity {ghost!r}: "
            f"{report!r}"
        )
    usage_rem = report_remainder_after_stripping_paths(
        strip_generated_covariates(report), path_tokens
    )
    success_rem = report_remainder_after_stripping_paths(
        strip_generated_covariates(success_report), path_tokens
    )
    print(
        f"[F03] usage remainder={usage_rem!r} "
        f"not-found class={nf_class_remainder!r}",
        flush=True,
    )
    assert _normalized_remainder(usage_rem) != _normalized_remainder(
        success_rem
    ), (
        "missing-argument report is not distinguishable from a successful "
        f"show after stripping paths; remainder={usage_rem!r}"
    )
    assert _normalized_remainder(usage_rem) != _normalized_remainder(
        nf_class_remainder
    ), (
        "missing-argument report is the not-found class remainder; "
        f"remainder={usage_rem!r}"
    )
    class_norm = _normalized_remainder(nf_class_remainder)
    for token in usage_rem.split():
        if not token or token in nf_class_remainder:
            continue
        stripped = usage_rem.replace(token, "", 1)
        if _normalized_remainder(stripped) == class_norm:
            raise AssertionError(
                "missing-argument report is the not-found class remainder "
                f"plus one extra token {token!r}; remainder={usage_rem!r}"
            )
    return report


def require_not_found(result: RunResult, identity: str) -> str:
    """Not-found carrier: non-success and the report identifies *identity*."""
    report = require_show_failure(result)
    assert report, (
        f"not-found show of {identity!r} produced empty combined streams"
    )
    assert identity in report, (
        f"not-found report does not identify identity {identity!r}: "
        f"{report!r}"
    )
    return report


def require_load_error(
    result: RunResult,
    not_found_report: str,
    path_tokens: Sequence[str],
    identity: str,
) -> str:
    """Load-error carrier: non-success and remainder differs from not-found."""
    report = require_show_failure(result)
    assert report, (
        f"load-error show of {identity!r} produced empty combined streams"
    )
    load_rem = not_found_class_remainder(report, identity, path_tokens)
    nf_rem = not_found_class_remainder(not_found_report, identity, path_tokens)
    print(
        f"[F03] load remainder={load_rem!r} not-found remainder={nf_rem!r}",
        flush=True,
    )
    assert load_rem != nf_rem, (
        "load-error report is not distinguishable from not-found after "
        f"stripping paths, identity {identity!r}, and generated covariates; "
        f"remainder={load_rem!r}"
    )
    return report


def concept_spec(
    identity: str,
    *,
    concept_type: str,
    title: str,
    description: str,
    body: str,
    tags: Sequence[str] | None = None,
    generated: Mapping[str, str] | None = None,
    extra: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """One concept dict for :func:`write_bundle`. Does not call the product."""
    spec: dict[str, Any] = {
        "identity": identity,
        "type": concept_type,
        "title": title,
        "description": description,
        "body": body,
    }
    if tags is not None:
        spec["tags"] = list(tags)
    if generated is not None:
        spec["generated"] = dict(generated)
    if extra is not None:
        spec["extra"] = dict(extra)
    return spec


def render_concept_markdown(
    *,
    concept_type: str,
    title: str,
    description: str,
    body: str,
    tags: Sequence[str] | None = None,
    generated: Mapping[str, str] | None = None,
    extra: Mapping[str, str] | None = None,
) -> str:
    """Render a concept file the test writes. Does not call the product."""
    lines = ["---", f"type: {concept_type}", f"title: {title}", f"description: {description}"]
    if tags:
        lines.append("tags:")
        for tag in tags:
            lines.append(f"  - {tag}")
    if generated is not None:
        lines.append("generated:")
        lines.append(f"  by: {generated['by']}")
        lines.append(f"  at: {generated['at']}")
    if extra:
        for key, value in extra.items():
            lines.append(f"{key}: {value}")
    lines.append("---")
    body_text = body if body.endswith("\n") else body + "\n"
    return "\n".join(lines) + "\n" + body_text


def write_bundle(
    ws: Workspace,
    rel: str | Path,
    concepts: Sequence[Mapping[str, Any]],
    *,
    agents: str | None = None,
) -> Path:
    """Write root index, root log, and concept files. Does not call the product."""
    root = ws.resolve(rel) if str(rel) not in ("", ".") else ws.path
    if root != ws.path and not _is_under(root, ws.path):
        raise HarnessError(f"bundle path escapes workspace: {rel!r}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.md").write_text(INDEX_MARKDOWN, encoding="utf-8")
    (root / "log.md").write_text(LOG_MARKDOWN, encoding="utf-8")
    if agents is not None:
        (root / "AGENTS.md").write_text(agents, encoding="utf-8")
    for spec in concepts:
        identity = str(spec["identity"])
        if not identity or identity.startswith("/") or ".." in Path(identity).parts:
            raise HarnessError(f"refusing to write escaping identity {identity!r}")
        markdown = render_concept_markdown(
            concept_type=str(spec["type"]),
            title=str(spec["title"]),
            description=str(spec["description"]),
            body=str(spec["body"]),
            tags=spec.get("tags"),
            generated=spec.get("generated"),
            extra=spec.get("extra"),
        )
        dest = root / f"{identity}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(markdown, encoding="utf-8")
    print(f"[F03] wrote bundle at {root} concepts={len(concepts)}", flush=True)
    return root


def _is_under(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def concept_file_bytes(path: str | Path) -> bytes:
    """On-disk bytes of a concept file. Raises if the file cannot be read."""
    return read_bytes(path)


def concept_body_from_file(path: str | Path) -> str:
    """Post-frontmatter body from a file the test wrote."""
    text = read_file(path)
    _mapping, body = split_yaml_frontmatter(text)
    return body


def record_string_values(obj: Any) -> frozenset[str]:
    """Walk a parsed JSON structure and collect exact string values."""
    collected: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, str):
            collected.add(value)
            return
        if isinstance(value, Mapping):
            for item in value.values():
                _walk(item)
            return
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            for item in value:
                _walk(item)
            return
        if value is None or isinstance(value, (bool, int, float)):
            return
        raise HarnessError(
            f"structured record is not a walkable JSON value: {type(value).__name__}"
        )

    _walk(obj)
    return frozenset(collected)


def body_value_candidates(body: str) -> frozenset[str]:
    """Post-frontmatter body spellings that differ only by a trailing newline."""
    if not body:
        raise HarnessError("empty body; cannot build body-value candidates")
    stripped = body.rstrip("\n")
    if not stripped:
        raise HarnessError("body is only newlines; cannot match a body value")
    return frozenset({body, stripped, stripped + "\n"})


def require_record_has_identity_type_body(
    record: Any,
    identity: str,
    concept_type: str,
    body: str,
) -> None:
    """Identity, type, and post-frontmatter body each appear as exact values."""
    values = record_string_values(record)
    body_ok = bool(body_value_candidates(body) & values)
    print(
        f"[F03] record values include identity={identity in values} "
        f"type={concept_type in values} body={body_ok}",
        flush=True,
    )
    if identity not in values:
        raise AssertionError(
            f"structured record has no exact identity value {identity!r}; "
            f"values={sorted(values)!r}"
        )
    if f"{identity}.md" in values and identity not in values:
        raise AssertionError(
            f"structured identity value is {identity}.md, not the stripped identity"
        )
    if concept_type not in values:
        raise AssertionError(
            f"structured record has no exact type value {concept_type!r}; "
            f"values={sorted(values)!r}"
        )
    if not body_ok:
        raise AssertionError(
            "structured record has no exact post-frontmatter body value; "
            f"wanted={body!r} values={sorted(values)!r}"
        )


def human_identity_after_removing_body(report: str, body: str) -> str:
    """Return *report* with the presented body removed. Raise if body absent."""
    if not body:
        raise HarnessError("body was not provided; cannot strip it from a report")
    stripped_body = body.strip()
    if body not in report and stripped_body not in report:
        raise HarnessError(
            "body is not in the report; cannot remove it: "
            f"body={body!r} report={report!r}"
        )
    text = report
    if body in text:
        text = text.replace(body, "")
    if stripped_body and stripped_body in text:
        text = text.replace(stripped_body, "")
    return text


def identity_occurs_not_followed_by_md(text: str, identity: str) -> bool:
    """True when *identity* occurs in *text* not immediately followed by ``.md``."""
    start = 0
    while True:
        index = text.find(identity, start)
        if index < 0:
            return False
        after = text[index + len(identity) :]
        if not after.startswith(".md"):
            return True
        start = index + 1


def relationship_remainder(report: str, tokens: Sequence[str]) -> str:
    """Strip named covariates (bodies, hrefs, identities, paths, wrapping)."""
    if not report:
        raise HarnessError(
            "empty report; cannot compute a relationship remainder"
        )
    text = report
    ordered = sorted({tok for tok in tokens if tok}, key=len, reverse=True)
    for tok in ordered:
        text = text.replace(tok, "")
    text = strip_generated_covariates(text)
    text = _WRAP_PUNCT.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


def href_variants(href: str) -> tuple[str, ...]:
    """Href spellings with and without a trailing ``.md``."""
    variants = {href}
    if href.endswith(".md"):
        variants.add(href[: -len(".md")])
    else:
        variants.add(f"{href}.md")
    base = href.rsplit("/", 1)[-1]
    variants.add(base)
    if base.endswith(".md"):
        variants.add(base[: -len(".md")])
    return tuple(v for v in variants if v)


def snapshot_tree(directory: str | Path) -> dict[str, bytes]:
    """Relative path → bytes for every regular file (and symlink target)."""
    root = Path(directory)
    if not path_is_dir(root):
        raise HarnessError(f"not a directory, cannot snapshot: {root}")
    snapshot: dict[str, bytes] = {}
    try:
        for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
            for name in filenames:
                full = Path(dirpath) / name
                rel = full.relative_to(root).as_posix()
                try:
                    if full.is_symlink():
                        snapshot[rel] = b"SYMLINK:" + os.fsencode(os.readlink(full))
                    elif full.is_file():
                        snapshot[rel] = full.read_bytes()
                except OSError as exc:
                    raise HarnessError(f"cannot read {full} for snapshot: {exc}") from exc
    except OSError as exc:
        raise HarnessError(f"cannot walk {root} for snapshot: {exc}") from exc
    return snapshot


def assert_human_presents(
    report: str,
    *,
    identity: str,
    concept_type: str,
    title: str,
    description: str,
    body_token: str,
) -> None:
    """Human combined output contains the named field values (not labels)."""
    print(
        f"[F03] human presents identity={identity!r} type={concept_type!r} "
        f"title={title!r} desc={description!r} body_token={body_token!r}",
        flush=True,
    )
    assert identity in report, (
        f"human show does not present identity {identity!r}: {report!r}"
    )
    assert concept_type in report, (
        f"human show does not present type {concept_type!r}: {report!r}"
    )
    assert title in report, (
        f"human show does not present title {title!r}: {report!r}"
    )
    assert description in report, (
        f"human show does not present description {description!r}: {report!r}"
    )
    assert body_token in report, (
        f"human show does not present body token {body_token!r}: {report!r}"
    )


def unselected_token_absent(report: str, token: str) -> None:
    """The unselected decoy's unique token is absent from the show."""
    assert token not in report, (
        f"show presented unselected decoy token {token!r}: {report!r}"
    )


def mcp_reply_for_id(batch: McpBatchResult, request_id: int | str) -> dict[str, Any]:
    """Return the JSON-RPC message for *request_id*. Raise if none exists."""
    matches: list[dict[str, Any]] = []
    for message in batch.messages:
        if not isinstance(message, dict):
            raise HarnessError(
                f"MCP stdout line is not an object: {message!r}"
            )
        mid = message.get("id")
        if mid == request_id or mid == str(request_id):
            matches.append(message)
    if not matches:
        raise HarnessError(
            f"no JSON-RPC reply for request id {request_id!r}; "
            f"messages={batch.messages!r}"
        )
    return matches[0]


def mcp_is_protocol_error(reply: Mapping[str, Any]) -> bool:
    """True when the reply is a JSON-RPC error object (has ``error``)."""
    return "error" in reply and reply.get("error") is not None


def mcp_is_tool_error(reply: Mapping[str, Any]) -> bool:
    """True when the reply is an MCP tool-error result (L265)."""
    result = reply.get("result")
    if not isinstance(result, Mapping):
        return False
    return result.get("isError") is True


def mcp_is_invalid_params(reply: Mapping[str, Any]) -> bool:
    """True when the reply is JSON-RPC invalid-params (L269)."""
    if not mcp_is_protocol_error(reply):
        return False
    error = reply.get("error")
    if not isinstance(error, Mapping):
        raise HarnessError(
            f"JSON-RPC error is not an object; cannot classify invalid-params: "
            f"{reply!r}"
        )
    code = error.get("code")
    if isinstance(code, bool) or not isinstance(code, (int, float)):
        raise HarnessError(
            f"JSON-RPC error has no numeric code; cannot classify "
            f"invalid-params: {reply!r}"
        )
    return int(code) == -32602


def require_mcp_tool_level_failure(outcome: McpShowOutcome) -> str:
    """Invalid-identity carrier: tool-level failure, not a protocol error."""
    if mcp_is_protocol_error(outcome.reply):
        raise AssertionError(
            "membundle_show rejected the identity as a JSON-RPC protocol error; "
            "L265 requires tool-level failures as tool errors, not protocol "
            f"errors; reply={outcome.reply!r}"
        )
    assert mcp_is_tool_error(outcome.reply), (
        "membundle_show of an invalid identity is not a tool-level failure; a "
        "successful tools/call (including an empty or differently shaped "
        f"result) is not a non-success inspection; reply={outcome.reply!r}"
    )
    return outcome.report_text


def require_mcp_required_identity_non_success(outcome: McpShowOutcome) -> str:
    """Missing concept_id: tool error or JSON-RPC invalid-params (L128, L269)."""
    tool_error = mcp_is_tool_error(outcome.reply)
    invalid_params = mcp_is_invalid_params(outcome.reply)
    assert tool_error or invalid_params, (
        "membundle_show without a concept identity must be a tool error or the "
        "JSON-RPC invalid-params used for unreadable parameters; a "
        "successful tools/call (including an empty result) is not a "
        f"non-success inspection; reply={outcome.reply!r}"
    )
    return outcome.report_text


def _tool_content_texts(result: Any) -> list[str]:
    texts: list[str] = []
    if not isinstance(result, Mapping):
        return texts
    content = result.get("content")
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
        for item in content:
            if isinstance(item, Mapping) and isinstance(item.get("text"), str):
                texts.append(item["text"])
    return texts


def mcp_payload_and_text(reply: Mapping[str, Any]) -> tuple[Any, str]:
    """Parse a tools/call reply into a walkable payload and concatenated text."""
    chunks: list[str] = []
    if mcp_is_protocol_error(reply):
        error = reply.get("error")
        chunks.append(str(error))
        return error, "\n".join(chunks)
    result = reply.get("result")
    texts = _tool_content_texts(result)
    chunks.extend(texts)
    payload: Any = result
    for text in texts:
        stripped = text.strip()
        if not stripped:
            continue
        try:
            payload = parse_json(stripped, what="mcp tool text")
            break
        except HarnessError:
            continue
    if isinstance(result, Mapping):
        for key, value in result.items():
            if isinstance(value, str):
                chunks.append(value)
    return payload, "\n".join(chunks)


def mcp_membundle_show(
    ws: Workspace,
    arguments: Mapping[str, Any],
    *,
    request_id: int | str = 10,
    cwd: str | Path | None = None,
) -> McpShowOutcome:
    """One ``membundle_show`` tools/call. A missing reply for *request_id* raises."""
    lines = [
        rpc_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "f03-suite", "version": "0"},
            },
            id=1,
        ),
        rpc_request(
            "tools/call",
            {"name": "membundle_show", "arguments": dict(arguments)},
            id=request_id,
        ),
    ]
    print(
        f"[F03] mcp membundle_show arguments={dict(arguments)!r} id={request_id!r}",
        flush=True,
    )
    binary = resolve_show_binary()
    try:
        batch = ws.mcp_batch(lines, cwd=cwd, binary=binary)
    except FileNotFoundError as exc:
        _raise_if_show_binary_missing(binary, exc)
    reply = mcp_reply_for_id(batch, request_id)
    payload, report_text = mcp_payload_and_text(reply)
    print(
        f"[F03] mcp reply protocol_error={mcp_is_protocol_error(reply)} "
        f"tool_error={mcp_is_tool_error(reply)} text={report_text!r}",
        flush=True,
    )
    return McpShowOutcome(
        batch=batch, reply=reply, payload=payload, report_text=report_text
    )


def mcp_show(
    ws: Workspace,
    concept_id: str,
    bundle: str | Path | None = None,
    *,
    request_id: int | str = 10,
    cwd: str | Path | None = None,
) -> McpShowOutcome:
    """membundle_show with a required concept identity and optional bundle path."""
    arguments: dict[str, Any] = {"concept_id": concept_id}
    if bundle is not None:
        arguments["bundle"] = str(bundle)
    return mcp_membundle_show(ws, arguments, request_id=request_id, cwd=cwd)


def require_mcp_success_record(
    outcome: McpShowOutcome,
    identity: str,
    concept_type: str,
    body: str,
) -> Any:
    """MCP success: a concept record with identity, type, and body values."""
    if mcp_is_protocol_error(outcome.reply):
        raise AssertionError(
            f"membundle_show returned a protocol error instead of a concept record: "
            f"{outcome.reply!r}"
        )
    if mcp_is_tool_error(outcome.reply):
        raise AssertionError(
            f"membundle_show marked a tool error on a real concept: "
            f"{outcome.report_text!r}"
        )
    require_record_has_identity_type_body(
        outcome.payload, identity, concept_type, body
    )
    return outcome.payload


def require_mcp_not_found(outcome: McpShowOutcome, identity: str) -> str:
    """MCP not-found: tool-error channel plus the missing identity."""
    if mcp_is_protocol_error(outcome.reply):
        raise AssertionError(
            "membundle_show not-found used a JSON-RPC protocol error instead of "
            f"the tool-error channel: {outcome.reply!r}"
        )
    assert mcp_is_tool_error(outcome.reply), (
        "membundle_show not-found is not marked as a tool error (L265); "
        f"reply={outcome.reply!r}"
    )
    assert identity in outcome.report_text, (
        f"membundle_show not-found does not identify {identity!r}: "
        f"{outcome.report_text!r}"
    )
    return outcome.report_text


def structured_stdout_is_success_record(
    result: RunResult,
    identity: str,
    concept_type: str,
    body: str,
) -> bool:
    """True when stdout parses as a walkable identity+type+body record."""
    if not result.stdout.strip():
        return False
    try:
        record = json_stdout(result)
        values = record_string_values(record)
    except HarnessError:
        return False
    return (
        identity in values
        and concept_type in values
        and bool(body_value_candidates(body) & values)
    )


def mcp_is_success_record(
    outcome: McpShowOutcome,
    identity: str,
    concept_type: str,
    body: str,
) -> bool:
    """True when the reply walks as identity+type+body without a tool error."""
    if mcp_is_protocol_error(outcome.reply) or mcp_is_tool_error(outcome.reply):
        return False
    try:
        values = record_string_values(outcome.payload)
    except HarnessError:
        return False
    return (
        identity in values
        and concept_type in values
        and bool(body_value_candidates(body) & values)
    )


def reject_identity_on_all_show_modes(
    ws: Workspace,
    concept_id: str,
    bundle: str | Path | None,
    *,
    forbidden_body: str | None = None,
    forbidden_file_bytes: bytes | None = None,
) -> list[RunResult]:
    """Human, structured, and raw show of *concept_id* must not succeed."""
    results: list[RunResult] = []
    for structured, raw in ((False, False), (True, False), (False, True)):
        result = run_show(
            ws, concept_id, bundle, structured=structured, raw=raw
        )
        require_not_successful_inspection(
            result,
            forbidden_body=forbidden_body,
            forbidden_file_bytes=forbidden_file_bytes,
        )
        results.append(result)
    return results


def require_not_successful_inspection(
    result: RunResult,
    *,
    forbidden_body: str | None = None,
    forbidden_file_bytes: bytes | None = None,
) -> str:
    """Non-success, and the aimed file is not delivered as a successful show."""
    report = require_show_failure(result)
    if forbidden_file_bytes is not None:
        assert result.stdout != forbidden_file_bytes, (
            "rejected identity still emitted the aimed file bytes on stdout"
        )
    if forbidden_body and result.stdout.strip():
        try:
            record = json_stdout(result)
            values = record_string_values(record)
        except HarnessError:
            record = None
            values = frozenset()
        if record is not None:
            assert forbidden_body not in values, (
                "rejected identity produced a structured concept record "
                f"containing {forbidden_body!r}; stdout={result.stdout!r}"
            )
    return report


def body_token_from(body: str) -> str:
    """First non-empty line of a fixture body, used as a unique presence token."""
    for line in body.splitlines():
        text = line.strip()
        if text:
            return text
    raise HarnessError(f"fixture body has no non-empty token: {body!r}")


def path_tokens_for(*paths: str | Path) -> list[str]:
    """Path spellings to strip from reports, including cwd."""
    tokens: list[str] = []
    for raw in paths:
        if raw is None:
            continue
        text = str(raw)
        if text:
            tokens.append(text)
            tokens.append(os.path.abspath(text) if os.path.isabs(text) else text)
            tokens.append(os.path.basename(text.rstrip("/")))
    return tokens


def markdown_link(label: str, href: str) -> str:
    """Inline Markdown link the test writes into a fixture body."""
    return f"[{label}]({href})"


def assert_snapshot_helper_sees_write(ws: Workspace, leaf: str) -> None:
    """Positive control: the snapshot helper observes a file the test wrote."""
    payload = b"snapshot-positive-control"
    ws.write(f"{leaf}/seen.bin", payload)
    seen = snapshot_tree(ws.resolve(leaf))
    print(f"[F03] snapshot control keys={sorted(seen)}", flush=True)
    assert seen.get("seen.bin") == payload, (
        "snapshot helper did not observe a file the test wrote; "
        f"seen={seen!r}"
    )


def ignore_list_fixture(ws: Workspace, *, fence_ignored: bool) -> dict[str, str]:
    """Bundle whose source body has a live Q link plus ignore-list hrefs."""
    (
        p_leaf,
        q_leaf,
        ign_leaf,
        decoy_leaf,
        ptyp,
        qtyp,
        ityp,
        dtyp,
        pttl,
        qttl,
        ittl,
        dttl,
        pdsc,
        qdsc,
        idsc,
        ddsc,
        ptok,
        qtok,
        itok,
        dtok,
    ) = unique_tokens(
        "pskip",
        "qskip",
        "ign",
        "decoy",
        "ptyp",
        "qtyp",
        "ityp",
        "dtyp",
        "pttl",
        "qttl",
        "ittl",
        "dttl",
        "pdsc",
        "qdsc",
        "idsc",
        "ddsc",
        "pbod",
        "qbod",
        "ibod",
        "dbod",
    )
    p_id = f"architecture/{p_leaf}"
    q_id = f"architecture/{q_leaf}"
    ign_id = f"architecture/{ign_leaf}"
    decoy_id = decoy_leaf
    ignored_link = markdown_link(ign_leaf, f"{ign_leaf}.md")
    if fence_ignored:
        ignored_block = f"```\n{ignored_link}\n```\n"
    else:
        ignored_block = f"{ignored_link}\n"
    p_body = (
        f"{ptok}\n\n"
        f"{markdown_link(q_leaf, f'{q_leaf}.md')}\n"
        f"{ignored_block}"
        f"{markdown_link('idx', 'index.md')}\n"
        f"{markdown_link('hist', '../log.md')}\n"
        f"{markdown_link('gov', '../AGENTS.md')}\n"
        f"{markdown_link('web', f'https://example.com/{decoy_leaf}.md')}\n"
    )
    rel = unique_tokens("kbign")[0]
    write_bundle(
        ws,
        rel,
        [
            concept_spec(p_id, concept_type=ptyp, title=pttl, description=pdsc, body=p_body),
            concept_spec(
                q_id,
                concept_type=qtyp,
                title=qttl,
                description=qdsc,
                body=f"{qtok}\n",
            ),
            concept_spec(
                ign_id,
                concept_type=ityp,
                title=ittl,
                description=idsc,
                body=f"{itok}\n",
            ),
            concept_spec(
                decoy_id,
                concept_type=dtyp,
                title=dttl,
                description=ddsc,
                body=f"{dtok}\n",
            ),
        ],
        agents="# governance\n",
    )
    return {
        "rel": rel,
        "p_id": p_id,
        "q_id": q_id,
        "ign_id": ign_id,
        "decoy_id": decoy_id,
        "p_body": p_body,
        "ign_body": f"{itok}\n",
        "decoy_body": f"{dtok}\n",
        "ptok": ptok,
        "qtok": qtok,
        "itok": itok,
        "dtok": dtok,
        "ptyp": ptyp,
        "pttl": pttl,
        "pdsc": pdsc,
    }
