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


class TestJestSealedWsBidAskUpdater:
    """
    @sealed — applyTickerUpdate / wsTickerUpdater.js (entry #74)
    Runs: webui/frontend/src/hooks/__tests__/test_sealed_ws_bidask_updater.test.js

    Contracts BU1–BU12: bid/ask update, mid fallbacks, PnL calc, short sign inversion,
    BTC/ETH multiplier, string parsing, timestamp stamp, field preservation.
    """

    def test_all_ws_bidask_updater_contracts_pass(self):
        """
        CONTRACT: applyTickerUpdate must pass all 12 Jest contract tests.
        FAILURE = live bid/ask + PnL recalculation is broken. Do NOT ignore.
        """
        result = _run_jest("test_sealed_ws_bidask_updater")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed applyTickerUpdate tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_ws_bidask_updater"
        )


class TestJestSealedProfitRatchetKPI:
    """
    @sealed — StrategyKPIBar Profit Ratchet KPI (entry #85)
    Runs: webui/frontend/src/components/mmm/__tests__/test_sealed_profit_ratchet_kpi.test.js

    Contracts PR1–PR13:
      PR1–PR4: KPI card present for 0DTE, 5DTE, STRADDLE_WITH_ADJUSTMENT, SHORT_WINDOW
      PR5–PR9: display value (OFF / Next $N / #N · Next $M / step default)
      PR10–PR12: color (#757575 disabled, #ffa726 armed, #66bb6a fired)
      PR13: null guard — no crash when session=null
    """

    def test_all_profit_ratchet_kpi_contracts_pass(self):
        """
        CONTRACT: StrategyKPIBar must render Profit Ratchet KPI for all strategies
        with correct value and color logic. 13 contracts.
        FAILURE = Profit Ratchet visibility regression. Do NOT ignore.
        """
        result = _run_jest("test_sealed_profit_ratchet_kpi")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed Profit Ratchet KPI tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_profit_ratchet_kpi"
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


class TestJestSealedReducePosition:
    """
    @sealed — handleReduceSelected + confirmReduceSelected (entry #86)
    Runs: webui/frontend/src/components/options/__tests__/test_sealed_reduce_position.test.js

    Contracts RD1–RD17:
      RD1–RD2:  pct guard (0 and 100 rejected)
      RD3–RD5:  lotsToClose = Math.max(1, Math.ceil(size * pct / 100)) — ceil not round
      RD6–RD7:  direction: size<0 → BUY, size>0 → SELL
      RD8:      remaining = currentSize - lotsToClose (non-negative)
      RD9:      is_closed positions excluded
      RD10–RD11: limit_price = mid(bid,ask); undefined when both zero
      RD12:     API confirm=true
      RD13:     API order_preference='maker_first' (never 'market_only')
      RD14–RD16: selectedStrikes/{dialog/percent cleared BEFORE first await
      RD17:     double-fire guard — inFlightRef blocks second concurrent call
    """

    def test_all_reduce_position_contracts_pass(self):
        """
        CONTRACT: handleReduceSelected + confirmReduceSelected must satisfy all 20
        RD contracts. FAILURE = reduce-by-% feature is broken or unsafe (real money).
        """
        result = _run_jest("test_sealed_reduce_position")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed ReducePosition tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_reduce_position"
        )


class TestJestSealedIncreasePosition:
    """
    @sealed — handleIncreaseSelected + confirmIncreaseSelected (entry #87)
    Runs: webui/frontend/src/components/options/__tests__/test_sealed_increase_position.test.js

    Contracts IA1–IA19:
      IA1–IA2:  pct guard (0 and 100 rejected)
      IA3–IA5:  lotsToAdd = Math.max(1, Math.ceil(size * pct / 100)) — ceil not round
      IA6:      short (size<0) → action=SELL (add more shorts)
      IA7:      long  (size>0) → action=BUY  (add more longs)
      IA8:      newSize = currentSize + lotsToAdd
      IA9:      is_closed positions excluded
      IA10–IA11: limit_price = mid(bid,ask); undefined when both zero
      IA12:     API confirm=true
      IA13:     API order_preference='maker_first' (never 'market_only')
      IA14:     API side='sell' for shorts, 'buy' for longs
      IA15–IA17: selectedStrikes/dialog/percent cleared BEFORE first await
      IA18:     double-fire guard — inFlightRef blocks second concurrent call
      IA18b:    inFlightRef reset to false after completion
      IA19:     all N orders placed via Promise.all (concurrent)
    """

    def test_all_increase_position_contracts_pass(self):
        """
        CONTRACT: handleIncreaseSelected + confirmIncreaseSelected must satisfy all 22
        IA contracts. FAILURE = increase-by-% feature is broken or unsafe (real money).
        """
        result = _run_jest("test_sealed_increase_position")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed IncreasePosition tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_increase_position"
        )


class TestJestSealedUseParsedPositions:
    """
    @sealed — useParsedPositions (entry #88)
    Runs: webui/frontend/src/components/options/__tests__/test_sealed_useParsedPositions.test.js

    Contracts PP1–PP5:
      PP1: empty selectedPositions + no futures → null (no ghost portfolio)
      PP2: 1 of 3 selected → only that 1 in parsedPositions (strict whitelist)
      PP3: realized_pnl=10, partial_realized_pnl=-71.14 → realizedPnl ≈ -61.14
      PP4: realized_pnl=5, no partial_realized_pnl → realizedPnl ≈ 5
      PP5: all N selected → all N in parsedPositions
    """

    def test_all_use_parsed_positions_contracts_pass(self):
        """
        CONTRACT: useParsedPositions must pass all 5 Jest contract tests.
        FAILURE = payoff graph shows wrong positions or wrong P&L at current spot.
        Do NOT ignore — directly affects P&L accuracy on a live trading UI.
        """
        result = _run_jest("test_sealed_useParsedPositions")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed useParsedPositions tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_useParsedPositions"
        )


class TestJestSealedHandleAssignToGroup:
    """
    @sealed — handleAssignToGroup (drag-and-drop group assignment) (entry #87)
    Runs: webui/frontend/src/components/options/__tests__/test_sealed_handleAssignToGroup.test.js

    Contracts HA1–HA8:
      HA1:  Assign ungrouped position to existing group
      HA2:  Remove symbol from old group when reassigning
      HA3:  Assign to null ungroups position
      HA4:  No duplicate symbols in group
      HA5:  Preserves other symbols when assigning new one
      HA6:  Group properties (name, color) preserved during assignment
      HA7:  State updater does not mutate input state (immutability)
      HA8:  Handle missing target group gracefully (no crash)
    """

    def test_all_handle_assign_to_group_contracts_pass(self):
        """
        CONTRACT: handleAssignToGroup state updater must pass all 8 Jest contract tests.
        FAILURE = drag-and-drop group assignment is broken. Position won't move to groups.
        """
        result = _run_jest("test_sealed_handleAssignToGroup")
        output = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"\n\n❌ Jest sealed handleAssignToGroup tests FAILED.\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- Jest output ---\n{output}\n"
            f"------------------\n"
            f"Fix the failing Jest tests before re-running.\n"
            f"Run directly: cd webui/frontend && npm test -- --watchAll=false "
            f"--testPathPattern=test_sealed_handleAssignToGroup"
        )
