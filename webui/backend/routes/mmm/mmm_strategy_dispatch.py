"""
MMM Strategy Dispatch

Central strategy routing for monitor Step 5.4 and strategy-level invariant checks.

This module keeps strategy branching in one place so runtime behavior and
validation rules remain explicit and auditable.
"""

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .mmm_dte_presets import (
    STRADDLE_ROLL_CATEGORY,
    STRADDLE_WITH_ADJUSTMENT_CATEGORY,
)
from .mmm_state import derive_strategy_type

log = logging.getLogger('mmm_strategy_dispatch')


DEFAULT_STRATEGY_TYPE = '0DTE'


RunStep54Fn = Callable[[Any, Dict[str, Any], str, Optional[float]], Awaitable[bool]]
ValidateSessionFn = Callable[[Dict[str, Any]], List[str]]


@dataclass(frozen=True)
class StrategyHandler:
    """Runtime + validation contract for one strategy."""

    strategy_type: str
    should_run_adjustment: bool
    # Wind-down (regime-triggered or time-based LIFO buyback) is designed for the
    # strangle: when premium collapses, it gracefully reduces exposure.
    # For straddle strategies both legs start ATM — wind-down would immediately
    # buy back the aggressor leg and break the straddle structure.
    should_run_wind_down: bool
    # ATM shield proactively closes the leg approaching ATM and re-sells further OTM.
    # For strangle this is a critical safety mechanism. For straddle strategies,
    # CE and PE are BOTH at the same ATM strike — the shield would fire immediately
    # on entry and continuously fight the strategy structure.
    should_run_atm_shield: bool
    run_step_5_4: RunStep54Fn
    validate_session: ValidateSessionFn


def resolve_strategy_type(session: Dict[str, Any]) -> str:
    """Resolve canonical strategy identity from session state."""
    if not isinstance(session, dict):
        return DEFAULT_STRATEGY_TYPE
    return session.get('strategy_type') or derive_strategy_type(session.get('params', {}))


def _normalize_strategy_type(value: Any) -> str:
    return derive_strategy_type({'strategy_type': value}, fallback=DEFAULT_STRATEGY_TYPE)


def _validate_true_straddle_shape(session: Dict[str, Any]) -> List[str]:
    """Validate CE/PE strike symmetry for straddle strategies."""
    errors: List[str] = []
    ce_state = session.get('ce', {}) or {}
    pe_state = session.get('pe', {}) or {}
    ce_strike = float(ce_state.get('active_strike', 0) or 0)
    pe_strike = float(pe_state.get('active_strike', 0) or 0)

    # Allow both-zero state for freshly created, not-yet-initialized sessions.
    if ce_strike <= 0 and pe_strike <= 0:
        return errors

    if ce_strike <= 0 or pe_strike <= 0:
        errors.append(
            'Straddle strategy requires both CE and PE active_strike to be initialized.'
        )
        return errors

    if abs(ce_strike - pe_strike) >= 1:
        errors.append(
            f'Straddle strategy requires equal CE/PE active strikes; got CE={int(ce_strike)}, PE={int(pe_strike)}.'
        )
    return errors


def _validate_default_strategy_session(_session: Dict[str, Any]) -> List[str]:
    return []


def _validate_straddle_with_adjustment_session(session: Dict[str, Any]) -> List[str]:
    errors = _validate_true_straddle_shape(session)
    params = session.get('params', {}) or {}

    # total_dte_hours is guaranteed by the preset builder at creation time and is
    # enforced by the explicit missing-param check in create_session_endpoint().
    # Only validate it here for sessions that have actually been entered (entry_time
    # present) so that the create-time call to validate_session_for_strategy does
    # not block creation for edge-case preset configurations.
    session_entered = bool(session.get('entry_time'))
    if session_entered:
        total_dte_hours = float(
            params.get('total_dte_hours')
            or params.get('session_window_hours')
            or 0.0
        )
        if total_dte_hours <= 0:
            errors.append(
                'STRADDLE_WITH_ADJUSTMENT requires positive total_dte_hours/session_window_hours.'
            )
    return errors


def _validate_straddle_roll_session(session: Dict[str, Any]) -> List[str]:
    errors = _validate_true_straddle_shape(session)

    # _preset_source is a legacy identity marker — not checked here because:
    # (a) this validator is only dispatched when strategy_type == STRADDLE_ROLL_CATEGORY,
    #     so identity is already confirmed by the dispatch layer, and
    # (b) checking _preset_source would fire spurious warnings for sessions created
    #     via the canonical strategy_type path without going through the preset builder.

    for side_key in ('ce', 'pe'):
        side_state = session.get(side_key, {}) or {}
        frozen_lots = int(side_state.get('frozen_total_lots', 0) or 0)
        if frozen_lots > 0:
            errors.append(
                f'STRADDLE_ROLL must not carry frozen lots; {side_key.upper()} has {frozen_lots}.'
            )
    return errors


async def _run_step_5_4_noop(
    _monitor,
    _session: Dict[str, Any],
    _sid: str,
    _minutes_to_expiry: Optional[float],
) -> bool:
    return False


async def _run_step_5_4_straddle_with_adjustment(
    monitor,
    session: Dict[str, Any],
    sid: str,
    minutes_to_expiry: Optional[float],
) -> bool:
    """
    Step 5.4 for STRADDLE_WITH_ADJUSTMENT.

    Returns True only when the roll actually fired.
    """
    if not (session.get('params', {}) or {}).get('straddle_roll_enabled', False):
        return False

    try:
        from .mmm_straddle_adjustment import execute_straddle_roll

        fired = await execute_straddle_roll(
            monitor,
            session,
            sid,
            minutes_to_expiry,
        )
        return bool(fired)
    except Exception as roll_err:
        log.error(f'[{sid}] Straddle Roll error: {roll_err}', exc_info=True)
        return False


async def _run_step_5_4_straddle_roll(
    monitor,
    session: Dict[str, Any],
    sid: str,
    minutes_to_expiry: Optional[float],
) -> bool:
    """
    Step 5.4 for STRADDLE_ROLL.

    Pure roll owns the decision tree, so trigger/adjustment path must always be
    skipped for this strategy (return True even if no roll fired).
    """
    try:
        from .mmm_straddle_roll_pure import execute_pure_straddle_roll
        await execute_pure_straddle_roll(
            monitor,
            session,
            sid,
            minutes_to_expiry,
        )
    except Exception as pure_roll_err:
        log.error(f'[{sid}] Pure Straddle Roll error: {pure_roll_err}', exc_info=True)

    return True


STRATEGY_DISPATCH: Dict[str, StrategyHandler] = {
    # Strangle strategies: full engine enabled, wind-down and ATM shield both active.
    '0DTE': StrategyHandler(
        strategy_type='0DTE',
        should_run_adjustment=True,
        should_run_wind_down=True,
        should_run_atm_shield=True,
        run_step_5_4=_run_step_5_4_noop,
        validate_session=_validate_default_strategy_session,
    ),
    '5DTE': StrategyHandler(
        strategy_type='5DTE',
        should_run_adjustment=True,
        should_run_wind_down=True,
        should_run_atm_shield=True,
        run_step_5_4=_run_step_5_4_noop,
        validate_session=_validate_default_strategy_session,
    ),
    'SHORT_WINDOW': StrategyHandler(
        strategy_type='SHORT_WINDOW',
        should_run_adjustment=True,
        should_run_wind_down=True,
        should_run_atm_shield=True,
        run_step_5_4=_run_step_5_4_noop,
        validate_session=_validate_default_strategy_session,
    ),
    # Straddle + Adjustment: adjustment engine enabled, but wind-down and ATM shield
    # must NOT run. Both legs start ATM — wind-down would buy back the aggressor leg
    # instead of running the standard hedge adjustment, and ATM shield would fire
    # immediately on entry since CE == PE == ATM strike.
    STRADDLE_WITH_ADJUSTMENT_CATEGORY: StrategyHandler(
        strategy_type=STRADDLE_WITH_ADJUSTMENT_CATEGORY,
        should_run_adjustment=True,
        should_run_wind_down=False,
        should_run_atm_shield=False,
        run_step_5_4=_run_step_5_4_straddle_with_adjustment,
        validate_session=_validate_straddle_with_adjustment_session,
    ),
    # Pure straddle roll: adjustment engine fully disabled, no wind-down or ATM shield.
    # Risk is managed exclusively via the 4-leg roll in Step 5.4.
    STRADDLE_ROLL_CATEGORY: StrategyHandler(
        strategy_type=STRADDLE_ROLL_CATEGORY,
        should_run_adjustment=False,
        should_run_wind_down=False,
        should_run_atm_shield=False,
        run_step_5_4=_run_step_5_4_straddle_roll,
        validate_session=_validate_straddle_roll_session,
    ),
}


def get_strategy_handler(strategy_type: Any) -> StrategyHandler:
    """Return strategy handler; defaults safely to 0DTE handler."""
    key = _normalize_strategy_type(strategy_type)
    return STRATEGY_DISPATCH.get(key, STRATEGY_DISPATCH[DEFAULT_STRATEGY_TYPE])


def validate_session_for_strategy(
    session: Dict[str, Any],
    strategy_type: Optional[str] = None,
) -> List[str]:
    """Run strategy invariant validator and return all violations."""
    resolved = strategy_type or resolve_strategy_type(session)
    handler = get_strategy_handler(resolved)
    try:
        return handler.validate_session(session)
    except Exception as validation_err:
        log.error(
            f"Strategy validator crashed for {handler.strategy_type}: {validation_err}",
            exc_info=True,
        )
        return [
            f'Strategy validator internal error for {handler.strategy_type}: {validation_err}'
        ]
