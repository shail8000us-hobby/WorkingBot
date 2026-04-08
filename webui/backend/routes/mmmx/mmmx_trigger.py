"""
MMMX Trigger — Priority-Ordered Trigger Evaluator

Pure function — no asyncio, no exchange calls, no I/O.
Evaluates protection triggers first, then deployment/drift triggers.
First match wins — no multiple triggers per beat.

Key function:
    evaluate(session, metrics) -> Optional[TriggerHit]

metrics dict populated by monitor before calling evaluate():
    {
        'portfolio_pnl':    float,
        'portfolio_delta':  float,
        'dte_days':         float,
        'iv_rank':          float | None,   # None if not yet fetched
        'lot_imbalance':    dict,            # from compute_lot_imbalance()
        'spot_price':       float | None,    # None if not yet fetched
    }

Priority table (first match wins — protection always beats deployment):
  1. DTE_CLOSE       — dte_days <= close_at_dte
  2. HARD_STOP       — portfolio_pnl <= -abs(hard_stop_usd)
  3. IV_CATASTROPHE  — iv_rank >= iv_catastrophe_pct
  4. NEAR_ITM        — any ACTIVE leg current_delta >= near_itm_delta
  5. PORTFOLIO_DELTA — abs(portfolio_delta) >= portfolio_delta_threshold
  6. DELTA_DRIFT     — any ACTIVE leg abs(current_delta - entry_delta) >= drift threshold
  7. IV_SPIKE        — iv_rank >= iv_spike_threshold_pct

Returns None if no trigger fires.
Returns None immediately if session status is not 'RUNNING'.

Isolation: ZERO imports from the MMM namespace — mmmx namespace only.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .mmmx_constants import TriggerName, TrncStatus

log = logging.getLogger('mmmx_trigger')

TRIGGER_PRIORITY: List[Tuple[str, str]] = [
    (TriggerName.DTE_CLOSE, 'critical'),
    (TriggerName.HARD_STOP, 'critical'),
    (TriggerName.IV_CATASTROPHE, 'critical'),
    (TriggerName.NEAR_ITM, 'critical'),
    (TriggerName.PORTFOLIO_DELTA, 'warning'),
    (TriggerName.DELTA_DRIFT, 'warning'),
    (TriggerName.IV_SPIKE, 'warning'),
]

TRIGGER_STATUS_FIRED = 'FIRED'
TRIGGER_STATUS_NOT_MET = 'NOT_MET'
TRIGGER_STATUS_SKIPPED = 'SKIPPED_AFTER_WINNER'
TRIGGER_STATUS_BLOCKED = 'BLOCKED'


def _derive_threshold_value(trigger_name: str, data: Dict[str, Any]) -> Tuple[Any, Any]:
    """Return (threshold, value) pair for UI ladder explainability."""
    if trigger_name == TriggerName.DTE_CLOSE:
        return data.get('close_at_dte'), data.get('dte_days')
    if trigger_name == TriggerName.HARD_STOP:
        hard = data.get('hard_stop_usd')
        return (-hard if hard is not None else None), data.get('portfolio_pnl')
    if trigger_name == TriggerName.IV_CATASTROPHE:
        return data.get('iv_catastrophe_pct'), data.get('iv_rank')
    if trigger_name == TriggerName.NEAR_ITM:
        return data.get('threshold'), data.get('delta', data.get('max_abs_delta'))
    if trigger_name == TriggerName.PORTFOLIO_DELTA:
        return data.get('threshold'), data.get('portfolio_delta')
    if trigger_name == TriggerName.DELTA_DRIFT:
        return data.get('threshold'), data.get('drift', data.get('max_drift'))
    if trigger_name == TriggerName.IV_SPIKE:
        return data.get('iv_spike_threshold_pct'), data.get('iv_rank')
    return None, None


# ── TriggerHit ────────────────────────────────────────────────────────────────

@dataclass
class TriggerHit:
    """Returned by evaluate() when a trigger fires."""
    trigger_name: str           # TriggerName constant
    reason: str                 # Human-readable description
    severity: str               # 'critical' | 'warning' | 'info'
    data: Dict[str, Any] = field(default_factory=dict)


# ── Main evaluator ────────────────────────────────────────────────────────────

def evaluate(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Optional[TriggerHit]:
    """
    Evaluate all triggers in priority order.
    Returns the first TriggerHit, or None if nothing fires.
    Returns None immediately if session status is not RUNNING.
    """
    hit, _ = evaluate_with_ladder(session, metrics)
    return hit


def evaluate_with_ladder(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Tuple[Optional[TriggerHit], List[Dict[str, Any]]]:
    """
    Evaluate triggers and return both winner + full priority ladder explanation.

    Returns:
      (winner, rows)

      winner: TriggerHit | None
      rows: [
        {
          'priority': int,
          'trigger_name': str,
          'severity': str,
          'status': 'FIRED'|'NOT_MET'|'SKIPPED_AFTER_WINNER'|'BLOCKED',
          'reason': str,
          'data': dict,
        }
      ]
    """
    params = session.get('params', {})
    status = session.get('status')

    rows: List[Dict[str, Any]] = []
    winner: Optional[TriggerHit] = None

    if status != 'RUNNING':
        reason = f"Session status {status!r} is not RUNNING"
        for idx, (name, severity) in enumerate(TRIGGER_PRIORITY, start=1):
            rows.append({
                'priority': idx,
                'trigger_name': name,
                'severity': severity,
                'status': TRIGGER_STATUS_BLOCKED,
                'reason': reason,
                'data': {},
                'threshold': None,
                'value': None,
            })
        return None, rows

    checks = [
        _check_dte_close,
        _check_hard_stop,
        _check_iv_catastrophe,
        _check_near_itm,
        _check_portfolio_delta,
        _check_delta_drift,
        _check_iv_spike,
    ]

    for idx, (check_fn, (name, severity)) in enumerate(
        zip(checks, TRIGGER_PRIORITY), start=1
    ):
        matched, reason, data = check_fn(session, metrics, params)
        threshold, value = _derive_threshold_value(name, data)

        if winner is None:
            if matched:
                winner = TriggerHit(
                    trigger_name=name,
                    reason=reason,
                    severity=severity,
                    data=data,
                )
                row_status = TRIGGER_STATUS_FIRED
            else:
                row_status = TRIGGER_STATUS_NOT_MET
        else:
            row_status = TRIGGER_STATUS_SKIPPED
            would_status = TRIGGER_STATUS_FIRED if matched else TRIGGER_STATUS_NOT_MET
            reason = (
                f"Skipped because higher-priority trigger already fired: "
                f"{winner.trigger_name} (would be {would_status}: {reason})"
            )
            data = {
                **data,
                'would_status': would_status,
            }

        rows.append({
            'priority': idx,
            'trigger_name': name,
            'severity': severity,
            'status': row_status,
            'reason': reason,
            'data': data,
            'threshold': threshold,
            'value': value,
            'excluded_by': winner.trigger_name if row_status == TRIGGER_STATUS_SKIPPED and winner else None,
        })

    return winner, rows


# ── Private helpers ───────────────────────────────────────────────────────────

def _scan_near_itm(
    session: Dict[str, Any],
    near_itm_delta: float,
) -> Optional[Tuple[Any, str, float]]:
    """
    Scan all ACTIVE tranche legs for abs(current_delta) >= near_itm_delta.
    Returns (tranche_id, side, delta) for the first match, or None.
    Falls back to entry_delta if current_delta is absent.
    """
    for tranche in session.get('tranches', []):
        for side in ('ce', 'pe'):
            leg = tranche.get(side, {})
            if not leg or leg.get('status') != TrncStatus.ACTIVE:
                continue
            delta = leg.get('current_delta')
            if delta is None:
                delta = leg.get('entry_delta', 0.0)
            if abs(delta) >= near_itm_delta:
                return (tranche.get('tranche_id'), side, delta)
    return None


def _max_abs_leg_delta(session: Dict[str, Any]) -> float:
    """Return maximum abs(delta) over ACTIVE legs (current_delta fallback entry_delta)."""
    max_abs = 0.0
    for tranche in session.get('tranches', []):
        for side in ('ce', 'pe'):
            leg = tranche.get(side, {})
            if not leg or leg.get('status') != TrncStatus.ACTIVE:
                continue
            delta = leg.get('current_delta')
            if delta is None:
                delta = leg.get('entry_delta', 0.0)
            max_abs = max(max_abs, abs(float(delta)))
    return max_abs


def _scan_delta_drift(
    session: Dict[str, Any],
    delta_drift_threshold: float,
) -> Optional[Tuple[Any, str, float]]:
    """
    Scan all ACTIVE tranche legs for delta drift >= threshold.
    drift = abs(current_delta - entry_delta)
    Returns (tranche_id, side, drift) for the first match, or None.
    Skips legs where current_delta is missing.
    """
    for tranche in session.get('tranches', []):
        for side in ('ce', 'pe'):
            leg = tranche.get(side, {})
            if not leg or leg.get('status') != TrncStatus.ACTIVE:
                continue
            entry_delta = leg.get('entry_delta', 0.0)
            current_delta = leg.get('current_delta')
            if current_delta is None:
                continue
            drift = abs(current_delta - entry_delta)
            if drift >= delta_drift_threshold:
                return (tranche.get('tranche_id'), side, drift)
    return None


def _max_delta_drift(session: Dict[str, Any]) -> float:
    """Return maximum observed delta drift across ACTIVE legs."""
    max_drift = 0.0
    for tranche in session.get('tranches', []):
        for side in ('ce', 'pe'):
            leg = tranche.get(side, {})
            if not leg or leg.get('status') != TrncStatus.ACTIVE:
                continue
            entry_delta = leg.get('entry_delta', 0.0)
            current_delta = leg.get('current_delta')
            if current_delta is None:
                continue
            drift = abs(float(current_delta) - float(entry_delta))
            max_drift = max(max_drift, drift)
    return max_drift


def _check_dte_close(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    dte_days = float(metrics.get('dte_days', 0.0))
    close_at_dte = params.get('close_at_dte', 7)
    matched = dte_days <= close_at_dte
    if matched:
        reason = f"DTE {dte_days:.2f} days <= close_at_dte {close_at_dte}"
    else:
        reason = f"DTE {dte_days:.2f} days > close_at_dte {close_at_dte}"
    return matched, reason, {'dte_days': dte_days, 'close_at_dte': close_at_dte}


def _check_hard_stop(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    portfolio_pnl = float(metrics.get('portfolio_pnl', 0.0))
    hard_stop_usd = abs(float(session.get('hard_stop_usd', 0.0)))
    if hard_stop_usd <= 0:
        return False, 'Hard stop disabled (hard_stop_usd <= 0)', {
            'portfolio_pnl': portfolio_pnl,
            'hard_stop_usd': hard_stop_usd,
        }

    matched = portfolio_pnl <= -hard_stop_usd
    if matched:
        reason = (
            f"Portfolio PnL {portfolio_pnl:.2f} USD <= "
            f"hard stop -{hard_stop_usd:.2f} USD"
        )
    else:
        reason = (
            f"Portfolio PnL {portfolio_pnl:.2f} USD > "
            f"hard stop -{hard_stop_usd:.2f} USD"
        )
    return matched, reason, {
        'portfolio_pnl': portfolio_pnl,
        'hard_stop_usd': hard_stop_usd,
    }


def _check_iv_catastrophe(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    iv_rank = metrics.get('iv_rank')
    iv_catastrophe_pct = params.get('iv_catastrophe_pct', 80)
    if iv_rank is None:
        return False, 'IV rank unavailable', {
            'iv_rank': iv_rank,
            'iv_catastrophe_pct': iv_catastrophe_pct,
        }

    iv_rank_f = float(iv_rank)
    matched = iv_rank_f >= iv_catastrophe_pct
    if matched:
        reason = (
            f"IV rank {iv_rank_f:.1f}% >= "
            f"catastrophe threshold {iv_catastrophe_pct}%"
        )
    else:
        reason = (
            f"IV rank {iv_rank_f:.1f}% < "
            f"catastrophe threshold {iv_catastrophe_pct}%"
        )
    return matched, reason, {
        'iv_rank': iv_rank_f,
        'iv_catastrophe_pct': iv_catastrophe_pct,
    }


def _check_near_itm(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    near_itm_delta = params.get('near_itm_delta', 0.55)
    near_itm_hit = _scan_near_itm(session, near_itm_delta)
    if near_itm_hit:
        tranche_id, side, delta = near_itm_hit
        return True, (
            f"Tranche {tranche_id}/{side} delta {delta:.3f} >= "
            f"near_itm threshold {near_itm_delta}"
        ), {
            'tranche_id': tranche_id,
            'side': side,
            'delta': delta,
            'threshold': near_itm_delta,
        }

    max_abs_delta = _max_abs_leg_delta(session)
    return False, (
        f"Max abs leg delta {max_abs_delta:.3f} < near_itm threshold {near_itm_delta}"
    ), {
        'max_abs_delta': max_abs_delta,
        'threshold': near_itm_delta,
    }


def _check_portfolio_delta(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    portfolio_delta = float(metrics.get('portfolio_delta', 0.0))
    portfolio_delta_threshold = params.get('portfolio_delta_threshold', 0.15)
    matched = abs(portfolio_delta) >= portfolio_delta_threshold
    if matched:
        reason = (
            f"Portfolio delta {portfolio_delta:.4f} >= "
            f"threshold {portfolio_delta_threshold}"
        )
    else:
        reason = (
            f"Portfolio delta {portfolio_delta:.4f} < "
            f"threshold {portfolio_delta_threshold}"
        )
    return matched, reason, {
        'portfolio_delta': portfolio_delta,
        'threshold': portfolio_delta_threshold,
    }


def _check_delta_drift(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    delta_drift_threshold = params.get('delta_drift_threshold', 0.35)
    drift_hit = _scan_delta_drift(session, delta_drift_threshold)
    if drift_hit:
        tranche_id, side, drift = drift_hit
        return True, (
            f"Tranche {tranche_id}/{side} delta drift {drift:.3f} >= "
            f"threshold {delta_drift_threshold}"
        ), {
            'tranche_id': tranche_id,
            'side': side,
            'drift': drift,
            'threshold': delta_drift_threshold,
        }

    max_drift = _max_delta_drift(session)
    return False, (
        f"Max delta drift {max_drift:.3f} < threshold {delta_drift_threshold}"
    ), {
        'max_drift': max_drift,
        'threshold': delta_drift_threshold,
    }


def _check_iv_spike(
    session: Dict[str, Any],
    metrics: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    iv_rank = metrics.get('iv_rank')
    iv_spike_threshold_pct = params.get('iv_spike_threshold_pct', 50)
    if iv_rank is None:
        return False, 'IV rank unavailable', {
            'iv_rank': iv_rank,
            'iv_spike_threshold_pct': iv_spike_threshold_pct,
        }

    iv_rank_f = float(iv_rank)
    matched = iv_rank_f >= iv_spike_threshold_pct
    if matched:
        reason = (
            f"IV rank {iv_rank_f:.1f}% >= "
            f"spike threshold {iv_spike_threshold_pct}%"
        )
    else:
        reason = (
            f"IV rank {iv_rank_f:.1f}% < "
            f"spike threshold {iv_spike_threshold_pct}%"
        )
    return matched, reason, {
        'iv_rank': iv_rank_f,
        'iv_spike_threshold_pct': iv_spike_threshold_pct,
    }
