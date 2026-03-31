"""
Contract tests for MMM Margin Guardian — T2-5

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Covers functions NOT in the existing test_sealed_margin_guardian.py (#73):
  fetch_margin_utilization   — async, parses wallet API response
  MarginGuardian.check()     — async orchestrator: interval gate, fetch, tier, lots
  get_margin_param_defaults  — trivial helper

File: webui/backend/routes/mmm/mmm_margin_guardian.py

--- fetch_margin_utilization contracts ---
C-FMU-1: list response → success=True, utilization computed
C-FMU-2: dict {'result': [...]} response → extracts wallets, success=True
C-FMU-3: dict with success=False → returns success=False, error message
C-FMU-4: no USD/USDT wallet → uses max-balance wallet as fallback
C-FMU-5: meta.net_equity present → uses meta value; fallback to balance when meta=0
C-FMU-6: total_used priority: blocked_margin > portfolio_margin > sum of parts
C-FMU-7: net_equity <= 0 → utilization = 100.0
C-FMU-8: exception in rest_client → success=False, error recorded
C-FMU-9: empty wallets list → success=False, 'No wallets returned'
C-FMU-10: uses get_wallet_balances() when get_wallet_balances_full not present

--- MarginGuardian.check() contracts ---
C-MGC-1: margin_monitor_enabled=False → checked=False, no rest_client call
C-MGC-2: check interval > 1, not yet due → checked=False, last tier returned
C-MGC-3: fetch fails → checked=True, require_action=False, last_tier preserved
C-MGC-4: GREEN tier → require_action=False
C-MGC-5: YELLOW tier → require_action=True, actions=['block_sells']
C-MGC-6: ORANGE tier → require_action=True, lots_to_close computed
C-MGC-7: tier_changed=True when tier differs from previous call
C-MGC-8: consecutive_critical >= threshold → force_stop_session in actions
C-MGC-9: consecutive_critical resets when tier recovers from CRITICAL

--- get_margin_param_defaults contracts ---
C-GMD-1: returns dict equal to MARGIN_PARAM_DEFAULTS
C-GMD-2: returns a copy — mutating result does not affect MARGIN_PARAM_DEFAULTS
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_PARAMS = {
    'margin_monitor_enabled': True,
    'margin_green_pct':    50.0,
    'margin_yellow_pct':   60.0,
    'margin_orange_pct':   75.0,
    'margin_red_pct':      85.0,
    'margin_critical_pct': 90.0,
    'margin_target_pct':   50.0,
    'margin_check_interval_beats': 1,
}


def _make_wallet(balance=10000, pos_margin=5000, order_margin=0,
                 blocked=0, portfolio=0, available=None, symbol='USD'):
    # Default available: balance - pos_margin (so balance-available = pos_margin when
    # no blocked/portfolio override is intended). Tests that explicitly test the
    # balance-minus-available path pass available directly.
    if available is None:
        available = balance - pos_margin
    return {
        'asset_symbol': symbol,
        'balance': balance,
        'available_balance': available,
        'position_margin': pos_margin,
        'order_margin': order_margin,
        'blocked_margin': blocked,
        'portfolio_margin': portfolio,
        'cross_position_margin': 0,
        'cross_order_margin': 0,
    }


def _make_client(wallets, meta=None, *, use_full=True):
    """Build a mock AsyncDeltaClient."""
    response = {'result': wallets, 'meta': meta or {}}
    client = AsyncMock()
    if use_full:
        client.get_wallet_balances_full = AsyncMock(return_value=response)
    else:
        del client.get_wallet_balances_full
        client.get_wallet_balances = AsyncMock(return_value=response)
    return client


def _session(params=None, ce_active=10, pe_active=10):
    return {
        'params': params or DEFAULT_PARAMS,
        'ce': {'active_lots': ce_active, 'frozen_positions': []},
        'pe': {'active_lots': pe_active, 'frozen_positions': []},
    }


# =============================================================================
# fetch_margin_utilization
# =============================================================================

class TestFetchMarginUtilization:

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_1_list_response(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        wallet = _make_wallet(balance=10000, pos_margin=3000, symbol='USD')
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(return_value=[wallet])
        result = await fetch_margin_utilization(client)
        assert result['success'] is True
        # blocked=0, portfolio=0 → total_used = 3000+0 = 3000; net_equity=balance=10000
        # utilization = 3000/10000*100 = 30.0
        assert abs(result['utilization_pct'] - 30.0) < 0.1
        assert result['balance'] == 10000

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_2_dict_result_response(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        wallet = _make_wallet(balance=5000, pos_margin=1000, symbol='USDT')
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )
        result = await fetch_margin_utilization(client)
        assert result['success'] is True

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_3_api_success_false(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'success': False, 'error': 'Unauthorized'}
        )
        result = await fetch_margin_utilization(client)
        assert result['success'] is False
        assert result['error'] is not None

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_4_no_usd_wallet_uses_max_balance(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        eth_wallet = _make_wallet(balance=100, symbol='ETH')
        btc_wallet = _make_wallet(balance=5000, symbol='BTC')  # largest balance
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [eth_wallet, btc_wallet], 'meta': {}}
        )
        result = await fetch_margin_utilization(client)
        assert result['success'] is True
        # Used BTC wallet (larger balance)
        assert result['balance'] == 5000

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_5_net_equity_from_meta(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        wallet = _make_wallet(balance=10000, pos_margin=2000, symbol='USD')
        meta = {'net_equity': 12000}  # higher than balance (includes unrealized pnl)
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': meta}
        )
        result = await fetch_margin_utilization(client)
        # net_equity=12000 from meta; total_used=2000 → util = 2000/12000*100 ≈ 16.67
        assert result['net_equity'] == 12000.0
        assert abs(result['utilization_pct'] - 16.67) < 0.1

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_5b_fallback_to_balance_when_meta_zero(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        wallet = _make_wallet(balance=8000, pos_margin=2000, symbol='USD')
        meta = {'net_equity': 0}  # zero → fallback to balance
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': meta}
        )
        result = await fetch_margin_utilization(client)
        assert result['net_equity'] == 8000.0  # fell back to balance
        assert abs(result['utilization_pct'] - 25.0) < 0.1

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_6_blocked_margin_priority(self):
        """blocked_margin > 0 → use blocked_margin as total_used.
        Set available=balance so balance-available=0 → priority falls to blocked."""
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        # balance-available=0 → skip primary; blocked=6000 takes priority
        wallet = _make_wallet(balance=10000, pos_margin=4000, order_margin=5000,
                              blocked=6000, portfolio=8000, available=10000, symbol='USD')
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )
        result = await fetch_margin_utilization(client)
        # total_used = blocked = 6000; utilization = 6000/10000*100 = 60.0
        assert abs(result['utilization_pct'] - 60.0) < 0.1

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_6b_portfolio_margin_fallback(self):
        """blocked=0 → use portfolio_margin as total_used.
        Set available=balance so balance-available=0 → priority falls to portfolio."""
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        # balance-available=0 → skip primary; blocked=0 → skip; portfolio=4000 used
        wallet = _make_wallet(balance=10000, pos_margin=2000, order_margin=1000,
                              blocked=0, portfolio=4000, available=10000, symbol='USD')
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )
        result = await fetch_margin_utilization(client)
        # total_used = portfolio = 4000; utilization = 4000/10000*100 = 40.0
        assert abs(result['utilization_pct'] - 40.0) < 0.1

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_6c_sum_of_parts_fallback(self):
        """blocked=0, portfolio=0 → sum of pos_margin + order_margin.
        Set available=balance so balance-available=0 → falls through to sum-of-parts."""
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        # balance-available=0, blocked=0, portfolio=0 → sum = 2000+1000 = 3000
        wallet = _make_wallet(balance=10000, pos_margin=2000, order_margin=1000,
                              blocked=0, portfolio=0, available=10000, symbol='USD')
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )
        result = await fetch_margin_utilization(client)
        # total_used = 2000 + 1000 = 3000; utilization = 3000/10000*100 = 30.0
        assert abs(result['utilization_pct'] - 30.0) < 0.1

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_7_net_equity_zero_gives_100pct(self):
        """net_equity <= 0 after meta and balance → utilization = 100%."""
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        wallet = _make_wallet(balance=0, pos_margin=0, symbol='USD')
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )
        result = await fetch_margin_utilization(client)
        assert result['utilization_pct'] == 100.0

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_8_exception_returns_failure(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(side_effect=Exception('Connection refused'))
        result = await fetch_margin_utilization(client)
        assert result['success'] is False
        assert 'Connection refused' in result['error']

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_9_empty_wallets_list(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [], 'meta': {}}
        )
        result = await fetch_margin_utilization(client)
        assert result['success'] is False
        assert 'No wallets' in result['error']

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_fmu_10_uses_get_wallet_balances_when_full_absent(self):
        """Falls back to get_wallet_balances() when full version is absent."""
        from webui.backend.routes.mmm.mmm_margin_guardian import fetch_margin_utilization
        wallet = _make_wallet(balance=5000, pos_margin=1000, symbol='USD')
        client = AsyncMock(spec=[])  # empty spec — no attributes by default
        client.get_wallet_balances = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )
        result = await fetch_margin_utilization(client)
        assert result['success'] is True


# =============================================================================
# MarginGuardian.check()
# =============================================================================

class TestMarginGuardianCheck:

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_mgc_1_disabled_skips_fetch(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import MarginGuardian
        guardian = MarginGuardian('test-session')
        params = {**DEFAULT_PARAMS, 'margin_monitor_enabled': False}
        sess = _session(params=params)
        client = AsyncMock()

        result = await guardian.check(sess, client, heartbeat_number=1)

        assert result['checked'] is False
        assert result['require_action'] is False
        client.get_wallet_balances_full.assert_not_called()

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_mgc_2_check_interval_not_due(self):
        """interval=3 → skip beats 1 and 2, run beat 3."""
        from webui.backend.routes.mmm.mmm_margin_guardian import MarginGuardian
        guardian = MarginGuardian('test-session')
        params = {**DEFAULT_PARAMS, 'margin_check_interval_beats': 3}
        sess = _session(params=params)
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [_make_wallet()], 'meta': {}}
        )

        r1 = await guardian.check(sess, client, heartbeat_number=1)
        assert r1['checked'] is False  # beat 1: 1-0=1 < 3 → skip

        r2 = await guardian.check(sess, client, heartbeat_number=2)
        assert r2['checked'] is False  # beat 2: 2-0=2 < 3 → skip

        r3 = await guardian.check(sess, client, heartbeat_number=3)
        assert r3['checked'] is True   # beat 3: 3-0=3 >= 3 → run

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_mgc_3_fetch_fail_keeps_last_tier(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import MarginGuardian, TIER_YELLOW
        guardian = MarginGuardian('test-session')
        guardian._last_tier = TIER_YELLOW  # previous tier was YELLOW
        sess = _session()
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [], 'meta': {}}  # empty → fetch fails
        )

        result = await guardian.check(sess, client, heartbeat_number=1)
        assert result['checked'] is True
        assert result['require_action'] is False  # fail-safe: don't escalate
        assert result['tier'] == TIER_YELLOW       # last known tier preserved

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_mgc_4_green_tier_no_action_required(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import MarginGuardian, TIER_GREEN
        guardian = MarginGuardian('test-session')
        # 30% utilization → GREEN
        wallet = _make_wallet(balance=10000, pos_margin=3000, symbol='USD')
        sess = _session()
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )

        result = await guardian.check(sess, client, heartbeat_number=1)
        assert result['checked'] is True
        assert result['require_action'] is False
        assert result['tier'] == TIER_GREEN

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_mgc_5_yellow_tier_require_action(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import MarginGuardian, TIER_YELLOW
        guardian = MarginGuardian('test-session')
        # 65% utilization → YELLOW (threshold=60)
        wallet = _make_wallet(balance=10000, pos_margin=6500, symbol='USD')
        sess = _session()
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )

        result = await guardian.check(sess, client, heartbeat_number=1)
        assert result['require_action'] is True
        assert result['tier'] == TIER_YELLOW
        assert 'block_sells' in result['actions']

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_mgc_6_orange_tier_computes_lots_to_close(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import MarginGuardian, TIER_ORANGE
        guardian = MarginGuardian('test-session')
        # 78% utilization → ORANGE (threshold=75)
        wallet = _make_wallet(balance=10000, pos_margin=7800, symbol='USD')
        sess = _session(ce_active=20, pe_active=20)
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )

        result = await guardian.check(sess, client, heartbeat_number=1)
        assert result['require_action'] is True
        assert result['tier'] == TIER_ORANGE
        assert result['lots_to_close']['ce'] > 0 or result['lots_to_close']['pe'] > 0

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_mgc_7_tier_changed_detected(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import MarginGuardian, TIER_GREEN, TIER_YELLOW
        guardian = MarginGuardian('test-session')
        # Start at GREEN. Call with YELLOW utilization → tier_changed=True
        wallet = _make_wallet(balance=10000, pos_margin=6500, symbol='USD')
        sess = _session()
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )

        result = await guardian.check(sess, client, heartbeat_number=1)
        assert result['tier_changed'] is True
        assert result['prev_tier'] == TIER_GREEN
        assert result['tier'] == TIER_YELLOW

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_mgc_8_consecutive_critical_triggers_force_stop(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import MarginGuardian, TIER_CRITICAL
        guardian = MarginGuardian('test-session')
        # 95% utilization → CRITICAL
        wallet = _make_wallet(balance=10000, pos_margin=9500, symbol='USD')
        sess = _session()
        # Set threshold=2 for faster testing
        sess['params'] = {**DEFAULT_PARAMS, 'consecutive_critical_threshold': 2}
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )

        # Beat 1: consecutive_critical = 1 (< threshold=2) → no force_stop yet
        r1 = await guardian.check(sess, client, heartbeat_number=1)
        assert 'force_stop_session' not in r1['actions']
        assert guardian._consecutive_critical == 1

        # Beat 2: consecutive_critical = 2 (>= threshold=2) → force_stop
        r2 = await guardian.check(sess, client, heartbeat_number=2)
        assert 'force_stop_session' in r2['actions']
        assert r2['tier'] == TIER_CRITICAL

    @pytest.mark.sealed
    @pytest.mark.asyncio
    async def test_c_mgc_9_consecutive_critical_resets_on_recovery(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import MarginGuardian
        guardian = MarginGuardian('test-session')
        guardian._consecutive_critical = 5  # artificially elevated

        # 30% utilization → GREEN → resets counter
        wallet = _make_wallet(balance=10000, pos_margin=3000, symbol='USD')
        sess = _session()
        client = AsyncMock()
        client.get_wallet_balances_full = AsyncMock(
            return_value={'result': [wallet], 'meta': {}}
        )

        await guardian.check(sess, client, heartbeat_number=1)
        assert guardian._consecutive_critical == 0


# =============================================================================
# get_margin_param_defaults
# =============================================================================

class TestGetMarginParamDefaults:

    @pytest.mark.sealed
    def test_c_gmd_1_returns_all_defaults(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import (
            get_margin_param_defaults, MARGIN_PARAM_DEFAULTS
        )
        result = get_margin_param_defaults()
        assert result == MARGIN_PARAM_DEFAULTS

    @pytest.mark.sealed
    def test_c_gmd_2_returns_copy_not_original(self):
        from webui.backend.routes.mmm.mmm_margin_guardian import (
            get_margin_param_defaults, MARGIN_PARAM_DEFAULTS
        )
        result = get_margin_param_defaults()
        result['margin_green_pct'] = 999.0  # mutate the copy
        assert MARGIN_PARAM_DEFAULTS['margin_green_pct'] != 999.0
