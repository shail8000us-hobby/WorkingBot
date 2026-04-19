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


class TestJestSealedPositionRowActions:
    """
    @sealed — PositionRow actions column (entry #65)
    Runs: webui/frontend/src/components/options/__tests__/test_sealed_position_row_actions.test.js
    """

    def test_all_position_row_actions_contracts_pass(self):
        """
        CONTRACT: PositionRow actions column (scale/roll/close/remove) must pass all Jest contract tests.
        This test FAILS if any Jest test fails or if Jest cannot run.
        """
        result = _run_jest("test_sealed_position_row_actions")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed PositionRow actions tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_position_row_actions"
        )


class TestJestSealedSLTPDialog:
    """
    @sealed — SLTPDialog.handleSave + handleRemove (entry #66)
    Runs: webui/frontend/src/components/options/__tests__/test_sealed_sltp_dialog.test.js
    """

    def test_all_sltp_dialog_contracts_pass(self):
        """
        CONTRACT: SLTPDialog handleSave and handleRemove must pass all Jest contract tests.
        This test FAILS if any Jest test fails or if Jest cannot run.
        """
        result = _run_jest("test_sealed_sltp_dialog")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed SLTPDialog tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_sltp_dialog"
        )


class TestJestSealedTakeProfitDialog:
    """
    @sealed — TakeProfitDialog.handleSave + handleRemove (entry #67)
    Runs: webui/frontend/src/components/options/__tests__/test_sealed_take_profit_dialog.test.js
    """

    def test_all_take_profit_dialog_contracts_pass(self):
        """
        CONTRACT: TakeProfitDialog handleSave and handleRemove must pass all Jest contract tests.
        This test FAILS if any Jest test fails or if Jest cannot run.
        """
        result = _run_jest("test_sealed_take_profit_dialog")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed TakeProfitDialog tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_take_profit_dialog"
        )


class TestJestSealedMMMMarginPanel:
    """
    @sealed — MMMMarginGuardianPanel sub-components (entry #75)
    Runs: webui/frontend/src/components/mmm/__tests__/test_sealed_mmm_margin_panel.test.js
    """

    def test_all_mmm_margin_panel_contracts_pass(self):
        """
        CONTRACT: Exchange Margin panel colors, tier labels, wallet rows, and
        TierLadder action descriptions must pass all Jest contract tests.
        """
        result = _run_jest("test_sealed_mmm_margin_panel")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed MMMMarginPanel tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_mmm_margin_panel"
        )


class TestJestSealedMMMSessionCard:
    """
    @sealed — SessionCard (MMM Dashboard) (entry #74)
    Runs: webui/frontend/src/components/mmm/__tests__/test_sealed_mmm_session_card.test.js
    """

    def test_all_mmm_session_card_contracts_pass(self):
        """
        CONTRACT: SessionCard action buttons and data display must pass all Jest contract tests.
        This test FAILS if any Jest test fails or if Jest cannot run.
        """
        result = _run_jest("test_sealed_mmm_session_card")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed MMMSessionCard tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_mmm_session_card"
        )


class TestJestSealedKillSwitchAndHardStop:
    """
    @sealed — Kill Switch + Hard Stop UI contracts (entry #77)
    Runs: webui/frontend/src/components/mmm/__tests__/test_sealed_kill_switch_and_hard_stop.test.js

    Contracts:
      KS1–KS8: Kill Switch button visibility and dialog flow on SessionCard
      HS1–HS6, HS2b, HS2c, HS3b, HS4b: Hard Stop display, threshold, color
    """

    def test_all_kill_switch_and_hard_stop_contracts_pass(self):
        """
        CONTRACT: Kill Switch button (KS1-KS8) and Hard Stop display (HS1-HS6)
        on SessionCard must pass all Jest contract tests.
        FAILURE = life-safety UI contract broken. Do NOT ignore.
        """
        result = _run_jest("test_sealed_kill_switch_and_hard_stop")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed Kill Switch + Hard Stop tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_kill_switch_and_hard_stop"
        )
