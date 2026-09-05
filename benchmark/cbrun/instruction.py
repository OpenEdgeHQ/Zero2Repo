"""Agent instruction assembly for cbrun.

The prompt tells the agent exactly what it has (inputs + environment), what its
goal is, and how it will be scored, without leaking anything about the hidden
acceptance tests. It reuses the Harbor adapter's ``_INSTRUCTION_PREAMBLE`` so
the from-scratch task framing stays identical across the two runners, then adds
cbrun-specific notes about the container environment, free development with only
a wall-clock limit, and the visible-vs-hidden test boundary.
"""

from __future__ import annotations

from coding_bench_harbor.adapter import _INSTRUCTION_PREAMBLE

from .submit import CONTAINER_SUBMIT_PATH, SUBMIT_TOKEN

__all__ = ["build_instruction", "ENVIRONMENT_NOTES"]

# Where the deliverable image exposes the public spec and the agent workspace.
PRD_CONTAINER_PATH = "/environment/prd/Full_PRD.md"
CONTRACT_CONTAINER_PATH = "/environment/Interface_Contract.md"
HARDWARE_CONTAINER_PATH = "/environment/Hardware_Requirements.md"
WORKSPACE_CONTAINER_PATH = "/app"


def _environment_notes(*, has_hardware: bool) -> str:
    hardware_line = ""
    if has_hardware:
        hardware_line = (
            f"* Hardware requirements are at `{HARDWARE_CONTAINER_PATH}` "
            "(also appended below when provided).\n"
        )
    return f"""\
## Your environment

* Your workspace is `{WORKSPACE_CONTAINER_PATH}` (your current working directory).
  Build the project here so it is importable / installable from this directory
  root (for example `pip install -e .`, or importable from the root).
* The full specification is also available as files inside the container:
  the PRD at `{PRD_CONTAINER_PATH}` and the Interface Contract at
  `{CONTRACT_CONTAINER_PATH}` (identical to the text below).
{hardware_line}* Language runtimes and dependencies the project needs are already installed in
  this image. You have network access for your own model/tool calls.

## How you work

* You may develop freely: there is no limit on the number of steps, turns, edits
  or commands. The only limit is a wall-clock time budget for the whole session.
* **Implement from scratch.** Build the target system described in the PRD and
  Interface Contract yourself. Do not download, clone, vendor, copy, or install
  an existing upstream implementation of that target system (for example via
  `pip install`, `npm install`, or `cargo add` for the product you are building).
  General-purpose libraries and tools are allowed; the described product behavior
  must be your own code.
* GitHub and other code-hosting sites for upstream projects are **not reachable**
  from this environment during your session.
* You are encouraged to write and run your OWN tests and checks repeatedly to
  validate your implementation against the PRD and Interface Contract, then fix
  and iterate. A real develop -> test -> debug loop is expected, not a single
  pass.
* When you are confident the implementation is complete, write the submit file
  described below, then you may end your session. Ending the session is **not**
  a submission.
* Submit by writing exactly this one-line file (no extra words):
  path `{CONTAINER_SUBMIT_PATH}`
  contents `{SUBMIT_TOKEN}`
* If that file is missing or its contents are wrong, this attempt fails and the
  hidden acceptance tests will not run.

## How you are scored

* After a valid submit file is present, a hidden acceptance test suite is run
  against your final workspace state and produces a binary pass/fail reward.
* The hidden tests are NOT present in this container and you cannot access them.
  Do not look for them, and do not special-case any test: implement the public
  Interface Contract behavior fully and correctly.
"""


# Backward-compatible alias for tests importing ENVIRONMENT_NOTES.
ENVIRONMENT_NOTES = _environment_notes(has_hardware=False)


def build_instruction(
    prd_text: str,
    contract_text: str,
    *,
    hardware_text: str | None = None,
) -> str:
    """Assemble the full agent prompt from the public spec.

    Order: shared from-scratch preamble, cbrun environment/scoring notes, then
    the verbatim PRD and Interface Contract. No hidden-test content is included.
    Optional hardware requirements are appended when provided.
    """
    hw = (hardware_text or "").strip()
    parts: list[str] = [_INSTRUCTION_PREAMBLE.rstrip(), "\n\n"]
    parts.append(_environment_notes(has_hardware=bool(hw)).rstrip())
    parts.append("\n\n---\n\n")
    parts.append("# Product Requirements Document\n\n")
    parts.append(prd_text.strip())
    parts.append("\n\n---\n\n")
    parts.append("# Interface Contract\n\n")
    parts.append(contract_text.strip())
    if hw:
        parts.append("\n\n---\n\n")
        parts.append("# Hardware Requirements\n\n")
        parts.append(hw)
    parts.append("\n")
    return "".join(parts)
