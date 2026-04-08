"""
MMMX Whipsaw Guard — Oscillation Scoring and Deployment Throttling

Detects rapid shield-fire oscillations and progressively restricts deployment
to avoid wasting capital in noisy, non-directional markets.

Spec: MMMX_COMPLETE.md — Whipsaw Guard (Fourth Protection Layer).

Four levels:
  NORMAL   (0–1): No restrictions
  CAUTION  (2):   Deploy move threshold ×1.5 (2% → 3%)
  RESTRICT (3):   Move threshold ×2.0, tranche size halved (10 → 5 lots)
  COOLDOWN (4+):  All new deployments skipped for `whipsaw_cooldown_interval_hours`

Key invariants:
  - Whipsaw detection does NOT block ATM shield or hard stop (protection > offense).
  - Score increments via score_tick() (called after ATM shield phase each beat).
  - Score decays via decay_score() (called at start of deployment step each beat).
  - All timestamps: datetime.now(timezone.utc).isoformat() — never naive utcnow().
  - This module is side-effect free on session EXCEPT for updating whipsaw state fields.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

from .mmmx_constants import WhipsawLevel, WHIPSAW_CAUTION_SCORE, WHIPSAW_RESTRICT_SCORE, WHIPSAW_COOLDOWN_SCORE

log = logging.getLogger('mmmx_whipsaw')


# ── Public API ─────────────────────────────────────────────────────────────────

def get_level(score: int) -> str:
    """
    Map whipsaw score to level string.

    Returns: 'NORMAL' | 'CAUTION' | 'RESTRICT' | 'COOLDOWN'
    """
    if score >= WHIPSAW_COOLDOWN_SCORE:
        return WhipsawLevel.COOLDOWN
    elif score >= WHIPSAW_RESTRICT_SCORE:
        return WhipsawLevel.RESTRICT
    elif score >= WHIPSAW_CAUTION_SCORE:
        return WhipsawLevel.CAUTION
    return WhipsawLevel.NORMAL


def score_tick(
    session: Dict[str, Any],
    shield_events_since_last: Optional[list] = None,
) -> int:
    """
    Evaluate new shield events from the current beat for whipsaw signals.

    Detects two types of oscillation:
      1. Noise: spot moved < whipsaw_spot_move_pct% between consecutive shield fires
         within the whipsaw_window_mins rolling window.
      2. Direction flip: CE→PE or PE→CE alternation with < 1% spot move = oscillation.

    If shield_events_since_last is None, reads new events from
    session['shield_event_history'][session['_whipsaw_last_checked_idx']:].

    Mutates session: _whipsaw_score, _whipsaw_last_noise_at, _whipsaw_last_checked_idx,
                     _whipsaw_skip_until (set when COOLDOWN threshold first crossed).

    Returns: new _whipsaw_score
    """
    params = session.get('params', {})
    window_mins     = float(params.get('whipsaw_window_mins', 30))
    noise_threshold = float(params.get('whipsaw_spot_move_pct', 0.3))
    cooldown_score  = int(params.get('whipsaw_cooldown_score', WHIPSAW_COOLDOWN_SCORE))
    cooldown_hours  = float(params.get('whipsaw_cooldown_interval_hours', 1.0))

    all_history = session.get('shield_event_history', [])

    if shield_events_since_last is None:
        last_idx = session.get('_whipsaw_last_checked_idx', 0)
        shield_events_since_last = all_history[last_idx:]

    if not shield_events_since_last:
        return session.get('_whipsaw_score', 0)

    now = datetime.now(timezone.utc)
    score = int(session.get('_whipsaw_score', 0))
    old_level = get_level(score)
    session_id = session.get('session_id', '')

    for event in shield_events_since_last:
        fired_at_str = event.get('fired_at') or event.get('timestamp')
        if not fired_at_str:
            continue

        try:
            event_dt = datetime.fromisoformat(fired_at_str)
        except (ValueError, TypeError):
            continue

        # Only consider events within the rolling window
        elapsed_mins = (now - event_dt).total_seconds() / 60.0
        if elapsed_mins > window_mins:
            continue

        # Find previous event in history
        try:
            event_idx = next(
                i for i, e in enumerate(all_history)
                if e is event or (
                    e.get('fired_at') == event.get('fired_at')
                    and e.get('tranche_id') == event.get('tranche_id')
                    and e.get('side') == event.get('side')
                )
            )
        except StopIteration:
            event_idx = -1

        if event_idx <= 0:
            # No previous event to compare against — first shield fire
            continue

        prev_event = all_history[event_idx - 1]

        prev_spot = float(prev_event.get('spot') or 0.0)
        curr_spot = float(event.get('spot') or 0.0)

        incremented_for_noise = False

        if prev_spot > 0 and curr_spot > 0:
            spot_delta_pct = abs(curr_spot - prev_spot) / prev_spot * 100.0

            # Rule 1: Spot moved < noise_threshold → noise (not market confirmation)
            if spot_delta_pct < noise_threshold:
                score += 1
                session['_whipsaw_last_noise_at'] = now.isoformat()
                incremented_for_noise = True
                log.info(
                    f"[Whipsaw][{session_id[:8]}] Noise detected: "
                    f"spot delta {spot_delta_pct:.3f}% < {noise_threshold}%. "
                    f"Score → {score}"
                )

            # Rule 2: Direction flip with minimal spot move = oscillation
            if (
                not incremented_for_noise
                and prev_event.get('side') != event.get('side')
                and spot_delta_pct < 1.0
            ):
                score += 1
                session['_whipsaw_last_noise_at'] = now.isoformat()
                log.info(
                    f"[Whipsaw][{session_id[:8]}] Direction flip detected: "
                    f"{prev_event.get('side')} → {event.get('side')}, "
                    f"spot delta {spot_delta_pct:.3f}%. Score → {score}"
                )
        else:
            # No spot data in events — use direction-flip detection only
            if prev_event.get('side') != event.get('side'):
                score += 1
                session['_whipsaw_last_noise_at'] = now.isoformat()
                log.info(
                    f"[Whipsaw][{session_id[:8]}] Direction flip (no spot data): "
                    f"{prev_event.get('side')} → {event.get('side')}. Score → {score}"
                )

    session['_whipsaw_score'] = score
    session['_whipsaw_last_checked_idx'] = len(all_history)

    # Set cooldown skip-until if we just crossed the threshold
    if score >= cooldown_score and session.get('_whipsaw_skip_until') is None:
        skip_until = now + timedelta(hours=cooldown_hours)
        session['_whipsaw_skip_until'] = skip_until.isoformat()
        log.warning(
            f"[Whipsaw][{session_id[:8]}] COOLDOWN entered. "
            f"Deployments blocked until {skip_until.isoformat()}"
        )

    # Alert on level transitions
    new_level = get_level(score)
    if new_level != old_level:
        _alert_level_change(session_id, new_level, score)

    return score


def decay_score(session: Dict[str, Any]) -> int:
    """
    Decay whipsaw score each beat when market has been quiet.

    Normal decay (score 1–3): decrement by 1 if time since last noise > 1 hour.
    Cooldown expiry (score 4+): if _whipsaw_skip_until has passed, decrement by 2
      (4 → 2) and clear _whipsaw_skip_until.

    Returns: new _whipsaw_score
    """
    score = int(session.get('_whipsaw_score', 0))
    if score <= 0:
        return 0

    params = session.get('params', {})
    cooldown_score  = int(params.get('whipsaw_cooldown_score', WHIPSAW_COOLDOWN_SCORE))
    session_id = session.get('session_id', '')

    now = datetime.now(timezone.utc)
    old_level = get_level(score)

    # -- Cooldown expiry: -2 reward ─────────────────────────────────────────────
    if score >= cooldown_score:
        skip_until_str = session.get('_whipsaw_skip_until')
        if skip_until_str:
            try:
                skip_until_dt = datetime.fromisoformat(skip_until_str)
                if now >= skip_until_dt:
                    score = max(0, score - 2)
                    session['_whipsaw_score'] = score
                    session['_whipsaw_skip_until'] = None
                    log.info(
                        f"[Whipsaw][{session_id[:8]}] Cooldown expired. "
                        f"Score decayed -2 → {score}."
                    )
                    _alert_level_change(session_id, get_level(score), score)
                # else: cooldown still active, no decay
            except (ValueError, TypeError):
                pass
        return session.get('_whipsaw_score', score)

    # -- Normal decay: -1 per beat if > 1 hour quiet ────────────────────────────
    last_noise_str = session.get('_whipsaw_last_noise_at')
    if last_noise_str:
        try:
            last_noise_dt = datetime.fromisoformat(last_noise_str)
            elapsed_hours = (now - last_noise_dt).total_seconds() / 3600.0
            if elapsed_hours >= 1.0:
                score = max(0, score - 1)
                session['_whipsaw_score'] = score
                if score == 0:
                    session['_whipsaw_last_noise_at'] = None
                log.info(
                    f"[Whipsaw][{session_id[:8]}] Score decayed -1 → {score} "
                    f"(quiet for {elapsed_hours:.1f}h)."
                )
                new_level = get_level(score)
                if new_level != old_level:
                    _alert_level_change(session_id, new_level, score)
        except (ValueError, TypeError):
            pass

    return session.get('_whipsaw_score', score)


def apply_to_deployment(
    session: Dict[str, Any],
    base_move_pct: float,
    base_size: int,
) -> Tuple[Optional[float], Optional[int]]:
    """
    Apply whipsaw score to deployment thresholds.

    Returns:
        (adjusted_move_pct, adjusted_size) — or (None, None) if COOLDOWN.
        Caller must check for None to skip deployment entirely.

    Spec: MMMX_COMPLETE.md — Whipsaw Guard → Four-Level Graduated Response.
    """
    params = session.get('params', {})
    caution_score  = int(params.get('whipsaw_caution_score',  WHIPSAW_CAUTION_SCORE))
    restrict_score = int(params.get('whipsaw_restrict_score', WHIPSAW_RESTRICT_SCORE))
    cooldown_score = int(params.get('whipsaw_cooldown_score', WHIPSAW_COOLDOWN_SCORE))

    score = int(session.get('_whipsaw_score', 0))

    if score >= cooldown_score:
        return None, None   # COOLDOWN: skip all deployments
    elif score >= restrict_score:
        return round(base_move_pct * 2.0, 4), max(1, base_size // 2)
    elif score >= caution_score:
        return round(base_move_pct * 1.5, 4), base_size
    else:
        return base_move_pct, base_size


def in_cooldown(session: Dict[str, Any]) -> bool:
    """Return True if deployments are currently blocked by whipsaw COOLDOWN."""
    params = session.get('params', {})
    cooldown_score = int(params.get('whipsaw_cooldown_score', WHIPSAW_COOLDOWN_SCORE))
    score = int(session.get('_whipsaw_score', 0))
    if score < cooldown_score:
        return False
    # Score is COOLDOWN — check if skip_until is still in the future
    skip_until_str = session.get('_whipsaw_skip_until')
    if not skip_until_str:
        return True   # score is >=4 but no timestamp set — treat as active
    try:
        skip_until_dt = datetime.fromisoformat(skip_until_str)
        return datetime.now(timezone.utc) < skip_until_dt
    except (ValueError, TypeError):
        return True


# ── Private helpers ────────────────────────────────────────────────────────────

def _alert_level_change(session_id: str, new_level: str, score: int) -> None:
    try:
        from .mmmx_telegram import alert_whipsaw
        alert_whipsaw(session_id, new_level, score)
    except Exception as exc:
        log.debug(f"[Whipsaw] Telegram alert suppressed: {exc}")
