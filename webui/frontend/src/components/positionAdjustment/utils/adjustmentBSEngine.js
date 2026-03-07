/**
 * Adjustment Black-Scholes Engine
 * =================================
 * Black-Scholes based calculation module for pre-expiry payoff curves,
 * theta fan, probability distribution, delta profile, and stress testing.
 *
 * This module extends the adjustment system without modifying the existing
 * adjustmentPayoffEngine.js (which handles at-expiry intrinsic only).
 *
 * Imports sealed functions from payoffCalculator.js (read-only).
 *
 * Created: March 6, 2026
 */

import {
    blackScholesPrice,
    normalCDF,
    createPriceDistribution,
    calculateImpliedVolatility,
    RISK_FREE_RATE,
} from '../../options/payoffCalculator';
import { getContractMultiplier } from '../../../utils/constants';
import { parsePositionSymbol, getTimeToExpiry } from './adjustmentPayoffEngine';

// ============================================================================
// IV RESOLUTION
// ============================================================================

/**
 * Resolve implied volatility for a position from its market price.
 * Uses Newton-Raphson IV solver from payoffCalculator.js (sealed).
 *
 * @param {Object} position - Position object with product_symbol, entry_price/mark_price
 * @param {number} spotPrice - Current spot price
 * @returns {number} IV as decimal (e.g. 0.8 for 80%), defaults to 0.8
 */
export function resolvePositionIV(position, spotPrice) {
    const parsed = parsePositionSymbol(position.product_symbol);
    if (!parsed) return 0.8;

    const { type, strike, expiry } = parsed;
    const marketPrice = position.mark_price || Math.abs(position.entry_price) || 0;
    const T = getTimeToExpiry(expiry);

    if (marketPrice <= 0 || spotPrice <= 0 || strike <= 0 || T <= 0.001) {
        return 0.8;
    }

    try {
        const iv = calculateImpliedVolatility(marketPrice, spotPrice, strike, T, RISK_FREE_RATE, type);
        // Clamp to reasonable range
        return Math.max(0.05, Math.min(3.0, iv));
    } catch {
        return 0.8;
    }
}

/**
 * Get weighted average IV across all positions.
 *
 * @param {Array} positions - Position objects
 * @param {number} spotPrice - Current spot price
 * @returns {number} Weighted average IV
 */
export function getWeightedIV(positions, spotPrice) {
    if (!positions || positions.length === 0) return 0.8;

    let totalWeight = 0;
    let weightedSum = 0;

    positions.forEach(pos => {
        const parsed = parsePositionSymbol(pos.product_symbol);
        if (!parsed) return;

        const iv = resolvePositionIV(pos, spotPrice);
        const multiplier = getContractMultiplier(pos.product_symbol);
        const weight = Math.abs(pos.size || 0) * parsed.strike * multiplier;

        if (weight > 0) {
            weightedSum += iv * weight;
            totalWeight += weight;
        }
    });

    return totalWeight > 0 ? weightedSum / totalWeight : 0.8;
}

// ============================================================================
// PRE-EXPIRY PAYOFF (Black-Scholes)
// ============================================================================

/**
 * Calculate PnL for a single position at a given spot price and time using BS.
 *
 * PnL = (BS_price_now - entry_price) × size × contractMultiplier
 *
 * @param {Object} position - Position object
 * @param {number} spotAtTarget - Hypothetical spot price
 * @param {number} T - Time to expiry in years at the target date
 * @param {number} iv - Implied volatility
 * @returns {number} PnL in USD
 */
function singlePositionBSPayoff(position, spotAtTarget, T, iv) {
    const parsed = parsePositionSymbol(position.product_symbol);
    if (!parsed) return 0;

    const { type, strike } = parsed;
    const size = position.size || 0;
    const entryPrice = Math.abs(position.entry_price || 0);
    const contractMultiplier = getContractMultiplier(position.product_symbol);

    // BS theoretical value at target date
    const theoreticalPrice = blackScholesPrice(spotAtTarget, strike, T, RISK_FREE_RATE, iv, type);

    // PnL = (current_value - entry_cost) × direction × contracts × multiplier
    const isLong = size > 0;
    const direction = isLong ? 1 : -1;
    const pnl = (theoreticalPrice - entryPrice) * direction * Math.abs(size) * contractMultiplier;

    return pnl;
}

/**
 * Calculate portfolio payoff at a specific time using Black-Scholes.
 *
 * @param {Array} positions - Array of position objects
 * @param {number} spotPrice - Current spot price (for IV resolution)
 * @param {number[]} priceRange - Array of price points for X-axis
 * @param {number} daysToTarget - Days from now until the target date
 * @param {number} [overrideIV] - Optional IV override (otherwise resolved per-position)
 * @returns {Array} Array of { price, pnl } objects
 */
export function calculatePreExpiryPayoff(positions, spotPrice, priceRange, daysToTarget, overrideIV) {
    if (!positions || positions.length === 0 || !priceRange || priceRange.length === 0) {
        return priceRange.map(price => ({ price, pnl: 0 }));
    }

    // Resolve IV per position (or use override)
    const positionsWithIV = positions.map(pos => ({
        pos,
        iv: overrideIV || resolvePositionIV(pos, spotPrice),
        T: Math.max(0.0001, getTimeToExpiry(parsePositionSymbol(pos.product_symbol)?.expiry) - (daysToTarget / 365.25)),
    }));

    return priceRange.map(price => {
        let totalPnl = 0;
        positionsWithIV.forEach(({ pos, iv, T }) => {
            // If T <= 0, use intrinsic (at expiry)
            const effectiveT = Math.max(0, T);
            totalPnl += singlePositionBSPayoff(pos, price, effectiveT, iv);
        });
        return {
            price,
            pnl: Math.round(totalPnl * 100) / 100,
        };
    });
}

// ============================================================================
// THETA FAN (MULTI-DATE DECAY CURVES)
// ============================================================================

/**
 * Calculate theta fan — 6 payoff curves at different time points.
 * T-10, T-7, T-5, T-3, T-1, T-0 (expiry)
 *
 * @param {Array} positions - Position objects
 * @param {number} spotPrice - Current spot price
 * @param {number[]} priceRange - Array of price points
 * @param {number} daysToExpiry - Days until expiry
 * @returns {Array} Array of { price, t10, t7, t5, t3, t1, expiry } objects
 */
export function calculateThetaFanCurves(positions, spotPrice, priceRange, daysToExpiry) {
    if (!positions || positions.length === 0) {
        return priceRange.map(price => ({
            price, t10: 0, t7: 0, t5: 0, t3: 0, t1: 0, expiry: 0,
        }));
    }

    const avgIV = getWeightedIV(positions, spotPrice);

    // Days before expiry for each curve
    const targetDays = [
        { key: 't10', daysBeforeExpiry: 10 },
        { key: 't7', daysBeforeExpiry: 7 },
        { key: 't5', daysBeforeExpiry: 5 },
        { key: 't3', daysBeforeExpiry: 3 },
        { key: 't1', daysBeforeExpiry: 1 },
        { key: 'expiry', daysBeforeExpiry: 0 },
    ];

    // Compute each curve
    const curves = {};
    targetDays.forEach(({ key, daysBeforeExpiry }) => {
        const daysFromNow = Math.max(0, daysToExpiry - daysBeforeExpiry);
        curves[key] = calculatePreExpiryPayoff(positions, spotPrice, priceRange, daysFromNow, avgIV);
    });

    // Merge into single data array for chart
    return priceRange.map((price, i) => {
        const row = { price };
        targetDays.forEach(({ key }) => {
            row[key] = curves[key][i]?.pnl || 0;
        });
        return row;
    });
}

// ============================================================================
// PROBABILITY DISTRIBUTION OVERLAY
// ============================================================================

/**
 * Calculate probability distribution overlay data for the chart.
 * Uses lognormal distribution (reusing createPriceDistribution from payoffCalculator.js).
 *
 * @param {number} spotPrice - Current spot price
 * @param {number} iv - Implied volatility
 * @param {number} timeToExpiry - Time to expiry in years
 * @param {number[]} priceRange - Array of price points
 * @param {number} [skewShift=0] - Put skew shift in $ (positive = shift peak left)
 * @returns {Array} Array of { price, density } with density normalized to 0-100 range
 */
export function calculateProbabilityOverlay(spotPrice, iv, timeToExpiry, priceRange, skewShift = 0) {
    if (!spotPrice || !iv || !timeToExpiry || timeToExpiry <= 0) {
        return priceRange.map(price => ({ price, density: 0 }));
    }

    // Adjust spot for skew (shift distribution peak slightly left)
    const adjustedSpot = spotPrice - skewShift;
    const pdfFn = createPriceDistribution(adjustedSpot, iv, timeToExpiry);

    // Calculate raw densities
    const rawData = priceRange.map(price => ({
        price,
        density: pdfFn(price),
    }));

    // Normalize to 0-100 range for chart overlay
    const maxDensity = Math.max(...rawData.map(d => d.density), 0.0001);
    return rawData.map(d => ({
        price: d.price,
        density: (d.density / maxDensity) * 100,
    }));
}

// ============================================================================
// DELTA PROFILE
// ============================================================================

/**
 * Calculate delta at each price point using finite difference.
 * delta ≈ [V(S+ε) - V(S-ε)] / (2ε)
 *
 * @param {Array} positions - Position objects
 * @param {number} spotPrice - Current spot price
 * @param {number[]} priceRange - Array of price points
 * @param {number} daysToTarget - Days from now to target date
 * @returns {Array} Array of { price, delta } objects
 */
export function calculateDeltaProfile(positions, spotPrice, priceRange, daysToTarget) {
    if (!positions || positions.length === 0) {
        return priceRange.map(price => ({ price, delta: 0 }));
    }

    const epsilon = 100; // $100 bump for finite difference
    const avgIV = getWeightedIV(positions, spotPrice);

    return priceRange.map(price => {
        const pUp = calculatePreExpiryPayoff(positions, spotPrice, [price + epsilon], daysToTarget, avgIV);
        const pDown = calculatePreExpiryPayoff(positions, spotPrice, [price - epsilon], daysToTarget, avgIV);

        const delta = (pUp[0].pnl - pDown[0].pnl) / (2 * epsilon);
        return {
            price,
            delta: Math.round(delta * 10000) / 10000,
        };
    });
}

// ============================================================================
// STRESS TEST MATRIX
// ============================================================================

/**
 * Price move scenarios (rows)
 */
const PRICE_MOVES = [-0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15];
const PRICE_MOVE_LABELS = ['-15%', '-10%', '-5%', '0%', '+5%', '+10%', '+15%'];

/**
 * IV change scenarios (columns) — in absolute vol points
 */
const IV_CHANGES = [-0.20, -0.10, 0, 0.10, 0.20];
const IV_CHANGE_LABELS = ['-20 vol', '-10 vol', '0', '+10 vol', '+20 vol'];

/**
 * Calculate stress test matrix for a set of positions.
 * Returns a 7×5 matrix of PnL values under different price & IV scenarios.
 *
 * @param {Array} positions - Position objects
 * @param {number} spotPrice - Current spot price
 * @param {number} daysToTarget - Days from now to target date
 * @returns {Object} { matrix: number[][], rowLabels, colLabels }
 */
export function calculateStressMatrix(positions, spotPrice, daysToTarget) {
    if (!positions || positions.length === 0 || !spotPrice) {
        return {
            matrix: PRICE_MOVES.map(() => IV_CHANGES.map(() => 0)),
            rowLabels: PRICE_MOVE_LABELS,
            colLabels: IV_CHANGE_LABELS,
        };
    }

    const baseIV = getWeightedIV(positions, spotPrice);

    const matrix = PRICE_MOVES.map(priceMove => {
        const stressedSpot = spotPrice * (1 + priceMove);

        return IV_CHANGES.map(ivChange => {
            const stressedIV = Math.max(0.05, baseIV + ivChange);

            // Calculate portfolio PnL under this scenario
            let totalPnl = 0;
            positions.forEach(pos => {
                const parsed = parsePositionSymbol(pos.product_symbol);
                if (!parsed) return;

                const T = Math.max(0, getTimeToExpiry(parsed.expiry) - (daysToTarget / 365.25));
                totalPnl += singlePositionBSPayoff(pos, stressedSpot, T, stressedIV);
            });

            return Math.round(totalPnl * 100) / 100;
        });
    });

    return {
        matrix,
        rowLabels: PRICE_MOVE_LABELS,
        colLabels: IV_CHANGE_LABELS,
    };
}

// ============================================================================
// NET DEBIT/CREDIT CALCULATION
// ============================================================================

/**
 * Calculate net debit/credit for proposed trades.
 * Positive = debit (net cost to enter), negative = credit (net premium received).
 *
 * @param {Array} proposedTrades - Array of trade objects { side, quantity, premium/ltp/price }
 * @returns {Object} { netAmount, perLot, totalQty, isDebit }
 */
export function calculateNetDebitCredit(proposedTrades) {
    if (!proposedTrades || proposedTrades.length === 0) {
        return { netAmount: 0, perLot: 0, totalQty: 0, isDebit: true };
    }

    let totalDebit = 0;
    let totalCredit = 0;
    let totalQty = 0;

    proposedTrades.forEach(trade => {
        const qty = Math.abs(trade.quantity || 1);
        const price = trade.premium || trade.ltp || trade.price || 0;
        const multiplier = getContractMultiplier(trade.symbol || `C-${trade.underlying || 'BTC'}-${trade.strike}-000000`);
        const amount = qty * price * multiplier;

        totalQty += qty;

        if (trade.side === 'buy') {
            totalDebit += amount; // Buying costs money
        } else {
            totalCredit += amount; // Selling receives money
        }
    });

    const netAmount = totalDebit - totalCredit; // Positive = debit
    const perLot = totalQty > 0 ? netAmount / totalQty : 0;

    return {
        netAmount: Math.round(netAmount * 100) / 100,
        perLot: Math.round(perLot * 100) / 100,
        totalQty,
        isDebit: netAmount >= 0,
    };
}

// ============================================================================
// DYNAMIC PRICE RANGE
// ============================================================================

/**
 * Generate price range that auto-expands to cover all strikes ±5%.
 *
 * @param {number} spotPrice - Current spot price
 * @param {Array} allPositions - All position objects (current + proposed)
 * @param {number} defaultRangePercent - Default range if no strikes (default 15%)
 * @param {number} points - Number of data points
 * @returns {number[]} Array of price points
 */
export function generateDynamicPriceRange(spotPrice, allPositions, defaultRangePercent = 15, points = 100) {
    let minStrike = spotPrice;
    let maxStrike = spotPrice;

    if (allPositions && allPositions.length > 0) {
        allPositions.forEach(pos => {
            const parsed = parsePositionSymbol(pos.product_symbol);
            if (parsed && parsed.strike) {
                minStrike = Math.min(minStrike, parsed.strike);
                maxStrike = Math.max(maxStrike, parsed.strike);
            }
        });
    }

    // Expand by 5% beyond lowest/highest strike
    const rangeMin = minStrike * 0.95;
    const rangeMax = maxStrike * 1.05;

    // Ensure at least the default range around spot
    const defaultMin = spotPrice * (1 - defaultRangePercent / 100);
    const defaultMax = spotPrice * (1 + defaultRangePercent / 100);

    const finalMin = Math.min(rangeMin, defaultMin);
    const finalMax = Math.max(rangeMax, defaultMax);

    const step = (finalMax - finalMin) / (points - 1);
    const prices = [];
    for (let i = 0; i < points; i++) {
        prices.push(Math.round(finalMin + i * step));
    }
    return prices;
}

// ============================================================================
// EXPORTS
// ============================================================================

export default {
    resolvePositionIV,
    getWeightedIV,
    calculatePreExpiryPayoff,
    calculateThetaFanCurves,
    calculateProbabilityOverlay,
    calculateDeltaProfile,
    calculateStressMatrix,
    calculateNetDebitCredit,
    generateDynamicPriceRange,
};
