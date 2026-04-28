"""
MMM Activity Log — Background Activities Tracker

Maintains an in-memory + persisted ring buffer of background activity events
so the WebUI can show users what the algo is doing in real-time:
- Order placement, fill waits, repricing, fills, errors
- Heartbeat execution, adjustments, reversals
- Safety events, session state changes

Created: February 15, 2026
"""

import json
import os
import logging
import queue
import threading
import shutil
from collections import Counter, deque
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

log = logging.getLogger('mmm_activity')

# Persist file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
ACTIVITY_FILE = os.path.join(DATA_DIR, 'mmm_activity_log.json')
ACTIVITY_BACKUP_FILE = f'{ACTIVITY_FILE}.bak'

# Maximum activities to keep in memory and on disk
# Fix #16: Increased from 200 to 500 for better post-crash debugging
MAX_ACTIVITIES = 500


def _titleize_activity_type(activity_type: str) -> str:
    """Convert snake_case activity keys to readable labels."""
    if not activity_type:
        return 'Unknown'
    return activity_type.replace('_', ' ').strip().title()


def _parse_iso_ts(ts: Any) -> Optional[datetime]:
    """Best-effort timestamp parser for ISO strings (UTC-normalized)."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        dt = ts
    else:
        raw = str(ts).strip()
        if not raw:
            return None
        if raw.endswith('Z'):
            raw = raw[:-1] + '+00:00'
        try:
            dt = datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

# Activity types
ACTIVITY_TYPES = {
    # Order lifecycle
    'order_placing': 'Placing Order',
    'order_placed': 'Order Placed',
    'order_waiting_fill': 'Waiting for Fill',
    'order_fill_check': 'Checking Fill Status',
    'order_filled': 'Order Filled',
    'order_repricing': 'Repricing Order',
    'order_repricing_aggressive': 'Aggressive Repricing',
    'order_amended': 'Order Amended',
    'order_cancelled': 'Order Cancelled',
    'order_failed': 'Order Failed',
    'order_retrying': 'Retrying Order',
    'pending_fill_recorded': 'Pending Fill Recorded',
    'pending_order_resolved': 'Pending Order Resolved',
    'pending_order_active': 'Pending Order Active',
    'order_partial_fill': 'Partial Fill',

    # Entry
    'entry_starting': 'Starting Entry',
    'entry_complete': 'Entry Complete',
    'entry_failed': 'Entry Failed',
    'entry_rolled_back': 'Entry Rolled Back',
    'entry_rollback': 'Rolling Back Entry',
    'entry_rollback_ok': 'Rollback Complete',
    'entry_rollback_failed': 'Rollback Failed',
    'entry_rollback_escalation': 'Rollback Escalated to Emergency',
    'partial_entry': 'Partial Entry',
    'partial_entry_retry': 'Partial Entry Retry',
    'partial_entry_retry_failed': 'Partial Entry Retry Failed',

    # Session lifecycle
    'session_created': 'Session Created',
    'session_initialized': 'Session Initialized',
    'session_starting': 'Session Starting',
    'session_started': 'Session Started',
    'session_adopted': 'Session Adopted',
    'session_paused': 'Session Paused',
    'session_resumed': 'Session Resumed',
    'session_stopped': 'Session Stopped',
    'force_heartbeat': 'Force Heartbeat',
    'watchdog': 'Watchdog Alert',

    # Adjustments
    'adjustment_triggered': 'Adjustment Triggered',
    'adjustment_complete': 'Adjustment Complete',
    'adjustment_skipped': 'Adjustment Skipped',
    'reversal_skip': 'Reversal Skip',
    'reversal_skip_force_through': 'Reversal Force Through',
    'strike_shift': 'Strike Shift',
    'shift_no_strike': 'Shift No Strike',
    'shift_aborted': 'Shift Aborted',
    'shift_candidate_stale': 'Shift Candidate Stale',
    'shift_fallback_below_floor': 'Shift Fallback Blocked',
    'shift_sell_failed_unfreeze': 'Shift Sell Failed (Unfrozen)',
    'shift_post_fill_error': 'Shift Post-Fill Error',
    'proactive_shift': 'Proactive Shift',
    'proactive_shift_lot_fallback': 'Proactive Shift Lot Fallback',
    'delta_neutral_match': 'Delta-Neutral Match',
    'cap_auto_shift': 'Cap Auto Shift',
    'capacity_full': 'Capacity Full',
    'delta_rescue': 'Delta Rescue',
    'trigger_cleared_by_close_at_5': 'Trigger Cleared',
    'cooldown_blocking': 'Cooldown Blocking',
    'itm_guard_blocked': 'ITM Guard Blocked',
    'itm_guard_bypassed': 'ITM Guard Bypassed',
    'gamma_projection_blocked': 'Gamma Projection Blocked',
    'consecutive_dir_blocked': 'Consecutive Direction Blocked',
    'consecutive_dir_auto_resume': 'Consecutive Direction Auto Resume',
    'replenish_grace_hold': 'Replenish Grace Hold',
    'adjustment_orphan': 'Adjustment Orphan (Manual Close Required)',
    'adjustment_recovery': 'Adjustment Recovery Attempt',
    'adjustment_recovery_ok': 'Adjustment Recovery OK',
    'adjustment_recovery_exception': 'Adjustment Recovery Exception',

    # Safety
    'safety_warning': 'Safety Warning',
    'safety': 'Safety Alert',
    'safety_block': 'Safety Block',
    'guardian_violation': 'Guardian Violation',
    'guardian_auto_heal': 'Guardian Auto-Heal',
    'god_correction': 'God Layer Correction',
    'strategy_validation': 'Strategy Validation',
    'trigger_stale': 'Stale Trigger',
    'max_loss_breach': 'Max Loss Breach',
    'hard_stop': 'Hard Stop',
    'expiry_close': 'Expiry Close',
    'adjustments_stopped': 'Adjustments Stopped',
    'asymmetry_side_block': 'Asymmetry Side Block',
    'asymmetry_side_blocked': 'Asymmetry Side Blocked',
    'dangerous_mode_bypass': 'Dangerous Mode Bypass',
    'dangerous_mode_blocked': 'Dangerous Mode Blocked',
    'shift_starvation_info':     'Shift Starvation (L1)',
    'shift_starvation_warning':  'Shift Starvation (L2)',
    'shift_starvation_critical': 'Shift Starvation (L3)',
    'exchange_position_warning': 'Exchange Position Warning',
    'exchange_position_info': 'Exchange Position Info',
    'reconciliation_warning': 'Reconciliation Warning',
    'reconciliation_autocorrect': 'Reconciliation Auto-Correct',
    'margin_tier_change': 'Margin Tier Change',
    'margin_red': 'Margin RED',
    'margin_critical': 'Margin CRITICAL',
    'ocs_auto_resume': 'One-Side-Close Auto Resume',
    'both_sides_closed_awake': 'Both Sides Closed (Awake Hours)',
    'regime_pause': 'Regime Pause',
    'regime_auto_resume': 'Regime Auto Resume',

    # Close-at-5
    'close_at_5': 'Position Closed',

    # Wind-down & Margin
    'wind_down': 'Wind-Down',
    'atm_wind_down': 'ATM Wind-Down',
    'atm_auto_close': 'ATM Auto-Close',
    'margin_wind_down': 'Margin Wind-Down',
    'margin_block_sells': 'Margin Block',

    # Regime
    'regime_control': 'Regime Control',
    'regime_block': 'Regime Block',
    'regime_emergency': 'Regime Emergency',

    # Both sides
    'both_sides_auto_decision': 'Both Sides Decision',

    # Perp Hedge
    'perp_hedge': 'Perp Hedge',

    # Delta Neutral Engine
    'delta_engine': 'Delta Hedge',

    # Emergency
    'emergency': 'Emergency',
    'emergency_order': 'Emergency Order',
    'emergency_placing': 'Emergency Placing',
    'emergency_filled': 'Emergency Filled',
    'emergency_error': 'Emergency Error',

    # Circuit breaker
    'heartbeat_partial': 'Partial Heartbeat',
    'heartbeat_miss': 'Missed Heartbeat',
    'heartbeat_error': 'Heartbeat Error',

    # Stale data
    'stale_price_warning': 'Stale Price',

    # Lot lifecycle (M1/M2/M3/Split Ledger)
    'harvest': 'Position Harvested',
    'recycle': 'Lot Recycling',
    'shift_recycle': 'Shift-Time Recycle',
    'rebalance_boost': 'Rebalance Boost',
    'trend_boost': 'Trend Boost',
    'whipsaw_guard': 'Whipsaw Guard',
    'whipsaw_smart_block': 'Smart Whipsaw Block',
    'atm_shield': 'ATM Shield',

    # Fill sync
    'fill_sync_confirmed': 'Fill Confirmed',
    'fill_sync_partial': 'Partial Sub-Fill',
    'worthless_expiry_closed': 'Worthless Expiry Closed',

    # Ghost-close recovery
    'ghost_close_recovered': 'Ghost Close Recovered',

    # Breakeven Engine
    'breakeven_zone_change': 'Breakeven Zone Change',
    'breakeven_band_contracting': 'Breakeven Band Contracting',
    'breakeven_narrow_band': 'Narrow Breakeven Band',

    # Gamma Detector Engine
    'gamma_zone_change': 'Gamma Zone Change',
    'gamma_danger_detected': 'Gamma Danger Detected',

    # Coordination Arbiter
    'arbiter_tier1':                  'Arbiter Tier 1 Action',
    'arbiter_stale_signal':           'Arbiter Stale Signal',
    'arbiter_defensive_shift_exec':   'Arbiter Defensive Shift',
    'arbiter_gamma_close_exec':       'Arbiter Gamma Close',
    'arbiter_margin_recovery_exec':   'Arbiter Margin Recovery',
    'regime_emergency_arbiter':       'Regime Emergency (Arbiter)',

    # Profit Ratchet
    'profit_ratchet': 'Profit Ratchet',

    # FSU: Favorable Scale-Up
    'scale_up_triggered': 'Scale-Up Triggered',
    'scale_up_complete': 'Scale-Up Complete',
    'scale_up_failed': 'Scale-Up Failed',
    'scale_up_no_strikes': 'Scale-Up No Strikes',

    # Adaptive Tuning Engine
    'param_adapted': 'Param Adapted',

    # Auto-Replenish Leg
    'replenish_triggered': 'Replenish Triggered',
    'replenish_complete': 'Replenish Complete',
    'replenish_failed': 'Replenish Failed',
    'replenish_blocked': 'Replenish Blocked',

    # Straddle Roll
    'straddle_roll': 'Straddle Roll',
    'straddle_roll_blocked': 'Roll Blocked',

    # Hot reload
    'hot_reload': 'Hot Reload',
    'set_active_strike': 'Set Active Strike',
    'manual_close_strike': 'Manual Close Strike',
    'manual_adjust_lots': 'Manual Adjust Lots',
    'manual_reduce': 'Manual Reduce',
    'manual_inject': 'Manual Inject',
    'pin_trigger': 'Pin Trigger',
    'unpin_trigger': 'Unpin Trigger',
    'auto_atm_promote': 'Auto ATM Promote',
    'auto_close_all': 'Auto Close All',
    'auto_close_failures': 'Auto Close Failures',

    # Global Graceful Exit / Kill Switch
    'session_exit_all_initiated': 'Exit All Initiated',
    'session_exit_all_completed': 'Exit All Complete',
    'session_exit_all_partial': 'Exit All Partial',
    'kill_switch_triggered': 'Kill Switch Triggered',

    # Reverse Mode
    'reverse_entry': 'Reverse Entry',
    'reverse_closed': 'Reverse Closed',
    'reverse_disabled': 'Reverse Disabled',
    'reverse_status': 'Reverse Status',

    # General
    'info': 'Info',
    'warning': 'Warning',
    'critical': 'Critical',
    'error': 'Error',
}

# Backward-compat aliases from old/log-noisy names to canonical types.
ACTIVITY_TYPE_ALIASES = {
    'session_pause': 'session_paused',
    'session_stop': 'session_stopped',
    'session_start': 'session_started',
    'safety_event': 'safety_warning',
    'max_loss': 'max_loss_breach',
}

# Activity categories for frontend filtering
ACTIVITY_CATEGORIES = {
    'orders': {'order_placing', 'order_placed', 'order_waiting_fill', 'order_fill_check',
               'order_filled', 'order_repricing', 'order_amended', 'order_cancelled',
               'order_failed', 'order_retrying', 'entry_starting', 'entry_complete',
               'entry_failed', 'entry_rollback', 'entry_rollback_ok', 'entry_rollback_failed',
                'entry_rolled_back', 'entry_rollback_escalation',
                'partial_entry', 'partial_entry_retry', 'partial_entry_retry_failed',
                'order_repricing_aggressive', 'pending_fill_recorded', 'pending_order_resolved',
                'pending_order_active', 'order_partial_fill',
               'emergency_order', 'emergency_placing', 'emergency_filled', 'emergency_error',
               'adjustment_orphan', 'adjustment_recovery', 'adjustment_recovery_ok',
               'adjustment_recovery_exception'},
    'adjustments': {'adjustment_triggered', 'adjustment_complete', 'adjustment_skipped',
                    'strike_shift', 'shift_post_fill_error',
                    'shift_no_strike', 'shift_aborted', 'shift_candidate_stale',
                    'shift_fallback_below_floor', 'shift_sell_failed_unfreeze',
                    'proactive_shift', 'proactive_shift_lot_fallback',
                    'delta_neutral_match', 'cap_auto_shift',
                    'reversal_skip', 'reversal_skip_force_through',
                    'cooldown_blocking', 'itm_guard_blocked', 'itm_guard_bypassed',
                    'gamma_projection_blocked', 'consecutive_dir_blocked',
                    'consecutive_dir_auto_resume', 'replenish_grace_hold', 'delta_rescue',
                    'trigger_cleared_by_close_at_5',
                    'close_at_5', 'wind_down', 'atm_wind_down', 'atm_auto_close',
                    'margin_wind_down', 'margin_block_sells', 'perp_hedge',
                    'both_sides_auto_decision',
                    'harvest', 'recycle', 'shift_recycle', 'rebalance_boost', 'trend_boost',
                    'scale_up_triggered', 'scale_up_complete', 'scale_up_failed',
                    'scale_up_no_strikes',
                    'replenish_triggered', 'replenish_complete', 'replenish_failed',
                    'replenish_blocked',
                    'straddle_roll', 'straddle_roll_blocked',
                    'reverse_entry', 'reverse_closed', 'reverse_status',
                    'manual_adjust_lots', 'manual_close_strike', 'manual_inject',
                    'manual_reduce', 'set_active_strike', 'pin_trigger', 'unpin_trigger',
                    'auto_atm_promote',
                    'fill_sync_confirmed', 'fill_sync_partial',
                    'worthless_expiry_closed',
                    'delta_engine',
                    'profit_ratchet'},
    'safety': {'safety_warning', 'safety_block', 'trigger_stale', 'max_loss_breach',
                'capacity_full',
                'safety', 'guardian_violation', 'guardian_auto_heal', 'god_correction',
                'strategy_validation',
                'hard_stop', 'expiry_close', 'adjustments_stopped',
                'dangerous_mode_bypass', 'dangerous_mode_blocked',
                'shift_starvation_info', 'shift_starvation_warning', 'shift_starvation_critical',
                'asymmetry_side_block', 'asymmetry_side_blocked',
                'exchange_position_warning', 'exchange_position_info',
                'reconciliation_warning', 'reconciliation_autocorrect',
                'margin_tier_change', 'margin_red', 'margin_critical',
                'regime_control', 'regime_block', 'regime_emergency', 'regime_pause',
                'regime_auto_resume', 'ocs_auto_resume', 'both_sides_closed_awake',
               'stale_price_warning', 'heartbeat_partial', 'heartbeat_miss', 'heartbeat_error',
                'whipsaw_guard', 'whipsaw_smart_block', 'atm_shield', 'ghost_close_recovered',
               'breakeven_zone_change', 'breakeven_band_contracting', 'breakeven_narrow_band',
               'gamma_zone_change', 'gamma_danger_detected',
               'reverse_disabled',
               'arbiter_tier1', 'arbiter_stale_signal', 'arbiter_defensive_shift_exec',
               'arbiter_gamma_close_exec', 'arbiter_margin_recovery_exec',
               'regime_emergency_arbiter'},
    'system': {'session_created', 'session_initialized', 'session_starting', 'session_started',
                'session_adopted', 'session_paused', 'session_resumed', 'session_stopped',
                'hot_reload', 'watchdog', 'force_heartbeat', 'emergency',
                'auto_close_all', 'auto_close_failures',
               'session_exit_all_initiated', 'session_exit_all_completed', 'session_exit_all_partial',
               'kill_switch_triggered',
               'param_adapted',
               'info', 'warning', 'critical', 'error'},
}

# Severity levels
SEVERITY_INFO = 'info'
SEVERITY_SUCCESS = 'success'
SEVERITY_WARNING = 'warning'
SEVERITY_ERROR = 'error'
SEVERITY_CRITICAL = 'critical'
SEVERITY_PROGRESS = 'progress'  # For ongoing actions (placing, waiting)

SEVERITY_PRIORITY = {
    SEVERITY_PROGRESS: 0,
    SEVERITY_INFO: 1,
    SEVERITY_SUCCESS: 2,
    SEVERITY_WARNING: 3,
    SEVERITY_ERROR: 4,
    SEVERITY_CRITICAL: 5,
}

# Reverse Mode activity type constants (importable by mmm_reverse.py)
ACTIVITY_REVERSE_ENTRY = 'reverse_entry'
ACTIVITY_REVERSE_CLOSED = 'reverse_closed'
ACTIVITY_REVERSE_DISABLED = 'reverse_disabled'
ACTIVITY_REVERSE_STATUS = 'reverse_status'


class MMMActivityLog:
    """
    Thread-safe activity log for MMM background operations.

    Activities are stored in a ring buffer (deque) and persisted to disk.
    The WebUI polls this to show users what's happening behind the scenes.
    """

    def __init__(self):
        self._lock = threading.RLock()  # C-8 fix: thread-safe access
        self._activities: deque = deque(maxlen=MAX_ACTIVITIES)
        # M-21 fix: create directory in __init__ not in _save_to_disk()
        os.makedirs(os.path.dirname(ACTIVITY_FILE), exist_ok=True)
        self._load_from_disk()
        self._counter = 0
        # Initialize _id_counter above the highest persisted ID to prevent
        # collisions after restart (IDs look like act_20260323_085500_000042).
        max_seen = 0
        for act in self._activities:
            act_id = act.get('id', '')
            if act_id.startswith('act_') and act_id.count('_') >= 3:
                try:
                    max_seen = max(max_seen, int(act_id.rsplit('_', 1)[-1]))
                except (ValueError, IndexError):
                    pass
        self._id_counter = max_seen
        # Recommendation #6: Activity log dedup tracking
        # Maps (type, session_id, message_prefix) → last_logged_timestamp
        self._dedup_cache: Dict[tuple, datetime] = {}
        self._DEDUP_INTERVAL_SECS = 30  # Suppress identical events within this window
        self._suppressed_dedup_count = 0
        # Background disk writer — keeps fsync/backup I/O off the event loop thread.
        # Queue is bounded (maxsize=10); if full, the write is dropped (non-critical
        # for a UI log — in-memory state is always authoritative).
        self._write_queue: queue.Queue = queue.Queue(maxsize=10)
        self._writer_thread = threading.Thread(
            target=self._background_writer,
            daemon=True,
            name='mmm-activity-writer',
        )
        self._writer_thread.start()

    def _load_file(self, path: str) -> List[Dict[str, Any]]:
        """Load activities payload from a file path."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            items = data.get('activities', [])
        elif isinstance(data, list):
            items = data
        else:
            items = []
        if not isinstance(items, list):
            return []
        return [i for i in items if isinstance(i, dict)]

    def _load_from_disk(self):
        """Load persisted activities on startup."""
        if not os.path.exists(ACTIVITY_FILE):
            return
        try:
            items = self._load_file(ACTIVITY_FILE)
            for item in items:
                self._activities.append(item)
            log.info(f"Loaded {len(self._activities)} activities from disk")
            return
        except Exception as e:
            log.warning(f"Could not load activity log: {e}")

        # Recovery path: malformed main file, attempt backup.
        if os.path.exists(ACTIVITY_BACKUP_FILE):
            try:
                items = self._load_file(ACTIVITY_BACKUP_FILE)
                for item in items:
                    self._activities.append(item)
                log.warning(
                    f"Recovered {len(self._activities)} activities from backup after primary log corruption"
                )
                return
            except Exception as be:
                log.warning(f"Could not recover activity log from backup: {be}")

        # Final fallback: quarantine corrupt file and continue with empty log.
        try:
            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            corrupt_path = f"{ACTIVITY_FILE}.corrupt.{ts}"
            os.replace(ACTIVITY_FILE, corrupt_path)
            log.error(f"Quarantined corrupt activity file at {corrupt_path}")
        except Exception as qe:
            log.warning(f"Could not quarantine corrupt activity log: {qe}")

    # M-7 fix: activity types that must always persist regardless of throttle
    _ALWAYS_PERSIST_TYPES = frozenset({
        'safety_event', 'safety', 'auto_close', 'auto_close_all', 'max_loss',
        'max_loss_breach', 'emergency', 'guardian_violation', 'guardian_auto_heal',
        'session_stop', 'session_stopped', 'session_pause', 'session_paused',
        'hard_stop', 'watchdog', 'margin_critical',
        'session_exit_all_initiated', 'session_exit_all_completed', 'session_exit_all_partial',
        'kill_switch_triggered',
        'error', 'critical',
    })

    def _should_persist(self, activity: Dict) -> bool:
        """M-7 fix: determine if this activity bypasses the throttle.

        Critical and error severity events, plus safety/session-lifecycle event
        types, always write to disk so post-crash debugging has full context.
        """
        # Always persist critical/error/warning severity
        if activity.get('severity') in (SEVERITY_CRITICAL, SEVERITY_ERROR, SEVERITY_WARNING):
            return True
        # Always persist important lifecycle types
        if activity.get('type') in self._ALWAYS_PERSIST_TYPES:
            return True
        # For all other events: apply the 1-in-2 throttle
        return self._counter % 2 == 0

    def _normalize_activity_type(self, activity_type: str) -> str:
        raw = str(activity_type or '').strip()
        if not raw:
            return 'info'
        return ACTIVITY_TYPE_ALIASES.get(raw, raw)

    def _normalize_severity(self, severity: str) -> str:
        sev = str(severity or '').strip().lower()
        if sev in SEVERITY_PRIORITY:
            return sev
        return SEVERITY_INFO

    def _infer_category(self, activity_type: str) -> str:
        for cat, types in ACTIVITY_CATEGORIES.items():
            if activity_type in types:
                return cat

        # Prefix/keyword fallback for forward-compatibility when new types are introduced.
        if activity_type.startswith('order_') or activity_type.startswith('pending_'):
            return 'orders'
        if (
            activity_type.startswith('replenish_')
            or activity_type.startswith('shift_')
            or activity_type.startswith('adjustment_')
            or activity_type.startswith('manual_')
            or activity_type.startswith('reversal_')
            or activity_type.startswith('scale_')
        ):
            return 'adjustments'
        if any(k in activity_type for k in (
            'safety', 'guardian', 'margin', 'regime', 'watchdog', 'reconciliation',
            'max_loss', 'hard_stop', 'stale', 'asymmetry', 'dangerous',
        )):
            return 'safety'
        return 'system'

    def _background_writer(self):
        """Drain the write queue and persist to disk off the event loop thread.

        Runs as a daemon thread so it exits automatically when the process ends.
        Blocks on queue.get() — no busy-loop, no sleep. Each item is either an
        activity dict (passed through to _do_save_to_disk for critical-bypass
        logic) or None (sentinel to drain a queued non-critical write).
        """
        while True:
            try:
                item = self._write_queue.get(timeout=5.0)
                self._do_save_to_disk(item)
            except queue.Empty:
                continue
            except Exception as e:
                log.warning(f"Activity background writer error: {e}")

    def _save_to_disk(self, activity: Dict = None):
        """Enqueue a disk write (throttled — every 2nd write).

        The counter increment and throttle check run synchronously so the 1-in-2
        cadence is correct. Actual I/O is handed off to the background writer
        thread so fsync/backup never block the event loop or the heartbeat thread.
        """
        self._counter += 1
        if activity is not None and not self._should_persist(activity):
            return
        try:
            self._write_queue.put_nowait(activity)
        except queue.Full:
            log.debug("Activity write queue full — disk write skipped (in-memory state intact)")

    def _do_save_to_disk(self, activity: Dict = None):
        """Persist activities to disk (called from background writer thread only).

        Fix #16: Atomic write (write to .tmp then rename) prevents corruption
        on crash mid-write.
        M-7 fix: critical/error/warning severity and safety event types bypass
        the throttle so they are always persisted for post-crash debugging.
        Fix: use unique tmp file per call to avoid race between concurrent
        heartbeat threads (Thread A renames .tmp away before Thread B can).
        H-12 fix: lock around os.rename() critical section.
        """
        tmp_file = None
        try:
            import tempfile
            fd, tmp_file = tempfile.mkstemp(
                suffix='.tmp',
                dir=os.path.dirname(ACTIVITY_FILE),
                prefix='mmm_activity_',
            )
            # Snapshot under lock then immediately release — disk I/O (json.dump/fsync/copy2)
            # must NOT hold the lock or add() blocks on every heartbeat log call.
            with self._lock:
                snapshot = list(self._activities)
            payload = {
                'activities': snapshot,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            with os.fdopen(fd, 'w') as f:
                json.dump(payload, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(ACTIVITY_FILE):
                try:
                    shutil.copy2(ACTIVITY_FILE, ACTIVITY_BACKUP_FILE)
                except Exception as be:
                    log.debug(f"Could not refresh activity log backup: {be}")
            # Atomic rename — survives crash between write and rename
            os.replace(tmp_file, ACTIVITY_FILE)
        except Exception as e:
            log.warning(f"Could not save activity log: {e}")
            # Clean up temp file if rename failed
            try:
                if tmp_file and os.path.exists(tmp_file):
                    os.unlink(tmp_file)
            except Exception as _e:
                log.error(f"Temp cleanup failed: {_e}")  # L-7 fix

    def add(
        self,
        activity_type: str,
        message: str,
        session_id: str = None,
        severity: str = SEVERITY_INFO,
        details: Dict = None,
    ) -> Dict:
        """
        Add a new activity to the log.

        Args:
            activity_type: One of ACTIVITY_TYPES keys
            message: Human-readable description
            session_id: Associated session ID (optional)
            severity: info | success | warning | error | progress
            details: Additional structured data

        Returns:
            The activity dict that was added, or None if deduplicated
        """
        activity_type = self._normalize_activity_type(activity_type)
        severity = self._normalize_severity(severity)
        msg = message if isinstance(message, str) else str(message)
        msg = msg.strip() or ACTIVITY_TYPES.get(activity_type, _titleize_activity_type(activity_type))
        if not isinstance(details, dict):
            details = {'raw': details}

        # Recommendation #6: Deduplicate spammy events
        # Only dedup types that fire every heartbeat; never dedup critical events
        _DEDUP_TYPES = {
            'info', 'warning', 'safety_warning', 'trigger_stale',
            'wind_down', 'regime_control',
        }
        if activity_type in _DEDUP_TYPES and severity not in (SEVERITY_ERROR, SEVERITY_CRITICAL):
            # Use first 80 chars of message as dedup key (ignores changing numbers)
            dedup_key = (activity_type, session_id or '', msg[:80])
            now = datetime.now(timezone.utc)
            last = self._dedup_cache.get(dedup_key)
            if last and (now - last).total_seconds() < self._DEDUP_INTERVAL_SECS:
                self._suppressed_dedup_count += 1
                return None  # Suppress duplicate
            self._dedup_cache[dedup_key] = now

            # Prune stale dedup entries every 100 adds
            if len(self._dedup_cache) > 500:
                cutoff = now
                self._dedup_cache = {
                    k: v for k, v in self._dedup_cache.items()
                    if (cutoff - v).total_seconds() < self._DEDUP_INTERVAL_SECS * 10
                }

        category = self._infer_category(activity_type)
        now = datetime.now(timezone.utc)

        # Audit fix: monotonic _id_counter guarantees uniqueness (collision with same-second + same-index is fixed)
        with self._lock:
            self._id_counter += 1
            activity_id = f"act_{now.strftime('%Y%m%d_%H%M%S')}_{self._id_counter:06d}"
        activity = {
            'id': activity_id,
            'timestamp': now.isoformat(),
            'type': activity_type,
            'type_label': ACTIVITY_TYPES.get(activity_type, _titleize_activity_type(activity_type)),
            'category': category,
            'message': msg,
            'session_id': session_id,
            'severity': severity,
            'details': details or {},
        }

        with self._lock:
            self._activities.append(activity)
        self._save_to_disk(activity)  # M-7 fix: pass activity for critical bypass

        # Also emit via WebSocket for real-time updates
        try:
            from .mmm_websocket import emit_activity
            emit_activity(activity)
        except ImportError:
            pass  # WebSocket not available
        except Exception as e:
            log.warning(f"Activity WS emit failed: {e}")  # M-23 fix

        return activity

    def get_recent(
        self,
        limit: int = 50,
        session_id: str = None,
        severity: str = None,
        category: str = None,
    ) -> List[Dict]:
        """
        Get recent activities, newest first.

        Args:
            limit: Max number to return
            session_id: Filter by session (optional)
            severity: Filter by severity (optional)
            category: Filter by category: orders|adjustments|safety|system (optional)

        Returns:
            List of activity dicts
        """
        result = self.query(
            limit=limit,
            session_id=session_id,
            severities=[severity] if severity else None,
            categories=[category] if category else None,
            order='desc',
        )
        return result.get('items', [])

    def query(
        self,
        limit: int = 50,
        session_id: str = None,
        severities: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        search: Optional[str] = None,
        cursor: Optional[str] = None,
        min_severity: Optional[str] = None,
        order: str = 'desc',
    ) -> Dict[str, Any]:
        """Advanced activity query with cursor pagination and full filters."""
        _limit = max(1, min(int(limit or 50), MAX_ACTIVITIES))
        with self._lock:
            items = list(self._activities)

        sev_set = {self._normalize_severity(s) for s in (severities or []) if s}
        cat_set = {str(c).strip().lower() for c in (categories or []) if c}
        type_set = {self._normalize_activity_type(t) for t in (types or []) if t}
        since_dt = _parse_iso_ts(since)
        until_dt = _parse_iso_ts(until)
        search_l = str(search or '').strip().lower()
        min_sev = self._normalize_severity(min_severity) if min_severity else None
        min_rank = SEVERITY_PRIORITY.get(min_sev, -1) if min_sev else -1

        filtered = []
        for a in items:
            if session_id and a.get('session_id') != session_id:
                continue

            a_type = self._normalize_activity_type(a.get('type', ''))
            if type_set and a_type not in type_set:
                continue

            a_cat = str(a.get('category', '')).strip().lower()
            if cat_set and a_cat not in cat_set:
                continue

            a_sev = self._normalize_severity(a.get('severity', ''))
            if sev_set and a_sev not in sev_set:
                continue
            if min_rank >= 0 and SEVERITY_PRIORITY.get(a_sev, 0) < min_rank:
                continue

            a_dt = _parse_iso_ts(a.get('timestamp'))
            if since_dt and (a_dt is None or a_dt < since_dt):
                continue
            if until_dt and (a_dt is None or a_dt > until_dt):
                continue

            if search_l:
                blob = ' '.join([
                    str(a.get('message', '')),
                    str(a.get('type', '')),
                    str(a.get('type_label', '')),
                    str(a.get('session_id', '')),
                ]).lower()
                if search_l not in blob:
                    continue

            filtered.append(a)

        reverse = str(order or 'desc').lower() != 'asc'
        filtered.sort(
            key=lambda a: (
                _parse_iso_ts(a.get('timestamp')) or datetime.fromtimestamp(0, tz=timezone.utc),
                str(a.get('id', '')),
            ),
            reverse=reverse,
        )

        start = 0
        if cursor:
            for idx, item in enumerate(filtered):
                if item.get('id') == cursor:
                    start = idx + 1
                    break

        page = filtered[start:start + _limit]
        has_more = (start + _limit) < len(filtered)
        next_cursor = page[-1].get('id') if has_more and page else None

        return {
            'items': page,
            'count': len(page),
            'total': len(filtered),
            'has_more': has_more,
            'next_cursor': next_cursor,
        }

    def get_stats(
        self,
        session_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate activity metrics for dashboards and diagnostics."""
        dataset = self.query(
            limit=MAX_ACTIVITIES,
            session_id=session_id,
            since=since,
            until=until,
            order='desc',
        ).get('items', [])

        by_severity = Counter(self._normalize_severity(a.get('severity')) for a in dataset)
        by_category = Counter(str(a.get('category', 'system')) for a in dataset)
        by_type = Counter(self._normalize_activity_type(a.get('type')) for a in dataset)
        by_session = Counter(str(a.get('session_id') or 'unknown') for a in dataset)

        ts_values = [_parse_iso_ts(a.get('timestamp')) for a in dataset]
        ts_values = [t for t in ts_values if t is not None]
        oldest_ts = min(ts_values).isoformat() if ts_values else None
        newest_ts = max(ts_values).isoformat() if ts_values else None

        return {
            'total': len(dataset),
            'critical_count': by_severity.get(SEVERITY_CRITICAL, 0),
            'error_count': by_severity.get(SEVERITY_ERROR, 0),
            'warning_count': by_severity.get(SEVERITY_WARNING, 0),
            'suppressed_dedup_count': self._suppressed_dedup_count,
            'by_severity': dict(by_severity),
            'by_category': dict(by_category),
            'top_types': by_type.most_common(15),
            'top_sessions': by_session.most_common(10),
            'oldest_timestamp': oldest_ts,
            'latest_timestamp': newest_ts,
        }

    def get_critical_feed(
        self,
        limit: int = 50,
        session_id: Optional[str] = None,
        since: Optional[str] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return warning/error/critical events prioritized for risk visibility."""
        return self.query(
            limit=limit,
            session_id=session_id,
            severities=[SEVERITY_WARNING, SEVERITY_ERROR, SEVERITY_CRITICAL],
            since=since,
            cursor=cursor,
            order='desc',
        )

    def clear(self, session_id: str = None):
        """Clear activities, optionally for a specific session only."""
        with self._lock:  # M-22 fix: atomic clear under lock
            if session_id:
                to_keep = [a for a in self._activities if a.get('session_id') != session_id]
                self._activities.clear()
                for a in to_keep:
                    self._activities.append(a)
                # Purge dedup cache for this session so post-clear events aren't suppressed
                # (k = (type, session_id, message_prefix) — index 1 is session_id)
                self._dedup_cache = {
                    k: v for k, v in self._dedup_cache.items() if k[1] != session_id
                }
            else:
                self._activities.clear()
                self._dedup_cache.clear()
        self._save_to_disk()

    def resolve_progress(self, session_id: str = None):
        """
        Remove all 'progress' severity activities for a session.
        Call this when entry completes or fails to clear stale 'fetching...' messages.
        """
        def should_keep(a):
            if a.get('severity') != 'progress':
                return True
            if session_id and a.get('session_id') != session_id:
                return True
            return False

        with self._lock:  # M-24 fix: atomic resolve under lock
            before = len(self._activities)
            to_keep = [a for a in self._activities if should_keep(a)]
            self._activities.clear()
            for a in to_keep:
                self._activities.append(a)
            removed = before - len(self._activities)
        if removed > 0:
            log.info(f"Resolved {removed} progress activities for session {session_id}")
            self._save_to_disk()
            # Emit refresh to frontend
            try:
                from .mmm_websocket import emit_activities_updated
                emit_activities_updated()
            except Exception:
                pass


# =============================================================================
# Singleton
# =============================================================================

_activity_instance = None
_activity_lock = threading.Lock()


def get_activity_log() -> MMMActivityLog:
    """Get singleton activity log instance."""
    global _activity_instance
    if _activity_instance is None:
        with _activity_lock:
            if _activity_instance is None:
                _activity_instance = MMMActivityLog()
    return _activity_instance


# =============================================================================
# Convenience helpers — call these from executor, monitor, api
# =============================================================================

def log_activity(
    activity_type: str,
    message: str,
    session_id: str = None,
    severity: str = SEVERITY_INFO,
    details: Dict = None,
) -> Dict:
    """Shortcut to add an activity to the global log."""
    return get_activity_log().add(
        activity_type=activity_type,
        message=message,
        session_id=session_id,
        severity=severity,
        details=details,
    )


def resolve_progress_activities(session_id: str = None):
    """Clear all 'progress' activities for a session (call when entry done)."""
    return get_activity_log().resolve_progress(session_id)
