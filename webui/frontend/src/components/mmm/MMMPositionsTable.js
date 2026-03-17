/**
 * MMMPositionsTable — Money Mind & Method
 *
 * Live positions table showing all open positions:
 * - Original entry positions (CE + PE)
 * - Adjustment fills at active strikes
 * - Frozen positions at old strikes (from strike shifts)
 * - P&L per row (color-coded green/red)
 * - Position type badges (Original, Adj #N, FROZEN)
 * - Per-strike current premiums via premium_map from heartbeat
 * - Frozen position tooltips explaining why frozen
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §2 (State), §6 (Updates), §10 (Strike Shift)
 *
 * Created: February 15, 2026
 * Updated: February 16, 2026 — Fixed current market price display, frozen tooltips
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
  IconButton,
} from '@mui/material';
import AcUnitIcon from '@mui/icons-material/AcUnit';
import PushPinOutlinedIcon from '@mui/icons-material/PushPinOutlined';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';

const TYPE_COLORS = {
  original: { bg: 'rgba(33,150,243,0.1)', color: '#2196f3', label: 'Original' },
  adjustment: { bg: 'rgba(255,152,0,0.1)', color: '#ff9800', label: 'Adjustment' },
  frozen: { bg: 'rgba(158,158,158,0.15)', color: '#9e9e9e', label: 'FROZEN' },
};

function formatNum(n, decimals = 2) {
  if (n == null || isNaN(n)) return '--';
  return Number(n).toFixed(decimals);
}

function pnlColor(pnl) {
  if (pnl > 0) return '#4caf50';
  if (pnl < 0) return '#f44336';
  return 'text.secondary';
}

export const LOT_SIZE_BTC = 0.001; // 1 contract = 0.001 BTC on Delta Exchange

// Statuses that confirm orders have actually been filled on exchange
export const CONFIRMED_STATUSES = ['RUNNING', 'PAUSED', 'BOTH_SIDES_UP', 'PARTIAL_ENTRY', 'STOPPED'];

/**
 * Resolve the current premium for a given position.
 *
 * Priority:
 * 1. premium_map from WebSocket heartbeat (real-time, ALL strikes)
 * 2. Active strike premium from heartbeat (ce_premium/pe_premium)
 * 3. session._premium_map (persisted from last heartbeat — survives page reload)
 * 4. null (unknown — shown as "--" in the UI)
 *
 * NOTE: We intentionally do NOT use trigger_snapshot here.
 * trigger_snapshot is the trigger REFERENCE level (the premium at the time
 * of the last adjustment), not the current market price. Using it would
 * display wildly incorrect "current" prices.
 */
export function resolveCurrentPremium(strike, sideKey, heartbeat, session) {
  const optionType = sideKey === 'ce' ? 'call' : 'put';
  const mapKey = `${Math.round(strike)}:${optionType}`;

  // 1. Check premium_map from real-time WebSocket heartbeat
  const premiumMap = heartbeat?.premium_map || {};
  if (premiumMap[mapKey] != null && premiumMap[mapKey] !== 0) {
    return premiumMap[mapKey];
  }

  // 2. If this is the active strike, use the heartbeat's ce/pe premium
  const sideState = session?.[sideKey] || {};
  const activeStrike = sideState.active_strike;
  if (activeStrike && Math.abs(strike - activeStrike) < 1) {
    const hbPremium = sideKey === 'ce' ? heartbeat?.ce_premium : heartbeat?.pe_premium;
    if (hbPremium != null && hbPremium > 0) {
      return hbPremium;
    }
  }

  // 3. Fallback to session's persisted premium_map (from last heartbeat)
  // This is saved by the backend on every heartbeat and persists across page reloads
  const sessionPremiumMap = session?._premium_map || {};
  if (sessionPremiumMap[mapKey] != null && sessionPremiumMap[mapKey] !== 0) {
    return sessionPremiumMap[mapKey];
  }

  // 4. Unknown — DO NOT use trigger_snapshot (it's a trigger reference, not current price)
  return null;
}

export function buildPositionRows(session, heartbeat) {
  const rows = [];
  if (!session) return rows;

  const status = (session.strategy_status || session.status || 'IDLE').toUpperCase();
  const isConfirmed = CONFIRMED_STATUSES.includes(status);

  // Don't show positions if orders haven't actually been filled
  // (IDLE/STARTING sessions have premiums from config, not real fills)
  if (!isConfirmed) return rows;

  for (const sideKey of ['ce', 'pe']) {
    const side = session[sideKey];
    if (!side) continue;

    // Original lots — only show if there's an actual fill price
    const hasFill = side.entry_fill_price != null || isConfirmed;
    if (side.original_lots > 0 && hasFill) {
      const currentPremium = resolveCurrentPremium(
        side.active_strike, sideKey, heartbeat, session
      );
      const pnl = currentPremium != null
        ? (side.original_premium - currentPremium) * side.original_lots * LOT_SIZE_BTC
        : null;
      rows.push({
        id: `${sideKey}-orig`,
        side: sideKey.toUpperCase(),
        sideKey,
        strike: side.active_strike,
        isActiveFocalPoint: true,
        type: 'original',
        lots: side.original_lots,
        entryPremium: side.original_premium,
        currentPremium,
        pnl,
      });
    }

    // Adjustment fills
    (side.adjustment_fills || []).forEach((fill, i) => {
      const lots = fill.lots || 0;
      const prem = fill.premium || 0;
      const fillStrike = fill.strike || side.active_strike;
      const isActiveFocalPoint = Math.abs(fillStrike - (side.active_strike || 0)) < 1;
      const currentPremium = resolveCurrentPremium(
        fillStrike, sideKey, heartbeat, session
      );
      const pnl = currentPremium != null
        ? (prem - currentPremium) * lots * LOT_SIZE_BTC
        : null;
      rows.push({
        id: `${sideKey}-adj-${i}`,
        side: sideKey.toUpperCase(),
        sideKey,
        strike: fillStrike,
        isActiveFocalPoint,
        type: 'adjustment',
        typeLabel: `Adj #${i + 1}`,
        lots,
        entryPremium: prem,
        currentPremium,
        pnl,
        adjType: fill.type,
        timestamp: fill.timestamp,
      });
    });

    // Frozen positions
    const params = session?.params || {};
    const maxLots = params.max_lots_per_side || 100;
    const totalSideLots = side.total_lots || 0;
    const capacityPressure = totalSideLots / Math.max(maxLots, 1);

    (side.frozen_positions || []).forEach((frozen, i) => {
      const lots = frozen.lots || 0;
      const prem = frozen.entry_premium || 0;
      const frozenStrike = frozen.strike;

      // Resolve current premium at the frozen strike
      const currentPremium = resolveCurrentPremium(
        frozenStrike, sideKey, heartbeat, session
      );
      const pnl = currentPremium != null
        ? (prem - currentPremium) * lots * LOT_SIZE_BTC
        : null;

      // Build tooltip info for frozen explanation
      const frozenAt = frozen.frozen_at
        ? (() => {
            try {
              const ts = frozen.frozen_at;
              const d = (ts.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(ts))
                ? new Date(ts) : new Date(ts + 'Z');
              return isNaN(d.getTime()) ? 'Unknown' : d.toLocaleString();
            } catch { return 'Unknown'; }
          })()
        : 'Unknown';
      const frozenType = frozen.type === 'original' ? 'Original position' : 'Adjustment position';
      const frozenReason = `Strike Shift: Position moved from strike ${Number(frozenStrike).toLocaleString()} to a closer strike.\n`
        + `${frozenType} frozen at ${frozenAt}.\n`
        + `Monitored for Close-at-5 but excluded from adjustment calculations (§10).`;

      // M1/M2 eligibility badges
      const profitPct = (prem > 0 && currentPremium != null)
        ? (prem - currentPremium) / prem * 100 : 0;
      const isHarvestable = (params.harvest_enabled !== false)
        && profitPct >= (params.harvest_profit_pct || 40)
        && capacityPressure >= (params.harvest_pressure_threshold || 0.6);
      const isRecyclable = (params.recycle_enabled !== false)
        && currentPremium != null
        && currentPremium <= (params.recycle_premium_ceiling || 50)
        && !(params.recycle_protect_original !== false && frozen.type === 'original');
      const harvestScore = profitPct * (lots / Math.max(totalSideLots, 1));

      rows.push({
        id: `${sideKey}-frozen-${i}`,
        side: sideKey.toUpperCase(),
        sideKey,
        strike: frozenStrike,
        isActiveFocalPoint: false,
        type: 'frozen',
        typeLabel: frozen.type === 'original' ? 'FROZEN (Orig)' : `FROZEN (Adj)`,
        lots,
        entryPremium: prem,
        currentPremium,
        pnl,
        frozenReason,
        frozenAt: frozen.frozen_at,
        frozenType: frozen.type,
        isHarvestable,
        isRecyclable,
        harvestScore,
        profitPct,
      });
    });
  }

  return rows;
}

export default function MMMPositionsTable({ session, heartbeat, onSetActiveStrike, onCloseStrike }) {
  const rows = useMemo(
    () => buildPositionRows(session, heartbeat),
    [session, heartbeat]
  );

  const status = (session?.strategy_status || session?.status || 'IDLE').toUpperCase();
  const canOperate = ['RUNNING', 'PAUSED'].includes(status);

  if (rows.length === 0) {
    const isStarting = status === 'STARTING';
    const isIdle = status === 'IDLE' || status === 'CREATED';
    let message = 'No positions yet. Initialize a session to see positions.';
    if (isStarting) {
      message = 'Placing orders on exchange... Positions will appear once orders are filled.';
    } else if (isIdle && session?.ce?.original_lots > 0) {
      message = 'No confirmed fills. Orders were not successfully placed on the exchange.';
    }
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color={isIdle && session?.ce?.original_lots > 0 ? 'warning.main' : 'text.secondary'} sx={{ fontSize: '1rem' }}>
          {message}
        </Typography>
      </Box>
    );
  }

  // Check if we have any premium data at all
  const hasPremiumData = rows.some(r => r.currentPremium != null && r.currentPremium > 0);

  const totalPnl = rows.reduce((sum, r) => sum + (r.pnl || 0), 0);

  return (
    <Box>
      {/* Section explainer */}
      <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', lineHeight: 1.5, mb: 1, fontStyle: 'italic', fontSize: '0.88rem', opacity: 0.75 }}>
        💡 Three position types: <strong>Original</strong> = initial CE+PE sold at entry (naturally offset each other). <strong>Adjustment</strong> = extra lots sold to cover losses (naked risk). <strong>Frozen</strong> = old positions at previous strikes after a shift (tracked for close-at-5).
      </Typography>
      {/* Premium data warning */}
      {!hasPremiumData && (
        <Box sx={{
          p: 1.5,
          mb: 1,
          borderRadius: 1,
          backgroundColor: 'rgba(255,152,0,0.08)',
          border: '1px solid rgba(255,152,0,0.3)',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}>
          <Typography variant="caption" sx={{ color: '#ff9800' }}>
            ⏳ Waiting for heartbeat data... Current prices will update on next heartbeat interval.
          </Typography>
        </Box>
      )}

      <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ '& th': { fontWeight: 700, fontSize: '0.9rem' } }}>
              <Tooltip title="CE (Call) = profits when BTC drops. PE (Put) = profits when BTC drops. You sold both to collect premium." arrow>
                <TableCell sx={{ cursor: 'help' }}>Side</TableCell>
              </Tooltip>
              <Tooltip title="The strike price of the option. CE strikes are above BTC spot, PE strikes are below. After a shift, you'll have positions at multiple strikes." arrow>
                <TableCell align="right" sx={{ cursor: 'help' }}>Strike</TableCell>
              </Tooltip>
              <Tooltip title="Original = entry positions (safe, offset each other). Adjustment = extra lots sold to hedge (naked risk). Frozen = positions from before a strike shift." arrow>
                <TableCell sx={{ cursor: 'help' }}>Type</TableCell>
              </Tooltip>
              <Tooltip title="Number of contracts at this strike. Each lot = 0.001 BTC on Delta Exchange." arrow>
                <TableCell align="right" sx={{ cursor: 'help' }}>Lots</TableCell>
              </Tooltip>
              <Tooltip title="Premium at which you SOLD this position. You collected this amount. You want it to go DOWN to profit." arrow>
                <TableCell align="right" sx={{ cursor: 'help' }}>Entry</TableCell>
              </Tooltip>
              <Tooltip title="Current market premium for this option. If lower than Entry = you're profiting. If higher = you're losing on this position." arrow>
                <TableCell align="right" sx={{ cursor: 'help' }}>Current</TableCell>
              </Tooltip>
              <Tooltip title="P&L for this row = (Entry - Current) × Lots × 0.001 BTC × BTC price. Positive = profit, negative = loss." arrow>
                <TableCell align="right" sx={{ cursor: 'help' }}>P&L</TableCell>
              </Tooltip>
              <TableCell align="center" sx={{ width: 90 }}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => {
              const typeCfg = TYPE_COLORS[row.type] || TYPE_COLORS.original;
              const isFrozen = row.type === 'frozen';

              return (
                <TableRow
                  key={row.id}
                  sx={{
                    bgcolor: typeCfg.bg,
                    opacity: isFrozen ? 0.75 : 1,
                    '&:last-child td': { borderBottom: 0 },
                  }}
                >
                  <TableCell>
                    <Chip
                      label={row.side}
                      size="small"
                      sx={{
                        fontWeight: 700,
                        bgcolor: row.side === 'CE' ? 'rgba(33,150,243,0.15)' : 'rgba(156,39,176,0.15)',
                        color: row.side === 'CE' ? '#2196f3' : '#9c27b0',
                      }}
                    />
                  </TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                    {Number(row.strike).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
                      {isFrozen ? (
                        <Tooltip
                          title={
                            <Box sx={{ whiteSpace: 'pre-line', fontSize: '0.85rem', p: 0.5 }}>
                              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5, fontSize: '0.8rem' }}>
                                ❄️ Frozen Position
                              </Typography>
                              {row.frozenReason}
                            </Box>
                          }
                          arrow
                          placement="top"
                        >
                          <Chip
                            icon={<AcUnitIcon sx={{ fontSize: '0.8rem !important' }} />}
                            label={row.typeLabel || typeCfg.label}
                            size="small"
                            variant="outlined"
                            sx={{
                              color: typeCfg.color,
                              borderColor: typeCfg.color,
                              fontSize: '0.88rem',
                              cursor: 'help',
                              '& .MuiChip-icon': { color: '#90caf9' },
                            }}
                          />
                        </Tooltip>
                      ) : (
                        <Chip
                          label={row.typeLabel || typeCfg.label}
                          size="small"
                          variant="outlined"
                          sx={{ color: typeCfg.color, borderColor: typeCfg.color, fontSize: '0.88rem' }}
                        />
                      )}
                      {row.isHarvestable && (
                        <Tooltip title={`M1 Harvestable — ${row.profitPct.toFixed(0)}% profit, score ${row.harvestScore.toFixed(1)}`} arrow placement="top">
                          <Chip
                            label="🌾"
                            size="small"
                            sx={{ height: 18, fontSize: '0.7rem', bgcolor: 'rgba(76,175,80,0.15)', color: '#4caf50', cursor: 'help', minWidth: 0, px: 0.25 }}
                          />
                        </Tooltip>
                      )}
                      {row.isRecyclable && !row.isHarvestable && (
                        <Tooltip title="M2 Recyclable — low premium, eligible for lot recycling" arrow placement="top">
                          <Chip
                            label="♻️"
                            size="small"
                            sx={{ height: 18, fontSize: '0.7rem', bgcolor: 'rgba(33,150,243,0.12)', color: '#2196f3', cursor: 'help', minWidth: 0, px: 0.25 }}
                          />
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 600 }}>
                    {row.lots}
                  </TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                    {formatNum(row.entryPremium)}
                  </TableCell>
                  <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                    {row.currentPremium != null && row.currentPremium > 0 ? (
                      formatNum(row.currentPremium)
                    ) : row.currentPremium === 0 ? (
                      <Tooltip title="Premium is 0.00 — option may have expired or be deep OTM">
                        <span style={{ color: '#ff9800' }}>0.00</span>
                      </Tooltip>
                    ) : (
                      <Tooltip title="Waiting for heartbeat data to fetch current price">
                        <span>—</span>
                      </Tooltip>
                    )}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      fontFamily: 'monospace',
                      fontWeight: 600,
                      color: row.pnl != null ? pnlColor(row.pnl) : 'text.disabled',
                    }}
                  >
                    {row.pnl != null ? (
                      <Tooltip title={`${formatNum(row.pnl, 4)} BTC`}>
                        <span>
                          {row.pnl >= 0 ? '+' : ''}${formatNum(row.pnl)}
                        </span>
                      </Tooltip>
                    ) : (
                      <Tooltip title="P&L unavailable — waiting for current premium data">
                        <span>—</span>
                      </Tooltip>
                    )}
                  </TableCell>
                  {/* Actions column */}
                  <TableCell align="center" sx={{ whiteSpace: 'nowrap', p: 0.5 }}>
                    {canOperate && !row.isActiveFocalPoint && onSetActiveStrike && (
                      <Tooltip
                        title={isFrozen
                          ? `Promote ${row.side} ${Number(row.strike).toLocaleString()} to active strike — re-activates this frozen position for monitoring`
                          : `Set ${row.side} active strike to ${Number(row.strike).toLocaleString()} — algo will monitor this strike`}
                        arrow
                      >
                        <IconButton
                          size="small"
                          onClick={() => onSetActiveStrike(row.sideKey, row.strike)}
                          sx={{ color: isFrozen ? '#ff9800' : '#42a5f5', p: 0.5 }}
                        >
                          <PushPinOutlinedIcon sx={{ fontSize: '1rem' }} />
                        </IconButton>
                      </Tooltip>
                    )}
                    {canOperate && onCloseStrike && (
                      <Tooltip
                        title={`Close ALL ${row.lots} lots of ${row.side} @ ${Number(row.strike).toLocaleString()} — places buyback order on exchange`}
                        arrow
                      >
                        <IconButton
                          size="small"
                          onClick={() => onCloseStrike(row.sideKey, row.strike, row.lots, row.currentPremium)}
                          sx={{ color: '#ef5350', p: 0.5 }}
                        >
                          <CancelOutlinedIcon sx={{ fontSize: '1rem' }} />
                        </IconButton>
                      </Tooltip>
                    )}
                    {(!canOperate || (!onSetActiveStrike && !onCloseStrike)) && (
                      <span style={{ color: 'transparent' }}>—</span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}

            {/* Total row */}
            <TableRow sx={{ '& td': { borderTop: '2px solid', borderColor: 'divider' } }}>
              <TableCell colSpan={6} align="right" sx={{ fontWeight: 700 }}>
                <Tooltip title="Sum of (Entry − Current) × Lots for all open positions. Does not include realized P&L from closed positions." arrow>
                  <span style={{ cursor: 'help' }}>Open Position P&L</span>
                </Tooltip>
              </TableCell>
              {/* P&L value */}
              <TableCell
                align="right"
                sx={{
                  fontFamily: 'monospace',
                  fontWeight: 700,
                  fontSize: '0.875rem',
                  color: pnlColor(totalPnl),
                }}
              >
                {totalPnl >= 0 ? '+' : ''}${formatNum(totalPnl)}
              </TableCell>
              {/* Empty Actions cell in total row */}
              <TableCell />
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
