/**
 * MMM Calculations — Money Mind & Method
 *
 * Client-side P&L preview math for quick UI estimates.
 * The actual calculations happen server-side — these are for display only.
 *
 * Created: February 15, 2026
 */

/**
 * Estimate P&L for a single position.
 * For sold options: P&L = (entry_premium - current_premium) × lots
 */
export function estimatePositionPnl(entryPremium, currentPremium, lots) {
  return (entryPremium - currentPremium) * lots;
}

/**
 * Estimate total unrealized P&L across all positions.
 */
export function estimateTotalUnrealizedPnl(session, ceNow, peNow) {
  if (!session) return 0;

  let total = 0;

  for (const sideKey of ['ce', 'pe']) {
    const side = session[sideKey];
    if (!side) continue;

    const current = sideKey === 'ce' ? ceNow : peNow;

    // Original
    if (side.original_lots > 0) {
      total += (side.original_premium - current) * side.original_lots;
    }

    // Adjustments
    (side.adjustment_fills || []).forEach((fill) => {
      total += (fill.premium - current) * fill.lots;
    });
  }

  return total;
}

/**
 * Calculate lots needed to cover a loss.
 */
export function calculateLots(loss, hedgePremium, bufferPct = 0.05) {
  if (hedgePremium <= 0) return 0;
  return Math.ceil((loss / hedgePremium) * (1 + bufferPct));
}

/**
 * Calculate excess above trigger.
 */
export function calculateExcess(currentPremium, triggerLevel) {
  return Math.max(0, currentPremium - triggerLevel);
}

/**
 * Check if trigger condition is met.
 */
export function isTriggered(currentPremium, triggerLevel, minTriggerMove = 3) {
  return (currentPremium - triggerLevel) > minTriggerMove;
}

/**
 * Estimate premium collected from selling.
 */
export function estimatePremiumCollected(lots, fillPrice) {
  return lots * fillPrice;
}
