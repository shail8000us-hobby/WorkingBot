"""
MMM Strategic Integrity Monitor — God Layer

Watches the session from 10,000 feet. The normal heartbeat guards (lot velocity,
regime, margin YELLOW, asymmetry) are individually rational but can collectively
block triggered hedge sells for many consecutive beats, causing the session shape
to drift from its intended hedge posture.

God Layer runs every ~25 minutes on its own clock, completely independent of
heartbeat speed or adaptive rate. It asks one question:

    "In the last 25 minutes, did PNL drift significantly AND was the algo inactive?"

If yes → one corrective adjustment in God mode, bypassing all soft guards.
If no  → take a fresh snapshot and go back to sleep.

God mode bypasses: lot velocity, regime BLOCK_SELLS, margin YELLOW, asymmetry.
God mode never bypasses: PAUSED, STOPPED, margin ORANGE/RED (wind_down),
    FORCE_REDUCE, stale monitor, straddle roll in progress, pending orders.

Architecture:
  - One StrategicIntegrityMonitor per session, stored as monitor._god
  - All persistent state stored in session['_god'] — survives session saves/loads
  - check() is sync — pure evaluation, no exchange calls
  - Caller (mmm_monitor._beat) handles the async order placement
  - god_enabled=False by default — deploy safely, enable per-session

Created: 2026-04-12
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple

log = logging.getLogger('mmm_god_layer')


class StrategicIntegrityMonitor:
    """
    God layer: periodic strategic drift correction.

    Lifecycle:
      1. monitor.__init__  → StrategicIntegrityMonitor(session_id)
      2. monitor.start()   → self._god.initialize(session)
      3. _beat() loop      → result = self._god.check(session, ce_now, pe_now, pnl)
                             if result['should_correct']:
                                 await self._process_adjustment(...)
                                 self._god.record_correction(session, result)
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

    # =========================================================================
    # State initialisation
    # =========================================================================

    def initialize(self, session: Dict) -> None:
        """Ensure _god state block exists. Called once at session start."""
        if '_god' not in session:
            session['_god'] = {
                'snapshot_pnl': None,
                'snapshot_time': None,
                'last_fired': None,
                'cooldown_until': None,
                'total_corrections': 0,
                'last_correction_detail': None,
            }

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _parse_iso(self, s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _is_in_cooldown(self, session: Dict) -> bool:
        cooldown_until = self._parse_iso(
            session.get('_god', {}).get('cooldown_until')
        )
        return cooldown_until is not None and self._now() < cooldown_until

    def _interval_elapsed(self, session: Dict, check_interval_min: int) -> bool:
        """True if enough time has passed since the last snapshot was taken."""
        snapshot_time = self._parse_iso(
            session.get('_god', {}).get('snapshot_time')
        )
        if snapshot_time is None:
            return True  # no snapshot yet → take one
        elapsed_min = (self._now() - snapshot_time).total_seconds() / 60
        return elapsed_min >= check_interval_min

    def _take_snapshot(self, session: Dict, current_pnl: float) -> None:
        """Record a fresh 25-min rolling baseline."""
        session.setdefault('_god', {})
        session['_god']['snapshot_pnl'] = current_pnl
        session['_god']['snapshot_time'] = self._now().isoformat()

    def _minutes_since_last_adjustment(self, session: Dict) -> float:
        """
        Scan adjustment_history in reverse to find the most recent ORGANIC hedge
        adjustment. Returns minutes since that adjustment, or 9999 if none.

        Skips:
        - OPERATOR / STRADDLE_ROLL / GOD_CORRECTION: injections, not hedge responses
        - is_arbiter_correction=True: arbiter-driven mechanical shifts keep the algo
          "busy" but do not represent the organic trigger system responding to PNL
          drift. God must fire when the ORGANIC system is inactive — counting arbiter
          shifts as "activity" starves God and prevents it from ever overriding a
          bad-direction cycle.
        """
        for adj in reversed(session.get('adjustment_history', [])):
            if adj.get('aggressor', '') in ('OPERATOR', 'STRADDLE_ROLL', 'GOD_CORRECTION'):
                continue
            if adj.get('is_arbiter_correction', False):
                continue
            ts = self._parse_iso(adj.get('timestamp', ''))
            if ts is not None:
                return (self._now() - ts).total_seconds() / 60
        return 9999.0

    # =========================================================================
    # Hard stop checks (God never acts when these are true)
    # =========================================================================

    def _hard_stops_active(self, session: Dict) -> Tuple[bool, str]:
        """
        Returns (blocked, reason) for conditions God must always respect.
        These represent genuine financial emergencies where adding sells makes
        things worse, or explicit operator commands to halt.
        """
        # Margin ORANGE/RED: adding more sells risks liquidation
        if session.get('_margin_wind_down'):
            return True, 'margin_wind_down active (ORANGE/RED tier)'

        # Gamma emergency: FORCE_REDUCE means stop adding, reduce instead
        regime_action = session.get('_regime_action')
        try:
            from .mmm_regime import ACTION_FORCE_REDUCE, ACTION_PAUSE
            if regime_action == ACTION_FORCE_REDUCE:
                return True, 'regime ACTION_FORCE_REDUCE active'
            if regime_action == ACTION_PAUSE:
                return True, 'regime ACTION_PAUSE active'
        except ImportError:
            pass

        # Stale monitor: G5 has flagged this instance as stale
        if session.get('_stale_abort_gen'):
            return True, 'stale monitor detected'

        # Straddle roll in progress: roll takes exclusive control
        if session.get('_straddle_roll_in_progress'):
            return True, 'straddle roll in progress'

        return False, ''

    # =========================================================================
    # Main evaluation
    # =========================================================================

    def check(
        self,
        session: Dict,
        ce_now: float,
        pe_now: float,
        current_pnl: float,
    ) -> Dict:
        """
        Evaluate whether a God-mode corrective adjustment is needed.

        Call this from _beat() after safety events and regime checks are
        processed, before trigger evaluation. The check is entirely sync.

        Returns a result dict:
            {
                'should_correct': bool,
                # Only present when should_correct=True:
                'aggressor':     str,   # 'ce' or 'pe'
                'hedge':         str,   # 'pe' or 'ce'
                'premium_now':   float,
                'hedge_premium': float,
                'reason':        str,
                'pnl_drift':     float,
                'minutes_inactive': float,
            }
        """
        NO_ACTION = {'should_correct': False}
        sid = self.session_id
        params = session.get('params', {})

        # Gate 1: Feature switch — off by default
        if not params.get('god_enabled', False):
            return NO_ACTION

        # Gate 2: Cooldown (stay silent after firing)
        if self._is_in_cooldown(session):
            return NO_ACTION

        # Gate 3: Hard financial/operator stops
        blocked, stop_reason = self._hard_stops_active(session)
        if blocked:
            log.debug(f"[{sid}] God layer: hard stop → {stop_reason}")
            return NO_ACTION

        # Gate 4: Check interval not yet elapsed
        check_interval_min = params.get('god_check_interval_min', 25)
        if not self._interval_elapsed(session, check_interval_min):
            return NO_ACTION

        # ── Interval has elapsed — evaluate signals ──

        god = session.get('_god', {})
        snapshot_pnl = god.get('snapshot_pnl')

        # First ever check: no snapshot yet — take one and sleep
        if snapshot_pnl is None:
            self._take_snapshot(session, current_pnl)
            log.info(f"[{sid}] God layer: initial snapshot taken, pnl={current_pnl:.2f}")
            return NO_ACTION

        # Signal 1: PNL has drifted down significantly in the window
        pnl_threshold = params.get('god_pnl_threshold', 40.0)
        pnl_drift = current_pnl - snapshot_pnl
        pnl_signal = pnl_drift < -pnl_threshold

        # Signal 2: Algo has been inactive (no executed adjustments recently)
        min_silence_min = params.get('god_min_silence_min', 20)
        minutes_inactive = self._minutes_since_last_adjustment(session)
        inactivity_signal = minutes_inactive >= min_silence_min

        if not pnl_signal or not inactivity_signal:
            # Session is healthy — reset window and sleep
            self._take_snapshot(session, current_pnl)
            if pnl_signal:
                log.info(
                    f"[{sid}] God layer: PNL drifted ${pnl_drift:.2f} but algo was "
                    f"active {minutes_inactive:.0f}min ago — no correction needed"
                )
            return NO_ACTION

        # Both signals fired — identify current aggressor via trigger evaluation
        try:
            from .mmm_trigger import evaluate_triggers, OUTCOME_CE, OUTCOME_PE
        except ImportError:
            log.warning(f"[{sid}] God layer: cannot import mmm_trigger — skipping")
            self._take_snapshot(session, current_pnl)
            return NO_ACTION

        trigger_result = evaluate_triggers(session, ce_now, pe_now)
        outcome = trigger_result.get('outcome', 'none')

        if outcome not in (OUTCOME_CE, OUTCOME_PE):
            # PNL drifted + algo inactive, but NO trigger firing right now.
            # Market may have recovered or reversed. Take fresh snapshot.
            log.info(
                f"[{sid}] God layer: drift=${pnl_drift:.2f}, inactive={minutes_inactive:.0f}m "
                f"— but no trigger active, taking fresh snapshot"
            )
            self._take_snapshot(session, current_pnl)
            return NO_ACTION

        aggressor = 'ce' if outcome == OUTCOME_CE else 'pe'
        hedge = 'pe' if aggressor == 'ce' else 'ce'
        premium_now = ce_now if aggressor == 'ce' else pe_now
        hedge_premium = pe_now if aggressor == 'ce' else ce_now

        reason = (
            f'God correction: PNL drifted ${pnl_drift:.2f} over ~{check_interval_min}min, '
            f'no adjustment for {minutes_inactive:.0f}min — '
            f'{aggressor.upper()} triggered, hedging {hedge.upper()} in god_mode'
        )

        log.warning(
            f"[{sid}] GOD LAYER FIRING: {reason}"
        )

        return {
            'should_correct': True,
            'aggressor': aggressor,
            'hedge': hedge,
            'premium_now': premium_now,
            'hedge_premium': hedge_premium,
            'reason': reason,
            'pnl_drift': pnl_drift,
            'minutes_inactive': minutes_inactive,
            'trigger_result': trigger_result,
        }

    # =========================================================================
    # Post-correction bookkeeping
    # =========================================================================

    def record_correction(self, session: Dict, result: Dict) -> None:
        """
        Call after the God-mode _process_adjustment() completes successfully.
        Sets cooldown, updates counters, takes fresh snapshot.
        """
        params = session.get('params', {})
        cooldown_min = params.get('god_cooldown_min', 45)
        now = self._now()

        session.setdefault('_god', {})
        god = session['_god']
        god['last_fired'] = now.isoformat()
        god['cooldown_until'] = (now + timedelta(minutes=cooldown_min)).isoformat()
        god['total_corrections'] = god.get('total_corrections', 0) + 1
        god['last_correction_detail'] = {
            'timestamp': now.isoformat(),
            'aggressor': result['aggressor'],
            'hedge': result['hedge'],
            'pnl_drift': round(result['pnl_drift'], 2),
            'minutes_inactive': round(result['minutes_inactive'], 1),
            'reason': result['reason'],
        }

        # Fresh snapshot — cooldown starts now, next window begins from this correction
        # Use snapshot_pnl = current (caller should pass post-correction PNL ideally,
        # but using pre-correction PNL is also safe — drift will be smaller next window)
        god['snapshot_pnl'] = None   # Force re-snapshot on next interval check
        god['snapshot_time'] = None

        log.info(
            f"[{self.session_id}] God layer: correction recorded, "
            f"cooldown until {god['cooldown_until']}, "
            f"total_corrections={god['total_corrections']}"
        )
