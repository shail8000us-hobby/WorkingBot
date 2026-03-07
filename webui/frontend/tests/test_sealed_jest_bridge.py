"""
Pytest wrapper for sealed Jest tests (JavaScript/React frontend)

SEALED — v1.0.0 — March 5, 2026
Do not modify without UNSEAL command in AI_SEAL.md

This file bridges the gap between `python3 -m pytest webui/ bot/ -m sealed -v`
and the Jest sealed tests that live in the React frontend.

It runs TWO Jest sealed test suites as a single pytest test so
the unified pytest command covers ALL sealed contracts — Python AND JavaScript.

Functions covered (by proxy):
  • Entries #44  — getOpenPositions     (chainAPI.js)
  • Entries #45–56 — payoffCalculator.js (all 12 math functions)

RUN (included automatically in):
    python3 -m pytest webui/ bot/ -m sealed -v
"""

import subprocess
import sys
import os
import pytest

pytestmark = pytest.mark.sealed

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..')


def _run_jest(pattern: str) -> subprocess.CompletedProcess:
    """Run react-app-rewired test for a given pattern. Returns CompletedProcess."""
    return subprocess.run(
        [
            "npx", "react-app-rewired", "test",
            "--watchAll=false",
            f"--testPathPattern={pattern}",
            "--verbose",
        ],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
    )


class TestJestSealedPayoffCalculator:
    """
    @sealed — payoffCalculator.js (entries #45–56)
    Runs: webui/frontend/src/components/options/__tests__/test_sealed_payoffCalculator.test.js
    """

    def test_all_payoff_calculator_contracts_pass(self):
        """
        CONTRACT: All 12 sealed payoffCalculator functions must pass their Jest tests.
        This test FAILS if any Jest test fails or if Jest cannot run.
        """
        result = _run_jest("test_sealed_payoffCalculator")
        output = result.stdout + result.stderr

        # Jest exit code 0 = all tests passed
        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed payoffCalculator tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_payoffCalculator"
        )


class TestJestSealedGetOpenPositions:
    """
    @sealed — getOpenPositions (entry #44)
    Runs: webui/frontend/src/components/optionsChain/services/__tests__/test_sealed_getOpenPositions.test.js
    """

    def test_all_get_open_positions_contracts_pass(self):
        """
        CONTRACT: getOpenPositions must pass all Jest contract tests.
        This test FAILS if any Jest test fails or if Jest cannot run.
        """
        result = _run_jest("test_sealed_getOpenPositions")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed getOpenPositions tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_getOpenPositions"
        )
