"""
MMM Coordination Arbiter — Phase 3 implementation of the sealed hierarchy.
Live mode (no shadow): see user directive 2026-04-28 in MMM_COORDINATION_PLAN.md.

The arbiter is a thin coordinator that activates ONLY at Tier 0 or Tier 1.
At Tier 2/3 (normal/elevated markets), this module is a no-op — operational
modules (whipsaw, regime, gamma, breakeven, harvester, etc.) run as designed.

When Tier 1 fires, the arbiter:
  1. Logs decision to activity log + audit JSON (Rule 7)
  2. Clears `_skip_to_pnl` if set by upstream blocks (Rule 2)
  3. Sets `_arbiter_decision_active=True` for downstream gates
  4. Routes to `mmm_monitor._execute_arbiter_decision()` which executes the
     action via existing tested order-placement infrastructure
     (close_position, _process_strike_shift, smart_execute, etc.)

User-facing toggle: `params['arbiter_enabled']` (default True). Hot-reloadable
via the WebUI settings dialog (advanced section).

Sealed hierarchy rules (see MMM_COORDINATION_PLAN.md):
  Rule 1: Tier 0 absolute (hard stop, ATM shield, time stop). Never bypassed.
  Rule 2: Tier 1 acts, doesn't block. Bypass operational gates, run defensive
          action — premium-aware strike shift / defensive close / margin
          recovery.
  Rule 3: Tier 2 silent. Modules work as designed. No arbiter intervention.
  Rule 4: Premium quality > quantity. Few high-premium policies, not many cheap.
  Rule 5: Last 30 min cool-down. NO Tier 1 bypass. Operational gates run.
  Rule 6: Stale = danger. Signals not refreshed → escalate one tier.
  Rule 7: Audit everything the arbiter changes.

Strategy-specific overrides:
  - STRADDLE_WITH_ADJUSTMENT: ATM shield + gamma BYPASSED at the strategy level.
    Smart whipsaw + Tier 1 defensive logic ACTIVE.
  - Reverse mode: isolated. Arbiter does not touch reverse positions; Tier 0
    still applies via existing close-order infrastructure.

Phase 1 audits that informed this design:
  - audit/mmm/coordination/00_PHASE_1_SUMMARY.md
  - audit/mmm/coordination/03_decision_map.md  (gate inventory + insertion point)
  - audit/mmm/coordination/04_gamma_engine_audit.md  (EMERGENCY → action)
  - audit/mmm/coordination/05_stale_detection_feasibility.md  (Rule 6 plumbing)

Created: 2026-04-28
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from .mmm_state import is_signal_fresh
from .mmm_dte_presets import STRADDLE_WITH_ADJUSTMENT_CATEGORY
from .mmm_strategy_dispatch import resolve_strategy_type

log = logging.getLogger('mmm_arbiter')


# =============================================================================
# Decision dataclasses (immutable result of evaluate())
# =============================================================================

# Action types
ACTION_NOOP = 'noop'
ACTION_DEFENSIVE_SHIFT = 'defensive_shift'
ACTION_GAMMA_EMERGENCY_CLOSE = 'gamma_emergency_close'
ACTION_MARGIN_RECOVERY = 'margin_recovery_buyback'

# Tier identifiers — match Phase 2 hierarchy
TIER_0_ABSOLUTE = 0
TIER_1_EXTREME = 1
TIER_2_ELEVATED = 2
TIER_3_NORMAL = 3


@dataclass(frozen=True)
class StaleSignal:
    """One stale signal recorded for audit trail per Rule 7."""
    name: str                 # e.g. 'breakeven_zone'
    raw_value: str
    effective_value: str      # after one-tier escalation
    last_updated_at: Optional[str]


@dataclass(frozen=True)
class ArbiterDecision:
    """Output of CoordinationArbiter.evaluate().

    `action_type == 'noop'` means arbiter does not intervene this beat.
    Any non-noop decision is a Tier 1 defensive action.
    """
    action_type: str                       # ACTION_*
    tier: int                              # 0 / 1 / 2 / 3
    trigger: str                           # short label e.g. 'breakeven_critical_pe'
    side: Optional[str] = None             # 'ce' or 'pe' for actions
    target_strike: Optional[float] = None
    target_premium: Optional[float] = None
    lots: Optional[int] = None
    reason: str = ''
    stale_signals: Tuple[StaleSignal, ...] = field(default_factory=tuple)
    # Diagnostic snapshot — what the arbiter saw at decision time
    snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_audit_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['stale_signals'] = [asdict(s) for s in self.stale_signals]
        return d


# =============================================================================
# Stale-aware signal accessors (Rule 6 — stale = danger)
# =============================================================================

# Per-tier escalation maps for stale signals.
_BE_ZONE_ESCALATE = {
    'SAFE': 'WARNING',
    'WARNING': 'DANGER',
    'DANGER': 'CRITICAL',
    'CRITICAL': 'CRITICAL',
}
_GAMMA_ESCALATE = {
    'NORMAL': 'SOFT',
    'SOFT': 'HARD',
    'HARD': 'EMERGENCY',
    'EMERGENCY': 'EMERGENCY',
}
_MARGIN_ESCALATE = {
    'GREEN': 'YELLOW',
    'YELLOW': 'ORANGE',
    'ORANGE': 'RED',
    'RED': 'CRITICAL',
    'CRITICAL': 'CRITICAL',
    '': 'GREEN',  # missing → treat as GREEN (engine never ran with bad data)
}


def _escalated_signal(
    session: Dict,
    signal_name: str,
    raw_value: str,
    escalate_map: Dict[str, str],
    max_age_seconds: float,
) -> Tuple[str, Optional[StaleSignal]]:
    """Return (effective_value, stale_record_or_None) for a signal.

    If signal is fresh → effective_value == raw_value, stale_record is None.
    If stale → effective_value escalated one tier, stale_record populated.
    """
    if is_signal_fresh(session, signal_name, max_age_seconds):
        return raw_value, None

    effective = escalate_map.get(raw_value, raw_value)
    record = StaleSignal(
        name=signal_name,
        raw_value=raw_value,
        effective_value=effective,
        last_updated_at=session.get(f'_{signal_name}_last_updated_at'),
    )
    return effective, record


def get_effective_breakeven_zone(session: Dict, max_age_seconds: float) -> Tuple[str, Optional[StaleSignal]]:
    raw = session.get('_breakeven_zone', 'SAFE')
    return _escalated_signal(session, 'breakeven_zone', raw, _BE_ZONE_ESCALATE, max_age_seconds)


def get_effective_gamma_regime(session: Dict, max_age_seconds: float) -> Tuple[str, Optional[StaleSignal]]:
    raw = session.get('_gamma_regime', 'NORMAL')
    return _escalated_signal(session, 'gamma_regime', raw, _GAMMA_ESCALATE, max_age_seconds)


def get_effective_margin_tier(session: Dict, max_age_seconds: float) -> Tuple[str, Optional[StaleSignal]]:
    raw = session.get('_margin_tier', 'GREEN')
    return _escalated_signal(session, 'margin_tier', raw, _MARGIN_ESCALATE, max_age_seconds)


# =============================================================================
# CoordinationArbiter
# =============================================================================

class CoordinationArbiter:
    """Phase 3 coordination arbiter.

    Stateless decision engine. Call `evaluate(session)` once per beat AFTER
    Step 5.8 (gamma detector) and BEFORE the skip-to-PNL gate.

    The arbiter does NOT execute trades. It returns an ArbiterDecision that
    the monitor (or test harness) translates into existing close/shift/sell
    pipeline calls.
    """
    name = 'ARBITER'

    # Warmup beats before activation (avoids fresh-session false stales)
    WARMUP_BEATS = 2

    # Last-30-min cool-down per Rule 5 — Tier 1 disabled in this window
    COOLDOWN_MINUTES_BEFORE_EXPIRY = 30

    def evaluate(self, session: Dict) -> ArbiterDecision:
        """Evaluate the hierarchy and return a decision for this beat.

        Returns ACTION_NOOP if:
          - In last 30 min before expiry (Rule 5)
          - Within first WARMUP_BEATS of session
          - No Tier 1 condition fires (Tier 2/3 — modules work as designed)
        """
        params = session.get('params', {})
        # Beat interval drives stale tolerance
        beat_interval_sec = float(params.get('adjustment_interval', 300))
        max_age_seconds = beat_interval_sec * 1.5

        # Diagnostic snapshot — captured upfront, returned with every decision
        snapshot = {
            'beat': session.get('adjustment_count', 0),
            'minutes_to_expiry': session.get('_minutes_to_expiry'),
            'beat_interval_sec': beat_interval_sec,
        }

        # ── Rule 5: last-30-min cool-down — arbiter is no-op ───────────────
        mte = session.get('_minutes_to_expiry')
        if mte is not None and mte <= self.COOLDOWN_MINUTES_BEFORE_EXPIRY:
            return ArbiterDecision(
                action_type=ACTION_NOOP,
                tier=TIER_3_NORMAL,
                trigger='last_30_min_cooldown',
                reason='Rule 5: Tier 1 bypass disabled in last 30 min before expiry',
                snapshot=snapshot,
            )

        # ── Warmup: not enough beats for stale-detection to be meaningful ──
        adj_count = int(session.get('adjustment_count', 0) or 0)
        # Use first heartbeat write as warmup proxy if no adjustments yet.
        # We can't know exact beat count without a counter, so use
        # adjustment_count + presence of any signal timestamp.
        if adj_count == 0 and not is_signal_fresh(session, 'breakeven_zone', max_age_seconds * 10):
            return ArbiterDecision(
                action_type=ACTION_NOOP,
                tier=TIER_3_NORMAL,
                trigger='warmup',
                reason=f'Session warmup: arbiter no-op until signals are populated',
                snapshot=snapshot,
            )

        # ── Read signals with stale escalation per Rule 6 ──────────────────
        be_zone, be_stale = get_effective_breakeven_zone(session, max_age_seconds)
        gamma, gamma_stale = get_effective_gamma_regime(session, max_age_seconds)
        margin, margin_stale = get_effective_margin_tier(session, max_age_seconds)

        stale_records = tuple(s for s in (be_stale, gamma_stale, margin_stale) if s is not None)
        snapshot.update({
            'be_zone': be_zone,
            'gamma_regime': gamma,
            'margin_tier': margin,
            'stale_count': len(stale_records),
        })

        # ── Tier 1 dispatch (Rule 2: act, don't block) ─────────────────────
        # Order matters: margin RED first (capital constraint binds anything else),
        # then gamma EMERGENCY (curvature reduce), then breakeven CRITICAL (premium shift).

        if margin == 'RED' or margin == 'CRITICAL':
            return self._margin_recovery(session, margin, stale_records, snapshot)

        if gamma == 'EMERGENCY':
            # STRADDLE_WITH_ADJUSTMENT bypasses gamma entirely — no Tier 1 gamma action
            if resolve_strategy_type(session) == STRADDLE_WITH_ADJUSTMENT_CATEGORY:
                snapshot['gamma_bypass_strategy'] = 'STRADDLE_WITH_ADJUSTMENT'
            else:
                return self._gamma_emergency(session, gamma, stale_records, snapshot)

        if be_zone == 'CRITICAL':
            return self._defensive_shift(session, be_zone, stale_records, snapshot)

        # ── Tier 2 / Tier 3 — modules as designed ──────────────────────────
        return ArbiterDecision(
            action_type=ACTION_NOOP,
            tier=TIER_2_ELEVATED if (be_zone in ('DANGER', 'WARNING') or gamma == 'HARD' or margin == 'ORANGE')
                 else TIER_3_NORMAL,
            trigger='no_tier1_condition',
            reason='Operational modules run as designed (Rule 3)',
            stale_signals=stale_records,
            snapshot=snapshot,
        )

    # =========================================================================
    # Tier 1 action handlers — return ArbiterDecision, no side effects
    # =========================================================================

    def _defensive_shift(
        self,
        session: Dict,
        be_zone: str,
        stale_records: Tuple[StaleSignal, ...],
        snapshot: Dict,
    ) -> ArbiterDecision:
        """Premium-aware defensive shift per Rule 4 (insurance company doctrine).

        Identify threatened side (closer to breakeven), shift opposite side to
        a strike where premium ≈ shift_target_premium. Sell minimum lots needed.
        """
        params = session.get('params', {})
        be_result = session.get('_breakeven_result', {}) or {}
        nearest_side = be_result.get('nearest_side', 'none')

        # Map nearest_side → threatened side. nearest_side is 'lower'/'upper'/'none'.
        # Lower breakeven threatened → PE side is in trouble (puts going ITM as spot drops)
        # Upper breakeven threatened → CE side is in trouble (calls going ITM as spot rises)
        if nearest_side == 'lower':
            threatened, opposite = 'pe', 'ce'
        elif nearest_side == 'upper':
            threatened, opposite = 'ce', 'pe'
        else:
            # Fallback: pick side with higher unrealized loss
            ce_pnl = float(session.get('ce', {}).get('unrealized_pnl', 0) or 0)
            pe_pnl = float(session.get('pe', {}).get('unrealized_pnl', 0) or 0)
            threatened = 'pe' if pe_pnl < ce_pnl else 'ce'
            opposite = 'ce' if threatened == 'pe' else 'pe'

        target_premium = float(params.get('shift_target_premium', 100.0))
        tolerance = float(params.get('shift_premium_tolerance', 10.0))

        snapshot.update({
            'threatened_side': threatened,
            'opposite_side': opposite,
            'target_premium': target_premium,
            'tolerance': tolerance,
        })

        return ArbiterDecision(
            action_type=ACTION_DEFENSIVE_SHIFT,
            tier=TIER_1_EXTREME,
            trigger=f'breakeven_{be_zone.lower()}_{threatened}',
            side=opposite,
            target_premium=target_premium,
            reason=(
                f'Tier 1: breakeven {be_zone} on {threatened.upper()} side. '
                f'Defensive shift on {opposite.upper()} → premium target ${target_premium:.0f}±${tolerance:.0f}. '
                f'Rule 4: write fewer high-premium policies, not many cheap. '
                f'Bypassing whipsaw / regime / cooldown / asymmetry per Rule 2.'
            ),
            stale_signals=stale_records,
            snapshot=snapshot,
        )

    def _gamma_emergency(
        self,
        session: Dict,
        gamma: str,
        stale_records: Tuple[StaleSignal, ...],
        snapshot: Dict,
    ) -> ArbiterDecision:
        """Defensive close on dominant-gamma side per Phase 1 audit Task 2.

        Replaces legacy `self.pause('Gamma emergency')` behaviour. Closes lots
        from whichever side contributes more dollar gamma until gamma drops
        below HARD limit.
        """
        ce_dgamma = float(session.get('_ce_dollar_gamma', 0) or 0)
        pe_dgamma = float(session.get('_pe_dollar_gamma', 0) or 0)
        dominant = 'ce' if ce_dgamma >= pe_dgamma else 'pe'

        # Lots to close: target enough reduction to drop one regime tier.
        # gamma scales linearly with lots; closing 25% of dominant side's lots
        # reduces dollar_gamma by ~25% per side. Phase 4 replay will tune this.
        dominant_lots = int(session.get(dominant, {}).get('active_lots', 0) or 0)
        close_lots = max(1, int(dominant_lots * 0.25))

        snapshot.update({
            'ce_dollar_gamma': ce_dgamma,
            'pe_dollar_gamma': pe_dgamma,
            'dominant_side': dominant,
            'dominant_lots': dominant_lots,
            'close_lots': close_lots,
        })

        return ArbiterDecision(
            action_type=ACTION_GAMMA_EMERGENCY_CLOSE,
            tier=TIER_1_EXTREME,
            trigger=f'gamma_emergency_{dominant}',
            side=dominant,
            lots=close_lots,
            reason=(
                f'Tier 1: gamma {gamma} on {dominant.upper()} side '
                f'($Γ_ce={ce_dgamma:.0f} vs $Γ_pe={pe_dgamma:.0f}). '
                f'Defensive close {close_lots} lots to reduce curvature. '
                f'Replaces legacy session pause per Phase 1 audit Task 2.'
            ),
            stale_signals=stale_records,
            snapshot=snapshot,
        )

    def _margin_recovery(
        self,
        session: Dict,
        margin: str,
        stale_records: Tuple[StaleSignal, ...],
        snapshot: Dict,
    ) -> ArbiterDecision:
        """Margin recovery via cheap-OTM buyback per Phase 2 / B2.

        When margin is RED/CRITICAL, the only allowed new trades are
        margin-reducing closes/buybacks. Identify cheapest OTM positions and
        buy them back to free margin.
        """
        # Find side with more positions of "cheap" premium (target buyback set).
        # Caller (monitor) executes via existing close pipeline; arbiter just
        # signals which side to scan.
        ce_lots = int(session.get('ce', {}).get('active_lots', 0) or 0)
        pe_lots = int(session.get('pe', {}).get('active_lots', 0) or 0)
        scan_side = 'ce' if ce_lots >= pe_lots else 'pe'

        snapshot.update({
            'margin_tier': margin,
            'ce_lots': ce_lots,
            'pe_lots': pe_lots,
            'scan_side': scan_side,
        })

        return ArbiterDecision(
            action_type=ACTION_MARGIN_RECOVERY,
            tier=TIER_1_EXTREME,
            trigger=f'margin_{margin.lower()}',
            side=scan_side,
            reason=(
                f'Tier 1: margin {margin}. Buyback cheap OTM on {scan_side.upper()} '
                f'(side with more lots) to free margin. New sells blocked '
                f'until margin returns to ORANGE/SAFE per Phase 2 / B2.'
            ),
            stale_signals=stale_records,
            snapshot=snapshot,
        )


# =============================================================================
# Module-level singleton (matches mmm_engine, mmm_breakeven_engine pattern)
# =============================================================================

_arbiter_instance: Optional[CoordinationArbiter] = None


def get_arbiter() -> CoordinationArbiter:
    """Return the module-level arbiter singleton. Stateless; safe to share."""
    global _arbiter_instance
    if _arbiter_instance is None:
        _arbiter_instance = CoordinationArbiter()
    return _arbiter_instance


def reset_arbiter() -> None:
    """Test-only helper to reset the singleton between sealed tests."""
    global _arbiter_instance
    _arbiter_instance = None
