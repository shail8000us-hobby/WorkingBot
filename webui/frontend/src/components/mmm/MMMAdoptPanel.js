/**
 * MMMAdoptPanel — Money Mind & Method
 *
 * "Adopt from Exchange" UI: scans Delta Exchange for open short BTC options,
 * lets the user select positions, assign active/frozen roles, and adopt them
 * into an MMM session.
 *
 * Multi-strike support: unlike Import mode (1 CE + 1 PE), Adopt handles
 * multiple strikes per side (e.g., CE at 98000 active + 99000 frozen).
 *
 * Asymmetric lots: different lot counts on CE vs PE are supported.
 *
 * Trigger initialization: defaults to "current prices" so the algo takes over
 * from NOW without immediately firing adjustments.
 *
 * Created: February 18, 2026
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
    Box,
    Typography,
    Paper,
    Button,
    Alert,
    CircularProgress,
    Chip,
    Tooltip,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Checkbox,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Divider,
    IconButton,
} from '@mui/material';
import {
    Search as ScanIcon,
    CheckCircle as AdoptIcon,
    Warning as WarningIcon,
    Refresh as RefreshIcon,
    ArrowForward as ArrowIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';

// =============================================================================
// Helpers
// =============================================================================

const fmtStrike = (v) =>
    typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : v;

const fmtPrem = (v) =>
    typeof v === 'number' ? `$${v.toFixed(2)}` : '—';

const fmtPnl = (v) => {
    if (typeof v !== 'number') return '—';
    const sign = v >= 0 ? '+' : '';
    return `${sign}${v.toFixed(4)} BTC`;
};

const formatExpiry = (ddmmyyyy) => {
    if (!ddmmyyyy || ddmmyyyy.length !== 8) return ddmmyyyy;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const dd = ddmmyyyy.slice(0, 2);
    const mm = parseInt(ddmmyyyy.slice(2, 4), 10) - 1;
    const yyyy = ddmmyyyy.slice(4, 8);
    return `${dd} ${months[mm] || '???'} ${yyyy}`;
};

// =============================================================================
// MMMAdoptPanel
// =============================================================================

const MMMAdoptPanel = ({ sessionId, selectedExpiry, onAdopted }) => {
    // ----- State -----
    const [positions, setPositions] = useState([]);
    const [spotPrice, setSpotPrice] = useState(null);
    const [expiriesAvailable, setExpiriesAvailable] = useState([]);
    const [scanning, setScanning] = useState(false);
    const [adopting, setAdopting] = useState(false);
    const [scanned, setScanned] = useState(false);

    // Selection state: { [symbol]: { selected: bool, role: 'active'|'frozen' } }
    const [selections, setSelections] = useState({});

    // Trigger mode
    const [triggerMode, setTriggerMode] = useState('current_prices');

    // UI state
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [warnings, setWarnings] = useState([]);

    const mounted = useRef(true);
    useEffect(() => () => { mounted.current = false; }, []);

    // ----- Scan exchange -----
    const handleScan = useCallback(async () => {
        setScanning(true);
        setError(null);
        setSuccess(null);
        setWarnings([]);
        setPositions([]);
        setSelections({});
        setScanned(false);

        try {
            const result = await mmmService.getExchangePositions(selectedExpiry || null);

            if (mounted.current) {
                if (result.success) {
                    setPositions(result.positions || []);
                    setSpotPrice(result.spot_price || null);
                    setExpiriesAvailable(result.expiries_with_positions || []);
                    setScanned(true);

                    // Auto-select all and auto-classify
                    const autoSelections = {};
                    const cePositions = (result.positions || []).filter(p => p.side === 'CE');
                    const pePositions = (result.positions || []).filter(p => p.side === 'PE');

                    // For each side, closest to ATM = active
                    const classifySide = (sidePositions) => {
                        if (sidePositions.length === 0) return;
                        const spot = result.spot_price || 0;
                        let activeSymbol = sidePositions[0].symbol;
                        if (spot > 0) {
                            let closest = sidePositions[0];
                            for (const p of sidePositions) {
                                if (Math.abs(p.strike - spot) < Math.abs(closest.strike - spot)) {
                                    closest = p;
                                }
                            }
                            activeSymbol = closest.symbol;
                        }
                        for (const p of sidePositions) {
                            autoSelections[p.symbol] = {
                                selected: true,
                                role: p.symbol === activeSymbol ? 'active' : 'frozen',
                            };
                        }
                    };

                    classifySide(cePositions);
                    classifySide(pePositions);
                    setSelections(autoSelections);

                    if ((result.positions || []).length === 0) {
                        setError('No open short BTC options positions found on the exchange.');
                    }
                } else {
                    setError(result.error || 'Failed to fetch exchange positions');
                }
            }
        } catch (err) {
            if (mounted.current) {
                setError(err.details?.error || err.message || 'Scan failed');
            }
        } finally {
            if (mounted.current) setScanning(false);
        }
    }, [selectedExpiry]);

    // ----- Toggle selection -----
    const handleToggle = useCallback((symbol) => {
        setSelections(prev => ({
            ...prev,
            [symbol]: {
                ...prev[symbol],
                selected: !prev[symbol]?.selected,
            },
        }));
    }, []);

    // ----- Change role -----
    const handleRoleChange = useCallback((symbol, role) => {
        setSelections(prev => {
            const pos = positions.find(p => p.symbol === symbol);
            if (!pos) return prev;

            const next = { ...prev };
            next[symbol] = { ...next[symbol], role };

            // If setting to active, demote other actives on same side
            if (role === 'active') {
                for (const p of positions) {
                    if (p.side === pos.side && p.symbol !== symbol && next[p.symbol]?.role === 'active') {
                        next[p.symbol] = { ...next[p.symbol], role: 'frozen' };
                    }
                }
            }

            return next;
        });
    }, [positions]);

    // ----- Compute selected positions -----
    const selectedPositions = positions.filter(p => selections[p.symbol]?.selected);
    const selectedCE = selectedPositions.filter(p => p.side === 'CE');
    const selectedPE = selectedPositions.filter(p => p.side === 'PE');
    const ceTotalLots = selectedCE.reduce((sum, p) => sum + p.lots, 0);
    const peTotalLots = selectedPE.reduce((sum, p) => sum + p.lots, 0);
    const ceActive = selectedCE.find(p => selections[p.symbol]?.role === 'active');
    const peActive = selectedPE.find(p => selections[p.symbol]?.role === 'active');
    const canAdopt = selectedCE.length > 0 && selectedPE.length > 0 && ceActive && peActive;

    // ----- Adopt -----
    const handleAdopt = useCallback(async () => {
        if (!canAdopt) {
            setError('Select at least one CE and one PE position with an active role assigned.');
            return;
        }
        if (!sessionId) {
            setError('No session ID');
            return;
        }

        setAdopting(true);
        setError(null);
        setSuccess(null);
        setWarnings([]);

        const positionsPayload = selectedPositions.map(p => ({
            symbol: p.symbol,
            strike: p.strike,
            lots: p.lots,
            entry_price: p.entry_price,
            side: p.side,
            role: selections[p.symbol]?.role || 'frozen',
        }));

        const expiry = selectedPositions[0]?.expiry || selectedExpiry;

        try {
            const result = await mmmService.adoptPositions(
                sessionId,
                positionsPayload,
                expiry,
                triggerMode,
            );

            if (mounted.current) {
                if (result.success) {
                    setSuccess(
                        `Positions adopted! ${selectedPositions.length} position(s) imported. ` +
                        'Session is ready — click START to begin monitoring.'
                    );
                    setWarnings(result.warnings || []);
                    onAdopted?.(result);

                    // Auto-start the session
                    try {
                        const startResult = await mmmService.startSession(sessionId);
                        if (mounted.current) {
                            if (startResult.success) {
                                setSuccess('Positions adopted and strategy started! Monitor active.');
                            } else {
                                setError(`Adopted but failed to start: ${startResult.error}`);
                            }
                        }
                    } catch (startErr) {
                        if (mounted.current) {
                            setError(`Adopted but start failed: ${startErr.details?.error || startErr.message}`);
                        }
                    }
                } else {
                    setError(result.error || 'Adoption failed');
                    setWarnings(result.warnings || []);
                }
            }
        } catch (err) {
            if (mounted.current) {
                const errData = err.details || {};
                setError(errData.error || err.message || 'Adoption failed');
                setWarnings(errData.warnings || []);
            }
        } finally {
            if (mounted.current) setAdopting(false);
        }
    }, [canAdopt, sessionId, selectedPositions, selectedExpiry, triggerMode, selections, onAdopted]);

    // ----- Render -----
    return (
        <Box>
            {/* Scan button */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Button
                    variant="contained"
                    onClick={handleScan}
                    disabled={scanning}
                    startIcon={scanning ? <CircularProgress size={16} /> : <ScanIcon />}
                    sx={{
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        fontWeight: 600,
                    }}
                >
                    {scanning ? 'Scanning...' : 'Scan Exchange'}
                </Button>
                {scanned && (
                    <Tooltip title="Rescan exchange">
                        <IconButton size="small" onClick={handleScan} disabled={scanning}>
                            <RefreshIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                )}
                {spotPrice && (
                    <Chip
                        label={`BTC Spot: $${spotPrice.toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
                        variant="outlined"
                        size="small"
                        sx={{ fontFamily: 'monospace', fontWeight: 600 }}
                    />
                )}
                {positions.length > 0 && (
                    <Chip
                        label={`${positions.length} position(s) found`}
                        color="primary"
                        size="small"
                    />
                )}
            </Box>

            {/* Errors & success */}
            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}
            {success && (
                <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
                    {success}
                </Alert>
            )}
            {warnings.map((w, i) => (
                <Alert key={i} severity="warning" sx={{ mb: 1 }} icon={<WarningIcon />}>
                    {w}
                </Alert>
            ))}

            {/* Positions table */}
            {scanned && positions.length > 0 && (
                <>
                    <TableContainer
                        component={Paper}
                        variant="outlined"
                        sx={{
                            mb: 2,
                            maxHeight: 400,
                            overflow: 'auto',
                            '& .MuiTableCell-root': {
                                py: 0.75,
                                px: 1,
                                fontSize: '0.82rem',
                            },
                        }}
                    >
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell padding="checkbox" />
                                    <TableCell>Side</TableCell>
                                    <TableCell>Expiry</TableCell>
                                    <TableCell align="right">Strike</TableCell>
                                    <TableCell align="right">Lots</TableCell>
                                    <TableCell align="right">Entry $</TableCell>
                                    <TableCell align="right">Mark $</TableCell>
                                    <TableCell align="right">P&L</TableCell>
                                    <TableCell align="right">IV</TableCell>
                                    <TableCell align="right">Δ</TableCell>
                                    <TableCell align="center">Role</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {positions.map((pos) => {
                                    const sel = selections[pos.symbol] || {};
                                    const isSelected = sel.selected;
                                    const role = sel.role || 'frozen';
                                    const sideColor = pos.side === 'CE' ? '#4caf50' : '#f44336';
                                    const pnlColor = pos.unrealized_pnl >= 0 ? '#4caf50' : '#f44336';

                                    return (
                                        <TableRow
                                            key={pos.symbol}
                                            hover
                                            sx={{
                                                backgroundColor: isSelected
                                                    ? (role === 'active' ? `${sideColor}10` : `${sideColor}06`)
                                                    : 'transparent',
                                                opacity: isSelected ? 1 : 0.5,
                                                '&:hover': { opacity: 1 },
                                            }}
                                        >
                                            <TableCell padding="checkbox">
                                                <Checkbox
                                                    checked={!!isSelected}
                                                    onChange={() => handleToggle(pos.symbol)}
                                                    size="small"
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={pos.side}
                                                    size="small"
                                                    sx={{
                                                        backgroundColor: `${sideColor}18`,
                                                        color: sideColor,
                                                        fontWeight: 700,
                                                        fontSize: '0.7rem',
                                                        height: 22,
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                                                {formatExpiry(pos.expiry)}
                                            </TableCell>
                                            <TableCell align="right" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                                                {fmtStrike(pos.strike)}
                                            </TableCell>
                                            <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                                                {pos.lots}
                                            </TableCell>
                                            <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                                                {fmtPrem(pos.entry_price)}
                                            </TableCell>
                                            <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                                                {fmtPrem(pos.mark_price)}
                                            </TableCell>
                                            <TableCell align="right" sx={{ fontFamily: 'monospace', color: pnlColor }}>
                                                {fmtPnl(pos.unrealized_pnl)}
                                            </TableCell>
                                            <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                                                {pos.iv ? `${(pos.iv * 100).toFixed(1)}%` : '—'}
                                            </TableCell>
                                            <TableCell align="right" sx={{ fontFamily: 'monospace' }}>
                                                {pos.delta?.toFixed(3) || '—'}
                                            </TableCell>
                                            <TableCell align="center">
                                                {isSelected && (
                                                    <Select
                                                        value={role}
                                                        onChange={(e) => handleRoleChange(pos.symbol, e.target.value)}
                                                        size="small"
                                                        variant="standard"
                                                        sx={{
                                                            fontSize: '0.75rem',
                                                            fontWeight: role === 'active' ? 700 : 400,
                                                            color: role === 'active' ? sideColor : 'text.secondary',
                                                        }}
                                                    >
                                                        <MenuItem value="active">Active</MenuItem>
                                                        <MenuItem value="frozen">Frozen</MenuItem>
                                                    </Select>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </TableContainer>

                    <Divider sx={{ mb: 2 }} />

                    {/* Summary & adopt section */}
                    {selectedPositions.length > 0 && (
                        <Paper
                            sx={{
                                p: 2, mb: 2,
                                border: '1px solid rgba(103,126,234,0.3)',
                                backgroundColor: 'rgba(103,126,234,0.04)',
                            }}
                        >
                            <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700 }}>
                                Adoption Summary
                            </Typography>

                            <Box sx={{ display: 'flex', gap: 4, mb: 2, flexWrap: 'wrap' }}>
                                {/* CE summary */}
                                <Box>
                                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                                        CE (Call) Side
                                    </Typography>
                                    {ceActive ? (
                                        <Box sx={{ mt: 0.5 }}>
                                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                                                <strong>Active:</strong> {fmtStrike(ceActive.strike)} × {ceActive.lots} lots
                                                @ {fmtPrem(ceActive.entry_price)}
                                            </Typography>
                                            {selectedCE.filter(p => p !== ceActive).map(p => (
                                                <Typography key={p.symbol} variant="body2"
                                                    sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                                                    Frozen: {fmtStrike(p.strike)} × {p.lots} lots
                                                    @ {fmtPrem(p.entry_price)}
                                                </Typography>
                                            ))}
                                            <Chip label={`${ceTotalLots} total lots`} size="small"
                                                sx={{ mt: 0.5, fontSize: '0.7rem' }} />
                                        </Box>
                                    ) : (
                                        <Typography variant="body2" color="error">No CE selected</Typography>
                                    )}
                                </Box>

                                {/* Arrow */}
                                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                    <ArrowIcon sx={{ color: 'text.disabled' }} />
                                </Box>

                                {/* PE summary */}
                                <Box>
                                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                                        PE (Put) Side
                                    </Typography>
                                    {peActive ? (
                                        <Box sx={{ mt: 0.5 }}>
                                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                                                <strong>Active:</strong> {fmtStrike(peActive.strike)} × {peActive.lots} lots
                                                @ {fmtPrem(peActive.entry_price)}
                                            </Typography>
                                            {selectedPE.filter(p => p !== peActive).map(p => (
                                                <Typography key={p.symbol} variant="body2"
                                                    sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>
                                                    Frozen: {fmtStrike(p.strike)} × {p.lots} lots
                                                    @ {fmtPrem(p.entry_price)}
                                                </Typography>
                                            ))}
                                            <Chip label={`${peTotalLots} total lots`} size="small"
                                                sx={{ mt: 0.5, fontSize: '0.7rem' }} />
                                        </Box>
                                    ) : (
                                        <Typography variant="body2" color="error">No PE selected</Typography>
                                    )}
                                </Box>
                            </Box>

                            {/* Trigger mode */}
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                                <FormControl size="small" sx={{ minWidth: 200 }}>
                                    <InputLabel>Trigger Mode</InputLabel>
                                    <Select
                                        value={triggerMode}
                                        label="Trigger Mode"
                                        onChange={(e) => setTriggerMode(e.target.value)}
                                    >
                                        <MenuItem value="current_prices">Current Prices (recommended)</MenuItem>
                                        <MenuItem value="entry_prices">Entry Prices</MenuItem>
                                    </Select>
                                </FormControl>
                                <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 350 }}>
                                    {triggerMode === 'current_prices'
                                        ? 'Triggers set to current premiums — algo takes over from NOW.'
                                        : 'Triggers set to original entry prices — may fire adjustments immediately if premiums have risen.'}
                                </Typography>
                            </Box>

                            {/* Lot mismatch warning */}
                            {ceTotalLots !== peTotalLots && (
                                <Alert severity="info" sx={{ mb: 1.5 }} icon={<WarningIcon />}>
                                    CE lots ({ceTotalLots}) ≠ PE lots ({peTotalLots}) — asymmetric position. This is allowed.
                                </Alert>
                            )}

                            {/* ADOPT button */}
                            <Button
                                variant="contained"
                                onClick={handleAdopt}
                                disabled={!canAdopt || adopting}
                                startIcon={adopting ? <CircularProgress size={16} /> : <AdoptIcon />}
                                sx={{
                                    background: canAdopt
                                        ? 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'
                                        : undefined,
                                    fontWeight: 700,
                                    px: 4,
                                    py: 1,
                                }}
                            >
                                {adopting ? 'Adopting...' : `Adopt ${selectedPositions.length} Position(s) & Start`}
                            </Button>
                        </Paper>
                    )}
                </>
            )}

            {/* Empty state after scan */}
            {scanned && positions.length === 0 && !error && (
                <Paper sx={{ p: 3, textAlign: 'center', opacity: 0.6 }}>
                    <Typography variant="body2">
                        No open short BTC options positions found on Delta Exchange
                        {selectedExpiry ? ` for expiry ${formatExpiry(selectedExpiry)}` : ''}.
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                        Make sure you have short options positions open on the exchange.
                    </Typography>
                </Paper>
            )}
        </Box>
    );
};

export default MMMAdoptPanel;
