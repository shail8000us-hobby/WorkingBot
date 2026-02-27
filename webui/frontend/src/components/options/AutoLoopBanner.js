/**
 * AutoLoopBanner Component
 *
 * ARCH-2: Extracted from OptionsPanel.js monolith.
 * Persistent sticky banner shown when auto-loop is running.
 * Displays per-expiry status, round progress, and stop controls.
 * 
 * Wrapped in React.memo — only re-renders when loop state changes.
 *
 * Created: February 26, 2026 (ARCH-2 refactor)
 */

import React from 'react';
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
} from '@mui/icons-material';

function AutoLoopBanner({
    autoLoopRunning,
    anyExpiryLoopRunning,
    autoLoopCurrentRound,
    autoLoopRounds,
    autoLoopProgress,
    expiryLoopState,
    stopAutoLoop,
    stopAllExpiryLoops,
    stopExpiryAutoLoop,
}) {
    if (!autoLoopRunning && !anyExpiryLoopRunning) return null;

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
            {/* Header row */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: anyExpiryLoopRunning ? 1 : 0 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <CircularProgress size={20} thickness={5} sx={{ color: '#000' }} />
                    <Typography variant="body1" fontWeight="bold">
                        🔁 AUTO-LOOP ACTIVE
                    </Typography>
                    {!anyExpiryLoopRunning && autoLoopRunning && (
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>
                            Round {autoLoopCurrentRound}/{autoLoopRounds} • {Object.values(autoLoopProgress).filter(p => p.status === 'filled').length}/{Object.keys(autoLoopProgress).length} filled
                        </Typography>
                    )}
                </Box>
                <Button
                    variant="contained"
                    size="small"
                    color="error"
                    onClick={anyExpiryLoopRunning ? stopAllExpiryLoops : stopAutoLoop}
                    startIcon={<BlockIcon />}
                    sx={{ fontWeight: 'bold', bgcolor: '#ef4444', '&:hover': { bgcolor: '#dc2626' } }}
                >
                    STOP ALL
                </Button>
            </Box>

            {/* Per-expiry detailed status */}
            {anyExpiryLoopRunning && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {Object.entries(expiryLoopState)
                        .filter(([_, state]) => state.running)
                        .map(([expiry, state]) => {
                            const filledCount = Object.values(state.progress || {}).filter(p => p.filled).length;
                            const totalCount = Object.keys(state.progress || {}).length;
                            const pendingCount = totalCount - filledCount;
                            return (
                                <Box key={expiry} sx={{ bgcolor: 'rgba(0,0,0,0.15)', p: 1, borderRadius: '6px' }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                                                📅 {expiry}
                                            </Typography>
                                            <Chip
                                                size="small"
                                                label={`Round ${state.currentRound}/${state.totalRounds}`}
                                                sx={{ bgcolor: 'rgba(0,0,0,0.2)', height: 20, fontSize: '0.7rem' }}
                                            />
                                            <Typography variant="caption" sx={{ color: 'rgba(0,0,0,0.7)' }}>
                                                ✅ {filledCount} filled • ⏳ {pendingCount} pending
                                            </Typography>
                                        </Box>
                                        <IconButton
                                            size="small"
                                            onClick={(e) => { e.stopPropagation(); stopExpiryAutoLoop(expiry); }}
                                            sx={{ p: 0.5, color: '#ef4444', bgcolor: 'rgba(239,68,68,0.2)', '&:hover': { bgcolor: 'rgba(239,68,68,0.3)' } }}
                                        >
                                            <BlockIcon sx={{ fontSize: 16 }} />
                                        </IconButton>
                                    </Box>
                                    {/* Per-symbol progress chips */}
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {Object.entries(state.progress || {}).map(([symbol, prog]) => {
                                            const parts = symbol.split('-');
                                            const optType = parts[0];
                                            const strike = parts[2];
                                            return (
                                                <Chip
                                                    key={symbol}
                                                    size="small"
                                                    label={`${prog.filled ? '✅' : '⏳'} ${optType}${strike}`}
                                                    sx={{
                                                        bgcolor: prog.filled ? 'rgba(16,185,129,0.3)' : 'rgba(0,0,0,0.2)',
                                                        color: prog.filled ? '#065f46' : '#000',
                                                        fontSize: '0.65rem',
                                                        height: 18,
                                                    }}
                                                />
                                            );
                                        })}
                                    </Box>
                                </Box>
                            );
                        })}
                </Box>
            )}
        </Box>
    );
}

export default React.memo(AutoLoopBanner);
