# feature: F01
"""Observation helpers for vendoring and registering the generic plugin.

Import side effects: none. Process spawn and filesystem writes happen only
when a caller invokes a function below.
"""

from __future__ import annotations

import re
import secrets
import shutil
import socket
from pathlib import Path
from typing import Mapping, Sequence

from _harness import (
    EFFECT_PLUGIN_NAME,
    GENERIC_PLUGIN_NAME,
    HarnessError,
    RunResult,
    Workspace,
    diagnostics,
    effect_plugin,
    generic_plugin,
    generic_plugin_path,
    list_files,
    node_modules_path,
    rule_key,
    snapshot_files,
)

GENERIC_RULE_NAMES: tuple[str, ...] = (
    "no-array-filter-map",
    "no-reduce-accumulator-copy",
    "no-chained-type-assertions",
    "no-conditional-empty-object-spread",
    "no-known-value-widening",
    "no-module-mocking",
    "no-object-parameters",
    "no-reflect-apply",
    "no-reflect-get",
    "no-runtime-typeof",
    "no-shape-in-symbol-names",
    "no-unknown-parameters",
    "no-unknown-returns",
    "no-unknown-type-aliases",
    "no-unsafe-dictionary-type",
    "no-widen-then-assert",
    "require-readable-spacing",
    "require-safety-comment-for-type-assertion",
)

EFFECT_RULE_NAMES: tuple[str, ...] = (
    "no-manual-effect-error-tag",
    "no-manual-tag-comparison",
    "no-manual-tagged-construction",
    "no-service-constructor-imports",
    "prefer-effect-match",
)

_JS_RULES = frozenset(
    {
        "no-array-filter-map",
        "no-reduce-accumulator-copy",
        "no-conditional-empty-object-spread",
        "no-module-mocking",
        "no-reflect-apply",
        "no-reflect-get",
        "no-runtime-typeof",
        "no-shape-in-symbol-names",
        "require-readable-spacing",
    }
)

# Role classification for dest files. The PRD requires license and provenance
# material under dest; it does not name MIT grant wording, an "as is"
# disclaimer, "upstream", "copied files", or a commit hash as the contents
# that make a file count. Basename families are one way a file can occupy a
# role; body role-words are another. Neither pins this checkout's paths.
# The word "upstream" is not a classifier: a provenance file still counts
# without that token, via another basename family or a provenance/vendored
# role word in the body.
_LICENSE_BASENAME = re.compile(
    r"^(?:license|licence|copying|copyright)(?:\.[^./]+)?$",
    re.IGNORECASE,
)
_PROVENANCE_BASENAME = re.compile(
    r"^(?:origin|provenance|notice|credits|authors|sources?)(?:\.[^./]+)?$",
    re.IGNORECASE,
)
_LICENSE_BODY = re.compile(r"\b(?:licen[cs]e|copyright)\b", re.IGNORECASE)
_PROVENANCE_BODY = re.compile(r"\b(?:provenance|vendored)\b", re.IGNORECASE)
_PLUGIN_WRAP = re.compile(r"^([A-Za-z0-9_.:-]+)\((.+)\)$")
_PLUGIN_SUFFIXES = {".ts", ".js", ".mjs", ".cjs", ".mts", ".cts"}
_SAFETY_COMMENT = "// SAFETY: parsed before branding."


def published_rule_id(rule: str) -> str:
    """Normalize a host finding code to ``<plugin>/<rule>``.

    The PRD names the plugin and the rule. Hosts may render that as a slash
    id or as ``plugin(rule)``; both are the same published pair. Do not
    require one host's punctuation.
    """
    current = rule.strip()
    matched = _PLUGIN_WRAP.match(current)
    if not matched:
        return current
    plugin, inner = matched.group(1), matched.group(2)
    if plugin in {"eslint", "eslint-plugin-js"}:
        return published_rule_id(inner)
    if "/" in inner:
        return inner
    return f"{plugin}/{inner}"


def fresh_ident(prefix: str = "id") -> str:
    """Return a runtime identifier that does not contain ``shape``."""
    while True:
        name = f"{prefix}{secrets.token_hex(4)}"
        if name.isidentifier() and "shape" not in name.lower():
            return name


def snippet_extension(rule_name: str) -> str:
    return "js" if rule_name in _JS_RULES else "ts"


def next_generic_rule(rule_name: str) -> str:
    index = GENERIC_RULE_NAMES.index(rule_name)
    return GENERIC_RULE_NAMES[(index + 1) % len(GENERIC_RULE_NAMES)]


def _norm_path_text(value: str) -> str:
    return value.replace("\\", "/").rstrip("/")


def _drop_dot_slash(form: str) -> str:
    """Strip repeated ``./`` prefixes. Do not treat ``/`` or ``.`` as a charset."""
    text = _norm_path_text(form)
    while text.startswith("./"):
        text = text[2:]
    return "" if text == "." else text


def _asked_dest(dest: str | Path) -> str:
    """Dest the invocation used, as a normalized relative (or given) spelling."""
    dest_path = Path(dest)
    form = _norm_path_text(dest_path.as_posix())
    if dest_path.is_absolute():
        return form
    return _drop_dot_slash(form)


def _dest_on_disk(dest: str | Path, cwd: str | Path | None = None) -> Path:
    """Locate dest from the path the suite passed, not from report spelling."""
    dest_path = Path(dest)
    if dest_path.is_absolute():
        return dest_path.resolve()
    if cwd is not None:
        return (Path(cwd) / dest_path).resolve()
    return dest_path.resolve()


def _strip_cwd_prefix(form: str, cwd: str | Path | None) -> str:
    """If a cwd prefix is present, strip it; the remainder is dest identity.

    A process.cwd()-resolved absolute dest and the cwd-relative dest the
    invocation used are the same identity. ``str.lstrip('./')`` is not
    that strip: it would drop the leading ``/`` of an absolute path and
    then fail to match the cwd prefix.
    """
    text = _norm_path_text(form)
    if cwd is None:
        return _drop_dot_slash(text)
    prefixes: list[str] = []
    cwd_path = Path(cwd)
    for raw in (
        str(cwd_path.resolve()),
        cwd_path.as_posix(),
        str(cwd),
    ):
        prefix = _norm_path_text(raw)
        if prefix and prefix not in prefixes:
            prefixes.append(prefix)
    for prefix in prefixes:
        if text == prefix:
            return ""
        glued = prefix + "/"
        if text.startswith(glued):
            return text[len(glued):]
    return _drop_dot_slash(text)


def _dest_forms(dest: str | Path, cwd: str | Path | None = None) -> tuple[str, ...]:
    """Spellings of dest that count as the same identity.

    Cwd-relative and process.cwd()-resolved absolute paths are the same dest:
    if a cwd prefix is present, strip it, then compare the remainder to the
    dest the copy was asked to use. Parent-suffix remainders that are not
    that dest (for example ``oxlint/lint-policy`` when dest is
    ``tools/oxlint/lint-policy``) are not dest identity.
    """
    dest_path = Path(dest)
    on_disk = _dest_on_disk(dest_path, cwd)
    asked = _asked_dest(dest_path)
    seen: list[str] = []

    def add(value: str) -> None:
        form = _norm_path_text(value)
        if form and form not in seen:
            seen.append(form)

    add(str(on_disk))
    add(on_disk.as_posix())
    add(asked)
    add(str(dest_path))
    add(dest_path.as_posix())
    if cwd is not None:
        try:
            add(on_disk.relative_to(Path(cwd).resolve()).as_posix())
        except ValueError:
            pass
        remainder = _strip_cwd_prefix(on_disk.as_posix(), cwd)
        if remainder == asked:
            add(remainder)
    return tuple(seen)


def dest_identified_in(
    text: str,
    dest: str | Path,
    cwd: str | Path | None = None,
) -> bool:
    """Whether *text* identifies *dest* by path identity, not path spelling.

    Identity is the dest the copy was asked to use. A cwd-relative spelling
    and a process.cwd()-resolved absolute spelling are the same dest: if a
    cwd prefix is present, strip it, then compare the remainder to that dest.
    """
    asked = _asked_dest(dest)
    haystack = text.replace("\\", "/")
    on_disk = _dest_on_disk(dest, cwd)
    disk_form = _norm_path_text(on_disk.as_posix())
    if asked and asked in haystack:
        return True
    if disk_form and disk_form in haystack:
        return True
    for token in re.findall(r"[^\s\"'`]+", haystack):
        remainder = _strip_cwd_prefix(token.rstrip(".,;:)"), cwd)
        if not remainder:
            continue
        if remainder == asked or remainder == disk_form:
            return True
        if asked and remainder.startswith(asked + "/"):
            return True
        if disk_form and remainder.startswith(disk_form + "/"):
            return True
    return False


def reported_generic_specifier(
    result: RunResult,
    dest: str | Path,
    cwd: str | Path | None = None,
) -> str:
    """Extract the generic-entry configure target from a successful copy report.

    Raises:
        HarnessError: if stdout/stderr cannot be decoded.
        AssertionError: if dest is unnamed or no entry-to-configure is named
            that is more specific than the dest directory.
    """
    dest_path = _dest_on_disk(dest, cwd)
    text = result.combined_text
    if not dest_identified_in(text, dest, cwd):
        raise AssertionError(
            "copy report does not identify the destination "
            f"{dest}; report={text!r}"
        )

    haystack = text.replace("\\", "/")
    candidates: list[Path] = []
    for form in sorted(_dest_forms(dest, cwd), key=len, reverse=True):
        pattern = re.compile(re.escape(form) + r"(?:/|\\)+([^\s\"'`]+)")
        for match in pattern.finditer(haystack):
            extra = match.group(1).rstrip(".,;:)\"'")
            if not extra:
                continue
            # Tree location comes from dest the suite passed, not from the
            # report's absolute-versus-relative spelling of that dest.
            candidates.append(dest_path / extra)

    more_specific: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError as exc:
            raise HarnessError(
                f"cannot resolve reported configure target {candidate}: {exc}"
            ) from exc
        try:
            rel = resolved.relative_to(dest_path)
        except ValueError:
            continue
        if resolved == dest_path or rel.as_posix() in ("", "."):
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        more_specific.append(resolved)

    if not more_specific:
        raise AssertionError(
            "copy report names the destination but does not name a generic-entry "
            "configure target more specific than the dest directory; "
            f"report={text!r}"
        )

    def _depth(path: Path) -> tuple[int, str]:
        rel = path.relative_to(dest_path)
        return (len(rel.parts), rel.as_posix())

    # Prefer the shallowest dest-relative file so a nested Effect entry
    # named in the same report is not taken as the generic configure target.
    files = [path for path in more_specific if path.is_file()]
    pool = files or more_specific
    pool.sort(key=_depth)
    chosen = pool[0]
    print(f"reported generic specifier={chosen}", flush=True)
    return str(chosen)


def require_copy_success(
    result: RunResult,
    dest: str | Path,
    cwd: str | Path | None = None,
) -> str:
    """Assert a successful copy and return the reported generic specifier."""
    dest_path = _dest_on_disk(dest, cwd)
    print(
        f"copy success probe exit={result.returncode} dest={dest_path}",
        flush=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            "copy must succeed; "
            f"exit={result.returncode}; stderr={result.stderr_text!r}"
        )
    if not dest_path.is_dir():
        raise AssertionError(f"copy did not create dest directory {dest_path}")
    specifier = reported_generic_specifier(result, dest, cwd)
    assert_generic_configure_target(specifier, dest_path)
    return specifier


def assert_generic_configure_target(
    specifier: str | Path,
    dest: str | Path,
    effect_specifier: str | Path | None = None,
) -> None:
    """Generic configure target is under dest, not dest, not the Effect entry."""
    dest_path = Path(dest).resolve()
    spec_path = Path(specifier).resolve()
    try:
        rel = spec_path.relative_to(dest_path)
    except ValueError as exc:
        raise AssertionError(
            f"generic-entry configure target {spec_path} is not under dest "
            f"{dest_path}"
        ) from exc
    if rel.as_posix() in ("", "."):
        raise AssertionError(
            "generic-entry configure target must be more specific than dest"
        )
    if effect_specifier is None:
        return
    effect_path = Path(effect_specifier).resolve()
    if spec_path == effect_path:
        raise AssertionError(
            "generic-entry configure target must not be the nested Effect entry"
        )


def require_copy_refusal(
    result: RunResult,
    dest: str | Path,
    *,
    before: Mapping[str, bytes],
    cwd: str | Path | None = None,
) -> None:
    """Assert occupied-dest refusal: unsuccessful exit, dest named, bytes kept."""
    dest_path = _dest_on_disk(dest, cwd)
    print(
        f"copy refusal probe exit={result.returncode} dest={dest_path}",
        flush=True,
    )
    if result.returncode == 0:
        raise AssertionError(
            "copy must refuse to overwrite an occupied dest without --force; "
            f"exit={result.returncode}; stdout={result.stdout_text!r}"
        )
    text = result.combined_text
    if not dest_identified_in(text, dest, cwd):
        raise AssertionError(
            "refusal must identify the destination "
            f"{dest}; report={text!r}"
        )
    after = snapshot_files(dest_path)
    if dict(after) != dict(before):
        raise AssertionError(
            "occupied dest bytes changed despite refusal without --force"
        )


def require_unpublished_name_host_refusal(
    result: RunResult,
    unpublished_names: Sequence[str],
) -> None:
    """Assert unclassified host output is the L103 unpublished-name refusal.

    An unpublished lint-policy rule name listed with a known enabled rule is a
    host-configuration concern. The allowed unclassified carrier is a host
    refusal that identifies those unpublished names and the loaded generic
    plugin. Any other non-zero unclassified output is not that carrier.

    Raises:
        HarnessError: if stdout/stderr cannot be decoded.
        AssertionError: if the invocation succeeded, or the report does not
            identify every unpublished name and the loaded generic plugin.
    """
    names = tuple(unpublished_names)
    print(
        f"unpublished-name host refusal exit={result.returncode} names={list(names)}",
        flush=True,
    )
    if result.returncode == 0:
        raise AssertionError(
            "listing unpublished lint-policy rule names must not succeed; "
            f"exit={result.returncode}; stdout={result.stdout_text!r}"
        )
    text = result.combined_text
    missing = [name for name in names if name not in text]
    if missing:
        raise AssertionError(
            "host-configuration refusal must identify the unpublished rule "
            f"names {missing}; report={text!r}"
        )
    if GENERIC_PLUGIN_NAME not in text:
        raise AssertionError(
            "host-configuration refusal must name the loaded plugin "
            f"{GENERIC_PLUGIN_NAME}; report={text!r}"
        )


def occupy_copied_plugin_paths(dest: str | Path, placeholder: str) -> tuple[Path, ...]:
    """Overwrite dest plugin-suffix files with *placeholder*.

    Occupies source-overlapping plugin paths left by a prior copy. The
    paths come from dest on disk, not from a pinned generic-entry
    basename. Destination-only extras that are not plugin-suffix files
    are not touched.
    """
    dest_path = Path(dest).resolve()
    if not dest_path.is_dir():
        raise AssertionError(f"dest is not a directory: {dest_path}")
    occupied: list[Path] = []
    for rel in list_files(dest_path):
        if rel.endswith(".d.ts"):
            continue
        path = dest_path / rel
        if path.suffix.lower() not in _PLUGIN_SUFFIXES:
            continue
        path.write_text(placeholder, encoding="utf-8")
        written = path.read_text(encoding="utf-8")
        if written != placeholder:
            raise AssertionError(
                f"failed to occupy source-overlapping plugin path {path}"
            )
        occupied.append(path)
    if not occupied:
        raise AssertionError(
            "copy left no plugin-suffix files under dest to occupy as "
            "source-overlapping plugin paths"
        )
    print(
        "occupied plugin paths="
        f"{[path.relative_to(dest_path).as_posix() for path in occupied]}",
        flush=True,
    )
    return tuple(occupied)


def assert_occupied_plugin_paths_overwritten(
    occupied: Sequence[str | Path],
    placeholder: str,
) -> None:
    """Source-overlapping plugin paths must not still hold the occupy bytes."""
    leftover: list[str] = []
    missing: list[str] = []
    for raw in occupied:
        path = Path(raw)
        if not path.is_file():
            missing.append(str(path))
            continue
        if path.read_text(encoding="utf-8") == placeholder:
            leftover.append(str(path))
    print(
        f"force-overwrite leftover={leftover} missing={missing}",
        flush=True,
    )
    if leftover:
        raise AssertionError(
            "--force must overwrite source-overlapping plugin paths so dest "
            "contains the copied plugin files; still placeholder: "
            f"{leftover}"
        )
    if missing:
        raise AssertionError(
            "--force must overwrite source-overlapping plugin paths; "
            f"occupied plugin files missing after copy: {missing}"
        )


def _is_license_material(rel: str, body: str) -> bool:
    name = Path(rel).name
    return bool(_LICENSE_BASENAME.match(name) or _LICENSE_BODY.search(body))


def _is_provenance_material(rel: str, body: str) -> bool:
    name = Path(rel).name
    return bool(_PROVENANCE_BASENAME.match(name) or _PROVENANCE_BODY.search(body))


def assert_license_and_provenance_material(dest: str | Path) -> None:
    """Dest contains license material and provenance material as files."""
    dest_path = Path(dest).resolve()
    texts: dict[str, str] = {}
    for rel, data in snapshot_files(dest_path).items():
        try:
            texts[rel] = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
    license_files = [
        rel for rel, body in texts.items() if _is_license_material(rel, body)
    ]
    provenance_files = [
        rel for rel, body in texts.items() if _is_provenance_material(rel, body)
    ]
    print(
        f"license-role files={license_files} provenance-role files={provenance_files}",
        flush=True,
    )
    if not license_files:
        raise AssertionError(
            "dest contains no license material among its files"
        )
    if not provenance_files:
        raise AssertionError(
            "dest contains no provenance material among its files"
        )


def assert_tree_unchanged_outside_dest(
    before: Mapping[str, bytes],
    after: Mapping[str, bytes],
    dest: str | Path,
) -> None:
    """Consuming-tree snapshot minus dest is equal."""
    dest_rel = Path(dest).as_posix().rstrip("/")
    prefix = dest_rel + "/"

    def outside(snapshot: Mapping[str, bytes]) -> dict[str, bytes]:
        return {
            key: value
            for key, value in snapshot.items()
            if key != dest_rel and not key.startswith(prefix)
        }

    before_out = outside(before)
    after_out = outside(after)
    extra = sorted(set(after_out) - set(before_out))
    missing = sorted(set(before_out) - set(after_out))
    changed = sorted(
        key
        for key in before_out
        if key in after_out and before_out[key] != after_out[key]
    )
    print(
        f"outside-dest extra={extra} missing={missing} changed={changed}",
        flush=True,
    )
    if extra or missing or changed:
        raise AssertionError(
            "copy must not create, delete, or edit files outside dest; "
            f"extra={extra} missing={missing} changed={changed}"
        )


def _tree_resolves_host_plugins(tree: Path) -> bool:
    """True when a file under *tree* can resolve the host plugins package."""
    pkg = tree / "node_modules" / "@oxlint" / "plugins"
    try:
        return pkg.is_dir()
    except OSError as exc:
        raise HarnessError(
            f"cannot inspect host plugins package at {pkg}: {exc}"
        ) from exc


def _attach_host_plugin_modules(tree: Path, source: Path) -> None:
    """Expose the host plugins package under *tree* for Node ESM lookup.

    A directory named ``node_modules`` that does not contain the host
    plugins package is not "already attached". Raises HarnessError when
    the path cannot be inspected or the attach cannot be created. Never
    returns a sentinel that would look like the package was present.
    """
    if _tree_resolves_host_plugins(tree):
        return
    dest = tree / "node_modules"
    try:
        dest_exists = dest.exists() or dest.is_symlink()
    except OSError as exc:
        raise HarnessError(
            f"cannot inspect host plugin modules path {dest}: {exc}"
        ) from exc
    if not dest_exists:
        try:
            dest.symlink_to(source, target_is_directory=True)
        except OSError as exc:
            raise HarnessError(
                f"cannot attach host plugin modules {source} -> {dest}: {exc}"
            ) from exc
        print(f"attached host plugin modules {dest} -> {source}", flush=True)
        return
    source_pkg = source / "@oxlint" / "plugins"
    try:
        source_ok = source_pkg.is_dir()
    except OSError as exc:
        raise HarnessError(
            f"cannot inspect host plugins package at {source_pkg}: {exc}"
        ) from exc
    if not source_ok:
        raise HarnessError(
            f"host plugins package is not a directory at {source_pkg}"
        )
    scoped = dest / "@oxlint"
    pkg = scoped / "plugins"
    try:
        scoped.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HarnessError(
            f"cannot create host plugins scope {scoped}: {exc}"
        ) from exc
    try:
        pkg_present = pkg.exists() or pkg.is_symlink()
    except OSError as exc:
        raise HarnessError(
            f"cannot inspect host plugins path {pkg}: {exc}"
        ) from exc
    if pkg_present:
        raise HarnessError(
            f"host plugins path exists but is not a usable package: {pkg}"
        )
    try:
        pkg.symlink_to(source_pkg, target_is_directory=True)
    except OSError as exc:
        raise HarnessError(
            f"cannot attach host plugins package {source_pkg} -> {pkg}: {exc}"
        ) from exc
    print(f"attached host plugins package {pkg} -> {source_pkg}", flush=True)


def _plugin_module_trees(
    ws: Workspace, specifier: str | Path | None = None
) -> tuple[Path, ...]:
    """Package roots from which Node ESM will look up the host plugins package.

    Copied plugins resolve from the consuming cwd. Isolated overlays copy
    product source without host modules and treat that tree as the product
    under test, so this helper does not attach onto the product root. A
    shipped in-tree specifier is made loadable by copying that tree into
    the consuming cwd (see ``materialize_shipped_generic_entry``).
    """
    work = ws.path.resolve()
    trees: list[Path] = [work]
    if specifier is None:
        return tuple(trees)
    spec = Path(specifier).resolve()
    try:
        spec.relative_to(work)
    except ValueError:
        return tuple(trees)
    parent = spec.parent
    if parent != work:
        trees.append(parent)
    return tuple(dict.fromkeys(trees))


def ensure_host_plugin_modules(
    ws: Workspace, specifier: str | Path | None = None
) -> None:
    """Expose the host plugins package where Node ESM will resolve it.

    The PRD assumes a consuming repository already has Oxlint (and its
    plugins-host package). Copy must not install that package. Node ESM
    plugin loads resolve from the importing file, not NODE_PATH.

    A dest under an empty consuming cwd cannot see the host plugins
    package unless those modules are present in that tree. Attach onto
    the consuming cwd (and the specifier's directory when it lives
    there). Do not mutate the product tree.
    """
    source = node_modules_path(root=ws.root)
    if not source.is_dir():
        raise HarnessError(f"host plugins package is not available at {source}")
    for tree in _plugin_module_trees(ws, specifier):
        _attach_host_plugin_modules(tree, source)


def materialize_shipped_generic_entry(ws: Workspace) -> str:
    """Return a specifier for the shipped generic catalog without skill-copy.

    L89 names a manual copy of the plugin tree as a public entry. Isolated
    overlays copy product source without host modules; Node ESM resolves
    the host plugins package from the importing file, so a specifier under
    the product root cannot see modules attached only onto the temp
    workspace. Copy the shipped generic tree (the product's plugin source,
    not a skill-copy destination) into the consuming cwd, attach host
    modules there, and return that entry. Does not mutate the product.

    Raises:
        HarnessError: if the shipped entry is missing, the copy fails, or
            the copied entry is not a file.
    """
    source_entry = generic_plugin_path(root=ws.root)
    source_tree = source_entry.parent
    dest_tree = ws.path / f"shipped-generic-{fresh_ident('g')}"
    try:
        shutil.copytree(source_tree, dest_tree, symlinks=False)
    except OSError as exc:
        raise HarnessError(
            f"cannot manually copy shipped generic plugin {source_tree} "
            f"-> {dest_tree}: {exc}"
        ) from exc
    dest_entry = dest_tree / source_entry.name
    try:
        present = dest_entry.is_file()
    except OSError as exc:
        raise HarnessError(
            f"cannot inspect copied shipped generic entry {dest_entry}: {exc}"
        ) from exc
    if not present:
        raise HarnessError(
            "manual copy of shipped generic plugin did not produce an "
            f"entry at {dest_entry}"
        )
    ensure_host_plugin_modules(ws, dest_entry)
    print(
        f"manual-copied shipped generic {source_entry} -> {dest_entry}",
        flush=True,
    )
    return str(dest_entry.resolve())


def copied_effect_specifier(
    ws: Workspace,
    dest: str | Path,
    generic_specifier: str | Path,
) -> str:
    """Return a nested dest file, other than the generic specifier, that is
    the Effect plugin: registered as published name lint-policy-effect, an
    Effect rule fires when that entry is enabled.

    A nested dest file the host will load at all is not enough. A nested
    duplicate of the generic plugin, or any other loadable JavaScript
    plugin that is not the Effect plugin, is rejected.
    """
    dest_path = Path(dest).resolve()
    if not dest_path.is_dir():
        raise HarnessError(f"dest is not a directory: {dest_path}")
    ensure_host_plugin_modules(ws, generic_specifier)
    generic_res = Path(generic_specifier).resolve()
    probe_rel = f"effect-id-{fresh_ident('p')}.js"
    probe = ws.write(probe_rel, snippet_manual_tag_comparison())
    effect_rule = "no-manual-tag-comparison"
    expected = rule_key(EFFECT_PLUGIN_NAME, effect_rule)
    mapping = {expected: "error"}

    candidates: list[Path] = []
    for rel in list_files(dest_path):
        if rel.endswith(".d.ts"):
            continue
        path = dest_path / rel
        if path.suffix.lower() not in _PLUGIN_SUFFIXES:
            continue
        if path.resolve() == generic_res:
            continue
        candidates.append(path)

    def _rank(path: Path) -> tuple[int, int, str]:
        rel = path.relative_to(dest_path).as_posix()
        nested = 0 if "/" in rel else 1
        return (nested, len(rel), rel)

    candidates.sort(key=_rank)
    last_error: HarnessError | None = None
    for candidate in candidates:
        plugin = effect_plugin(specifier=candidate, root=ws.root)
        try:
            result = ws.lint([probe], plugins=[plugin], rules=mapping)
            findings = effect_plugin_findings(result)
        except HarnessError as exc:
            last_error = exc
            print(f"effect-identity miss {candidate}: {exc}", flush=True)
            continue
        print(
            f"effect-identity probe {candidate} exit={result.returncode} "
            f"findings={findings}",
            flush=True,
        )
        if expected not in findings:
            print(
                f"effect-identity miss {candidate}: no {expected} diagnostic",
                flush=True,
            )
            continue
        if result.returncode == 0:
            print(
                f"effect-identity miss {candidate}: Effect rule id present "
                "but lint succeeded",
                flush=True,
            )
            continue
        print(f"effect-identity hit {candidate}", flush=True)
        return str(candidate.resolve())
    raise HarnessError(
        "no nested dest file other than the generic specifier is the "
        f"Effect plugin ({EFFECT_PLUGIN_NAME}); last={last_error!r}"
    )


def lint_generic(
    ws: Workspace,
    files: Sequence[str | Path],
    rules: Sequence[str],
    specifier: str | Path,
) -> RunResult:
    """Register lint-policy only and enable *rules* at error."""
    ensure_host_plugin_modules(ws, specifier)
    plugin = generic_plugin(specifier=specifier, root=ws.root)
    mapping = {rule_key(GENERIC_PLUGIN_NAME, name): "error" for name in rules}
    print(
        f"lint-generic specifier={specifier} rules={list(rules)} files={list(files)}",
        flush=True,
    )
    return ws.lint(files, plugins=[plugin], rules=mapping)


def _ids_for_plugin(result: RunResult, plugin: str) -> tuple[str, ...]:
    """Published ``plugin/rule`` ids from classified lint JSON."""
    prefix = f"{plugin}/"
    ids: list[str] = []
    for item in diagnostics(result):
        published = published_rule_id(item.rule)
        if published.startswith(prefix):
            ids.append(published)
    return tuple(ids)


def lint_policy_findings(result: RunResult) -> tuple[str, ...]:
    """Published lint-policy rule ids (lint-policy-effect does not match)."""
    return _ids_for_plugin(result, GENERIC_PLUGIN_NAME)


def effect_plugin_findings(result: RunResult) -> tuple[str, ...]:
    return _ids_for_plugin(result, EFFECT_PLUGIN_NAME)


def rule_fired(findings: Sequence[str], rule_name: str) -> bool:
    expected = rule_key(GENERIC_PLUGIN_NAME, rule_name)
    return expected in findings


def assert_fired(result: RunResult, rule_name: str) -> None:
    generic = lint_policy_findings(result)
    effect = effect_plugin_findings(result)
    print(
        f"assert-fired {rule_name} exit={result.returncode} "
        f"generic={generic} effect={effect}",
        flush=True,
    )
    if result.returncode == 0:
        raise AssertionError(
            f"enabled rule {rule_name} at error must fail lint; "
            f"exit={result.returncode}"
        )
    expected = rule_key(GENERIC_PLUGIN_NAME, rule_name)
    if expected not in generic:
        raise AssertionError(f"expected diagnostic {expected}; got {generic}")
    if effect:
        raise AssertionError(
            f"unexpected {EFFECT_PLUGIN_NAME} findings {effect}"
        )


def assert_only_rule(result: RunResult, rule_name: str) -> None:
    generic = lint_policy_findings(result)
    effect = effect_plugin_findings(result)
    expected = rule_key(GENERIC_PLUGIN_NAME, rule_name)
    print(
        f"assert-only {rule_name} exit={result.returncode} ids={generic} "
        f"effect={effect}",
        flush=True,
    )
    if result.returncode == 0:
        raise AssertionError(
            f"enabled rule {rule_name} at error must fail lint; exit=0"
        )
    unique = tuple(dict.fromkeys(generic))
    if unique != (expected,):
        raise AssertionError(f"expected only {expected}; got {generic}")
    if effect:
        raise AssertionError(
            f"unexpected {EFFECT_PLUGIN_NAME} findings {effect}"
        )


def assert_not_fired(result: RunResult, rule_name: str) -> None:
    generic = lint_policy_findings(result)
    print(
        f"assert-not-fired {rule_name} exit={result.returncode} generic={generic}",
        flush=True,
    )
    if rule_fired(generic, rule_name):
        raise AssertionError(f"rule {rule_name} must not fire; got {generic}")


def assert_no_plugin_findings(result: RunResult) -> None:
    generic = lint_policy_findings(result)
    effect = effect_plugin_findings(result)
    print(
        f"assert-no-plugin-findings exit={result.returncode} "
        f"generic={generic} effect={effect}",
        flush=True,
    )
    if generic or effect:
        raise AssertionError(
            "expected no lint-policy or lint-policy-effect diagnostics; "
            f"generic={generic} effect={effect}"
        )


def snippet_no_array_filter_map(*, twin: bool = False) -> str:
    if not twin:
        return "[].filter(active).map(email);\n"
    keep = fresh_ident("keep")
    pick = fresh_ident("pick")
    return f"[].filter({keep}).map({pick});\n"


def snippet_no_reduce_accumulator_copy(*, twin: bool = False) -> str:
    key = "id" if not twin else fresh_ident("key")
    return (
        f"void [].reduce((acc, item) => Object.assign({{}}, acc, {{ {key}: item }}), {{}});\n"
    )


def snippet_no_conditional_empty_object_spread(*, twin: bool = False) -> str:
    field = "payload" if not twin else fresh_ident("field")
    cond = "ready" if not twin else fresh_ident("cond")
    return f"void ({{ ...({cond} ? {{ {field}: 1 }} : {{}}) }});\n"


def snippet_no_chained_type_assertions(*, twin: bool = False) -> str:
    target = "User" if not twin else fresh_ident("Target")
    value = "input" if not twin else fresh_ident("val")
    return f"{_SAFETY_COMMENT}\nvoid ({value} as unknown as {target});\n"


def snippet_no_known_value_widening(*, twin: bool = False) -> str:
    command = "Command" if not twin else fresh_ident("Cmd")
    binding = "commands" if not twin else fresh_ident("table")
    key = "start" if not twin else fresh_ident("go")
    starter = "startCommand" if not twin else fresh_ident("run")
    return (
        f"type {command} = () => void;\n"
        f"\n"
        f"const {binding}: Record<string, {command}> = {{ {key}: {starter} }};\n"
    )


def snippet_no_widen_then_assert(*, twin: bool = False) -> str:
    type_name = "UserId" if not twin else fresh_ident("Parsed")
    source = "source" if not twin else fresh_ident("src")
    wide = "widened" if not twin else fresh_ident("wide")
    parsed = "parsed" if not twin else fresh_ident("got")
    return (
        f"type {type_name} = {{ readonly id: string }};\n"
        f"\n"
        f"function load() {{\n"
        f"  const {source} = {{ id: \"second\" }};\n"
        f"  const {wide}: any = {source};\n"
        f"  {_SAFETY_COMMENT}\n"
        f"  const {parsed} = {wide} as {type_name};\n"
        f"\n"
        f"  return {parsed};\n"
        f"}}\n"
    )


def snippet_require_safety_comment_for_type_assertion(*, twin: bool = False) -> str:
    target = "User" if not twin else fresh_ident("Target")
    value = "input" if not twin else fresh_ident("val")
    return f"void ({value} as {target});\n"


def snippet_no_object_parameters(*, twin: bool = False) -> str:
    name = "accept" if not twin else fresh_ident("take")
    param = "value" if not twin else fresh_ident("arg")
    return f"function {name}({param}: object) {{}}\n"


def snippet_no_unknown_parameters(*, twin: bool = False) -> str:
    name = "parse" if not twin else fresh_ident("read")
    param = "value" if not twin else fresh_ident("arg")
    return f"function {name}({param}: unknown) {{}}\n"


def snippet_no_unknown_returns(*, twin: bool = False) -> str:
    name = "load" if not twin else fresh_ident("fetch")
    return f"function {name}(): unknown {{ return input; }}\n"


def snippet_no_unknown_type_aliases(*, twin: bool = False) -> str:
    alias = "UnusedAlias" if not twin else fresh_ident("Alias")
    return f"type {alias} = unknown;\n"


def snippet_no_unsafe_dictionary_type(*, twin: bool = False) -> str:
    alias = "OpenDict" if not twin else fresh_ident("Dict")
    return f"type {alias} = Record<string, unknown>;\n"


def snippet_no_runtime_typeof(*, twin: bool = False) -> str:
    name = "parseInput" if not twin else fresh_ident("check")
    param = "input" if not twin else fresh_ident("arg")
    return f"function {name}({param}) {{ return typeof {param} === \"string\"; }}\n"


def snippet_no_reflect_apply(*, twin: bool = False) -> str:
    op = "operation" if not twin else fresh_ident("op")
    owner = "owner" if not twin else fresh_ident("own")
    args = "args" if not twin else fresh_ident("argv")
    return f"Reflect.apply({op}, {owner}, {args});\n"


def snippet_no_reflect_get(*, twin: bool = False) -> str:
    owner = "owner" if not twin else fresh_ident("own")
    key = "key" if not twin else fresh_ident("slot")
    return f"Reflect.get({owner}, {key});\n"


def snippet_no_module_mocking(*, twin: bool = False) -> str:
    module = "./user-store" if not twin else f"./{fresh_ident('mod')}"
    return f"vi.mock(\"{module}\");\n"


def snippet_no_shape_in_symbol_names(*, twin: bool = False) -> str:
    if not twin:
        return "const shape = 1;\n"
    return f"const {fresh_ident('payload')}Shape = 1;\n"


def snippet_require_readable_spacing(*, twin: bool = False) -> str:
    first = "firstValue" if not twin else fresh_ident("one")
    second = "secondValue" if not twin else fresh_ident("two")
    return f"const {first} = 1;\nconst {second} = 2;\n"


def snippet_manual_tag_comparison() -> str:
    return 'void (value._tag === "Ready");\n'


def snippet_same_file_unknown_alias(*, twin: bool = False) -> str:
    alias = "UnknownValue" if not twin else fresh_ident("Alias")
    name = "load" if not twin else fresh_ident("fetch")
    return (
        f"type {alias} = unknown;\n"
        f"\n"
        f"function {name}(): {alias} {{\n"
        f"  return input;\n"
        f"}}\n"
    )


_SNIPPETS = {
    "no-array-filter-map": snippet_no_array_filter_map,
    "no-reduce-accumulator-copy": snippet_no_reduce_accumulator_copy,
    "no-chained-type-assertions": snippet_no_chained_type_assertions,
    "no-conditional-empty-object-spread": snippet_no_conditional_empty_object_spread,
    "no-known-value-widening": snippet_no_known_value_widening,
    "no-module-mocking": snippet_no_module_mocking,
    "no-object-parameters": snippet_no_object_parameters,
    "no-reflect-apply": snippet_no_reflect_apply,
    "no-reflect-get": snippet_no_reflect_get,
    "no-runtime-typeof": snippet_no_runtime_typeof,
    "no-shape-in-symbol-names": snippet_no_shape_in_symbol_names,
    "no-unknown-parameters": snippet_no_unknown_parameters,
    "no-unknown-returns": snippet_no_unknown_returns,
    "no-unknown-type-aliases": snippet_no_unknown_type_aliases,
    "no-unsafe-dictionary-type": snippet_no_unsafe_dictionary_type,
    "no-widen-then-assert": snippet_no_widen_then_assert,
    "require-readable-spacing": snippet_require_readable_spacing,
    "require-safety-comment-for-type-assertion": (
        snippet_require_safety_comment_for_type_assertion
    ),
}


def unique_source(rule_name: str, *, twin: bool = False) -> str:
    try:
        builder = _SNIPPETS[rule_name]
    except KeyError as exc:
        raise HarnessError(f"no unique snippet for {rule_name}") from exc
    return builder(twin=twin)


def write_cross_file_call_signature_filter_map(ws: Workspace) -> Path:
    """Write a file under lint whose only array evidence is a cross-file call.

    The other file exports a function with an explicit array return
    annotation (the call signature). The file under lint imports that
    function and chains adjacent filter then map on the call. Same-file
    array literals, annotations, and const aliases are absent from the
    file under lint.
    """
    factory = fresh_ident("make")
    keep = fresh_ident("keep")
    pick = fresh_ident("pick")
    mod_stem = fresh_ident("mod")
    mod_rel = f"{mod_stem}.ts"
    ws.write(
        mod_rel,
        f"export function {factory}(): string[] {{\n  return [];\n}}\n",
    )
    source = (
        f'import {{ {factory} }} from "./{mod_rel}";\n'
        f"\n"
        f"{factory}().filter({keep}).map({pick});\n"
    )
    path = ws.write(f"cross-sig-{fresh_ident('h')}.ts", source)
    print(
        f"cross-file call signature factory={mod_rel} consumer={path.name}",
        flush=True,
    )
    return path


def write_unique_snippet(
    ws: Workspace,
    rule_name: str,
    *,
    twin: bool = False,
    prefix: str = "",
) -> Path:
    token = fresh_ident("s")
    ext = snippet_extension(rule_name)
    rel = f"{prefix}{rule_name}-{token}.{ext}"
    source = unique_source(rule_name, twin=twin)
    print(f"write snippet {rel} for {rule_name} twin={twin}", flush=True)
    return ws.write(rel, source)


def assert_outbound_connect_blocked() -> None:
    """Positive control: a deliberate outbound connect from this process fails."""
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=2):
            raise AssertionError(
                "network observer is silent: outbound connect to 1.1.1.1:53 succeeded"
            )
    except OSError as exc:
        print(f"outbound connect blocked as required: {exc}", flush=True)


def run_copy_without_network(
    ws: Workspace,
    args: Sequence[str] | None = None,
) -> RunResult:
    """Run skill copy in the live network-less environment.

    The observer is this process: a deliberate outbound connect must fail
    (positive control). The copy then runs in the same environment. A silent
    observer (connect succeeds) fails the test. The copy child is the skill
    copy entry; dest population is asserted by the caller.
    """
    assert_outbound_connect_blocked()
    result = ws.copy(args)
    print(
        f"network-less copy exit={result.returncode} argv={list(result.argv)!r}",
        flush=True,
    )
    return result
