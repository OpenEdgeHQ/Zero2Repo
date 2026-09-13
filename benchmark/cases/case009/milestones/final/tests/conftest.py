# feature: F00
"""Pytest fixtures and import-path setup for the shared suite harness.

Reusable invocation / isolation machinery lives in ``_harness``; this
module only wires pytest to that machinery and ensures
``from _harness import ...`` resolves when tests are collected from the
repository root.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from _harness import product_bin, repo_root, workspace  # noqa: E402


@pytest.fixture
def workspace_root() -> Path:
    """Absolute path of the built repository root (pytest process cwd)."""
    return repo_root()


@pytest.fixture
def product_binary(workspace_root: Path) -> Path:
    """Absolute path of the recipe-built product binary.

    Raises ``FileNotFoundError`` at fixture setup if the binary is missing
    — that is a build/substrate gap, not a product-behavior judgment.
    """
    return product_bin(root=workspace_root)


@pytest.fixture
def isolated_ws():
    """Yield an ephemeral work directory with isolated HOME; tear down after."""
    with workspace() as ws:
        yield ws


@pytest.fixture(autouse=True)
def _restore_cwd():
    """Restore the process cwd after each test, even if a helper left it changed."""
    previous = os.getcwd()
    try:
        yield
    finally:
        os.chdir(previous)
