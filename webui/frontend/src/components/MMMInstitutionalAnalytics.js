import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Paper, Typography, Grid, Alert, Divider, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  CircularProgress, Tabs, Tab, Tooltip, LinearProgress,
} from '@mui/material';
import TrendingUpIcon    from '@mui/icons-material/TrendingUp';
import TrendingDownIcon  from '@mui/icons-material/TrendingDown';
import WarningAmberIcon  from '@mui/icons-material/WarningAmber';
import CheckCircleIcon   from '@mui/icons-material/CheckCircle';
import ShowChartIcon     from '@mui/icons-material/ShowChart';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import RefreshIcon       from '@mui/icons-material/Refresh';
import IconButton        from '@mui/material/IconButton';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip as RTooltip, LineChart, Line, ReferenceLine, Cell,
} from 'recharts';
import mmmService from './mmm/mmmService';

// ─── colour tokens ──────────────────────────────────────────────────────────
const C = {
  blue:   '#00d4ff',
  green:  '#4caf50',
  red:    '#f44336',
  orange: '#ff9800',
  yellow: '#ffd43b',
  purple: '#ab47bc',
  teal:   '#26c6da',
  bg:     '#1a1a1a',
  card:   '#222',
  grid:   '#333',
};

// ─── tiny helpers ───────────────────────────────────────────────────────────
const fmt  = (n, decimals = 2) => (n == null ? '—' : Number(n).toFixed(decimals));
const fmtD = (n) => `$${fmt(n)}`;
const pct  = (n) => `${fmt(n, 1)}%`;
const cls  = (v) => v > 0 ? C.green : v < 0 ? C.red : '#aaa';

// ─────────────────────────────────────────────────────────────────────────────
//  Main component
// ─────────────────────────────────────────────────────────────────────────────
const MMMInstitutionalAnalytics = () => {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [tab,     setTab]     = useState(0);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      const res = await mmmService.getAggregatedAnalytics();
      if (res.success) { setData(res.aggregated); setError(null); }
      else              setError('Backend returned error');
    } catch (e) {
      setError(e.message || 'Failed to fetch analytics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    const id = setInterval(fetch, 60_000);
    return () => clearInterval(id);
  }, [fetch]);

  if (loading) return (
    <Box display="flex" justifyContent="center" alignItems="center" minHeight="300px">
      <CircularProgress sx={{ color: C.blue }} />
    </Box>
  );

  if (error) return <Alert severity="error">{error}</Alert>;

  const meta = data?.meta || data?.metadata || {};
  const n    = meta.total_sessions || meta.total_sessions_analyzed || 0;

  if (!data || n === 0) return (
    <Alert severity="info" icon={<ShowChartIcon />} sx={{ mt: 2 }}>
      No historical session data yet. Complete a few sessions and come back —
      the analytics will tell you exactly how much capital you need to scale.
    </Alert>
  );

  const { overview, capital_planning, risk_profile, profitability,
          algo_behavior, distributions, session_table } = data;

  return (
    <Box sx={{ color: '#eee', pb: 4 }}>

      {/* ── Header ── */}
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, color: C.blue }}>
            <AccountBalanceIcon sx={{ mr: 1, verticalAlign: 'middle', fontSize: 22 }} />
            Institutional Analytics
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {n} sessions analysed · updated {new Date(meta.generated_at || Date.now()).toLocaleTimeString()}
          </Typography>
        </Box>
        <IconButton onClick={fetch} size="small" sx={{ color: C.blue }}>
          <RefreshIcon />
        </IconButton>
      </Box>

      {/* ── Top KPI strip ── */}
      <Grid container spacing={1.5} mb={2}>
        <Grid item xs={6} sm={3}>
          <KPICard label="Win Rate"
            value={pct(overview?.win_rate_pct)}
            sub={`${overview?.profitable_sessions ?? '—'} wins / ${overview?.losing_sessions ?? '—'} losses`}
            color={overview?.win_rate_pct >= 70 ? C.green : C.orange}
            icon={<CheckCircleIcon fontSize="small" />} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <KPICard label="Total P&L"
            value={fmtD(overview?.total_pnl)}
            sub={`avg ${fmtD(overview?.avg_pnl_per_session)} / session`}
            color={cls(overview?.total_pnl)}
            icon={overview?.total_pnl >= 0 ? <TrendingUpIcon fontSize="small" /> : <TrendingDownIcon fontSize="small" />} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <KPICard label="Expected Value"
            value={fmtD(overview?.expected_value)}
            sub="per session (EV)"
            color={cls(overview?.expected_value)}
            icon={<ShowChartIcon fontSize="small" />} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <KPICard label="Auto-Close Risk"
            value={pct(risk_profile?.autoclose_probability_pct)}
            sub={`${risk_profile?.autoclose_sessions ?? 0} / ${n} sessions`}
            color={risk_profile?.autoclose_probability_pct > 15 ? C.red : risk_profile?.autoclose_probability_pct > 5 ? C.orange : C.green}
            icon={<WarningAmberIcon fontSize="small" />} />
        </Grid>
      </Grid>

      {/* ── Section tabs ── */}
      <Tabs value={tab} onChange={(_, v) => setTab(v)}
        sx={{ mb: 2, borderBottom: `1px solid ${C.grid}`,
              '& .MuiTab-root': { color: '#aaa', textTransform: 'none', minWidth: 0, px: 2 },
              '& .Mui-selected': { color: C.blue } }}
        TabIndicatorProps={{ style: { backgroundColor: C.blue } }}>
        <Tab label="💰 Capital Planning" />
        <Tab label="⚠️ Risk Profile" />
        <Tab label="📊 Profitability" />
        <Tab label="⚙️ Algo Behaviour" />
        <Tab label="📋 Session Log" />
      </Tabs>

      {/* ══════════════════════════════════════════════════════════════════
          TAB 0 — CAPITAL PLANNING
      ══════════════════════════════════════════════════════════════════ */}
      {tab === 0 && <CapitalPlanningTab cp={capital_planning} distributions={distributions} />}

      {/* ══════════════════════════════════════════════════════════════════
          TAB 1 — RISK PROFILE
      ══════════════════════════════════════════════════════════════════ */}
      {tab === 1 && <RiskProfileTab rp={risk_profile} n={n} />}

      {/* ══════════════════════════════════════════════════════════════════
          TAB 2 — PROFITABILITY
      ══════════════════════════════════════════════════════════════════ */}
      {tab === 2 && <ProfitabilityTab pf={profitability} distributions={distributions} />}

      {/* ══════════════════════════════════════════════════════════════════
          TAB 3 — ALGO BEHAVIOUR
      ══════════════════════════════════════════════════════════════════ */}
      {tab === 3 && <AlgoBehaviourTab ab={algo_behavior} distributions={distributions} />}

      {/* ══════════════════════════════════════════════════════════════════
          TAB 4 — SESSION LOG
      ══════════════════════════════════════════════════════════════════ */}
      {tab === 4 && <SessionLogTab rows={session_table || []} />}

    </Box>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  TAB 0 — Capital Planning
// ─────────────────────────────────────────────────────────────────────────────
const CapitalPlanningTab = ({ cp, distributions }) => {
  if (!cp) return null;
  return (
    <Box>
      <SectionHeader
        title="Capital Requirements"
        desc="Every time the market moves against you, the algo sells MORE lots to hedge.
This section shows the MAXIMUM lots ever created in a single session — that is your true capital requirement at scale." />

      {/* Peak exposure numbers */}
      <Grid container spacing={2} mb={3}>
        <Grid item xs={12} sm={4}>
          <StatPanel accent={C.red} title="CE Peak (worst session)">
            <BigStat value={cp.max_ce_lots_ever} label="lots" />
            <Row label="Average peak" value={cp.avg_ce_peak} />
            <Row label="95th pct peak" value={cp.p95_combined_peak} />
          </StatPanel>
        </Grid>
        <Grid item xs={12} sm={4}>
          <StatPanel accent={C.blue} title="PE Peak (worst session)">
            <BigStat value={cp.max_pe_lots_ever} label="lots" />
            <Row label="Average peak" value={cp.avg_pe_peak} />
          </StatPanel>
        </Grid>
        <Grid item xs={12} sm={4}>
          <StatPanel accent={C.yellow} title="Combined Peak (worst session)">
            <BigStat value={cp.max_combined_lots_ever} label="total lots" />
            <Row label="Average peak"   value={cp.avg_combined_peak} />
            <Row label="P95 peak"       value={cp.p95_combined_peak} />
            <Row label="P99 peak"       value={cp.p99_combined_peak} />
          </StatPanel>
        </Grid>
      </Grid>

      {/* Capital multiplier */}
      <Paper sx={{ p: 2, mb: 3, bgcolor: C.card, border: `1px solid ${C.yellow}33` }}>
        <Typography variant="subtitle2" sx={{ color: C.yellow, mb: 1, fontWeight: 700 }}>
          Capital Multiplier — How Much Does Position Grow?
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Multiplier = peak total lots ÷ initial lots. If you start 10+10=20 lots and peak hits 80, multiplier = 4×.
          You need 4× the starting capital reserved.
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={4}>
            <Typography variant="h3" sx={{ color: C.green, fontWeight: 700 }}>{fmt(cp.avg_capital_multiplier ?? 0, 2)}×</Typography>
            <Typography variant="caption" color="text.secondary">Average multiplier</Typography>
          </Grid>
          <Grid item xs={4}>
            <Typography variant="h3" sx={{ color: C.orange, fontWeight: 700 }}>{fmt(cp.p95_capital_multiplier ?? 0, 2)}×</Typography>
            <Typography variant="caption" color="text.secondary">95th percentile (plan for this)</Typography>
          </Grid>
          <Grid item xs={4}>
            <Typography variant="h3" sx={{ color: C.red, fontWeight: 700 }}>{fmt(cp.max_capital_multiplier ?? 0, 2)}×</Typography>
            <Typography variant="caption" color="text.secondary">Worst case ever</Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Lot growth distribution chart */}
      {cp.growth_distribution?.length > 0 && (
        <Paper sx={{ p: 2, mb: 3, bgcolor: C.card }}>
          <Typography variant="subtitle2" sx={{ color: C.blue, mb: 1, fontWeight: 700 }}>
            How Often Does Position Size Grow? (All Sessions)
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={2}>
            "1× = no addition" means the algo never needed to hedge. ">4×" means extreme market movement.
          </Typography>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={cp.growth_distribution} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
              <XAxis dataKey="label" tick={{ fill: '#aaa', fontSize: 11 }} />
              <YAxis tick={{ fill: '#aaa', fontSize: 11 }} />
              <RTooltip contentStyle={{ background: C.bg, border: `1px solid ${C.grid}`, color: '#eee' }}
                formatter={(v, _, p) => [`${v} sessions (${p.payload.pct}%)`, 'Count']} />
              <Bar dataKey="count" radius={[4,4,0,0]}>
                {cp.growth_distribution.map((d, i) => (
                  <Cell key={i} fill={
                    d.label === '1× (no addition)' ? C.green :
                    d.label === '1–2×' ? C.teal :
                    d.label === '2–3×' ? C.orange :
                    d.label === '3–4×' ? '#ef6c00' : C.red
                  } />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Paper>
      )}

      {/* Scaling scenarios table */}
      {cp.scaling_scenarios?.length > 0 && (
        <Paper sx={{ p: 2, bgcolor: C.card }}>
          <Typography variant="subtitle2" sx={{ color: C.blue, mb: 0.5, fontWeight: 700 }}>
            Scaling Calculator — Capital Required by Starting Lot Size
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={2}>
            Based on worst-case multiplier observed ({fmt(cp.max_capital_multiplier ?? 0, 2)}×).
            "Required capital" = worst-case peak lots × 3× entry premium × 0.001 BTC/lot (conservative margin estimate).
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ '& th': { color: '#aaa', fontSize: 11, fontWeight: 700, borderBottom: `1px solid ${C.grid}` } }}>
                  <TableCell>Start Lots / Side</TableCell>
                  <TableCell align="right">Total Start</TableCell>
                  <TableCell align="right">Expected Peak</TableCell>
                  <TableCell align="right">Worst-Case Peak</TableCell>
                  <TableCell align="right">Min Capital Reserve</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {cp.scaling_scenarios.map((s, i) => (
                  <TableRow key={i} hover sx={{ '& td': { borderBottom: `1px solid ${C.grid}22`, py: 0.8 } }}>
                    <TableCell sx={{ fontWeight: 700, color: C.blue }}>{s.start_lots_per_side}</TableCell>
                    <TableCell align="right">{s.total_start_lots}</TableCell>
                    <TableCell align="right" sx={{ color: C.green }}>{s.expected_peak_lots}</TableCell>
                    <TableCell align="right" sx={{ color: C.red, fontWeight: 600 }}>{s.worst_case_peak_lots}</TableCell>
                    <TableCell align="right" sx={{ color: C.yellow, fontWeight: 700 }}>${s.required_capital_usd?.toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}
    </Box>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  TAB 1 — Risk Profile
// ─────────────────────────────────────────────────────────────────────────────
const RiskProfileTab = ({ rp, n }) => {
  if (!rp) return null;

  const RiskRow = ({ label, value, total, color, desc }) => (
    <Box mb={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
        <Box>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{label}</Typography>
          {desc && <Typography variant="caption" color="text.secondary">{desc}</Typography>}
        </Box>
        <Box textAlign="right">
          <Typography variant="h6" sx={{ color, fontWeight: 700 }}>{value}</Typography>
          {total != null && <Typography variant="caption" color="text.secondary">{total} / {n} sessions</Typography>}
        </Box>
      </Box>
      <LinearProgress variant="determinate"
        value={Math.min(parseFloat(value) || 0, 100)}
        sx={{ height: 6, borderRadius: 3, bgcolor: `${C.grid}`, '& .MuiLinearProgress-bar': { bgcolor: color } }} />
    </Box>
  );

  return (
    <Box>
      <SectionHeader
        title="Risk Profile"
        desc="Probability of each adverse event based on historical sessions. Use this to decide your risk tolerance before scaling." />

      <Grid container spacing={2}>
        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 2.5, bgcolor: C.card }}>
            <Typography variant="subtitle2" sx={{ color: C.orange, mb: 2, fontWeight: 700 }}>Event Probabilities</Typography>

            <RiskRow label="Auto-Close Triggered"
              value={pct(rp.autoclose_probability_pct)}
              total={rp.autoclose_sessions}
              color={rp.autoclose_probability_pct > 15 ? C.red : rp.autoclose_probability_pct > 5 ? C.orange : C.green}
              desc="Algo exits position because premium fell below threshold" />

            <RiskRow label="Max-Loss Exit"
              value={pct(rp.max_loss_probability_pct)}
              total={rp.max_loss_exit_sessions}
              color={rp.max_loss_probability_pct > 10 ? C.red : C.green}
              desc="Session terminated because P&L hit hard stop" />

            <RiskRow label="Both-Sides-Up Triggered"
              value={pct(rp.both_sides_probability_pct)}
              total={rp.both_sides_triggered}
              color={rp.both_sides_probability_pct > 30 ? C.orange : C.teal}
              desc="Market moved so much both CE and PE were deep ITM simultaneously" />

            <RiskRow label="Close-at-5 Triggered ✓"
              value={pct(rp.close5_probability_pct)}
              total={rp.close5_sessions}
              color={C.green}
              desc="Algo bought back cheap options (healthy — locking profit)" />
          </Paper>
        </Grid>

        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 2.5, bgcolor: C.card, height: '100%' }}>
            <Typography variant="subtitle2" sx={{ color: C.red, mb: 2, fontWeight: 700 }}>Drawdown Analysis</Typography>

            <Box mb={2}>
              <Typography variant="caption" color="text.secondary">Worst Drawdown Ever</Typography>
              <Typography variant="h4" sx={{ color: C.red, fontWeight: 700 }}>{fmtD(rp.worst_drawdown_usd)}</Typography>
            </Box>
            <Divider sx={{ borderColor: C.grid, mb: 2 }} />
            <Row label="Average max drawdown" value={fmtD(rp.avg_max_drawdown_usd)} />
            <Row label="95th pct drawdown"     value={fmtD(rp.p95_drawdown_usd)} />
            <Row label="Sessions with data"    value={rp.sessions_with_drawdown_data} />
            <Divider sx={{ borderColor: C.grid, my: 2 }} />
            <Typography variant="caption" color="text.secondary">Reversal Stats</Typography>
            <Row label="Avg reversals / session" value={rp.avg_reversals_per_session} />
            <Row label="P95 reversals / session" value={rp.p95_reversals_per_session} />
            <Row label="Total reversals         " value={rp.total_reversals} />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  TAB 2 — Profitability
// ─────────────────────────────────────────────────────────────────────────────
const ProfitabilityTab = ({ pf, distributions }) => {
  if (!pf) return null;

  const pnl_ts  = distributions?.pnl_timeseries  || [];
  const pnl_dist= pf.pnl_distribution            || [];

  return (
    <Box>
      <SectionHeader
        title="Profitability"
        desc="P&L distribution across all completed sessions. The cumulative P&L line tells you whether this strategy is truly working over time." />

      {/* Top stats */}
      <Grid container spacing={1.5} mb={3}>
        {[
          { label: 'Total P&L',    value: fmtD(pf.total_pnl),    color: cls(pf.total_pnl) },
          { label: 'Average',      value: fmtD(pf.avg_pnl),      color: cls(pf.avg_pnl) },
          { label: 'Median',       value: fmtD(pf.median_pnl),   color: cls(pf.median_pnl) },
          { label: 'Best Session', value: fmtD(pf.best_session),  color: C.green },
          { label: 'Worst Session',value: fmtD(pf.worst_session), color: C.red },
          { label: 'Avg Win',      value: fmtD(pf.avg_win),       color: C.green },
          { label: 'Avg Loss',     value: fmtD(pf.avg_loss),      color: C.red },
          { label: 'Profit Factor',value: fmt(pf.profit_factor),  color: pf.profit_factor >= 1.5 ? C.green : pf.profit_factor >= 1 ? C.orange : C.red },
        ].map(({ label, value, color }) => (
          <Grid item xs={6} sm={3} key={label}>
            <Paper sx={{ p: 1.5, bgcolor: C.card, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
              <Typography variant="h6" sx={{ color, fontWeight: 700 }}>{value}</Typography>
            </Paper>
          </Grid>
        ))}
      </Grid>

      {/* Projected monthly */}
      <Alert severity={pf.projected_monthly_usd >= 0 ? 'success' : 'warning'} sx={{ mb: 3 }}>
        <strong>Projected monthly income (22 trading days): {fmtD(pf.projected_monthly_usd)}</strong>
        &nbsp;— based on average P&L per session.&nbsp;
        Profit factor: <strong>{fmt(pf.profit_factor)}</strong> (above 1.5 = solid strategy).&nbsp;
        Avg session duration: <strong>{pf.avg_session_duration_mins} min</strong>.
      </Alert>

      {/* Cumulative P&L line chart */}
      {pnl_ts.length > 0 && (
        <Paper sx={{ p: 2, mb: 3, bgcolor: C.card }}>
          <Typography variant="subtitle2" sx={{ color: C.blue, mb: 1, fontWeight: 700 }}>
            Cumulative P&L Over All Sessions
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" mb={1.5}>
            An upward sloping line = strategy is working. Flat or downward = re-examine.
          </Typography>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={pnl_ts} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
              <XAxis dataKey="session_id" tick={false} />
              <YAxis tick={{ fill: '#aaa', fontSize: 11 }} tickFormatter={v => `$${v}`} />
              <RTooltip contentStyle={{ background: C.bg, border: `1px solid ${C.grid}`, color: '#eee' }}
                formatter={(v, name) => [`$${v.toFixed(2)}`, name === 'cumulative_pnl' ? 'Cumulative P&L' : 'Session P&L']}
                labelFormatter={l => l} />
              <ReferenceLine y={0} stroke={C.grid} strokeDasharray="4 4" />
              <Line type="monotone" dataKey="cumulative_pnl" stroke={C.green}  strokeWidth={2} dot={false} name="cumulative_pnl" />
              <Line type="monotone" dataKey="pnl"            stroke={C.blue}   strokeWidth={1} dot={{ r: 3, fill: C.blue }} name="pnl" opacity={0.5} />
            </LineChart>
          </ResponsiveContainer>
        </Paper>
      )}

      {/* P&L distribution histogram */}
      {pnl_dist.length > 0 && (
        <Paper sx={{ p: 2, bgcolor: C.card }}>
          <Typography variant="subtitle2" sx={{ color: C.blue, mb: 1, fontWeight: 700 }}>
            P&L Distribution (Frequency)
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" mb={1.5}>
            Bars to the right of $0 = profitable sessions. The taller the right side, the better.
          </Typography>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={pnl_dist} margin={{ top: 5, right: 10, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
              <XAxis dataKey="label" tick={{ fill: '#aaa', fontSize: 10, angle: -20, dy: 10 }} />
              <YAxis tick={{ fill: '#aaa', fontSize: 11 }} />
              <RTooltip contentStyle={{ background: C.bg, border: `1px solid ${C.grid}`, color: '#eee' }}
                formatter={(v, _, p) => [`${v} sessions (${p.payload.pct}%)`, 'Count']} />
              <Bar dataKey="count" radius={[4,4,0,0]}>
                {pnl_dist.map((d, i) => (
                  <Cell key={i} fill={d.bucket_lo >= 0 ? C.green : C.red} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Paper>
      )}
    </Box>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  TAB 3 — Algo Behaviour
// ─────────────────────────────────────────────────────────────────────────────
const AlgoBehaviourTab = ({ ab, distributions }) => {
  if (!ab) return null;
  const adj_hist = distributions?.adjustment_histogram || [];
  const dur_hist = distributions?.duration_histogram   || [];

  return (
    <Box>
      <SectionHeader
        title="Algo Behaviour"
        desc="How actively does the algorithm trade? Understand frequency of adjustments, reversals and shifts to gauge strategy activity." />

      <Grid container spacing={2} mb={3}>
        <Grid item xs={12} sm={6}>
          <StatPanel accent={C.blue} title="Adjustments (Hedging Events)">
            <Row label="Total adjustments"         value={ab.total_adjustments} />
            <Row label="Avg per session"            value={ab.avg_adj_per_session} />
            <Row label="95th pct per session"       value={ab.p95_adj_per_session} />
            <Row label="Max in single session"      value={ab.max_adj_in_session} />
            <Divider sx={{ borderColor: C.grid, my: 1 }} />
            <Row label="CE adjustments total"       value={ab.total_ce_adjustments} />
            <Row label="PE adjustments total"       value={ab.total_pe_adjustments} />
            <Row label="CE : PE ratio"              value={ab.ce_pe_ratio} />
          </StatPanel>
        </Grid>
        <Grid item xs={12} sm={6}>
          <StatPanel accent={C.purple} title="Reversals, Shifts & Buybacks">
            <Row label="Total reversals"            value={ab.total_reversals} />
            <Row label="Avg reversals / session"    value={ab.avg_reversals_per_session} />
            <Row label="Max reversals (1 session)"  value={ab.max_reversals_in_session} />
            <Divider sx={{ borderColor: C.grid, my: 1 }} />
            <Row label="Total strike shifts"        value={ab.total_shifts} />
            <Row label="Avg shifts / session"       value={ab.avg_shifts_per_session} />
            <Divider sx={{ borderColor: C.grid, my: 1 }} />
            <Row label="Close-at-5 events total"    value={ab.total_close5_events} />
            <Row label="Avg close-at-5 / session"   value={ab.avg_close5_per_session} />
          </StatPanel>
        </Grid>
      </Grid>

      {/* Volume */}
      <Paper sx={{ p: 2, mb: 3, bgcolor: C.card }}>
        <Typography variant="subtitle2" sx={{ color: C.teal, mb: 1, fontWeight: 700 }}>Trading Volume</Typography>
        <Grid container spacing={2}>
          <Grid item xs={4}><BigStat value={ab.total_ce_lots_traded} label="CE lots sold total" /></Grid>
          <Grid item xs={4}><BigStat value={ab.total_pe_lots_traded} label="PE lots sold total" /></Grid>
          <Grid item xs={4}><BigStat value={ab.total_volume_lots}    label="combined lots total" /></Grid>
        </Grid>
        <Typography variant="caption" color="text.secondary" display="block" mt={1}>
          Avg {ab.avg_volume_per_session} lots traded per session
        </Typography>
      </Paper>

      {/* Adjustment frequency histogram */}
      {adj_hist.length > 0 && (
        <Paper sx={{ p: 2, mb: 2, bgcolor: C.card }}>
          <Typography variant="subtitle2" sx={{ color: C.blue, mb: 1, fontWeight: 700 }}>
            Adjustments per Session — Distribution
          </Typography>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={adj_hist} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
              <XAxis dataKey="label" tick={{ fill: '#aaa', fontSize: 11 }} />
              <YAxis tick={{ fill: '#aaa', fontSize: 11 }} />
              <RTooltip contentStyle={{ background: C.bg, border: `1px solid ${C.grid}`, color: '#eee' }}
                formatter={(v, _, p) => [`${v} sessions (${p.payload.pct}%)`, 'Count']} />
              <Bar dataKey="count" fill={C.blue} radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </Paper>
      )}

      {/* Duration histogram */}
      {dur_hist.length > 0 && (
        <Paper sx={{ p: 2, bgcolor: C.card }}>
          <Typography variant="subtitle2" sx={{ color: C.teal, mb: 1, fontWeight: 700 }}>
            Session Duration Distribution (minutes)
          </Typography>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={dur_hist} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
              <XAxis dataKey="label" tick={{ fill: '#aaa', fontSize: 11 }} />
              <YAxis tick={{ fill: '#aaa', fontSize: 11 }} />
              <RTooltip contentStyle={{ background: C.bg, border: `1px solid ${C.grid}`, color: '#eee' }}
                formatter={(v, _, p) => [`${v} sessions (${p.payload.pct}%)`, 'Count']} />
              <Bar dataKey="count" fill={C.teal} radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </Paper>
      )}
    </Box>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  TAB 4 — Session Log
// ─────────────────────────────────────────────────────────────────────────────
const SessionLogTab = ({ rows }) => {
  const [sort, setSort] = useState({ col: null, dir: 1 });

  const toggleSort = (col) => setSort(s =>
    s.col === col ? { col, dir: s.dir * -1 } : { col, dir: -1 }
  );

  const sorted = [...rows].sort((a, b) => {
    if (!sort.col) return 0;
    const va = a[sort.col] ?? 0;
    const vb = b[sort.col] ?? 0;
    return (va < vb ? -1 : va > vb ? 1 : 0) * sort.dir;
  });

  const TH = ({ col, children, align = 'left' }) => (
    <TableCell align={align}
      onClick={() => toggleSort(col)}
      sx={{ color: sort.col === col ? C.blue : '#aaa', fontWeight: 700, fontSize: 11,
            borderBottom: `1px solid ${C.grid}`, cursor: 'pointer', whiteSpace: 'nowrap',
            '&:hover': { color: C.blue } }}>
      {children}{sort.col === col ? (sort.dir === -1 ? ' ↓' : ' ↑') : ''}
    </TableCell>
  );

  return (
    <Box>
      <SectionHeader
        title="Session Log"
        desc={`${rows.length} sessions. Click column headers to sort. This is your raw data — use it to find outliers and patterns.`} />

      <TableContainer component={Paper} sx={{ bgcolor: C.card, maxHeight: 520 }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TH col="session_id">Session</TH>
              <TH col="expiry">Expiry</TH>
              <TH col="status">Status</TH>
              <TH col="duration_mins" align="right">Duration</TH>
              <TH col="initial_lots" align="right">Start Lots</TH>
              <TH col="max_combined_lots" align="right">Peak Lots</TH>
              <TH col="capital_multiplier" align="right">Mult</TH>
              <TH col="total_adjustments" align="right">Adj</TH>
              <TH col="total_reversals" align="right">Rev</TH>
              <TH col="total_shifts" align="right">Shifts</TH>
              <TH col="close5_count" align="right">Close5</TH>
              <TH col="autoclose_lots" align="right">AutoCls</TH>
              <TH col="max_drawdown" align="right">Drawdn</TH>
              <TH col="pnl" align="right">P&L</TH>
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map((r, i) => (
              <TableRow key={r.session_id || i} hover
                sx={{ '& td': { borderBottom: `1px solid ${C.grid}22`, fontSize: 12, py: 0.6 } }}>
                <TableCell sx={{ fontFamily: 'monospace', fontSize: 11, color: '#ddd' }}>
                  <Tooltip title={r.session_id}><span>{r.session_id}</span></Tooltip>
                </TableCell>
                <TableCell sx={{ color: '#aaa' }}>{r.expiry || '—'}</TableCell>
                <TableCell>
                  <Chip label={r.status || '—'} size="small"
                    sx={{ fontSize: 10, height: 18,
                      bgcolor: r.status === 'STOPPED' ? '#1b5e2044' : r.status === 'RUNNING' ? '#0d47a144' : '#33333388',
                      color: r.status === 'STOPPED' ? C.green : r.status === 'RUNNING' ? C.blue : '#aaa' }} />
                </TableCell>
                <TableCell align="right" sx={{ color: '#aaa' }}>{r.duration_mins} m</TableCell>
                <TableCell align="right">{r.initial_lots}</TableCell>
                <TableCell align="right" sx={{ color: C.yellow, fontWeight: 600 }}>{r.max_combined_lots}</TableCell>
                <TableCell align="right" sx={{ color: r.capital_multiplier > 3 ? C.red : r.capital_multiplier > 2 ? C.orange : '#aaa' }}>
                  {r.capital_multiplier > 0 ? `${r.capital_multiplier}×` : '—'}
                </TableCell>
                <TableCell align="right">{r.total_adjustments}</TableCell>
                <TableCell align="right" sx={{ color: r.total_reversals > 3 ? C.orange : '#aaa' }}>{r.total_reversals}</TableCell>
                <TableCell align="right">{r.total_shifts}</TableCell>
                <TableCell align="right" sx={{ color: r.close5_count > 0 ? C.green : '#aaa' }}>{r.close5_count}</TableCell>
                <TableCell align="right" sx={{ color: r.autoclose_lots > 0 ? C.red : '#aaa' }}>{r.autoclose_lots || '—'}</TableCell>
                <TableCell align="right" sx={{ color: r.max_drawdown > 0 ? C.red : '#aaa' }}>
                  {r.max_drawdown > 0 ? `$${r.max_drawdown}` : '—'}
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 700, color: cls(r.pnl) }}>
                  ${r.pnl?.toFixed(2)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
//  Shared sub-components
// ─────────────────────────────────────────────────────────────────────────────

const KPICard = ({ label, value, sub, color, icon }) => (
  <Paper sx={{ p: 1.5, bgcolor: C.card, borderLeft: `3px solid ${color}`, height: '100%' }}>
    <Box display="flex" justifyContent="space-between" alignItems="flex-start">
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Box sx={{ color }}>{icon}</Box>
    </Box>
    <Typography variant="h5" sx={{ fontWeight: 700, color, mt: 0.5 }}>{value}</Typography>
    {sub && <Typography variant="caption" color="text.secondary">{sub}</Typography>}
  </Paper>
);

const StatPanel = ({ title, accent, children }) => (
  <Paper sx={{ p: 2, bgcolor: C.card, height: '100%', borderTop: `2px solid ${accent}44` }}>
    <Typography variant="subtitle2" sx={{ color: accent, fontWeight: 700, mb: 1.5 }}>{title}</Typography>
    {children}
  </Paper>
);

const BigStat = ({ value, label }) => (
  <Box mb={1}>
    <Typography variant="h4" sx={{ fontWeight: 700, color: '#fff' }}>{value ?? '—'}</Typography>
    <Typography variant="caption" color="text.secondary">{label}</Typography>
  </Box>
);

const Row = ({ label, value }) => (
  <Box display="flex" justifyContent="space-between" alignItems="center" py={0.3}>
    <Typography variant="caption" color="text.secondary">{label}</Typography>
    <Typography variant="caption" sx={{ fontWeight: 600, color: '#ddd' }}>{value ?? '—'}</Typography>
  </Box>
);

const SectionHeader = ({ title, desc }) => (
  <Box mb={2.5}>
    <Typography variant="h6" sx={{ fontWeight: 700, color: C.blue }}>{title}</Typography>
    <Typography variant="body2" color="text.secondary">{desc}</Typography>
    <Divider sx={{ borderColor: C.grid, mt: 1 }} />
  </Box>
);

export default MMMInstitutionalAnalytics;
