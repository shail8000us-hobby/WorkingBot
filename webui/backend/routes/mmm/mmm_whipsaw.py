"""
MMM Whipsaw Dispatcher — Phase 3 (Smart Engine Shadow)

Single entry point for all whipsaw decisions.

Default engine : LEGACY  (see DEFAULT_ENGINE)
Kill-switch    : MMM_WHIPSAW_FORCE_LEGACY=1 env var — overrides on every call.
State isolation: LEGACY writes _whipsaw_* keys; SMART writes _smart_ws_* keys.
Shadow mode    : non-active engine runs in observe-only mode; result stored in
                 _smart_ws_shadow_last but never returned as the primary decision.
"""

import os
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from webui.backend.routes.mmm.mmm_safety import MMMSafety
from webui.backend.routes.mmm.mmm_dte_presets import STRADDLE_WITH_ADJUSTMENT_CATEGORY
from webui.backend.routes.mmm.mmm_strategy_dispatch import resolve_strategy_type

log = logging.getLogger('mmm_whipsaw')


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WhipsawDecision:
    engine: str               # 'LEGACY' | 'SMART' | 'OFF'
    block_adjustment: bool    # equivalent to legacy stop_adjustments
    trigger_widen_factor: float  # 1.0 = no change; applied at monitor trigger eval
    lot_scalar: float         # 1.0 = no change; applied at monitor lot calculation
    score: float              # raw int for LEGACY; 0–1 float for SMART
    mode: str                 # LEGACY: NORMAL/CAUTION/RESTRICT/COOLDOWN
    events: tuple             # passthrough to websocket + audit (tuple for hashability)
    trace: dict               # structured debug; goes to _whipsaw_trace


@dataclass
class WhipsawCtx:
    """Per-beat context passed to engine.evaluate()."""
    ce_now: float = 0.0
    pe_now: float = 0.0
    spot: float = 0.0
    iv: float = 0.0
    heartbeat_ts: Any = None
    recent_fills: list = field(default_factory=list)
    # Phase 3 additions (defaults preserve backward compat with Phase 1/2 call sites)
    aggressor: str = ''                   # 'ce' | 'pe' | '' — which side triggered
    premium_trigger_fired: bool = False   # whether premium trigger fired this beat


# ---------------------------------------------------------------------------
# Engine implementations
# ---------------------------------------------------------------------------

class LegacyWhipsawEngine:
    """
    Wraps the existing MMMSafety.check_whipsaw() call.
    Translates its event list + session state into a WhipsawDecision.
    Does NOT change any legacy decision logic, state keys, or thresholds.
    """
    name = 'LEGACY'

    def __init__(self) -> None:
        self._safety = MMMSafety()

    def evaluate(self, session: dict, ctx: WhipsawCtx) -> WhipsawDecision:
        events = self._safety.check_whipsaw(session)

        score = session.get('_whipsaw_score', 0)
        params = session.get('params', {})
        caution = params.get('whipsaw_caution_score', 2)
        restrict = params.get('whipsaw_restrict_score', 3)
        cooldown = params.get('whipsaw_cooldown_score', 4)

        is_straddle_adj = resolve_strategy_type(session) == STRADDLE_WITH_ADJUSTMENT_CATEGORY

        # Trigger widen factor — mirrors mmm_monitor.py lines 3343-3348
        if score >= restrict:
            wf = 2.0
        elif score >= caution:
            wf = 1.5
        else:
            wf = 1.0
        trigger_widen_factor = 1.0 if is_straddle_adj else wf

        # Lot scalar — mirrors mmm_monitor.py lines 4922-4926
        # Caller still applies "lots > 1" guard before scaling.
        lot_scalar = 1.0
        if score >= restrict and not is_straddle_adj:
            lot_scalar = 0.5

        # Mode
        if score >= cooldown:
            mode = 'COOLDOWN'
        elif score >= restrict:
            mode = 'RESTRICT'
        elif score >= caution:
            mode = 'CAUTION'
        else:
            mode = 'NORMAL'

        block = any(e.get('action') == 'stop_adjustments' for e in events)

        return WhipsawDecision(
            engine='LEGACY',
            block_adjustment=block,
            trigger_widen_factor=trigger_widen_factor,
            lot_scalar=lot_scalar,
            score=float(score),
            mode=mode,
            events=tuple(events),
            trace={
                'score': score,
                'mode': mode,
                'is_straddle_adj': is_straddle_adj,
                'trigger_widen_factor': trigger_widen_factor,
                'lot_scalar': lot_scalar,
            },
        )

    def reset_state(self, session: dict) -> None:
        pass


class NullWhipsawEngine:
    """Returns a no-op decision — all scalars 1.0, no events, no state writes."""
    name = 'OFF'

    def evaluate(self, session: dict, ctx: WhipsawCtx) -> WhipsawDecision:
        return WhipsawDecision(
            engine='OFF',
            block_adjustment=False,
            trigger_widen_factor=1.0,
            lot_scalar=1.0,
            score=0.0,
            mode='NORMAL',
            events=(),
            trace={},
        )

    def reset_state(self, session: dict) -> None:
        pass


# ---------------------------------------------------------------------------
# Engine dispatch table
# ---------------------------------------------------------------------------

def _build_dispatch() -> Dict[str, Any]:
    from webui.backend.routes.mmm.mmm_whipsaw_smart import SmartWhipsawEngine
    return {
        'LEGACY': LegacyWhipsawEngine(),
        'SMART':  SmartWhipsawEngine(),
        'OFF':    NullWhipsawEngine(),
    }


WHIPSAW_ENGINE_DISPATCH: Dict[str, Any] = _build_dispatch()

DEFAULT_ENGINE = 'SMART'


# ---------------------------------------------------------------------------
# Engine selector
# ---------------------------------------------------------------------------

def select_engine(session: dict) -> Any:
    """Return the active engine instance for this heartbeat.

    Priority:
      1. MMM_WHIPSAW_FORCE_LEGACY env var (emergency kill-switch)
      2. session['params']['whipsaw_engine'] param  (SMART | LEGACY | OFF)
      3. DEFAULT_ENGINE fallback
    """
    if os.environ.get('MMM_WHIPSAW_FORCE_LEGACY') == '1':
        return WHIPSAW_ENGINE_DISPATCH['LEGACY']
    params = session.get('params', {})
    engine_name = params.get('whipsaw_engine', DEFAULT_ENGINE)
    return WHIPSAW_ENGINE_DISPATCH.get(engine_name, WHIPSAW_ENGINE_DISPATCH[DEFAULT_ENGINE])


# ---------------------------------------------------------------------------
# Dispatcher entry points
# ---------------------------------------------------------------------------

def whipsaw_decide(session: dict, ctx: WhipsawCtx) -> WhipsawDecision:
    """Run the active engine and return its WhipsawDecision.

    Also:
    - Appends a spot-log sample to _smart_ws_series (always, for Smart detectors).
    - Runs shadow engine if enabled, stores result in _smart_ws_shadow_last.
    """
    from webui.backend.routes.mmm.mmm_whipsaw_spot_log import append_sample
    # Always build the rolling spot log so Smart detectors have data when promoted.
    try:
        append_sample(session, spot=ctx.spot, ce=ctx.ce_now, pe=ctx.pe_now, iv=ctx.iv)
    except Exception as e:
        log.warning(f'spot-log append failed (non-fatal): {e}')

    engine = select_engine(session)
    decision = engine.evaluate(session, ctx)
    # Tell mmm_safety.run_all_checks() the dispatcher already handled whipsaw this beat.
    # Without this, safety always calls check_whipsaw() again — double-executing legacy logic
    # even when engine=OFF (NullEngine) or SMART. The flag is read at mmm_safety.py:68.
    session['_whipsaw_dispatcher_ran'] = True

    # Shadow mode: run the non-active engine for comparison, never return its decision.
    _maybe_run_shadow(session, ctx, engine, decision)

    return decision


def _maybe_run_shadow(
    session: dict,
    ctx: WhipsawCtx,
    primary_engine: Any,
    primary_decision: WhipsawDecision,
) -> None:
    """Run the non-active engine in observe-only mode and store its result.

    Two directions:
      A) LEGACY (or OFF) is primary → shadow-run Smart when whipsaw_engine_shadow=True.
         Stores _smart_ws_shadow_last.
      B) SMART is primary → shadow-run Legacy when whipsaw_engine_shadow=True.
         Stores _ws_legacy_shadow_last for compare-tab rollback reference.

    Single control: whipsaw_engine_shadow.  whipsaw_smart_enabled is deprecated and
    has no effect on shadow routing (see select_engine() docstring).

    Shadow engine always runs on deepcopy; state writes discarded.
    """
    params = session.get('params', {})
    shadow_enabled = params.get('whipsaw_engine_shadow', False)

    if primary_engine.name != 'SMART':
        # Case A: Legacy (or OFF) is primary → shadow-run Smart only when explicitly enabled
        if not shadow_enabled:
            return
        smart_engine = WHIPSAW_ENGINE_DISPATCH.get('SMART')
        if smart_engine is None:
            return
        try:
            shadow_session  = deepcopy(session)
            shadow_decision = smart_engine.evaluate(shadow_session, ctx)
            session['_smart_ws_shadow_last'] = {
                'ts': datetime.now(timezone.utc).isoformat(),
                'primary_engine': primary_engine.name,
                'primary_mode': primary_decision.mode,
                'primary_score': float(primary_decision.score),
                'shadow_engine': 'SMART',
                'shadow_mode': shadow_decision.mode,
                'shadow_score': float(shadow_decision.score),
                'shadow_block': shadow_decision.block_adjustment,
                'shadow_lot_scalar': shadow_decision.lot_scalar,
                'shadow_trigger_widen': shadow_decision.trigger_widen_factor,
                'disagree': (
                    primary_decision.block_adjustment != shadow_decision.block_adjustment
                    or primary_decision.lot_scalar != shadow_decision.lot_scalar
                ),
            }
            log.debug(
                f'Shadow SMART: score={shadow_decision.score:.3f} mode={shadow_decision.mode} '
                f'disagree={session["_smart_ws_shadow_last"]["disagree"]}'
            )
        except Exception as e:
            log.warning(f'Shadow engine error (non-fatal): {e}')

    else:
        # Case B: Smart is primary → shadow-run Legacy for rollback comparison
        if not shadow_enabled:
            return
        legacy_engine = WHIPSAW_ENGINE_DISPATCH.get('LEGACY')
        if legacy_engine is None:
            return
        try:
            shadow_session  = deepcopy(session)
            shadow_decision = legacy_engine.evaluate(shadow_session, ctx)
            session['_ws_legacy_shadow_last'] = {
                'ts': datetime.now(timezone.utc).isoformat(),
                'primary_engine': 'SMART',
                'primary_mode': primary_decision.mode,
                'primary_score': float(primary_decision.score),
                'shadow_engine': 'LEGACY',
                'shadow_mode': shadow_decision.mode,
                'shadow_score': float(shadow_decision.score),
                'shadow_block': shadow_decision.block_adjustment,
                'shadow_lot_scalar': shadow_decision.lot_scalar,
                'shadow_trigger_widen': shadow_decision.trigger_widen_factor,
                'disagree': (
                    primary_decision.block_adjustment != shadow_decision.block_adjustment
                    or primary_decision.lot_scalar != shadow_decision.lot_scalar
                ),
            }
            log.debug(
                f'Shadow LEGACY: score={shadow_decision.score:.0f} mode={shadow_decision.mode} '
                f'disagree={session["_ws_legacy_shadow_last"]["disagree"]}'
            )
        except Exception as e:
            log.warning(f'Shadow legacy engine error (non-fatal): {e}')


def get_whipsaw_decision(session: dict, ctx: WhipsawCtx) -> WhipsawDecision:
    """Per-beat cached accessor used by mmm_monitor.py.

    The MMMMonitor stores the result in self._beat_whipsaw_decision after the
    first call at Step 6 (trigger widening); subsequent call sites (Step 7,
    lot reduction) retrieve it via self._beat_whipsaw_decision directly.
    This function is the canonical call site — monitors must not call
    whipsaw_decide() directly.
    """
    return whipsaw_decide(session, ctx)
