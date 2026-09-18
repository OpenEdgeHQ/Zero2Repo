"""Per-case upstream denylist: L3 install shims and L4 static scan."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .submit import CONTAINER_SUBMIT_PATH, SUBMIT_TOKEN

__all__ = [
    "DenylistSpec",
    "ImportHit",
    "InstalledHit",
    "ScanResult",
    "CONTAINER_DENYLIST_HASHES_PATH",
    "DEFAULT_FIX_RETRIES",
    "GITHUB_BLOCK_HOSTS",
    "build_fix_instruction",
    "install_ban_hashes",
    "FORBIDDEN_IMPORT_BAN",
    "MissingDenylist",
    "load_denylist",
    "require_denylist",
    "normalize_pkg_name",
    "render_pip_shim",
    "render_conda_shim",
    "line_imports_token",
    "scan_workspace_imports",
    "validate_denylist_artifact",
    "validate_denylist_payload",
    "import_root_from_ban_token",
    "import_roots_from_ban_tokens",
    "is_command_like_token",
    "is_probeable_import_root",
    "denylist_hashes_from_payload",
    "render_strip_script",
    "render_npm_shim",
    "render_pip_module_hook",
    "probe_spec_from_payload",
    "probe_banned_imports",
    "log_probe_result",
    "ALLOWED_JUDGE_BANS",
]

ALLOWED_JUDGE_BANS = frozenset(
    {"socket", "subprocess", "network", "filesystem_outside_workspace"}
)

CONTAINER_DENYLIST_HASHES_PATH = "/opt/cbrun/denylist.hashes"
CONTAINER_STRIP_SCRIPT_PATH = "/opt/cbrun/strip_banned.py"
CONTAINER_PIP_HOOK_PATH = "/opt/cbrun/cbrun_denylist_hook.py"
SHIM_BIN_DIR = "/opt/cbrun/bin"
PIP_BLOCK_CMDS = frozenset({"install", "i", "add", "download", "wheel"})
_PROBEABLE_ROOT = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_VERSION_ROOT = re.compile(r"^v\d+$")
_COMMAND_LIKE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HEADER_SUFFIXES = (".h", ".hh", ".hpp", ".hxx", ".cpp", ".cc", ".cxx")
DEFAULT_FIX_RETRIES = 1

GITHUB_BLOCK_HOSTS = (
    "github.com",
    "www.github.com",
    "api.github.com",
    "codeload.github.com",
    "gist.github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
)

# Scan only source-like files under /app.
_SOURCE_SUFFIXES = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".cu",
    ".cuh",
    ".cpp",
    ".cc",
    ".cxx",
    ".h",
    ".hpp",
    ".hh",
    ".rs",
    ".go",
    ".java",
    ".cs",
    ".rb",
    ".php",
    ".dart",
    ".swift",
    ".kt",
    ".scala",
    ".sh",
    ".bash",
    ".zsh",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".md",
}

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".tox",
}

# import_ban must target the upstream *product* under test, not general toolchain/stdlib
# layers that the Interface Contract may explicitly allow (e.g. libcu++ ``cuda::`` on CUDA cases).
FORBIDDEN_IMPORT_BAN = frozenset(
    {
        "cuda::",
        "cuda/",
        "std::",
        "numpy",
        "numpy/",
        "torch",
        "torch::",
    }
)


def validate_denylist_payload(payload: dict) -> list[str]:
    """Return policy violations for a denylist.json object (empty if OK)."""
    errors: list[str] = []
    case_id = str(payload.get("case_id") or "?")
    for token in payload.get("import_ban") or []:
        text = str(token).strip()
        if not text:
            errors.append(f"{case_id}: import_ban contains empty token")
            continue
        if text in FORBIDDEN_IMPORT_BAN:
            errors.append(
                f"{case_id}: import_ban must not include general infrastructure token {text!r}"
            )
    return errors


def _normalize_identity_fragment(text: str) -> str:
    """Loose normalization for overlap checks between ban tokens and case identity."""
    t = str(text).strip().lower().rstrip(":").rstrip("/")
    t = t.replace("_", "-").replace(".", "-")
    t = re.sub(r"[^a-z0-9-]+", "-", t)
    while "--" in t:
        t = t.replace("--", "-")
    return t.strip("-")


def _ban_token_matches_identity(token: str, manifest: dict) -> bool:
    """True when a ban token plausibly targets this case's upstream product identity."""
    norm = _normalize_identity_fragment(token)
    if len(norm) < 3:
        return False

    hay: set[str] = set()
    for term in manifest.get("sensitive_terms") or []:
        hay.add(_normalize_identity_fragment(term))
    for key in ("repo_slug", "repository_url", "case_id"):
        value = manifest.get(key)
        if value:
            hay.add(_normalize_identity_fragment(str(value)))
    init = manifest.get("init_metadata") or {}
    for key in ("suggested_neutral_name", "tech_stack"):
        value = init.get(key)
        if value:
            hay.add(_normalize_identity_fragment(str(value)))

    for h in hay:
        if len(h) < 3:
            continue
        if norm in h or h in norm:
            return True

    for part in re.split(r"[/\\:]+", str(token).lower()):
        part_norm = _normalize_identity_fragment(part)
        if len(part_norm) < 3:
            continue
        for h in hay:
            if len(h) < 3:
                continue
            if part_norm in h or h in part_norm:
                return True
    return False


def validate_denylist_artifact(
    payload: dict,
    manifest: dict,
    *,
    case_id: str | None = None,
) -> list[str]:
    """Shape + policy + identity overlap checks for a Stage G denylist.json artifact."""
    errors = list(validate_denylist_payload(payload))
    cid = str(payload.get("case_id") or case_id or "?")
    expected_case = case_id or str(manifest.get("case_id") or "")

    if int(payload.get("schema_version") or 0) != 1:
        errors.append(f"{cid}: schema_version must be 1")
    if expected_case and payload.get("case_id") != expected_case:
        errors.append(f"{cid}: case_id must be {expected_case!r}")
    if not str(payload.get("ecosystem") or "").strip():
        errors.append(f"{cid}: ecosystem is required")

    install = [str(x).strip() for x in (payload.get("install_ban") or []) if str(x).strip()]
    imports = [str(x).strip() for x in (payload.get("import_ban") or []) if str(x).strip()]
    if not install and not imports:
        errors.append(f"{cid}: at least one install_ban or import_ban token required")

    bans = install + imports
    if bans and not any(_ban_token_matches_identity(token, manifest) for token in bans):
        errors.append(
            f"{cid}: no denylist token overlaps case identity metadata "
            "(sensitive_terms / repo identity)"
        )
    return errors


_PY_SUFFIXES = {".py", ".pyi"}
_JS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
_C_SUFFIXES = {".c", ".h", ".hpp", ".hh", ".cc", ".cxx", ".cpp", ".cu", ".cuh"}
_HASH_COMMENT_SUFFIXES = _PY_SUFFIXES | {".rb", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml"}
_SLASH_COMMENT_SUFFIXES = (
    _JS_SUFFIXES | _C_SUFFIXES | {".java", ".kt", ".scala", ".cs", ".go", ".rs", ".swift", ".dart"}
)


def _strip_hash_or_slash_comment(line: str, *, slash: bool, hash_comment: bool) -> str:
    """Drop trailing comments; keep string literals so import specifiers stay visible."""
    stripped = line.strip()
    if not stripped:
        return ""
    if hash_comment and stripped.startswith("#"):
        return ""
    if slash and stripped.startswith("//"):
        return ""
    out: list[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    idx = 0
    while idx < len(line):
        ch = line[idx]
        if ch == "'" and not in_double and not in_backtick:
            in_single = not in_single
        elif ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
        elif ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
        elif not in_single and not in_double and not in_backtick:
            if hash_comment and ch == "#":
                break
            if slash and line.startswith("//", idx):
                break
        out.append(ch)
        idx += 1
    return "".join(out)


def _strip_quoted_spans(text: str) -> str:
    """Replace quoted spans with spaces so leftover tokens are real code."""
    out: list[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    for ch in text:
        if ch == "'" and not in_double and not in_backtick:
            in_single = not in_single
            out.append(" ")
            continue
        if ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
            out.append(" ")
            continue
        if ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            out.append(" ")
            continue
        out.append(" " if (in_single or in_double or in_backtick) else ch)
    return "".join(out)


def _comment_mode(suffix: str) -> tuple[bool, bool]:
    hash_comment = suffix in _HASH_COMMENT_SUFFIXES
    slash = suffix in _SLASH_COMMENT_SUFFIXES
    if suffix in {".php"}:
        hash_comment = True
        slash = True
    return hash_comment, slash


def _code_minus_comments(line: str, suffix: str) -> str:
    hash_comment, slash = _comment_mode(suffix)
    return _strip_hash_or_slash_comment(line, slash=slash, hash_comment=hash_comment)


def _python_imports_token(code: str, token: str) -> bool:
    pattern = rf"(?:^|;)\s*(?:import|from)\s+(?:[A-Za-z_][\w]*\.)*{re.escape(token)}\b"
    return re.search(pattern, code) is not None


def _js_imports_token(code: str, token: str) -> bool:
    base = token.rstrip("/")
    quoted = rf"""['"](?:{re.escape(base)})(?:['"/]|$)"""
    patterns = (
        rf"(?:^|;)\s*import\s+(?:[^'\"\n]+?\s+from\s+)?{quoted}",
        rf"(?:^|;)\s*export\s+(?:[^'\"\n]+?\s+from\s+){quoted}",
        rf"\brequire\s*\(\s*{quoted}",
        rf"\bimport\s*\(\s*{quoted}",
    )
    return any(re.search(p, code) for p in patterns)


def _go_imports_token(code: str, token: str) -> bool:
    base = token.rstrip("/")
    return re.search(rf"""(?:^|;)\s*import\s+(?:\w+\s+)?["`](?:{re.escape(base)})""", code) is not None


def _rust_imports_token(code: str, token: str) -> bool:
    return (
        re.search(rf"(?:^|;)\s*(?:use|extern\s+crate)\s+{re.escape(token)}\b", code) is not None
    )


def _jvm_imports_token(code: str, token: str) -> bool:
    return re.search(rf"(?:^|;)\s*import\s+(?:static\s+)?{re.escape(token)}[.;]", code) is not None


def _c_includes_token(code: str, token: str) -> bool:
    base = token.rstrip("/")
    return re.search(rf"""#\s*include\s*[<"]{re.escape(base)}""", code) is not None


def _ruby_imports_token(code: str, token: str) -> bool:
    base = token.rstrip("/")
    quoted = rf"""['"](?:{re.escape(base)})(?:['"/]|$)"""
    return re.search(rf"\b(?:require|require_relative)\s*\(?\s*{quoted}", code) is not None


def _php_imports_token(code: str, token: str) -> bool:
    if re.search(rf"(?:^|;)\s*use\s+{re.escape(token)}\b", code):
        return True
    return _ruby_imports_token(code, token)


def _csharp_imports_token(code: str, token: str) -> bool:
    return re.search(rf"(?:^|;)\s*using\s+{re.escape(token)}\b", code) is not None


def _path_import_hit(code: str, token: str) -> bool:
    if token not in code:
        return False
    return bool(
        re.search(
            rf"""(?:import|from|require|require_relative|include|use)\b.*{re.escape(token)}""",
            code,
        )
    )


def line_imports_token(line: str, token: str, suffix: str = ".py") -> bool:
    """True when *line* is a real import/require/use of *token*, not prose."""
    code = _code_minus_comments(line, suffix)
    if not code.strip():
        return False
    if token.endswith("::"):
        return token in _strip_quoted_spans(code)
    if token.endswith("/") or "\\" in token:
        return _path_import_hit(code, token)
    ext = suffix.lower()
    if ext in _PY_SUFFIXES:
        return _python_imports_token(code, token)
    if ext in _JS_SUFFIXES:
        return _js_imports_token(code, token)
    if ext == ".go":
        return _go_imports_token(code, token)
    if ext == ".rs":
        return _rust_imports_token(code, token)
    if ext in {".java", ".kt", ".scala"}:
        return _jvm_imports_token(code, token)
    if ext in _C_SUFFIXES:
        return _c_includes_token(code, token)
    if ext == ".rb":
        return _ruby_imports_token(code, token)
    if ext == ".php":
        return _php_imports_token(code, token)
    if ext == ".cs":
        return _csharp_imports_token(code, token)
    if ext in {".dart", ".swift"}:
        return _jvm_imports_token(code, token) or _js_imports_token(code, token)
    # Unknown / data files: only structured import forms, never a bare word.
    return (
        _python_imports_token(code, token)
        or _js_imports_token(code, token)
        or _path_import_hit(code, token)
    )


@dataclass(frozen=True)
class DenylistSpec:
    case_id: str
    ecosystem: str
    install_ban: tuple[str, ...]
    import_ban: tuple[str, ...]
    notes: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.install_ban or self.import_ban)


@dataclass(frozen=True)
class ImportHit:
    token: str
    path: str
    line: int
    line_text: str


@dataclass(frozen=True)
class InstalledHit:
    package: str


@dataclass
class ScanResult:
    import_hits: list[ImportHit] = field(default_factory=list)
    installed_warnings: list[InstalledHit] = field(default_factory=list)

    @property
    def has_hard_violation(self) -> bool:
        return bool(self.import_hits)


def install_ban_hashes(install_ban: tuple[str, ...] | list[str]) -> list[str]:
    """SHA-256 hex digests of normalized install-ban package names (for image baking)."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in install_ban:
        norm = normalize_pkg_name(str(raw))
        if not norm:
            continue
        digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        if digest not in seen:
            seen.add(digest)
            out.append(digest)
    return out


def install_ban_hashes_from_file(denylist_path: Path) -> list[str]:
    if not denylist_path.is_file():
        return []
    data = json.loads(denylist_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    return denylist_hashes_from_payload(data)


def is_probeable_import_root(root: str) -> bool:
    """True when *root* is safe to pass to find_spec / require.resolve / rmdir."""
    text = str(root or "").strip()
    if text.startswith("@") and "/" in text:
        parts = [p for p in text.split("/") if p]
        if len(parts) != 2:
            return False
        scoped = parts[0][1:] if parts[0].startswith("@") else parts[0]
        return is_probeable_import_root(scoped) and is_probeable_import_root(parts[1])
    if len(text) < 3:
        return False
    if not _PROBEABLE_ROOT.fullmatch(text):
        return False
    if _VERSION_ROOT.fullmatch(text):
        return False
    return True


def is_command_like_token(token: str) -> bool:
    """True when *token* may be a PATH binary (not a header or C++ qualifier)."""
    text = str(token or "").strip().rstrip("/")
    if not text or "/" in text or "::" in text:
        return False
    if any(text.endswith(suf) for suf in _HEADER_SUFFIXES):
        return False
    return bool(_COMMAND_LIKE.fullmatch(text))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def denylist_hashes_from_payload(payload: dict) -> list[str]:
    """Hashes for install_ban names plus probeable import roots / raw filenames."""
    seen: set[str] = set()
    out: list[str] = []

    def add(text: str) -> None:
        value = str(text or "").strip()
        if not value:
            return
        digest = _hash_text(value)
        if digest not in seen:
            seen.add(digest)
            out.append(digest)

    for raw in payload.get("install_ban") or []:
        norm = normalize_pkg_name(str(raw))
        if norm:
            add(norm)
    for raw in payload.get("import_ban") or []:
        token = str(raw).strip()
        if not token:
            continue
        add(token.lower().rstrip("/"))
        base = Path(token).name.lower()
        if base:
            add(base)
        root = import_root_from_ban_token(token)
        if root and is_probeable_import_root(root):
            add(root.lower())
            add(normalize_pkg_name(root))
    return out


def normalize_pkg_name(name: str) -> str:
    """PEP 503-ish normalization for pip/conda package names."""
    text = name.strip().lower()
    text = text.split("[", 1)[0]  # extras
    text = text.split("@", 1)[0]  # direct URL
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.replace("_", "-").replace(".", "-")


def load_denylist(case_dir: Path | str) -> DenylistSpec | None:
    path = Path(case_dir) / "source" / "denylist.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    install = tuple(str(x) for x in (data.get("install_ban") or []) if str(x).strip())
    imports = tuple(str(x) for x in (data.get("import_ban") or []) if str(x).strip())
    if not install and not imports:
        return None
    return DenylistSpec(
        case_id=str(data.get("case_id") or Path(case_dir).name),
        ecosystem=str(data.get("ecosystem") or ""),
        install_ban=install,
        import_ban=imports,
        notes=str(data.get("notes") or ""),
    )


class MissingDenylist(RuntimeError):
    """source/denylist.json is absent or has no ban entries."""


def require_denylist(case_dir: Path | str) -> DenylistSpec:
    """Load the denylist or raise. Missing / empty is not a clean scan."""
    path = Path(case_dir) / "source" / "denylist.json"
    spec = load_denylist(case_dir)
    if spec is not None:
        return spec
    if not path.is_file():
        raise MissingDenylist(
            f"source/denylist.json is missing at {path}. "
            "Every released case tracks this file; restore it from git, "
            "or pass --no-enforce-denylist to skip the scan."
        )
    raise MissingDenylist(
        f"source/denylist.json at {path} has no install_ban or import_ban. "
        "An empty denylist is not a pass. Fix the file or pass "
        "--no-enforce-denylist."
    )


def _normalized_ban_set(spec: DenylistSpec) -> set[str]:
    return {normalize_pkg_name(x) for x in spec.install_ban}


def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        files.append(path)
    return files


def scan_workspace_imports(workspace: Path, spec: DenylistSpec) -> list[ImportHit]:
    hits: list[ImportHit] = []
    if not spec.import_ban:
        return hits
    for file_path in _iter_source_files(workspace):
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        suffix = file_path.suffix.lower()
        for line_no, line in enumerate(lines, start=1):
            for token in spec.import_ban:
                if line_imports_token(line, token, suffix):
                    hits.append(
                        ImportHit(
                            token=token,
                            path=str(file_path),
                            line=line_no,
                            line_text=line.strip()[:200],
                        )
                    )
                    break
    return hits


def scan_installed_warnings(packages: list[str], spec: DenylistSpec) -> list[InstalledHit]:
    if not spec.install_ban:
        return []
    banned = _normalized_ban_set(spec)
    warnings: list[InstalledHit] = []
    seen: set[str] = set()
    for pkg in packages:
        norm = normalize_pkg_name(pkg)
        if norm in banned and norm not in seen:
            seen.add(norm)
            warnings.append(InstalledHit(package=pkg))
    return warnings


def build_fix_instruction(base_instruction: str, hits: list[ImportHit]) -> str:
    lines = [
        base_instruction.rstrip(),
        "",
        "---",
        "",
        "## Denylist violation — fix required before submission",
        "",
        "Your current workspace uses upstream implementations that must be removed.",
        "Implement the required behavior yourself from the PRD and Interface Contract.",
        "Do not install, import, or wrap the upstream product listed below.",
        "",
        "Violations detected:",
        "",
    ]
    for hit in hits:
        lines.append(f"- `{hit.token}` at `{hit.path}` line {hit.line}: `{hit.line_text}`")
    lines.extend(
        [
            "",
            "Remove these upstream dependencies and re-implement the functionality.",
            f"When the fix is complete, write the submit file again at `{CONTAINER_SUBMIT_PATH}` "
            f"with exactly the one-line contents `{SUBMIT_TOKEN}`. Ending the session is not a "
            "submission.",
            "",
        ]
    )
    return "\n".join(lines)


_PIP_SHIM = r"""#!/bin/bash
set -eu
HASHES="/opt/cbrun/denylist.hashes"
SHIM_DIR="/opt/cbrun/bin"
if [[ ! -f "$HASHES" ]]; then
  REAL="$(type -ap pip 2>/dev/null | grep -v "$SHIM_DIR" | head -1 || true)"
  exec "${REAL:-/usr/bin/pip}" "$@"
fi
python3 - "$@" <<'PY'
import hashlib, re, sys
from pathlib import Path

ban = {ln.strip() for ln in Path("/opt/cbrun/denylist.hashes").read_text().splitlines() if ln.strip()}

def norm(name: str) -> str:
    name = name.strip().lower().split("[", 1)[0].split("@", 1)[0]
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    return name.replace("_", "-").replace(".", "-")

def check(name: str) -> None:
    digest = hashlib.sha256(norm(name).encode()).hexdigest()
    if digest in ban:
        print(f"[cbrun denylist] blocked install of upstream package: {name}", file=sys.stderr)
        print("[cbrun denylist] implement this functionality yourself; do not reuse the upstream product.", file=sys.stderr)
        sys.exit(1)

argv = sys.argv[1:]
i = 0
install_cmds = {"install", "i", "add", "download", "wheel"}
while i < len(argv):
    tok = argv[i]
    if tok in install_cmds:
        i += 1
        while i < len(argv):
            arg = argv[i]
            if arg.startswith("-"):
                if arg in ("-r", "--requirement") and i + 1 < len(argv):
                    req = Path(argv[i + 1])
                    if req.is_file():
                        for line in req.read_text().splitlines():
                            line = line.strip()
                            if line and not line.startswith("#"):
                                check(line.split(";", 1)[0].strip())
                    i += 2
                    continue
                i += 1
                continue
            check(arg)
            i += 1
        break
    i += 1
PY
REAL="$(type -ap pip 2>/dev/null | grep -v "$SHIM_DIR" | head -1 || true)"
exec "${REAL:-/usr/bin/pip}" "$@"
"""

_CONDA_SHIM = r"""#!/bin/bash
set -eu
HASHES="/opt/cbrun/denylist.hashes"
SHIM_DIR="/opt/cbrun/bin"
if [[ ! -f "$HASHES" ]]; then
  REAL="$(type -ap conda 2>/dev/null | grep -v "$SHIM_DIR" | head -1 || true)"
  exec "${REAL:-conda}" "$@"
fi
python3 - "$@" <<'PY'
import hashlib, re, sys
from pathlib import Path

ban = {ln.strip() for ln in Path("/opt/cbrun/denylist.hashes").read_text().splitlines() if ln.strip()}

def norm(name: str) -> str:
    name = name.strip().lower().split("[", 1)[0].split("@", 1)[0]
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    return name.replace("_", "-").replace(".", "-")

def check(name: str) -> None:
    digest = hashlib.sha256(norm(name).encode()).hexdigest()
    if digest in ban:
        print(f"[cbrun denylist] blocked install of upstream package: {name}", file=sys.stderr)
        print("[cbrun denylist] implement this functionality yourself; do not reuse the upstream product.", file=sys.stderr)
        sys.exit(1)

argv = sys.argv[1:]
if argv and argv[0] in ("install", "create"):
    for arg in argv[1:]:
        if arg.startswith("-"):
            continue
        check(arg)
PY
REAL="$(type -ap conda 2>/dev/null | grep -v "$SHIM_DIR" | head -1 || true)"
exec "${REAL:-conda}" "$@"
"""

_NPM_SHIM = r"""#!/bin/bash
set -eu
HASHES="/opt/cbrun/denylist.hashes"
SHIM_DIR="/opt/cbrun/bin"
SELF="$(basename "$0")"
if [[ ! -f "$HASHES" ]]; then
  REAL="$(type -ap "$SELF" 2>/dev/null | grep -v "$SHIM_DIR" | head -1 || true)"
  exec "${REAL:-$SELF}" "$@"
fi
python3 - "$@" <<'PY'
import hashlib, re, sys
from pathlib import Path

ban = {ln.strip() for ln in Path("/opt/cbrun/denylist.hashes").read_text().splitlines() if ln.strip()}

def norm(name: str) -> str:
    name = name.strip().lower().split("[", 1)[0]
    if name.startswith("@"):
        return name.split("?", 1)[0]
    name = name.split("@", 1)[0]
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    return name.replace("_", "-").replace(".", "-")

def check(name: str) -> None:
    digest = hashlib.sha256(norm(name).encode()).hexdigest()
    raw = hashlib.sha256(name.strip().lower().encode()).hexdigest()
    if digest in ban or raw in ban:
        print(f"[cbrun denylist] blocked install of upstream package: {name}", file=sys.stderr)
        print("[cbrun denylist] implement this functionality yourself; do not reuse the upstream product.", file=sys.stderr)
        sys.exit(1)

argv = sys.argv[1:]
i = 0
install_cmds = {"install", "i", "add"}
while i < len(argv):
    tok = argv[i]
    if tok in install_cmds:
        i += 1
        while i < len(argv):
            arg = argv[i]
            if arg.startswith("-"):
                i += 1
                continue
            check(arg)
            i += 1
        break
    i += 1
PY
REAL="$(type -ap "$SELF" 2>/dev/null | grep -v "$SHIM_DIR" | head -1 || true)"
exec "${REAL:-$SELF}" "$@"
"""

_STRIP_SCRIPT = r'''#!/usr/bin/env python3
"""Remove image artefacts whose names hash to the denylist set."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HASHES = Path(os.environ.get("CBRUN_DENYLIST_HASHES", "/opt/cbrun/denylist.hashes"))


def _norm(name: str) -> str:
    text = name.strip().lower().split("[", 1)[0].split("@", 1)[0]
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.replace("_", "-").replace(".", "-")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_ban() -> set[str]:
    if not HASHES.is_file():
        return set()
    return {ln.strip() for ln in HASHES.read_text(encoding="utf-8").splitlines() if ln.strip()}


BAN = _load_ban()


def _banned(name: str) -> bool:
    raw = str(name or "").strip().lower()
    if not raw:
        return False
    return _digest(raw) in BAN or _digest(_norm(raw)) in BAN


def _pythons() -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for cand in ("/opt/conda/bin/python3", "/usr/bin/python3", shutil.which("python3") or ""):
        if cand and os.path.isfile(cand) and cand not in seen:
            seen.add(cand)
            found.append(cand)
    return found


def _run_json(argv: list[str]) -> object | None:
    try:
        out = subprocess.check_output(argv, text=True, stderr=subprocess.DEVNULL)
        return json.loads(out)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def _uninstall(py: str, dists: list[str]) -> None:
    if not dists:
        return
    subprocess.run(
        [py, "-m", "pip", "uninstall", "-y", "--break-system-packages", *dists],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _maybe_rm(path: Path) -> None:
    name = path.name
    stem = name
    for suf in (".dist-info", ".egg-info", ".json", ".so"):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
    candidates = {name.lower(), stem.lower()}
    head = re.match(r"^([A-Za-z0-9_.]+)", stem)
    if head:
        candidates.add(head.group(1).lower())
    named = re.match(r"^([A-Za-z0-9_.]+(?:-[A-Za-z][A-Za-z0-9_.]+)*)-\d", stem)
    if named:
        candidates.add(named.group(1).lower())
    if name.startswith("lib") and ".so" in name:
        core = name[3:].split(".so", 1)[0]
        candidates.add(core.lower())
        candidates.add(("lib" + core).lower())
    if not any(_banned(item) for item in candidates):
        return
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        print(f"[cbrun] removed leftover {_digest(name)[:8]}", flush=True)
    except OSError:
        pass


def _scan_dir(path: Path) -> None:
    if not path.is_dir():
        return
    try:
        children = list(path.iterdir())
    except OSError:
        return
    for child in children:
        _maybe_rm(child)


def main() -> int:
    if not BAN:
        return 0
    for py in _pythons():
        names = _run_json(
            [
                py,
                "-c",
                "import importlib.metadata as m, json; "
                "print(json.dumps([d.metadata['Name'] for d in m.distributions() "
                "if d.metadata.get('Name')]))",
            ]
        )
        mapping = _run_json(
            [
                py,
                "-c",
                "import importlib.metadata as m, json; "
                "print(json.dumps({k: list(v) for k, v in m.packages_distributions().items()}))",
            ]
        )
        to_remove: set[str] = set()
        if isinstance(names, list):
            for dist in names:
                if _banned(str(dist)):
                    to_remove.add(str(dist))
        if isinstance(mapping, dict):
            for pkg, dists in mapping.items():
                if _banned(str(pkg)):
                    to_remove.update(str(x) for x in (dists or []))
                for dist in dists or []:
                    if _banned(str(dist)):
                        to_remove.add(str(dist))
        if to_remove:
            _uninstall(py, sorted(to_remove))
            print(f"[cbrun] stripped {len(to_remove)} dist(s)", flush=True)
        sites = _run_json(
            [
                py,
                "-c",
                "import json, site; "
                "print(json.dumps(list(site.getsitepackages()) + [site.getusersitepackages()]))",
            ]
        )
        if isinstance(sites, list):
            for site_dir in sites:
                _scan_dir(Path(str(site_dir)))

    extra = os.environ.get("CBRUN_STRIP_SCAN_DIRS", "")
    scan_roots = [
        Path("/opt/conda/bin"),
        Path("/usr/local/bin"),
        Path("/opt/conda/conda-meta"),
        Path("/usr/include"),
        Path("/usr/local/include"),
        Path("/usr/local/lib/node_modules"),
        Path("/opt/nodejs/lib/node_modules"),
        Path("/usr/lib"),
        Path("/usr/local/lib"),
        Path("/usr/lib/x86_64-linux-gnu"),
    ]
    for raw in extra.split(":"):
        if raw.strip():
            scan_roots.append(Path(raw.strip()))
    for root in scan_roots:
        _scan_dir(root)

    npm = shutil.which("npm")
    if npm:
        data = _run_json([npm, "ls", "-g", "--depth=0", "--json"])
        deps = data.get("dependencies") if isinstance(data, dict) else None
        if isinstance(deps, dict):
            for name in deps:
                if _banned(str(name)):
                    subprocess.run(
                        [npm, "uninstall", "-g", str(name)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

_PIP_MODULE_HOOK = r'''"""Block ``python -m pip`` installs that hash to the denylist set."""
from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

_HASHES = Path(os.environ.get("CBRUN_DENYLIST_HASHES", "/opt/cbrun/denylist.hashes"))
_CMDS = {"install", "i", "add", "download", "wheel"}


def _norm(name: str) -> str:
    text = name.strip().lower().split("[", 1)[0].split("@", 1)[0]
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.replace("_", "-").replace(".", "-")


def check_orig_argv(argv=None, hashes_path=None) -> None:
    path = Path(hashes_path) if hashes_path else _HASHES
    if not path.is_file():
        return
    ban = {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()}
    if not ban:
        return
    args = list(argv if argv is not None else getattr(sys, "orig_argv", sys.argv))
    try:
        idx = args.index("-m")
    except ValueError:
        return
    if idx + 1 >= len(args) or args[idx + 1] != "pip":
        return
    rest = args[idx + 2 :]
    i = 0
    names: list[str] = []
    while i < len(rest):
        tok = rest[i]
        if tok in _CMDS:
            i += 1
            while i < len(rest):
                arg = rest[i]
                if arg.startswith("-"):
                    if arg in ("-r", "--requirement") and i + 1 < len(rest):
                        req = Path(rest[i + 1])
                        if req.is_file():
                            for line in req.read_text(encoding="utf-8").splitlines():
                                line = line.strip()
                                if line and not line.startswith("#"):
                                    names.append(line.split(";", 1)[0].strip())
                        i += 2
                        continue
                    i += 1
                    continue
                names.append(arg)
                i += 1
            break
        i += 1
    for name in names:
        digest = hashlib.sha256(_norm(name).encode()).hexdigest()
        if digest in ban:
            print(
                f"[cbrun denylist] blocked install of upstream package: {name}",
                file=sys.stderr,
            )
            print(
                "[cbrun denylist] implement this functionality yourself; "
                "do not reuse the upstream product.",
                file=sys.stderr,
            )
            raise SystemExit(1)


check_orig_argv()
'''


def render_pip_shim() -> str:
    return _PIP_SHIM


def render_conda_shim() -> str:
    return _CONDA_SHIM


def render_npm_shim() -> str:
    return _NPM_SHIM


def render_strip_script() -> str:
    return _STRIP_SCRIPT


def render_pip_module_hook() -> str:
    return _PIP_MODULE_HOOK


def write_shim_assets(
    build_ctx: Path,
    denylist_path: Path,
    *,
    required: bool = False,
) -> str:
    """Copy hash denylist + shim scripts into Docker build context; return Dockerfile snippet."""
    if not denylist_path.is_file():
        if required:
            raise MissingDenylist(
                f"source/denylist.json is missing at {denylist_path}. "
                "Every released case tracks this file; restore it from git, "
                "or pass --no-enforce-denylist to skip the scan."
            )
        return ""
    hashes = install_ban_hashes_from_file(denylist_path)
    if not hashes:
        return ""

    build_ctx.mkdir(parents=True, exist_ok=True)
    (build_ctx / "denylist.hashes").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    (build_ctx / "strip_banned.py").write_text(render_strip_script(), encoding="utf-8")
    (build_ctx / "cbrun_denylist_hook.py").write_text(render_pip_module_hook(), encoding="utf-8")
    shim_dir = build_ctx / "shims"
    shim_dir.mkdir(exist_ok=True)
    pip_shim = render_pip_shim()
    conda_shim = render_conda_shim()
    npm_shim = render_npm_shim()
    for name, content in (
        ("pip", pip_shim),
        ("pip3", pip_shim),
        ("conda", conda_shim),
        ("mamba", conda_shim),
        ("uv", pip_shim),
        ("npm", npm_shim),
        ("npx", npm_shim),
        ("pnpm", npm_shim),
        ("yarn", npm_shim),
    ):
        (shim_dir / name).write_text(content, encoding="utf-8")
    bins = " ".join(
        f"{SHIM_BIN_DIR}/{name}"
        for name in ("pip", "pip3", "conda", "mamba", "uv", "npm", "npx", "pnpm", "yarn")
    )
    return (
        f"COPY denylist.hashes {CONTAINER_DENYLIST_HASHES_PATH}\n"
        f"COPY strip_banned.py {CONTAINER_STRIP_SCRIPT_PATH}\n"
        f"COPY cbrun_denylist_hook.py {CONTAINER_PIP_HOOK_PATH}\n"
        f"COPY shims/ {SHIM_BIN_DIR}/\n"
        f"RUN chmod +x {bins} && "
        f"python3 {CONTAINER_STRIP_SCRIPT_PATH} && "
        "for py in /opt/conda/bin/python3 /usr/bin/python3; do "
        '  if [ -x "$py" ]; then '
        '    dest="$($py -c \'import site; print(site.getsitepackages()[0])\')" && '
        f'    ln -sfn {CONTAINER_PIP_HOOK_PATH} "$dest/cbrun_denylist_hook.py" && '
        '    printf \'import cbrun_denylist_hook\\n\' > "$dest/zz_cbrun_denylist.pth"; '
        "  fi; "
        "done && "
        f'printf "export PATH={SHIM_BIN_DIR}:\\$PATH\\n" > /etc/profile.d/00-cbrun-denylist.sh\n'
        f"ENV PATH={SHIM_BIN_DIR}:$PATH\n"
    )


def import_root_from_ban_token(token: str) -> str | None:
    """Normalize one ``import_ban`` token to the top-level import root."""
    text = str(token).strip().rstrip("/")
    if not text:
        return None
    if text.startswith("@") and "/" in text:
        parts = [p for p in text.split("/") if p]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return None
    if "/" in text:
        last = text.rsplit("/", 1)[-1].strip()
        return last or None
    if "." in text:
        first = text.split(".", 1)[0].strip()
        return first or None
    return text


def import_roots_from_ban_tokens(tokens: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    roots: list[str] = []
    for token in tokens:
        root = import_root_from_ban_token(token)
        if root is None or root in seen:
            continue
        seen.add(root)
        roots.append(root)
    return roots


def _stdlib_roots() -> set[str]:
    import sys

    names = getattr(sys, "stdlib_module_names", None)
    return set(names) if names else set()


def _parse_probe_rows(output: str, roots: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for raw in output.splitlines():
        line = raw.strip()
        if not line or "\t" not in line:
            continue
        name, origin = line.split("\t", 1)
        if name in roots:
            found[name] = origin.strip()
    return found


@dataclass
class ProbeSpec:
    python_roots: list[str] = field(default_factory=list)
    node_roots: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    watch_ada: bool = False


def probe_spec_from_payload(payload: dict) -> ProbeSpec:
    tokens = [str(x).strip() for x in (payload.get("import_ban") or []) if str(x).strip()]
    install = [str(x).strip() for x in (payload.get("install_ban") or []) if str(x).strip()]
    raw_roots = import_roots_from_ban_tokens(tokens)
    python_roots = [r for r in raw_roots if is_probeable_import_root(r)]
    node_roots = [
        r for r in raw_roots if is_probeable_import_root(r) or (r.startswith("@") and "/" in r)
    ]
    commands = []
    seen_cmd: set[str] = set()
    for tok in tokens + install:
        cmd = tok.strip().rstrip("/")
        if is_command_like_token(tok) and cmd not in seen_cmd:
            seen_cmd.add(cmd)
            commands.append(cmd)
    headers: list[str] = []
    seen_hdr: set[str] = set()
    for tok in tokens + install:
        base = Path(tok.strip().rstrip("/")).name
        if any(base.endswith(suf) for suf in (".h", ".hh", ".hpp", ".hxx")) and base not in seen_hdr:
            seen_hdr.add(base)
            headers.append(base)
    watch_ada = any(
        (import_root_from_ban_token(tok) or "").lower() == "ada" or tok.strip().lower() == "ada"
        for tok in tokens + install
    )
    return ProbeSpec(
        python_roots=python_roots,
        node_roots=node_roots,
        commands=commands,
        headers=headers,
        watch_ada=watch_ada,
    )


def _unified_probe_command(spec: ProbeSpec) -> str:
    blob = json.dumps(
        {
            "python_roots": spec.python_roots,
            "node_roots": spec.node_roots,
            "commands": spec.commands,
            "headers": spec.headers,
            "watch_ada": spec.watch_ada,
        }
    )
    return (
        "python3 - <<'PY'\n"
        "import importlib.util, json, os, shutil, subprocess, sys\n"
        f"spec = json.loads({json.dumps(blob)})\n"
        "def pythons():\n"
        "    seen = set()\n"
        "    for p in ('/opt/conda/bin/python3', '/usr/bin/python3', shutil.which('python3') or ''):\n"
        "        if p and os.path.isfile(p) and p not in seen:\n"
        "            seen.add(p)\n"
        "            yield p\n"
        "for py in list(pythons()) or [sys.executable]:\n"
        "    code = (\n"
        "        'import importlib.util, json, sys\\n'\n"
        "        'roots = json.loads(sys.argv[1])\\n'\n"
        "        'std = set(getattr(sys, \"stdlib_module_names\", ()) )\\n'\n"
        "        'for root in roots:\\n'\n"
        "        '    if root in std:\\n'\n"
        "        '        print(root + \"\\\\t__STDLIB__\")\\n'\n"
        "        '        continue\\n'\n"
        "        '    try:\\n'\n"
        "        '        found = importlib.util.find_spec(root)\\n'\n"
        "        '    except (ModuleNotFoundError, ValueError):\\n'\n"
        "        '        print(root + \"\\\\t__ABSENT__\")\\n'\n"
        "        '        continue\\n'\n"
        "        '    if found is None:\\n'\n"
        "        '        print(root + \"\\\\t__ABSENT__\")\\n'\n"
        "        '        continue\\n'\n"
        "        '    origin = found.origin or \"\"\\n'\n"
        "        '    if origin:\\n'\n"
        "        '        print(root + \"\\\\t\" + origin)\\n'\n"
        "        '        continue\\n'\n"
        "        '    locs = list(found.submodule_search_locations or [])\\n'\n"
        "        '    print(root + \"\\\\t\" + (locs[0] if locs else \"__PRESENT__\"))\\n'\n"
        "    )\n"
        "    try:\n"
        "        out = subprocess.check_output([py, '-c', code, json.dumps(spec['python_roots'])], text=True)\n"
        "    except Exception as exc:\n"
        "        print('pyerr\\t' + py + '\\t' + str(exc))\n"
        "        continue\n"
        "    sys.stdout.write(out)\n"
        "if shutil.which('node') and spec['node_roots']:\n"
        "    for root in spec['node_roots']:\n"
        "        try:\n"
        "            loc = subprocess.check_output(\n"
        "                ['node', '-e', 'try { console.log(require.resolve(process.argv[1])) } '\n"
        "                 'catch (e) { console.log(\"__ABSENT__\") }', root],\n"
        "                text=True, stderr=subprocess.DEVNULL,\n"
        "            ).strip()\n"
        "        except Exception:\n"
        "            loc = '__ABSENT__'\n"
        "        print('node\\t' + root + '\\t' + loc)\n"
        "        for base in ('/usr/local/lib/node_modules', '/opt/nodejs/lib/node_modules'):\n"
        "            path = os.path.join(base, root)\n"
        "            print('nmdir\\t' + root + '\\t' + ('PRESENT' if os.path.exists(path) else 'ABSENT'))\n"
        "for name in spec['commands']:\n"
        "    print('cmd\\t' + name + '\\t' + (shutil.which(name) or '__ABSENT__'))\n"
        "for hdr in spec['headers']:\n"
        "    hits = [p for p in ('/usr/include/' + hdr, '/usr/local/include/' + hdr) if os.path.exists(p)]\n"
        "    print('hdr\\t' + hdr + '\\t' + (hits[0] if hits else '__ABSENT__'))\n"
        "    libhits = []\n"
        "    stem = hdr.rsplit('.', 1)[0]\n"
        "    for libdir in ('/usr/lib', '/usr/local/lib', '/usr/lib/x86_64-linux-gnu'):\n"
        "        for fn in ('lib' + stem + '.so', 'lib' + stem + '.a'):\n"
        "            p = os.path.join(libdir, fn)\n"
        "            if os.path.exists(p):\n"
        "                libhits.append(p)\n"
        "    print('lib\\t' + stem + '\\t' + (libhits[0] if libhits else '__ABSENT__'))\n"
        "print('warm\\t/opt/cb-warm\\t' + ('PRESENT' if os.path.exists('/opt/cb-warm') else 'ABSENT'))\n"
        "print('repo\\t/opt/codingbench/repo\\t' + ('PRESENT' if os.path.exists('/opt/codingbench/repo') else 'ABSENT'))\n"
        "if spec['watch_ada'] and shutil.which('node'):\n"
        "    try:\n"
        "        ver = subprocess.check_output(['node', '-p', 'process.versions.ada||\"\"'], text=True).strip()\n"
        "    except Exception:\n"
        "        ver = ''\n"
        "    print('adaver\\t' + (ver or 'ABSENT'))\n"
        "PY"
    )


@dataclass
class ImportProbeResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _record_present(result: ImportProbeResult, tag: str, kind: str, name: str, origin: str) -> None:
    if origin in {"", "__ABSENT__", "__STDLIB__", "ABSENT"}:
        return
    result.errors.append(
        f"banned {kind} {name!r} is present in {tag} (origin={origin})"
    )


def probe_banned_imports(
    tag: str,
    denylist_path: Path | str,
    *,
    runner=None,
) -> ImportProbeResult:
    """Probe whether banned roots, binaries, or leftovers resolve in *tag*."""
    result = ImportProbeResult()
    path = Path(denylist_path)
    if not path.is_file():
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.errors.append(f"denylist unreadable: {path}: {exc}")
        return result
    if not isinstance(payload, dict):
        result.errors.append(f"denylist is not an object: {path}")
        return result
    spec = probe_spec_from_payload(payload)
    command = _unified_probe_command(spec)
    if runner is None:
        from .docker_env import Container

        container = Container.start(tag, network="none")
        try:
            outcome = container.exec(command, timeout_sec=60.0)
        finally:
            container.remove()
    else:
        outcome = runner(command)
    tail = getattr(outcome, "tail", "") or ""
    roots = list(spec.python_roots)
    found = _parse_probe_rows(tail, roots)
    for root, origin in found.items():
        if origin and origin not in {"__ABSENT__", "__STDLIB__"}:
            result.errors.append(
                f"banned import root {root!r} is importable in {tag} (origin={origin})"
            )
    for raw in tail.splitlines():
        parts = raw.strip().split("\t")
        if not parts:
            continue
        kind = parts[0]
        if kind == "node" and len(parts) >= 3:
            _record_present(result, tag, "npm package", parts[1], parts[2])
        elif kind == "nmdir" and len(parts) >= 3:
            _record_present(result, tag, "npm directory", parts[1], parts[2])
        elif kind == "cmd" and len(parts) >= 3:
            _record_present(result, tag, "command", parts[1], parts[2])
        elif kind == "hdr" and len(parts) >= 3:
            _record_present(result, tag, "header", parts[1], parts[2])
        elif kind == "lib" and len(parts) >= 3:
            _record_present(result, tag, "library", parts[1], parts[2])
        elif kind == "warm" and len(parts) >= 3 and parts[2] == "PRESENT":
            result.errors.append(f"upstream leftover /opt/cb-warm is present in {tag}")
        elif kind == "repo" and len(parts) >= 3 and parts[2] == "PRESENT":
            result.errors.append(f"upstream leftover /opt/codingbench/repo is present in {tag}")
        elif kind == "adaver" and len(parts) >= 2 and parts[1] not in {"", "ABSENT"}:
            result.warnings.append(
                f"Node runtime reports process.versions.ada={parts[1]!r} in {tag}"
            )
    return result


def log_probe_result(probe: ImportProbeResult, *, prefix: str = "[cbrun]") -> None:
    for warning in probe.warnings:
        print(f"{prefix} denylist probe warning: {warning}", flush=True)
    for error in probe.errors:
        print(f"{prefix} denylist probe error: {error}", file=sys.stderr, flush=True)
