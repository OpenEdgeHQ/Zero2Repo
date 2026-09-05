"""cbrun: a Harbor-independent solver benchmark runner for zero2repo.

The runner gives an autonomous coding agent only the public task spec
(PRD + Interface Contract) inside a per-case GT-free container, lets it develop
freely (no turn/step cap, only a wall-clock limit), then injects the hidden
acceptance tests and scores the final workspace state with a binary reward.

Design invariants (see ``benchmark/cbrun/README.md``):

* Solver-only: the agent writes the implementation in ``/app``; the hidden test
  code is a benchmark asset, never an agent output.
* Fairness: the solve container physically does not contain ``/tests/final``;
  the hidden tests are re-injected only for the judge phase.
* Free development, time-limited: no step/turn/cost cap, only a wall-clock
  ``max_agent_timeout_sec`` (final-stage default 2h) and a separate judge
  ``max_test_timeout_sec``.
* Submission is an explicit file (``/logs/agent/submit``). CLI exit is not a
  submit. The isolated judge runs only after a valid submit and a clean
  denylist scan.
"""

from __future__ import annotations

__version__ = "0.1.0"
