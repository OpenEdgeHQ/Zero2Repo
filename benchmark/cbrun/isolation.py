"""Hidden-test isolation and task.toml synthesis for cbrun.

Fairness model:

* The solve container is built from a per-case ``:agent`` image whose layers do
  not contain ``/tests/final`` (see :mod:`cbrun.images`); the hidden tests live
  only in a host-side cache.
* For the judge phase the runner copies only ``/app`` into a fresh ``:agent``
  container, re-injects the cached hidden tests plus a synthesized
  ``/task.toml``, then runs ``final_judge.py``.

This module owns the task.toml synthesis (and the install/build/workdir merge
precedence) so the rule lives in one place. The hidden ``test_command`` is taken
by ``final_judge`` from the injected ``/tests/final/test_manifest.json``; the
synthesized ``runner`` block supplies install/build/workdir.
"""

from __future__ import annotations

import tomli_w

from .assets import CaseSpec
from .steps import Step

__all__ = ["merge_runner", "synthesize_task_toml"]


def _nonempty(value: object) -> str:
    text = str(value or "").strip()
    return text


def merge_runner(case: CaseSpec, step: Step) -> dict[str, str]:
    """Merge runner fields with documented precedence.

    Base is the case ``source/manifest.json`` runner; the step/final
    ``test_manifest`` inline ``install_command`` / ``build_command`` /
    ``workdir`` / ``test_command`` override it when present and non-empty. This
    resolves the real divergence where e.g. srush carries ``install_command`` in
    its test_manifest while cccl carries it in the source runner.
    """
    tm = step.test_manifest or {}
    install = _nonempty(tm.get("install_command")) or _nonempty(case.install_command)
    build = _nonempty(tm.get("build_command")) or _nonempty(case.build_command)
    workdir = _nonempty(tm.get("workdir")) or _nonempty(case.workdir) or "."
    test_command = _nonempty(tm.get("test_command")) or _nonempty(case.test_command)
    return {
        "install_command": install,
        "build_command": build,
        "test_command": test_command,
        "workdir": workdir,
    }


def synthesize_task_toml(case: CaseSpec, step: Step) -> bytes:
    """Render the ``/task.toml`` bytes consumed by ``final_judge.py``.

    Only ``metadata.runner`` is load-bearing for the judge (install/build/
    workdir); the rest is descriptive metadata kept consistent with the Harbor
    task.toml shape.
    """
    runner = merge_runner(case, step)
    doc = {
        "schema_version": "1.1",
        "metadata": {
            "case_id": case.case_id,
            "language": case.language,
            "judge_mode": "final_tests",
            "final_step": step.index,
            "acceptance_stage": "final" if step.is_final else f"step_{step.index}",
            "benchmark_mode": "cbrun_solver",
            "runner": runner,
        },
    }
    return tomli_w.dumps(doc).encode("utf-8")
