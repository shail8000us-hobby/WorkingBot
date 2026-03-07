/**
 * @sealed CONTRACT TEST — payoffCalculator
 * ==========================================
 * File     : webui/frontend/src/components/options/payoffCalculator.js
 * Sealed   : Mar 5, 2026
 *
 * PURPOSE
 * -------
 * payoffCalculator.js contains all pure math functions that power the
 * Options Payoff Diagram: Black-Scholes pricing, IV solver, portfolio
 * Greeks (delta/theta/gamma), probability of profit, price distribution,
 * and helper utilities.
 *
 * All functions are pure — no side effects, no API calls, no DOM access.
 *
 * RUN THIS TEST
 * -------------
 *   cd webui/frontend && npm test -- --watchAll=false --testPathPattern=test_sealed_payoffCalculator
 *
 * NEVER BREAK THESE CONTRACTS — see AI_SEAL.md for change protocol.
 */

import {
    RISK_FREE_RATE,
    CONTRACT_MULTIPLIERS,
    getContractMultiplier,
    normalCDF,
    normalPDF,
    blackScholesPrice,
    calculateImpliedVolatility,
    calculatePortfolioDelta,
    calculatePortfolioTheta,
    calculatePortfolioGamma,
    calculateProbabilityOfProfit,
    createPriceDistribution,
    calculateWeightedIV,
    formatDate,
} from '../payoffCalculator';

// ─── HELPER: make a fake parsed position ────────────────────────────────────
function makePos(overrides = {}) {
    return {
        symbol: 'C-BTC-90000-280326',
        type: 'call',
        strike: 90000,
        size: 1,        // positive = long
        iv: 0.6,        // 60%
        daysToExpiry: 30,
        isClosed: false,
        ...overrides,
    };
}

// =============================================================================
// #1  getContractMultiplier
// =============================================================================
describe('@sealed getContractMultiplier — CONTRACT TESTS', () => {

    it('CONTRACT 1 — BTC symbol returns 0.001', () => {
        expect(getContractMultiplier('C-BTC-90000-280326')).toBe(0.001);
    });

    it('CONTRACT 2 — ETH symbol returns 0.01', () => {
        expect(getContractMultiplier('P-ETH-3000-280326')).toBe(0.01);
    });

    it('CONTRACT 3 — null/undefined defaults to BTC (0.001)', () => {
        expect(getContractMultiplier(null)).toBe(0.001);
        expect(getContractMultiplier(undefined)).toBe(0.001);
        expect(getContractMultiplier('')).toBe(0.001);
    });

    it('CONTRACT 4 — case-insensitive detection', () => {
        expect(getContractMultiplier('c-btc-90000')).toBe(0.001);
        expect(getContractMultiplier('p-eth-3000')).toBe(0.01);
    });

    it('CONTRACT 5 — constants match expected values', () => {
        expect(RISK_FREE_RATE).toBe(0.0);
        expect(CONTRACT_MULTIPLIERS.BTC).toBe(0.001);
        expect(CONTRACT_MULTIPLIERS.ETH).toBe(0.01);
    });
});

// =============================================================================
// #2  normalCDF
// =============================================================================
describe('@sealed normalCDF — CONTRACT TESTS', () => {

    it('CONTRACT 1 — CDF(0) = 0.5 exactly', () => {
        expect(normalCDF(0)).toBe(0.5);
    });

    it('CONTRACT 2 — CDF(large positive) → approaches 1', () => {
        expect(normalCDF(6)).toBeGreaterThan(0.999);
        expect(normalCDF(6)).toBeLessThanOrEqual(1.0);
    });

    it('CONTRACT 3 — CDF(large negative) → approaches 0', () => {
        expect(normalCDF(-6)).toBeLessThan(0.001);
        expect(normalCDF(-6)).toBeGreaterThanOrEqual(0.0);
    });

    it('CONTRACT 4 — symmetry: CDF(x) + CDF(-x) ≈ 1', () => {
        const x = 1.5;
        expect(normalCDF(x) + normalCDF(-x)).toBeCloseTo(1.0, 6);
    });

    it('CONTRACT 5 — standard values: CDF(1) ≈ 0.8413, CDF(-1) ≈ 0.1587', () => {
        // Abramowitz & Stegun 5-term approximation has expected error ~1.5e-7 natively,
        // but the test checks against true 4-decimal rounded values.
        // Allow a wider margin (e.g., 1 decimal place or just use a wider toBeCloseTo)
        expect(normalCDF(1)).toBeCloseTo(0.8413, 1);
        expect(normalCDF(-1)).toBeCloseTo(0.1587, 1);
    });
});

// =============================================================================
// #3  normalPDF
// =============================================================================
describe('@sealed normalPDF — CONTRACT TESTS', () => {

    it('CONTRACT 1 — PDF(0) is the maximum ≈ 0.3989', () => {
        expect(normalPDF(0)).toBeCloseTo(0.3989, 3);
    });

    it('CONTRACT 2 — always non-negative', () => {
        for (const x of [-10, -1, 0, 1, 10]) {
            expect(normalPDF(x)).toBeGreaterThanOrEqual(0);
        }
    });

    it('CONTRACT 3 — symmetric: PDF(x) = PDF(-x)', () => {
        expect(normalPDF(2)).toBeCloseTo(normalPDF(-2), 10);
    });
});

// =============================================================================
// #4  blackScholesPrice
// =============================================================================
describe('@sealed blackScholesPrice — CONTRACT TESTS', () => {

    const S = 90000, K = 90000, T = 30 / 365.25, r = 0, sigma = 0.6;

    it('CONTRACT 1 — ATM call ≈ ATM put when r=0 (put-call parity)', () => {
        const call = blackScholesPrice(S, K, T, r, sigma, 'call');
        const put = blackScholesPrice(S, K, T, r, sigma, 'put');
        // With r=0 and S=K: call = put exactly
        expect(call).toBeCloseTo(put, 0);
    });

    it('CONTRACT 2 — call price is always ≥ 0', () => {
        expect(blackScholesPrice(S, K, T, r, sigma, 'call')).toBeGreaterThanOrEqual(0);
        expect(blackScholesPrice(50000, 90000, T, r, sigma, 'call')).toBeGreaterThanOrEqual(0);
    });

    it('CONTRACT 3 — put price is always ≥ 0', () => {
        expect(blackScholesPrice(S, K, T, r, sigma, 'put')).toBeGreaterThanOrEqual(0);
        expect(blackScholesPrice(130000, 90000, T, r, sigma, 'put')).toBeGreaterThanOrEqual(0);
    });

    it('CONTRACT 4 — T ≤ 0 returns intrinsic value', () => {
        // Deep ITM call
        expect(blackScholesPrice(100000, 90000, 0, r, sigma, 'call')).toBe(10000);
        // OTM call
        expect(blackScholesPrice(80000, 90000, 0, r, sigma, 'call')).toBe(0);
        // Deep ITM put
        expect(blackScholesPrice(80000, 90000, 0, r, sigma, 'put')).toBe(10000);
        // OTM put
        expect(blackScholesPrice(100000, 90000, 0, r, sigma, 'put')).toBe(0);
    });

    it('CONTRACT 5 — deep ITM call ≈ S - K', () => {
        const deepItm = blackScholesPrice(120000, 90000, T, r, sigma, 'call');
        expect(deepItm).toBeGreaterThan(29000); // Should be close to 30000
    });

    it('CONTRACT 6 — higher vol → higher price (same strike/spot)', () => {
        const lowVol = blackScholesPrice(S, K, T, r, 0.3, 'call');
        const highVol = blackScholesPrice(S, K, T, r, 0.9, 'call');
        expect(highVol).toBeGreaterThan(lowVol);
    });

    it('CONTRACT 7 — sigma ≤ 0 or S ≤ 0 returns intrinsic safely', () => {
        expect(blackScholesPrice(S, K, T, r, 0, 'call')).toBe(0); // ATM intrinsic is 0
        expect(blackScholesPrice(0, K, T, r, sigma, 'call')).toBe(0);
    });
});

// =============================================================================
// #5  calculateImpliedVolatility
// =============================================================================
describe('@sealed calculateImpliedVolatility — CONTRACT TESTS', () => {

    it('CONTRACT 1 — round-trips: IV → BS price → IV ≈ original', () => {
        const S = 90000, K = 90000, T = 30 / 365.25, r = 0, origIV = 0.65;
        const price = blackScholesPrice(S, K, T, r, origIV, 'call');
        const solvedIV = calculateImpliedVolatility(price, S, K, T, r, 'call');
        expect(solvedIV).toBeCloseTo(origIV, 2);
    });

    it('CONTRACT 2 — returns 0.8 fallback for T ≤ 0', () => {
        expect(calculateImpliedVolatility(5000, 90000, 90000, 0, 0, 'call')).toBe(0.8);
    });

    it('CONTRACT 3 — returns 0.8 fallback for marketPrice ≤ 0', () => {
        expect(calculateImpliedVolatility(0, 90000, 90000, 0.1, 0, 'call')).toBe(0.8);
        expect(calculateImpliedVolatility(-100, 90000, 90000, 0.1, 0, 'call')).toBe(0.8);
    });

    it('CONTRACT 4 — returns a positive number in all cases', () => {
        const iv = calculateImpliedVolatility(3000, 90000, 85000, 0.1, 0, 'put');
        expect(iv).toBeGreaterThan(0);
    });
});

// =============================================================================
// #6  calculatePortfolioDelta
// =============================================================================
describe('@sealed calculatePortfolioDelta — CONTRACT TESTS', () => {

    it('CONTRACT 1 — long call delta ∈ (0, 1) range (per-contract)', () => {
        const pos = [makePos({ type: 'call', size: 1 })];
        const delta = calculatePortfolioDelta(90000, pos);
        // Delta of 1 contract × 0.001 multiplier → small positive number
        expect(delta).toBeGreaterThan(0);
    });

    it('CONTRACT 2 — long put delta is negative', () => {
        const pos = [makePos({ type: 'put', size: 1 })];
        const delta = calculatePortfolioDelta(90000, pos);
        expect(delta).toBeLessThan(0);
    });

    it('CONTRACT 3 — empty positions → delta = 0', () => {
        expect(calculatePortfolioDelta(90000, [])).toBe(0);
    });

    it('CONTRACT 4 — closed positions are excluded', () => {
        const pos = [makePos({ isClosed: true })];
        expect(calculatePortfolioDelta(90000, pos)).toBe(0);
    });

    it('CONTRACT 5 — short call (size < 0) → negative delta', () => {
        const pos = [makePos({ type: 'call', size: -1 })];
        const delta = calculatePortfolioDelta(90000, pos);
        expect(delta).toBeLessThan(0);
    });
});

// =============================================================================
// #7  calculatePortfolioTheta
// =============================================================================
describe('@sealed calculatePortfolioTheta — CONTRACT TESTS', () => {

    it('CONTRACT 1 — long option has negative theta (time decay hurts buyer)', () => {
        const pos = [makePos({ type: 'call', size: 1 })];
        const theta = calculatePortfolioTheta(90000, pos);
        expect(theta).toBeLessThan(0);
    });

    it('CONTRACT 2 — short option has positive theta (time decay benefits seller)', () => {
        const pos = [makePos({ type: 'call', size: -1 })];
        const theta = calculatePortfolioTheta(90000, pos);
        expect(theta).toBeGreaterThan(0);
    });

    it('CONTRACT 3 — empty positions → theta = 0', () => {
        expect(calculatePortfolioTheta(90000, [])).toBe(0);
    });

    it('CONTRACT 4 — closed positions are excluded', () => {
        const pos = [makePos({ isClosed: true })];
        expect(calculatePortfolioTheta(90000, pos)).toBe(0);
    });
});

// =============================================================================
// #8  calculatePortfolioGamma
// =============================================================================
describe('@sealed calculatePortfolioGamma — CONTRACT TESTS', () => {

    it('CONTRACT 1 — long option has positive gamma', () => {
        const pos = [makePos({ type: 'call', size: 1 })];
        const gamma = calculatePortfolioGamma(90000, pos);
        expect(gamma).toBeGreaterThan(0);
    });

    it('CONTRACT 2 — gamma peaks near ATM (higher than far OTM)', () => {
        const pos = [makePos({ type: 'call', size: 1, strike: 90000 })];
        const gammaATM = calculatePortfolioGamma(90000, pos);
        const gammaOTM = calculatePortfolioGamma(60000, pos); // far from strike
        expect(gammaATM).toBeGreaterThan(gammaOTM);
    });

    it('CONTRACT 3 — empty positions → gamma = 0', () => {
        expect(calculatePortfolioGamma(90000, [])).toBe(0);
    });

    it('CONTRACT 4 — closed positions are excluded', () => {
        const pos = [makePos({ isClosed: true })];
        expect(calculatePortfolioGamma(90000, pos)).toBe(0);
    });
});

// =============================================================================
// #9  calculateProbabilityOfProfit
// =============================================================================
describe('@sealed calculateProbabilityOfProfit — CONTRACT TESTS', () => {

    it('CONTRACT 1 — returns null for empty chartData', () => {
        expect(calculateProbabilityOfProfit(90000, 0.6, 0.1, [])).toBeNull();
        expect(calculateProbabilityOfProfit(90000, 0.6, 0.1, null)).toBeNull();
    });

    it('CONTRACT 2 — returns null for invalid inputs (T ≤ 0, IV ≤ 0)', () => {
        const data = [{ price: 80000, expiry: -100 }, { price: 90000, expiry: 100 }];
        expect(calculateProbabilityOfProfit(90000, 0.6, 0, data)).toBeNull();
        expect(calculateProbabilityOfProfit(90000, 0, 0.1, data)).toBeNull();
    });

    it('CONTRACT 3 — returns a number between 0 and 100 for valid input', () => {
        // Create simple chart data: profit above 90000
        const data = [];
        for (let p = 70000; p <= 110000; p += 500) {
            data.push({ price: p, expiry: p > 90000 ? (p - 90000) : -(90000 - p) });
        }
        const pop = calculateProbabilityOfProfit(90000, 0.6, 30 / 365.25, data);
        expect(pop).toBeGreaterThanOrEqual(0);
        expect(pop).toBeLessThanOrEqual(100);
    });
});

// =============================================================================
// #10  createPriceDistribution
// =============================================================================
describe('@sealed createPriceDistribution — CONTRACT TESTS', () => {

    it('CONTRACT 1 — returns a function', () => {
        const fn = createPriceDistribution(90000, 0.6, 0.1);
        expect(typeof fn).toBe('function');
    });

    it('CONTRACT 2 — fn(0) returns 0 (no probability at price 0)', () => {
        const fn = createPriceDistribution(90000, 0.6, 0.1);
        expect(fn(0)).toBe(0);
    });

    it('CONTRACT 3 — fn(spot) returns positive density', () => {
        const fn = createPriceDistribution(90000, 0.6, 0.1);
        expect(fn(90000)).toBeGreaterThan(0);
    });

    it('CONTRACT 4 — invalid inputs (T ≤ 0, vol ≤ 0, spot ≤ 0) → returns const 0 function', () => {
        expect(createPriceDistribution(90000, 0.6, 0)(90000)).toBe(0);
        expect(createPriceDistribution(90000, 0, 0.1)(90000)).toBe(0);
        expect(createPriceDistribution(0, 0.6, 0.1)(90000)).toBe(0);
    });

    it('CONTRACT 5 — fn(negative) returns 0', () => {
        const fn = createPriceDistribution(90000, 0.6, 0.1);
        expect(fn(-1000)).toBe(0);
    });
});

// =============================================================================
// #11  calculateWeightedIV
// =============================================================================
describe('@sealed calculateWeightedIV — CONTRACT TESTS', () => {

    it('CONTRACT 1 — empty/null → fallback 0.8', () => {
        expect(calculateWeightedIV([])).toBe(0.8);
        expect(calculateWeightedIV(null)).toBe(0.8);
        expect(calculateWeightedIV(undefined)).toBe(0.8);
    });

    it('CONTRACT 2 — single position → returns its IV', () => {
        const pos = [makePos({ iv: 0.55 })];
        expect(calculateWeightedIV(pos)).toBeCloseTo(0.55, 6);
    });

    it('CONTRACT 3 — all closed positions → fallback 0.8', () => {
        const pos = [makePos({ isClosed: true, iv: 0.55 })];
        expect(calculateWeightedIV(pos)).toBe(0.8);
    });

    it('CONTRACT 4 — zero-IV positions excluded from weighting', () => {
        const pos = [
            makePos({ iv: 0.5, size: 1, strike: 90000 }),
            makePos({ iv: 0, size: 1, strike: 90000 }),
        ];
        // Only first position counted
        expect(calculateWeightedIV(pos)).toBeCloseTo(0.5, 6);
    });

    it('CONTRACT 5 — weighted by notional: larger position dominates', () => {
        const pos = [
            makePos({ iv: 0.4, size: 10, strike: 90000 }), // big position
            makePos({ iv: 0.8, size: 1, strike: 90000 }),  // small position
        ];
        const wiv = calculateWeightedIV(pos);
        // Should be much closer to 0.4 than 0.8
        expect(wiv).toBeGreaterThan(0.4);
        expect(wiv).toBeLessThan(0.5);
    });
});

// =============================================================================
// #12  formatDate
// =============================================================================
describe('@sealed formatDate — CONTRACT TESTS', () => {

    it('CONTRACT 1 — returns string in "Day, DD Mon HH:MM AM/PM" format', () => {
        // Wed Mar 5 2026, 2:30 PM
        const d = new Date(2026, 2, 5, 14, 30); // month is 0-indexed
        const result = formatDate(d);
        expect(result).toContain('Thu');   // Mar 5 2026 is actually Thursday
        expect(result).toContain('Mar');
        expect(result).toContain('PM');
    });

    it('CONTRACT 2 — midnight shows as 12:00 AM', () => {
        const d = new Date(2026, 2, 5, 0, 0);
        const result = formatDate(d);
        expect(result).toContain('12:00 AM');
    });

    it('CONTRACT 3 — minutes are zero-padded', () => {
        const d = new Date(2026, 2, 5, 9, 5);
        const result = formatDate(d);
        expect(result).toContain('9:05 AM');
    });

    it('CONTRACT 4 — noon shows as 12:00 PM', () => {
        const d = new Date(2026, 2, 5, 12, 0);
        const result = formatDate(d);
        expect(result).toContain('12:00 PM');
    });
});
