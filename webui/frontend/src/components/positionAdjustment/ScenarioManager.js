/**
 * Scenario Manager
 * =================
 * Save/Load adjustment scenarios to localStorage.
 * Allows users to save proposed trade configurations and restore them later.
 *
 * Created: March 6, 2026
 */

import React, { useState, useMemo, useCallback } from 'react';
import {
    Box,
    Button,
    Typography,
    Menu,
    MenuItem,
    ListItemText,
    ListItemSecondaryAction,
    IconButton,
    Tooltip,
    Divider,
    Chip,
} from '@mui/material';
import {
    Save as SaveIcon,
    History as HistoryIcon,
    Delete as DeleteIcon,
    RestoreFromTrash as RestoreIcon,
} from '@mui/icons-material';

const STORAGE_KEY = 'adjustment_scenarios';
const MAX_SCENARIOS = 10;

/**
 * Load scenarios from localStorage 
 */
function loadScenarios() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

/**
 * Save scenarios to localStorage
 */
function saveScenarios(scenarios) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(scenarios));
    } catch (e) {
        console.error('[ScenarioManager] Save error:', e);
    }
}

/**
 * Auto-generate scenario name based on timestamp
 */
function generateName() {
    const now = new Date();
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const ampm = now.getHours() >= 12 ? 'PM' : 'AM';
    const hours = now.getHours() % 12 || 12;
    const minutes = String(now.getMinutes()).padStart(2, '0');
    return `Scenario — ${months[now.getMonth()]} ${now.getDate()}, ${hours}:${minutes} ${ampm}`;
}

/**
 * @param {Object} props
 * @param {Array} props.proposedTrades - Current proposed trades array
 * @param {Object} props.metrics - Current metrics snapshot { maxProfit, maxLoss, delta }
 * @param {Function} props.onRestoreScenario - Callback to restore a saved scenario's trades
 */
export default function ScenarioManager({ proposedTrades = [], metrics, onRestoreScenario }) {
    const [anchorEl, setAnchorEl] = useState(null);
    const [scenarios, setScenarios] = useState(loadScenarios);

    const refresh = useCallback(() => {
        setScenarios(loadScenarios());
    }, []);

    // Save current trades as a scenario
    const handleSave = () => {
        if (!proposedTrades || proposedTrades.length === 0) return;

        const scenario = {
            id: Date.now(),
            name: generateName(),
            timestamp: new Date().toISOString(),
            legs: proposedTrades.map(t => ({
                symbol: t.symbol,
                side: t.side,
                strike: t.strike,
                expiry: t.expiry,
                type: t.type,
                quantity: t.quantity || 1,
                premium: t.premium || t.ltp || t.price || 0,
                underlying: t.underlying,
            })),
            snapshot: {
                maxProfit: metrics?.raw?.combined?.maxProfit || null,
                maxLoss: metrics?.raw?.combined?.maxLoss || null,
                delta: metrics?.raw?.combined?.netDelta || null,
                legCount: proposedTrades.length,
            },
        };

        const updated = [scenario, ...scenarios].slice(0, MAX_SCENARIOS);
        saveScenarios(updated);
        setScenarios(updated);
    };

    // Delete a scenario
    const handleDelete = (id) => {
        const updated = scenarios.filter(s => s.id !== id);
        saveScenarios(updated);
        setScenarios(updated);
    };

    // Restore a scenario
    const handleRestore = (scenario) => {
        setAnchorEl(null);
        onRestoreScenario?.(scenario.legs);
    };

    // Format relative time
    const relativeTime = (isoStr) => {
        const diff = Date.now() - new Date(isoStr).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return `${mins}m ago`;
        const hours = Math.floor(mins / 60);
        if (hours < 24) return `${hours}h ago`;
        return `${Math.floor(hours / 24)}d ago`;
    };

    const hasTrades = proposedTrades && proposedTrades.length > 0;

    return (
        <Box sx={{ display: 'flex', gap: 0.5 }}>
            {/* Save button */}
            <Tooltip title={hasTrades ? "Save current scenario" : "Add trades first"}>
                <span>
                    <Button
                        size="small"
                        startIcon={<SaveIcon sx={{ fontSize: 14 }} />}
                        disabled={!hasTrades}
                        onClick={handleSave}
                        sx={{
                            color: '#22c55e',
                            fontSize: '0.7rem',
                            textTransform: 'none',
                            minWidth: 0,
                            px: 1,
                            '&:hover': { bgcolor: 'rgba(34, 197, 94, 0.1)' },
                            '&.Mui-disabled': { color: '#64748b' },
                        }}
                    >
                        Save
                    </Button>
                </span>
            </Tooltip>

            {/* History dropdown */}
            <Tooltip title="Load saved scenario">
                <Button
                    size="small"
                    startIcon={<HistoryIcon sx={{ fontSize: 14 }} />}
                    onClick={(e) => { refresh(); setAnchorEl(e.currentTarget); }}
                    sx={{
                        color: '#94a3b8',
                        fontSize: '0.7rem',
                        textTransform: 'none',
                        minWidth: 0,
                        px: 1,
                        '&:hover': { bgcolor: 'rgba(148, 163, 184, 0.1)' },
                    }}
                >
                    {scenarios.length > 0 ? `History (${scenarios.length})` : 'History'}
                </Button>
            </Tooltip>

            <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={() => setAnchorEl(null)}
                PaperProps={{
                    sx: {
                        bgcolor: '#1e293b',
                        border: '1px solid rgba(71, 85, 105, 0.5)',
                        maxHeight: 320,
                        minWidth: 280,
                    },
                }}
            >
                {scenarios.length === 0 ? (
                    <MenuItem disabled>
                        <Typography variant="body2" sx={{ color: '#64748b', fontSize: '0.75rem' }}>
                            No saved scenarios
                        </Typography>
                    </MenuItem>
                ) : (
                    scenarios.map((sc, idx) => (
                        <Box key={sc.id}>
                            <MenuItem
                                onClick={() => handleRestore(sc)}
                                sx={{ py: 1, pr: 6 }}
                            >
                                <ListItemText
                                    primary={
                                        <Typography variant="body2" sx={{ color: '#e2e8f0', fontSize: '0.8rem' }}>
                                            {sc.name}
                                        </Typography>
                                    }
                                    secondary={
                                        <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
                                            <Chip
                                                label={`${sc.snapshot?.legCount || sc.legs?.length || 0} legs`}
                                                size="small"
                                                sx={{ height: 18, fontSize: '0.6rem', bgcolor: 'rgba(59, 130, 246, 0.2)', color: '#3b82f6' }}
                                            />
                                            <Typography variant="caption" sx={{ color: '#64748b', fontSize: '0.6rem', lineHeight: '18px' }}>
                                                {relativeTime(sc.timestamp)}
                                            </Typography>
                                        </Box>
                                    }
                                />
                                <ListItemSecondaryAction>
                                    <IconButton
                                        edge="end"
                                        size="small"
                                        onClick={(e) => { e.stopPropagation(); handleDelete(sc.id); }}
                                        sx={{ color: '#ef4444', opacity: 0.6, '&:hover': { opacity: 1 } }}
                                    >
                                        <DeleteIcon sx={{ fontSize: 14 }} />
                                    </IconButton>
                                </ListItemSecondaryAction>
                            </MenuItem>
                            {idx < scenarios.length - 1 && <Divider sx={{ borderColor: 'rgba(71, 85, 105, 0.3)' }} />}
                        </Box>
                    ))
                )}
            </Menu>
        </Box>
    );
}
