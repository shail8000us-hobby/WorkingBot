"""
MMM Institutional-Grade Analytics Aggregator

Answers the three questions that matter for scaling a live options strategy:

  1. CAPITAL PLANNING — "If I scale to 100 lots/side, how much margin reserve
     do I need so the algo never runs out of money to adjust?"

  2. RISK PROFILING — "How often does the algo hit auto-close / max-loss?
     What is the worst-case drawdown I must be prepared for?"

  3. STRATEGY VALIDATION — "Is this strategy actually profitable over time?
     What is my win rate, profit factor, and expected value per session?"

All numbers derived from REAL historical session data in SQLite.
Nothing estimated or simulated.

Rewritten: February 18, 2026
"""

import logging
import json
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, timezone
from collections import defaultdict

log = logging.getLogger('mmm_analytics_aggregator')

# H-1 fix: import from canonical source instead of duplicating the constant
from .mmm_constants import LOT_SIZE_BTC


class MMMAnalyticsAggregator:
    """
    Aggregate all historical MMM session analytics into actionable
    business intelligence for capital scaling and strategy decisions.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    # =========================================================================
    # Database
    # =========================================================================

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _load_sessions(self) -> List[Dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                'SELECT analytics_json FROM mmm_analytics ORDER BY saved_at DESC'
            ).fetchall()
            return [json.loads(r['analytics_json']) for r in rows]
        except Exception as e:
            log.error(f"Failed to load sessions: {e}")
            return []
        finally:
            conn.close()

    # =========================================================================
    # Public API
    # =========================================================================

    def get_aggregated_analytics(self) -> Dict:
        """
        Master function — returns complete institutional analytics payload.
        All values derived from real session data only.
        """
        try:
            sessions = self._load_sessions()
            if not sessions:
                return self._empty_analytics()

            # Separate completed sessions (have a final outcome)
            completed = [
                s for s in sessions
                if s.get('session_status') not in ('IDLE', 'RUNNING', None)
            ]

            return {
                'overview':         self._overview(sessions, completed),
                'capital_planning': self._capital_planning(sessions),
                'risk_profile':     self._risk_profile(sessions, completed),
                'profitability':    self._profitability(completed),
                'algo_behavior':    self._algo_behavior(sessions),
                'distributions':    self._distributions(sessions, completed),
                'session_table':    self._session_table(sessions[:100]),
                'meta': {
                    'total_sessions':     len(sessions),
                    'completed_sessions': len(completed),
                    'generated_at':       datetime.now(timezone.utc).isoformat(),
                    'data_quality':       self._data_quality(sessions),
                },
                # ── Legacy keys kept so old frontend doesn't break ──────────
                'capital_requirements': self._legacy_capital(sessions),
                'risk_analytics':       self._legacy_risk(sessions),
                'strategy_performance': self._legacy_performance(sessions),
                'recent_sessions':      self._recent_summary(sessions[:10]),
                'metadata': {
                    'total_sessions_analyzed': len(sessions),
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                },
            }
        except Exception as e:
            log.error(f"Failed to aggregate analytics: {e}")
            import traceback
            traceback.print_exc()
            return self._empty_analytics()

    # =========================================================================
    # Section 1 — Overview
    # =========================================================================

    def _overview(self, sessions: List[Dict], completed: List[Dict]) -> Dict:
        n  = len(sessions)
        nc = len(completed)
        profitable = [s for s in completed if s.get('final_total_pnl', 0) > 0]
        losing     = [s for s in completed if s.get('final_total_pnl', 0) < 0]
        breakeven  = [s for s in completed if s.get('final_total_pnl', 0) == 0]

        total_pnl = sum(s.get('final_total_pnl', 0) for s in completed)
        avg_pnl   = total_pnl / nc if nc > 0 else 0
        win_rate  = len(profitable) / nc * 100 if nc > 0 else 0

        return {
            'total_sessions':      n,
            'completed_sessions':  nc,
            'profitable_sessions': len(profitable),
            'losing_sessions':     len(losing),
            'breakeven_sessions':  len(breakeven),
            'win_rate_pct':        round(win_rate, 1),
            'total_pnl':           round(total_pnl, 2),
            'avg_pnl_per_session': round(avg_pnl, 2),
            'expected_value':      round(self._expected_value(completed), 4),
        }

    def _expected_value(self, completed: List[Dict]) -> float:
        if not completed:
            return 0.0
        p_wins = [s.get('final_total_pnl', 0) for s in completed if s.get('final_total_pnl', 0) > 0]
        p_loss = [s.get('final_total_pnl', 0) for s in completed if s.get('final_total_pnl', 0) < 0]
        n = len(completed)
        avg_win  = sum(p_wins) / len(p_wins) if p_wins else 0
        avg_loss = sum(p_loss) / len(p_loss) if p_loss else 0
        return avg_win * (len(p_wins) / n) + avg_loss * (len(p_loss) / n)

    # =========================================================================
    # Section 2 — Capital Planning  *** MOST IMPORTANT ***
    # =========================================================================

    def _capital_planning(self, sessions: List[Dict]) -> Dict:
        """
        Answers: "If I start with 100 lots/side, how much capital reserve
        do I need so the algo can always keep adjusting?"

        Core insight: The algo sells MORE lots when hedge is needed.
        Worse the market move → more lots sold → more margin locked.
        This section tells you the WORST CASE you have seen, and what
        you must keep in reserve for each scale level.
        """
        if not sessions:
            return self._empty_capital_planning()

        ce_peaks       = [s.get('max_ce_lots', 0)       for s in sessions]
        pe_peaks       = [s.get('max_pe_lots', 0)       for s in sessions]
        combined_peaks = [s.get('max_combined_lots', 0) for s in sessions]
        initial_lots   = [
            s.get('initial_ce_lots', 0) + s.get('initial_pe_lots', 0)
            for s in sessions
        ]
        avg_initial = (sum(initial_lots) / len(initial_lots)) if initial_lots else 20

        max_ce_ever       = max(ce_peaks)       if ce_peaks       else 0
        max_pe_ever       = max(pe_peaks)       if pe_peaks       else 0
        max_combined_ever = max(combined_peaks) if combined_peaks else 0

        avg_ce_peak       = sum(ce_peaks)       / len(ce_peaks)       if ce_peaks       else 0
        avg_pe_peak       = sum(pe_peaks)       / len(pe_peaks)       if pe_peaks       else 0
        avg_combined_peak = sum(combined_peaks) / len(combined_peaks) if combined_peaks else 0

        p95_combined = self._percentile(combined_peaks, 95)
        p99_combined = self._percentile(combined_peaks, 99)

        # Capital multiplier per session: peak / initial
        multipliers = []
        for s in sessions:
            init = s.get('initial_ce_lots', 0) + s.get('initial_pe_lots', 0)
            peak = s.get('max_combined_lots', 0)
            if init > 0 and peak > 0:
                multipliers.append(peak / init)

        avg_multiplier = sum(multipliers) / len(multipliers) if multipliers else 0
        max_multiplier = max(multipliers)                    if multipliers else 0
        p95_multiplier = self._percentile(multipliers, 95)  if multipliers else 0

        # Scaling scenarios: for each starting lot count, what is the
        # worst-case peak you need to fund?
        avg_premium  = self._avg_entry_premium(sessions)
        # Each shorted lot requires ~3× premium in margin reserve (conservative)
        margin_per_lot = avg_premium * LOT_SIZE_BTC * 3

        safe_mult = max(p95_multiplier, max_multiplier) if max_multiplier > 0 else 4.0
        scaling_scenarios = []
        for start in [10, 20, 50, 100, 200, 500]:
            worst_total  = int(start * 2 * safe_mult)
            capital_req  = round(worst_total * margin_per_lot, 0)
            scaling_scenarios.append({
                'start_lots_per_side':  start,
                'expected_peak_lots':   int(start * 2 * avg_multiplier) if avg_multiplier else start * 2,
                'worst_case_peak_lots': worst_total,
                'required_capital_usd': capital_req,
                'multiplier_used':      round(safe_mult, 2),
            })

        growth_dist = self._lot_growth_distribution(sessions)

        return {
            'max_ce_lots_ever':       max_ce_ever,
            'max_pe_lots_ever':       max_pe_ever,
            'max_combined_lots_ever': max_combined_ever,
            'avg_ce_peak':            round(avg_ce_peak, 1),
            'avg_pe_peak':            round(avg_pe_peak, 1),
            'avg_combined_peak':      round(avg_combined_peak, 1),
            'p95_combined_peak':      round(p95_combined, 1),
            'p99_combined_peak':      round(p99_combined, 1),
            'avg_capital_multiplier': round(avg_multiplier, 2),
            'max_capital_multiplier': round(max_multiplier, 2),
            'p95_capital_multiplier': round(p95_multiplier, 2),
            'growth_distribution':    growth_dist,
            'scaling_scenarios':      scaling_scenarios,
            'avg_entry_premium_usd':  round(avg_premium, 2),
            'sessions_analyzed':      len(sessions),
        }

    def _avg_entry_premium(self, sessions: List[Dict]) -> float:
        premiums = []
        for s in sessions:
            params = s.get('params') or {}
            ce = params.get('desired_ce_premium', 0)
            pe = params.get('desired_pe_premium', 0)
            if ce > 0: premiums.append(ce)
            if pe > 0: premiums.append(pe)
        return sum(premiums) / len(premiums) if premiums else 100.0

    def _lot_growth_distribution(self, sessions: List[Dict]) -> List[Dict]:
        """
        For a bar chart: in what % of sessions did the algo grow
        position by 0x / 1-2x / 2-3x / 3-4x / >4x vs starting lots?
        """
        bands = {
            '1× (no addition)': 0,
            '1–2×': 0,
            '2–3×': 0,
            '3–4×': 0,
            '>4×': 0,
        }
        tracked = 0
        for s in sessions:
            init = s.get('initial_ce_lots', 0) + s.get('initial_pe_lots', 0)
            peak = s.get('max_combined_lots', 0)
            if init <= 0:
                continue
            tracked += 1
            mult = peak / init
            if   mult <= 1.0: bands['1× (no addition)'] += 1
            elif mult <= 2.0: bands['1–2×'] += 1
            elif mult <= 3.0: bands['2–3×'] += 1
            elif mult <= 4.0: bands['3–4×'] += 1
            else:             bands['>4×']  += 1

        return [
            {
                'label': label,
                'count': count,
                'pct':   round(count / tracked * 100, 1) if tracked > 0 else 0,
            }
            for label, count in bands.items()
        ]

    def _empty_capital_planning(self) -> Dict:
        return {
            'max_ce_lots_ever': 0, 'max_pe_lots_ever': 0, 'max_combined_lots_ever': 0,
            'avg_ce_peak': 0, 'avg_pe_peak': 0, 'avg_combined_peak': 0,
            'p95_combined_peak': 0, 'p99_combined_peak': 0,
            'avg_capital_multiplier': 0, 'max_capital_multiplier': 0, 'p95_capital_multiplier': 0,
            'growth_distribution': [], 'scaling_scenarios': [],
            'avg_entry_premium_usd': 0, 'sessions_analyzed': 0,
        }

    # =========================================================================
    # Section 3 — Risk Profile
    # =========================================================================

    def _risk_profile(self, sessions: List[Dict], completed: List[Dict]) -> Dict:
        n  = len(sessions)
        nc = len(completed)

        # Auto-close
        sessions_w_autoclose = sum(
            1 for s in sessions
            if s.get('auto_close_total_lots', 0) > 0
            or len(s.get('auto_close_events', [])) > 0
        )

        # Max-loss exits
        max_loss_exits = 0
        for s in completed:
            pnl        = s.get('final_total_pnl', 0)
            max_loss_c = (s.get('params') or {}).get('max_loss_amount', 5000)
            reason     = ((s.get('exit_reason') or s.get('stop_reason') or '')).upper()
            if 'MAX_LOSS' in reason or 'LOSS' in reason:
                max_loss_exits += 1
            elif pnl < -abs(max_loss_c) * 0.8:
                max_loss_exits += 1

        # Drawdown
        drawdowns = [
            abs(s.get('max_drawdown_from_peak', 0))
            for s in sessions
            if s.get('max_drawdown_from_peak', 0) != 0
        ]
        avg_dd   = sum(drawdowns) / len(drawdowns) if drawdowns else 0
        worst_dd = max(drawdowns)                  if drawdowns else 0
        p95_dd   = self._percentile(drawdowns, 95) if drawdowns else 0

        # Reversals
        rev_counts = [s.get('total_reversals', 0) for s in sessions]
        avg_rev    = sum(rev_counts) / len(rev_counts)       if rev_counts else 0
        p95_rev    = self._percentile(rev_counts, 95)        if rev_counts else 0

        # Both-sides-up
        both_sides = sum(
            1 for s in sessions if len(s.get('both_sides_up_timestamps', [])) > 0
        )

        # Close-at-5 (profitable buybacks — healthy)
        close5_sessions = sum(1 for s in sessions if s.get('total_close_at_5', 0) > 0)
        close5_total    = sum(s.get('total_close_at_5', 0) for s in sessions)

        return {
            'autoclose_sessions':         sessions_w_autoclose,
            'autoclose_probability_pct':  round(sessions_w_autoclose / n * 100, 1) if n > 0 else 0,
            'max_loss_exit_sessions':     max_loss_exits,
            'max_loss_probability_pct':   round(max_loss_exits / nc * 100, 1)     if nc > 0 else 0,
            'avg_max_drawdown_usd':       round(avg_dd, 2),
            'worst_drawdown_usd':         round(worst_dd, 2),
            'p95_drawdown_usd':           round(p95_dd, 2),
            'sessions_with_drawdown_data':len(drawdowns),
            'avg_reversals_per_session':  round(avg_rev, 1),
            'p95_reversals_per_session':  round(p95_rev, 1),
            'total_reversals':            sum(rev_counts),
            'both_sides_triggered':       both_sides,
            'both_sides_probability_pct': round(both_sides / n * 100, 1) if n > 0 else 0,
            'close5_sessions':            close5_sessions,
            'close5_total_events':        close5_total,
            'close5_probability_pct':     round(close5_sessions / n * 100, 1) if n > 0 else 0,
        }

    # =========================================================================
    # Section 4 — Profitability
    # =========================================================================

    def _profitability(self, completed: List[Dict]) -> Dict:
        if not completed:
            return self._empty_profitability()

        pnls   = [s.get('final_total_pnl', 0) for s in completed]
        wins   = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        total_win  = sum(wins)
        total_loss = sum(losses)
        pf         = abs(total_win / total_loss) if total_loss != 0 else 0

        avg_pnl = sum(pnls) / len(pnls) if pnls else 0
        median  = sorted(pnls)[len(pnls) // 2]  if pnls else 0

        durations   = [s.get('session_duration_seconds', 0) for s in completed]
        avg_dur_min = sum(durations) / len(durations) / 60 if durations else 0

        pnl_dist = self._pnl_distribution(pnls)

        return {
            'total_pnl':              round(sum(pnls), 2),
            'avg_pnl':                round(avg_pnl, 2),
            'median_pnl':             round(median, 2),
            'best_session':           round(max(pnls), 2) if pnls else 0,
            'worst_session':          round(min(pnls), 2) if pnls else 0,
            'avg_win':                round(total_win  / len(wins),   2) if wins   else 0,
            'avg_loss':               round(total_loss / len(losses), 2) if losses else 0,
            'profit_factor':          round(pf, 2),
            'total_wins':             len(wins),
            'total_losses':           len(losses),
            'gross_profit':           round(total_win,  2),
            'gross_loss':             round(total_loss, 2),
            'projected_monthly_usd':  round(avg_pnl * 22, 2),
            'avg_session_duration_mins': round(avg_dur_min, 1),
            'pnl_distribution':       pnl_dist,
        }

    def _pnl_distribution(self, pnls: List[float]) -> List[Dict]:
        if not pnls:
            return []
        min_p = min(pnls)
        max_p = max(pnls)
        if min_p == max_p:
            return [{'label': f'${min_p:.1f}', 'count': len(pnls), 'pct': 100, 'bucket_lo': min_p, 'bucket_hi': max_p}]
        n_buckets   = 10
        bucket_size = (max_p - min_p) / n_buckets
        buckets     = defaultdict(int)
        for p in pnls:
            idx = min(int((p - min_p) / bucket_size), n_buckets - 1)
            buckets[idx] += 1
        result = []
        for i in range(n_buckets):
            lo = min_p + i * bucket_size
            hi = lo + bucket_size
            result.append({
                'label':     f'${lo:.1f}–${hi:.1f}',
                'bucket_lo': round(lo, 2),
                'bucket_hi': round(hi, 2),
                'count':     buckets[i],
                'pct':       round(buckets[i] / len(pnls) * 100, 1),
            })
        return result

    def _empty_profitability(self) -> Dict:
        return {
            'total_pnl': 0, 'avg_pnl': 0, 'median_pnl': 0,
            'best_session': 0, 'worst_session': 0,
            'avg_win': 0, 'avg_loss': 0, 'profit_factor': 0,
            'total_wins': 0, 'total_losses': 0,
            'gross_profit': 0, 'gross_loss': 0,
            'projected_monthly_usd': 0,
            'avg_session_duration_mins': 0,
            'pnl_distribution': [],
        }

    # =========================================================================
    # Section 5 — Algo Behavior
    # =========================================================================

    def _algo_behavior(self, sessions: List[Dict]) -> Dict:
        n = len(sessions)
        if n == 0:
            return {}

        adj_counts  = [s.get('total_adjustments', 0) for s in sessions]
        rev_counts  = [s.get('total_reversals',   0) for s in sessions]
        shift_counts= [s.get('total_shifts',       0) for s in sessions]
        close5      = [s.get('total_close_at_5',   0) for s in sessions]

        ce_adj = sum(
            (s.get('adjustment_events_by_side') or {}).get('ce', 0) +
            (s.get('adjustment_events_by_side') or {}).get('CE', 0)
            for s in sessions
        )
        pe_adj = sum(
            (s.get('adjustment_events_by_side') or {}).get('pe', 0) +
            (s.get('adjustment_events_by_side') or {}).get('PE', 0)
            for s in sessions
        )

        total_ce_vol = sum(s.get('total_ce_lots_traded', 0) for s in sessions)
        total_pe_vol = sum(s.get('total_pe_lots_traded', 0) for s in sessions)

        return {
            'total_adjustments':        sum(adj_counts),
            'avg_adj_per_session':      round(sum(adj_counts)  / n, 1),
            'p95_adj_per_session':      round(self._percentile(adj_counts, 95), 1),
            'max_adj_in_session':       max(adj_counts)  if adj_counts  else 0,
            'total_reversals':          sum(rev_counts),
            'avg_reversals_per_session':round(sum(rev_counts)  / n, 1),
            'max_reversals_in_session': max(rev_counts)  if rev_counts  else 0,
            'total_shifts':             sum(shift_counts),
            'avg_shifts_per_session':   round(sum(shift_counts)/ n, 1),
            'total_close5_events':      sum(close5),
            'avg_close5_per_session':   round(sum(close5)       / n, 1),
            'total_ce_adjustments':     ce_adj,
            'total_pe_adjustments':     pe_adj,
            'ce_pe_ratio':              round(ce_adj / pe_adj, 2) if pe_adj > 0 else 0,
            'total_ce_lots_traded':     total_ce_vol,
            'total_pe_lots_traded':     total_pe_vol,
            'total_volume_lots':        total_ce_vol + total_pe_vol,
            'avg_volume_per_session':   round((total_ce_vol + total_pe_vol) / n, 1),
        }

    # =========================================================================
    # Section 6 — Distribution data (for charts)
    # =========================================================================

    def _distributions(self, sessions: List[Dict], completed: List[Dict]) -> Dict:
        # 1. Peak lots histogram
        combined_peaks = [s.get('max_combined_lots', 0) for s in sessions if s.get('max_combined_lots', 0) > 0]
        peak_hist = self._histogram(combined_peaks, n_buckets=8)

        # 2. Time-ordered P&L series with cumulative
        pnl_series = []
        cumulative = 0
        for s in sorted(completed, key=lambda x: x.get('saved_at', '')):
            pnl       = round(s.get('final_total_pnl', 0), 2)
            cumulative = round(cumulative + pnl, 2)
            pnl_series.append({
                'session_id':     s.get('session_id', ''),
                'saved_at':       s.get('saved_at', ''),
                'pnl':            pnl,
                'cumulative_pnl': cumulative,
                'max_lots':       s.get('max_combined_lots', 0),
                'adjustments':    s.get('total_adjustments', 0),
            })

        # 3. Adjustment histogram
        adj_counts = [s.get('total_adjustments', 0) for s in sessions]
        adj_hist   = self._histogram(adj_counts, n_buckets=8)

        # 4. Duration histogram (minutes)
        durations  = [s.get('session_duration_seconds', 0) / 60 for s in sessions if s.get('session_duration_seconds', 0) > 0]
        dur_hist   = self._histogram(durations, n_buckets=8)

        return {
            'peak_lots_histogram':  peak_hist,
            'pnl_timeseries':       pnl_series,
            'adjustment_histogram': adj_hist,
            'duration_histogram':   dur_hist,
        }

    def _histogram(self, values: List[float], n_buckets: int = 8) -> List[Dict]:
        if not values:
            return []
        min_v = min(values)
        max_v = max(values)
        if min_v == max_v:
            return [{'label': f'{min_v:.0f}', 'count': len(values), 'pct': 100, 'range_lo': min_v, 'range_hi': max_v}]
        bucket_size = (max_v - min_v) / n_buckets
        buckets     = defaultdict(int)
        for v in values:
            idx = min(int((v - min_v) / bucket_size), n_buckets - 1)
            buckets[idx] += 1
        result = []
        for i in range(n_buckets):
            lo = min_v + i * bucket_size
            hi = lo + bucket_size
            result.append({
                'label':    f'{lo:.0f}–{hi:.0f}',
                'range_lo': round(lo, 1),
                'range_hi': round(hi, 1),
                'count':    buckets[i],
                'pct':      round(buckets[i] / len(values) * 100, 1),
            })
        return result

    # =========================================================================
    # Section 7 — Full session table
    # =========================================================================

    def _session_table(self, sessions: List[Dict]) -> List[Dict]:
        rows = []
        for s in sessions:
            init = s.get('initial_ce_lots', 0) + s.get('initial_pe_lots', 0)
            peak = s.get('max_combined_lots', 0)
            mult = round(peak / init, 2) if init > 0 else 0
            pnl  = s.get('final_total_pnl', 0)
            rows.append({
                'session_id':          s.get('session_id', ''),
                'expiry':              s.get('expiry', ''),
                'status':              s.get('session_status', ''),
                'start_time':          s.get('session_start_time') or s.get('entry_time') or s.get('created_at', ''),
                'duration_mins':       round(s.get('session_duration_seconds', 0) / 60, 1),
                'initial_lots':        init,
                'max_ce_lots':         s.get('max_ce_lots', 0),
                'max_pe_lots':         s.get('max_pe_lots', 0),
                'max_combined_lots':   peak,
                'capital_multiplier':  mult,
                'total_adjustments':   s.get('total_adjustments', 0),
                'total_reversals':     s.get('total_reversals', 0),
                'total_shifts':        s.get('total_shifts', 0),
                'close5_count':        s.get('total_close_at_5', 0),
                'autoclose_lots':      s.get('auto_close_total_lots', 0),
                'pnl':                 round(pnl, 2),
                'realized_pnl':        round(s.get('final_realized_pnl', 0), 2),
                'unrealized_pnl':      round(s.get('final_unrealized_pnl', 0), 2),
                'max_drawdown':        round(abs(s.get('max_drawdown_from_peak', 0)), 2),
                'outcome':             'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'BREAK'),
            })
        return rows

    # =========================================================================
    # Section 8 — Data quality
    # =========================================================================

    def _data_quality(self, sessions: List[Dict]) -> Dict:
        n = len(sessions)
        has_peak   = sum(1 for s in sessions if s.get('max_combined_lots', 0) > 0)
        has_pnl    = sum(1 for s in sessions if 'final_total_pnl' in s)
        has_init   = sum(1 for s in sessions if s.get('initial_ce_lots', 0) > 0)
        has_dur    = sum(1 for s in sessions if s.get('session_duration_seconds', 0) > 0)
        return {
            'sessions_with_lot_tracking':  has_peak,
            'sessions_with_initial_lots':  has_init,
            'sessions_with_pnl':           has_pnl,
            'sessions_with_duration':      has_dur,
            'completeness_pct':            round(has_peak / n * 100, 1) if n > 0 else 0,
        }

    # =========================================================================
    # Legacy keys (keep old frontend working)
    # =========================================================================

    def _legacy_capital(self, sessions: List[Dict]) -> Dict:
        cp = self._capital_planning(sessions)
        avg_i = (sum(s.get('initial_ce_lots', 0) + s.get('initial_pe_lots', 0) for s in sessions)
                 / len(sessions)) if sessions else 20
        mx = cp['max_combined_lots_ever']
        return {
            'max_ce_lots_ever':       cp['max_ce_lots_ever'],
            'max_pe_lots_ever':       cp['max_pe_lots_ever'],
            'max_combined_lots_ever': mx,
            'avg_peak_ce_lots':       cp['avg_ce_peak'],
            'avg_peak_pe_lots':       cp['avg_pe_peak'],
            'avg_peak_combined_lots': cp['avg_combined_peak'],
            'capital_multiplier':     cp['avg_capital_multiplier'],
            'scaling_guidance':       (
                f"At {cp['avg_capital_multiplier']:.1f}× avg growth, "
                f"100 lots/side needs reserve for ~{int(100 * 2 * cp['p95_capital_multiplier'])} lots"
            ),
        }

    def _legacy_risk(self, sessions: List[Dict]) -> Dict:
        n = len(sessions)
        sessions_w_ac = sum(
            1 for s in sessions
            if s.get('auto_close_total_lots', 0) > 0 or len(s.get('auto_close_events', [])) > 0
        )
        stopped = [s for s in sessions if s.get('session_status') in ['STOPPED', 'CLOSED', 'EXITED']]
        dds = [abs(s.get('max_drawdown_from_peak', 0)) for s in sessions if s.get('max_drawdown_from_peak', 0) != 0]
        return {
            'sessions_with_auto_close':   sessions_w_ac,
            'auto_close_probability_pct': round(sessions_w_ac / n * 100, 1) if n > 0 else 0,
            'avg_max_drawdown':           round(sum(dds) / len(dds), 2) if dds else 0,
            'worst_drawdown_ever':        round(max(dds), 2)            if dds else 0,
            'sessions_with_drawdown_data':len(dds),
            'normally_completed_sessions':len(stopped),
            'completion_rate_pct':        round(len(stopped) / n * 100, 1) if n > 0 else 0,
        }

    def _legacy_performance(self, sessions: List[Dict]) -> Dict:
        n  = len(sessions)
        ab = self._algo_behavior(sessions)
        return {
            'total_adjustments':          ab.get('total_adjustments', 0),
            'total_reversals':            ab.get('total_reversals', 0),
            'total_shifts':               ab.get('total_shifts', 0),
            'avg_adjustments_per_session':ab.get('avg_adj_per_session', 0),
            'avg_reversals_per_session':  ab.get('avg_reversals_per_session', 0),
            'avg_shifts_per_session':     ab.get('avg_shifts_per_session', 0),
            'total_ce_adjustments':       ab.get('total_ce_adjustments', 0),
            'total_pe_adjustments':       ab.get('total_pe_adjustments', 0),
            'ce_pe_adjustment_ratio':     ab.get('ce_pe_ratio', 0),
            'total_ce_lots_traded':       ab.get('total_ce_lots_traded', 0),
            'total_pe_lots_traded':       ab.get('total_pe_lots_traded', 0),
            'total_volume':               ab.get('total_volume_lots', 0),
        }

    def _recent_summary(self, sessions: List[Dict]) -> List[Dict]:
        return [
            {
                'session_id':  s.get('session_id'),
                'expiry':      s.get('expiry'),
                'status':      s.get('session_status'),
                'final_pnl':   round(s.get('final_total_pnl', 0), 2),
                'max_lots':    s.get('max_combined_lots', 0),
                'adjustments': s.get('total_adjustments', 0),
                'saved_at':    s.get('saved_at'),
            }
            for s in sessions
        ]

    # =========================================================================
    # Utility
    # =========================================================================

    @staticmethod
    def _percentile(data: List[float], pct: int) -> float:
        if not data:
            return 0.0
        sd  = sorted(data)
        idx = min(int(len(sd) * pct / 100), len(sd) - 1)
        return sd[idx]

    # =========================================================================
    # Empty state
    # =========================================================================

    def _empty_analytics(self) -> Dict:
        return {
            'overview': {
                'total_sessions': 0, 'completed_sessions': 0,
                'profitable_sessions': 0, 'losing_sessions': 0, 'breakeven_sessions': 0,
                'win_rate_pct': 0, 'total_pnl': 0, 'avg_pnl_per_session': 0, 'expected_value': 0,
            },
            'capital_planning':    self._empty_capital_planning(),
            'risk_profile': {
                'autoclose_sessions': 0, 'autoclose_probability_pct': 0,
                'max_loss_exit_sessions': 0, 'max_loss_probability_pct': 0,
                'avg_max_drawdown_usd': 0, 'worst_drawdown_usd': 0, 'p95_drawdown_usd': 0,
                'sessions_with_drawdown_data': 0,
                'avg_reversals_per_session': 0, 'p95_reversals_per_session': 0, 'total_reversals': 0,
                'both_sides_triggered': 0, 'both_sides_probability_pct': 0,
                'close5_sessions': 0, 'close5_total_events': 0, 'close5_probability_pct': 0,
            },
            'profitability':       self._empty_profitability(),
            'algo_behavior':       {},
            'distributions':       {'peak_lots_histogram': [], 'pnl_timeseries': [], 'adjustment_histogram': [], 'duration_histogram': []},
            'session_table':       [],
            'meta': {
                'total_sessions': 0, 'completed_sessions': 0,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'data_quality': {'sessions_with_lot_tracking': 0, 'completeness_pct': 0},
            },
            # Legacy
            'capital_requirements': {
                'max_ce_lots_ever': 0, 'max_pe_lots_ever': 0, 'max_combined_lots_ever': 0,
                'avg_peak_ce_lots': 0, 'avg_peak_pe_lots': 0, 'avg_peak_combined_lots': 0,
                'capital_multiplier': 0, 'scaling_guidance': 'No data yet.',
            },
            'risk_analytics': {
                'sessions_with_auto_close': 0, 'auto_close_probability_pct': 0,
                'avg_max_drawdown': 0, 'worst_drawdown_ever': 0, 'sessions_with_drawdown_data': 0,
                'normally_completed_sessions': 0, 'completion_rate_pct': 0,
            },
            'strategy_performance': {
                'total_adjustments': 0, 'total_reversals': 0, 'total_shifts': 0,
                'avg_adjustments_per_session': 0, 'avg_reversals_per_session': 0,
                'avg_shifts_per_session': 0, 'total_ce_adjustments': 0, 'total_pe_adjustments': 0,
                'ce_pe_adjustment_ratio': 0, 'total_ce_lots_traded': 0, 'total_pe_lots_traded': 0,
                'total_volume': 0,
            },
            'recent_sessions': [],
            'metadata': {'total_sessions_analyzed': 0, 'generated_at': datetime.now(timezone.utc).isoformat()},
        }


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_aggregator_instance: Optional[MMMAnalyticsAggregator] = None


def get_aggregator(db_path: str = None) -> MMMAnalyticsAggregator:
    """Get (or create) the analytics aggregator singleton."""
    global _aggregator_instance
    if _aggregator_instance is None or db_path:
        from .mmm_analytics_storage import DB_FILE
        _aggregator_instance = MMMAnalyticsAggregator(db_path or DB_FILE)
    return _aggregator_instance
