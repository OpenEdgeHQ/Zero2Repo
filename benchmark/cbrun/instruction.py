"""Agent instruction assembly for cbrun.

The prompt tells the agent exactly what it has (inputs + environment), what its
goal is, and how it will be scored, without leaking anything about the hidden
acceptance tests. Specification bodies (PRD, Interface Contract, optional
hardware) stay on disk at fixed container paths; the prompt only names those
paths so it stays well under the Linux per-argument size limit.
"""

from __future__ import annotations

from coding_bench_harbor.adapter import build_contract_notes

from .submit import CONTAINER_SUBMIT_PATH, SUBMIT_TOKEN

__all__ = ["build_instruction", "ENVIRONMENT_NOTES"]

# Where the deliverable image exposes the public spec and the agent workspace.
PRD_CONTAINER_PATH = "/environment/prd/Full_PRD.md"
CONTRACT_CONTAINER_PATH = "/environment/Interface_Contract.md"
HARDWARE_CONTAINER_PATH = "/environment/Hardware_Requirements.md"
WORKSPACE_CONTAINER_PATH = "/app"

_INSTRUCTION_PREAMBLE = """\
# Development Task

You are an autonomous software engineer. Build the complete project described
in the specification files listed below, from scratch, in your current working
directory. Implement every step of the development plan so that the finished
project fully satisfies the specification.

Read those files in full before you start writing code.

When you are done, the workspace must be in a state the hidden tests can use
directly. See the Build contract below for whether a build step is required
and where outputs must remain.

---

"""


def _environment_notes(*, has_hardware: bool) -> str:
    hardware_line = ""
    if has_hardware:
        hardware_line = (
            f"* Hardware requirements are at `{HARDWARE_CONTAINER_PATH}`.\n"
        )
    return f"""\
## Your environment

* Your workspace is `{WORKSPACE_CONTAINER_PATH}` (your current working directory).
  Build the project here. See the Build contract below for how the judge
  locates outputs.
* The full specification is in these files. Read them in full before you start:
  the PRD at `{PRD_CONTAINER_PATH}` and the Interface Contract at
  `{CONTRACT_CONTAINER_PATH}`.
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
    *,
    has_hardware: bool = False,
    build_command: str = "",
    workdir: str = ".",
) -> str:
    """Assemble the agent prompt: preamble, environment notes, build contract.

    Specification bodies are not inlined. The agent must read the files at
    ``PRD_CONTAINER_PATH``, ``CONTRACT_CONTAINER_PATH``, and (when present)
    ``HARDWARE_CONTAINER_PATH``. No hidden-test content is included.
    """
    parts: list[str] = [_INSTRUCTION_PREAMBLE.rstrip(), "\n\n"]
    parts.append(_environment_notes(has_hardware=has_hardware).rstrip())
    parts.append("\n\n")
    parts.append(build_contract_notes(build_command, workdir).rstrip())
    parts.append("\n")
    return "".join(parts)
