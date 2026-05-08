/**
 * AutoLoopBanner Component
 *
 * Persistent sticky banner shown when auto-loop is running.
 * Displays:
 *  - per-expiry status (round counter, countdown to next fire when interval set)
 *  - partial-fill chips (filled / partial / pending)
 *  - poll-error indicator
 *  - STOP firing + CANCEL pending controls
 *
 * Re-renders only on prop changes (React.memo).
 *
 * Created: February 26, 2026 (ARCH-2 refactor)
 * Updated: 2026-05-06 (v1.1.0 hybrid-trigger model)
 */

import React, { useEffect, useState } from 'react';
import {
    Box,
    Chip,
    Tooltip,
    Typography,
    Button,
    IconButton,
    CircularProgress,
} from '@mui/material';
import {
    Block as BlockIcon,
    ExpandLess as ExpandLessIcon,
    ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';

// ── Helpers ───────────────────────────────────────────────────────────

function formatCountdown(targetIso) {
    if (!targetIso) return null;
    const target = new Date(targetIso).getTime();
    if (isNaN(target)) return null;
    const remaining = Math.max(0, Math.floor((target - Date.now()) / 1000));
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
}

function classifyOrder(prog) {
    const target = prog.size ?? prog.target_size ?? 0;
    const filledQty = prog.filled_size ?? 0;
    const filled = !!prog.filled || (target > 0 && filledQty >= target);
    const partial = !filled && filledQty > 0;
    return { target, filledQty, filled, partial };
}

function chipPalette(filled, partial, hasError) {
    if (hasError) return { bg: 'rgba(239,68,68,0.25)', fg: '#fee2e2' };
    if (filled) return { bg: 'rgba(16,185,129,0.30)', fg: '#065f46' };
    if (partial) return { bg: 'rgba(234,179,8,0.30)', fg: '#713f12' };
    return { bg: 'rgba(0,0,0,0.20)', fg: '#000' };
}

// Use a 1-Hz tick for live countdowns without tying to parent re-renders.
function useTicker(intervalMs = 1000) {
    const [, setTick] = useState(0);
    useEffect(() => {
        const id = setInterval(() => setTick((t) => (t + 1) % 1e9), intervalMs);
        return () => clearInterval(id);
    }, [intervalMs]);
}

// ── Single-leg chip ───────────────────────────────────────────────────

function LegChip({ symbol, prog }) {
    const parts = symbol.split('-');
    const optType = parts[0] || '';
    const strike = parts[2] || symbol;
    const { target, filledQty, filled, partial } = classifyOrder(prog);
    const hasPollError = !!prog.lastPollError || !!prog.last_poll_error;
    const palette = chipPalette(filled, partial, hasPollError);
    const icon = filled ? '✅' : partial ? '🟡' : '⏳';
    const sizeLabel = partial ? ` ${filledQty}/${target}` : '';
    const errorLabel = hasPollError ? ' ⚠' : '';
    const tipParts = [
        `${optType}${strike} target ${target}`,
        partial ? `partially filled ${filledQty}/${target}` : (filled ? 'fully filled' : 'on book'),
        prog.placedPrice || prog.placed_price ? `placed @ ${prog.placedPrice || prog.placed_price}` : null,
        prog.fillPrice || prog.fill_price ? `fill @ ${prog.fillPrice || prog.fill_price}` : null,
        hasPollError ? `poll error: ${prog.lastPollError || prog.last_poll_error}` : null,
        prog.error ? `error: ${prog.error}` : null,
    ].filter(Boolean);

    return (
        <Tooltip title={tipParts.join(' · ')}>
            <Chip
                size="small"
                label={`${icon} ${optType}${strike}${sizeLabel}${errorLabel}`}
                sx={{
                    bgcolor: palette.bg,
                    color: palette.fg,
                    fontSize: '0.65rem',
                    height: 18,
                }}
            />
        </Tooltip>
    );
}

// ── Per-round breakdown (multi-round display) ─────────────────────────

function PerRoundBreakdown({ rounds }) {
    if (!Array.isArray(rounds) || rounds.length === 0) return null;
    return (
        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            {rounds.map((rd) => {
                const orders = rd.orders || [];
                const filled = orders.filter(o => (o.target_size || 0) > 0 && (o.filled_size || 0) >= (o.target_size || 0)).length;
                const partial = orders.filter(o => {
                    const t = o.target_size || 0;
                    const f = o.filled_size || 0;
                    return f > 0 && f < t;
                }).length;
                const cancelled = orders.filter(o => o.state === 'cancelled' || o.state === 'error').length;
                return (
                    <Box key={rd.round_num} sx={{
                        bgcolor: 'rgba(0,0,0,0.15)',
                        p: 0.75,
                        borderRadius: '6px',
                    }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                            <Typography variant="caption" sx={{ fontWeight: 'bold', minWidth: 70 }}>
                                R{rd.round_num}
                            </Typography>
                            <Typography variant="caption" sx={{ opacity: 0.75 }}>
                                fired {rd.fired_at ? new Date(rd.fired_at).toLocaleTimeString() : '—'}
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'rgba(16,185,129,0.85)' }}>
                                ✅ {filled}
                            </Typography>
                            {partial > 0 && (
                                <Typography variant="caption" sx={{ color: 'rgba(234,179,8,0.95)' }}>
                                    🟡 {partial}
                                </Typography>
                            )}
                            {cancelled > 0 && (
                                <Typography variant="caption" sx={{ color: 'rgba(239,68,68,0.85)' }}>
                                    ✖ {cancelled}
                                </Typography>
                            )}
                        </Box>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                            {orders.map((o, i) => (
                                <LegChip
                                    key={`${rd.round_num}-${o.symbol}-${o.order_id || i}`}
                                    symbol={o.symbol}
                                    prog={{
                                        size: o.target_size,
                                        filled_size: o.filled_size,
                                        filled: (o.target_size || 0) > 0 && (o.filled_size || 0) >= (o.target_size || 0),
                                        placed_price: o.placed_price,
                                        fill_price: o.fill_price,
                                        last_poll_error: o.last_poll_error,
                                        error: o.state === 'cancelled' || o.state === 'error' ? (o.error || o.state) : null,
                                    }}
                                />
                            ))}
                        </Box>
                    </Box>
                );
            })}
        </Box>
    );
}

// ── Main banner ───────────────────────────────────────────────────────

function AutoLoopBanner({
    autoLoopRunning,
    anyExpiryLoopRunning,
    autoLoopCurrentRound,
    autoLoopRounds,
    autoLoopProgress,
    autoLoopRoundsData,
    autoLoopNextFireAt,
    expiryLoopState,
    stopAutoLoop,
    stopAllExpiryLoops,
    stopExpiryAutoLoop,
    cancelPendingMainAutoLoop,
    cancelPendingExpiryAutoLoop,
}) {
    // Re-render every second so countdown timers update
    useTicker(1000);
    const [collapsed, setCollapsed] = useState(false);
    if (!autoLoopRunning && !anyExpiryLoopRunning) return null;

    const mainCountdown = formatCountdown(autoLoopNextFireAt);
    const mainHasMultipleRounds = Array.isArray(autoLoopRoundsData) && autoLoopRoundsData.length >= 1;

    // Compact per-expiry summary line shown in collapsed header
    const runningExpiries = anyExpiryLoopRunning
        ? Object.entries(expiryLoopState).filter(([, s]) => s.running)
        : [];

    return (
        <Box sx={{
            position: 'sticky',
            top: 0,
            zIndex: 1100,
            bgcolor: 'rgba(251, 191, 36, 0.95)',
            color: '#000',
            py: 1,
            px: 2,
            mb: 1,
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(251, 191, 36, 0.4)',
            animation: 'pulse-banner 2s infinite',
            '@keyframes pulse-banner': {
                '0%, 100%': { boxShadow: '0 4px 12px rgba(251, 191, 36, 0.4)' },
                '50%': { boxShadow: '0 4px 20px rgba(251, 191, 36, 0.7)' },
            },
        }}>
            {/* Header row — always visible */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
                    <CircularProgress size={20} thickness={5} sx={{ color: '#000', flexShrink: 0 }} />
                    <Typography variant="body1" fontWeight="bold" sx={{ flexShrink: 0 }}>
                        🔁 AUTO-LOOP ACTIVE
                    </Typography>
                    {!anyExpiryLoopRunning && autoLoopRunning && (
                        <>
                            <Typography variant="body2" sx={{ opacity: 0.85, flexShrink: 0 }}>
                                Round {autoLoopCurrentRound}/{autoLoopRounds}
                            </Typography>
                            {mainCountdown && (
                                <Tooltip title="Next round will fire when current round fully fills OR this timer hits 0:00 — whichever first.">
                                    <Chip
                                        size="small"
                                        label={`⏱ next in ${mainCountdown}`}
                                        sx={{ bgcolor: 'rgba(0,0,0,0.18)', color: '#000', height: 22, fontWeight: 'bold', flexShrink: 0 }}
                                    />
                                </Tooltip>
                            )}
                        </>
                    )}
                    {/* Collapsed per-expiry summary */}
                    {anyExpiryLoopRunning && collapsed && (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                            {runningExpiries.map(([expiry, state]) => {
                                const cd = formatCountdown(state.nextFireAt);
                                return (
                                    <Chip
                                        key={expiry}
                                        size="small"
                                        label={`${expiry} R${state.currentRound}/${state.totalRounds}${cd ? ` ⏱${cd}` : ''}`}
                                        sx={{ bgcolor: 'rgba(0,0,0,0.18)', color: '#000', height: 22, fontSize: '0.7rem', fontWeight: 'bold' }}
                                    />
                                );
                            })}
                        </Box>
                    )}
                </Box>
                <Box sx={{ display: 'flex', gap: 0.75, flexShrink: 0, alignItems: 'center' }}>
                    <Button
                        variant="contained"
                        size="small"
                        color="error"
                        onClick={anyExpiryLoopRunning ? stopAllExpiryLoops : stopAutoLoop}
                        startIcon={<BlockIcon />}
                        sx={{ fontWeight: 'bold', bgcolor: '#ef4444', '&:hover': { bgcolor: '#dc2626' } }}
                    >
                        STOP firing
                    </Button>
                    {!anyExpiryLoopRunning && autoLoopRunning && cancelPendingMainAutoLoop && (
                        <Button
                            variant="outlined"
                            size="small"
                            onClick={cancelPendingMainAutoLoop}
                            sx={{
                                fontWeight: 'bold',
                                color: '#7f1d1d',
                                borderColor: '#7f1d1d',
                                bgcolor: 'rgba(255,255,255,0.4)',
                                '&:hover': { bgcolor: 'rgba(255,255,255,0.6)', borderColor: '#7f1d1d' },
                            }}
                        >
                            ✖ CANCEL pending
                        </Button>
                    )}
                    <Tooltip title={collapsed ? 'Expand details' : 'Collapse to compact view'}>
                        <IconButton
                            size="small"
                            onClick={() => setCollapsed(c => !c)}
                            sx={{ p: 0.5, color: '#000', bgcolor: 'rgba(0,0,0,0.12)', '&:hover': { bgcolor: 'rgba(0,0,0,0.22)' } }}
                        >
                            {collapsed ? <ExpandMoreIcon sx={{ fontSize: 18 }} /> : <ExpandLessIcon sx={{ fontSize: 18 }} />}
                        </IconButton>
                    </Tooltip>
                </Box>
            </Box>

            {/* Expanded detail area */}
            {!collapsed && (
                <>
                    {/* Single-loop (main) per-round breakdown */}
                    {!anyExpiryLoopRunning && autoLoopRunning && mainHasMultipleRounds && (
                        <Box sx={{ mt: 1 }}>
                            <PerRoundBreakdown rounds={autoLoopRoundsData} />
                        </Box>
                    )}

                    {/* Single-loop legacy chips (only shown when no per-round breakdown is available) */}
                    {!anyExpiryLoopRunning && autoLoopRunning && !mainHasMultipleRounds && autoLoopProgress && (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.75 }}>
                            {Object.entries(autoLoopProgress).map(([symbol, prog]) => (
                                <LegChip key={symbol} symbol={symbol} prog={prog} />
                            ))}
                        </Box>
                    )}

                    {/* Per-expiry detailed status */}
                    {anyExpiryLoopRunning && (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
                            {runningExpiries.map(([expiry, state]) => {
                                const filledCount = Object.values(state.progress || {}).filter(p => {
                                    const t = p.size || 0;
                                    const f = p.filled_size || 0;
                                    return p.filled || (t > 0 && f >= t);
                                }).length;
                                const partialCount = Object.values(state.progress || {}).filter(p => {
                                    const t = p.size || 0;
                                    const f = p.filled_size || 0;
                                    return !p.filled && f > 0 && f < t;
                                }).length;
                                const totalCount = Object.keys(state.progress || {}).length;
                                const pendingCount = Math.max(0, totalCount - filledCount - partialCount);
                                const expiryCountdown = formatCountdown(state.nextFireAt);
                                const rounds = Array.isArray(state.rounds) ? state.rounds : [];
                                const showRoundBreakdown = rounds.length >= 1;
                                return (
                                    <Box key={expiry} sx={{ bgcolor: 'rgba(0,0,0,0.15)', p: 1, borderRadius: '6px' }}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5, flexWrap: 'wrap', gap: 1 }}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                                                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                                                    📅 {expiry}
                                                </Typography>
                                                <Chip
                                                    size="small"
                                                    label={`Round ${state.currentRound}/${state.totalRounds}`}
                                                    sx={{ bgcolor: 'rgba(0,0,0,0.2)', height: 20, fontSize: '0.7rem' }}
                                                />
                                                {expiryCountdown && (
                                                    <Tooltip title="Time until next round fires (or fills complete — whichever first)">
                                                        <Chip
                                                            size="small"
                                                            label={`⏱ ${expiryCountdown}`}
                                                            sx={{ bgcolor: 'rgba(0,0,0,0.25)', height: 20, fontSize: '0.7rem', fontWeight: 'bold' }}
                                                        />
                                                    </Tooltip>
                                                )}
                                                <Typography variant="caption" sx={{ color: 'rgba(0,0,0,0.7)' }}>
                                                    ✅ {filledCount}{partialCount > 0 ? ` · 🟡 ${partialCount}` : ''} · ⏳ {pendingCount}
                                                </Typography>
                                            </Box>
                                            <Box sx={{ display: 'flex', gap: 0.5 }}>
                                                <IconButton
                                                    size="small"
                                                    onClick={(e) => { e.stopPropagation(); stopExpiryAutoLoop(expiry); }}
                                                    title="Stop firing future rounds (keeps existing orders on the exchange)"
                                                    sx={{ p: 0.5, color: '#ef4444', bgcolor: 'rgba(239,68,68,0.2)', '&:hover': { bgcolor: 'rgba(239,68,68,0.3)' } }}
                                                >
                                                    <BlockIcon sx={{ fontSize: 16 }} />
                                                </IconButton>
                                                {cancelPendingExpiryAutoLoop && (
                                                    <Button
                                                        size="small"
                                                        variant="outlined"
                                                        onClick={(e) => { e.stopPropagation(); cancelPendingExpiryAutoLoop(expiry); }}
                                                        sx={{
                                                            py: 0,
                                                            px: 1,
                                                            minWidth: 0,
                                                            fontSize: '0.65rem',
                                                            fontWeight: 'bold',
                                                            color: '#7f1d1d',
                                                            borderColor: '#7f1d1d',
                                                            '&:hover': { bgcolor: 'rgba(127,29,29,0.1)', borderColor: '#7f1d1d' },
                                                        }}
                                                    >
                                                        ✖ Cancel pending
                                                    </Button>
                                                )}
                                            </Box>
                                        </Box>
                                        {/* Per-round breakdown when available; otherwise flat chip strip */}
                                        {showRoundBreakdown ? (
                                            <PerRoundBreakdown rounds={rounds} />
                                        ) : (
                                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                                {Object.entries(state.progress || {}).map(([symbol, prog]) => (
                                                    <LegChip key={symbol} symbol={symbol} prog={prog} />
                                                ))}
                                            </Box>
                                        )}
                                    </Box>
                                );
                            })}
                        </Box>
                    )}
                </>
            )}
        </Box>
    );
}

export default React.memo(AutoLoopBanner);
