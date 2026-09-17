"""Declarative asset checks for a single case directory.

Callers pass any directory that looks like a case. The released suite is
not imported here so unit tests can use synthetic fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from coding_bench_harbor._leakage import scan_leakage

from .denylist import ALLOWED_JUDGE_BANS, validate_denylist_artifact

__all__ = ["check_case_assets"]

_OUTSIDE_CACHE = "/opt/cb-cache"


def check_case_assets(case_dir: Path | str) -> list[str]:
    """Return human-readable problems for *case_dir* (empty if clean)."""
    case_dir = Path(case_dir)
    errors: list[str] = []
    cid = case_dir.name

    manifest_path = case_dir / "source" / "manifest.json"
    lock_path = case_dir / "source" / "recipe.lock.json"
    prd_path = case_dir / "public" / "Full_PRD.md"
    contract_path = case_dir / "public" / "Interface_Contract.md"
    tests_manifest_path = case_dir / "milestones" / "final" / "test_manifest.json"
    final_dir = case_dir / "milestones" / "final"

    for path in (manifest_path, lock_path, prd_path, contract_path, tests_manifest_path):
        if not path.is_file():
            errors.append(f"{cid}: missing {path.relative_to(case_dir)}")

    manifest: dict = {}
    lock: dict = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{cid}: invalid manifest.json: {exc}")
            return errors
    if lock_path.is_file():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{cid}: invalid recipe.lock.json: {exc}")
            return errors

    runner = manifest.get("runner") if isinstance(manifest.get("runner"), dict) else {}
    lock_runner = lock.get("runner") if isinstance(lock.get("runner"), dict) else {}
    for field in ("install_command", "build_command"):
        left = str(runner.get(field) or "")
        right = str(lock_runner.get(field) or "")
        if left != right:
            errors.append(f"{cid}: manifest and lock disagree on runner.{field}")

    install = str(runner.get("install_command") or "")
    resources = case_dir / "source" / "env" / "resources.json"
    if _OUTSIDE_CACHE in install and not resources.is_file():
        errors.append(
            f"{cid}: install_command references {_OUTSIDE_CACHE} without "
            "source/env/resources.json"
        )

    raw_bans = runner.get("judge_bans") or []
    if isinstance(raw_bans, str):
        raw_bans = [part.strip() for part in raw_bans.split(",")]
    for ban in raw_bans:
        token = str(ban).strip()
        if token and token not in ALLOWED_JUDGE_BANS:
            errors.append(f"{cid}: unknown judge_bans value {token!r}")

    terms = [str(t) for t in (manifest.get("sensitive_terms") or []) if str(t).strip()]
    public_text = ""
    if prd_path.is_file():
        public_text += prd_path.read_text(encoding="utf-8")
    if contract_path.is_file():
        public_text += "\n" + contract_path.read_text(encoding="utf-8")
    public_text += "\n" + str(runner.get("build_command") or "")
    for hit in scan_leakage(public_text, terms):
        errors.append(f"{cid}: public leakage of {hit.term!r} ({hit.occurrences})")

    denylist_path = case_dir / "source" / "denylist.json"
    if denylist_path.is_file():
        try:
            payload = json.loads(denylist_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{cid}: invalid denylist.json: {exc}")
        else:
            if isinstance(payload, dict) and isinstance(manifest, dict):
                errors.extend(validate_denylist_artifact(payload, manifest, case_id=cid))

    if tests_manifest_path.is_file():
        try:
            tests_manifest = json.loads(tests_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{cid}: invalid test_manifest.json: {exc}")
            return errors
        names = list(tests_manifest.get("test_files") or [])
        names.extend(tests_manifest.get("support_files") or [])
        for name in names:
            rel = Path(str(name))
            target = (final_dir / rel).resolve()
            try:
                target.relative_to(final_dir.resolve())
            except ValueError:
                errors.append(f"{cid}: test file escapes milestones/final: {name}")
                continue
            if not target.is_file():
                errors.append(f"{cid}: test_manifest references missing {name}")
    return errors
