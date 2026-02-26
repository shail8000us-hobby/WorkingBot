/**
 * MMMRegimePanel — Regime-Aware Risk Controls Dashboard
 *
 * Displays the three regime control states:
 *   A. Volatility Regime Filter (IV spike + RV detection)
 *   B. Portfolio Gamma Cap (dollar gamma limits)
 *   C. Trend Detection Guard (directional move detection)
 *
 * Plus the aggregate regime action controlling the adjustment engine.
 *
 * Maps to MMM_REGIME_RISK_CONTROLS_DESIGN.md Section D.5.5
 *
 * Created: February 20, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Chip,
  Alert,
  Divider,
  Tooltip,
  CircularProgress,
  LinearProgress,
} from '@mui/material';
import {
  TrendingUp as TrendUpIcon,
  TrendingDown as TrendDownIcon,
  ShowChart as ChartIcon,
  Shield as ShieldIcon,
  Warning as WarningIcon,
  Block as BlockIcon,
  CheckCircle as CheckIcon,
  ErrorOutline as ErrorIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';


// =============================================================================
// Regime Status Colors & Labels
// =============================================================================

const REGIME_COLORS = {
  // Aggregate
  NORMAL: '#4caf50',
  WARN: '#ff9800',
  BLOCK_CE_SELLS: '#ff5722',
  BLOCK_PE_SELLS: '#ff5722',
  BLOCK_ALL_SELLS: '#f44336',
  FORCE_REDUCE: '#d32f2f',
  // Vol
  ELEVATED: '#ff9800',
  HIGH: '#f44336',
  // Gamma
  SOFT: '#ff9800',
  HARD: '#ff5722',
  EMERGENCY: '#d32f2f',
  // Trend
  TREND_UP: '#ff5722',
  TREND_DOWN: '#ff5722',
};

// Trend tier display names and colors
const TREND_TIER_NAMES = {
  0: 'NORMAL',
  1: 'ALERT',
  2: 'GUARD',
  3: 'BLOCK',
  4: 'WIND-DOWN',
};

const TREND_TIER_COLORS = {
  0: '#4caf50',   // green  — normal
  1: '#ff9800',   // orange — alert
  2: '#ff5722',   // deep orange — guard
  3: '#f44336',   // red — block
  4: '#d32f2f',   // dark red — wind-down
};

const ACTION_LABELS = {
  NORMAL: 'All Clear',
  WARN: 'Elevated Risk',
  BLOCK_CE_SELLS: 'CE Sells Blocked',
  BLOCK_PE_SELLS: 'PE Sells Blocked',
  BLOCK_ALL_SELLS: 'All Sells Blocked',
  FORCE_REDUCE: 'Emergency Reduction',
};

const ACTION_DESCRIPTIONS = {
  NORMAL: 'All regime controls clear. Normal adjustment behavior.',
  WARN: 'Trend Tier 1 (Alert) or Gamma approaching soft limit. Lot sizes reduced, adjustments allowed with enhanced logging.',
  BLOCK_CE_SELLS: 'Trend guard Tier 2+ detected upward move. CE sells blocked (PE adjustments still allowed).',
  BLOCK_PE_SELLS: 'Trend guard Tier 2+ detected downward move. PE sells blocked (CE adjustments still allowed).',
  BLOCK_ALL_SELLS: 'Trend Tier 3 (Block) or multiple regime controls active. All new sell orders blocked. Risk-reducing trades continue.',
  FORCE_REDUCE: 'Gamma emergency or Trend Tier 4 (Wind-Down). Forcing position reduction via wind-down buybacks.',
};


// =============================================================================
// Sub-Components
// =============================================================================

function RegimeStatusBanner({ regimeAction }) {
  const color = REGIME_COLORS[regimeAction] || '#4caf50';
  const label = ACTION_LABELS[regimeAction] || regimeAction;
  const desc = ACTION_DESCRIPTIONS[regimeAction] || '';

  const bgAlpha = regimeAction === 'NORMAL' ? '0.08' : '0.15';

  return (
    <Alert
      severity={regimeAction === 'NORMAL' ? 'success' : regimeAction === 'WARN' ? 'warning' : 'error'}
      icon={
        regimeAction === 'NORMAL' ? <CheckIcon /> :
        regimeAction === 'FORCE_REDUCE' ? <ErrorIcon /> :
        regimeAction.includes('BLOCK') ? <BlockIcon /> :
        <WarningIcon />
      }
      sx={{
        mb: 2,
        backgroundColor: `rgba(${regimeAction === 'NORMAL' ? '76,175,80' : '244,67,54'},${bgAlpha})`,
        border: `1px solid ${color}40`,
        '& .MuiAlert-icon': { color },
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
        Regime: {label}
      </Typography>
      <Typography variant="body2" sx={{ opacity: 0.85 }}>
        {desc}
      </Typography>
    </Alert>
  );
}


function VolRegimeCard({ volRegime, details }) {
  const color = REGIME_COLORS[volRegime] || '#4caf50';
  const ivChange = details?.iv_change_pct || 0;
  const rv = details?.rv_annualized || 0;
  const score = details?.vol_regime_score || 0;

  return (
    <Paper sx={{ p: 2, border: `1px solid ${color}40`, backgroundColor: `${color}08` }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Volatility Regime
        </Typography>
        <Chip
          label={volRegime}
          size="small"
          sx={{
            fontWeight: 700,
            fontFamily: 'monospace',
            backgroundColor: `${color}20`,
            color: color,
            border: `1px solid ${color}40`,
          }}
        />
      </Box>

      <Grid container spacing={1}>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>IV Change</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, color: Math.abs(ivChange) > 20 ? '#ff5722' : 'inherit' }}>
            {ivChange >= 0 ? '+' : ''}{ivChange.toFixed(1)}%
          </Typography>
        </Grid>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Realized Vol</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, color: rv > 80 ? '#ff5722' : 'inherit' }}>
            {rv.toFixed(1)}%
          </Typography>
        </Grid>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Score</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {score.toFixed(2)}
          </Typography>
        </Grid>
      </Grid>

      {/* Score bar */}
      <Box sx={{ mt: 1 }}>
        <LinearProgress
          variant="determinate"
          value={Math.min(score * 100, 100)}
          sx={{
            height: 6,
            borderRadius: 3,
            backgroundColor: 'rgba(255,255,255,0.1)',
            '& .MuiLinearProgress-bar': {
              backgroundColor: score > 1.0 ? '#f44336' : score >= 0.7 ? '#ff9800' : '#4caf50',
              borderRadius: 3,
            },
          }}
        />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
          <Typography variant="caption" sx={{ opacity: 0.4, fontSize: '0.65rem' }}>Normal</Typography>
          <Typography variant="caption" sx={{ opacity: 0.4, fontSize: '0.65rem' }}>0.7</Typography>
          <Typography variant="caption" sx={{ opacity: 0.4, fontSize: '0.65rem' }}>1.0</Typography>
        </Box>
      </Box>
    </Paper>
  );
}


function GammaRegimeCard({ gammaRegime, details }) {
  const color = REGIME_COLORS[gammaRegime] || '#4caf50';
  const dollarGamma = details?.dollar_gamma || 0;
  const softLimit = details?.gamma_soft_limit || 50;
  const hardLimit = details?.gamma_hard_limit || 100;

  const pct = hardLimit > 0 ? Math.min((dollarGamma / hardLimit) * 100, 120) : 0;

  return (
    <Paper sx={{ p: 2, border: `1px solid ${color}40`, backgroundColor: `${color}08` }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Portfolio Gamma Cap
        </Typography>
        <Chip
          label={gammaRegime}
          size="small"
          sx={{
            fontWeight: 700,
            fontFamily: 'monospace',
            backgroundColor: `${color}20`,
            color: color,
            border: `1px solid ${color}40`,
          }}
        />
      </Box>

      <Grid container spacing={1}>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Dollar Gamma</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, color: dollarGamma > softLimit ? '#ff5722' : 'inherit' }}>
            ${dollarGamma.toFixed(2)}
          </Typography>
        </Grid>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Soft Limit</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            ${softLimit.toFixed(0)}
          </Typography>
        </Grid>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Hard Limit</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            ${hardLimit.toFixed(0)}
          </Typography>
        </Grid>
      </Grid>

      {/* Gamma bar */}
      <Box sx={{ mt: 1 }}>
        <LinearProgress
          variant="determinate"
          value={Math.min(pct, 100)}
          sx={{
            height: 6,
            borderRadius: 3,
            backgroundColor: 'rgba(255,255,255,0.1)',
            '& .MuiLinearProgress-bar': {
              backgroundColor: pct > 100 ? '#f44336' : pct > 50 ? '#ff9800' : '#4caf50',
              borderRadius: 3,
            },
          }}
        />
      </Box>
    </Paper>
  );
}


function TrendRegimeCard({ trendRegime, details, trendTier, trendDirection }) {
  const tier = trendTier || details?.trend_tier || 0;
  const direction = trendDirection || details?.trend_direction || 'none';
  const tierName = TREND_TIER_NAMES[tier] || 'UNKNOWN';
  const color = TREND_TIER_COLORS[tier] || '#4caf50';
  const movePct = details?.spot_move_pct || 0;
  const emaSlope = details?.ema_slope || 0;
  const anchor = details?.trend_anchor || 0;
  const accelPct = details?.trend_acceleration_move_pct || 0;

  const trendIcon = direction === 'up' ? <TrendUpIcon sx={{ color: tier > 0 ? '#f44336' : '#4caf50' }} /> :
                    direction === 'down' ? <TrendDownIcon sx={{ color: tier > 0 ? '#f44336' : '#4caf50' }} /> :
                    <ChartIcon sx={{ color: '#4caf50' }} />;

  const chipLabel = tier === 0 ? 'NORMAL' : `T${tier} ${tierName}${direction !== 'none' ? ` ${direction.toUpperCase()}` : ''}`;

  return (
    <Paper sx={{ p: 2, border: `1px solid ${color}40`, backgroundColor: `${color}08` }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {trendIcon}
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            Trend Detection
          </Typography>
        </Box>
        <Chip
          label={chipLabel}
          size="small"
          sx={{
            fontWeight: 700,
            fontFamily: 'monospace',
            backgroundColor: `${color}20`,
            color: color,
            border: `1px solid ${color}40`,
          }}
        />
      </Box>

      {/* Tier progress indicator */}
      {tier > 0 && (
        <Box sx={{ display: 'flex', gap: 0.5, mb: 1 }}>
          {[1, 2, 3, 4].map((t) => (
            <Box
              key={t}
              sx={{
                flex: 1, height: 4, borderRadius: 1,
                backgroundColor: t <= tier ? TREND_TIER_COLORS[t] : '#e0e0e0',
                opacity: t <= tier ? 1 : 0.3,
              }}
            />
          ))}
        </Box>
      )}

      <Grid container spacing={1}>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Spot Move</Typography>
          <Typography variant="body2" sx={{
            fontFamily: 'monospace', fontWeight: 600,
            color: Math.abs(movePct) > 1.0 ? '#ff5722' : 'inherit',
          }}>
            {movePct >= 0 ? '+' : ''}{movePct.toFixed(2)}%
          </Typography>
        </Grid>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>EMA Slope</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {emaSlope >= 0 ? '+' : ''}{emaSlope.toFixed(1)}
          </Typography>
        </Grid>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Accel</Typography>
          <Typography variant="body2" sx={{
            fontFamily: 'monospace', fontWeight: 600,
            color: Math.abs(accelPct) > 0.3 ? '#ff9800' : 'inherit',
          }}>
            {accelPct >= 0 ? '+' : ''}{accelPct.toFixed(2)}%
          </Typography>
        </Grid>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Anchor</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            ${anchor > 0 ? anchor.toFixed(0) : '-'}
          </Typography>
        </Grid>
      </Grid>
    </Paper>
  );
}


// =============================================================================
// Main Component
// =============================================================================

export default function MMMRegimePanel({ session, regimeData, heartbeat }) {
  const [fullRegime, setFullRegime] = useState(null);
  const [loading, setLoading] = useState(false);

  // Use WebSocket regime data if available, otherwise fetch via REST
  const regime = regimeData || fullRegime;

  // Also check heartbeat for embedded regime data
  const heartbeatRegime = heartbeat?.regime;

  const effectiveRegime = regime || (heartbeatRegime ? {
    regime_action: heartbeatRegime.regime_action,
    vol_regime: heartbeatRegime.vol_regime,
    gamma_regime: heartbeatRegime.gamma_regime,
    trend_regime: heartbeatRegime.trend_regime,
    details: {
      dollar_gamma: heartbeatRegime.dollar_gamma,
      spot_move_pct: heartbeatRegime.trend_move_pct,
      vol_regime_score: heartbeatRegime.vol_regime_score,
    },
  } : null);

  const fetchRegime = useCallback(async () => {
    if (!session?.session_id) return;
    try {
      setLoading(true);
      const data = await mmmService.getRegimeStatus(session.session_id);
      if (data.success) {
        setFullRegime(data);
      }
    } catch (err) {
      // Non-fatal
    } finally {
      setLoading(false);
    }
  }, [session?.session_id]);

  // Fetch on mount and periodically
  useEffect(() => {
    fetchRegime();
    const interval = setInterval(fetchRegime, 30000); // Every 30s
    return () => clearInterval(interval);
  }, [fetchRegime]);

  if (!effectiveRegime) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        {loading ? (
          <CircularProgress size={24} />
        ) : (
          <Typography variant="body2" sx={{ opacity: 0.5 }}>
            Regime data not yet available. Start a session to see regime controls.
          </Typography>
        )}
      </Box>
    );
  }

  const {
    regime_action = 'NORMAL',
    vol_regime = 'NORMAL',
    gamma_regime = 'NORMAL',
    trend_regime = 'NORMAL',
    trend_tier = 0,
    trend_direction = 'none',
    details = {},
    observation_mode = false,
  } = effectiveRegime;

  return (
    <Box>
      {/* Observation Mode Banner */}
      {observation_mode && (
        <Alert
          severity="info"
          sx={{
            mb: 2,
            backgroundColor: 'rgba(33,150,243,0.1)',
            border: '1px solid rgba(33,150,243,0.3)',
          }}
        >
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            👁️ OBSERVATION MODE — Regime Disabled
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.85 }}>
            Data is being collected but NO trades are blocked or forced. Enable "Regime Enabled" in Settings to activate enforcement.
          </Typography>
        </Alert>
      )}
      {/* Aggregate Status Banner */}
      {!observation_mode && <RegimeStatusBanner regimeAction={regime_action} />}

      {/* Three Control Cards */}
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}>
          <VolRegimeCard volRegime={vol_regime} details={details} />
        </Grid>
        <Grid item xs={12} md={4}>
          <GammaRegimeCard gammaRegime={gamma_regime} details={details} />
        </Grid>
        <Grid item xs={12} md={4}>
          <TrendRegimeCard trendRegime={trend_regime} details={details} trendTier={trend_tier} trendDirection={trend_direction} />
        </Grid>
      </Grid>

      {/* How It Works */}
      <Box sx={{ mt: 2 }}>
        <Divider sx={{ mb: 1.5 }} />
        <Typography variant="caption" sx={{ opacity: 0.5, display: 'block', mb: 1 }}>
          Regime controls run every heartbeat between safety checks and trigger evaluation.
          Risk-reducing trades (close-at-5, wind-down buybacks) are always immune to regime blocks.
        </Typography>
        <Grid container spacing={1}>
          <Grid item xs={4}>
            <Typography variant="caption" sx={{ opacity: 0.4, fontSize: '0.65rem' }}>
              <strong>Vol Filter:</strong> Blocks all sells when IV spikes or RV is elevated.
            </Typography>
          </Grid>
          <Grid item xs={4}>
            <Typography variant="caption" sx={{ opacity: 0.4, fontSize: '0.65rem' }}>
              <strong>Gamma Cap:</strong> Blocks sells when portfolio dollar gamma exceeds limits. Emergency mode forces position reduction.
            </Typography>
          </Grid>
          <Grid item xs={4}>
            <Typography variant="caption" sx={{ opacity: 0.4, fontSize: '0.65rem' }}>
              <strong>Trend Guard:</strong> Directional blocking — only blocks the dangerous side. TREND_UP blocks CE sells, TREND_DOWN blocks PE sells.
            </Typography>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
}
