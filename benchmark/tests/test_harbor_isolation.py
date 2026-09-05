"""Harbor task.toml isolation settings (no case tree required)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))
sys.path.insert(0, str(BENCHMARK_ROOT.parent / "tools"))

from coding_bench_harbor.adapter import _build_task_toml  # noqa: E402


def test_task_toml_uses_separate_environment_and_app_artifact() -> None:
    case = SimpleNamespace(
        case_id="demo-001",
        language="python",
        acceptance=SimpleNamespace(gt_step=1),
        runner=SimpleNamespace(
            install_command="pip install -e .",
            build_command="",
            test_command="python3 -m pytest",
            workdir=".",
        ),
    )
    doc = _build_task_toml(
        case,
        difficulty="medium",
        agent_timeout_sec=7200.0,
        verifier_timeout_sec=600.0,
        build_timeout_sec=600.0,
        cpus=2,
        memory_mb=4096,
        storage_mb=10240,
    )
    assert doc["environment_mode"] == "separate"
    assert doc["artifacts"] == ["/app"]
