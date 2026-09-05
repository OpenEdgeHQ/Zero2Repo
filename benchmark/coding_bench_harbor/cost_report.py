"""Harbor trial/job cost enrichment via CalLLMCost.

Examples
--------
Enrich one trial after a Harbor run:

    zero2repo-cost trial --trial-dir jobs/opencode-v1/my-case__abc123

Enrich every trial under a job:

    zero2repo-cost job --job-dir jobs/opencode-v1
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from cost_utils import (  # noqa: E402
    backfill_case_run_costs,
    enrich_job_result_jsons,
    enrich_trial_result_json,
    main as cost_utils_main,
)


def main(argv: list[str] | None = None) -> int:
    """Delegate to ``tools/cost_utils.py`` CLI (trial/job/case subcommands)."""
    return cost_utils_main(argv)


__all__ = [
    "backfill_case_run_costs",
    "enrich_job_result_jsons",
    "enrich_trial_result_json",
    "main",
]
