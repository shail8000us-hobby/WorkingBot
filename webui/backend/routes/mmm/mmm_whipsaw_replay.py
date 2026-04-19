"""
mmm_whipsaw_replay — deterministic replay harness (Phase 4).

Given a session snapshot (with _smart_ws_series + adjustment_history),
replays two engines beat-by-beat and returns a comparison report.

Usage:
    from webui.backend.routes.mmm.mmm_whipsaw_replay import replay_session
    report = replay_session(session_snapshot)
    # {
    #   'beats': [{'ts', 'spot', 'engine_a_mode', 'engine_a_block', ...}, ...],
    #   'summary': {'total_beats', 'disagree_count', 'disagree_pct', ...},
    # }
"""

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger('mmm_whipsaw_replay')


def _ts_to_utc(ts_str: str) -> Optional[datetime]:
    try:
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except (ValueError, TypeError):
        return None


def _sub_session(session: dict, series_up_to: list, beat_ts: Optional[datetime]) -> dict:
    """Build an isolated session copy for a single replay beat."""
    sub = deepcopy(session)
    sub['_smart_ws_series'] = list(series_up_to)
    # Trim adjustment_history to entries at or before this beat's timestamp
    if beat_ts is not None:
        adj_hist = session.get('adjustment_history', [])
        sub['adjustment_history'] = [
            h for h in adj_hist
            if _ts_before_or_equal(h.get('timestamp', ''), beat_ts)
        ]
    # Reset legacy whipsaw state for clean replay of each engine
    for k in ('_whipsaw_score', '_whipsaw_state', '_whipsaw_skip_until',
              '_whipsaw_last_checked_idx', '_whipsaw_last_noise_at'):
        sub.pop(k, None)
    # Reset smart state so each beat is computed fresh
    for k in list(sub.keys()):
        if k.startswith('_smart_ws_') and k != '_smart_ws_series':
            del sub[k]
    return sub


def _ts_before_or_equal(ts_str: str, cutoff: datetime) -> bool:
    ts = _ts_to_utc(ts_str)
    return ts is None or ts <= cutoff


def replay_session(
    session_snapshot: dict,
    engine_a: str = 'LEGACY',
    engine_b: str = 'SMART',
    param_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Replay engine_a vs engine_b beat-by-beat over _smart_ws_series.

    Deterministic: same snapshot + same overrides always produces same output.

    Returns:
        {
            'beats': list[dict],    # one entry per series sample
            'summary': dict,        # aggregate metrics
        }
    """
    # Deferred imports to avoid circular references at module load
    from webui.backend.routes.mmm.mmm_whipsaw import WhipsawCtx, WHIPSAW_ENGINE_DISPATCH

    series = session_snapshot.get('_smart_ws_series', [])
    if not series:
        return {'beats': [], 'summary': _empty_summary(engine_a, engine_b)}

    eng_a = WHIPSAW_ENGINE_DISPATCH.get(engine_a)
    eng_b = WHIPSAW_ENGINE_DISPATCH.get(engine_b)
    if eng_a is None or eng_b is None:
        unknown = engine_a if eng_a is None else engine_b
        return {
            'beats': [],
            'summary': _empty_summary(engine_a, engine_b),
            'error': f'Unknown engine: {unknown}',
        }

    beats: List[dict] = []
    for i, sample in enumerate(series):
        spot = float(sample.get('spot') or 0.0)
        ce   = float(sample.get('ce')   or 0.0)
        pe   = float(sample.get('pe')   or 0.0)
        iv   = float(sample.get('iv')   or 0.0)
        ts   = sample.get('ts', '')

        beat_ts = _ts_to_utc(ts)
        ctx = WhipsawCtx(ce_now=ce, pe_now=pe, spot=spot, iv=iv)

        sub_a = _sub_session(session_snapshot, series[:i + 1], beat_ts)
        sub_b = _sub_session(session_snapshot, series[:i + 1], beat_ts)

        if param_overrides:
            sub_a.setdefault('params', {}).update(param_overrides)
            sub_b.setdefault('params', {}).update(param_overrides)

        try:
            dec_a = eng_a.evaluate(sub_a, ctx)
        except Exception as exc:
            log.warning(f'Replay beat {i} engine_a ({engine_a}) error: {exc}')
            continue
        try:
            dec_b = eng_b.evaluate(sub_b, ctx)
        except Exception as exc:
            log.warning(f'Replay beat {i} engine_b ({engine_b}) error: {exc}')
            continue

        disagree = (
            dec_a.block_adjustment != dec_b.block_adjustment
            or dec_a.lot_scalar != dec_b.lot_scalar
        )
        beats.append({
            'ts': ts,
            'spot': spot,
            f'{engine_a.lower()}_mode': dec_a.mode,
            f'{engine_a.lower()}_block': dec_a.block_adjustment,
            f'{engine_a.lower()}_score': round(float(dec_a.score), 4),
            f'{engine_a.lower()}_lot_scalar': dec_a.lot_scalar,
            f'{engine_a.lower()}_widen': dec_a.trigger_widen_factor,
            f'{engine_b.lower()}_mode': dec_b.mode,
            f'{engine_b.lower()}_block': dec_b.block_adjustment,
            f'{engine_b.lower()}_score': round(float(dec_b.score), 4),
            f'{engine_b.lower()}_lot_scalar': dec_b.lot_scalar,
            f'{engine_b.lower()}_widen': dec_b.trigger_widen_factor,
            'disagree': disagree,
        })

    summary = _compute_summary(beats, engine_a, engine_b)
    return {'beats': beats, 'summary': summary}


def _empty_summary(engine_a: str = 'LEGACY', engine_b: str = 'SMART') -> dict:
    return {
        'total_beats': 0,
        'disagree_count': 0,
        'disagree_pct': 0.0,
        f'{engine_a.lower()}_block_count': 0,
        f'{engine_b.lower()}_block_count': 0,
        f'{engine_a.lower()}_only_block': 0,
        f'{engine_b.lower()}_only_block': 0,
    }


def _compute_summary(beats: list, engine_a: str, engine_b: str) -> dict:
    if not beats:
        return _empty_summary(engine_a, engine_b)
    total = len(beats)
    disagree_count = sum(1 for b in beats if b.get('disagree'))
    a_block = sum(1 for b in beats if b.get(f'{engine_a.lower()}_block'))
    b_block = sum(1 for b in beats if b.get(f'{engine_b.lower()}_block'))
    a_only  = sum(1 for b in beats if b.get(f'{engine_a.lower()}_block') and not b.get(f'{engine_b.lower()}_block'))
    b_only  = sum(1 for b in beats if b.get(f'{engine_b.lower()}_block') and not b.get(f'{engine_a.lower()}_block'))
    return {
        'total_beats': total,
        'disagree_count': disagree_count,
        'disagree_pct': round(disagree_count / total * 100, 1),
        f'{engine_a.lower()}_block_count': a_block,
        f'{engine_b.lower()}_block_count': b_block,
        f'{engine_a.lower()}_only_block': a_only,
        f'{engine_b.lower()}_only_block': b_only,
    }
