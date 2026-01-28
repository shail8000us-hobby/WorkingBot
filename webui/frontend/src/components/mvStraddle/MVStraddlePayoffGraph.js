/**
 * MV Straddle Payoff Graph - Industry Best
 * =========================================
 * Professional payoff visualization for MV Straddle positions.
 * 
 * Features (matching Sensibull/Opstra style):
 * - Drag-to-zoom on chart (select area and zoom)
 * - Dual lines: "On Expiry" (green/red) + "On Target Date" (blue)
 * - Interactive time slider (hourly precision for 0 DTE)
 * - BTC target price slider with reset-to-ATM
 * - Projected profit display at target price
 * - Position selection checkboxes
 * - Smart Y-axis auto-scaling
 * 
 * MV Straddle payoff:
 * - Long: Profit = |Spot - Strike| - Premium
 * - Short: Profit = Premium - |Spot - Strike|
 * 
 * Created: January 27, 2026
 */

import React, { useMemo, useState, useCallback, useRef } from 'react';
import {
    ResponsiveContainer,
    ComposedChart,
    Line,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceLine,
    ReferenceArea,
} from 'recharts';
import {
    Box, Typography, Paper, Chip, Slider, Stack, Divider,
    IconButton, FormControlLabel, Switch, Checkbox,
    Collapse, Button, Alert
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import SelectAllIcon from '@mui/icons-material/SelectAll';
import DeselectIcon from '@mui/icons-material/Deselect';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

// MV Straddle contract multiplier (1 lot = 0.001 BTC)
const CONTRACT_MULTIPLIER = 0.001;

/**
 * Calculate MV Straddle payoff at expiry
 */
const calculateStraddlePayoff = (spotPrice, strike, entryPrice, size) => {
    const intrinsicValue = Math.abs(spotPrice - strike);
    const absSize = Math.abs(size);
    const isShort = size < 0;

    if (isShort) {
        return (entryPrice - intrinsicValue) * absSize * CONTRACT_MULTIPLIER;
    } else {
        return (intrinsicValue - entryPrice) * absSize * CONTRACT_MULTIPLIER;
    }
};

/**
 * Standard Normal CDF approximation (Abramowitz and Stegun)
 */
const normalCDF = (x) => {
    const a1 = 0.254829592;
    const a2 = -0.284496736;
    const a3 = 1.421413741;
    const a4 = -1.453152027;
    const a5 = 1.061405429;
    const p = 0.3275911;

    const sign = x < 0 ? -1 : 1;
    x = Math.abs(x);

    const t = 1.0 / (1.0 + p * x);
    const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x / 2);

    return 0.5 * (1.0 + sign * y);
};

/**
 * Black-Scholes Call Price
 */
const blackScholesCall = (S, K, T, r, sigma) => {
    if (T <= 0) return Math.max(0, S - K);

    const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T));
    const d2 = d1 - sigma * Math.sqrt(T);

    return S * normalCDF(d1) - K * Math.exp(-r * T) * normalCDF(d2);
};

/**
 * Black-Scholes Put Price
 */
const blackScholesPut = (S, K, T, r, sigma) => {
    if (T <= 0) return Math.max(0, K - S);

    const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T));
    const d2 = d1 - sigma * Math.sqrt(T);

    return K * Math.exp(-r * T) * normalCDF(-d2) - S * normalCDF(-d1);
};

/**
 * Calculate MV Straddle value before expiry using Black-Scholes
 * Straddle = Call + Put at same strike
 */
const calculateStraddleValueBeforeExpiry = (spotPrice, strike, entryPrice, size, daysToExpiry, iv = 0.8) => {
    const absSize = Math.abs(size);
    const isShort = size < 0;

    // Convert days to years
    const T = Math.max(daysToExpiry / 365.25, 0.0001);

    // Risk-free rate (assume ~5% for crypto)
    const r = 0.05;

    // Calculate straddle value using Black-Scholes
    // Straddle = Call + Put at same strike
    const callValue = blackScholesCall(spotPrice, strike, T, r, iv);
    const putValue = blackScholesPut(spotPrice, strike, T, r, iv);
    const straddleValue = callValue + putValue;

    // P&L calculation
    if (isShort) {
        // Short: profit when current straddle value < entry price
        return (entryPrice - straddleValue) * absSize * CONTRACT_MULTIPLIER;
    } else {
        // Long: profit when current straddle value > entry price
        return (straddleValue - entryPrice) * absSize * CONTRACT_MULTIPLIER;
    }
};

/**
 * Format currency for display
 */
const formatCurrency = (value) => {
    if (Math.abs(value) >= 1000) {
        return `$${(value / 1000).toFixed(1)}K`;
    }
    return `$${value.toFixed(2)}`;
};

/**
 * Format date for display
 */
const formatDate = (date) => {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const hours = date.getHours();
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const hour12 = hours % 12 || 12;
    return `${days[date.getDay()]}, ${date.getDate()} ${months[date.getMonth()]} ${hour12}:${minutes} ${ampm}`;
};

/**
 * Custom Tooltip - Sensibull Style
 */
const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;

    const expiry = payload.find((p) => p.dataKey === 'expiry')?.value ?? 0;
    const target = payload.find((p) => p.dataKey === 'target')?.value;

    return (
        <Paper
            sx={{
                p: 1.5,
                bgcolor: 'rgba(15, 23, 42, 0.95)',
                border: '1px solid',
                borderColor: 'primary.main',
                backdropFilter: 'blur(8px)',
                minWidth: 200,
            }}
        >
            <Typography variant="body2" fontWeight="bold" sx={{ color: '#f8fafc' }}>
                BTC: ${Number(label).toLocaleString()}
            </Typography>
            <Divider sx={{ my: 0.5, borderColor: 'rgba(255,255,255,0.1)' }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 0.5 }}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    On Expiry:
                </Typography>
                <Typography
                    variant="body2"
                    fontWeight="bold"
                    sx={{ color: expiry >= 0 ? '#10b981' : '#ef4444' }}
                >
                    {expiry >= 0 ? '+' : ''}{formatCurrency(expiry)}
                </Typography>
            </Box>
            {target !== undefined && (
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 0.5 }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                        On Target Date:
                    </Typography>
                    <Typography
                        variant="body2"
                        fontWeight="bold"
                        sx={{ color: '#3b82f6' }}
                    >
                        {target >= 0 ? '+' : ''}{formatCurrency(target)}
                    </Typography>
                </Box>
            )}
        </Paper>
    );
};

/**
 * Position Selection Chip
 */
const PositionChip = ({ position, isSelected, onToggle }) => {
    const isShort = position.size < 0;

    return (
        <Chip
            size="small"
            onClick={onToggle}
            icon={
                <Checkbox
                    checked={isSelected}
                    size="small"
                    sx={{
                        p: 0,
                        color: isShort ? '#ef4444' : '#10b981',
                        '&.Mui-checked': { color: isShort ? '#ef4444' : '#10b981' }
                    }}
                />
            }
            sx={{
                bgcolor: isSelected
                    ? (isShort ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)')
                    : 'rgba(255,255,255,0.05)',
                color: isSelected
                    ? (isShort ? '#ef4444' : '#10b981')
                    : 'text.secondary',
                fontWeight: 500,
                border: '1px solid',
                borderColor: isSelected
                    ? (isShort ? 'rgba(239,68,68,0.5)' : 'rgba(16,185,129,0.5)')
                    : 'rgba(255,255,255,0.1)',
                transition: 'all 0.2s ease',
                cursor: 'pointer',
                '&:hover': {
                    bgcolor: isShort ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)',
                    borderColor: isShort ? '#ef4444' : '#10b981',
                },
            }}
            label={`${isShort ? 'Short' : 'Long'} ${Math.abs(position.size)} @ $${position.strike.toLocaleString()}`}
        />
    );
};

/**
 * MV Straddle Payoff Graph Component
 */
const MVStraddlePayoffGraph = ({ positions = [], spotPrice: propSpotPrice }) => {
    // Chart state
    const [priceRangePercent, setPriceRangePercent] = useState(15);
    const [targetDaysFromNow, setTargetDaysFromNow] = useState(0);
    const [targetPricePercent, setTargetPricePercent] = useState(0);
    const [positionsExpanded, setPositionsExpanded] = useState(true);

    // Zoom state
    const [isZoomed, setIsZoomed] = useState(false);
    const [zoomDomain, setZoomDomain] = useState({ left: null, right: null });

    // Drag-to-zoom selection state
    const [selectionStart, setSelectionStart] = useState(null);
    const [selectionEnd, setSelectionEnd] = useState(null);
    const [isSelecting, setIsSelecting] = useState(false);

    // Selected positions (default: all selected)
    const [selectedPositions, setSelectedPositions] = useState(() => {
        const initial = {};
        positions.forEach(pos => {
            initial[pos.product_symbol] = true;
        });
        return initial;
    });

    // Update selected positions when positions change
    React.useEffect(() => {
        setSelectedPositions(prev => {
            const updated = { ...prev };
            positions.forEach(pos => {
                if (updated[pos.product_symbol] === undefined) {
                    updated[pos.product_symbol] = true;
                }
            });
            Object.keys(updated).forEach(symbol => {
                if (!positions.find(p => p.product_symbol === symbol)) {
                    delete updated[symbol];
                }
            });
            return updated;
        });
    }, [positions]);

    const togglePosition = useCallback((symbol) => {
        setSelectedPositions(prev => ({
            ...prev,
            [symbol]: !prev[symbol]
        }));
    }, []);

    const selectAll = useCallback(() => {
        const all = {};
        positions.forEach(pos => { all[pos.product_symbol] = true; });
        setSelectedPositions(all);
    }, [positions]);

    const deselectAll = useCallback(() => {
        const none = {};
        positions.forEach(pos => { none[pos.product_symbol] = false; });
        setSelectedPositions(none);
    }, [positions]);

    const selectedCount = Object.values(selectedPositions).filter(Boolean).length;

    // ========================================================================
    // PARSE POSITIONS & CALCULATE CHART DATA
    // ========================================================================
    const chartData = useMemo(() => {
        if (!positions || positions.length === 0) return null;

        const activePositions = positions.filter(pos => selectedPositions[pos.product_symbol]);

        if (activePositions.length === 0) {
            return { noSelection: true, allPositions: positions };
        }

        // Get spot price
        let spotPrice = propSpotPrice;
        if (!spotPrice) {
            const firstPos = activePositions[0];
            if (firstPos) {
                const parts = firstPos.product_symbol?.split('-') || [];
                const strike = parts.length >= 3 ? parseInt(parts[2]) : 0;
                spotPrice = strike || 95000;
            }
        }

        // Parse all active positions
        const parsedPositions = activePositions.map((pos) => {
            const parts = pos.product_symbol?.split('-') || [];
            const strike = parts.length >= 3 ? parseInt(parts[2]) : 0;
            const expiryCode = parts.length >= 4 ? parts[3] : '';

            let expiryDate = null;
            let daysToExpiry = 0;
            if (expiryCode.length === 6) {
                const day = parseInt(expiryCode.substring(0, 2));
                const month = parseInt(expiryCode.substring(2, 4)) - 1;
                const year = 2000 + parseInt(expiryCode.substring(4, 6));
                // BTC options expire at 5:30 PM IST = 12:00 UTC
                expiryDate = new Date(Date.UTC(year, month, day, 12, 0, 0));
                daysToExpiry = Math.max(0, (expiryDate - new Date()) / (1000 * 60 * 60 * 24));
            }

            // Get IV from position or default
            const iv = parseFloat(pos.iv) || 0.8;

            return {
                symbol: pos.product_symbol,
                strike,
                expiryDate,
                daysToExpiry,
                size: parseFloat(pos.size || 0),
                entryPrice: parseFloat(pos.entry_price || 0),
                markPrice: parseFloat(pos.mark_price || 0),
                currentPnl: parseFloat(pos.unrealized_pnl || 0),
                iv,
            };
        });

        // Find nearest expiry
        const nearestExpiry = parsedPositions.reduce(
            (min, p) => (p.expiryDate && p.expiryDate < min ? p.expiryDate : min),
            parsedPositions[0]?.expiryDate || new Date(Date.now() + 24 * 60 * 60 * 1000)
        );
        const now = new Date();
        const actualDaysToExpiry = Math.max(0, (nearestExpiry - now) / (1000 * 60 * 60 * 24));
        const minDaysToExpiry = Math.max(0.001, actualDaysToExpiry);

        // Calculate price range
        const allStrikes = parsedPositions.map((p) => p.strike).filter((s) => s > 0);
        const avgStrike = allStrikes.length > 0
            ? allStrikes.reduce((a, b) => a + b, 0) / allStrikes.length
            : spotPrice;

        const centerPrice = spotPrice || avgStrike;
        const minPrice = centerPrice * (1 - priceRangePercent / 100);
        const maxPrice = centerPrice * (1 + priceRangePercent / 100);
        const numPoints = 200;
        const priceStep = (maxPrice - minPrice) / numPoints;

        // Target date and price
        const targetDate = new Date(now.getTime() + targetDaysFromNow * 24 * 60 * 60 * 1000);
        const targetPrice = centerPrice * (1 + targetPricePercent / 100);
        const daysToExpiryFromTarget = Math.max(0, (nearestExpiry - targetDate) / (1000 * 60 * 60 * 24));

        const data = [];
        let globalMaxProfit = -Infinity;
        let globalMaxLoss = Infinity;
        let maxTargetProfit = -Infinity;
        let maxTargetLoss = Infinity;

        for (let i = 0; i <= numPoints; i++) {
            const price = minPrice + i * priceStep;
            const point = { price: Math.round(price) };

            // Calculate "On Expiry" payoff
            let expiryPayoff = 0;
            parsedPositions.forEach((pos) => {
                expiryPayoff += calculateStraddlePayoff(price, pos.strike, pos.entryPrice, pos.size);
            });

            // Calculate "On Target Date" payoff (before expiry)
            let targetPayoff = 0;
            parsedPositions.forEach((pos) => {
                const remainingDays = Math.max(0.001, pos.daysToExpiry - targetDaysFromNow);
                targetPayoff += calculateStraddleValueBeforeExpiry(
                    price,
                    pos.strike,
                    pos.entryPrice,
                    pos.size,
                    remainingDays,
                    pos.iv
                );
            });

            // Track min/max
            if (expiryPayoff > globalMaxProfit) globalMaxProfit = expiryPayoff;
            if (expiryPayoff < globalMaxLoss) globalMaxLoss = expiryPayoff;
            if (targetPayoff > maxTargetProfit) maxTargetProfit = targetPayoff;
            if (targetPayoff < maxTargetLoss) maxTargetLoss = targetPayoff;

            point.expiryProfit = expiryPayoff >= 0 ? expiryPayoff : 0;
            point.expiryLoss = expiryPayoff < 0 ? expiryPayoff : 0;
            point.expiry = expiryPayoff;
            point.target = targetPayoff;

            data.push(point);
        }

        // Calculate breakevens
        const breakevens = [];
        data.forEach((point, idx) => {
            if (idx > 0) {
                const prev = data[idx - 1].expiry;
                const curr = point.expiry;
                if ((prev < 0 && curr >= 0) || (prev > 0 && curr <= 0)) {
                    breakevens.push(point.price);
                }
            }
        });

        // Find projected profit at target price
        const targetPricePoint = data.find((d) => Math.abs(d.price - targetPrice) < priceStep * 1.5);
        const projectedProfit = targetPricePoint?.target ?? 0;

        // Smart Y-axis scaling
        const maxProfit = isFinite(globalMaxProfit) ? globalMaxProfit : 0;
        const maxLoss = isFinite(globalMaxLoss) ? globalMaxLoss : 0;
        const overallMax = Math.max(maxProfit, maxTargetProfit);
        const overallMin = Math.min(maxLoss, maxTargetLoss);

        const dataRange = overallMax - overallMin;
        const padding = Math.max(dataRange * 0.15, 0.5);

        let yMin = overallMin - padding;
        let yMax = overallMax + padding;

        const actualSpotPriceValue = propSpotPrice || spotPrice || centerPrice;

        // Debug logging
        console.log('[MVStraddlePayoffGraph] ATM Line Debug:', {
            propSpotPrice,
            calculatedSpotPrice: spotPrice,
            centerPrice,
            actualSpotPrice: actualSpotPriceValue,
            minPrice,
            maxPrice,
            isInRange: actualSpotPriceValue >= minPrice && actualSpotPriceValue <= maxPrice
        });

        return {
            data,
            positions: parsedPositions,
            allPositions: positions.map(pos => {
                const parts = pos.product_symbol?.split('-') || [];
                return {
                    symbol: pos.product_symbol,
                    strike: parts.length >= 3 ? parseInt(parts[2]) : 0,
                    size: parseFloat(pos.size || 0),
                    entryPrice: parseFloat(pos.entry_price || 0),
                };
            }),
            actualSpotPrice: actualSpotPriceValue,  // Real BTC market price for ATM line (fallback chain)
            spotPrice: centerPrice,  // Center price for calculations/display
            targetPrice,
            minPrice,
            maxPrice,
            maxProfit,
            maxLoss,
            breakevens,
            projectedProfit,
            targetDate,
            daysToExpiryFromTarget,
            minDaysToExpiry,
            nearestExpiry,
            yMin,
            yMax,
        };
    }, [positions, propSpotPrice, priceRangePercent, targetDaysFromNow, targetPricePercent, selectedPositions]);

    // ========================================================================
    // DRAG-TO-ZOOM HANDLERS
    // ========================================================================
    const handleMouseDown = useCallback((e) => {
        if (e && e.activeLabel) {
            setSelectionStart(e.activeLabel);
            setSelectionEnd(e.activeLabel);
            setIsSelecting(true);
        }
    }, []);

    const handleMouseMove = useCallback((e) => {
        if (isSelecting && e && e.activeLabel) {
            setSelectionEnd(e.activeLabel);
        }
    }, [isSelecting]);

    const handleMouseUp = useCallback(() => {
        if (isSelecting && selectionStart !== null && selectionEnd !== null) {
            const left = Math.min(selectionStart, selectionEnd);
            const right = Math.max(selectionStart, selectionEnd);

            // Only zoom if selection is meaningful (at least 1% of range)
            if (chartData && right - left > (chartData.maxPrice - chartData.minPrice) * 0.01) {
                setZoomDomain({ left, right });
                setIsZoomed(true);
            }
        }
        setSelectionStart(null);
        setSelectionEnd(null);
        setIsSelecting(false);
    }, [isSelecting, selectionStart, selectionEnd, chartData]);

    // Zoom button handlers
    const handleZoomIn = useCallback(() => {
        if (!chartData || chartData.noSelection) return;
        const { minPrice, maxPrice, spotPrice } = chartData;
        const currentLeft = isZoomed && zoomDomain.left ? zoomDomain.left : minPrice;
        const currentRight = isZoomed && zoomDomain.right ? zoomDomain.right : maxPrice;
        const currentCenter = (currentLeft + currentRight) / 2;
        const currentRange = currentRight - currentLeft;
        const newRange = currentRange * 0.5;

        if (newRange < 1000) return;

        const newLeft = Math.max(minPrice, currentCenter - newRange / 2);
        const newRight = Math.min(maxPrice, currentCenter + newRange / 2);

        setZoomDomain({ left: newLeft, right: newRight });
        setIsZoomed(true);
    }, [chartData, isZoomed, zoomDomain]);

    const handleZoomOut = useCallback(() => {
        if (!chartData || chartData.noSelection || !isZoomed) return;
        const { minPrice, maxPrice } = chartData;
        const currentLeft = zoomDomain.left || minPrice;
        const currentRight = zoomDomain.right || maxPrice;
        const currentCenter = (currentLeft + currentRight) / 2;
        const currentRange = currentRight - currentLeft;
        const newRange = currentRange * 2;

        let newLeft = currentCenter - newRange / 2;
        let newRight = currentCenter + newRange / 2;

        if (newLeft <= minPrice && newRight >= maxPrice) {
            setZoomDomain({ left: null, right: null });
            setIsZoomed(false);
            return;
        }

        setZoomDomain({
            left: Math.max(minPrice, newLeft),
            right: Math.min(maxPrice, newRight)
        });
    }, [chartData, isZoomed, zoomDomain]);

    const handleResetZoom = useCallback(() => {
        setZoomDomain({ left: null, right: null });
        setIsZoomed(false);
    }, []);

    // Get filtered data for display
    const displayData = useMemo(() => {
        if (!chartData || chartData.noSelection) return [];
        if (!isZoomed || !zoomDomain.left || !zoomDomain.right) {
            return chartData.data;
        }
        return chartData.data.filter(
            (d) => d.price >= zoomDomain.left && d.price <= zoomDomain.right
        );
    }, [chartData, isZoomed, zoomDomain]);

    // Recalculate Y bounds for zoomed view
    const zoomedYBounds = useMemo(() => {
        if (!displayData || displayData.length === 0 || !chartData) {
            return { yMin: chartData?.yMin || -10, yMax: chartData?.yMax || 10 };
        }

        let minY = Infinity;
        let maxY = -Infinity;

        displayData.forEach(d => {
            if (d.expiry < minY) minY = d.expiry;
            if (d.expiry > maxY) maxY = d.expiry;
            if (d.target < minY) minY = d.target;
            if (d.target > maxY) maxY = d.target;
        });

        const range = maxY - minY;
        const padding = Math.max(range * 0.15, 0.5);

        return {
            yMin: minY - padding,
            yMax: maxY + padding,
        };
    }, [displayData, chartData]);

    // ========================================================================
    // RENDER
    // ========================================================================
    if (!positions || positions.length === 0) {
        return (
            <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'background.default' }}>
                <Typography color="text.secondary">
                    No MV Straddle positions to display payoff graph
                </Typography>
            </Paper>
        );
    }

    if (chartData?.noSelection) {
        return (
            <Paper sx={{ p: 2, bgcolor: 'background.paper' }}>
                <Typography variant="h6" fontWeight="bold" sx={{ mb: 2 }}>
                    📈 MV Straddle Payoff
                </Typography>
                <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, mb: 2 }}>
                    <Typography variant="subtitle2" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                        Select Positions:
                        <Button size="small" startIcon={<SelectAllIcon />} onClick={selectAll}>
                            All
                        </Button>
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {chartData?.allPositions?.map((pos) => {
                            const parts = pos.product_symbol?.split('-') || [];
                            return (
                                <PositionChip
                                    key={pos.product_symbol}
                                    position={{
                                        symbol: pos.product_symbol,
                                        strike: parts.length >= 3 ? parseInt(parts[2]) : 0,
                                        size: parseFloat(pos.size || 0),
                                    }}
                                    isSelected={selectedPositions[pos.product_symbol]}
                                    onToggle={() => togglePosition(pos.product_symbol)}
                                />
                            );
                        })}
                    </Box>
                </Box>
                <Alert severity="info" sx={{ bgcolor: 'rgba(59,130,246,0.1)' }}>
                    Select at least one position to view the payoff graph
                </Alert>
            </Paper>
        );
    }

    const {
        spotPrice, actualSpotPrice, targetPrice, maxProfit, maxLoss, breakevens, projectedProfit,
        targetDate, daysToExpiryFromTarget, minDaysToExpiry, nearestExpiry, yMin, yMax
    } = chartData;

    const effectiveYMin = isZoomed ? zoomedYBounds.yMin : yMin;
    const effectiveYMax = isZoomed ? zoomedYBounds.yMax : yMax;

    return (
        <Paper sx={{ p: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
            {/* Header with Title and Controls */}
            <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
                <Typography variant="h6" fontWeight="bold">
                    Payoff Graph
                </Typography>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    {/* Legend */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Box sx={{ width: 16, height: 3, bgcolor: '#10b981', borderRadius: 1 }} />
                        <Typography variant="caption" color="text.secondary">On Expiry</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Box sx={{ width: 16, height: 3, bgcolor: '#3b82f6', borderRadius: 1 }} />
                        <Typography variant="caption" color="text.secondary">On Target Date</Typography>
                    </Box>

                    {/* Zoom Controls */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                        <IconButton
                            size="small"
                            onClick={handleZoomIn}
                            title="Zoom In"
                            sx={{ border: '1px solid rgba(255,255,255,0.1)' }}
                        >
                            <ZoomInIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                            size="small"
                            onClick={handleZoomOut}
                            disabled={!isZoomed}
                            title="Zoom Out"
                            sx={{ border: '1px solid rgba(255,255,255,0.1)' }}
                        >
                            <ZoomOutIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                            size="small"
                            onClick={handleResetZoom}
                            disabled={!isZoomed}
                            title="Reset"
                            sx={{ border: '1px solid rgba(255,255,255,0.1)' }}
                        >
                            <RestartAltIcon fontSize="small" />
                        </IconButton>
                    </Box>
                </Box>
            </Box>

            {/* Current Price & Drag Hint */}
            <Box sx={{ textAlign: 'center', mb: 1 }}>
                <Chip
                    label={`Current price: $${spotPrice.toLocaleString()}`}
                    size="small"
                    sx={{ bgcolor: 'rgba(59,130,246,0.2)', color: '#3b82f6', fontWeight: 600 }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                    👆 Drag on chart to select an area and zoom
                </Typography>
            </Box>

            {/* Position Selection - Collapsible */}
            <Box sx={{ mb: 2, bgcolor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
                <Box
                    sx={{
                        p: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                    }}
                    onClick={() => setPositionsExpanded(!positionsExpanded)}
                >
                    <Typography variant="caption" fontWeight="bold">
                        📊 Positions ({selectedCount}/{positions.length})
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <IconButton size="small" onClick={(e) => { e.stopPropagation(); selectAll(); }}>
                            <SelectAllIcon fontSize="small" />
                        </IconButton>
                        <IconButton size="small" onClick={(e) => { e.stopPropagation(); deselectAll(); }}>
                            <DeselectIcon fontSize="small" />
                        </IconButton>
                        {positionsExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                    </Box>
                </Box>
                <Collapse in={positionsExpanded}>
                    <Box sx={{ px: 1, pb: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {chartData.allPositions?.map((pos) => (
                            <PositionChip
                                key={pos.symbol}
                                position={pos}
                                isSelected={selectedPositions[pos.symbol]}
                                onToggle={() => togglePosition(pos.symbol)}
                            />
                        ))}
                    </Box>
                </Collapse>
            </Box>

            {/* Breakeven & Metrics Panel (Sensibull Style) */}
            <Box sx={{ mb: 2, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2 }}>
                {/* Profit Section */}
                <Box sx={{ p: 2, bgcolor: 'rgba(16,185,129,0.1)', borderRadius: 1, border: '1px solid rgba(16,185,129,0.3)' }}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                        Profit left
                    </Typography>
                    <Typography variant="h6" fontWeight="bold" sx={{ color: '#10b981' }}>
                        {isFinite(maxProfit) && maxProfit > 0 ? `+${formatCurrency(maxProfit)}` : 'Unlimited'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                        Max Profit: {isFinite(maxProfit) ? formatCurrency(Math.abs(maxProfit)) : 'Unlimited'}
                        {isFinite(maxProfit) && maxProfit > 0 && ` (+${((maxProfit / Math.abs(projectedProfit || 1)) * 100).toFixed(0)}%)`}
                    </Typography>
                </Box>

                {/* Loss Section */}
                <Box sx={{ p: 2, bgcolor: 'rgba(239,68,68,0.1)', borderRadius: 1, border: '1px solid rgba(239,68,68,0.3)' }}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                        Loss left
                    </Typography>
                    <Typography variant="h6" fontWeight="bold" sx={{ color: '#ef4444' }}>
                        {isFinite(maxLoss) && maxLoss < 0 ? formatCurrency(maxLoss) : 'Unlimited'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                        Max Loss: {isFinite(maxLoss) ? formatCurrency(Math.abs(maxLoss)) : 'Unlimited'}
                        {isFinite(maxLoss) && maxLoss < 0 && ` (${((maxLoss / Math.abs(projectedProfit || 1)) * 100).toFixed(0)}%)`}
                    </Typography>
                </Box>

                {/* Breakeven Section */}
                <Box sx={{ p: 2, bgcolor: 'rgba(251,191,36,0.1)', borderRadius: 1, border: '1px solid rgba(251,191,36,0.3)' }}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                        Breakeven
                    </Typography>
                    {breakevens.length > 0 ? (
                        <>
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                                {breakevens.length === 1 ? '1 point' : `${breakevens.length} points`}
                            </Typography>
                            {breakevens.map((be, idx) => {
                                const bePercent = ((be / spotPrice - 1) * 100).toFixed(1);
                                const sign = bePercent >= 0 ? '+' : '';
                                return (
                                    <Box key={idx} sx={{ mb: idx < breakevens.length - 1 ? 0.5 : 0 }}>
                                        <Typography variant="body2" fontWeight="bold" sx={{ color: '#fbbf24' }}>
                                            ${be.toLocaleString()}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            ({sign}{bePercent}%)
                                        </Typography>
                                    </Box>
                                );
                            })}
                        </>
                    ) : (
                        <>
                            <Typography variant="body2" fontWeight="bold" sx={{ color: '#fbbf24' }}>
                                N/A
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                No breakeven for this strategy
                            </Typography>
                        </>
                    )}
                </Box>

                {/* Reward/Risk Section */}
                <Box sx={{ p: 2, bgcolor: 'rgba(59,130,246,0.1)', borderRadius: 1, border: '1px solid rgba(59,130,246,0.3)' }}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                        Reward / Risk
                    </Typography>
                    {isFinite(maxProfit) && isFinite(maxLoss) && maxLoss !== 0 ? (
                        <>
                            <Typography variant="h6" fontWeight="bold" sx={{ color: '#3b82f6' }}>
                                {Math.abs(maxProfit / maxLoss).toFixed(2)} : 1
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                {maxProfit > Math.abs(maxLoss) ? 'Favorable' : maxProfit < Math.abs(maxLoss) ? 'Unfavorable' : 'Balanced'}
                            </Typography>
                        </>
                    ) : (
                        <>
                            <Typography variant="h6" fontWeight="bold" sx={{ color: '#3b82f6' }}>
                                N/A
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                Limited profit or loss
                            </Typography>
                        </>
                    )}
                </Box>
            </Box>

            {/* Chart */}
            <Box sx={{ height: 320, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1, p: 1 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                        data={displayData}
                        margin={{ top: 15, right: 30, left: 10, bottom: 10 }}
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        onMouseLeave={handleMouseUp}
                    >
                        <defs>
                            <linearGradient id="mvProfitGradient2" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                                <stop offset="95%" stopColor="#10b981" stopOpacity={0.02} />
                            </linearGradient>
                            <linearGradient id="mvLossGradient2" x1="0" y1="1" x2="0" y2="0">
                                <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
                            </linearGradient>
                        </defs>

                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />

                        <XAxis
                            dataKey="price"
                            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
                            stroke="rgba(255,255,255,0.4)"
                            fontSize={10}
                        />

                        <YAxis
                            domain={[effectiveYMin, effectiveYMax]}
                            tickFormatter={(v) => formatCurrency(v)}
                            stroke="rgba(255,255,255,0.4)"
                            fontSize={10}
                            width={55}
                        />

                        <Tooltip content={<CustomTooltip />} />

                        {/* Drag selection highlight */}
                        {isSelecting && selectionStart !== null && selectionEnd !== null && (
                            <ReferenceArea
                                x1={Math.min(selectionStart, selectionEnd)}
                                x2={Math.max(selectionStart, selectionEnd)}
                                fill="rgba(59, 130, 246, 0.3)"
                                stroke="#3b82f6"
                                strokeDasharray="3 3"
                            />
                        )}

                        {/* Zero line */}
                        <ReferenceLine y={0} stroke="rgba(255,255,255,0.4)" strokeDasharray="4 4" />

                        {/* Spot/ATM reference */}
                        {actualSpotPrice && actualSpotPrice > 0 && (
                            <ReferenceLine
                                x={actualSpotPrice}
                                stroke="#fbbf24"
                                strokeWidth={2}
                                strokeDasharray="6 3"
                                label={{ value: 'ATM', position: 'top', fill: '#fbbf24', fontSize: 10 }}
                            />
                        )}

                        {/* Strike references */}
                        {chartData.positions.map((pos, idx) => (
                            <ReferenceLine
                                key={idx}
                                x={pos.strike}
                                stroke="#9333ea"
                                strokeWidth={1}
                                strokeDasharray="2 2"
                            />
                        ))}

                        {/* Profit/Loss areas */}
                        <Area type="monotone" dataKey="expiryProfit" fill="url(#mvProfitGradient2)" stroke="none" />
                        <Area type="monotone" dataKey="expiryLoss" fill="url(#mvLossGradient2)" stroke="none" />

                        {/* Expiry line */}
                        <Line
                            type="monotone"
                            dataKey="expiry"
                            stroke="#10b981"
                            strokeWidth={2}
                            dot={false}
                            activeDot={{ r: 4, fill: '#10b981', stroke: '#fff' }}
                        />

                        {/* Target date line */}
                        <Line
                            type="monotone"
                            dataKey="target"
                            stroke="#3b82f6"
                            strokeWidth={2}
                            dot={false}
                            activeDot={{ r: 4, fill: '#3b82f6', stroke: '#fff' }}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </Box>

            {/* Projected Profit Display */}
            <Box sx={{ textAlign: 'center', mt: 1.5 }}>
                <Chip
                    label={`Projected profit at spot: ${projectedProfit >= 0 ? '+' : ''}${formatCurrency(projectedProfit)}`}
                    sx={{
                        bgcolor: projectedProfit >= 0 ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)',
                        color: projectedProfit >= 0 ? '#10b981' : '#ef4444',
                        fontWeight: 'bold',
                        px: 2,
                    }}
                />
            </Box>

            {/* BTC Target Price Slider */}
            <Box sx={{ mt: 2, px: 2, py: 1.5, bgcolor: 'rgba(0,0,0,0.3)', borderRadius: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" fontWeight="bold">BTC Target</Typography>
                        <Chip
                            label={targetPricePercent === 0 ? 'ATM' : 'Custom'}
                            size="small"
                            sx={{
                                height: 18,
                                fontSize: 10,
                                bgcolor: targetPricePercent === 0 ? 'rgba(251, 191, 36, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                                color: targetPricePercent === 0 ? '#fbbf24' : '#3b82f6',
                            }}
                        />
                        <Typography
                            variant="caption"
                            onClick={() => setTargetPricePercent(0)}
                            sx={{ color: '#3b82f6', cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                        >
                            Reset to ATM
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" color="text.secondary">
                            {targetPricePercent >= 0 ? '+' : ''}{targetPricePercent.toFixed(1)}%
                        </Typography>
                        <IconButton size="small" onClick={() => setTargetPricePercent((p) => Math.max(-30, p - 1))}>
                            <Typography sx={{ fontWeight: 'bold', fontSize: 14 }}>−</Typography>
                        </IconButton>
                        <Typography variant="body2" fontWeight="bold" sx={{ minWidth: 80, textAlign: 'center' }}>
                            ${targetPrice.toLocaleString()}
                        </Typography>
                        <IconButton size="small" onClick={() => setTargetPricePercent((p) => Math.min(30, p + 1))}>
                            <Typography sx={{ fontWeight: 'bold', fontSize: 14 }}>+</Typography>
                        </IconButton>
                    </Box>
                </Box>
                <Slider
                    value={targetPricePercent}
                    onChange={(e, v) => setTargetPricePercent(v)}
                    min={-30}
                    max={30}
                    step={0.5}
                    sx={{
                        color: '#3b82f6',
                        mt: 0.5,
                        '& .MuiSlider-thumb': { width: 12, height: 12 },
                        '& .MuiSlider-track': { height: 3 },
                        '& .MuiSlider-rail': { height: 3, bgcolor: 'rgba(255,255,255,0.1)' },
                    }}
                />
            </Box>

            {/* Time to Expiry Slider */}
            <Box sx={{ mt: 2, px: 2, py: 1.5, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                        Time to expiry: {Math.floor(daysToExpiryFromTarget)}D {Math.round((daysToExpiryFromTarget % 1) * 24)}H
                        {daysToExpiryFromTarget < 1 && ' (0 DTE)'}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <IconButton size="small" onClick={() => setTargetDaysFromNow((d) => Math.max(0, d - 1 / 24))} title="-1 hour">
                            <ChevronLeftIcon fontSize="small" />
                        </IconButton>
                        <Typography variant="caption" sx={{ minWidth: 160, textAlign: 'center' }}>
                            {formatDate(targetDate)}
                        </Typography>
                        <IconButton size="small" onClick={() => setTargetDaysFromNow((d) => Math.min(minDaysToExpiry, d + 1 / 24))} title="+1 hour">
                            <ChevronRightIcon fontSize="small" />
                        </IconButton>
                    </Box>
                </Box>
                <Slider
                    value={targetDaysFromNow}
                    onChange={(e, v) => setTargetDaysFromNow(v)}
                    min={0}
                    max={minDaysToExpiry}
                    step={minDaysToExpiry < 1 ? 1 / 24 : 0.5}
                    marks={[
                        { value: 0, label: 'Now' },
                        { value: minDaysToExpiry, label: minDaysToExpiry < 1 ? `${Math.round(minDaysToExpiry * 24)}h` : `${Math.ceil(minDaysToExpiry)}d` },
                    ]}
                    sx={{
                        '& .MuiSlider-markLabel': { fontSize: 10 },
                        '& .MuiSlider-thumb': { width: 12, height: 12 },
                    }}
                />
            </Box>

            {/* Statistics Row */}
            <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: 'wrap', gap: 0.5, justifyContent: 'center' }}>
                <Chip
                    label={`Max Profit: ${maxProfit >= 0 ? '+' : ''}${formatCurrency(maxProfit)}`}
                    size="small"
                    sx={{ bgcolor: 'rgba(16,185,129,0.15)', color: '#10b981', fontWeight: 600 }}
                />
                <Chip
                    label={`Max Loss: ${formatCurrency(maxLoss)}`}
                    size="small"
                    sx={{ bgcolor: 'rgba(239,68,68,0.15)', color: '#ef4444', fontWeight: 600 }}
                />
                {breakevens.length > 0 && (
                    <Chip
                        label={`Breakevens: ${breakevens.map((b) => `$${b.toLocaleString()}`).join(', ')}`}
                        size="small"
                        variant="outlined"
                        sx={{ fontWeight: 500 }}
                    />
                )}
            </Stack>
        </Paper>
    );
};

export default MVStraddlePayoffGraph;
