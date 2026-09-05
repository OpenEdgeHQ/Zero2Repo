#!/usr/bin/env python3
"""Validate OpenCode-produced artifact contracts (schema-only, language-agnostic).

Python orchestrators must not infer language, test framework, or file extensions.
OpenCode writes these JSON contracts; this module only validates structure and paths.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from timeout_config import validate_runner_timeouts

RUNNER_REQUIRED = (
    "language_label",
    "install_command",
    "test_command_template",
    "workdir",
)
RUNNER_OPTIONAL = (
    "build_command",
    "test_file_patterns",
    "source_file_patterns",
    # docker_image: optional base picked by init from the curated allowlist
    # (docker_agent.BASE_IMAGE_ALLOWLIST). When set it must be an allowlist member;
    # when absent the harness resolves DEFAULT_BASE_IMAGE. Language runtimes are
    # layered on top via install_command, so the base is OS-only.
    "docker_image",
    # docker_gpus: "all" (or a device spec) only for cases with a mandatory GPU profile.
    "docker_gpus",
)

TEST_MANIFEST_REQUIRED = ("schema_version", "step", "test_files", "test_command", "workdir")
TEST_USAGE_REQUIRED = ("schema_version", "modules", "names")
INTERFACE_DEPENDENCY_REQUIRED = ("target", "requirement", "test_refs")

HARDWARE_PROFILE_REQUIRED = ("id", "label", "probes")
HARDWARE_PROFILE_OPTIONAL = (
    "mandatory",
    "description",
    "setup_notes",
    "build_notes",
    "platforms",
    "required_platforms",
)
VALID_PLATFORMS = frozenset({"linux", "darwin", "windows"})

# coverage_matrix.json (judge-only, F-gate consumed): merges the capability inventory with
# the coverage proof. It is an internal artifact (may contain interface/surface names) and is
# NOT scanned as a public deliverable.
COVERAGE_MATRIX_ENTRY_REQUIRED = (
    "capability_id",
    "prd_refs",
    "priority",
    "coverage_status",
    "test_refs",
    "strength",
)
COVERAGE_MATRIX_ENTRY_OPTIONAL = (
    "expected_surface",
    "oracle",
    "mocking",
    "notes",
)
COVERAGE_PRIORITIES = frozenset({"core", "non_core"})
COVERAGE_STATUSES = frozenset({
    "core_covered",
    "representative_sampled",
    "bound_by_profile",
    "gap_or_risk",
    "out_of_scope",
})
# Ordered weakest→strongest is not implied; this is a closed enum of test-strength kinds.
COVERAGE_STRENGTHS = frozenset({
    "gpu_execution",
    "value_oracle",
    "invariant",
    "roundtrip",
    "negative_type",
    "isolation",
    "stateful",
    "smoke_only",
    "mock_contract",
    "mock_replaces_core_behavior",
})
# Strengths that are too weak to count as real coverage of a core capability.
COVERAGE_WEAK_STRENGTHS = frozenset({"smoke_only", "mock_replaces_core_behavior"})

SUITABILITY_VERDICTS = frozenset({"usable", "needs_trimming", "unusable"})
SUITABILITY_DIMENSIONS = (
    "external_resources",
    "environment_hardware",
    "blackbox_testability",
)
SUITABILITY_FINDING_SEVERITIES = frozenset({"error", "warning"})
SUITABILITY_ENVIRONMENT_METHODS = frozenset({"docker", "native", "none"})


@dataclass
class ContractIssue:
    severity: str  # "error" | "warning"
    rule: str
    message: str


def _is_str_list(value: object, field: str, issues: list[ContractIssue]) -> bool:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        issues.append(ContractIssue("error", "invalid-field", f"{field} must be a list of strings"))
        return False
    return True


def _identifiers_from_dependency_target(target: str) -> set[str]:
    """Extract identifier tokens from a dotted dependency target path."""
    names: set[str] = set()
    for segment in target.split("."):
        seg = segment.strip()
        if seg:
            names.add(seg)
    return names


def _validate_interface_dependencies(deps: object, issues: list[ContractIssue]) -> None:
    """Validate optional interface_dependencies list (extra fields allowed per entry)."""
    if deps is None:
        return
    if not isinstance(deps, list):
        issues.append(ContractIssue(
            "error", "invalid-field", "interface_dependencies must be a list",
        ))
        return
    for idx, entry in enumerate(deps):
        prefix = f"interface_dependencies[{idx}]"
        if not isinstance(entry, dict):
            issues.append(ContractIssue(
                "error", "invalid-field", f"{prefix} must be an object",
            ))
            continue
        for key in INTERFACE_DEPENDENCY_REQUIRED:
            if key not in entry:
                issues.append(ContractIssue(
                    "error", "missing-field", f"{prefix}.{key} is required",
                ))
        target = entry.get("target")
        if "target" in entry and (not isinstance(target, str) or not target.strip()):
            issues.append(ContractIssue(
                "error", "invalid-field", f"{prefix}.target must be a non-empty string",
            ))
        requirement = entry.get("requirement")
        if "requirement" in entry and (not isinstance(requirement, str) or not requirement.strip()):
            issues.append(ContractIssue(
                "error", "invalid-field", f"{prefix}.requirement must be a non-empty string",
            ))
        test_refs = entry.get("test_refs")
        if test_refs is not None:
            _is_str_list(test_refs, f"{prefix}.test_refs", issues)
        access = entry.get("access")
        if access is not None:
            _is_str_list(access, f"{prefix}.access", issues)
        elif any(key in entry for key in INTERFACE_DEPENDENCY_REQUIRED):
            issues.append(ContractIssue(
                "warning", "missing-access", f"{prefix}.access is recommended",
            ))
        members = entry.get("members")
        if members is not None:
            _is_str_list(members, f"{prefix}.members", issues)


def _interface_dependency_key(entry: dict) -> tuple[str, str]:
    target = entry.get("target", "")
    requirement = entry.get("requirement", "")
    if isinstance(target, str) and isinstance(requirement, str):
        return (target, requirement)
    return (json.dumps(entry, sort_keys=True), "")


def _merge_interface_dependency_entries(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    for key, value in incoming.items():
        if key == "test_refs":
            existing_refs = list(merged.get("test_refs", []) or [])
            seen_refs = set(existing_refs)
            for ref in value if isinstance(value, list) else []:
                if isinstance(ref, str) and ref not in seen_refs:
                    seen_refs.add(ref)
                    existing_refs.append(ref)
            merged["test_refs"] = existing_refs
        elif key == "access":
            existing_access = list(merged.get("access", []) or [])
            seen_access = set(existing_access)
            for access in value if isinstance(value, list) else []:
                if isinstance(access, str) and access not in seen_access:
                    seen_access.add(access)
                    existing_access.append(access)
            merged["access"] = existing_access
        elif key not in merged:
            merged[key] = value
    return merged


def normalize_runner(runner: dict) -> dict:
    """Map legacy manifest runner fields to the current contract schema."""
    normalized = dict(runner)
    if "language_label" not in normalized and "language" in normalized:
        normalized["language_label"] = normalized["language"]
    if "test_command_template" not in normalized and "test_command" in normalized:
        normalized["test_command_template"] = normalized["test_command"]
    install = normalized.get("install_command")
    if isinstance(install, str) and not install.strip():
        normalized["install_command"] = "true"
    return normalized


def validate_runner(runner: object) -> list[ContractIssue]:
    """Validate case-level runner block from init Round 0 / manifest.json."""
    issues: list[ContractIssue] = []
    if not isinstance(runner, dict):
        return [ContractIssue("error", "invalid-runner", "runner must be a JSON object")]

    runner = normalize_runner(runner)

    for key in RUNNER_REQUIRED:
        val = runner.get(key)
        if not isinstance(val, str) or not val.strip():
            issues.append(ContractIssue("error", "missing-field", f"runner.{key} is required"))

    for key in RUNNER_OPTIONAL:
        val = runner.get(key)
        if val is None:
            continue
        if key.endswith("_patterns"):
            _is_str_list(val, f"runner.{key}", issues)
        elif not isinstance(val, str):
            issues.append(ContractIssue("error", "invalid-field", f"runner.{key} must be a string"))

    docker_image = runner.get("docker_image")
    if isinstance(docker_image, str) and docker_image.strip():
        from docker_agent import BASE_IMAGE_ALLOWLIST

        if docker_image.strip() not in BASE_IMAGE_ALLOWLIST:
            issues.append(ContractIssue(
                "error",
                "invalid-base-image",
                f"runner.docker_image {docker_image.strip()!r} is not in the curated base "
                f"allowlist {list(BASE_IMAGE_ALLOWLIST)}; pick the closest OS match and "
                "install language runtimes via install_command",
            ))

    tpl = runner.get("test_command_template", "")
    if isinstance(tpl, str) and tpl and "{test_files}" not in tpl and "{test_dir}" not in tpl:
        issues.append(ContractIssue(
            "warning",
            "template-placeholders",
            "runner.test_command_template should include {test_files} or {test_dir}",
        ))

    for rule, message in validate_runner_timeouts(runner):
        issues.append(ContractIssue("error", rule, message))

    issues.extend(validate_runner_bakeability(runner))

    return issues


def validate_runner_bakeability(runner: dict) -> list[ContractIssue]:
    """Lint runner commands for patterns that break docker-commit bakeability."""
    issues: list[ContractIssue] = []
    install = runner.get("install_command", "")
    build = runner.get("build_command", "")
    if not isinstance(install, str):
        install = ""
    if not isinstance(build, str):
        build = ""
    combined = f"{install}\n{build}"

    if re.search(r"\brustup\b", combined) and not re.search(
        r"\b(CARGO_HOME|RUSTUP_HOME)\b", combined
    ):
        issues.append(ContractIssue(
            "warning",
            "bakeability-rustup",
            "rustup appears without CARGO_HOME/RUSTUP_HOME; the toolchain may install "
            "under $HOME and not survive docker commit or recipe replay",
        ))

    lang_managers = (
        ("nvm install", "nvm"),
        ("pyenv install", "pyenv"),
        ("rbenv install", "rbenv"),
    )
    for needle, label in lang_managers:
        if needle in combined and not re.search(
            r"(/usr/local|/opt/|XDG_|NVM_DIR=|PYENV_ROOT=|RBENV_ROOT=)",
            combined,
        ):
            issues.append(ContractIssue(
                "warning",
                "bakeability-lang-manager",
                f"{label} install without an explicit image-local path may not bake into :final",
            ))

    for field, val in (("install_command", install), ("build_command", build)):
        if isinstance(val, str) and (
            re.search(r"\$HOME|~/\.", val) or "--user" in val
        ):
            issues.append(ContractIssue(
                "warning",
                "bakeability-home-path",
                f"runner.{field} references $HOME, ~/. paths, or pip --user; prefer "
                "/usr/local or /opt paths so recipe replay matches :final",
            ))

    return issues


def validate_hardware_requirements(hw: object) -> list[ContractIssue]:
    """Validate case-level hardware_requirements from init Round 0 / manifest.json."""
    issues: list[ContractIssue] = []
    if not isinstance(hw, dict):
        return [ContractIssue("error", "invalid-hardware", "hardware_requirements must be a JSON object")]

    if hw.get("schema_version") != 1:
        issues.append(ContractIssue(
            "warning", "schema-version",
            "hardware_requirements.schema_version should be 1",
        ))

    summary = hw.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        issues.append(ContractIssue(
            "error", "missing-field", "hardware_requirements.summary is required",
        ))

    profiles = hw.get("profiles")
    if not isinstance(profiles, list) or len(profiles) == 0:
        issues.append(ContractIssue(
            "error", "missing-field", "hardware_requirements.profiles must be a non-empty list",
        ))
        return issues

    seen_ids: set[str] = set()
    has_mandatory = False
    for idx, profile in enumerate(profiles):
        prefix = f"hardware_requirements.profiles[{idx}]"
        if not isinstance(profile, dict):
            issues.append(ContractIssue("error", "invalid-field", f"{prefix} must be an object"))
            continue

        for key in HARDWARE_PROFILE_REQUIRED:
            val = profile.get(key)
            if key == "probes":
                if not _is_str_list(val, f"{prefix}.{key}", issues) or not val:
                    if isinstance(val, list) and len(val) == 0:
                        issues.append(ContractIssue(
                            "error", "empty-probes", f"{prefix}.probes must not be empty",
                        ))
            elif not isinstance(val, str) or not val.strip():
                issues.append(ContractIssue(
                    "error", "missing-field", f"{prefix}.{key} is required",
                ))

        pid = profile.get("id")
        if isinstance(pid, str):
            if pid in seen_ids:
                issues.append(ContractIssue(
                    "error", "duplicate-id", f"duplicate hardware profile id: {pid}",
                ))
            seen_ids.add(pid)

        if profile.get("mandatory") is True:
            has_mandatory = True

        for plat_field in ("platforms", "required_platforms"):
            plats = profile.get(plat_field)
            if plats is None:
                continue
            if not _is_str_list(plats, f"{prefix}.{plat_field}", issues):
                continue
            for plat in plats:
                if plat not in VALID_PLATFORMS:
                    issues.append(ContractIssue(
                        "warning", "unknown-platform",
                        f"{prefix}.{plat_field} contains unknown platform {plat!r}; "
                        f"expected one of {sorted(VALID_PLATFORMS)}",
                    ))

    if not has_mandatory:
        issues.append(ContractIssue(
            "warning", "no-mandatory-profile",
            "hardware_requirements should include at least one mandatory profile",
        ))

    return issues


def validate_suitability(data: object) -> list[ContractIssue]:
    """Validate repo suitability assessment JSON (schema-only, no content judgment)."""
    issues: list[ContractIssue] = []
    if not isinstance(data, dict):
        return [ContractIssue("error", "invalid-suitability", "suitability must be a JSON object")]

    if data.get("schema_version") != 1:
        issues.append(ContractIssue(
            "warning", "schema-version", "suitability.schema_version should be 1",
        ))

    for key in ("case_id", "repo_slug", "repository_url", "summary", "assessed_at"):
        val = data.get(key)
        if not isinstance(val, str) or not val.strip():
            issues.append(ContractIssue("error", "missing-field", f"suitability.{key} is required"))

    verdict = data.get("verdict")
    if verdict not in SUITABILITY_VERDICTS:
        issues.append(ContractIssue(
            "error", "invalid-verdict",
            f"suitability.verdict must be one of {sorted(SUITABILITY_VERDICTS)}",
        ))

    dimensions = data.get("dimensions")
    if not isinstance(dimensions, dict):
        issues.append(ContractIssue(
            "error", "missing-field", "suitability.dimensions must be an object",
        ))
    else:
        for dim in SUITABILITY_DIMENSIONS:
            block = dimensions.get(dim)
            prefix = f"suitability.dimensions.{dim}"
            if not isinstance(block, dict):
                issues.append(ContractIssue(
                    "error", "missing-field", f"{prefix} must be an object",
                ))
                continue
            if not isinstance(block.get("passed"), bool):
                issues.append(ContractIssue(
                    "error", "invalid-field", f"{prefix}.passed must be a boolean",
                ))
            findings = block.get("findings")
            if not isinstance(findings, list):
                issues.append(ContractIssue(
                    "error", "invalid-field", f"{prefix}.findings must be a list",
                ))
            else:
                for idx, finding in enumerate(findings):
                    fprefix = f"{prefix}.findings[{idx}]"
                    if not isinstance(finding, dict):
                        issues.append(ContractIssue(
                            "error", "invalid-field", f"{fprefix} must be an object",
                        ))
                        continue
                    sev = finding.get("severity")
                    if sev not in SUITABILITY_FINDING_SEVERITIES:
                        issues.append(ContractIssue(
                            "error", "invalid-field",
                            f"{fprefix}.severity must be error or warning",
                        ))
                    msg = finding.get("message")
                    if not isinstance(msg, str) or not msg.strip():
                        issues.append(ContractIssue(
                            "error", "missing-field", f"{fprefix}.message is required",
                        ))

    evidence = data.get("empirical_evidence")
    if not isinstance(evidence, dict):
        issues.append(ContractIssue(
            "error", "missing-field", "suitability.empirical_evidence must be an object",
        ))
    else:
        method = evidence.get("environment_method")
        if method not in SUITABILITY_ENVIRONMENT_METHODS:
            issues.append(ContractIssue(
                "error", "invalid-field",
                "suitability.empirical_evidence.environment_method must be "
                f"one of {sorted(SUITABILITY_ENVIRONMENT_METHODS)}",
            ))
        for key in (
            "dockerfile_path",
            "docker_image_tag",
            "docker_image_path",
            "install_command",
            "build_command",
            "test_command",
            "install_output_summary",
            "build_output_summary",
            "test_output_summary",
        ):
            val = evidence.get(key)
            if val is not None and not isinstance(val, str):
                issues.append(ContractIssue(
                    "error", "invalid-field",
                    f"suitability.empirical_evidence.{key} must be a string",
                ))
        for key in ("install_exit_code", "build_exit_code", "test_exit_code"):
            val = evidence.get(key)
            if val is not None and not isinstance(val, int):
                issues.append(ContractIssue(
                    "error", "invalid-field",
                    f"suitability.empirical_evidence.{key} must be an integer",
                ))
        if not isinstance(evidence.get("docker_image_saved"), bool):
            issues.append(ContractIssue(
                "error", "invalid-field",
                "suitability.empirical_evidence.docker_image_saved must be a boolean",
            ))
        if not isinstance(evidence.get("tests_passed"), bool):
            issues.append(ContractIssue(
                "error", "invalid-field",
                "suitability.empirical_evidence.tests_passed must be a boolean",
            ))

    for key in ("recommended_trim", "blocking_items"):
        val = data.get(key)
        if val is None:
            continue
        if not _is_str_list(val, f"suitability.{key}", issues):
            continue

    return issues


def format_hardware_block(hw: object, *, platform: str | None = None) -> str:
    """Format hardware requirements for prompt injection."""
    from hardware_requirements import format_hardware_block as _format_hardware_block

    return _format_hardware_block(hw, platform=platform)


def _command_operand_tokens(command: str) -> list[str]:
    """Return operand tokens from a resolved shell command (language-agnostic).

    Drops flags (leading ``-``), env assignments (``NAME=value``) and unresolved
    ``{placeholder}`` tokens. No extension, language, or framework knowledge is
    used — callers decide meaning purely from filesystem existence.
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        return []
    operands: list[str] = []
    for tok in parts:
        if not tok or tok.startswith("-"):
            continue
        if "{" in tok or "}" in tok:
            continue
        if "=" in tok.split("/", 1)[0]:  # env assignment, e.g. PYTHONPATH=code
            continue
        operands.append(tok)
    return operands


def _path_exists_safe(base: Path, token: str) -> bool:
    """``(base / token).exists()`` that never raises on pathological tokens.

    Command operands can be long quoted arguments (e.g. a space-joined list of
    build targets) rather than real paths. Probing such a token as a path can
    exceed the filesystem name limit (ENAMETOOLONG) or embed NUL bytes; either
    way the token is simply not an existing path, so swallow OSError/ValueError
    instead of crashing the manifest validation.
    """
    try:
        return (base / token).exists()
    except (OSError, ValueError):
        return False


def _check_command_paths_resolve(
    manifest: dict,
    step_dir: Path,
    workdir: Path,
    issues: list[ContractIssue],
) -> None:
    """Flag a workdir that cannot resolve a path the test_command explicitly names.

    Purely structural and language-agnostic: a token is treated as a misplaced
    path only when it does NOT exist relative to the declared ``workdir`` but DOES
    exist relative to a deeper directory inside the step tree (e.g. ``code/``).
    Tokens that exist nowhere (binary names, reporters, runner subcommands) are
    ignored, so this never infers language, framework, or file extensions.

    This catches the common milestone drift where the runner contract's
    repo-root ``workdir`` (``"."``) is copied verbatim even though the milestone
    places the implementation and its config files under ``code/``.
    """
    template = manifest.get("test_command")
    if not isinstance(template, str) or not template.strip():
        return
    test_files = [f for f in manifest.get("test_files", []) if isinstance(f, str)]
    try:
        resolved = apply_test_manifest_command(
            template, step_dir=step_dir, workdir=workdir, test_files_rel=test_files,
        )
    except Exception:
        return

    workdir = workdir.resolve()
    step_root = step_dir.resolve()
    # Candidate anchors: one level of step subdirectories deeper than the step
    # root (typically code/, tests/). Excludes the declared workdir itself so we
    # only ever suggest moving the cwd *into* a subtree, never out of one.
    candidates = [d for d in sorted(step_root.iterdir()) if d.is_dir()]
    for tok in _command_operand_tokens(resolved):
        if _path_exists_safe(workdir, tok):
            continue
        better = next(
            (d for d in candidates if d.resolve() != workdir and _path_exists_safe(d, tok)),
            None,
        )
        if better is not None:
            rel = os.path.relpath(better, step_root)
            issues.append(ContractIssue(
                "error",
                "workdir-unresolved",
                f"test_command references '{tok}', which does not exist under the "
                f"declared workdir '{manifest.get('workdir')}' but does exist under "
                f"'{rel}'. Set workdir to '{rel}' so the command runs from there.",
            ))
            return


# Interpreters that execute only their FIRST script argument and pass the rest as
# argv. A bare ``<interp> {test_files}`` expanded to multiple files therefore runs
# only the first file and silently drops the others, making the exit code lie about
# the suite. Test runners (pytest, jest, mocha, ...) instead consume every file.
_SINGLE_SCRIPT_INTERPRETERS: frozenset[str] = frozenset({
    "python", "python2", "python3", "node", "nodejs", "ruby", "php",
    "perl", "lua", "bash", "sh", "zsh", "Rscript", "deno", "bun",
})


def _bare_interpreter_multifile(cmd: str) -> bool:
    """True when ``cmd`` feeds ``{test_files}`` directly to a single-script interpreter.

    Detects the ``python {test_files}`` family (optionally with ``NAME=value`` env
    prefixes and flags), where multiple files would only run the first. Templates that
    route files through a runner (``python -m pytest {test_files}``, ``npx jest ...``)
    or use ``{test_dir}`` are not flagged.
    """
    if "{test_files}" not in cmd or "{test_dir}" in cmd:
        return False
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return False
    idx = 0
    while idx < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[idx]):
        idx += 1
    if idx >= len(tokens):
        return False
    program = tokens[idx].rsplit("/", 1)[-1]
    files_at = next((j for j, t in enumerate(tokens) if "{test_files}" in t), None)
    if files_at is None or files_at <= idx:
        return False
    non_flag_between = [t for t in tokens[idx + 1:files_at] if not t.startswith("-")]
    if non_flag_between:
        return False
    return program in _SINGLE_SCRIPT_INTERPRETERS


def validate_test_manifest(manifest: object, step_dir: Path | None = None) -> list[ContractIssue]:
    """Validate test_manifest.json; optionally check paths exist under step_dir."""
    issues: list[ContractIssue] = []
    if not isinstance(manifest, dict):
        return [ContractIssue("error", "invalid-manifest", "test_manifest must be a JSON object")]

    for key in TEST_MANIFEST_REQUIRED:
        if key not in manifest:
            issues.append(ContractIssue("error", "missing-field", f"test_manifest.{key} is required"))

    if not _is_str_list(manifest.get("test_files"), "test_files", issues):
        pass
    elif len(manifest.get("test_files", [])) == 0:
        issues.append(ContractIssue("error", "empty-test-files", "test_files must not be empty"))

    if not isinstance(manifest.get("test_command"), str) or not manifest["test_command"].strip():
        issues.append(ContractIssue("error", "invalid-field", "test_command must be a non-empty string"))
    else:
        cmd = manifest["test_command"]
        if "{test_files}" not in cmd and "{test_dir}" not in cmd:
            issues.append(ContractIssue(
                "warning",
                "template-placeholders",
                "test_command should include {test_files} or {test_dir} placeholders",
            ))
        test_files = manifest.get("test_files")
        if (
            isinstance(test_files, list)
            and len(test_files) > 1
            and _bare_interpreter_multifile(cmd)
        ):
            issues.append(ContractIssue(
                "error",
                "multifile-bare-interpreter",
                "test_command runs a bare interpreter on multiple {test_files}; a bare "
                "interpreter executes only the first file and ignores the rest. Use a "
                "test runner (e.g. 'python -m pytest {test_files}'), a {test_dir} entry "
                "point, or split into one file.",
            ))

    if not isinstance(manifest.get("workdir"), str) or not manifest["workdir"].strip():
        issues.append(ContractIssue("error", "invalid-field", "workdir must be a non-empty string"))

    if step_dir is not None:
        workdir = step_dir / manifest.get("workdir", "")
        if not workdir.is_dir():
            issues.append(ContractIssue("error", "missing-workdir", f"workdir not found: {workdir}"))
        else:
            _check_command_paths_resolve(manifest, step_dir, workdir, issues)
        for rel in manifest.get("test_files", []):
            if not isinstance(rel, str):
                continue
            rel_path = Path(rel)
            if rel_path.is_absolute():
                issues.append(ContractIssue(
                    "error", "absolute-path", f"test_files must be relative to step dir: {rel}",
                ))
                continue
            if ".." in rel_path.parts:
                issues.append(ContractIssue(
                    "error", "parent-segment",
                    f"test_files must not contain '..'; use step-relative paths like tests/<file>: {rel}",
                ))
                continue
            tf = step_dir / rel
            if not tf.is_file():
                issues.append(ContractIssue("error", "missing-test-file", f"test file not found: {tf}"))
            else:
                try:
                    tf.resolve().relative_to(step_dir.resolve())
                except ValueError:
                    issues.append(ContractIssue(
                        "error", "path-escape", f"test file must be under step dir: {rel}",
                    ))
    return issues


def resolve_test_command_placeholders(
    step_dir: Path,
    workdir: Path,
    test_files_rel: list[str],
) -> tuple[list[str], str]:
    """Resolve {test_files} and {test_dir} paths relative to shell cwd (workdir).

    test_files_rel are always relative to the milestone step root (e.g. tests/foo.c).
    The returned paths are suitable for substitution into test_command before bash runs
    with cwd=workdir.
    """
    step_dir = step_dir.resolve()
    workdir = workdir.resolve()
    files_for_cmd: list[str] = []
    for rel in test_files_rel:
        if not isinstance(rel, str) or not rel.strip():
            continue
        abs_path = (step_dir / rel).resolve()
        files_for_cmd.append(os.path.relpath(abs_path, workdir))
    tests_root = (step_dir / "tests").resolve()
    test_dir = os.path.relpath(tests_root, workdir) if tests_root.is_dir() else "."
    return files_for_cmd, test_dir


def validate_test_usage(usage: object) -> list[ContractIssue]:
    """Validate test_usage.json structure."""
    issues: list[ContractIssue] = []
    if not isinstance(usage, dict):
        return [ContractIssue("error", "invalid-usage", "test_usage must be a JSON object")]

    for key in TEST_USAGE_REQUIRED:
        if key not in usage:
            issues.append(ContractIssue("error", "missing-field", f"test_usage.{key} is required"))

    _is_str_list(usage.get("modules"), "modules", issues)
    _is_str_list(usage.get("names"), "names", issues)

    imports = usage.get("imports")
    if imports is not None and not isinstance(imports, list):
        issues.append(ContractIssue("error", "invalid-field", "imports must be a list"))
    _validate_interface_dependencies(usage.get("interface_dependencies"), issues)
    return issues


def validate_coverage_matrix(data: object) -> list[ContractIssue]:
    """Validate coverage_matrix.json (schema + enum closure, language-agnostic).

    The matrix is the single new judge-only structured artifact: it lists every capability
    in scope, classifies each as ``core``/``non_core``, and records the coverage status,
    test references, and test strength. Schema validation here is the substrate the F-gate's
    semantic checks (core capabilities must be covered by real, non-mock tests) build on.
    """
    issues: list[ContractIssue] = []
    if not isinstance(data, dict):
        return [ContractIssue("error", "invalid-coverage-matrix", "coverage_matrix must be a JSON object")]

    if data.get("schema_version") != 1:
        issues.append(ContractIssue(
            "warning", "schema-version", "coverage_matrix.schema_version should be 1",
        ))

    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list) or len(capabilities) == 0:
        issues.append(ContractIssue(
            "error", "missing-field", "coverage_matrix.capabilities must be a non-empty list",
        ))
        return issues

    seen_ids: set[str] = set()
    for idx, entry in enumerate(capabilities):
        prefix = f"capabilities[{idx}]"
        if not isinstance(entry, dict):
            issues.append(ContractIssue("error", "invalid-field", f"{prefix} must be an object"))
            continue

        for key in COVERAGE_MATRIX_ENTRY_REQUIRED:
            if key not in entry:
                issues.append(ContractIssue(
                    "error", "missing-field", f"{prefix}.{key} is required",
                ))

        cap_id = entry.get("capability_id")
        if isinstance(cap_id, str) and cap_id.strip():
            if cap_id in seen_ids:
                issues.append(ContractIssue(
                    "error", "duplicate-id", f"duplicate capability_id: {cap_id}",
                ))
            seen_ids.add(cap_id)
        elif "capability_id" in entry:
            issues.append(ContractIssue(
                "error", "invalid-field", f"{prefix}.capability_id must be a non-empty string",
            ))

        _is_str_list(entry.get("prd_refs", []), f"{prefix}.prd_refs", issues)
        _is_str_list(entry.get("test_refs", []), f"{prefix}.test_refs", issues)

        priority = entry.get("priority")
        if priority is not None and priority not in COVERAGE_PRIORITIES:
            issues.append(ContractIssue(
                "error", "invalid-field",
                f"{prefix}.priority must be one of {sorted(COVERAGE_PRIORITIES)}",
            ))

        status = entry.get("coverage_status")
        if status is not None and status not in COVERAGE_STATUSES:
            issues.append(ContractIssue(
                "error", "invalid-field",
                f"{prefix}.coverage_status must be one of {sorted(COVERAGE_STATUSES)}",
            ))

        strength = entry.get("strength")
        # strength may be a single value or a list (a capability covered by several tests).
        strengths = strength if isinstance(strength, list) else [strength]
        for s in strengths:
            if s is not None and s not in COVERAGE_STRENGTHS:
                issues.append(ContractIssue(
                    "error", "invalid-field",
                    f"{prefix}.strength must be drawn from {sorted(COVERAGE_STRENGTHS)}",
                ))
    return issues


def coverage_matrix_core_gaps(data: dict) -> list[ContractIssue]:
    """Semantic F-gate: every ``core`` capability must be genuinely covered.

    A core capability must (a) declare ``coverage_status: core_covered``, (b) have at least
    one ``test_refs`` entry, and (c) not rely solely on a weak strength (``smoke_only`` /
    ``mock_replaces_core_behavior``). ``gap_or_risk`` or ``out_of_scope`` is not acceptable
    for a core capability. Assumes the schema already validated.
    """
    issues: list[ContractIssue] = []
    for entry in data.get("capabilities", []) or []:
        if not isinstance(entry, dict) or entry.get("priority") != "core":
            continue
        cap_id = entry.get("capability_id", "<unknown>")
        status = entry.get("coverage_status")
        if status != "core_covered":
            issues.append(ContractIssue(
                "error", "core-not-covered",
                f"core capability '{cap_id}' has coverage_status={status!r} (must be core_covered)",
            ))
        test_refs = entry.get("test_refs") or []
        if not isinstance(test_refs, list) or len(test_refs) == 0:
            issues.append(ContractIssue(
                "error", "core-no-test",
                f"core capability '{cap_id}' has no test_refs",
            ))
        strength = entry.get("strength")
        strengths = set(strength if isinstance(strength, list) else [strength])
        if strengths and strengths <= COVERAGE_WEAK_STRENGTHS:
            issues.append(ContractIssue(
                "error", "core-weak-strength",
                f"core capability '{cap_id}' relies only on weak strength {sorted(strengths)}",
            ))
    return issues


def load_json(path: Path) -> tuple[dict | None, list[ContractIssue]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except FileNotFoundError:
        return None, [ContractIssue("error", "missing-file", f"Missing {path}")]
    except json.JSONDecodeError as exc:
        return None, [ContractIssue("error", "invalid-json", f"Invalid JSON in {path}: {exc}")]


def test_usage_names(usage: dict) -> set[str]:
    names = set(usage.get("names", []) or [])
    for imp in usage.get("imports", []) or []:
        if isinstance(imp, dict):
            for n in imp.get("names", []) or []:
                if isinstance(n, str):
                    names.add(n)
    for dep in usage.get("interface_dependencies", []) or []:
        if isinstance(dep, dict):
            target = dep.get("target")
            if isinstance(target, str):
                names.update(_identifiers_from_dependency_target(target))
    return names


_COVERAGE_GENERIC_ARG_SPACE_RE = re.compile(r",\s+")
_COVERAGE_IL_ARITY_SUFFIX_RE = re.compile(r"`\d+$")


def _normalize_coverage_generics(text: str) -> str:
    """Collapse whitespace after commas inside angle-bracket generic lists."""
    def _collapse_generic_arg_spaces(match: re.Match[str]) -> str:
        inner = _COVERAGE_GENERIC_ARG_SPACE_RE.sub(",", match.group(1))
        return f"<{inner}>"

    normalized = text or ""
    while True:
        updated = re.sub(r"<([^<>]+)>", _collapse_generic_arg_spaces, normalized)
        if updated == normalized:
            break
        normalized = updated
    return normalized


def _normalize_coverage_symbol(symbol: str) -> str:
    """Normalize a symbol for language-agnostic Contract coverage matching."""
    s = (symbol or "").strip()
    if not s:
        return s
    s = _COVERAGE_IL_ARITY_SUFFIX_RE.sub("", s)
    return _normalize_coverage_generics(s)


def _normalize_coverage_text(text: str) -> str:
    """Apply the same normalization rules to Contract prose before matching."""
    return _normalize_coverage_generics(text or "")


def _coverage_leaf_identifier(symbol: str) -> str:
    """Return the trailing identifier for dotted or C++ scoped symbols."""
    s = (symbol or "").strip()
    if not s:
        return s
    if "." in s:
        return s.rsplit(".", 1)[-1].strip()
    if "::" in s:
        return s.rsplit("::", 1)[-1].strip()
    return s


def _symbol_word_present(text: str, token: str) -> bool:
    """True when ``token`` appears as a whole identifier in ``text``."""
    leaf = (token or "").strip()
    if not leaf:
        return False
    return (
        re.search(
            r"(?<![A-Za-z0-9_])" + re.escape(leaf) + r"(?![A-Za-z0-9_])",
            text,
        )
        is not None
    )


def _symbol_present_in_text(text: str, symbol: str) -> bool:
    """Language-agnostic membership: full dotted path as substring, else leaf token.

    A symbol counts as covered when its exact (possibly dotted) form appears as a
    substring, or when its trailing identifier appears as a whole word. This mirrors
    how a Contract document references a public name: either the fully-qualified path
    (``pkg.mod.Name``, ``ns::Type::Method``) or the bare leaf (``Name``) inside prose /
    signatures / tables.

    Generic-argument spacing (``<A, B>`` vs ``<A,B>``) and .NET IL arity suffixes
    (``Type`1``) are normalized before comparison so Contract prose is not penalized
    for canonical formatting differences.
    """
    s = _normalize_coverage_symbol((symbol or "").strip())
    if not s:
        return True
    normalized_text = _normalize_coverage_text(text)
    # Path-style module/header tokens may appear verbatim in Contract tables.
    if "/" in s or "\\" in s:
        if s.replace("\\", "/") in normalized_text.replace("\\", "/"):
            return True
    # Dotted paths (pkg.mod.Name) may appear verbatim as a substring in tables/prose.
    if "." in s and s in normalized_text:
        return True
    # C++ scoped paths (gpp::DeviceReduce::Reduce) may appear verbatim as a substring.
    if "::" in s and s in normalized_text:
        return True
    # Match the trailing identifier as a whole word, never as a substring of a larger
    # token — so a bare name like ``App`` is not "covered" by the word ``Application``.
    leaf = _coverage_leaf_identifier(s)
    if not leaf:
        return False
    return _symbol_word_present(normalized_text, leaf)


def _is_product_module_for_coverage(module: str, all_modules: list[str], usage: dict) -> bool:
    """Return True when a ``test_usage.json`` module token is part of the public product API.

    Bare tokens without path separators are treated as harness/stdlib imports unless
    they are clearly product roots: referenced in ``names``/``imports``, prefixed by
    other modules, or the sole module entry in the usage inventory.
    """
    mod = (module or "").strip()
    if not mod:
        return False
    if "/" in mod or "\\" in mod:
        return True
    if "." in mod:
        return True

    prefix_dot = mod + "."
    for name in usage.get("names", []) or []:
        if isinstance(name, str) and (name == mod or name.startswith(prefix_dot)):
            return True

    prefix_slash = mod + "/"
    for other in all_modules:
        if other == mod:
            continue
        if other.startswith(prefix_slash) or other.startswith(prefix_dot):
            return True

    for imp in usage.get("imports", []) or []:
        if not isinstance(imp, dict) or imp.get("module") != mod:
            continue
        imp_names = imp.get("names") or []
        if any(isinstance(n, str) and n.strip() for n in imp_names):
            return True

    if len(all_modules) == 1 and all_modules[0] == mod:
        return True

    return False


def infer_interface_dependency_members(target: str, requirement: str) -> list[str] | None:
    """Infer public member symbols for synthetic grouped dependency targets.

    Used when backfilling ``interface_dependencies[].members`` so coverage checks
    validate real API/command names instead of internal grouped target keys.
    """
    leaf = (target or "").rsplit(".", 1)[-1].strip()
    req = requirement or ""

    if leaf == "ChaosPipelineBuilderExtensions":
        members = re.findall(r"AddChaos\w+", req)
        return members or None

    backtick_tokens: list[str] = []
    for raw in re.findall(r"`([^`]+)`", req):
        token = raw.strip().split()[0]
        if token and token not in backtick_tokens:
            backtick_tokens.append(token)
    if backtick_tokens and (
        leaf.startswith("-")
        or ".cli." in target
        or target.startswith("kvcache.cli")
    ):
        return backtick_tokens

    if "_" in leaf and leaf.replace("_", "").isalnum():
        parts = leaf.split("_")
        if len(parts) >= 2:
            return parts

    return None


def _expand_dependency_tokens(tokens: list[str]) -> list[str]:
    """Expand synthetic grouped identifiers (``append_prepend``) into checkable parts."""
    expanded: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        for part in [tok, *tok.split("_")] if "_" in tok else [tok]:
            if part and part not in seen:
                seen.add(part)
                expanded.append(part)
    return expanded


def _dependency_target_present_in_text(
    text: str,
    target: str,
    members: list[str] | None = None,
) -> bool:
    """A dependency target is covered when any identifier token it names is present.

    ``interface_dependencies[].target`` can be a dotted path (``pkg.mod.Class.attr``)
    or carry a free-text qualifier (``cloudsync_client (native library discovery)``).
    Extract identifier-ish tokens and treat the target as covered when at least one
    is present, keeping false-positive noise low for a report-to-E (warning) signal.

    When ``members`` is a non-empty list, coverage is decided by whether every listed
    public symbol or command name appears in the Contract (for synthetic grouped targets
    whose ``target`` leaf is an internal coverage key, not a real API name).
    """
    if members:
        return all(_symbol_present_in_text(text, member) for member in members)
    tokens = _expand_dependency_tokens(
        re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", target or "")
    )
    if not tokens:
        return True
    return any(_symbol_present_in_text(text, tok) for tok in tokens)


@dataclass
class ContractCoverage:
    """Forward-coverage report: which test_usage symbols are absent from the Contract."""

    missing_names: list[str]
    missing_modules: list[str]
    missing_dep_targets: list[str]
    total_names: int
    total_modules: int
    total_deps: int

    @property
    def has_gaps(self) -> bool:
        return bool(self.missing_names or self.missing_modules or self.missing_dep_targets)


def compute_contract_coverage(usage: dict, contract_text: str) -> ContractCoverage:
    """Compute which ``test_usage.json`` symbols are not referenced by the Contract text.

    Language-agnostic and deterministic: no AST, no framework assumptions. Covers the
    three observable surfaces the hidden tests rely on — module paths, imported/called
    names, and ``interface_dependencies`` targets — so a missing entry flags a Contract
    that under-specifies the public interface (a solvability gap, not a difficulty knob).
    """
    text = contract_text or ""

    module_set: list[str] = []
    seen_modules: set[str] = set()
    for mod in usage.get("modules", []) or []:
        if isinstance(mod, str) and mod not in seen_modules:
            seen_modules.add(mod)
            module_set.append(mod)
    for imp in usage.get("imports", []) or []:
        if isinstance(imp, dict):
            mod = imp.get("module")
            if isinstance(mod, str) and mod not in seen_modules:
                seen_modules.add(mod)
                module_set.append(mod)

    name_set: list[str] = []
    seen_names: set[str] = set()
    for name in usage.get("names", []) or []:
        if isinstance(name, str) and name not in seen_names:
            seen_names.add(name)
            name_set.append(name)
    for imp in usage.get("imports", []) or []:
        if isinstance(imp, dict):
            for n in imp.get("names", []) or []:
                if isinstance(n, str) and n not in seen_names:
                    seen_names.add(n)
                    name_set.append(n)

    dep_targets: list[tuple[str, list[str] | None]] = []
    for dep in usage.get("interface_dependencies", []) or []:
        if isinstance(dep, dict):
            target = dep.get("target")
            members_raw = dep.get("members")
            members: list[str] | None = None
            if isinstance(members_raw, list):
                members = [
                    m.strip()
                    for m in members_raw
                    if isinstance(m, str) and m.strip()
                ] or None
            if isinstance(target, str) and target.strip():
                dep_targets.append((target, members))

    product_modules = [
        m for m in module_set if _is_product_module_for_coverage(m, module_set, usage)
    ]
    missing_modules = [
        m for m in product_modules if not _symbol_present_in_text(text, m)
    ]
    missing_names = [n for n in name_set if not _symbol_present_in_text(text, n)]
    missing_dep_targets = [
        target
        for target, members in dep_targets
        if not _dependency_target_present_in_text(text, target, members)
    ]

    return ContractCoverage(
        missing_names=missing_names,
        missing_modules=missing_modules,
        missing_dep_targets=missing_dep_targets,
        total_names=len(name_set),
        total_modules=len(module_set),
        total_deps=len(dep_targets),
    )


def format_runner_block(runner: dict) -> str:
    """Format runner for prompt injection."""
    lines = [
        f"- language_label: {runner.get('language_label', '')}",
        f"- install_command: {runner.get('install_command', '')}",
        f"- build_command: {runner.get('build_command', '(none)')}",
        f"- test_command_template: {runner.get('test_command_template', '')}",
        f"- workdir: {runner.get('workdir', '.')}",
    ]
    patterns = runner.get("test_file_patterns") or []
    if patterns:
        lines.append(f"- test_file_patterns: {', '.join(patterns)}")
    return "\n".join(lines)


def render_test_command(template: str, *, test_files: list[str], test_dir: str) -> str:
    """Substitute placeholders in runner or test command template."""
    files_str = " ".join(test_files)
    return template.replace("{test_files}", files_str).replace("{test_dir}", test_dir)


def render_test_commands(template: str, *, test_files: list[str], test_dir: str) -> list[str]:
    """Render a template into one shell command per test file when needed.

    A ``{test_files}`` template that lists multiple files in a single command is a
    trap for bare interpreters: ``python a.py b.py c.py`` runs only ``a.py`` and
    silently drops the rest, so the exit code no longer reflects the whole suite.
    To keep the signal trustworthy regardless of language, expand such a template
    into one command per file. Runners that accept many files (pytest, jest, ...)
    still produce the correct aggregate pass/fail when invoked once per file.

    ``{test_dir}`` templates do not list files individually, so they are rendered
    as a single command unchanged.
    """
    if "{test_files}" in template and "{test_dir}" not in template and len(test_files) > 1:
        return [
            render_test_command(template, test_files=[one], test_dir=test_dir)
            for one in test_files
        ]
    return [render_test_command(template, test_files=test_files, test_dir=test_dir)]


def apply_test_manifest_command(
    template: str,
    *,
    step_dir: Path,
    workdir: Path,
    test_files_rel: list[str],
    test_files_override: list[Path] | None = None,
) -> str:
    """Build the final shell command with placeholders resolved for workdir."""
    if "{test_files}" not in template and "{test_dir}" not in template:
        return template
    if test_files_override is not None:
        files_for_cmd = [str(p) for p in test_files_override]
        test_dir = str(test_files_override[0].parent) if test_files_override else "."
    else:
        files_for_cmd, test_dir = resolve_test_command_placeholders(
            step_dir, workdir, test_files_rel,
        )
    return render_test_command(template, test_files=files_for_cmd, test_dir=test_dir)


def apply_test_manifest_commands(
    template: str,
    *,
    step_dir: Path,
    workdir: Path,
    test_files_rel: list[str],
    test_files_override: list[Path] | None = None,
) -> list[str]:
    """Like :func:`apply_test_manifest_command` but returns one command per test
    file when the template lists files individually (see :func:`render_test_commands`)."""
    if "{test_files}" not in template and "{test_dir}" not in template:
        return [template]
    if test_files_override is not None:
        files_for_cmd = [str(p) for p in test_files_override]
        test_dir = str(test_files_override[0].parent) if test_files_override else "."
    else:
        files_for_cmd, test_dir = resolve_test_command_placeholders(
            step_dir, workdir, test_files_rel,
        )
    return render_test_commands(template, test_files=files_for_cmd, test_dir=test_dir)


_STEP_DIR_RE = re.compile(r"^step_(\d+)$")
FINAL_ACCEPTANCE_DIR_NAME = "final"


def parse_milestone_step_dir_name(name: str) -> int | None:
    """Return step number for ``step_<N>`` only; ignore ``step_1_opencode`` etc."""
    match = _STEP_DIR_RE.match(name)
    return int(match.group(1)) if match else None


def is_final_acceptance_dir(path: Path) -> bool:
    """True when *path* is the canonical ``milestones/final`` acceptance directory."""
    return path.is_dir() and path.name == FINAL_ACCEPTANCE_DIR_NAME


def resolve_final_acceptance_dir(milestones_dir: Path) -> Path | None:
    """Return ``milestones/final`` when it exists and has ``test_manifest.json``."""
    candidate = milestones_dir / FINAL_ACCEPTANCE_DIR_NAME
    if not candidate.is_dir():
        return None
    if not (candidate / "test_manifest.json").is_file():
        return None
    return candidate


GT_CODE_DIR_NAME = "gt"


def resolve_gt_code_dir(milestones_dir: Path) -> tuple[int, Path] | None:
    """Return (step_num, code_dir) for the canonical GT implementation.

    The repo-direct (repo-final) pipeline owns its GT at ``milestones/gt/code/`` and that is
    the authoritative final GT, so it takes priority (step_num 0) whenever present — a stale
    ``step_<N>/code`` left over from an earlier step-by-step run must never shadow it.
    Otherwise, fall back to the highest ``step_<N>/code`` (step-by-step pipeline).
    """
    repo_gt = milestones_dir / GT_CODE_DIR_NAME / "code"
    if repo_gt.is_dir():
        return 0, repo_gt
    best_step: int | None = None
    best_code: Path | None = None
    for step_num in list_milestone_step_numbers(milestones_dir):
        code_dir = milestones_dir / f"step_{step_num}" / "code"
        if code_dir.is_dir():
            if best_step is None or step_num > best_step:
                best_step = step_num
                best_code = code_dir
    if best_step is not None and best_code is not None:
        return best_step, best_code
    return None


def list_milestone_step_numbers(milestones_dir: Path) -> list[int]:
    """Sorted step numbers that have a milestone directory under *milestones_dir*."""
    numbers: list[int] = []
    if not milestones_dir.is_dir():
        return numbers
    for path in milestones_dir.iterdir():
        if not path.is_dir():
            continue
        step_num = parse_milestone_step_dir_name(path.name)
        if step_num is not None:
            numbers.append(step_num)
    return sorted(set(numbers))


def resolve_step_dirs(
    milestones_dir: Path,
    up_to_step: int | None = None,
    *,
    require_test_manifest: bool = True,
) -> list[Path]:
    """Return milestone step dirs ``step_<N>`` in order, excluding suffixed noise dirs."""
    entries: list[tuple[int, Path]] = []
    if not milestones_dir.is_dir():
        return []
    for path in milestones_dir.iterdir():
        if not path.is_dir():
            continue
        step_num = parse_milestone_step_dir_name(path.name)
        if step_num is None:
            continue
        if up_to_step is not None and step_num > up_to_step:
            continue
        if require_test_manifest and not (path / "test_manifest.json").is_file():
            continue
        entries.append((step_num, path))
    entries.sort(key=lambda item: item[0])
    return [path for _, path in entries]


def merge_test_usage(step_dirs: list[Path]) -> dict:
    """Merge test_usage.json from multiple milestone steps (deduplicated)."""
    merged: dict = {"schema_version": 1, "modules": [], "names": [], "imports": []}
    seen_modules: set[str] = set()
    seen_names: set[str] = set()
    seen_import_keys: set[str] = set()
    seen_dep_keys: dict[tuple[str, str], int] = {}

    for step_dir in step_dirs:
        usage_path = step_dir / "test_usage.json"
        if not usage_path.is_file():
            continue
        try:
            usage = json.loads(usage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(usage, dict):
            continue
        for module in usage.get("modules", []) or []:
            if isinstance(module, str) and module not in seen_modules:
                seen_modules.add(module)
                merged["modules"].append(module)
        for name in usage.get("names", []) or []:
            if isinstance(name, str) and name not in seen_names:
                seen_names.add(name)
                merged["names"].append(name)
        for imp in usage.get("imports", []) or []:
            if not isinstance(imp, dict):
                continue
            key = json.dumps(imp, sort_keys=True)
            if key not in seen_import_keys:
                seen_import_keys.add(key)
                merged["imports"].append(imp)
        deps = usage.get("interface_dependencies", []) or []
        if isinstance(deps, list) and deps:
            if "interface_dependencies" not in merged:
                merged["interface_dependencies"] = []
            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                dep_key = _interface_dependency_key(dep)
                if dep_key in seen_dep_keys:
                    idx = seen_dep_keys[dep_key]
                    merged["interface_dependencies"][idx] = _merge_interface_dependency_entries(
                        merged["interface_dependencies"][idx], dep,
                    )
                else:
                    seen_dep_keys[dep_key] = len(merged["interface_dependencies"])
                    merged["interface_dependencies"].append(dict(dep))
    return merged


# ---------------------------------------------------------------------------
# D_SELFTEST_PROGRESS.json — Stage D hotfix self-test completion (judge-only)
# ---------------------------------------------------------------------------
#
# When CaseEnv is active (repo-final main path), AgentSandbox is passthrough: container
# paths under case_dir are shared with the host. ``selftest_workdir`` is informational
# (often a container-only path such as /opt/codingbench/repo); the orchestrator does not
# validate its existence on the host. Downstream E/F agents read ``last_run_command`` and
# execute ``run_acceptance.sh`` instead.

D_SELFTEST_PROGRESS_FILENAME = "D_SELFTEST_PROGRESS.json"
D_SELFTEST_PROGRESS_SCHEMA_VERSION = 1

SELFTEST_PROGRESS_REQUIRED = (
    "schema_version",
    "round",
    "total",
    "passed",
    "failed",
    "complete",
    "selftest_workdir",
    "test_manifest_path",
    "cases",
    "last_run_command",
    "last_run_output_tail",
)

SELFTEST_CASE_STATUSES = frozenset({"passed", "failed", "skipped", "error"})


def load_selftest_progress(
    final_dir: Path,
    *,
    expected_round: int | None = None,
    canonical_manifest: Path | None = None,
) -> tuple[dict | None, list[ContractIssue]]:
    """Load and structurally validate ``D_SELFTEST_PROGRESS.json`` under *final_dir*."""
    path = final_dir / D_SELFTEST_PROGRESS_FILENAME
    data, issues = load_json(path)
    if data is None:
        return None, issues
    issues.extend(
        validate_selftest_progress(
            data,
            final_dir=final_dir,
            expected_round=expected_round,
            canonical_manifest=canonical_manifest,
        )
    )
    return data, issues


def validate_selftest_progress(
    data: object,
    *,
    final_dir: Path,
    expected_round: int | None = None,
    canonical_manifest: Path | None = None,
) -> list[ContractIssue]:
    """Structural validation only — no test-framework semantics."""
    issues: list[ContractIssue] = []
    if not isinstance(data, dict):
        return [ContractIssue("error", "invalid-selftest-progress", "progress must be a JSON object")]

    for key in SELFTEST_PROGRESS_REQUIRED:
        if key not in data:
            issues.append(ContractIssue(
                "error", "missing-field", f"D_SELFTEST_PROGRESS.{key} is required",
            ))

    if data.get("schema_version") != D_SELFTEST_PROGRESS_SCHEMA_VERSION:
        issues.append(ContractIssue(
            "error", "schema-version",
            f"D_SELFTEST_PROGRESS.schema_version must be {D_SELFTEST_PROGRESS_SCHEMA_VERSION}",
        ))

    round_val = data.get("round")
    if not isinstance(round_val, int) or round_val < 1:
        issues.append(ContractIssue(
            "error", "invalid-field", "D_SELFTEST_PROGRESS.round must be a positive integer",
        ))
    elif expected_round is not None and round_val != expected_round:
        issues.append(ContractIssue(
            "error", "stale-round",
            f"D_SELFTEST_PROGRESS.round is {round_val}, expected {expected_round}",
        ))

    for count_key in ("total", "passed", "failed"):
        val = data.get(count_key)
        if not isinstance(val, int) or val < 0:
            issues.append(ContractIssue(
                "error", "invalid-field",
                f"D_SELFTEST_PROGRESS.{count_key} must be a non-negative integer",
            ))

    complete = data.get("complete")
    if not isinstance(complete, bool):
        issues.append(ContractIssue(
            "error", "invalid-field", "D_SELFTEST_PROGRESS.complete must be a boolean",
        ))

    workdir_raw = data.get("selftest_workdir")
    if isinstance(workdir_raw, str) and workdir_raw.strip():
        workdir_path = Path(workdir_raw).expanduser()
        if not workdir_path.is_absolute():
            issues.append(ContractIssue(
                "error", "invalid-field",
                "D_SELFTEST_PROGRESS.selftest_workdir must be an absolute path",
            ))
    elif "selftest_workdir" in data:
        issues.append(ContractIssue(
            "error", "invalid-field",
            "D_SELFTEST_PROGRESS.selftest_workdir must be a non-empty absolute path string",
        ))

    manifest_raw = data.get("test_manifest_path")
    if isinstance(manifest_raw, str) and manifest_raw.strip():
        manifest_path = Path(manifest_raw).expanduser()
        if not manifest_path.is_absolute():
            issues.append(ContractIssue(
                "error", "invalid-field",
                "D_SELFTEST_PROGRESS.test_manifest_path must be an absolute path",
            ))
        elif not manifest_path.is_file():
            issues.append(ContractIssue(
                "error", "missing-manifest",
                f"D_SELFTEST_PROGRESS.test_manifest_path not found: {manifest_path}",
            ))
        elif canonical_manifest is not None:
            try:
                if manifest_path.resolve() != canonical_manifest.resolve():
                    issues.append(ContractIssue(
                        "error", "manifest-mismatch",
                        "D_SELFTEST_PROGRESS.test_manifest_path must match the stage manifest",
                    ))
            except OSError:
                issues.append(ContractIssue(
                    "error", "manifest-mismatch",
                    "D_SELFTEST_PROGRESS.test_manifest_path could not be resolved",
                ))
    elif "test_manifest_path" in data:
        issues.append(ContractIssue(
            "error", "invalid-field",
            "D_SELFTEST_PROGRESS.test_manifest_path must be a non-empty absolute path string",
        ))

    last_cmd = data.get("last_run_command")
    if not isinstance(last_cmd, str) or len(last_cmd.strip()) < 8:
        issues.append(ContractIssue(
            "error", "invalid-field",
            "D_SELFTEST_PROGRESS.last_run_command must be a substantive reproducible command",
        ))

    output_tail = data.get("last_run_output_tail")
    if not isinstance(output_tail, str) or len(output_tail.strip()) < 20:
        issues.append(ContractIssue(
            "error", "invalid-field",
            "D_SELFTEST_PROGRESS.last_run_output_tail must contain substantive run output",
        ))

    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) == 0:
        issues.append(ContractIssue(
            "error", "invalid-field", "D_SELFTEST_PROGRESS.cases must be a non-empty list",
        ))
        return issues

    case_ids: set[str] = set()
    status_counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    for idx, entry in enumerate(cases):
        prefix = f"cases[{idx}]"
        if not isinstance(entry, dict):
            issues.append(ContractIssue("error", "invalid-field", f"{prefix} must be an object"))
            continue
        case_id = entry.get("id")
        status = entry.get("status")
        if not isinstance(case_id, str) or not case_id.strip():
            issues.append(ContractIssue(
                "error", "invalid-field", f"{prefix}.id must be a non-empty string",
            ))
        elif case_id in case_ids:
            issues.append(ContractIssue(
                "error", "duplicate-case", f"duplicate case id: {case_id}",
            ))
        else:
            case_ids.add(case_id)
        if status not in SELFTEST_CASE_STATUSES:
            issues.append(ContractIssue(
                "error", "invalid-field",
                f"{prefix}.status must be one of {sorted(SELFTEST_CASE_STATUSES)}",
            ))
        elif isinstance(status, str):
            status_counts[status] = status_counts.get(status, 0) + 1

    total = data.get("total")
    passed = data.get("passed")
    failed = data.get("failed")
    if isinstance(total, int) and isinstance(passed, int) and isinstance(failed, int):
        if len(cases) != total:
            issues.append(ContractIssue(
                "error", "count-mismatch",
                f"D_SELFTEST_PROGRESS.total ({total}) must equal len(cases) ({len(cases)})",
            ))
        if passed + failed != total:
            issues.append(ContractIssue(
                "error", "count-mismatch",
                "D_SELFTEST_PROGRESS.passed + failed must equal total",
            ))
        if status_counts.get("passed", 0) != passed:
            issues.append(ContractIssue(
                "error", "count-mismatch",
                "D_SELFTEST_PROGRESS.passed must match passed cases in cases[]",
            ))
        if status_counts.get("failed", 0) != failed:
            issues.append(ContractIssue(
                "error", "count-mismatch",
                "D_SELFTEST_PROGRESS.failed must match failed cases in cases[]",
            ))
        expected_complete = passed == total and failed == 0
        if isinstance(complete, bool) and complete != expected_complete:
            issues.append(ContractIssue(
                "error", "complete-mismatch",
                "D_SELFTEST_PROGRESS.complete must be true iff all cases passed",
            ))

    return issues


def is_selftest_complete(
    data: dict | None,
    issues: list[ContractIssue],
    *,
    expected_round: int | None = None,
) -> bool:
    """True when structural validation passes and the agent reports 100% green."""
    if data is None:
        return False
    if any(i.severity == "error" for i in issues):
        return False
    if expected_round is not None and data.get("round") != expected_round:
        return False
    if not data.get("complete"):
        return False
    total = data.get("total")
    passed = data.get("passed")
    failed = data.get("failed")
    if not isinstance(total, int) or not isinstance(passed, int) or not isinstance(failed, int):
        return False
    return passed == total and failed == 0 and total > 0


def format_incomplete_selftest_feedback(
    data: dict | None,
    issues: list[ContractIssue],
) -> str:
    """Human-readable feedback for the next D hotfix session when progress is incomplete."""
    lines = [
        "## Self-test progress incomplete",
        "",
    ]
    if data is None:
        lines.append(
            f"Missing `{D_SELFTEST_PROGRESS_FILENAME}`. You must run the full acceptance "
            "suite synchronously in this session, record every case, and write the progress "
            "file before ending."
        )
        if issues:
            lines.append("")
            lines.append("Validation issues:")
            for issue in issues:
                lines.append(f"- {issue.message}")
        return "\n".join(lines)

    passed = data.get("passed", "?")
    total = data.get("total", "?")
    failed = data.get("failed", "?")
    lines.append(f"Current progress: {passed}/{total} passed, {failed} failed.")
    if issues:
        lines.append("")
        lines.append("Structural validation issues (fix the progress file or re-run honestly):")
        for issue in issues:
            lines.append(f"- {issue.message}")

    failed_cases = [
        c.get("id", "?")
        for c in (data.get("cases") or [])
        if isinstance(c, dict) and c.get("status") == "failed"
    ]
    if failed_cases:
        lines.append("")
        lines.append("Failed cases:")
        for case_id in failed_cases[:30]:
            lines.append(f"- {case_id}")
        if len(failed_cases) > 30:
            lines.append(f"- ... and {len(failed_cases) - 30} more")

    lines.extend([
        "",
        f"Write `{D_SELFTEST_PROGRESS_FILENAME}` with `complete: true` only after every case "
        "has genuinely passed in a foreground synchronous run. Do not end your session until "
        "then.",
    ])
    return "\n".join(lines)


def format_orchestrator_acceptance_failure_feedback(
    *,
    exit_code: int,
    command: str,
    output_tail: str,
    workdir: str,
) -> str:
    """Feedback for the next D hotfix when orchestrator acceptance verification is red."""
    lines = [
        "## Orchestrator acceptance verification failed",
        "",
        "The pipeline ran your `run_acceptance.sh` synchronously after your session ended. "
        "It did **not** exit 0 — fix the failures below and re-run honestly.",
        "",
        f"- exit code: {exit_code}",
        f"- workdir: {workdir}",
        f"- command: `{command}`",
        "",
        "### Output tail (from orchestrator run)",
        "",
        "```",
        (output_tail or "(no output captured)")[-4000:],
        "```",
        "",
        f"Write `{D_SELFTEST_PROGRESS_FILENAME}` with `complete: true` only after a genuine "
        "green run. The orchestrator will re-verify when your session ends.",
    ]
    return "\n".join(lines)


def write_orchestrator_selftest_progress(
    final_dir: Path,
    *,
    round_num: int,
    command: str,
    output_tail: str,
    workdir: Path,
    manifest_path: Path,
) -> Path:
    """Persist suite-level progress backed by an orchestrator acceptance run."""
    import json
    from datetime import datetime, timezone

    payload = {
        "schema_version": D_SELFTEST_PROGRESS_SCHEMA_VERSION,
        "round": round_num,
        "total": 1,
        "passed": 1,
        "failed": 0,
        "complete": True,
        "selftest_workdir": str(workdir.resolve()),
        "test_manifest_path": str(manifest_path.resolve()),
        "cases": [{"id": "run_acceptance.sh", "status": "passed"}],
        "last_run_command": command,
        "last_run_output_tail": (output_tail or "")[-4000:],
        "orchestrator_verified": True,
        "orchestrator_verified_at": datetime.now(timezone.utc).isoformat(),
    }
    path = final_dir / D_SELFTEST_PROGRESS_FILENAME
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# run_acceptance.sh + run_acceptance_meta.json — repo-final hard execution entry
# ---------------------------------------------------------------------------

RUN_ACCEPTANCE_SCRIPT_NAME = "run_acceptance.sh"
RUN_ACCEPTANCE_META_FILENAME = "run_acceptance_meta.json"
RUN_ACCEPTANCE_META_SCHEMA_VERSION = 1

RUN_ACCEPTANCE_META_REQUIRED = (
    "schema_version",
    "generated_at",
    "script_path",
    "script_sha256",
    "test_manifest_path",
    "manifest_sha256",
)

F_BENCHMARK_RESULTS_FILENAME = "F_BENCHMARK_RESULTS.json"
F_BENCHMARK_RESULTS_SCHEMA_VERSION = 1

F_BENCHMARK_RESULTS_REQUIRED = (
    "schema_version",
    "complete",
    "f0_overlay_exit_code",
    "f1_overlay_exit_code",
    "benchmark_image_tag",
    "verification_command",
    "removed_paths",
)

F_BENCHMARK_RESULTS_OPTIONAL = (
    "complete_image_tag",
    "complete_image_tar",
)


def _sha256_file(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_run_acceptance_meta(final_dir: Path) -> tuple[dict | None, list[ContractIssue]]:
    """Compute and persist ``run_acceptance_meta.json`` from on-disk artifacts."""
    issues: list[ContractIssue] = []
    script = final_dir / RUN_ACCEPTANCE_SCRIPT_NAME
    manifest = final_dir / "test_manifest.json"
    if not script.is_file():
        issues.append(ContractIssue(
            "error", "missing-script",
            f"{RUN_ACCEPTANCE_SCRIPT_NAME} not found under milestones/final",
        ))
        return None, issues
    if not manifest.is_file():
        issues.append(ContractIssue(
            "error", "missing-manifest",
            "test_manifest.json not found under milestones/final",
        ))
        return None, issues
    from datetime import datetime, timezone
    data = {
        "schema_version": RUN_ACCEPTANCE_META_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script_path": RUN_ACCEPTANCE_SCRIPT_NAME,
        "script_sha256": _sha256_file(script),
        "test_manifest_path": "test_manifest.json",
        "manifest_sha256": _sha256_file(manifest),
    }
    meta_path = final_dir / RUN_ACCEPTANCE_META_FILENAME
    meta_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    issues.extend(validate_run_acceptance_meta(data, final_dir=final_dir))
    return data, issues


def validate_run_acceptance_meta(
    data: object,
    *,
    final_dir: Path,
) -> list[ContractIssue]:
    """Structural validation for ``run_acceptance_meta.json``."""
    issues: list[ContractIssue] = []
    if not isinstance(data, dict):
        return [ContractIssue("error", "invalid-meta", "run_acceptance_meta must be a JSON object")]
    for key in RUN_ACCEPTANCE_META_REQUIRED:
        if key not in data:
            issues.append(ContractIssue(
                "error", "missing-field", f"run_acceptance_meta.{key} is required",
            ))
    if data.get("schema_version") != RUN_ACCEPTANCE_META_SCHEMA_VERSION:
        issues.append(ContractIssue(
            "error", "schema-version",
            f"run_acceptance_meta.schema_version must be {RUN_ACCEPTANCE_META_SCHEMA_VERSION}",
        ))
    script_rel = data.get("script_path")
    if script_rel != RUN_ACCEPTANCE_SCRIPT_NAME:
        issues.append(ContractIssue(
            "error", "invalid-field",
            f"run_acceptance_meta.script_path must be {RUN_ACCEPTANCE_SCRIPT_NAME!r}",
        ))
    script = final_dir / RUN_ACCEPTANCE_SCRIPT_NAME
    if script.is_file() and isinstance(data.get("script_sha256"), str):
        actual = _sha256_file(script)
        if data["script_sha256"] != actual:
            issues.append(ContractIssue(
                "error", "hash-mismatch",
                "run_acceptance_meta.script_sha256 does not match run_acceptance.sh",
            ))
    manifest = final_dir / "test_manifest.json"
    if manifest.is_file() and isinstance(data.get("manifest_sha256"), str):
        actual = _sha256_file(manifest)
        if data["manifest_sha256"] != actual:
            issues.append(ContractIssue(
                "error", "hash-mismatch",
                "run_acceptance_meta.manifest_sha256 does not match test_manifest.json",
            ))
    return issues


def load_run_acceptance_meta(final_dir: Path) -> tuple[dict | None, list[ContractIssue]]:
    path = final_dir / RUN_ACCEPTANCE_META_FILENAME
    data, issues = load_json(path)
    if data is None:
        return None, issues
    issues.extend(validate_run_acceptance_meta(data, final_dir=final_dir))
    return data, issues


def validate_f_benchmark_results(
    data: object,
    *,
    final_dir: Path | None = None,
) -> list[ContractIssue]:
    """Structural validation for ``F_BENCHMARK_RESULTS.json``."""
    issues: list[ContractIssue] = []
    if not isinstance(data, dict):
        return [ContractIssue("error", "invalid-results", "F_BENCHMARK_RESULTS must be a JSON object")]
    for key in F_BENCHMARK_RESULTS_REQUIRED:
        if key not in data:
            issues.append(ContractIssue(
                "error", "missing-field", f"F_BENCHMARK_RESULTS.{key} is required",
            ))
    if data.get("schema_version") != F_BENCHMARK_RESULTS_SCHEMA_VERSION:
        issues.append(ContractIssue(
            "error", "schema-version",
            f"F_BENCHMARK_RESULTS.schema_version must be {F_BENCHMARK_RESULTS_SCHEMA_VERSION}",
        ))
    if data.get("complete") is not True:
        issues.append(ContractIssue(
            "error", "incomplete",
            "F_BENCHMARK_RESULTS.complete must be true",
        ))
    for code_key in ("f0_overlay_exit_code", "f1_overlay_exit_code"):
        val = data.get(code_key)
        if not isinstance(val, int):
            issues.append(ContractIssue(
                "error", "invalid-field",
                f"F_BENCHMARK_RESULTS.{code_key} must be an integer exit code",
            ))
        elif val != 0:
            issues.append(ContractIssue(
                "error", "nonzero-exit",
                f"F_BENCHMARK_RESULTS.{code_key} must be 0 (got {val})",
            ))
    tag = data.get("benchmark_image_tag")
    if not isinstance(tag, str) or not tag.strip():
        issues.append(ContractIssue(
            "error", "invalid-field",
            "F_BENCHMARK_RESULTS.benchmark_image_tag must be a non-empty string",
        ))
    cmd = data.get("verification_command")
    if not isinstance(cmd, str) or len(cmd.strip()) < 8:
        issues.append(ContractIssue(
            "error", "invalid-field",
            "F_BENCHMARK_RESULTS.verification_command must be a substantive command string",
        ))
    removed = data.get("removed_paths")
    if not isinstance(removed, list):
        issues.append(ContractIssue(
            "error", "invalid-field",
            "F_BENCHMARK_RESULTS.removed_paths must be a list",
        ))
    for key in F_BENCHMARK_RESULTS_OPTIONAL:
        val = data.get(key)
        if val is None:
            continue
        if not isinstance(val, str) or not val.strip():
            issues.append(ContractIssue(
                "error", "invalid-field",
                f"F_BENCHMARK_RESULTS.{key} must be a non-empty string when present",
            ))
    return issues


def load_f_benchmark_results(final_dir: Path) -> tuple[dict | None, list[ContractIssue]]:
    path = final_dir / F_BENCHMARK_RESULTS_FILENAME
    data, issues = load_json(path)
    if data is None:
        return None, issues
    issues.extend(validate_f_benchmark_results(data, final_dir=final_dir))
    return data, issues


def f_benchmark_results_complete(data: dict | None, issues: list[ContractIssue]) -> bool:
    if data is None:
        return False
    return not any(i.severity == "error" for i in issues) and bool(data.get("complete"))
