/**
 * MMMConsolidatedPositions — Money Mind & Method
 *
 * Consolidated positions panel that groups scattered individual fills
 * (original, adjustment, frozen) into consolidated rows by (side, strike).
 *
 * Shows:
 * - Side (CE/PE), Strike, Total Lots, Notional BTC
 * - Weighted Average Entry Premium
 * - Current Market Premium (from heartbeat)
 * - Total P&L per consolidated position
 * - Position breakdown tooltip (how many original + adjustment + frozen)
 *
 * Created: February 18, 2026
 */

import React, { useMemo } from 'react';
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
} from '@mui/material';
import AcUnitIcon from '@mui/icons-material/AcUnit';
import {
  buildPositionRows,
  LOT_SIZE_BTC,
  CONFIRMED_STATUSES,
} from './MMMPositionsTable';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatNum(n, decimals = 2) {
  if (n == null || isNaN(n)) return '--';
  return Number(n).toFixed(decimals);
}

function pnlColor(pnl) {
  if (pnl > 0) return '#4caf50';
  if (pnl < 0) return '#f44336';
  return 'text.secondary';
}

/**
 * Build consolidated position rows by grouping individual fills.
 *
 * Groups by (side, strike) and aggregates:
 * - Total lots
 * - Weighted average entry premium
 * - Current premium (same for all fills at same strike)
 * - Total P&L
 * - Breakdown counts by type
 */
function buildConsolidatedRows(session, heartbeat) {
  const rows = buildPositionRows(session, heartbeat);
  if (rows.length === 0) return [];

  // Group by (side, strike)
  const groups = {};
  for (const row of rows) {
    const key = `${row.side}-${row.strike}`;
    if (!groups[key]) {
      groups[key] = {
        side: row.side,
        strike: row.strike,
        totalLots: 0,
        totalEntryWeighted: 0, // sum of (lots * entryPremium)
        currentPremium: row.currentPremium,
        totalPnl: 0,
        hasPnl: false,
        breakdown: { original: 0, adjustment: 0, frozen: 0 },
        isFrozen: true, // Will be set to false if any non-frozen entry exists
        rows: [],
      };
    }
    const g = groups[key];
    g.totalLots += row.lots;
    g.totalEntryWeighted += row.lots * (row.entryPremium || 0);
    if (row.pnl != null) {
      g.totalPnl += row.pnl;
      g.hasPnl = true;
    }
    g.breakdown[row.type] = (g.breakdown[row.type] || 0) + row.lots;
    if (row.type !== 'frozen') g.isFrozen = false;
    // Use the most recent non-null current premium
    if (row.currentPremium != null) g.currentPremium = row.currentPremium;
    g.rows.push(row);
  }

  // Convert to array and compute weighted avg entry
  return Object.values(groups).map((g) => ({
    key: `${g.side}-${g.strike}`,
    side: g.side,
    strike: g.strike,
    totalLots: g.totalLots,
    notionalBtc: g.totalLots * LOT_SIZE_BTC,
    avgEntry: g.totalLots > 0 ? g.totalEntryWeighted / g.totalLots : 0,
    currentPremium: g.currentPremium,
    totalPnl: g.hasPnl ? g.totalPnl : null,
    breakdown: g.breakdown,
    isFrozen: g.isFrozen,
    fillCount: g.rows.length,
    rows: g.rows,
  })).sort((a, b) => {
    // Active before frozen, CE before PE, then by strike
    if (a.isFrozen !== b.isFrozen) return a.isFrozen ? 1 : -1;
    if (a.side !== b.side) return a.side < b.side ? -1 : 1;
    return a.strike - b.strike;
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export default function MMMConsolidatedPositions({ session, heartbeat }) {
  const consolidated = useMemo(
    () => buildConsolidatedRows(session, heartbeat),
    [session, heartbeat]
  );

  const status = (session?.strategy_status || session?.status || 'IDLE').toUpperCase();

  if (consolidated.length === 0) {
    const isStarting = status === 'STARTING';
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary" sx={{ fontSize: '1rem' }}>
          {isStarting
            ? 'Placing orders... Consolidated positions will appear once orders are filled.'
            : 'No positions to consolidate.'}
        </Typography>
      </Box>
    );
  }

  const hasPremiumData = consolidated.some(
    (r) => r.currentPremium != null && r.currentPremium > 0
  );
  const grandPnl = consolidated.reduce((s, r) => s + (r.totalPnl || 0), 0);
  const grandLots = consolidated.reduce((s, r) => s + r.totalLots, 0);
  const grandNotional = grandLots * LOT_SIZE_BTC;

  return (
    <Box>
      {/* Explainer */}
      <Typography
        variant="caption"
        sx={{
          display: 'block',
          color: 'text.secondary',
          lineHeight: 1.5,
          mb: 1,
          fontStyle: 'italic',
          fontSize: '0.88rem',
          opacity: 0.75,
        }}
      >
        📊 Consolidated view groups all fills (original + adjustments + frozen) at
        the same strike into a single row. Weighted average entry reflects
        the blended cost across all fills.
      </Typography>

      {!hasPremiumData && (
        <Box
          sx={{
            p: 1.5,
            mb: 1,
            borderRadius: 1,
            backgroundColor: 'rgba(255,152,0,0.08)',
            border: '1px solid rgba(255,152,0,0.3)',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <Typography variant="caption" sx={{ color: '#ff9800' }}>
            ⏳ Waiting for heartbeat data... Current prices will update on next
            heartbeat interval.
          </Typography>
        </Box>
      )}

      <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ '& th': { fontWeight: 700, fontSize: '0.9rem' } }}>
              <Tooltip title="CE (Call) or PE (Put) side" arrow>
                <TableCell sx={{ cursor: 'help' }}>Side</TableCell>
              </Tooltip>
              <Tooltip title="Strike price" arrow>
                <TableCell align="right" sx={{ cursor: 'help' }}>Strike</TableCell>
              </Tooltip>
              <Tooltip
                title="Total lots across all fills (original + adjustment + frozen) at this strike"
                arrow
              >
                <TableCell align="right" sx={{ cursor: 'help' }}>Lots</TableCell>
              </Tooltip>
              <Tooltip title="Notional BTC exposure = Lots × 0.001 BTC" arrow>
                <TableCell align="right" sx={{ cursor: 'help' }}>BTC</TableCell>
              </Tooltip>
              <Tooltip
                title="Weighted average entry premium across all fills at this strike"
                arrow
              >
                <TableCell align="right" sx={{ cursor: 'help' }}>Avg Entry</TableCell>
              </Tooltip>
              <Tooltip title="Current market premium from latest heartbeat" arrow>
                <TableCell align="right" sx={{ cursor: 'help' }}>Current</TableCell>
              </Tooltip>
              <Tooltip
                title="Total P&L for all lots at this strike = Σ (entry - current) × lots × 0.001"
                arrow
              >
                <TableCell align="right" sx={{ cursor: 'help' }}>P&L</TableCell>
              </Tooltip>
              <Tooltip title="Number of individual fills grouped into this row" arrow>
                <TableCell align="center" sx={{ cursor: 'help' }}>Fills</TableCell>
              </Tooltip>
            </TableRow>
          </TableHead>
          <TableBody>
            {consolidated.map((row) => {
              const bd = row.breakdown;
              const breakdownText = [
                bd.original > 0 && `Original: ${bd.original} lots`,
                bd.adjustment > 0 && `Adjustment: ${bd.adjustment} lots`,
                bd.frozen > 0 && `Frozen: ${bd.frozen} lots`,
              ]
                .filter(Boolean)
                .join('\n');

              return (
                <TableRow
                  key={row.key}
                  sx={{
                    bgcolor: row.isFrozen
                      ? 'rgba(158,158,158,0.08)'
                      : 'transparent',
                    opacity: row.isFrozen ? 0.75 : 1,
                    '&:last-child td': { borderBottom: 0 },
                  }}
                >
                  {/* Side */}
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      {row.isFrozen && (
                        <AcUnitIcon sx={{ fontSize: '0.85rem', color: '#90caf9' }} />
                      )}
                      <Chip
                        label={row.side}
                        size="small"
                        sx={{
                          fontWeight: 700,
                          bgcolor:
                            row.side === 'CE'
                              ? 'rgba(33,150,243,0.15)'
                              : 'rgba(156,39,176,0.15)',
                          color: row.side === 'CE' ? '#2196f3' : '#9c27b0',
                        }}
                      />
                    </Box>
                  </TableCell>

                  {/* Strike */}
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                    {Number(row.strike).toLocaleString()}
                  </TableCell>

                  {/* Total Lots */}
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    {row.totalLots}
                  </TableCell>

                  {/* Notional BTC */}
                  <TableCell
                    align="right"
                    sx={{ fontFamily: 'monospace', fontSize: '0.88rem' }}
                  >
                    {row.notionalBtc.toFixed(3)}
                  </TableCell>

                  {/* Weighted Avg Entry */}
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                    {formatNum(row.avgEntry)}
                  </TableCell>

                  {/* Current Premium */}
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                    {row.currentPremium != null && row.currentPremium > 0 ? (
                      formatNum(row.currentPremium)
                    ) : row.currentPremium === 0 ? (
                      <Tooltip title="Premium is 0.00 — option may have expired or be deep OTM">
                        <span style={{ color: '#ff9800' }}>0.00</span>
                      </Tooltip>
                    ) : (
                      <Tooltip title="Waiting for heartbeat data">
                        <span>—</span>
                      </Tooltip>
                    )}
                  </TableCell>

                  {/* Total P&L */}
                  <TableCell
                    align="right"
                    sx={{
                      fontFamily: 'monospace',
                      fontWeight: 600,
                      color:
                        row.totalPnl != null
                          ? pnlColor(row.totalPnl)
                          : 'text.disabled',
                    }}
                  >
                    {row.totalPnl != null ? (
                      <Tooltip title={`${formatNum(row.totalPnl, 4)} BTC`}>
                        <span>
                          {row.totalPnl >= 0 ? '+' : ''}${formatNum(row.totalPnl)}
                        </span>
                      </Tooltip>
                    ) : (
                      '—'
                    )}
                  </TableCell>

                  {/* Fill Count with breakdown tooltip */}
                  <TableCell align="center">
                    <Tooltip
                      title={
                        <Box
                          sx={{
                            whiteSpace: 'pre-line',
                            fontSize: '0.9rem',
                            p: 0.5,
                          }}
                        >
                          <Typography
                            variant="subtitle2"
                            sx={{
                              fontWeight: 700,
                              mb: 0.5,
                              fontSize: '0.85rem',
                            }}
                          >
                            Position Breakdown
                          </Typography>
                          {breakdownText}
                        </Box>
                      }
                      arrow
                    >
                      <Chip
                        label={row.fillCount}
                        size="small"
                        variant="outlined"
                        sx={{
                          fontWeight: 600,
                          fontSize: '0.88rem',
                          cursor: 'help',
                          minWidth: 32,
                        }}
                      />
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}

            {/* Totals row */}
            <TableRow
              sx={{ '& td': { borderTop: '2px solid', borderColor: 'divider' } }}
            >
              <TableCell colSpan={2} sx={{ fontWeight: 700 }}>
                Total
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>
                {grandLots}
              </TableCell>
              <TableCell
                align="right"
                sx={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.88rem' }}
              >
                {grandNotional.toFixed(3)}
              </TableCell>
              <TableCell />
              <TableCell />
              <TableCell
                align="right"
                sx={{
                  fontFamily: 'monospace',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  color: pnlColor(grandPnl),
                }}
              >
                {grandPnl >= 0 ? '+' : ''}${formatNum(grandPnl)}
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 700 }}>
                {consolidated.length}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
