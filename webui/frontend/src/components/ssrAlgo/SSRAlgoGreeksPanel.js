/**
 * SSR ALGO Greeks & P&L Panel
 *
 * Displays live portfolio Greeks (delta, gamma, theta, vega),
 * unrealized/realized P&L, DTE phase, IV rank, and regime status.
 *
 * Phase 9 of SSR Algo Development Plan
 * Created: February 20, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Chip, Tooltip, LinearProgress } from '@mui/material';
import ssrAlgoService from './ssrAlgoService';

/* ── Color helpers ── */
const deltaColor = (v) => {
  const a = Math.abs(v);
  if (a >= 0.80) return '#ef4444';
  if (a >= 0.40) return '#f97316';
  if (a >= 0.20) return '#fbbf24';
  return '#4ade80';
};

const pnlColor = (v) => v > 0 ? '#4ade80' : v < 0 ? '#f87171' : '#94a3b8';

const dtePhaseColor = {
  EARLY_LIFE: '#3b82f6',
  PEAK_THETA: '#22c55e',
  GAMMA_DANGER: '#f97316',
  EXIT_ZONE: '#ef4444',
};

const dtePhaseLabel = {
  EARLY_LIFE: 'Early Life',
  PEAK_THETA: 'Peak Theta',
  GAMMA_DANGER: 'Gamma Danger',
  EXIT_ZONE: 'Exit Zone',
};

const regimeColors = {
  ranging: '#4ade80',
  trending: '#f97316',
  high_vol: '#a78bfa',
  low_vol: '#64748b',
};

/* ── Greek Bar ── */
const GreekBar = ({ label, value, maxVal, color, unit = '', tooltip }) => {
  const pct = Math.min(100, Math.abs(value) / maxVal * 100);
  return (
    <Tooltip title={tooltip || `${label}: ${value}${unit}`} placement="left">
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.6 }}>
        <Typography sx={{
          width: 42, fontSize: 11, fontWeight: 700, color: '#94a3b8',
          textTransform: 'uppercase', letterSpacing: '0.3px', textAlign: 'right',
        }}>
          {label}
        </Typography>
        <Box sx={{ flex: 1, height: 8, bgcolor: 'rgba(71,85,105,0.25)', borderRadius: 4, overflow: 'hidden' }}>
          <Box sx={{
            width: `${pct}%`, height: '100%', borderRadius: 4,
            bgcolor: color, transition: 'width 0.4s ease',
          }} />
        </Box>
        <Typography sx={{
          width: 70, fontSize: 12, fontWeight: 700, textAlign: 'right',
          fontFamily: '"JetBrains Mono", monospace', color,
        }}>
          {value > 0 ? '+' : ''}{typeof value === 'number' ? value.toFixed(4) : value}{unit}
        </Typography>
      </Box>
    </Tooltip>
  );
};

/* ── Metric Row ── */
const MiniMetric = ({ label, value, color, mono = true }) => (
  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 0.2 }}>
    <Typography sx={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>
      {label}
    </Typography>
    <Typography sx={{
      fontSize: 13, fontWeight: 700, color: color || '#e2e8f0',
      fontFamily: mono ? '"JetBrains Mono", monospace' : 'inherit',
    }}>
      {value}
    </Typography>
  </Box>
);

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN PANEL
   ═══════════════════════════════════════════════════════════════════════════ */
const SSRAlgoGreeksPanel = ({ session, compact = false }) => {
  const [greeksData, setGreeksData] = useState(null);
  const [rvIvData, setRvIvData] = useState(null);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loading, setLoading] = useState(false);

  const sessionId = session?.session_id;
  const hasPositions = session?.positions?.length > 0;

  const fetchGreeks = useCallback(async () => {
    if (!sessionId || !hasPositions) return;
    setLoading(true);
    try {
      const r = await ssrAlgoService.getSessionGreeks(sessionId);
      if (r.success) setGreeksData(r);
    } catch (e) { console.debug('Greeks fetch failed:', e); }
    finally { setLoading(false); }
  }, [sessionId, hasPositions]);

  const fetchRvIv = useCallback(async () => {
    if (!sessionId) return;
    try {
      const r = await ssrAlgoService.getSessionRvIv(sessionId);
      if (r.success) setRvIvData(r);
    } catch (e) { console.debug('RV/IV fetch failed:', e); }
  }, [sessionId]);

  const fetchAnalytics = useCallback(async () => {
    if (!sessionId) return;
    try {
      const r = await ssrAlgoService.getSessionAnalytics(sessionId);
      if (r.success) setAnalyticsData(r.analytics);
    } catch (e) { console.debug('Analytics fetch failed:', e); }
  }, [sessionId]);

  useEffect(() => {
    fetchGreeks();
    fetchRvIv();
    fetchAnalytics();
    const i = setInterval(fetchGreeks, 10000);
    const j = setInterval(fetchRvIv, 60000); // Every 60s
    const k = setInterval(fetchAnalytics, 30000); // Every 30s
    return () => { clearInterval(i); clearInterval(j); clearInterval(k); };
  }, [fetchGreeks, fetchRvIv, fetchAnalytics]);

  // Use session cached data as fallback
  const greeks = greeksData?.live_greeks || session?.live_greeks || {};
  const pnl = greeksData?.live_pnl || session?.live_pnl || {};
  const updatedAt = greeksData?.greeks_updated_at || session?.greeks_updated_at;

  const netDelta = greeks.net_delta || 0;
  const netGamma = greeks.net_gamma || 0;
  const netTheta = greeks.net_theta || 0;
  const netVega = greeks.net_vega || 0;

  const unrealizedPnl = pnl.unrealized_pnl || 0;
  const realizedPnl = pnl.realized_pnl || 0;
  const totalPnl = pnl.total_pnl || 0;

  const dtePhase = session?.current_dte_phase;
  const regime = session?.current_regime;
  const hedgeCount = session?.daily_hedge_count || 0;

  if (!hasPositions) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography sx={{ color: '#64748b', fontSize: 13 }}>No positions — Greeks will appear after session starts</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: compact ? 1 : 1.5, display: 'flex', flexDirection: 'column', gap: 1.2 }}>
      {loading && <LinearProgress sx={{ height: 2, mb: 0.5, borderRadius: 1 }} />}

      {/* ── P&L Section ── */}
      <Box sx={{
        p: 1.2, borderRadius: 1.5,
        background: totalPnl >= 0
          ? 'linear-gradient(135deg, rgba(34,197,94,0.12) 0%, rgba(34,197,94,0.04) 100%)'
          : 'linear-gradient(135deg, rgba(239,68,68,0.12) 0%, rgba(239,68,68,0.04) 100%)',
        border: `1px solid ${totalPnl >= 0 ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
      }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
          <Typography sx={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            Total P&L
          </Typography>
          <Typography sx={{
            fontSize: 20, fontWeight: 800,
            fontFamily: '"JetBrains Mono", monospace',
            color: pnlColor(totalPnl),
          }}>
            {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <MiniMetric label="Unrealized" value={`${unrealizedPnl >= 0 ? '+' : ''}$${unrealizedPnl.toFixed(2)}`} color={pnlColor(unrealizedPnl)} />
          <MiniMetric label="Realized" value={`${realizedPnl >= 0 ? '+' : ''}$${realizedPnl.toFixed(2)}`} color={pnlColor(realizedPnl)} />
        </Box>
      </Box>

      {/* ── Greeks Bars ── */}
      <Box sx={{
        p: 1.2, borderRadius: 1.5,
        bgcolor: 'rgba(30,41,59,0.5)',
        border: '1px solid rgba(71,85,105,0.25)',
      }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.8 }}>
          <Typography sx={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            Portfolio Greeks
          </Typography>
          {updatedAt && (
            <Typography sx={{ fontSize: 10, color: '#475569' }}>
              {new Date(updatedAt).toLocaleTimeString()}
            </Typography>
          )}
        </Box>

        <GreekBar
          label="Delta"
          value={netDelta}
          maxVal={1.0}
          color={deltaColor(netDelta)}
          tooltip={`Net Delta: ${netDelta.toFixed(6)} — ${Math.abs(netDelta) > 0.40 ? 'Hedge recommended' : 'Within range'}`}
        />
        <GreekBar
          label="Gamma"
          value={netGamma}
          maxVal={0.5}
          color="#818cf8"
          tooltip={`Net Gamma: ${netGamma.toFixed(6)}`}
        />
        <GreekBar
          label="Theta"
          value={netTheta}
          maxVal={50}
          color={netTheta > 0 ? '#4ade80' : '#f87171'}
          tooltip={`Net Theta: ${netTheta.toFixed(4)} — ${netTheta > 0 ? `Earning $${netTheta.toFixed(2)}/day` : 'Paying theta'}`}
        />
        <GreekBar
          label="Vega"
          value={netVega}
          maxVal={500}
          color="#c084fc"
          tooltip={`Net Vega: ${netVega.toFixed(4)}`}
        />
      </Box>

      {/* ── Status Badges Row ── */}
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.8 }}>
        {/* DTE Phase */}
        {dtePhase && (
          <Tooltip title={dtePhaseLabel[dtePhase] || dtePhase}>
            <Chip
              size="small"
              label={`DTE: ${dtePhaseLabel[dtePhase] || dtePhase}`}
              sx={{
                height: 22, fontSize: 11, fontWeight: 700,
                bgcolor: `${dtePhaseColor[dtePhase] || '#64748b'}22`,
                color: dtePhaseColor[dtePhase] || '#94a3b8',
                border: `1px solid ${dtePhaseColor[dtePhase] || '#64748b'}44`,
              }}
            />
          </Tooltip>
        )}

        {/* Regime */}
        {regime && (
          <Tooltip title={`Market regime: ${regime}`}>
            <Chip
              size="small"
              label={`Regime: ${regime}`}
              sx={{
                height: 22, fontSize: 11, fontWeight: 700,
                bgcolor: `${regimeColors[regime] || '#64748b'}22`,
                color: regimeColors[regime] || '#94a3b8',
                border: `1px solid ${regimeColors[regime] || '#64748b'}44`,
              }}
            />
          </Tooltip>
        )}

        {/* Hedge count */}
        {hedgeCount > 0 && (
          <Chip
            size="small"
            label={`Hedges: ${hedgeCount}`}
            sx={{
              height: 22, fontSize: 11, fontWeight: 700,
              bgcolor: 'rgba(251,191,36,0.15)',
              color: '#fbbf24',
              border: '1px solid rgba(251,191,36,0.3)',
            }}
          />
        )}

        {/* Delta hedge status */}
        {session?.delta_hedge_config?.enabled && (
          <Chip
            size="small"
            label="Delta Hedge ON"
            sx={{
              height: 22, fontSize: 11, fontWeight: 700,
              bgcolor: 'rgba(56,189,248,0.15)',
              color: '#38bdf8',
              border: '1px solid rgba(56,189,248,0.3)',
            }}
          />
        )}
      </Box>

      {/* ── Per-leg P&L breakdown (expandable) ── */}
      {pnl.per_leg_pnl?.length > 0 && !compact && (
        <Box sx={{
          p: 1, borderRadius: 1.5,
          bgcolor: 'rgba(30,41,59,0.3)',
          border: '1px solid rgba(71,85,105,0.2)',
        }}>
          <Typography sx={{ fontSize: 11, fontWeight: 700, color: '#64748b', mb: 0.5, textTransform: 'uppercase' }}>
            Per-Leg P&L
          </Typography>
          {pnl.per_leg_pnl.map((leg, i) => (
            <Box key={i} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.2 }}>
              <Typography sx={{ fontSize: 11, color: '#94a3b8', fontFamily: '"JetBrains Mono", monospace' }}>
                {leg.leg_key || leg.symbol?.slice(-15) || `Leg ${i + 1}`}
              </Typography>
              <Typography sx={{
                fontSize: 11, fontWeight: 700, color: pnlColor(leg.pnl || 0),
                fontFamily: '"JetBrains Mono", monospace',
              }}>
                {(leg.pnl || 0) >= 0 ? '+' : ''}${(leg.pnl || 0).toFixed(2)}
              </Typography>
            </Box>
          ))}
        </Box>
      )}

      {/* ── RV/IV Volatility Analysis ── */}
      {rvIvData?.snapshot && (
        <Box sx={{
          p: 1.2, borderRadius: 1.5,
          bgcolor: 'rgba(30,41,59,0.5)',
          border: '1px solid rgba(71,85,105,0.25)',
        }}>
          <Typography sx={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', mb: 0.8, textTransform: 'uppercase' }}>
            🔬 Volatility Analysis (RV vs IV)
          </Typography>
          {rvIvData.snapshot.signal === 'INSUFFICIENT_DATA' ? (
            <Typography sx={{ fontSize: 12, color: '#64748b', fontStyle: 'italic' }}>
              Collecting price data... (need ~5 min of monitoring)
            </Typography>
          ) : (
            <>
              <Box sx={{ display: 'flex', gap: 1.5, mb: 0.8 }}>
                <Box sx={{ flex: 1 }}>
                  <MiniMetric label="RV (5d)" value={rvIvData.snapshot.rv_5d != null ? `${(rvIvData.snapshot.rv_5d * 100).toFixed(1)}%` : '—'} color="#818cf8" />
                  <MiniMetric label="RV (20d)" value={rvIvData.snapshot.rv_20d != null ? `${(rvIvData.snapshot.rv_20d * 100).toFixed(1)}%` : '—'} color="#818cf8" />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <MiniMetric label="ATM IV" value={rvIvData.snapshot.atm_iv != null ? `${(rvIvData.snapshot.atm_iv * 100).toFixed(1)}%` : '—'} color="#c084fc" />
                  <MiniMetric label="RV/IV" value={rvIvData.snapshot.rv_iv_ratio != null ? rvIvData.snapshot.rv_iv_ratio.toFixed(2) : '—'} color={rvIvData.snapshot.rv_iv_ratio > 1.2 ? '#f87171' : rvIvData.snapshot.rv_iv_ratio < 0.7 ? '#4ade80' : '#fbbf24'} />
                </Box>
              </Box>
              <Chip
                size="small"
                label={`Signal: ${rvIvData.snapshot.signal?.replace('_', ' ') || 'N/A'}`}
                sx={{
                  height: 22, fontSize: 11, fontWeight: 700,
                  bgcolor: rvIvData.snapshot.signal === 'SELL_PREMIUM' ? 'rgba(74,222,128,0.15)' : rvIvData.snapshot.signal === 'DANGER' ? 'rgba(239,68,68,0.15)' : 'rgba(251,191,36,0.15)',
                  color: rvIvData.snapshot.signal === 'SELL_PREMIUM' ? '#4ade80' : rvIvData.snapshot.signal === 'DANGER' ? '#f87171' : '#fbbf24',
                  border: `1px solid ${rvIvData.snapshot.signal === 'SELL_PREMIUM' ? 'rgba(74,222,128,0.3)' : rvIvData.snapshot.signal === 'DANGER' ? 'rgba(239,68,68,0.3)' : 'rgba(251,191,36,0.3)'}`,
                }}
              />
            </>
          )}
        </Box>
      )}

      {/* ── Session Analytics Summary ── */}
      {analyticsData && (
        <Box sx={{
          p: 1.2, borderRadius: 1.5,
          bgcolor: 'rgba(30,41,59,0.5)',
          border: '1px solid rgba(71,85,105,0.25)',
        }}>
          <Typography sx={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', mb: 0.8, textTransform: 'uppercase' }}>
            📊 Session Analytics
          </Typography>
          <Box sx={{ display: 'flex', gap: 1.5, mb: 0.5 }}>
            <Box sx={{ flex: 1 }}>
              <MiniMetric label="Net Premium" value={`$${(analyticsData.net_premium || 0).toFixed(2)}`} color="#818cf8" />
              <MiniMetric label="Return/Prem" value={`${(analyticsData.return_on_premium_pct || 0).toFixed(1)}%`} color={pnlColor(analyticsData.return_on_premium_pct || 0)} />
              <MiniMetric label="Holding" value={`${(analyticsData.holding_period_hours || 0).toFixed(0)}h`} color="#94a3b8" />
            </Box>
            <Box sx={{ flex: 1 }}>
              <MiniMetric label="Max DD" value={`$${(analyticsData.max_drawdown || 0).toFixed(2)}`} color={analyticsData.max_drawdown > 0 ? '#f87171' : '#94a3b8'} />
              <MiniMetric label="Θ/Day" value={`$${(analyticsData.theta_per_day || 0).toFixed(3)}`} color={analyticsData.theta_per_day > 0 ? '#f87171' : '#4ade80'} />
              <MiniMetric label="Adjustments" value={`${analyticsData.adjustment_count || 0}`} color="#fbbf24" />
            </Box>
          </Box>
          {analyticsData.execution_quality && (
            <Box sx={{ mt: 0.5, pt: 0.5, borderTop: '1px solid rgba(71,85,105,0.2)' }}>
              <MiniMetric label="Orders" value={`${analyticsData.execution_quality.total_orders || 0}`} color="#94a3b8" />
              {analyticsData.execution_quality.avg_slippage_pct > 0 && (
                <MiniMetric label="Avg Slippage" value={`${analyticsData.execution_quality.avg_slippage_pct.toFixed(2)}%`} color="#fbbf24" />
              )}
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
};

export default SSRAlgoGreeksPanel;
