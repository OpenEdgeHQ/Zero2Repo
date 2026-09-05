"""Per-case upstream denylist: L3 install shims and L4 static scan."""

from __future__ import annotations

import hashlib
import json
import re
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
    "load_denylist",
    "normalize_pkg_name",
    "render_pip_shim",
    "render_conda_shim",
    "line_imports_token",
    "scan_workspace_imports",
    "validate_denylist_artifact",
    "validate_denylist_payload",
]

CONTAINER_DENYLIST_HASHES_PATH = "/opt/cbrun/denylist.hashes"
SHIM_BIN_DIR = "/opt/cbrun/bin"
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
    install = data.get("install_ban") or []
    return install_ban_hashes(tuple(str(x) for x in install if str(x).strip()))


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
install_cmds = {"install", "i", "add"}
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


def render_pip_shim() -> str:
    return _PIP_SHIM


def render_conda_shim() -> str:
    return _CONDA_SHIM


def write_shim_assets(build_ctx: Path, denylist_path: Path) -> str:
    """Copy hash denylist + shim scripts into Docker build context; return Dockerfile snippet."""
    if not denylist_path.is_file():
        return ""
    hashes = install_ban_hashes_from_file(denylist_path)
    if not hashes:
        return ""

    build_ctx.mkdir(parents=True, exist_ok=True)
    (build_ctx / "denylist.hashes").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    shim_dir = build_ctx / "shims"
    shim_dir.mkdir(exist_ok=True)
    pip_shim = render_pip_shim()
    conda_shim = render_conda_shim()
    for name, content in (
        ("pip", pip_shim),
        ("pip3", pip_shim),
        ("conda", conda_shim),
        ("mamba", conda_shim),
        ("uv", pip_shim),
    ):
        (shim_dir / name).write_text(content, encoding="utf-8")
    return (
        f"COPY denylist.hashes {CONTAINER_DENYLIST_HASHES_PATH}\n"
        f"COPY shims/ {SHIM_BIN_DIR}/\n"
        f"RUN chmod +x {SHIM_BIN_DIR}/pip {SHIM_BIN_DIR}/pip3 {SHIM_BIN_DIR}/conda "
        f"{SHIM_BIN_DIR}/mamba {SHIM_BIN_DIR}/uv && "
        f'printf "export PATH={SHIM_BIN_DIR}:\\$PATH\\n" > /etc/profile.d/00-cbrun-denylist.sh\n'
        f"ENV PATH={SHIM_BIN_DIR}:$PATH\n"
    )
