"""
SmartWhipsawEngine — Phase 3 (shadow-only)

Implements 7 detectors, composite score, 4-mode state machine, adjustment token
budget, and multi-gate trigger evaluation. Runs in shadow mode until Phase 6
(operator promotion).

State key namespace: _smart_ws_*  (never writes _whipsaw_* keys)
Never reads _whipsaw_* state.

See WHIPSAW_INTELLIGENCE_UPGRADE.md for full specification.
"""

import math
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from webui.backend.routes.mmm.mmm_whipsaw_spot_log import (
    get_series,
    extract_spots,
    extract_premiums,
)
from webui.backend.routes.mmm.mmm_dte_presets import STRADDLE_WITH_ADJUSTMENT_CATEGORY
from webui.backend.routes.mmm.mmm_strategy_dispatch import resolve_strategy_type

log = logging.getLogger('mmm_whipsaw_smart')

# ---------------------------------------------------------------------------
# Composite score weights (§3.8) — module-level constants in Phase 3.
# Promoted to hot-reload params in Phase 5 after replay tuning.
# ---------------------------------------------------------------------------
_W_FLIP          = 0.30
_W_ER            = 0.20
_W_OSCILLATION   = 0.10
_W_SYMMETRY      = 0.10
_W_OUTCOME       = 0.15
_W_RVIV          = 0.10
_W_GAMMA         = 0.05


# ---------------------------------------------------------------------------
# TokenBudget
# ---------------------------------------------------------------------------

@dataclass
class TokenBudget:
    """Per-session adjustment token budget (§4.2 / §4.3)."""
    tokens_remaining: float
    tokens_per_session: float

    def spend(self, cost: float) -> bool:
        """Spend tokens; returns True if sufficient budget, False if not."""
        if self.tokens_remaining >= cost:
            self.tokens_remaining = round(self.tokens_remaining - cost, 6)
            return True
        return False

    def credit_patience(self, amount: float = 0.5) -> None:
        """Credit back partial token for a skipped adjustment (patience bonus)."""
        self.tokens_remaining = min(
            self.tokens_per_session,
            round(self.tokens_remaining + amount, 6),
        )

    def cost_for_mode(self, mode: str, is_flip: bool) -> float:
        """Token cost: 1 baseline, +1 if flip occurred, +0.5 in DEFENSIVE."""
        base = 1.0
        if is_flip:
            base += 1.0
        if mode == 'DEFENSIVE':
            base += 0.5
        return base


def _load_budget(
    session: dict,
    tokens_per_session: float,
    refresh_per_hour: float = 0.0,
    interval_mins: float = 5.0,
) -> TokenBudget:
    """Load token budget from session, initializing if absent.

    When refresh_per_hour > 0, drips tokens back each beat proportionally.
    This prevents late-session starvation in long ODTE sessions.
    """
    remaining = session.get('_smart_ws_tokens', None)
    if remaining is None:
        remaining = tokens_per_session
    else:
        remaining = float(remaining)
        if refresh_per_hour > 0.0 and remaining < tokens_per_session:
            drip = (interval_mins / 60.0) * refresh_per_hour
            remaining = min(tokens_per_session, remaining + drip)
    return TokenBudget(tokens_remaining=remaining, tokens_per_session=tokens_per_session)


def _save_budget(session: dict, budget: TokenBudget) -> None:
    session['_smart_ws_tokens'] = budget.tokens_remaining


# ---------------------------------------------------------------------------
# §3.1 Aggressor-Flip Counter
# ---------------------------------------------------------------------------

def flip_counter_score(
    session: dict,
    window_mins: float = 30.0,
    now: Optional[datetime] = None,
) -> float:
    """
    Score [0,1]: how many aggressor flips occurred in the rolling window,
    weighted by recency (exponential decay). §3.1

    3+ weighted flips → score near 1.0.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    history = session.get('adjustment_history', [])
    if len(history) < 2:
        return 0.0

    cutoff = now - timedelta(minutes=window_mins)
    half_life = window_mins / 3.0  # aggressive: 10 min half-life in 30-min window

    # Collect (timestamp, aggressor) pairs within window, newest first
    entries = []
    for h in reversed(history):
        try:
            ts = datetime.fromisoformat(h['timestamp'])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                break
            entries.append((ts, h.get('aggressor', '')))
        except (ValueError, KeyError, TypeError):
            continue

    if len(entries) < 2:
        return 0.0

    entries.reverse()  # oldest first for flip detection
    weighted_flips = 0.0
    for i in range(1, len(entries)):
        if entries[i][1] and entries[i - 1][1] and entries[i][1] != entries[i - 1][1]:
            age_mins = (now - entries[i][0]).total_seconds() / 60.0
            weight = math.exp(-age_mins / half_life)
            weighted_flips += weight

    # Normalise: 3 weighted flips = score 0.75; capped at 1.0
    return min(1.0, weighted_flips / 3.0)


# ---------------------------------------------------------------------------
# §3.2 Kaufman Efficiency Ratio
# ---------------------------------------------------------------------------

def efficiency_ratio_score(spots: List[float]) -> float:
    """
    Score [0,1]: 1 - ER. High ER (trend) → low score. Low ER (chop) → high score.
    Returns 0.5 when insufficient data. §3.2
    """
    if len(spots) < 2:
        return 0.5
    displacement = abs(spots[-1] - spots[0])
    path_length = sum(abs(spots[i] - spots[i - 1]) for i in range(1, len(spots)))
    if path_length == 0.0:
        return 0.0  # no movement → not ranging
    er = min(1.0, displacement / path_length)
    return round(1.0 - er, 6)


# ---------------------------------------------------------------------------
# §3.3 Spot Oscillation Amplitude
# ---------------------------------------------------------------------------

def oscillation_score(spots: List[float], sensitivity_pct: float = 0.15) -> float:
    """
    Score [0,1]: fraction of 6 local extrema detected in spot series.
    Each reversal must be >= sensitivity_pct% to count. §3.3
    """
    if len(spots) < 3:
        return 0.0
    extrema = 0
    for i in range(1, len(spots) - 1):
        move_before = spots[i] - spots[i - 1]
        move_after = spots[i + 1] - spots[i]
        if spots[i - 1] == 0:
            continue
        pct_change = abs(move_before) / spots[i - 1] * 100.0
        if pct_change < sensitivity_pct:
            continue
        if (move_before > 0 and move_after < 0) or (move_before < 0 and move_after > 0):
            extrema += 1
    return min(1.0, extrema / 6.0)


# ---------------------------------------------------------------------------
# §3.4 Premium Symmetry Oscillation
# ---------------------------------------------------------------------------

def premium_symmetry_score(ces: List[float], pes: List[float]) -> float:
    """
    Score [0,1]: fraction of 4 dominance sign-changes in the CE/PE ratio. §3.4
    dominance = (CE - PE) / (CE + PE).
    """
    if len(ces) < 2 or len(ces) != len(pes):
        return 0.0
    signs = []
    for ce, pe in zip(ces, pes):
        total = ce + pe
        if total == 0:
            continue
        dom = (ce - pe) / total
        if dom > 0:
            signs.append(1)
        elif dom < 0:
            signs.append(-1)
        # dom == 0: skip (neutral)
    sign_flips = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i - 1])
    return min(1.0, sign_flips / 4.0)


# ---------------------------------------------------------------------------
# §3.5 Adjustment Outcome Memory
# ---------------------------------------------------------------------------

def adjustment_outcome_score(session: dict, k: int = 3) -> float:
    """
    Score [0,1]: how much of the recent K adjustments show alternating aggressors
    (a proxy for whipsaw: each flip implies the previous adjustment was fighting
    against the new direction). §3.5
    """
    history = session.get('adjustment_history', [])
    if len(history) < 2:
        return 0.0
    recent = [h.get('aggressor', '') for h in history[-k:] if h.get('aggressor')]
    if len(recent) < 2:
        return 0.0
    flips = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i - 1])
    return min(1.0, flips / max(1, len(recent) - 1))


# ---------------------------------------------------------------------------
# §3.6 Realized vs Implied Vol Divergence
# ---------------------------------------------------------------------------

def rv_iv_divergence_score(
    spots: List[float],
    iv_now: float,
    interval_mins: float = 5.0,
    rv_iv_floor: float = 0.6,
) -> float:
    """
    Score [0,1]: low RV relative to IV suggests options are overpriced and
    triggers are noise-driven. §3.6

    rv/iv < floor → score proportional to shortfall.
    rv/iv >= 1    → score 0 (RV confirms IV, moves are real).
    iv_now == 0   → return 0 (neutral; can't compare).
    """
    if iv_now <= 0 or len(spots) < 2:
        return 0.0
    log_returns = [
        math.log(spots[i] / spots[i - 1])
        for i in range(1, len(spots))
        if spots[i - 1] > 0 and spots[i] > 0
    ]
    if len(log_returns) < 2:
        return 0.0
    mean_r = sum(log_returns) / len(log_returns)
    variance = sum((r - mean_r) ** 2 for r in log_returns) / (len(log_returns) - 1)
    std_r = math.sqrt(variance)
    # Annualise: periods per year = 365 * 1440 / interval_mins
    periods_per_year = 365.0 * 1440.0 / max(interval_mins, 1.0)
    rv_annual = std_r * math.sqrt(periods_per_year)
    ratio = rv_annual / iv_now
    if ratio >= 1.0:
        return 0.0
    # Below floor: rising divergence score
    score = max(0.0, 1.0 - ratio / rv_iv_floor)
    return min(1.0, round(score, 6))


# ---------------------------------------------------------------------------
# §3.7 Gamma Zone Score
# ---------------------------------------------------------------------------

def gamma_zone_score(
    session: dict,
    spot: float,
    osc_score: float,
    proximity_band_pct: float = 0.3,
) -> float:
    """
    Score [0,1]: weight oscillation by spot's proximity to the active strikes.
    Oscillation near the strike is more dangerous than oscillation far away. §3.7

    proximity_band_pct: within this % of strike → full proximity (1.0).
    """
    if spot <= 0:
        return osc_score * 0.5
    ce_data = session.get('ce', {})
    pe_data = session.get('pe', {})
    ce_strike = ce_data.get('strike') or session.get('_ce_strike')
    pe_strike = pe_data.get('strike') or session.get('_pe_strike')
    if not ce_strike and not pe_strike:
        return osc_score * 0.5  # strikes unknown → discount
    distances = []
    if ce_strike:
        distances.append(abs(spot - float(ce_strike)) / spot * 100.0)
    if pe_strike:
        distances.append(abs(spot - float(pe_strike)) / spot * 100.0)
    min_dist_pct = min(distances)
    proximity = max(0.0, 1.0 - min_dist_pct / max(proximity_band_pct, 0.001))
    return min(1.0, round(proximity * osc_score, 6))


# ---------------------------------------------------------------------------
# §3.8 Composite Score
# ---------------------------------------------------------------------------

def compute_composite(
    scores: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Weighted sum of detector scores → [0,1]. §3.8

    weights: optional override dict — any key missing falls back to module defaults.
    Late-session overrides come from evaluate() via Proposal 1.
    """
    w_flip = weights.get('flip',        _W_FLIP)        if weights else _W_FLIP
    w_er   = weights.get('er',          _W_ER)          if weights else _W_ER
    w_osc  = weights.get('oscillation', _W_OSCILLATION) if weights else _W_OSCILLATION
    w_sym  = weights.get('symmetry',    _W_SYMMETRY)    if weights else _W_SYMMETRY
    w_out  = weights.get('outcome',     _W_OUTCOME)     if weights else _W_OUTCOME
    w_rviv = weights.get('rviv',        _W_RVIV)        if weights else _W_RVIV
    w_gam  = weights.get('gamma',       _W_GAMMA)       if weights else _W_GAMMA
    return min(1.0, max(0.0, round(
        w_flip * scores.get('flip', 0.0)
        + w_er   * scores.get('er', 0.0)
        + w_osc  * scores.get('oscillation', 0.0)
        + w_sym  * scores.get('symmetry', 0.0)
        + w_out  * scores.get('outcome', 0.0)
        + w_rviv * scores.get('rviv', 0.0)
        + w_gam  * scores.get('gamma', 0.0),
        6,
    )))


# ---------------------------------------------------------------------------
# §4.1 Mode from composite score
# ---------------------------------------------------------------------------

def mode_from_score(
    score: float,
    defensive: float = 0.30,
    observe: float = 0.60,
    lockdown: float = 0.80,
    in_expiry_window: bool = False,
    minutes_to_expiry: Optional[float] = None,
) -> str:
    """Map composite score to 4-mode stance. §4.1 + §9.2 expiry tightening."""
    # §9.2: tighten thresholds near expiry
    if minutes_to_expiry is not None:
        if minutes_to_expiry <= 5:
            defensive = min(defensive, 0.20)
            observe   = min(observe,   0.40)
        elif minutes_to_expiry <= 30:
            defensive = min(defensive, 0.20)

    if score >= lockdown:
        return 'LOCKDOWN'
    if score >= observe:
        return 'OBSERVE'
    if score >= defensive:
        return 'DEFENSIVE'
    return 'NORMAL'


# ---------------------------------------------------------------------------
# §5 Multi-gate trigger evaluation
# ---------------------------------------------------------------------------

def _gate_spot_confirmation(series: list, ctx) -> bool:
    """Gate 2: spot moved meaningfully (rough ATR comparison)."""
    spots = extract_spots(series)
    if len(spots) < 3:
        return True  # insufficient data → give benefit of doubt
    step_changes = [abs(spots[i] - spots[i - 1]) for i in range(1, len(spots))]
    atr_est = (sum(step_changes) / len(step_changes)) * 1.5
    if atr_est == 0:
        return True
    displacement = abs(spots[-1] - spots[0])
    return displacement >= 0.5 * atr_est


def _gate_aggressor_persistence(session: dict, ctx) -> bool:
    """Gate 3: same aggressor for >= 2 consecutive adjustments."""
    history = session.get('adjustment_history', [])
    if len(history) < 2:
        return True  # no flip history → benefit of doubt
    recent = [h.get('aggressor', '') for h in history[-2:] if h.get('aggressor')]
    if len(recent) < 2:
        return True
    return recent[0] == recent[1]


def _gate_efficiency(series: list, er_threshold: float = 0.35) -> bool:
    """Gate 4: efficiency ratio >= threshold (not pure chop)."""
    spots = extract_spots(series)
    er_whipsaw = efficiency_ratio_score(spots)
    # er_whipsaw = 1 - ER, so ER = 1 - er_whipsaw
    er = 1.0 - er_whipsaw
    return er >= er_threshold


def _gate_vol_alignment(series: list, ctx, rv_iv_floor: float = 0.8) -> bool:
    """
    Gate 5: RV >= rv_iv_floor × IV, or spot broke recent range.
    Returns True when vol confirms the move is real.
    """
    spots = extract_spots(series)
    iv = getattr(ctx, 'iv', 0.0) or 0.0
    if iv > 0 and len(spots) >= 2:
        log_returns = [
            math.log(spots[i] / spots[i - 1])
            for i in range(1, len(spots))
            if spots[i - 1] > 0
        ]
        if len(log_returns) >= 2:
            mean_r = sum(log_returns) / len(log_returns)
            std_r = math.sqrt(
                sum((r - mean_r) ** 2 for r in log_returns) / (len(log_returns) - 1)
            )
            annualised = std_r * math.sqrt(365.0 * 1440.0 / 5.0)
            if annualised >= rv_iv_floor * iv:
                return True
    # Fallback: spot broke recent high/low by >= 0.1%
    if len(spots) >= 4:
        recent_high = max(spots[:-1])
        recent_low  = min(spots[:-1])
        spot_now = spots[-1]
        if spot_now > recent_high * 1.001 or spot_now < recent_low * 0.999:
            return True
    return False  # cannot confirm vol alignment → conservative


def multi_gate_decide(
    session: dict,
    ctx,
    series: list,
    mode: str,
    composite_score: float,
) -> Tuple[bool, float, float, list]:
    """
    Evaluate 5 gates and return (block, trigger_widen_factor, lot_scalar, events).

    Gate counts required:
      NORMAL    → 3 of 5
      DEFENSIVE → 4 of 5 (§5.4 / §10 step 7b)
      OBSERVE   → no new sells (block=True)
      LOCKDOWN  → block=True

    §5.4 asymmetric gate: if adding to thinner side, require +1 gate.
    §5.3 pressure-release override: if pressure indicators critical, bypass.
    """
    events = []
    params        = session.get('params', {})
    gate_normal   = int(params.get('smart_ws_gate_count_normal',    3))
    gate_def      = int(params.get('smart_ws_gate_count_defensive', 4))
    scalar_def    = float(params.get('smart_ws_size_scalar_defensive', 0.5))
    scalar_obs    = float(params.get('smart_ws_size_scalar_observe',   0.25))

    if mode == 'LOCKDOWN':
        events.append({
            'type': 'smart_whipsaw',
            'level': 'alert',
            'action': 'stop_adjustments',
            'message': f'Smart whipsaw LOCKDOWN (score {composite_score:.2f}): all adjustments blocked.',
            'source': 'SMART',
        })
        return True, 3.0, 0.0, events

    if mode == 'OBSERVE':
        events.append({
            'type': 'smart_whipsaw',
            'level': 'warning',
            'action': 'stop_adjustments',
            'message': f'Smart whipsaw OBSERVE (score {composite_score:.2f}): new sells paused, closes/harvests still allowed.',
            'source': 'SMART',
        })
        return True, 2.0, scalar_obs, events

    # Evaluate gates 1–5
    g1 = getattr(ctx, 'premium_trigger_fired', True)   # Gate 1: trigger fired
    g2 = _gate_spot_confirmation(series, ctx)           # Gate 2: spot moved
    g3 = _gate_aggressor_persistence(session, ctx)      # Gate 3: same aggressor
    g4 = _gate_efficiency(series)                       # Gate 4: ER >= 0.35
    g5 = _gate_vol_alignment(series, ctx)               # Gate 5: vol aligned
    gates_passed = sum([g1, g2, g3, g4, g5])

    # §5.4 asymmetric: adding to thinner side → +1 required
    required = gate_def if mode == 'DEFENSIVE' else gate_normal
    if _is_adding_to_thinner_side(session):
        required += 1
        required = min(required, 5)  # cap at 5

    block = gates_passed < required

    # Size scalars
    if mode == 'DEFENSIVE':
        trigger_widen = 1.5
        lot_scalar    = scalar_def
    else:  # NORMAL
        trigger_widen = 1.0
        lot_scalar    = 1.0

    if block:
        events.append({
            'type': 'smart_whipsaw',
            'level': 'info',
            'action': 'warn',
            'message': (
                f'Smart gate check: {gates_passed}/{5} gates passed '
                f'(required {required}) in {mode} mode. Adjustment suppressed.'
            ),
            'source': 'SMART',
            'details': {
                'gates': [g1, g2, g3, g4, g5],
                'passed': gates_passed,
                'required': required,
                'mode': mode,
            },
        })
    return block, trigger_widen, lot_scalar, events


def _is_adding_to_thinner_side(session: dict) -> bool:
    """True if the aggressor side has fewer active lots than the other side."""
    history = session.get('adjustment_history', [])
    if not history:
        return False
    last_aggressor = history[-1].get('aggressor', '') if history else ''
    if not last_aggressor:
        return False
    ce_lots = session.get('ce', {}).get('total_lots', 0)
    pe_lots = session.get('pe', {}).get('total_lots', 0)
    if last_aggressor == 'ce' and ce_lots < pe_lots:
        return True
    if last_aggressor == 'pe' and pe_lots < ce_lots:
        return True
    return False


# ---------------------------------------------------------------------------
# §8 Cooldown computation
# ---------------------------------------------------------------------------

def compute_cooldown_beats(flips_in_window: int, base_beats: int = 1) -> int:
    """Exponential cooldown: base * 2^flips. §8"""
    return max(base_beats, base_beats * (2 ** flips_in_window))


# ---------------------------------------------------------------------------
# SmartWhipsawEngine
# ---------------------------------------------------------------------------

class SmartWhipsawEngine:
    """
    Phase-3 smart whipsaw engine. Implements WHIPSAW_INTELLIGENCE_UPGRADE.md §10
    decision framework (9-step) in evaluate().

    State namespace: _smart_ws_*
    Never reads or writes _whipsaw_* keys.
    """
    name = 'SMART'

    def evaluate(self, session: dict, ctx) -> 'WhipsawDecision':  # forward ref
        from webui.backend.routes.mmm.mmm_whipsaw import WhipsawDecision

        params   = session.get('params', {})
        is_straddle_adj = resolve_strategy_type(session) == STRADDLE_WITH_ADJUSTMENT_CATEGORY

        # Load params
        defensive_thr = float(params.get('smart_ws_score_defensive', 0.30))
        observe_thr   = float(params.get('smart_ws_score_observe',   0.60))
        lockdown_thr  = float(params.get('smart_ws_score_lockdown',  0.80))
        tokens_init   = float(params.get('smart_ws_tokens_per_session', 10.0))
        flip_window   = float(params.get('smart_ws_flip_window_mins', 30.0))
        er_window     = float(params.get('smart_ws_er_window_mins',   30.0))
        osc_sens      = float(params.get('smart_ws_oscillation_sensitivity_pct', 0.15))
        rv_floor      = float(params.get('smart_ws_rv_iv_ratio_floor', 0.6))
        base_beats    = int(params.get('smart_ws_cooldown_base_beats', 1))
        relax_mins    = float(params.get('smart_ws_late_session_relax_mins', 180.0))
        refresh_rate  = float(params.get('smart_ws_token_refresh_per_hour', 1.0))
        interval_mins = float(params.get('adjustment_interval', 300)) / 60.0

        # ── [Proposal 3] §8 Cooldown enforcement — check before detectors ────
        _in_cooldown = False
        _now = datetime.now(timezone.utc)
        cooldown_until_str = session.get('_smart_ws_cooldown_until')
        if cooldown_until_str:
            try:
                cooldown_until_ts = datetime.fromisoformat(cooldown_until_str)
                if _now < cooldown_until_ts:
                    _in_cooldown = True
                else:
                    session.pop('_smart_ws_cooldown_until', None)
            except (ValueError, TypeError):
                session.pop('_smart_ws_cooldown_until', None)

        # ── Step 1: compute state ───────────────────────────────────────────
        series = get_series(session, window_mins=max(flip_window, er_window))
        spots  = extract_spots(series)
        ces, pes = extract_premiums(series)

        flip_sc  = flip_counter_score(session, window_mins=flip_window)
        er_sc    = efficiency_ratio_score(extract_spots(get_series(session, er_window)))
        osc_sc   = oscillation_score(spots, sensitivity_pct=osc_sens)
        sym_sc   = premium_symmetry_score(ces, pes)
        out_sc   = adjustment_outcome_score(session)
        rviv_sc  = rv_iv_divergence_score(
            spots, iv_now=getattr(ctx, 'iv', 0.0) or 0.0,
            rv_iv_floor=rv_floor,
        )
        gam_sc   = gamma_zone_score(session, spot=ctx.spot, osc_score=osc_sc)

        all_scores = {
            'flip': flip_sc, 'er': er_sc, 'oscillation': osc_sc,
            'symmetry': sym_sc, 'outcome': out_sc, 'rviv': rviv_sc,
            'gamma': gam_sc,
        }

        dte = session.get('_minutes_to_expiry')

        # ── [Proposal 1] Late-session weight adjustment ──────────────────────
        # In the last 3 hours (30 < DTE < relax_mins): flip/ER detectors are less
        # reliable (gamma-driven repositioning looks like whipsaw). Shift weight
        # toward gamma zone and adjustment outcome, which are more predictive.
        _late_session = dte is not None and 30.0 < dte <= relax_mins
        if _late_session:
            composite_weights = {
                'flip':        0.20,  # 0.30 → repositioning near expiry is real
                'er':          0.10,  # 0.20 → gamma chop is real, not noise
                'oscillation': 0.10,
                'symmetry':    0.10,
                'outcome':     0.25,  # 0.15 → adjustment history more predictive
                'rviv':        0.10,
                'gamma':       0.15,  # 0.05 → near-strike moves more significant
            }
        else:
            composite_weights = None  # use module-level defaults

        composite = compute_composite(all_scores, weights=composite_weights)

        mode = mode_from_score(
            composite,
            defensive=defensive_thr, observe=observe_thr, lockdown=lockdown_thr,
            minutes_to_expiry=dte,
        )

        # ── Step 2: pressure-release override (§5.3) ────────────────────────
        pressure_override = _check_pressure_override(session)
        if pressure_override:
            mode = 'NORMAL'
            log.debug('Smart: pressure-release override → forced NORMAL mode')

        # ── Step 4 / multi-gate ─────────────────────────────────────────────
        block, trigger_widen_factor, lot_scalar, events = multi_gate_decide(
            session, ctx, series, mode, composite,
        )
        # Track gate-count blocks for cooldown (OBSERVE/LOCKDOWN self-sustain; no extra cooldown needed)
        gate_count_blocked = block and mode in ('NORMAL', 'DEFENSIVE')

        # §5.4 flip penalty: reduce lot scalar for recent aggressor flip activity.
        # Only applied when not a straddle adj (straddle bypass resets lot_scalar=1.0 below).
        flip_count_approx = int(flip_sc * 3)
        flip_penalty_val  = float(params.get('smart_ws_flip_penalty', 0.5))
        if not is_straddle_adj and flip_count_approx > 0 and flip_sc > 0.1 and lot_scalar > 0:
            lot_scalar = max(0.1, lot_scalar * (flip_penalty_val ** flip_count_approx))

        # ── [Proposal 3] Enforce active cooldown (pressure override bypasses) ─
        if _in_cooldown and not pressure_override and not is_straddle_adj:
            if not block:
                block = True
                events.append({
                    'type': 'smart_whipsaw',
                    'level': 'info',
                    'action': 'warn',
                    'message': f'Smart whipsaw cooldown active (until {cooldown_until_str[:19]}Z). Adjustment suppressed.',
                    'source': 'SMART',
                })

        # STRADDLE_WITH_ADJUSTMENT bypass (§0 rule 6) — overrides all smart limits
        if is_straddle_adj:
            trigger_widen_factor = 1.0
            lot_scalar = 1.0
            block = False

        # ── Step 5: token budget ────────────────────────────────────────────
        budget = _load_budget(session, tokens_init, refresh_per_hour=refresh_rate, interval_mins=interval_mins)
        recent_is_flip = flip_sc > 0.05
        token_cost = budget.cost_for_mode(mode, is_flip=recent_is_flip)
        if is_straddle_adj:
            # STRADDLE bypass also skips token spend — token budget must not
            # override the §0 rule 6 invariant that gamma never blocks adjustment.
            # No spend, no credit — _load_budget already applied the beat drip.
            pass
        elif not block and not budget.spend(token_cost):
            block = True
            events.append({
                'type': 'smart_whipsaw',
                'level': 'info',
                'action': 'warn',
                'message': f'Smart token budget exhausted ({budget.tokens_remaining:.1f} remaining, needed {token_cost:.1f}).',
                'source': 'SMART',
            })
        elif block:
            budget.credit_patience()  # §4.3 patience bonus
        _save_budget(session, budget)

        # ── §8 Cooldown beats — now enforced, not just informational ─────────
        # flip_count_approx already computed above (flip penalty section)
        cooldown_beats = compute_cooldown_beats(flip_count_approx, base_beats)

        # ── [Proposal 3] Set cooldown expiry when gate-blocking fresh ─────────
        if gate_count_blocked and not is_straddle_adj and not _in_cooldown:
            cooldown_secs = cooldown_beats * (interval_mins * 60.0)
            _cooldown_until = _now + timedelta(seconds=cooldown_secs)
            session['_smart_ws_cooldown_until'] = _cooldown_until.isoformat()
            log.debug(
                f'Smart: cooldown set {cooldown_beats} beats ({cooldown_secs:.0f}s) '
                f'until {_cooldown_until.isoformat()[:19]}'
            )
        elif not block and not is_straddle_adj:
            # Adjustment genuinely allowed — clear any stale cooldown
            session.pop('_smart_ws_cooldown_until', None)

        # ── Write smart state ────────────────────────────────────────────────
        session['_smart_ws_score']  = composite
        session['_smart_ws_mode']   = mode
        session['_smart_ws_late_session'] = _late_session
        session['_smart_ws_last_flip_at'] = session.get('_smart_ws_last_flip_at', '')
        session['_smart_ws_flip_count_30m'] = flip_count_approx
        session['_smart_ws_last_decision'] = {
            'ts': _now.isoformat(),
            'score': composite,
            'mode': mode,
            'scores': all_scores,
            'gates_block': block,
            'trigger_widen_factor': trigger_widen_factor,
            'lot_scalar': lot_scalar,
            'cooldown_beats': cooldown_beats,
            'in_cooldown': _in_cooldown,
            'token_remaining': budget.tokens_remaining,
            'pressure_override': pressure_override,
            'late_session': _late_session,
            'weights': 'late_session' if _late_session else 'default',
        }

        return WhipsawDecision(
            engine='SMART',
            block_adjustment=block,
            trigger_widen_factor=trigger_widen_factor,
            lot_scalar=lot_scalar,
            score=composite,
            mode=mode,
            events=tuple(events),
            trace=dict(session['_smart_ws_last_decision']),
        )

    def reset_state(self, session: dict) -> None:
        for key in list(session.keys()):
            if key.startswith('_smart_ws_'):
                del session[key]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_pressure_override(session: dict) -> bool:
    """
    §5.3 pressure-release: bypass gates when critical indicators fire.
    Checks margin tier >= ORANGE or loss velocity > threshold.
    """
    # Margin tier check
    margin_tier = session.get('_margin_tier', '')
    if margin_tier in ('ORANGE', 'RED', 'CRITICAL'):
        return True
    # Loss velocity: if _loss_velocity_per_min set by monitor and exceeds threshold
    loss_vel = session.get('_smart_ws_loss_velocity', 0.0)
    if loss_vel and loss_vel > 50.0:  # $50/min for 3 beats = override
        return True
    return False
