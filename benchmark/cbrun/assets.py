"""Case asset discovery for cbrun.

Thin wrapper around the Harbor adapter's case loader so cbrun reuses one source
of truth for parsing ``source/manifest.json`` runner metadata, the PRD, the
Interface Contract and the final acceptance milestone. Unlike the adapter's
released-suite gate, cbrun loads any case (the GPU cases are not in the released
CPU suite), so it always passes ``require_released=False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from coding_bench_harbor.adapter import (
    AdapterError,
    CaseAssets,
    _full_prd_text,
    discover_case,
)

__all__ = ["AdapterError", "CaseAssets", "CaseSpec", "load_case"]


@dataclass(frozen=True)
class CaseSpec:
    """Resolved public spec + runner metadata for a single case."""

    case_id: str
    language: str
    prd_text: str
    contract_text: str
    sensitive_terms: list[str]
    # Runner contract from source/manifest.json (post-normalization).
    install_command: str
    build_command: str
    test_command: str
    workdir: str
    docker_image: str
    docker_gpus: str
    hardware_text: str | None
    # Raw assets for downstream phases.
    assets: CaseAssets


def _runner_raw(assets: CaseAssets) -> dict:
    """Re-read the raw runner block to recover optional docker_* fields.

    ``CaseAssets.runner`` only keeps the language/install/build/test/workdir
    subset, but cbrun also needs ``docker_image`` and ``docker_gpus`` to decide
    GPU passthrough and the agent-image base. Read them from the manifest.
    """
    import json

    from coding_bench_harbor.adapter import normalize_runner

    manifest_path = Path(assets.acceptance.acceptance_dir).parents[1] / "source" / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return normalize_runner(manifest.get("runner", {}) or {})


def load_case(case_dir: Path | str) -> CaseSpec:
    """Discover and validate a case directory into a :class:`CaseSpec`."""
    case_dir = Path(case_dir)
    assets = discover_case(case_dir, require_released=False, require_gt=False)
    contract_text = assets.contract_path.read_text(encoding="utf-8")
    prd_text = _full_prd_text(assets)

    runner_raw = _runner_raw(assets)
    docker_image = str(runner_raw.get("docker_image", "") or "").strip()
    docker_gpus = str(runner_raw.get("docker_gpus", "") or "").strip()

    hw_path = case_dir / "public" / "Hardware_Requirements.md"
    hardware_text = None
    if hw_path.is_file():
        text = hw_path.read_text(encoding="utf-8").strip()
        hardware_text = text or None

    return CaseSpec(
        case_id=assets.case_id,
        language=assets.language,
        prd_text=prd_text,
        contract_text=contract_text,
        sensitive_terms=list(assets.sensitive_terms),
        install_command=assets.runner.install_command,
        build_command=assets.runner.build_command,
        test_command=assets.runner.test_command,
        workdir=assets.runner.workdir or ".",
        docker_image=docker_image,
        docker_gpus=docker_gpus,
        hardware_text=hardware_text,
        assets=assets,
    )
