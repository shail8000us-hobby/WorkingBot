/**
 * PositionRow Component
 *
 * ARCH-2: Extracted from OptionsPanel.js monolith.
 * Renders a single position row in the options table.
 * Wrapped in React.memo to prevent re-renders when only unrelated state changes.
 *
 * This is the largest JSX block (~700 lines) extracted from the monolith,
 * giving the biggest performance win since each row now only re-renders
 * when its own position data or settings change.
 *
 * Created: February 26, 2026 (ARCH-2 refactor)
 *
 * @sealed — Actions column (C+/P+ scale, Roll, Close/Remove buttons)
 * Sealed: Mar 12, 2026 — Test: src/components/options/__tests__/test_sealed_position_row_actions.test.js
 */

import React, { useRef, useEffect, useCallback } from 'react';
import {
    TableCell,
    Box,
    Chip,
    Tooltip,
    Typography,
    Checkbox,
    TextField,
    IconButton,
    Button,
} from '@mui/material';
import {
    TrendingUp,
    TrendingDown,
    Close as CloseIcon,
    DragIndicator as DragIcon,
    Visibility as VisibilityIcon,
    Timer as TimerIcon,
    Label as LabelIcon,
    BookmarkBorder as BookmarkBorderIcon,
    Bookmark as BookmarkIcon,
} from '@mui/icons-material';
import SLTPIndicator from './SLTPIndicator';
import MaxLossIndicator from './MaxLossIndicator';
import TakeProfitIndicator from './TakeProfitIndicator';
import { AutomationButton } from './automation';

// Utility functions (same as in OptionsPanel — module-level for stable references)
const formatPnl = (pnl) => {
    const numPnl = Number(pnl) || 0;
    const formatted = Math.abs(numPnl).toFixed(4);
    return numPnl >= 0 ? `+$${formatted}` : `-$${formatted}`;
};

const formatPnlPct = (pct) => {
    const numPct = Number(pct) || 0;
    const formatted = Math.abs(numPct).toFixed(2);
    return numPct >= 0 ? `+${formatted}%` : `-${formatted}%`;
};

const formatUsd = (value) => {
    const num = Number(value) || 0;
    if (num >= 1000 || num <= -1000) {
        return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return '$' + num.toFixed(2);
};

const getPnlColor = (pnl) => {
    if (pnl > 0) return '#10b981';
    if (pnl < 0) return '#ef4444';
    return '#94a3b8';
};

const getPositionType = (symbol) => {
    if (symbol.startsWith('C-')) return { type: 'CALL', color: '#3b82f6' };
    if (symbol.startsWith('P-')) return { type: 'PUT', color: '#a855f7' };
    if (symbol.startsWith('MV-')) return { type: 'MV STRADDLE', color: '#00bcd4' };
    return { type: 'UNKNOWN', color: '#6b7280' };
};

// ─── Option 1: Quick-fill preset buttons + Option 3: Scroll wheel ────────────
// Extracted as a separate component so it can use hooks (useRef/useEffect/useCallback)
// without forcing PositionRow to re-render on scroll activation state changes.
function BatchQtyCell({ pos, batchQty, savedBatchQtyValue, cellSx, onBatchQtyChange, onSaveBatchQty, onUnsaveBatchQty }) {
    const wheelRef = useRef(null);

    // Stable ref for the wheel handler so we don't re-attach the listener on every batchQty change
    const wheelHandlerRef = useRef(null);
    wheelHandlerRef.current = useCallback((e) => {
        e.preventDefault();
        const delta = e.deltaY < 0 ? 1 : -1;
        const current = batchQty || 0;
        let next = current + delta;
        if (next === 0) next = delta;  // skip 0
        onBatchQtyChange(pos.product_symbol, next);
    }, [batchQty, onBatchQtyChange, pos.product_symbol]);

    // Non-passive wheel listener so preventDefault() actually stops page scroll
    useEffect(() => {
        const el = wheelRef.current;
        if (!el) return;
        const handler = (e) => wheelHandlerRef.current(e);
        el.addEventListener('wheel', handler, { passive: false });
        return () => el.removeEventListener('wheel', handler);
    }, []); // attach once; current value is accessed via wheelHandlerRef

    const QUICK_PRESETS = [1, 5, 10, 25];

    return (
        <TableCell align="center" sx={cellSx}>
            <Box ref={wheelRef} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
                {/* Main input + bookmark */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
                    <TextField
                        size="small"
                        type="number"
                        placeholder="±qty"
                        value={batchQty || ''}
                        onChange={(e) => {
                            const value = e.target.value === '' ? 0 : parseInt(e.target.value);
                            onBatchQtyChange(pos.product_symbol, value);
                        }}
                        inputProps={{
                            // Suppress native number-input scroll so our wheel handler is the only one
                            onWheel: (e) => e.target.blur(),
                        }}
                        sx={{
                            width: '60px',
                            '& .MuiInputBase-input': {
                                textAlign: 'center',
                                fontSize: '0.875rem',
                                padding: '4px 6px',
                                color: batchQty > 0 ? '#10b981' : batchQty < 0 ? '#ef4444' : 'inherit',
                            },
                        }}
                    />
                    <Tooltip
                        title={
                            savedBatchQtyValue
                                ? `Saved: ${savedBatchQtyValue > 0 ? '+' : ''}${savedBatchQtyValue} — click to unsave`
                                : batchQty
                                ? `Save ${batchQty > 0 ? '+' : ''}${batchQty} for this strike`
                                : 'Enter a qty first, then save'
                        }
                    >
                        <span>
                            <IconButton
                                size="small"
                                disabled={!savedBatchQtyValue && !batchQty}
                                onClick={() => {
                                    if (savedBatchQtyValue) {
                                        onUnsaveBatchQty(pos.product_symbol);
                                    } else {
                                        onSaveBatchQty(pos.product_symbol, batchQty);
                                    }
                                }}
                                sx={{ padding: '2px' }}
                            >
                                {savedBatchQtyValue ? (
                                    <BookmarkIcon sx={{ fontSize: '0.9rem', color: '#06b6d4' }} />
                                ) : (
                                    <BookmarkBorderIcon sx={{ fontSize: '0.9rem', color: 'text.disabled' }} />
                                )}
                            </IconButton>
                        </span>
                    </Tooltip>
                </Box>

                {/* Option 1 — Quick-fill preset buttons (+N, sign-aware) */}
                <Tooltip title="Click to set qty (preserves sign if already negative). Right-click for opposite sign.">
                    <Box sx={{ display: 'flex', gap: '2px' }}>
                        {QUICK_PRESETS.map((preset) => (
                            <Button
                                key={preset}
                                size="small"
                                variant="outlined"
                                onClick={() => {
                                    // preserve current sign; default to positive
                                    const sign = batchQty < 0 ? -1 : 1;
                                    onBatchQtyChange(pos.product_symbol, sign * preset);
                                }}
                                onContextMenu={(e) => {
                                    e.preventDefault();
                                    const sign = batchQty >= 0 ? -1 : 1;  // flip sign on right-click
                                    onBatchQtyChange(pos.product_symbol, sign * preset);
                                }}
                                sx={{
                                    minWidth: 0,
                                    px: '4px',
                                    py: '1px',
                                    fontSize: '0.6rem',
                                    lineHeight: 1.2,
                                    color: batchQty < 0 ? '#ef4444' : '#10b981',
                                    borderColor: batchQty < 0 ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)',
                                    '&:hover': {
                                        borderColor: batchQty < 0 ? '#ef4444' : '#10b981',
                                        bgcolor: batchQty < 0 ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)',
                                    },
                                }}
                            >
                                {preset}
                            </Button>
                        ))}
                    </Box>
                </Tooltip>

                {/* Saved value quick-load */}
                {savedBatchQtyValue && savedBatchQtyValue !== batchQty && (
                    <Tooltip title={`Load saved qty: ${savedBatchQtyValue > 0 ? '+' : ''}${savedBatchQtyValue}`}>
                        <Typography
                            variant="caption"
                            onClick={() => onBatchQtyChange(pos.product_symbol, savedBatchQtyValue)}
                            sx={{
                                fontSize: '0.65rem',
                                color: '#06b6d4',
                                cursor: 'pointer',
                                lineHeight: 1,
                                '&:hover': { textDecoration: 'underline' },
                            }}
                        >
                            📌 {savedBatchQtyValue > 0 ? '+' : ''}{savedBatchQtyValue}
                        </Typography>
                    </Tooltip>
                )}
            </Box>
        </TableCell>
    );
}

/**
 * Single position row for the options table.
 *
 * Props are intentionally flat to enable React.memo shallow comparison.
 */
// 🔒 SEALED #65 — test: test_sealed_position_row_actions.test.js
function PositionRow({
    pos,
    index,
    optionInfo,
    posType,
    daysToExp,
    isClosed,
    effectiveSize,
    cashflow,
    cellSx,
    rowBgColor,
    rowHoverColor,
    isCall,
    isPut,
    isLong,
    isQuickMode,
    // Column visibility
    visibleColumns,
    // Selection states
    isSelected,
    isPayoffSelected,
    batchQty,
    // Settings
    slTpSetting,
    maxLossSetting,
    tpSetting,
    popValue,
    posGreeks,
    ivrData,
    feesPaid,
    skipConfirmStrike,
    scalingRecommendation,
    // Callbacks
    onToggleStrikeSelection,
    onTogglePayoffSelection,
    onToggleHidden,
    onBatchQtyChange,
    savedBatchQtyValue,
    onSaveBatchQty,
    onUnsaveBatchQty,
    onSetSLTP,
    onSetTP,
    onMaxLossUpdate,
    onTakeProfitUpdate,
    onHandleAdd,
    onHandleClose,
    onRoll,
    onDisableSkipConfirm,
    onRemoveClosedPosition,
    // Context
    status,
    closedPositionData,
    DEFAULT_SIZE,
    // Drag handle props are passed through children render prop
    attributes,
    listeners,
    // Group assignment (optional — only passed when groups exist)
    onGroupClick,
}) {
    return (
        <>
            {/* Selection Checkbox */}
            <TableCell
                padding="checkbox"
                sx={{
                    backgroundColor: `${rowBgColor} !important`,
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Checkbox
                        checked={!!isSelected}
                        onChange={() => onToggleStrikeSelection(pos.product_symbol)}
                        sx={{
                            color: isCall ? '#10b981' : '#ef4444',
                            '&.Mui-checked': { color: isCall ? '#10b981' : '#ef4444' },
                        }}
                    />
                </Box>
            </TableCell>

            {/* Drag Handle */}
            <TableCell
                sx={{
                    backgroundColor: `${rowBgColor} !important`,
                    borderLeft: `3px solid ${posType.color}`,
                    cursor: 'grab',
                    '&:active': { cursor: 'grabbing' },
                    p: '0 4px',
                }}
                {...attributes}
                {...listeners}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                    <Tooltip title="Drag to reorder positions. Your custom order will be saved.">
                        <DragIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                    </Tooltip>
                    {onGroupClick && (
                        <Tooltip title="Assign to group">
                            <IconButton
                                size="small"
                                onClick={onGroupClick}
                                sx={{
                                    p: 0.25,
                                    color: 'text.secondary',
                                    opacity: 0.6,
                                    '&:hover': { opacity: 1, color: 'primary.main' },
                                }}
                            >
                                <LabelIcon sx={{ fontSize: 14 }} />
                            </IconButton>
                        </Tooltip>
                    )}
                </Box>
            </TableCell>

            {/* Symbol */}
            {visibleColumns.symbol && (
                <TableCell
                    sx={{
                        backgroundColor: `${rowBgColor} !important`,
                        '&:hover': { backgroundColor: `${rowHoverColor} !important` },
                    }}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Tooltip
                            title={
                                isPayoffSelected
                                    ? 'Selected for payoff graph'
                                    : 'Click to include in payoff graph'
                            }
                        >
                            <Checkbox
                                checked={isPayoffSelected}
                                onChange={() => onTogglePayoffSelection(pos.product_symbol)}
                                sx={{ color: '#3b82f6', '&.Mui-checked': { color: '#3b82f6' } }}
                            />
                        </Tooltip>
                        <Chip
                            label={optionInfo.type}
                            size="small"
                            sx={{
                                bgcolor: posType.color + '20',
                                color: posType.color,
                                fontWeight: 'bold',
                                minWidth: 50,
                            }}
                        />
                        <Typography variant="body2" fontWeight="medium">
                            {optionInfo.underlying}
                        </Typography>
                    </Box>
                </TableCell>
            )}

            {/* Hide/Show Button */}
            <TableCell align="center" sx={cellSx} width="50px">
                <Tooltip title="Hide from table and payoff graph">
                    <IconButton
                        size="small"
                        onClick={() => onToggleHidden(pos.product_symbol)}
                        sx={{ opacity: 0.7, '&:hover': { opacity: 1 } }}
                    >
                        <VisibilityIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                </Tooltip>
            </TableCell>

            {/* Strike */}
            {visibleColumns.strike && (
                <TableCell align="right" sx={cellSx}>
                    <Typography fontWeight="bold">
                        ${optionInfo.strike.toLocaleString()}
                    </Typography>
                </TableCell>
            )}

            {/* Automation */}
            {visibleColumns.auto && (
                <TableCell align="center" sx={{ ...cellSx, p: 0.5 }}>
                    <AutomationButton position={pos} />
                </TableCell>
            )}

            {/* Expiry */}
            {visibleColumns.expiry && (
                <TableCell align="right" sx={cellSx}>
                    {(() => {
                        const hoursLeft = daysToExp * 24;
                        const isExpiredOrExpiring = daysToExp < 1;
                        const countdownLabel = isExpiredOrExpiring
                            ? hoursLeft <= 0
                                ? 'EXPIRY'
                                : hoursLeft < 1
                                    ? `${Math.floor(hoursLeft * 60)}m`
                                    : `${Math.floor(hoursLeft)}h ${Math.floor((hoursLeft % 1) * 60)}m`
                            : daysToExp < 2
                                ? `1d ${Math.floor((daysToExp % 1) * 24)}h`
                                : optionInfo.expiry;
                        const urgencyColor = hoursLeft <= 0
                            ? '#666'
                            : daysToExp < 0.125
                                ? '#ef4444'
                                : daysToExp < 1
                                    ? '#f59e0b'
                                    : undefined;
                        return (
                            <Tooltip title={`${(Number(daysToExp) || 0).toFixed(2)} days to expiry (${optionInfo.expiry})`}>
                                <Chip
                                    label={isExpiredOrExpiring ? `⏰ ${countdownLabel}` : countdownLabel}
                                    size="small"
                                    variant={isExpiredOrExpiring ? 'filled' : 'outlined'}
                                    icon={isExpiredOrExpiring ? undefined : <TimerIcon />}
                                    sx={{
                                        borderColor: urgencyColor,
                                        color: urgencyColor,
                                        bgcolor: isExpiredOrExpiring && daysToExp > 0 ? `${urgencyColor}15` : undefined,
                                        fontWeight: isExpiredOrExpiring ? 'bold' : undefined,
                                        animation: daysToExp > 0 && daysToExp < 0.04 ? 'pulse 1s infinite' : 'none',
                                        '@keyframes pulse': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.5 } },
                                    }}
                                />
                            </Tooltip>
                        );
                    })()}
                </TableCell>
            )}

            {/* Size */}
            {visibleColumns.size && (
                <TableCell align="right" sx={cellSx}>
                    {isClosed ? (
                        <Chip
                            label="CLOSED"
                            size="small"
                            sx={{
                                bgcolor: 'rgba(100, 100, 100, 0.2)',
                                color: '#888',
                                fontWeight: 'bold',
                                fontSize: '0.65rem',
                            }}
                        />
                    ) : (
                        <Chip
                            icon={isLong ? <TrendingUp /> : <TrendingDown />}
                            label={Math.abs(pos.size)}
                            size="small"
                            sx={{
                                bgcolor: isLong ? '#10b98120' : '#ef444420',
                                color: isLong ? '#10b981' : '#ef4444',
                            }}
                        />
                    )}
                </TableCell>
            )}

            {/* Batch Quantity Input */}
            {visibleColumns.batchQty && (
                <BatchQtyCell
                    pos={pos}
                    batchQty={batchQty}
                    savedBatchQtyValue={savedBatchQtyValue}
                    cellSx={cellSx}
                    onBatchQtyChange={onBatchQtyChange}
                    onSaveBatchQty={onSaveBatchQty}
                    onUnsaveBatchQty={onUnsaveBatchQty}
                />
            )}

            {/* Cashflow */}
            {visibleColumns.cashflow && (
                <TableCell align="right" sx={cellSx}>
                    <Tooltip title={
                        <Box>
                            <Typography variant="caption" display="block" fontWeight="bold">Cashflow Breakdown</Typography>
                            <Typography variant="caption" display="block">
                                Entry: ${(Number(pos.entry_price) || 0).toFixed(2)} × Size: {Math.abs(pos.size || 0)} × Multiplier: 0.001
                            </Typography>
                            <Typography variant="caption" display="block">
                                = {formatUsd(Number(cashflow) || 0)} {effectiveSize > 0 ? '(paid)' : '(received)'}
                            </Typography>
                        </Box>
                    }>
                        <Typography
                            variant="body2"
                            fontWeight="medium"
                            sx={{ color: effectiveSize > 0 ? '#ef4444' : '#10b981' }}
                        >
                            {formatUsd(Number(cashflow) || 0)}
                        </Typography>
                    </Tooltip>
                </TableCell>
            )}

            {/* Entry Price */}
            {visibleColumns.entry && (
                <TableCell align="right" sx={cellSx}>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {formatUsd(Number(pos.entry_price) || 0)}
                    </Typography>
                </TableCell>
            )}

            {/* Bid Price */}
            {visibleColumns.bid && (
                <TableCell align="right" sx={cellSx}>
                    <Typography variant="body2" sx={{ color: '#10b981', fontFamily: 'monospace' }}>
                        {formatUsd(Number(pos.best_bid) || 0)}
                    </Typography>
                </TableCell>
            )}

            {/* Ask Price with Spread indicator */}
            {visibleColumns.ask && (
                <TableCell align="right" sx={cellSx}>
                    {(() => {
                        const bid = Number(pos.best_bid) || 0;
                        const ask = Number(pos.best_ask) || 0;
                        const mid = (bid + ask) / 2;
                        const spreadAbs = ask - bid;
                        const spreadPct = mid > 0 ? (spreadAbs / mid * 100) : 0;
                        const spreadColor = spreadPct > 5 ? '#ef4444' : spreadPct > 1 ? '#f59e0b' : '#10b981';
                        return (
                            <Tooltip title={mid > 0 ? `Spread: ${formatUsd(spreadAbs)} (${spreadPct.toFixed(1)}%) · Mid: ${formatUsd(mid)}` : ''}>
                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                                    <Typography variant="body2" sx={{ color: '#ef4444', fontFamily: 'monospace' }}>
                                        {formatUsd(ask)}
                                    </Typography>
                                    {mid > 0 && (
                                        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: spreadColor, flexShrink: 0 }} />
                                    )}
                                </Box>
                            </Tooltip>
                        );
                    })()}
                </TableCell>
            )}

            {/* SL/TP Indicator */}
            {visibleColumns.sltp && (
                <TableCell align="center" sx={cellSx}>
                    <SLTPIndicator
                        settings={slTpSetting}
                        position={pos}
                        onEdit={() => onSetSLTP(pos)}
                    />
                </TableCell>
            )}

            {/* Max Loss Indicator */}
            {visibleColumns.maxLoss && (
                <TableCell align="center" sx={cellSx}>
                    <MaxLossIndicator
                        symbol={pos.product_symbol}
                        currentPnl={pos.unrealized_pnl || 0}
                        settings={maxLossSetting}
                        onUpdate={onMaxLossUpdate}
                    />
                </TableCell>
            )}

            {/* Take Profit Indicator */}
            {visibleColumns.takeProfit && (
                <TableCell align="center" sx={cellSx}>
                    <TakeProfitIndicator
                        symbol={pos.product_symbol}
                        currentPnl={pos.unrealized_pnl || 0}
                        currentSize={Math.abs(pos.size || 0)}
                        settings={tpSetting}
                        onEdit={() => onSetTP(pos)}
                        onUpdate={onTakeProfitUpdate}
                    />
                </TableCell>
            )}

            {/* IV */}
            {visibleColumns.iv && (
                <TableCell align="right" sx={cellSx}>
                    {(() => {
                        if (!pos.iv) return <Typography variant="body2">-</Typography>;
                        const ivPct = pos.iv * 100;
                        const suspicious = ivPct < 15 || ivPct > 200;
                        return (
                            <Tooltip title={suspicious ? `IV ${ivPct.toFixed(1)}% may be unreliable — ${ivPct < 15 ? 'unusually low for options' : 'unusually high, check data quality'}` : `IV: ${ivPct.toFixed(1)}%`}>
                                <Typography variant="body2" sx={{ color: suspicious ? '#f59e0b' : undefined, fontWeight: suspicious ? 'bold' : undefined }}>
                                    {`${ivPct.toFixed(1)}%`}
                                    {suspicious && <Typography component="span" sx={{ fontSize: '0.6rem', ml: 0.3 }}>⚠</Typography>}
                                </Typography>
                            </Tooltip>
                        );
                    })()}
                </TableCell>
            )}

            {/* PoP */}
            {visibleColumns.pop && (
                <TableCell align="center" sx={cellSx}>
                    {popValue !== undefined ? (
                        popValue === -1 ? (
                            <Tooltip title="PoP calculation unavailable for this position">
                                <Typography variant="body2" color="text.secondary">N/A</Typography>
                            </Tooltip>
                        ) : (
                            <Tooltip title={
                                popValue < 1
                                    ? 'Very low probability of profit'
                                    : popValue > 99
                                        ? 'Very high probability of profit'
                                        : `${popValue.toFixed(1)}% chance of profit at expiry`
                            }>
                                <Chip
                                    label={
                                        popValue < 1 ? '< 1%' : popValue > 99 ? '> 99%' : `${popValue.toFixed(1)}%`
                                    }
                                    size="small"
                                    sx={{
                                        bgcolor: popValue > 50 ? 'success.main' : popValue < 20 ? 'error.main' : 'warning.main',
                                        color: 'white',
                                        fontWeight: 'bold',
                                        fontSize: '0.75rem',
                                        height: 22,
                                    }}
                                />
                            </Tooltip>
                        )
                    ) : (
                        <Typography variant="body2" color="text.secondary">-</Typography>
                    )}
                </TableCell>
            )}

            {/* PnL */}
            {visibleColumns.pnl && (
                <TableCell align="right" sx={cellSx}>
                    {(() => {
                        const unrealizedPnl = Number(pos.unrealized_pnl) || 0;
                        const realizedPnl = Number(pos.realized_pnl) || 0;
                        // Closed rows: unrealized=0, realized=cumulative from store. Live rows: both from exchange.
                        const totalPnl = isClosed ? realizedPnl : unrealizedPnl + realizedPnl;
                        const totalPnlColor = getPnlColor(totalPnl);
                        const rawPct = pos.pnl_percentage || 0;
                        const cashflowVal = Number(pos.cashflow) || 0;

                        // P3-B: % return for closed rows
                        const entryPrice = Number(pos.entry_price) || 0;
                        const origSize   = Math.abs(Number(pos.original_size) || 0);
                        const cost       = entryPrice * origSize * 0.001;
                        const returnPct  = cost > 0 ? (realizedPnl / cost) * 100 : null;

                        const tooltipText = (() => {
                            if (isClosed) {
                                const pctStr = returnPct != null ? ` (${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(1)}%)` : '';
                                return `Realized PnL: ${formatPnl(realizedPnl)}${pctStr}`;
                            }
                            if (realizedPnl !== 0) {
                                return `Unrealized: ${formatPnl(unrealizedPnl)} + Realized: ${formatPnl(realizedPnl)} = Total: ${formatPnl(totalPnl)}`;
                            }
                            if (Math.abs(rawPct) > 200 && cashflowVal !== 0) {
                                return `Raw PnL %: ${rawPct.toFixed(1)}% (vs cashflow $${Math.abs(cashflowVal).toFixed(2)}). Large % due to small premium denominator.`;
                            }
                            return `PnL: ${formatPnl(unrealizedPnl)} (${rawPct.toFixed(1)}%)`;
                        })();

                        return (
                            <Tooltip title={tooltipText}>
                                <Box>
                                    <Typography fontWeight="bold" sx={{ color: totalPnlColor }}>
                                        {formatPnl(totalPnl)}
                                    </Typography>
                                    {isClosed ? (
                                        <Typography variant="caption" sx={{ color: getPnlColor(realizedPnl), fontStyle: 'italic' }}>
                                            {returnPct != null
                                                ? `${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(1)}% realized`
                                                : 'Realized'}
                                        </Typography>
                                    ) : realizedPnl !== 0 ? (
                                        <Typography variant="caption" sx={{ color: getPnlColor(realizedPnl), fontStyle: 'italic' }}>
                                            incl. {formatPnl(realizedPnl)} realized
                                        </Typography>
                                    ) : (
                                        <Typography variant="caption" sx={{ color: totalPnlColor }}>
                                            {(() => {
                                                const pct = pos.pnl_percentage || 0;
                                                if (pct > 200) return '>+200%';
                                                if (pct < -200) return '<-200%';
                                                return formatPnlPct(pct);
                                            })()}
                                        </Typography>
                                    )}
                                </Box>
                            </Tooltip>
                        );
                    })()}
                </TableCell>
            )}

            {/* F2: IVR — IV Rank badge */}
            {visibleColumns.ivr && (
                <TableCell align="center" sx={cellSx}>
                    {ivrData ? (() => {
                        const ivr = ivrData.ivr;
                        const color = ivr <= 30 ? '#10b981' : ivr <= 60 ? '#f59e0b' : '#ef4444';
                        const label = ivr <= 30 ? 'Low' : ivr <= 60 ? 'Mid' : 'Rich';
                        const bgColor = ivr <= 30 ? 'rgba(16,185,129,0.15)' : ivr <= 60 ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)';
                        return (
                            <Tooltip title={`IVP: ${ivrData.ivp} | 52W: ${ivrData.low_52w}%–${ivrData.high_52w}%`}>
                                <Chip
                                    label={`${label} ${ivr.toFixed(0)}`}
                                    size="small"
                                    sx={{ bgcolor: bgColor, color, fontSize: '0.6rem', height: 18, fontWeight: 600 }}
                                />
                            </Tooltip>
                        );
                    })() : (
                        <Typography variant="caption" sx={{ color: '#475569' }}>N/A</Typography>
                    )}
                </TableCell>
            )}

            {/* F3: DTE */}
            {visibleColumns.dte && (
                <TableCell align="center" sx={cellSx}>
                    <Typography
                        variant="body2"
                        sx={{
                            fontWeight: 600,
                            color: (posGreeks?.dte ?? daysToExp) <= 7 ? '#ef4444' : '#94a3b8',
                            fontSize: '0.8rem',
                        }}
                    >
                        {posGreeks?.dte ?? daysToExp ?? '-'}
                    </Typography>
                </TableCell>
            )}

            {/* F3: Position Delta */}
            {visibleColumns.posDelta && (
                <TableCell align="right" sx={cellSx}>
                    <Typography variant="body2" sx={{
                        color: (posGreeks?.delta ?? 0) >= 0 ? '#10b981' : '#ef4444',
                        fontSize: '0.78rem',
                    }}>
                        {posGreeks ? (posGreeks.delta > 0 ? '+' : '') + posGreeks.delta.toFixed(4) : '-'}
                    </Typography>
                </TableCell>
            )}

            {/* F3: Position Theta */}
            {visibleColumns.posTheta && (
                <TableCell align="right" sx={cellSx}>
                    <Tooltip title="Theta: $/day for this position">
                        <Typography variant="body2" sx={{
                            color: (posGreeks?.theta ?? 0) >= 0 ? '#10b981' : '#f59e0b',
                            fontSize: '0.78rem',
                        }}>
                            {posGreeks ? (posGreeks.theta > 0 ? '+$' : '-$') + Math.abs(posGreeks.theta).toFixed(2) : '-'}
                        </Typography>
                    </Tooltip>
                </TableCell>
            )}

            {/* F3: Position Gamma */}
            {visibleColumns.posGamma && (
                <TableCell align="right" sx={cellSx}>
                    <Typography variant="body2" sx={{ color: '#a855f7', fontSize: '0.78rem' }}>
                        {posGreeks ? posGreeks.gamma.toFixed(6) : '-'}
                    </Typography>
                </TableCell>
            )}

            {/* F3: Position Vega */}
            {visibleColumns.posVega && (
                <TableCell align="right" sx={cellSx}>
                    <Tooltip title="Vega: $ per 1 vol-point change">
                        <Typography variant="body2" sx={{
                            color: (posGreeks?.vega ?? 0) >= 0 ? '#f59e0b' : '#94a3b8',
                            fontSize: '0.78rem',
                        }}>
                            {posGreeks ? '$' + posGreeks.vega.toFixed(2) : '-'}
                        </Typography>
                    </Tooltip>
                </TableCell>
            )}

            {/* Exchange fees paid */}
            {visibleColumns.fees && (
                <TableCell align="right" sx={cellSx}>
                    <Tooltip title="Cumulative exchange fees paid on this symbol (USD, last 30 days from /v2/fills)">
                        <Typography variant="body2" sx={{ color: '#f59e0b', fontSize: '0.78rem', fontWeight: 500 }}>
                            {feesPaid > 0 ? `$${feesPaid.toFixed(2)}` : (feesPaid === 0 ? '$0.00' : '-')}
                        </Typography>
                    </Tooltip>
                </TableCell>
            )}

            {/* Actions */}
            {visibleColumns.actions && (
                <TableCell align="center" sx={cellSx}>
                    <Box
                        sx={{
                            display: 'flex',
                            gap: 0.5,
                            justifyContent: 'center',
                            alignItems: 'center',
                            minWidth: 180,
                            flexWrap: 'nowrap',
                        }}
                    >
                        {/* Quick Execute Mode Indicator */}
                        {isQuickMode && (
                            <Tooltip
                                title={`Quick mode: Click C+/P+ to instantly ${skipConfirmStrike?.side || 'sell'} ${skipConfirmStrike?.size || DEFAULT_SIZE} lots. Click ⚡ to disable.`}
                            >
                                <Chip
                                    label={`⚡${skipConfirmStrike?.size || DEFAULT_SIZE}`}
                                    size="small"
                                    onClick={() => onDisableSkipConfirm(pos.product_symbol)}
                                    sx={{
                                        cursor: 'pointer',
                                        bgcolor: '#fbbf24',
                                        color: '#000',
                                        fontWeight: 'bold',
                                        minWidth: 32,
                                        maxHeight: 24,
                                        fontSize: '0.75rem',
                                        '&:hover': { bgcolor: '#f59e0b' },
                                    }}
                                />
                            </Tooltip>
                        )}

                        {(() => {
                            const recommendation = scalingRecommendation || { action: 'hold', size: 0, reason: '', confidence: 'low', riskLevel: 'medium' };
                            const tooltipTitle = (
                                <Box>
                                    <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
                                        Smart Scaling Recommendation
                                    </Typography>
                                    <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                                        Action:{' '}
                                        {recommendation.action === 'scale'
                                            ? '✅ Scale In'
                                            : recommendation.action === 'reduce'
                                                ? '⚠️ Reduce'
                                                : '⏸️ Hold'}
                                    </Typography>
                                    {recommendation.size > 0 && (
                                        <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                                            Size: {recommendation.size} contracts
                                        </Typography>
                                    )}
                                    <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                                        {recommendation.reason}
                                    </Typography>
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            display: 'block',
                                            color:
                                                recommendation.riskLevel === 'high' ? '#ef4444'
                                                    : recommendation.riskLevel === 'low' ? '#10b981'
                                                        : '#f59e0b',
                                        }}
                                    >
                                        Risk: {recommendation.riskLevel.toUpperCase()} | Confidence: {recommendation.confidence.toUpperCase()}
                                    </Typography>
                                </Box>
                            );

                            return (
                                <Tooltip title={tooltipTitle}>
                                    <IconButton
                                        size="medium"
                                        color="primary"
                                        onClick={() => onHandleAdd(pos)}
                                        disabled={!status?.trading_allowed}
                                        sx={{
                                            bgcolor:
                                                recommendation.action === 'scale'
                                                    ? isCall ? '#10b981' : '#ef4444'
                                                    : recommendation.action === 'reduce'
                                                        ? '#ef4444'
                                                        : '#6b7280',
                                            color: 'white',
                                            fontWeight: 'bold',
                                            fontSize: 14,
                                            minWidth: 36,
                                            '&:hover': {
                                                bgcolor:
                                                    recommendation.action === 'scale'
                                                        ? isCall ? '#059669' : '#dc2626'
                                                        : '#4b5563',
                                            },
                                            '&:disabled': { bgcolor: 'action.disabledBackground' },
                                        }}
                                    >
                                        {isCall ? 'C' : 'P'}+
                                    </IconButton>
                                </Tooltip>
                            );
                        })()}

                        {/* F9: Roll button — shown for open short positions, amber when DTE ≤ 14 */}
                        {!isClosed && onRoll && (
                            <Tooltip title={`Roll to further expiry${(posGreeks?.dte ?? daysToExp) <= 14 ? ' ⚠️ expiry approaching' : ''}`}>
                                <Button
                                    size="small"
                                    variant="outlined"
                                    onClick={() => onRoll(pos)}
                                    sx={{
                                        minWidth: 36, px: 0.75, py: 0.25, fontSize: '0.65rem', height: 28,
                                        borderColor: (posGreeks?.dte ?? daysToExp) <= 14
                                            ? 'rgba(251,191,36,0.6)' : 'rgba(99,102,241,0.4)',
                                        color: (posGreeks?.dte ?? daysToExp) <= 14 ? '#fbbf24' : '#818cf8',
                                        '&:hover': {
                                            borderColor: (posGreeks?.dte ?? daysToExp) <= 14 ? '#fbbf24' : '#6366f1',
                                            bgcolor: (posGreeks?.dte ?? daysToExp) <= 14
                                                ? 'rgba(251,191,36,0.1)' : 'rgba(99,102,241,0.1)',
                                        },
                                    }}
                                >
                                    Roll
                                </Button>
                            </Tooltip>
                        )}

                        {/* Visual Separator */}
                        <Box sx={{ width: '2px', height: '32px', bgcolor: 'divider', mx: 0.25 }} />

                        {isClosed ? (
                            <Tooltip title="🗑️ Remove from display - This removes the closed position from tracking">
                                <IconButton
                                    size="medium"
                                    color="default"
                                    onClick={() => onRemoveClosedPosition(pos.product_symbol)}
                                    sx={{
                                        border: '2px solid',
                                        borderColor: 'text.secondary',
                                        color: 'text.secondary',
                                        '&:hover': { bgcolor: 'action.hover', borderColor: 'error.main', color: 'error.main' },
                                    }}
                                >
                                    <CloseIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        ) : (
                            <Tooltip title="⚠️ CLOSE POSITION - This will exit your entire position!">
                                <IconButton
                                    size="medium"
                                    color="error"
                                    onClick={() => onHandleClose(pos)}
                                    disabled={!status?.trading_allowed}
                                    sx={{
                                        border: '2px solid',
                                        borderColor: 'error.main',
                                        '&:hover': { bgcolor: 'error.main', color: 'white' },
                                    }}
                                >
                                    <CloseIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        )}
                    </Box>
                </TableCell>
            )}
        </>
    );
}

// ARCH-2: React.memo prevents re-renders when parent state changes but this row's props haven't
export default React.memo(PositionRow);
