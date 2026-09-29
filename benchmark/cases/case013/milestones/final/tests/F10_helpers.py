# feature: F10
"""Observation helpers for the membundle agents command (FP-10).

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
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, NoReturn

from _harness import (
    HarnessError,
    RunResult,
    Workspace,
    json_stdout,
    path_is_file,
    path_is_symlink,
)
from F01_helpers import (
    combined_report,
    report_remainder_after_stripping_paths,
    unique_leaf,
)
from F02_helpers import BEGIN_MEMBUNDLE_COMMENT, END_MEMBUNDLE_COMMENT
from F08_helpers import (
    PASSING_AGENTS_TEXT,
    SSOT_LINKS,
    _walk_values,
)

MBG_RULE_IDS = ("MBG-001", "MBG-002", "MBG-003", "MBG-004", "MBG-005")

SsotKind = Literal["missing", "regular", "correct", "wrong_target"]

_ATX = re.compile(r"^(#{1,6})(?:[ \t]+(.+?))?[ \t]*#*[ \t]*$")
_BUDGET_FORBIDDEN = ("20", "400", "mbg-", "mermaid")

_PROFILE_PHRASES: dict[str, tuple[str, ...]] = {
    "software": ("clean architecture", "tdd"),
    "research": ("citation integrity",),
    "legal": ("privacy", "compliance"),
    "coaching": ("icf ethics",),
    "books": ("canon", "spoilers"),
}

# Recipe artifact name. The binary is built in a writable copy, not the judge cwd.
_BIN_REL = Path("bin") / "membundle"
_BUILD_LOCK = threading.Lock()
_BUILD_DONE = False
_BUILT_BIN: Path | None = None
_NEVER_EXECUTED = (
    "the agents call was never executed and its results are missing"
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
    print(f"[F10] GOFLAGS=-buildvcs=false make build cwd={root}", flush=True)
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
        print(f"[F10] make build could not start: {exc}", flush=True)
        return False
    print(f"[F10] make build exit={completed.returncode}", flush=True)
    if completed.returncode != 0:
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        print(
            f"[F10] make build stdout={stdout[-2000:]!r} "
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
            print(f"[F10] resolved built binary={_BUILT_BIN!r}", flush=True)
        return _BUILT_BIN


def resolve_agents_binary() -> Path:
    """Single resolver for every F10 agents lint, init, link, and check call.

    When the pytest cwd contains the product sources, copies those sources
    to a writable directory, runs ``GOFLAGS=-buildvcs=false make build``
    there, and returns only that ``bin/membundle``. When that executable
    is absent, fails the test. Does not return a synthetic success, a
    synthetic lint finding, a synthetic symlink, or a synthetic status:
    those are agents outcomes, and an empty workspace would then look like
    a completed agents command.
    """
    binary = _workdir_membundle()
    # TEST-FIX((none)): upstream Makefile:78 shows go build opens bin/membundle in the working directory and fails with "open bin/membundle: read-only file system" when that directory cannot accept the write, so agents never runs and its results are missing.
    assert binary is not None, _NEVER_EXECUTED
    return binary


def _raise_if_agents_binary_missing(binary: Path, exc: FileNotFoundError) -> NoReturn:
    """Turn a vanished workdir binary into the never-executed assertion."""
    if binary.is_file() and os.access(binary, os.X_OK):
        raise exc
    # TEST-FIX(F10): upstream _harness.py:620 shows FileNotFoundError before agents lint, init, link, or check when bin/membundle is absent; Makefile:78 writes that binary only after GOFLAGS=-buildvcs=false make build.
    raise AssertionError(_NEVER_EXECUTED) from None


def _invoke_agents(
    ws: Workspace,
    args: Sequence[str],
    *,
    cwd: str | Path | None,
) -> RunResult:
    """Invoke agents through the single workdir resolver."""
    binary = resolve_agents_binary()
    try:
        return ws.invoke(args, cwd=cwd, binary=binary)
    except FileNotFoundError as exc:
        _raise_if_agents_binary_missing(binary, exc)


def _root_path(ws: Workspace, root: str | Path | None) -> Path:
    if root is None:
        return ws.path
    path = Path(root)
    if path.is_absolute():
        return path
    return ws.path / path


def _normalize_mention(text: str) -> str:
    return text.lower().replace("_", " ").replace("/", " ")


def budget_safe_token(prefix: str) -> str:
    """Runtime-unique token that cannot be confused with 20 / 400 / rule ids."""
    for _ in range(64):
        token = unique_leaf(prefix)
        low = token.lower()
        if any(part in low for part in _BUDGET_FORBIDDEN):
            continue
        return token
    raise HarnessError(
        f"could not generate a budget-safe token from prefix {prefix!r}"
    )


def budget_safe_tokens(*prefixes: str) -> tuple[str, ...]:
    tokens = [budget_safe_token(prefix) for prefix in prefixes]
    for index, left in enumerate(tokens):
        for other, right in enumerate(tokens):
            if index == other:
                continue
            if left in right or right in left:
                raise HarnessError(
                    f"generated tokens overlap: {left!r} vs {right!r}"
                )
    return tuple(tokens)


def budget_word_list(count: int, prefix: str) -> list[str]:
    """Distinct whitespace-separated words for token-budget fixtures."""
    words: list[str] = []
    seen: set[str] = set()
    while len(words) < count:
        word = budget_safe_token(prefix)
        if word in seen:
            continue
        overlap = False
        for existing in words:
            if word in existing or existing in word:
                overlap = True
                break
        if overlap:
            continue
        seen.add(word)
        words.append(word)
    return words


def run_agents_lint(
    ws: Workspace,
    path: str | Path | None = None,
    *,
    budget: int | None = None,
    structured: bool = False,
    extra_args: Sequence[str] = (),
    cwd: str | Path | None = None,
) -> RunResult:
    """Invoke ``membundle agents lint`` with optional path, cap, and structured output."""
    args: list[str] = ["agents", "lint"]
    if budget is not None:
        args.append(f"--budget={budget}")
    if structured:
        args.append("--json")
    args.extend(str(a) for a in extra_args)
    if path is not None:
        args.append(str(path))
    print(
        f"[F10] lint argv={args!r} cwd={cwd!r} structured={structured}",
        flush=True,
    )
    return _invoke_agents(ws, args, cwd=cwd)


def run_agents_init(
    ws: Workspace,
    root: str | Path | None = None,
    *,
    domain: str | None = None,
    name: str | None = None,
    overwrite: bool = False,
    extra_args: Sequence[str] = (),
    cwd: str | Path | None = None,
) -> RunResult:
    """Invoke ``membundle agents init`` with optional domain, name, root, overwrite."""
    args: list[str] = ["agents", "init"]
    if domain is not None:
        args.extend(["--domain", str(domain)])
    if name is not None:
        args.extend(["--name", str(name)])
    if root is not None:
        args.extend(["--root", str(root)])
    if overwrite:
        args.append("--force")
    args.extend(str(a) for a in extra_args)
    print(
        f"[F10] init argv={args!r} cwd={cwd!r} overwrite={overwrite}",
        flush=True,
    )
    return _invoke_agents(ws, args, cwd=cwd)


def run_agents_link(
    ws: Workspace,
    root: str | Path | None = None,
    *,
    check_only: bool = False,
    overwrite: bool = False,
    extra_args: Sequence[str] = (),
    cwd: str | Path | None = None,
) -> RunResult:
    """Invoke ``membundle agents link`` with optional root, check-only, overwrite."""
    args: list[str] = ["agents", "link"]
    if root is not None:
        args.extend(["--root", str(root)])
    if check_only:
        args.append("--check")
    if overwrite:
        args.append("--force")
    args.extend(str(a) for a in extra_args)
    print(
        f"[F10] link argv={args!r} cwd={cwd!r} check_only={check_only} "
        f"overwrite={overwrite}",
        flush=True,
    )
    return _invoke_agents(ws, args, cwd=cwd)


def run_agents_check(
    ws: Workspace,
    root: str | Path | None = None,
    *,
    extra_args: Sequence[str] = (),
    cwd: str | Path | None = None,
) -> RunResult:
    """Invoke ``membundle agents check`` with optional target root."""
    args: list[str] = ["agents", "check"]
    if root is not None:
        args.extend(["--root", str(root)])
    args.extend(str(a) for a in extra_args)
    print(f"[F10] check argv={args!r} cwd={cwd!r}", flush=True)
    return _invoke_agents(ws, args, cwd=cwd)


def require_agents_success(result: RunResult) -> str:
    """Agents success carrier: POSIX status 0."""
    report = combined_report(result)
    print(
        f"[F10] success-carrier exit={result.returncode} report_len={len(report)}",
        flush=True,
    )
    assert result.returncode == 0, (
        f"agents command did not end with status 0 (exit {result.returncode}); "
        f"report={report!r}"
    )
    return report


def require_agents_failure(result: RunResult) -> str:
    """Agents failure carrier: non-zero status. Does not require 1 vs 2."""
    report = combined_report(result)
    print(
        f"[F10] failure-carrier exit={result.returncode} report_len={len(report)}",
        flush=True,
    )
    assert result.returncode != 0, (
        f"agents command succeeded (exit 0) on a case that must not succeed; "
        f"report={report!r}"
    )
    return report


def parse_structured_lint(result: RunResult) -> Any:
    """Parse requested structured lint stdout as JSON. Raises if it cannot."""
    payload = json_stdout(result, what="agents lint --json stdout")
    print(
        f"[F10] structured lint type={type(payload).__name__} "
        f"exit={result.returncode}",
        flush=True,
    )
    return payload


def structured_strings(obj: Any) -> list[str]:
    """Walk string values (and mapping keys) from a structured payload."""
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            found.append(value)
            return
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if isinstance(key, str):
                    found.append(key)
                elif key is None or isinstance(key, (int, float, bool)):
                    pass
                else:
                    raise HarnessError(
                        f"unclassified structured mapping key: {type(key).__name__}"
                    )
                walk(nested)
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                walk(item)
            return
        if isinstance(value, (int, float, bool)) or value is None:
            return
        raise HarnessError(
            f"unclassified structured value: {type(value).__name__}: {value!r}"
        )

    walk(obj)
    return found


def _rule_in_strings(strings: Sequence[str], rule_id: str) -> bool:
    return any(rule_id in text for text in strings)


def assert_rule_reported(payload: Any, rule_id: str) -> list[str]:
    """Named MBG identifier appears among walked structured strings."""
    strings = structured_strings(payload)
    print(f"[F10] rule-reported {rule_id} strings={strings!r}", flush=True)
    assert _rule_in_strings(strings, rule_id), (
        f"structured lint did not report rule identifier {rule_id}; "
        f"walked={strings!r}"
    )
    return strings


def assert_rule_absent(payload: Any, rule_id: str) -> list[str]:
    """Named MBG identifier is absent from walked structured strings."""
    strings = structured_strings(payload)
    print(f"[F10] rule-absent {rule_id} strings={strings!r}", flush=True)
    assert not _rule_in_strings(strings, rule_id), (
        f"structured lint reported {rule_id} on a file that must not; "
        f"walked={strings!r}"
    )
    return strings


def assert_rule_only(payload: Any, rule_id: str) -> list[str]:
    """Named MBG-00N is present; the other four MBG-001–MBG-005 ids are absent."""
    if rule_id not in MBG_RULE_IDS:
        raise HarnessError(f"not an MBG-001–MBG-005 identifier: {rule_id!r}")
    strings = assert_rule_reported(payload, rule_id)
    for other in MBG_RULE_IDS:
        if other == rule_id:
            continue
        assert not _rule_in_strings(strings, other), (
            f"structured lint for {rule_id} also reported {other}; "
            f"walked={strings!r}"
        )
    return strings


def write_agents(ws: Workspace, rel: str | Path, body: str) -> Path:
    """Write an AGENTS.md-shaped file under the workspace."""
    dest = ws.write(rel, body)
    print(f"[F10] wrote {dest} bytes={len(body.encode('utf-8'))}", flush=True)
    return dest


def ascii_agents_body(
    *,
    invariants_item: str | None = None,
    section0: str | None = "mermaid",
    extra: str = "",
    invariants_heading: str = "Invariants",
    extra_invariants_items: Sequence[str] = (),
    inner: str = "keep compact",
) -> str:
    """Constructable ASCII AGENTS.md that is otherwise a single-rule-clean file.

    Callers pass hyphen-item text. Section 0 includes mermaid when *section0*
    is a string; ``section0=None`` omits the Domain Codex / 0. heading.
    """
    parts: list[str] = []
    if section0 is not None:
        parts.append("# 0. Domain Codex")
        parts.append(section0)
        parts.append("")
    parts.append(BEGIN_MEMBUNDLE_COMMENT)
    parts.append(inner)
    parts.append(END_MEMBUNDLE_COMMENT)
    parts.append("")
    if invariants_item is not None:
        heading = invariants_heading if invariants_heading else "Invariants"
        if not heading.startswith("#"):
            parts.append(f"## {heading}")
        else:
            parts.append(heading)
        parts.append(f"- {invariants_item}")
        for item in extra_invariants_items:
            parts.append(f"- {item}")
        parts.append("")
    if extra:
        parts.append(extra if extra.endswith("\n") else extra + "\n")
    return "\n".join(parts)


def domain_codex_region(text: str) -> str:
    """Slice from a 0. / domain-codex ATX heading to the next heading, BEGIN, or EOF.

    Raises ``HarnessError`` if no such heading exists.
    """
    lines = text.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        match = _ATX.match(line)
        if match is None or not line.lstrip().startswith("#"):
            continue
        content = (match.group(2) or "").strip()
        lower = content.lower()
        if content.startswith("0.") or "domain codex" in lower:
            start = index
            break
    if start is None:
        raise HarnessError(
            "no ATX heading that starts with 0. or contains domain codex"
        )
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if BEGIN_MEMBUNDLE_COMMENT in lines[index]:
            end = index
            break
        match = _ATX.match(lines[index])
        if match is not None and lines[index].lstrip().startswith("#"):
            end = index
            break
    region = "\n".join(lines[start:end])
    print(
        f"[F10] domain-codex region start={start} end={end} len={len(region)}",
        flush=True,
    )
    return region


def _mapping_kind(root: Path, rel: str) -> SsotKind:
    path = root / rel
    agents = root / "AGENTS.md"
    try:
        is_link = path_is_symlink(path)
    except HarnessError:
        raise
    if not is_link:
        try:
            if path.exists():
                if path.is_file() and not path.is_symlink():
                    return "regular"
                raise HarnessError(
                    f"unclassified SSoT mapping at {path}: exists but is "
                    f"neither a symlink nor a regular file"
                )
            return "missing"
        except OSError as exc:
            raise HarnessError(f"cannot stat SSoT mapping {path}: {exc}") from exc
    if not agents.is_file():
        return "wrong_target"
    try:
        resolved = path.resolve()
        if not resolved.exists():
            return "wrong_target"
        if resolved.samefile(agents):
            return "correct"
        return "wrong_target"
    except OSError:
        return "wrong_target"


def assert_ssot_mapping_state(
    root: str | Path,
    rel: str,
    *,
    kind: SsotKind,
) -> SsotKind:
    """Classify one L69 mapping: missing / regular / correct / wrong_target."""
    base = Path(root)
    if kind not in ("missing", "regular", "correct", "wrong_target"):
        raise HarnessError(f"unclassified requested SSoT kind: {kind!r}")
    actual = _mapping_kind(base, rel)
    print(
        f"[F10] ssot {rel} actual={actual} expected={kind} root={base}",
        flush=True,
    )
    assert actual == kind, (
        f"SSoT mapping {rel} is {actual}, expected {kind}, under {base}"
    )
    return actual


def assert_named_ssot_symlinks(root: str | Path) -> None:
    """All four L69 paths are symlinks whose resolved file is root/AGENTS.md."""
    base = Path(root)
    agents = base / "AGENTS.md"
    if not path_is_file(agents):
        raise HarnessError(
            f"cannot verify SSoT symlinks; root AGENTS.md is not a file: {agents}"
        )
    for rel, _target in SSOT_LINKS:
        path = base / rel
        if not path.exists() and not path_is_symlink(path):
            raise HarnessError(f"SSoT mapping is missing: {path}")
        if not path_is_symlink(path):
            raise HarnessError(
                f"SSoT mapping exists but is not a symlink: {path}"
            )
        try:
            resolved = path.resolve()
        except OSError as exc:
            raise HarnessError(
                f"SSoT mapping {path} cannot be resolved: {exc}"
            ) from exc
        if not resolved.exists():
            raise HarnessError(
                f"SSoT mapping {path} is dangling; resolved={resolved}"
            )
        try:
            same = resolved.samefile(agents)
        except OSError as exc:
            raise HarnessError(
                f"cannot compare {resolved} to {agents}: {exc}"
            ) from exc
        if not same:
            raise HarnessError(
                f"SSoT mapping {path} resolves to {resolved}, not {agents}"
            )
    print(f"[F10] all four SSoT mappings resolve to {agents}", flush=True)


def mentions_profile(region: str, profile: str) -> bool:
    """Case-insensitive mention of that profile's PRD tokens (_ as space)."""
    key = profile.lower()
    if key not in _PROFILE_PHRASES:
        raise HarnessError(f"unknown domain profile {profile!r}")
    normalized = _normalize_mention(region)
    phrases = _PROFILE_PHRASES[key]
    for phrase in phrases:
        needle = _normalize_mention(phrase)
        if needle in normalized:
            continue
        words = [word for word in needle.split() if word]
        if words and all(word in normalized for word in words):
            continue
        print(
            f"[F10] profile {key} missing {phrase!r} in region",
            flush=True,
        )
        return False
    print(f"[F10] profile {key} mentions {phrases!r}", flush=True)
    return True


def human_budget_remainder(
    report: str,
    *,
    path_tokens: Sequence[str],
    fixture_tokens: Sequence[str],
) -> str:
    """Strip workspace paths, MBG-001–MBG-005 identifiers, and fixture tokens."""
    remainder = report_remainder_after_stripping_paths(report, path_tokens)
    for rule_id in sorted(MBG_RULE_IDS, key=len, reverse=True):
        remainder = remainder.replace(rule_id, "")
    for token in sorted((str(t) for t in fixture_tokens if t), key=len, reverse=True):
        remainder = remainder.replace(token, "")
    print(f"[F10] human-budget remainder={remainder!r}", flush=True)
    return remainder


def remainder_has_quantity(text: str, quantity: int) -> bool:
    """True when *quantity* appears as a whole number, not inside a larger integer."""
    return re.search(rf"(?<![0-9]){quantity}(?![0-9])", text) is not None


def assert_human_in_force_budget_remainders_differ(
    cap20_remainder: str,
    *four_hundred_remainders: str,
) -> None:
    """Omit / non-positive / explicit-400 human remainders differ from cap-20.

    After the same path / MBG-001–MBG-005 identifier / fixture-token strip, a
    canned report that always contains both 400 and 20 has one remainder on
    every run. The in-force human budget is that contrast. The other sample
    cap integer is not required to be absent.
    """
    if not four_hundred_remainders:
        raise HarnessError(
            "need at least one omit/non-positive/explicit-400 remainder "
            "to contrast with cap 20"
        )
    print(
        f"[F10] human-budget cap20 remainder={cap20_remainder!r} "
        f"400-arm remainders={list(four_hundred_remainders)!r}",
        flush=True,
    )
    for rem in four_hundred_remainders:
        assert rem != cap20_remainder, (
            "omit/non-positive/explicit-400 human remainder did not differ "
            "from the cap-20 remainder after path/identifier/token strip; "
            "a canned report that always prints both 400 and 20 satisfies "
            "presence checks without tracking the in-force budget: "
            f"{rem!r}"
        )


def payload_remainder_after_strip(
    payload: Any,
    *,
    path_tokens: Sequence[str],
    fixture_tokens: Sequence[str],
) -> str:
    """Walked structured strings after stripping paths and unique file tokens."""
    blob = "\n".join(structured_strings(payload))
    remainder = report_remainder_after_stripping_paths(blob, path_tokens)
    for token in sorted((str(t) for t in fixture_tokens if t), key=len, reverse=True):
        remainder = remainder.replace(token, "")
    print(f"[F10] payload remainder={remainder!r}", flush=True)
    return remainder


def unique_passing_agents() -> tuple[str, str]:
    """Sealed passing sample plus a runtime-unique ASCII line that does not break MBG."""
    token = budget_safe_token("note")
    body = PASSING_AGENTS_TEXT + f"\n## 2. Notes\n{token}\n"
    return body, token


def structured_sequence_lengths(obj: Any) -> list[int]:
    """Lengths of JSON arrays in a structured payload. Raises on unclassified input."""
    found: list[int] = []

    def walk(value: Any) -> None:
        if isinstance(value, (str, bytes, bytearray)):
            return
        if isinstance(value, Mapping):
            for nested in value.values():
                walk(nested)
            return
        if isinstance(value, Sequence):
            found.append(len(value))
            for item in value:
                walk(item)
            return
        if isinstance(value, (int, float, bool)) or value is None:
            return
        raise HarnessError(
            f"unclassified structured value while walking array lengths: "
            f"{type(value).__name__}: {value!r}"
        )

    walk(obj)
    print(f"[F10] structured array lengths={found!r}", flush=True)
    return found


def fixture_line_integers(text: str, *needles: str) -> set[int]:
    """1-based and 0-based line numbers of planted needles (input covariates)."""
    drop: set[int] = set()
    lines = text.splitlines()
    for needle in needles:
        hits = 0
        for index, line in enumerate(lines, start=1):
            if needle in line:
                hits += 1
                drop.add(index)
                drop.add(index - 1)
        if hits == 0:
            raise HarnessError(
                f"fixture needle {needle!r} missing from planted text"
            )
    print(f"[F10] fixture line covariates={sorted(drop)!r}", flush=True)
    return drop


def assert_structured_counts_greater(
    fewer: Any,
    more: Any,
    *,
    rule_id: str,
    drop_integers: Sequence[int],
) -> None:
    """More-findings arm reports a greater count than the fewer-findings arm.

    Any one public-surface carrier is enough: JSON numbers after dropping
    planted line positions, JSON array lengths, or how often the named rule
    identifier appears among walked strings. Key names are not pinned.
    """
    drop = {int(n) for n in drop_integers}
    few_nums = [
        float(v) for v in _walk_values(fewer, want=int) if int(v) not in drop
    ]
    more_nums = [
        float(v) for v in _walk_values(more, want=int) if int(v) not in drop
    ]
    few_lens = structured_sequence_lengths(fewer)
    more_lens = structured_sequence_lengths(more)
    few_ids = sum(text.count(rule_id) for text in structured_strings(fewer))
    more_ids = sum(text.count(rule_id) for text in structured_strings(more))

    def _pad_desc(values: Sequence[float]) -> list[float]:
        ordered = sorted((float(v) for v in values), reverse=True)
        return ordered

    few_pad = _pad_desc(few_nums)
    more_pad = _pad_desc(more_nums)
    width = max(len(few_pad), len(more_pad))
    few_pad = few_pad + [0.0] * (width - len(few_pad))
    more_pad = more_pad + [0.0] * (width - len(more_pad))
    numbers_greater = bool(width) and more_pad > few_pad

    few_lpad = _pad_desc(few_lens)
    more_lpad = _pad_desc(more_lens)
    lwidth = max(len(few_lpad), len(more_lpad))
    few_lpad = few_lpad + [0.0] * (lwidth - len(few_lpad))
    more_lpad = more_lpad + [0.0] * (lwidth - len(more_lpad))
    lengths_greater = bool(lwidth) and more_lpad > few_lpad
    ids_greater = more_ids > few_ids
    print(
        f"[F10] counts numbers fewer={few_pad!r} more={more_pad!r} "
        f"lengths fewer={few_lpad!r} more={more_lpad!r} "
        f"{rule_id} fewer={few_ids} more={more_ids}",
        flush=True,
    )
    assert numbers_greater or lengths_greater or ids_greater, (
        "structured lint did not report a greater count on the more-findings "
        f"arm; numbers fewer={few_pad!r} more={more_pad!r}; "
        f"array lengths fewer={few_lpad!r} more={more_lpad!r}; "
        f"{rule_id} occurrences fewer={few_ids} more={more_ids}"
    )


_DROP = object()


def _carries_mbg_identifier(obj: Any) -> bool:
    if isinstance(obj, str):
        return any(rule_id in obj for rule_id in MBG_RULE_IDS)
    if isinstance(obj, Mapping):
        strings = structured_strings(obj)
        return any(_rule_in_strings(strings, rule_id) for rule_id in MBG_RULE_IDS)
    return False


def drop_mbg_finding_records(obj: Any, *, is_root: bool = True) -> Any:
    """Remove finding records (nodes that carry MBG-001–MBG-005 identifiers).

    The root object is kept even when it contains those identifiers nested
    under findings. Unclassified values raise; they are never mapped to
    absence.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Mapping):
        if not is_root and _carries_mbg_identifier(obj):
            return _DROP
        out: dict[Any, Any] = {}
        for key, value in obj.items():
            if not isinstance(key, (str, int, float, bool)) and key is not None:
                raise HarnessError(
                    f"unclassified structured mapping key while dropping "
                    f"findings: {type(key).__name__}"
                )
            kept = drop_mbg_finding_records(value, is_root=False)
            if kept is _DROP:
                continue
            out[key] = kept
        return out
    if isinstance(obj, Sequence) and not isinstance(obj, (bytes, bytearray)):
        kept_items: list[Any] = []
        for item in obj:
            if isinstance(item, str) and _carries_mbg_identifier(item):
                continue
            kept = drop_mbg_finding_records(item, is_root=False)
            if kept is _DROP:
                continue
            kept_items.append(kept)
        return kept_items
    raise HarnessError(
        f"unclassified structured value while dropping findings: "
        f"{type(obj).__name__}: {obj!r}"
    )


def token_statistics_grouping(payload: Any) -> Any:
    """Structured leftover after finding records are removed (L301 grouping).

    Pass/fail and counts stay in the tree so two same-file runs that differ
    only in caller cap share them; the leftover grouping still has to report
    the in-force cap, the exceeded mark, and an estimate.
    """
    grouping = drop_mbg_finding_records(payload)
    print(
        f"[F10] token-statistics grouping after findings dropped="
        f"{grouping!r}",
        flush=True,
    )
    return grouping


def grouping_integers(obj: Any) -> list[int]:
    """Sortable integers in a structured leftover grouping."""
    found = [int(v) for v in _walk_values(obj, want=int)]
    print(f"[F10] grouping integers={found!r}", flush=True)
    return found


def grouping_booleans(obj: Any) -> list[bool]:
    """Two-state boolean values in a structured leftover grouping."""
    found = [bool(v) for v in _walk_values(obj, want=bool)]
    print(f"[F10] grouping booleans={found!r}", flush=True)
    return found


def payload_has_mbg_findings(payload: Any) -> bool:
    strings = structured_strings(payload)
    return any(_rule_in_strings(strings, rule_id) for rule_id in MBG_RULE_IDS)


def payload_reports_mbg005(payload: Any) -> bool:
    return _rule_in_strings(structured_strings(payload), "MBG-005")


def count_finding_records(obj: Any, *, is_root: bool = True) -> int:
    """How many finding records (nodes carrying MBG-001–MBG-005) sit under *obj*."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return 0
    if isinstance(obj, Mapping):
        if not is_root and _carries_mbg_identifier(obj):
            return 1
        return sum(count_finding_records(v, is_root=False) for v in obj.values())
    if isinstance(obj, Sequence) and not isinstance(obj, (bytes, bytearray)):
        total = 0
        for item in obj:
            if isinstance(item, str) and _carries_mbg_identifier(item):
                total += 1
            else:
                total += count_finding_records(item, is_root=False)
        return total
    raise HarnessError(
        f"unclassified structured value while counting findings: "
        f"{type(obj).__name__}: {obj!r}"
    )


_PATHISH = re.compile(r"[/\\]|\.md$", re.IGNORECASE)
_PASS_STRINGS = frozenset({"pass", "passed", "ok", "success", "true"})
_FAIL_STRINGS = frozenset({"fail", "failed", "failure", "error", "false"})


def _as_int_leaf(value: int | float) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _collect_leaves(obj: Any) -> Counter[tuple[str, Any]]:
    """Typed leftover leaves. Path-like strings and MBG identifiers are covariates."""
    found: Counter[tuple[str, Any]] = Counter()

    def walk(value: Any) -> None:
        if isinstance(value, bool):
            found[("bool", value)] += 1
            return
        as_int = _as_int_leaf(value) if isinstance(value, (int, float)) else None
        if as_int is not None:
            found[("int", as_int)] += 1
            return
        if isinstance(value, float):
            found[("float", float(value))] += 1
            return
        if isinstance(value, str):
            text = value
            for rule_id in sorted(MBG_RULE_IDS, key=len, reverse=True):
                text = text.replace(rule_id, "")
            text = text.strip()
            if not text or _PATHISH.search(text):
                return
            found[("str", text)] += 1
            return
        if value is None:
            return
        if isinstance(value, Mapping):
            for nested in value.values():
                walk(nested)
            return
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            for item in value:
                walk(item)
            return
        raise HarnessError(
            f"unclassified structured value while collecting leftover leaves: "
            f"{type(value).__name__}: {value!r}"
        )

    walk(obj)
    return found


def _drop_one(leaves: Counter[tuple[str, Any]], leaf: tuple[str, Any]) -> None:
    if leaves[leaf] <= 0:
        return
    leaves[leaf] -= 1
    if leaves[leaf] <= 0:
        del leaves[leaf]


def leftover_grouping_two_state(
    payload: Any,
    *,
    caps: Sequence[int] = (),
    drop_pass_fail: bool = True,
) -> Counter[tuple[str, Any]]:
    """Leftover grouping leaves after findings, optional pass/fail, counts, and caps.

    Field names and exceeded-mark encoding are not pinned. Path-like strings
    and MBG identifiers are stripped as covariates. A leftover boolean that is
    not the mark stays in the bag on every arm and cannot by itself create a
    difference that tracks MBG-005.
    """
    grouping = token_statistics_grouping(payload)
    leaves = _collect_leaves(grouping)
    passed = not payload_has_mbg_findings(payload)
    finding_count = count_finding_records(payload)
    if drop_pass_fail:
        if leaves[("bool", passed)] > 0:
            _drop_one(leaves, ("bool", passed))
        elif leaves[("int", 1 if passed else 0)] > 0:
            _drop_one(leaves, ("int", 1 if passed else 0))
        else:
            wanted = _PASS_STRINGS if passed else _FAIL_STRINGS
            for key in list(leaves):
                kind, text = key
                if kind == "str" and str(text).strip().lower() in wanted:
                    _drop_one(leaves, key)
                    break
    _drop_one(leaves, ("int", finding_count))
    for cap in caps:
        while leaves[("int", int(cap))] > 0:
            _drop_one(leaves, ("int", int(cap)))
    print(
        f"[F10] leftover two-state passed={passed} finding_count={finding_count} "
        f"caps={list(caps)!r} leaves={dict(leaves)!r}",
        flush=True,
    )
    return leaves


def _drop_unique_non_mark_ints(
    left: Counter[tuple[str, Any]],
    right: Counter[tuple[str, Any]],
) -> tuple[Counter[tuple[str, Any]], Counter[tuple[str, Any]]]:
    """Drop sortable integers unique to one arm, keeping 0/1 as possible two-states."""
    left = left.copy()
    right = right.copy()
    left_ints = {value for kind, value in left if kind == "int"}
    right_ints = {value for kind, value in right if kind == "int"}
    for number in left_ints - right_ints:
        if number in (0, 1):
            continue
        del left[("int", number)]
    for number in right_ints - left_ints:
        if number in (0, 1):
            continue
        del right[("int", number)]
    left_floats = {value for kind, value in left if kind == "float"}
    right_floats = {value for kind, value in right if kind == "float"}
    for number in left_floats - right_floats:
        del left[("float", number)]
    for number in right_floats - left_floats:
        del right[("float", number)]
    return left, right


def assert_in_force_cap_differs(
    omit_payload: Any,
    cap20_payload: Any,
    *,
    also_400: Sequence[Any] = (),
) -> None:
    """Same-file leftover grouping reports in-force cap 400 vs 20 (L301/L316).

    After findings are removed, omit (and each non-positive / explicit-400
    twin) still contains sortable integer 400, the cap-20 run contains 20,
    and the two integer bags differ. Shared counts and the estimate cancel
    across the same file; dummy bags that always contain both 400 and 20
    do not differ.
    """
    omit_g = token_statistics_grouping(omit_payload)
    cap20_g = token_statistics_grouping(cap20_payload)
    omit_ints = set(grouping_integers(omit_g))
    cap20_ints = set(grouping_integers(cap20_g))
    print(
        f"[F10] in-force cap omit_ints={sorted(omit_ints)!r} "
        f"cap20_ints={sorted(cap20_ints)!r}",
        flush=True,
    )
    assert 400 in omit_ints, (
        "structured leftover grouping after removing findings does not "
        f"report in-force cap 400 when the caller omits the cap: "
        f"{sorted(omit_ints)!r}"
    )
    assert 20 in cap20_ints, (
        "structured leftover grouping after removing findings does not "
        f"report in-force cap 20 when the caller supplies 20: "
        f"{sorted(cap20_ints)!r}"
    )
    assert omit_ints != cap20_ints, (
        "two structured runs of the same file that differ only in the "
        "caller cap did not differ in the reported in-force cap; "
        f"both={sorted(omit_ints)!r}"
    )
    for extra in also_400:
        extra_ints = set(grouping_integers(token_statistics_grouping(extra)))
        assert 400 in extra_ints, (
            "structured leftover grouping does not report in-force cap 400 "
            f"for a non-positive or explicit-400 caller cap: "
            f"{sorted(extra_ints)!r}"
        )
    shared = (omit_ints & cap20_ints) - {0, 1}
    print(f"[F10] estimate-presence shared non-count ints={sorted(shared)!r}", flush=True)
    assert shared, (
        "structured leftover grouping after removing findings does not "
        "report a working-memory estimate as a sortable integer (presence); "
        f"omit={sorted(omit_ints)!r} cap20={sorted(cap20_ints)!r}"
    )


def assert_exceeded_mark_matches_mbg005(
    under_clean: Any,
    under_other_fail: Any,
    over_mbg005: Any,
    *,
    caps: Sequence[int] = (20, 400),
) -> None:
    """Leftover grouping two-state matches MBG-005 presence (encoding open).

    After pass/fail, counts, findings, in-force cap integers, and unique
    estimate integers are stripped, the two MBG-005-absent arms match each
    other and differ from the MBG-005-present arm. A leftover boolean that
    is not the mark is the same on every arm and cannot satisfy this.
    Boolean, string, and 0/1 integer encodings of the mark all remain.
    """
    assert not payload_reports_mbg005(under_clean), (
        "under-budget clean arm unexpectedly reports MBG-005"
    )
    assert not payload_reports_mbg005(under_other_fail), (
        "under-budget non-MBG-005 fail arm unexpectedly reports MBG-005"
    )
    assert payload_reports_mbg005(over_mbg005), (
        "over-budget arm does not report MBG-005 among findings"
    )
    clean = leftover_grouping_two_state(under_clean, caps=caps, drop_pass_fail=True)
    other = leftover_grouping_two_state(
        under_other_fail, caps=caps, drop_pass_fail=True
    )
    over = leftover_grouping_two_state(over_mbg005, caps=caps, drop_pass_fail=True)
    clean_vs_other, other_vs_clean = _drop_unique_non_mark_ints(clean, other)
    print(
        f"[F10] exceeded two-state clean={dict(clean_vs_other)!r} "
        f"other={dict(other_vs_clean)!r}",
        flush=True,
    )
    assert clean_vs_other == other_vs_clean, (
        "under-budget leftover grouping two-state differs between a clean "
        "run and an MBG-001 (non-MBG-005) failure after findings, pass/fail, "
        f"counts, and caps are removed; clean={dict(clean_vs_other)!r} "
        f"other={dict(other_vs_clean)!r}"
    )
    clean_vs_over, over_vs_clean = _drop_unique_non_mark_ints(clean, over)
    other_vs_over, over_vs_other = _drop_unique_non_mark_ints(other, over)
    print(
        f"[F10] exceeded two-state vs over clean={dict(clean_vs_over)!r} "
        f"other={dict(other_vs_over)!r} over={dict(over_vs_clean)!r}",
        flush=True,
    )
    assert clean_vs_over != over_vs_clean, (
        "two structured runs that differ in whether the estimate exceeds "
        "the cap did not differ in the leftover grouping two-state matching "
        f"MBG-005 presence; both={dict(clean_vs_over)!r}"
    )
    assert other_vs_over != over_vs_other, (
        "leftover grouping two-state does not match MBG-005 presence: an "
        "MBG-001 failure and an MBG-005 failure left the same mark after "
        f"findings, pass/fail, counts, and caps are removed; "
        f"both={dict(other_vs_over)!r}"
    )


def assert_structured_pass_fail_distinct(pass_payload: Any, fail_payload: Any) -> None:
    """Structured pass/fail is a JSON field, not findings ids or process exit.

    After finding records and the matching error-count integer are removed
    from the parsed payloads (returncode is never consulted), a two-state
    leftover still differs between a passing structured run and a failing
    one. Unique estimate integers and in-force caps are stripped so the
    remaining difference cannot be token statistics.
    """
    assert not payload_has_mbg_findings(pass_payload), (
        "pass arm still reports an MBG identifier; cannot isolate pass/fail"
    )
    assert payload_has_mbg_findings(fail_payload), (
        "fail arm reports no MBG identifier; cannot isolate pass/fail"
    )
    passed = leftover_grouping_two_state(
        pass_payload, caps=(20, 400), drop_pass_fail=False
    )
    failed = leftover_grouping_two_state(
        fail_payload, caps=(20, 400), drop_pass_fail=False
    )
    passed_cmp, failed_cmp = _drop_unique_non_mark_ints(passed, failed)
    print(
        f"[F10] structured pass/fail pass={dict(passed_cmp)!r} "
        f"fail={dict(failed_cmp)!r}",
        flush=True,
    )
    assert passed_cmp != failed_cmp, (
        "structured leftover after findings and counts are removed does not "
        "still differ in pass/fail (distinct from findings identifiers and "
        f"from process exit); pass={dict(passed_cmp)!r} fail={dict(failed_cmp)!r}"
    )


def _root_integer_counts(obj: Any) -> Counter[int]:
    """Sortable integers at the leftover root, not inside nested groupings."""
    if not isinstance(obj, Mapping):
        raise HarnessError(
            "structured leftover after findings is not a mapping: "
            f"{type(obj).__name__}: {obj!r}"
        )
    found: Counter[int] = Counter()
    for value in obj.values():
        if isinstance(value, bool):
            continue
        as_int = _as_int_leaf(value) if isinstance(value, (int, float)) else None
        if as_int is not None:
            found[as_int] += 1
    print(f"[F10] root leftover integers={dict(found)!r}", flush=True)
    return found


def _nested_integer_counts(obj: Any) -> Counter[int]:
    """Sortable integers sitting inside nested leftover mappings (token statistics)."""
    if not isinstance(obj, Mapping):
        raise HarnessError(
            "structured leftover after findings is not a mapping: "
            f"{type(obj).__name__}: {obj!r}"
        )
    found: Counter[int] = Counter()
    for value in obj.values():
        if isinstance(value, Mapping):
            for number in grouping_integers(value):
                found[int(number)] += 1
            continue
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                if isinstance(item, Mapping):
                    for number in grouping_integers(item):
                        found[int(number)] += 1
    print(f"[F10] nested leftover integers={dict(found)!r}", flush=True)
    return found


def _root_has_bool(obj: Any) -> bool:
    if not isinstance(obj, Mapping):
        return False
    return any(isinstance(value, bool) for value in obj.values())


def _drop_one_int(bag: Counter[int], number: int) -> None:
    if bag[number] <= 0:
        return
    bag[number] -= 1
    if bag[number] <= 0:
        del bag[number]


def _warning_count_bag(
    grouping: Any,
    *,
    finding_count: int,
    payload: Any,
    caps: Sequence[int],
    max_finding: int,
) -> Counter[int]:
    """Leftover root integers after error/finding count, pass/fail, and token stats."""
    bag = _root_integer_counts(grouping)
    nested = _nested_integer_counts(grouping)
    _drop_one_int(bag, int(finding_count))
    if not _root_has_bool(grouping):
        passed = not payload_has_mbg_findings(payload)
        _drop_one_int(bag, 1 if passed else 0)
    for number, count in list(nested.items()):
        remaining = int(count)
        while bag[int(number)] > 0 and remaining > 0:
            _drop_one_int(bag, int(number))
            remaining -= 1
    for cap in caps:
        while bag[int(cap)] > 0:
            _drop_one_int(bag, int(cap))
    for number in list(bag):
        if int(number) > int(max_finding):
            del bag[number]
    print(f"[F10] warning-count bag={dict(bag)!r}", flush=True)
    return bag


def assert_warning_count_unchanged_when_errors_increase(
    fewer: Any,
    more: Any,
    *,
    caps: Sequence[int] = (400, 20),
) -> None:
    """Warning count stays put while the error/finding count increases (L301).

    After findings are removed, a warning count remains as a distinct
    observable from the error/finding count. When MBG findings fire they
    increment the error side and not the warning side. Zero warning is
    allowed. Field names are not pinned. Nested token-statistics integers,
    leftover booleans, an exclusive remainder, and a 400-versus-20 echo
    are not that count.
    """
    few_n = count_finding_records(fewer)
    more_n = count_finding_records(more)
    print(
        f"[F10] warning-vs-error finding_count fewer={few_n} more={more_n}",
        flush=True,
    )
    assert more_n > few_n, (
        "more-findings arm does not have more MBG finding records than the "
        f"fewer-findings arm; fewer={few_n} more={more_n}"
    )
    few_g = token_statistics_grouping(fewer)
    more_g = token_statistics_grouping(more)
    few_root = _root_integer_counts(few_g)
    more_root = _root_integer_counts(more_g)
    assert few_root[int(few_n)] > 0, (
        "structured leftover after findings are removed has no error/finding "
        f"count matching {few_n} on the fewer-findings arm; root={dict(few_root)!r}"
    )
    assert more_root[int(more_n)] > 0, (
        "structured leftover after findings are removed has no error/finding "
        f"count matching {more_n} on the more-findings arm; root={dict(more_root)!r}"
    )
    few_warn = _warning_count_bag(
        few_g,
        finding_count=few_n,
        payload=fewer,
        caps=caps,
        max_finding=more_n,
    )
    more_warn = _warning_count_bag(
        more_g,
        finding_count=more_n,
        payload=more,
        caps=caps,
        max_finding=more_n,
    )
    print(
        f"[F10] warning bags fewer={dict(few_warn)!r} more={dict(more_warn)!r}",
        flush=True,
    )
    assert few_warn == more_warn, (
        "warning count changed when MBG error/finding count increased; "
        f"fewer={dict(few_warn)!r} more={dict(more_warn)!r}"
    )
    assert sum(few_warn.values()) > 0, (
        "structured leftover after findings, error/finding count, pass/fail, "
        "and token-statistics integers are removed has no warning count "
        "distinct from the error/finding count; "
        f"fewer root={dict(few_root)!r} more root={dict(more_root)!r}"
    )


def _leftover_estimate_integers(
    payload: Any, *, shared_caps: Sequence[int]
) -> set[int]:
    leaves = leftover_grouping_two_state(
        payload, caps=shared_caps, drop_pass_fail=True
    )
    found = {
        int(value)
        for (kind, value), count in leaves.items()
        if kind == "int" and int(value) not in (0, 1) and count > 0
    }
    print(f"[F10] leftover estimate integers={sorted(found)!r}", flush=True)
    return found


def assert_working_memory_estimate_sorts_below(
    inner_payload: Any,
    whole_payload: Any,
    *,
    shared_caps: Sequence[int] = (20,),
) -> None:
    """Well-formed-delimiter leftover estimate sorts strictly below whole-file.

    After pass/fail, counts, findings, the shared cap, and 0/1 are removed,
    the leftover grouping's working-memory estimate (a sortable integer;
    exact value not scored) for the begin-then-end run of the same
    huge-prefix file must sort strictly below the omitted-delimiter
    whole-file run. Extra comment-line bytes cannot produce that order on
    a whole-file-only estimator.
    """
    inner_rest = _leftover_estimate_integers(
        inner_payload, shared_caps=shared_caps
    )
    whole_rest = _leftover_estimate_integers(
        whole_payload, shared_caps=shared_caps
    )
    shared = inner_rest & whole_rest
    inner_only = inner_rest - shared
    whole_only = whole_rest - shared
    print(
        f"[F10] estimate order inner_only={sorted(inner_only)!r} "
        f"whole_only={sorted(whole_only)!r} shared={sorted(shared)!r}",
        flush=True,
    )
    assert inner_only and whole_only, (
        "leftover grouping working-memory estimate (sortable integer, exact "
        "value not scored) does not differ between the well-formed-delimiter "
        "run and the otherwise-whole-file run after removing pass/fail, "
        "counts, findings, the shared cap, and 0/1; "
        f"inner={sorted(inner_rest)!r} whole={sorted(whole_rest)!r}"
    )
    assert max(inner_only) < min(whole_only), (
        "leftover grouping working-memory estimate for the well-formed "
        "begin-then-end run does not sort strictly below the omitted-delimiter "
        "whole-file run; extra comment-line bytes cannot produce that order "
        "on a whole-file-only estimator; "
        f"inner_only={sorted(inner_only)!r} whole_only={sorted(whole_only)!r}"
    )
