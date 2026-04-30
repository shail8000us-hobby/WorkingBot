/**
 * usePayoffData — Custom hook for Options Payoff data computation
 *
 * Extracted from OptionsPayoffDiagram.js (D2) to separate computation
 * from presentation. Contains parsedPositions and chartData useMemos.
 *
 * @version 1.0.0
 */

import { useMemo } from 'react';
import {
  blackScholesPrice,
  calculateImpliedVolatility,
  getContractMultiplier,
  RISK_FREE_RATE,
  createPriceDistribution,
  calculateWeightedIV,
  calculateProbabilityOfProfit,
} from './payoffCalculator';

/**
 * Parse raw position data into normalized format for payoff computation.
 *
 * @param {Array} positions - Raw positions from API
 * @param {Array} selectedPositions - Whitelisted product symbols
 * @param {Array} futuresPositions - Futures positions
 * @returns {Object|null} Parsed positions + spotPrice + minDaysToExpiry + nearestExpiry
 */
export const useParsedPositions = (positions, selectedPositions, futuresPositions, indexPrices = {}) => {
  return useMemo(() => {
    if (!positions || positions.length === 0) return null;

    // When no positions are explicitly selected, show all — keeping the payoff
    // aligned with the position rows by default. An explicit selection narrows the view.
    const visiblePositions = selectedPositions.length > 0
      ? positions.filter((p) => selectedPositions.includes(p.product_symbol))
      : positions;

    // Determine underlying asset from visible positions (BTC or ETH)
    const underlying = visiblePositions.length > 0
      ? (visiblePositions[0].product_symbol.split('-')[1] || 'BTC')
      : 'BTC';

    // Use live index price as authoritative spot (same for all expiries).
    // greeks.spot varies per expiry on Delta Exchange, causing ATM to shift
    // when selecting positions from different expiries.
    const liveSpot = indexPrices[underlying] || 0;
    let spotPrice = 90000;
    if (liveSpot > 0) {
      spotPrice = liveSpot;
    } else if (visiblePositions.length > 0 && visiblePositions[0]?.greeks?.spot) {
      spotPrice = parseFloat(visiblePositions[0].greeks.spot);
    } else if (futuresPositions.length > 0 && futuresPositions[0]?.mark_price) {
      spotPrice = parseFloat(futuresPositions[0].mark_price);
    }

    if (visiblePositions.length === 0 && futuresPositions.length === 0) return null;

    if (visiblePositions.length === 0) {
      return {
        positions: [],
        spotPrice,
        minDaysToExpiry: 0.001,
        riskFreeRate: RISK_FREE_RATE,
        nearestExpiry: new Date(Date.now() + 24 * 60 * 60 * 1000),
      };
    }

    const riskFreeRate = RISK_FREE_RATE;

    const parsed = visiblePositions.map((pos) => {
      const parts = pos.product_symbol.split('-');
      const optionType = parts[0] === 'C' ? 'call' : 'put';
      const strike = parseFloat(parts[2]);

      const expiryStr = parts[3];
      const day = parseInt(expiryStr.substring(0, 2));
      const month = parseInt(expiryStr.substring(2, 4)) - 1;
      const year = 2000 + parseInt(expiryStr.substring(4, 6));
      const expiryDate = new Date(Date.UTC(year, month, day, 12, 0, 0));

      const now = new Date();
      const msToExpiry = expiryDate - now;
      const daysToExpiry = Math.max(0, msToExpiry / (1000 * 60 * 60 * 24));
      const yearsToExpiry = daysToExpiry / 365.25;

      const size = parseFloat(pos.size || 0);
      const entryPrice = parseFloat(pos.entry_price || 0);
      const isClosed = pos.is_closed === true || size === 0;
      // realized_pnl: cumulative for closed rows (from ClosedPositionStore), partial-exit total for live rows (from exchange)
      const realizedPnl = parseFloat(pos.realized_pnl || 0);

      const bestBid = parseFloat(pos.best_bid || 0);
      const bestAsk = parseFloat(pos.best_ask || 0);
      const midPrice = bestBid > 0 && bestAsk > 0 ? (bestBid + bestAsk) / 2 : 0;
      let markPrice = midPrice > 0 ? midPrice : parseFloat(pos.mid_price || pos.mark_price || 0);
      if (!isClosed && markPrice === 0 && Math.abs(size) > 0 && entryPrice > 0) {
        // All price fields are missing — derive effective mark price from the exchange's
        // unrealized_pnl so the payoff curve at current spot matches the position row.
        // unrealized_pnl = (mark - entry) * size * multiplier  →  mark = entry + pnl/(size*mult)
        const exchPnl = parseFloat(pos.unrealized_pnl);
        if (isFinite(exchPnl) && exchPnl !== 0) {
          const mult = getContractMultiplier(pos.product_symbol);
          const derived = entryPrice + exchPnl / (size * mult);
          if (isFinite(derived) && derived > 0) markPrice = derived;
        }
      }
      if (markPrice === 0) markPrice = entryPrice;

      let iv = 0.8;
      const exchangeIV = pos.greeks?.iv ? parseFloat(pos.greeks.iv) : null;
      if (exchangeIV && exchangeIV > 0.05 && exchangeIV < 4.0) {
        iv = exchangeIV;
      } else if (markPrice > 0 && yearsToExpiry > 0.001 && !isClosed) {
        const calculatedIV = calculateImpliedVolatility(markPrice, spotPrice, strike, yearsToExpiry, riskFreeRate, optionType);
        if (calculatedIV > 0.05 && calculatedIV < 4.0) iv = calculatedIV;
      }

      return { symbol: pos.product_symbol, type: optionType, strike, expiryDate, daysToExpiry, yearsToExpiry, size, entryPrice, markPrice, iv, isClosed, realizedPnl };
    });

    const nonClosedPositions = parsed.filter(p => !p.isClosed);
    const positionsForExpiry = nonClosedPositions.length > 0 ? nonClosedPositions : parsed;

    const nearestExpiry = positionsForExpiry.length > 0
      ? positionsForExpiry.reduce((min, p) => (p.expiryDate < min ? p.expiryDate : min), positionsForExpiry[0].expiryDate)
      : new Date(Date.now() + 24 * 60 * 60 * 1000);

    const now = new Date();
    const actualDaysToExpiry = Math.max(0, (nearestExpiry - now) / (1000 * 60 * 60 * 24));
    const minDaysToExpiry = Math.max(0.001, actualDaysToExpiry);

    return { positions: parsed, spotPrice, minDaysToExpiry, riskFreeRate, nearestExpiry };
  }, [positions, selectedPositions, futuresPositions, indexPrices]);
};

/**
 * Compute full chart payoff data from parsed positions + user controls.
 *
 * @param {Object|null} parsedPositions - Output from useParsedPositions
 * @param {Object} opts - { priceRangePercent, targetDaysFromNow, targetPricePercent, showMultiDate, showProbDist, futuresPositions }
 * @returns {Object|null} Chart data object
 */
export const useChartData = (parsedPositions, opts) => {
  const { priceRangePercent, targetDaysFromNow, targetPricePercent, showMultiDate, showProbDist, futuresPositions } = opts;

  return useMemo(() => {
    if (!parsedPositions) return null;

    const { positions: parsedPos, spotPrice, minDaysToExpiry, riskFreeRate, nearestExpiry } = parsedPositions;

    const DEFAULT_RANGE = 6000;
    const MAX_ZOOM_RANGE = 30000;
    let optimalMinPrice = spotPrice - DEFAULT_RANGE;
    let optimalMaxPrice = spotPrice + DEFAULT_RANGE;

    if (parsedPos.length > 0) {
      const strikes = parsedPos.map(p => p.strike);
      const minStrike = Math.min(...strikes);
      const maxStrike = Math.max(...strikes);
      const strikeBuffer = 2000;
      if (minStrike - strikeBuffer < optimalMinPrice) optimalMinPrice = minStrike - strikeBuffer;
      if (maxStrike + strikeBuffer > optimalMaxPrice) optimalMaxPrice = maxStrike + strikeBuffer;
      const spotToMin = spotPrice - optimalMinPrice;
      const spotToMax = optimalMaxPrice - spotPrice;
      const maxOffset = Math.max(spotToMin, spotToMax);
      optimalMinPrice = spotPrice - maxOffset;
      optimalMaxPrice = spotPrice + maxOffset;
    }

    const isDefaultRange = priceRangePercent === 20;
    let minPrice, maxPrice;
    if (isDefaultRange) {
      minPrice = optimalMinPrice;
      maxPrice = optimalMaxPrice;
    } else {
      const userRange = Math.min(spotPrice * (priceRangePercent / 100), MAX_ZOOM_RANGE);
      minPrice = spotPrice - userRange;
      maxPrice = spotPrice + userRange;
    }

    const numPoints = 200;
    const priceStep = (maxPrice - minPrice) / numPoints;
    const now = new Date();
    const targetDate = new Date(now.getTime() + targetDaysFromNow * 24 * 60 * 60 * 1000);
    const targetPrice = spotPrice * (1 + targetPricePercent / 100);
    const daysToExpiryFromTarget = Math.max(0, (nearestExpiry - targetDate) / (1000 * 60 * 60 * 24));

    const calcProjectedPayoff = (price, daysFromNow) => {
      let payoff = 0;
      parsedPos.forEach((pos) => {
        // Always include realized PnL: cumulative for closed rows, partial-exit total for live rows
        payoff += pos.realizedPnl || 0;
        if (pos.isClosed) { return; }
        const absSize = Math.abs(pos.size);
        const isShort = pos.size < 0;
        const multiplier = getContractMultiplier(pos.symbol);

        const remainingDays = pos.daysToExpiry - daysFromNow;

        // At or past expiry: intrinsic value only (no time premium)
        if (remainingDays <= 0) {
          const intrinsic = pos.type === 'call'
            ? Math.max(0, price - pos.strike)
            : Math.max(0, pos.strike - price);
          if (isShort) payoff += (pos.entryPrice - intrinsic) * absSize * multiplier;
          else payoff += (intrinsic - pos.entryPrice) * absSize * multiplier;
          return;
        }

        // ── Market-Calibrated BSM Pricing (Industry Standard) ──────────────
        // Problem: for near-expiry options (< 24h), standard BSM with exchange
        // annualised IV diverges significantly from actual market prices because
        // the exchange IV is derived from a vol-surface model that accounts for
        // the discrete settlement, smile, and microstructure effects that BSM ignores.
        //
        // Solution (used by Sensibull, Opstra, TastyWorks):
        //   1. Anchor to the actual market price (bid/ask mid) at the current spot.
        //   2. Use the BSM time-value RATIO to distribute the market time premium
        //      across both the spatial (price) axis and the temporal (days) axis.
        //   This preserves model-consistency for shape while matching market reality
        //   at the current spot today.
        // ─────────────────────────────────────────────────────────────────────

        const nowYears = Math.max(1e-7, pos.daysToExpiry / 365.25);
        const remainingYears = Math.max(1e-7, remainingDays / 365.25);

        // Intrinsic values
        const intrinsicAtSpot = pos.type === 'call'
          ? Math.max(0, spotPrice - pos.strike)
          : Math.max(0, pos.strike - spotPrice);
        const intrinsicAtPrice = pos.type === 'call'
          ? Math.max(0, price - pos.strike)
          : Math.max(0, pos.strike - price);

        // BSM values at current spot for "now" and "future" time slices
        const bsAtSpotNow = blackScholesPrice(spotPrice, pos.strike, nowYears, riskFreeRate, pos.iv, pos.type);
        const bsAtSpotFuture = blackScholesPrice(spotPrice, pos.strike, remainingYears, riskFreeRate, pos.iv, pos.type);
        const bsTVAtSpotNow = Math.max(0, bsAtSpotNow - intrinsicAtSpot);
        const bsTVAtSpotFuture = Math.max(0, bsAtSpotFuture - intrinsicAtSpot);

        // Actual market time value at current spot (mark price above intrinsic)
        // Fallback to BS if markPrice is unavailable
        const markPx = (pos.markPrice > 0) ? pos.markPrice : bsAtSpotNow;
        const marketTV = Math.max(0, markPx - intrinsicAtSpot);

        // Step 1 — Project market time value forward to the target time slice
        //   ratio = BSforward / BSnow  (how much time value BSM says remains)
        let calibratedTVAtSpot;
        if (bsTVAtSpotNow > 1e-9) {
          calibratedTVAtSpot = marketTV * (bsTVAtSpotFuture / bsTVAtSpotNow);
        } else {
          // BSM cannot model time value (deep OTM / essentially expired):
          // fall back to sqrt-time decay (consistent with ATM-approximation)
          calibratedTVAtSpot = marketTV * Math.sqrt(remainingDays / pos.daysToExpiry);
        }

        // Step 2 — Distribute calibrated time value across the price axis
        //   using BSM time-value shape at the target time slice
        const bsAtPriceFuture = blackScholesPrice(price, pos.strike, remainingYears, riskFreeRate, pos.iv, pos.type);
        const bsTVAtPriceFuture = Math.max(0, bsAtPriceFuture - intrinsicAtPrice);

        let theo;
        if (bsTVAtSpotFuture > 1e-9) {
          theo = intrinsicAtPrice + calibratedTVAtSpot * (bsTVAtPriceFuture / bsTVAtSpotFuture);
        } else {
          // Essentially at expiry — intrinsic only
          theo = intrinsicAtPrice;
        }

        const safeTheo = isFinite(theo) ? Math.max(0, theo) : intrinsicAtPrice;
        if (isShort) payoff += (pos.entryPrice - safeTheo) * absSize * multiplier;
        else payoff += (safeTheo - pos.entryPrice) * absSize * multiplier;
      });
      futuresPositions.forEach((futPos) => {
        payoff += (price - futPos.entry_price) * futPos.size * getContractMultiplier(futPos.product_symbol);
      });
      return isFinite(payoff) ? payoff : 0;
    };

    const weightedIV = showProbDist && parsedPos.length > 0 ? calculateWeightedIV(parsedPos) : 0.8;
    const avgYearsToExpiry = minDaysToExpiry / 365.25;
    const distFn = showProbDist && parsedPos.length > 0 && avgYearsToExpiry > 1e-6
      ? createPriceDistribution(spotPrice, weightedIV, avgYearsToExpiry) : null;

    const midDays = minDaysToExpiry * 0.5;
    const data = [];

    for (let i = 0; i <= numPoints; i++) {
      const price = minPrice + i * priceStep;
      const point = { price: Math.round(price) };

      let expiryPayoff = 0;
      parsedPos.forEach((pos) => {
        // Always include realized PnL: cumulative for closed rows, partial-exit total for live rows
        expiryPayoff += pos.realizedPnl || 0;
        if (pos.isClosed) { return; }
        const intrinsic = pos.type === 'call' ? Math.max(0, price - pos.strike) : Math.max(0, pos.strike - price);
        const absSize = Math.abs(pos.size);
        const isShort = pos.size < 0;
        const multiplier = getContractMultiplier(pos.symbol);
        if (isShort) expiryPayoff += (pos.entryPrice - intrinsic) * absSize * multiplier;
        else expiryPayoff += (intrinsic - pos.entryPrice) * absSize * multiplier;
      });

      futuresPositions.forEach((futPos) => {
        expiryPayoff += (price - futPos.entry_price) * futPos.size * getContractMultiplier(futPos.product_symbol);
      });

      const safeExpiry = isFinite(expiryPayoff) ? expiryPayoff : 0;
      point.expiryProfit = safeExpiry >= 0 ? safeExpiry : 0;
      point.expiryLoss = safeExpiry < 0 ? safeExpiry : 0;
      point.expiry = safeExpiry;
      point.expiryGreen = safeExpiry >= 0 ? safeExpiry : null;
      point.expiryRed = safeExpiry <= 0 ? safeExpiry : null;

      point.target = calcProjectedPayoff(price, targetDaysFromNow);

      if (showMultiDate) {
        if (targetDaysFromNow > 0.02) point.today = calcProjectedPayoff(price, 0);
        point.mid = calcProjectedPayoff(price, midDays);
      }

      if (distFn) point.probRaw = distFn(price);
      data.push(point);
    }

    // C5: Zero-crossing interpolation
    const interpolated = [];
    for (let i = 0; i < data.length; i++) {
      if (i > 0) {
        const prev = data[i - 1];
        const curr = data[i];
        if ((prev.expiry > 0 && curr.expiry < 0) || (prev.expiry < 0 && curr.expiry > 0)) {
          const frac = Math.abs(prev.expiry) / (Math.abs(prev.expiry) + Math.abs(curr.expiry));
          const zeroPrice = prev.price + frac * (curr.price - prev.price);
          const zeroPoint = { ...curr, price: Math.round(zeroPrice), expiry: 0, expiryProfit: 0, expiryLoss: 0, expiryGreen: 0, expiryRed: 0 };
          if (prev.target !== undefined && curr.target !== undefined) {
            zeroPoint.target = prev.target + frac * (curr.target - prev.target);
          }
          interpolated.push(zeroPoint);
        }
      }
      interpolated.push(data[i]);
    }
    data.length = 0;
    interpolated.forEach((d) => data.push(d));

    if (distFn) {
      let maxProb = 0;
      data.forEach((d) => { if (d.probRaw > maxProb) maxProb = d.probRaw; });
      const probScale = maxProb > 0 ? 100 / maxProb : 0;
      data.forEach((d) => { d.probability = (d.probRaw || 0) * probScale; });
    }

    let maxProfit = -Infinity, maxLoss = Infinity;
    let maxTargetProfit = -Infinity, maxTargetLoss = Infinity;
    const breakevens = [];

    data.forEach((point, idx) => {
      if (point.expiry > maxProfit) maxProfit = point.expiry;
      if (point.expiry < maxLoss) maxLoss = point.expiry;
      if (point.target > maxTargetProfit) maxTargetProfit = point.target;
      if (point.target < maxTargetLoss) maxTargetLoss = point.target;
      if (point.today !== undefined) {
        if (point.today > maxTargetProfit) maxTargetProfit = point.today;
        if (point.today < maxTargetLoss) maxTargetLoss = point.today;
      }
      if (point.mid !== undefined) {
        if (point.mid > maxTargetProfit) maxTargetProfit = point.mid;
        if (point.mid < maxTargetLoss) maxTargetLoss = point.mid;
      }
      if (idx > 0) {
        const prev = data[idx - 1].expiry;
        const curr = point.expiry;
        if ((prev < 0 && curr >= 0) || (prev > 0 && curr <= 0)) breakevens.push(point.price);
      }
    });

    // ── Y-axis domain: keep zero at the visual centre ──────────────────────
    // The key insight: when maxProfit is small (e.g. $30) but maxLoss is large
    // (e.g. -$1256), the raw loss value will dominate the Y scale and squeeze the
    // profitable region into a tiny sliver at the top. Instead we build a
    // *symmetric* range around zero so the profit zone always gets equal screen space.
    //
    // Strategy:
    //   1. Add a small padding above the max profit.
    //   2. Mirror that same extent below zero (i.e. yMin = -yMax).
    //   3. If the actual max loss is deeper than that mirrored extent, extend the
    //      bottom – but never let the loss region exceed 3× the profit region, so
    //      the profit zone still gets a meaningful slice of the chart.
    const overallMax = Math.max(maxProfit, maxTargetProfit, 0);
    const overallMin = Math.min(maxLoss, maxTargetLoss, 0); // negative or 0

    // Padding above the peak profit (at least $2 so a flat line is still visible)
    const profitPaddingPercent = overallMax < 50 ? 0.4 : overallMax < 200 ? 0.25 : 0.15;
    const profitPadding = Math.max(Math.abs(overallMax) * profitPaddingPercent, 2);
    const rawYMax = overallMax + profitPadding;

    // Symmetric lower bound (zero at centre)
    const symmetricYMin = -rawYMax;

    // Actual lower bound — extend only if loss is deeper, but cap at 3× profit range
    // so extreme losses don't dominate the scale and crush the profit zone
    const cappedLossExtent = Math.max(Math.abs(overallMin), rawYMax);
    const maxAllowedExtent = rawYMax * 3; // never let loss zone take >75% of the chart
    const actualExtent = Math.min(cappedLossExtent, maxAllowedExtent);
    const rawYMin = -actualExtent;

    // Final bounds — always at least ±2 so a flat line at zero is still visible
    const yMin = Math.min(rawYMin, symmetricYMin, -2);
    const yMax = Math.max(rawYMax, 2);

    const targetPricePoint = data.find((d) => Math.abs(d.price - targetPrice) < priceStep * 1.5);
    const projectedProfit = targetPricePoint?.target ?? 0;

    const totalPremiumCollected = parsedPos.reduce((sum, p) => {
      return sum + p.entryPrice * Math.abs(p.size) * getContractMultiplier(p.symbol);
    }, 0);
    const profitPct = totalPremiumCollected > 0 ? ((projectedProfit / totalPremiumCollected) * 100).toFixed(2) : 0;

    const popWeightedIV = parsedPos.length > 0 ? calculateWeightedIV(parsedPos) : 0.8;
    const avgYearsToExpiryPoP = minDaysToExpiry / 365.25;
    const probabilityOfProfit = calculateProbabilityOfProfit(spotPrice, popWeightedIV, avgYearsToExpiryPoP, data);

    return {
      data, spotPrice, targetPrice,
      maxProfit: isFinite(maxProfit) ? maxProfit : 0,
      maxLoss: isFinite(maxLoss) ? maxLoss : 0,
      breakevens, projectedProfit, profitPct, targetDate, daysToExpiryFromTarget,
      minDaysToExpiry, nearestExpiry, minPrice, maxPrice,
      yMin: isFinite(yMin) ? yMin : -10,
      yMax: isFinite(yMax) ? yMax : 10,
      probabilityOfProfit,
      parsedPositions: parsedPos,
    };
  }, [parsedPositions, priceRangePercent, targetDaysFromNow, targetPricePercent, futuresPositions, showMultiDate, showProbDist]);
};
