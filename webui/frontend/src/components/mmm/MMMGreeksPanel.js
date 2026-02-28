/**
 * MMMGreeksPanel — Money Mind & Method
 *
 * Live Greeks, Implied Volatility, and position analytics panel.
 * Fetches data from the backend /greeks-iv endpoint which calls
 * Delta Exchange /v2/tickers/{symbol} for each open position.
 *
 * Displays per-position:
 * - Side (CE/PE), Strike, Lots
 * - Greeks: Delta (δ), Gamma (γ), Theta (θ), Vega (ν), Rho (ρ)
 * - IV: Mark IV, Bid IV, Ask IV
 * - Position-weighted Greeks totals
 *
 * Auto-refreshes every 60 seconds when the tab is visible.
 *
 * Created: February 18, 2026
 */

import React, { useState, useCallback } from 'react';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Typography,
  Tooltip,
  CircularProgress,
  IconButton,
  Alert,
  Button,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import AcUnitIcon from '@mui/icons-material/AcUnit';
import mmmService from './mmmService';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function fmtGreek(val, decimals = 4) {
  if (val == null || isNaN(val)) return '—';
  return Number(val).toFixed(decimals);
}

function fmtIV(val) {
  if (val == null || isNaN(val)) return '—';
  return `${(Number(val) * 100).toFixed(1)}%`;
}

function fmtNum(n, decimals = 2) {
  if (n == null || isNaN(n)) return '--';
  return Number(n).toFixed(decimals);
}

function pnlColor(pnl) {
  if (pnl > 0) return '#4caf50';
  if (pnl < 0) return '#f44336';
  return 'text.secondary';
}

const REFRESH_INTERVAL = 60_000; // 60 seconds

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export default function MMMGreeksPanel({ session }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastFetch, setLastFetch] = useState(null);

  const sessionId = session?.session_id;

  const fetchGreeks = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await mmmService.getGreeksIV(sessionId);
      if (result.success) {
        setData(result);
        setLastFetch(new Date());
      } else {
        setError(result.error || 'Unknown error');
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch Greeks/IV data');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // Initial fetch + auto-refresh — pauses when tab is hidden
  useVisibilityAwarePolling(fetchGreeks, REFRESH_INTERVAL, 120000);

  if (!sessionId) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">No session selected.</Typography>
      </Box>
    );
  }

  if (loading && !data) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <CircularProgress size={28} sx={{ mb: 1 }} />
        <Typography color="text.secondary" sx={{ fontSize: '0.9rem' }}>
          Fetching Greeks & IV from Delta Exchange...
        </Typography>
      </Box>
    );
  }

  if (error && !data) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error" sx={{ mb: 1 }}>
          {error}
        </Alert>
        <Button onClick={fetchGreeks} size="small">
          Retry
        </Button>
      </Box>
    );
  }

  const positions = data?.positions || [];
  const spotPrice = data?.spot_price || 0;

  // Compute portfolio-level weighted Greeks
  // Backend already returns position Greeks (negated for short positions),
  // so we simply weight by lots here.
  const totals = positions.reduce(
    (acc, p) => {
      const lots = p.lots || 0;
      const g = p.greeks || {};
      acc.lots += lots;
      acc.delta += (g.delta || 0) * lots;
      acc.gamma += (g.gamma || 0) * lots;
      acc.theta += (g.theta || 0) * lots;
      acc.vega += (g.vega || 0) * lots;
      acc.pnl += p.pnl || 0;
      return acc;
    },
    { lots: 0, delta: 0, gamma: 0, theta: 0, vega: 0, pnl: 0 }
  );

  return (
    <Box>
      {/* Header with refresh */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 1,
        }}
      >
        <Typography
          variant="caption"
          sx={{
            color: 'text.secondary',
            fontStyle: 'italic',
            fontSize: '0.82rem',
            opacity: 0.75,
          }}
        >
          📐 Live Greeks and Implied Volatility from Delta Exchange tickers.
          Position-weighted totals show portfolio-level risk exposure.
          {spotPrice > 0 && ` BTC Spot: $${Number(spotPrice).toLocaleString()}`}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {lastFetch && (
            <Typography
              variant="caption"
              sx={{ color: 'text.secondary', fontSize: '0.75rem' }}
            >
              Updated {lastFetch.toLocaleTimeString()}
            </Typography>
          )}
          <Tooltip title="Refresh Greeks & IV">
            <IconButton size="small" onClick={fetchGreeks} disabled={loading}>
              {loading ? (
                <CircularProgress size={16} />
              ) : (
                <RefreshIcon fontSize="small" />
              )}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && (
        <Alert severity="warning" sx={{ mb: 1, py: 0 }}>
          {error} — showing last data
        </Alert>
      )}

      {positions.length === 0 ? (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography color="text.secondary">
            No positions with Greeks data available.
          </Typography>
        </Box>
      ) : (
        <TableContainer
          component={Paper}
          variant="outlined"
          sx={{ borderRadius: 2 }}
        >
          <Table size="small">
            <TableHead>
              <TableRow
                sx={{ '& th': { fontWeight: 700, fontSize: '0.82rem' } }}
              >
                <TableCell>Side</TableCell>
                <TableCell align="right">Strike</TableCell>
                <TableCell align="right">Lots</TableCell>
                <TableCell align="right">Mark</TableCell>
                <Tooltip
                  title="Delta (δ): Rate of change of option price per $1 move in BTC. Short positions: negative delta on calls, positive on puts."
                  arrow
                >
                  <TableCell
                    align="right"
                    sx={{ cursor: 'help', color: '#42a5f5' }}
                  >
                    δ Delta
                  </TableCell>
                </Tooltip>
                <Tooltip
                  title="Gamma (γ): Rate of change of delta. High gamma = delta changes rapidly with BTC moves."
                  arrow
                >
                  <TableCell
                    align="right"
                    sx={{ cursor: 'help', color: '#ab47bc' }}
                  >
                    γ Gamma
                  </TableCell>
                </Tooltip>
                <Tooltip
                  title="Theta (θ): Time decay per day. As option sellers, positive theta earns you money each day."
                  arrow
                >
                  <TableCell
                    align="right"
                    sx={{ cursor: 'help', color: '#66bb6a' }}
                  >
                    θ Theta
                  </TableCell>
                </Tooltip>
                <Tooltip
                  title="Vega (ν): Sensitivity to 1% change in IV. High vega = more exposure to volatility changes."
                  arrow
                >
                  <TableCell
                    align="right"
                    sx={{ cursor: 'help', color: '#ffa726' }}
                  >
                    ν Vega
                  </TableCell>
                </Tooltip>
                <Tooltip
                  title="Mark Implied Volatility — the market's consensus IV for this option"
                  arrow
                >
                  <TableCell
                    align="right"
                    sx={{ cursor: 'help', color: '#ef5350' }}
                  >
                    Mark IV
                  </TableCell>
                </Tooltip>
                <Tooltip title="Bid IV / Ask IV — IV at best bid and ask" arrow>
                  <TableCell align="right" sx={{ cursor: 'help' }}>
                    Bid / Ask IV
                  </TableCell>
                </Tooltip>
                <TableCell align="right">P&L</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {positions.map((pos) => {
                const g = pos.greeks || {};
                const iv = pos.iv || {};
                const isFrozen = pos.frozen;
                const lots = pos.lots || 0;
                // Position-level Greeks = per-lot Greek × lots
                const posGreeks = {
                  delta: g.delta != null ? g.delta * lots : null,
                  gamma: g.gamma != null ? g.gamma * lots : null,
                  theta: g.theta != null ? g.theta * lots : null,
                  vega: g.vega != null ? g.vega * lots : null,
                };

                return (
                  <TableRow
                    key={`${pos.side}-${pos.strike}`}
                    sx={{
                      bgcolor: isFrozen
                        ? 'rgba(158,158,158,0.08)'
                        : 'transparent',
                      opacity: isFrozen ? 0.75 : 1,
                      '&:last-child td': { borderBottom: 0 },
                    }}
                  >
                    {/* Side */}
                    <TableCell>
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                        }}
                      >
                        {isFrozen && (
                          <AcUnitIcon
                            sx={{ fontSize: '0.85rem', color: '#90caf9' }}
                          />
                        )}
                        <Chip
                          label={pos.side}
                          size="small"
                          sx={{
                            fontWeight: 700,
                            bgcolor:
                              pos.side === 'CE'
                                ? 'rgba(33,150,243,0.15)'
                                : 'rgba(156,39,176,0.15)',
                            color:
                              pos.side === 'CE' ? '#2196f3' : '#9c27b0',
                          }}
                        />
                      </Box>
                    </TableCell>

                    {/* Strike */}
                    <TableCell
                      align="right"
                      sx={{ fontFamily: 'monospace' }}
                    >
                      {Number(pos.strike).toLocaleString()}
                    </TableCell>

                    {/* Lots */}
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      {pos.lots}
                    </TableCell>

                    {/* Mark Price */}
                    <TableCell
                      align="right"
                      sx={{ fontFamily: 'monospace' }}
                    >
                      {fmtNum(pos.mark_price)}
                    </TableCell>

                    {/* Delta (position total) */}
                    <TableCell
                      align="right"
                      sx={{ fontFamily: 'monospace', color: '#42a5f5' }}
                    >
                      {fmtGreek(posGreeks.delta)}
                    </TableCell>

                    {/* Gamma (position total) */}
                    <TableCell
                      align="right"
                      sx={{ fontFamily: 'monospace', color: '#ab47bc' }}
                    >
                      {fmtGreek(posGreeks.gamma, 6)}
                    </TableCell>

                    {/* Theta (position total) */}
                    <TableCell
                      align="right"
                      sx={{ fontFamily: 'monospace', color: '#66bb6a' }}
                    >
                      {fmtGreek(posGreeks.theta)}
                    </TableCell>

                    {/* Vega (position total) */}
                    <TableCell
                      align="right"
                      sx={{ fontFamily: 'monospace', color: '#ffa726' }}
                    >
                      {fmtGreek(posGreeks.vega)}
                    </TableCell>

                    {/* Mark IV */}
                    <TableCell
                      align="right"
                      sx={{ fontFamily: 'monospace', color: '#ef5350' }}
                    >
                      {fmtIV(iv.mark_iv)}
                    </TableCell>

                    {/* Bid / Ask IV */}
                    <TableCell
                      align="right"
                      sx={{
                        fontFamily: 'monospace',
                        fontSize: '0.8rem',
                      }}
                    >
                      {fmtIV(iv.bid_iv)} / {fmtIV(iv.ask_iv)}
                    </TableCell>

                    {/* P&L */}
                    <TableCell
                      align="right"
                      sx={{
                        fontFamily: 'monospace',
                        fontWeight: 600,
                        color:
                          pos.pnl != null
                            ? pnlColor(pos.pnl)
                            : 'text.disabled',
                      }}
                    >
                      {pos.pnl != null ? (
                        <span>
                          {pos.pnl >= 0 ? '+' : ''}${fmtNum(pos.pnl)}
                        </span>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}

              {/* Portfolio totals row */}
              <TableRow
                sx={{
                  '& td': { borderTop: '2px solid', borderColor: 'divider' },
                }}
              >
                <TableCell colSpan={2} sx={{ fontWeight: 700 }}>
                  Portfolio Total
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 700 }}>
                  {totals.lots}
                </TableCell>
                <TableCell />
                <TableCell
                  align="right"
                  sx={{
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    color: '#42a5f5',
                  }}
                >
                  {fmtGreek(totals.delta)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    color: '#ab47bc',
                  }}
                >
                  {fmtGreek(totals.gamma, 6)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    color: '#66bb6a',
                  }}
                >
                  {fmtGreek(totals.theta)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    color: '#ffa726',
                  }}
                >
                  {fmtGreek(totals.vega)}
                </TableCell>
                <TableCell />
                <TableCell />
                <TableCell
                  align="right"
                  sx={{
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    fontSize: '0.875rem',
                    color: pnlColor(totals.pnl),
                  }}
                >
                  {totals.pnl >= 0 ? '+' : ''}${fmtNum(totals.pnl)}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
