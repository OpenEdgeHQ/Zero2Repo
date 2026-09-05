"""Unit tests for cbrun denylist loading, scan, and fix instruction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun.denylist import (  # noqa: E402
    DenylistSpec,
    FORBIDDEN_IMPORT_BAN,
    build_fix_instruction,
    line_imports_token,
    load_denylist,
    normalize_pkg_name,
    scan_installed_warnings,
    scan_workspace_imports,
    validate_denylist_artifact,
    validate_denylist_payload,
)
from cbrun.submit import CONTAINER_SUBMIT_PATH, SUBMIT_TOKEN  # noqa: E402


def test_normalize_pkg_name() -> None:
    assert normalize_pkg_name("SymPy") == "sympy"
    assert normalize_pkg_name("flash_attn[dev]") == "flash-attn"
    assert normalize_pkg_name("barryvdh/laravel-ide-helper") == "barryvdh-laravel-ide-helper"


def test_load_denylist_from_case_dir(tmp_path: Path) -> None:
    case_dir = tmp_path / "case010"
    source = case_dir / "source"
    source.mkdir(parents=True)
    (source / "denylist.json").write_text(
        json.dumps(
            {
                "case_id": "case010",
                "ecosystem": "pip",
                "install_ban": ["sympy"],
                "import_ban": ["sympy"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    spec = load_denylist(case_dir)
    assert spec is not None
    assert spec.case_id == "case010"
    assert "sympy" in spec.install_ban
    assert "sympy" in spec.import_ban


def test_scan_workspace_imports_detects_sympy(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    (workspace / "solver.py").write_text("import sympy\nfrom sympy import Symbol\n", encoding="utf-8")
    spec = DenylistSpec(case_id="x", ecosystem="pip", install_ban=("sympy",), import_ban=("sympy",))
    hits = scan_workspace_imports(workspace, spec)
    assert hits
    assert hits[0].token == "sympy"
    assert hits[0].line == 1


def test_installed_warnings_only_for_banned_packages() -> None:
    spec = DenylistSpec(case_id="x", ecosystem="pip", install_ban=("sympy",), import_ban=("sympy",))
    warnings = scan_installed_warnings(["mpmath", "sympy", "pytest"], spec)
    assert len(warnings) == 1
    assert warnings[0].package == "sympy"


def test_build_fix_instruction_lists_hits() -> None:
    from cbrun.denylist import ImportHit

    hits = [
        ImportHit(token="sympy", path="/app/x.py", line=3, line_text="import sympy"),
    ]
    out = build_fix_instruction("BASE", hits)
    assert "BASE" in out
    assert "sympy" in out
    assert "fix required" in out.lower()
    assert CONTAINER_SUBMIT_PATH in out
    assert SUBMIT_TOKEN in out
    assert "end your session again" not in out.lower()


def test_install_ban_hashes_normalized() -> None:
    from cbrun.denylist import install_ban_hashes, normalize_pkg_name
    import hashlib

    hashes = install_ban_hashes(("flash_attn", "flash-attn"))
    assert len(hashes) == 1
    expected = hashlib.sha256(normalize_pkg_name("flash_attn").encode()).hexdigest()
    assert hashes[0] == expected


def test_write_shim_assets_uses_hashes_not_plaintext(tmp_path: Path) -> None:
    from cbrun.denylist import CONTAINER_DENYLIST_HASHES_PATH, write_shim_assets

    case_dir = tmp_path / "case"
    source = case_dir / "source"
    source.mkdir(parents=True)
    denylist = source / "denylist.json"
    denylist.write_text(
        '{"install_ban": ["sympy"], "import_ban": ["sympy"]}',
        encoding="utf-8",
    )
    build_ctx = tmp_path / "ctx"
    snippet = write_shim_assets(build_ctx, denylist)
    assert CONTAINER_DENYLIST_HASHES_PATH in snippet
    assert "denylist.json" not in snippet
    assert (build_ctx / "denylist.hashes").is_file()
    assert "sympy" not in (build_ctx / "denylist.hashes").read_text(encoding="utf-8")
    pip_shim = (build_ctx / "shims" / "pip").read_text(encoding="utf-8")
    assert "denylist.hashes" in pip_shim
    assert "denylist.json" not in pip_shim


def test_validate_denylist_payload_rejects_cuda_namespace() -> None:
    errors = validate_denylist_payload(
        {"case_id": "case027", "import_ban": ["cuda::", "cub::"], "install_ban": ["cub"]},
    )
    assert any("cuda::" in err for err in errors)


def test_all_case_denylists_satisfy_policy() -> None:
    cases_root = BENCHMARK_ROOT / "cases"
    violations: list[str] = []
    for path in sorted(cases_root.glob("case*/source/denylist.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        violations.extend(validate_denylist_payload(payload))
        for token in payload.get("import_ban") or []:
            if token in FORBIDDEN_IMPORT_BAN:
                violations.append(f"{path}: forbidden import_ban token {token!r}")
    assert not violations, "\n".join(violations)


def test_scan_workspace_imports_ignores_docstring_and_string_prose(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    (workspace / "core.py").write_text(
        '"""instructs click to ignore unknown options."""\n'
        'MSG = "the first argument is a click command object"\n'
        "x = 1  # mentions click in a comment\n",
        encoding="utf-8",
    )
    spec = DenylistSpec(case_id="x", ecosystem="pip", install_ban=("click",), import_ban=("click",))
    assert scan_workspace_imports(workspace, spec) == []


def test_scan_workspace_imports_detects_real_click_import(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    (workspace / "core.py").write_text(
        '"""instructs click to ignore unknown options."""\n'
        "import click\n"
        "from click import Option\n",
        encoding="utf-8",
    )
    spec = DenylistSpec(case_id="x", ecosystem="pip", install_ban=("click",), import_ban=("click",))
    hits = scan_workspace_imports(workspace, spec)
    assert {hit.line for hit in hits} == {2, 3}
    assert all(hit.token == "click" for hit in hits)


def test_line_imports_token_python_and_js_forms() -> None:
    assert line_imports_token("import click", "click", ".py")
    assert line_imports_token("from click.core import Group", "click", ".py")
    assert line_imports_token("import pkg.click", "click", ".py")
    assert not line_imports_token('"""instructs click to ignore"""', "click", ".py")
    assert not line_imports_token('name = "click"', "click", ".py")
    assert line_imports_token("import x from 'click'", "click", ".ts")
    assert line_imports_token("const c = require('click')", "click", ".js")
    assert not line_imports_token("const msg = 'click helper'", "click", ".js")


def test_scan_workspace_imports_skips_cpp_line_comments(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir()
    (workspace / "vec.h").write_text(
        "// `thrust::device_reference` ergonomics\nauto x = cuda::make_counting_iterator(0);\n",
        encoding="utf-8",
    )
    spec = DenylistSpec(
        case_id="case027",
        ecosystem="cuda",
        install_ban=("cub",),
        import_ban=("thrust::", "cub::"),
    )
    hits = scan_workspace_imports(workspace, spec)
    assert hits == []


def test_load_denylist_case001_allows_cuda_namespace() -> None:
    case_dir = BENCHMARK_ROOT / "cases" / "case001"
    if not (case_dir / "source" / "denylist.json").is_file():
        pytest.skip("denylist.json is not part of the public case bundle")
    spec = load_denylist(case_dir)
    assert spec is not None
    assert "cuda::" not in spec.import_ban
    assert "cub::" in spec.import_ban


def test_validate_denylist_artifact_rejects_cuda_namespace() -> None:
    manifest = {"case_id": "case027", "sensitive_terms": ["cub", "thrust", "cccl"]}
    errors = validate_denylist_artifact(
        {
            "schema_version": 1,
            "case_id": "case027",
            "ecosystem": "cuda",
            "install_ban": ["cub"],
            "import_ban": ["cuda::", "cub::"],
            "notes": "bad",
        },
        manifest,
        case_id="case027",
    )
    assert any("cuda::" in err for err in errors)


def test_validate_denylist_artifact_requires_ban_token() -> None:
    manifest = {"case_id": "case027", "sensitive_terms": ["cub"]}
    errors = validate_denylist_artifact(
        {
            "schema_version": 1,
            "case_id": "case027",
            "ecosystem": "cuda",
            "install_ban": [],
            "import_ban": [],
            "notes": "empty",
        },
        manifest,
        case_id="case027",
    )
    assert any("at least one" in err for err in errors)


def test_validate_denylist_artifact_accepts_empty_import_ban_for_source_case() -> None:
    manifest = {
        "case_id": "case030",
        "sensitive_terms": ["reinforcement-learning-an-introduction"],
    }
    errors = validate_denylist_artifact(
        {
            "schema_version": 1,
            "case_id": "case030",
            "ecosystem": "source",
            "install_ban": ["reinforcement-learning-an-introduction"],
            "import_ban": [],
            "notes": "source-only",
        },
        manifest,
        case_id="case030",
    )
    assert errors == []


def test_validate_denylist_artifact_accepts_case001_shape() -> None:
    denylist_path = BENCHMARK_ROOT / "cases" / "case001" / "source" / "denylist.json"
    if not denylist_path.is_file():
        pytest.skip("denylist.json is not part of the public case bundle")
    manifest = json.loads(
        (BENCHMARK_ROOT / "cases" / "case001" / "source" / "manifest.json").read_text(
            encoding="utf-8",
        ),
    )
    payload = json.loads(denylist_path.read_text(encoding="utf-8"))
    assert validate_denylist_artifact(payload, manifest, case_id="case001") == []
