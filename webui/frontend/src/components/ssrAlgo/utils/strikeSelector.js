/**
 * Strike Selector Utility
 * 
 * Client-side utilities for strike selection and validation.
 * Mirrors backend logic for preview and validation purposes.
 * 
 * Per Implementation Plan: Section 2.3 - utils/strikeSelector.js
 * Created: February 3, 2026
 */

/**
 * Default strike configuration
 */
export const DEFAULT_STRIKE_CONFIG = {
  otm_buy_percent_min: 45,
  otm_buy_percent_max: 49,
  far_otm_percent_min: 20,
  far_otm_percent_max: 30,
};

/**
 * Validate strike configuration values
 * @param {Object} config - Strike configuration
 * @returns {Object} { valid: boolean, errors: string[] }
 */
export const validateStrikeConfig = (config) => {
  const errors = [];

  const {
    otm_buy_percent_min = 45,
    otm_buy_percent_max = 49,
    far_otm_percent_min = 20,
    far_otm_percent_max = 30,
  } = config || {};

  // Validate OTM buy range
  if (otm_buy_percent_min < 30 || otm_buy_percent_min > 60) {
    errors.push('OTM buy minimum must be between 30% and 60%');
  }
  if (otm_buy_percent_max < 35 || otm_buy_percent_max > 65) {
    errors.push('OTM buy maximum must be between 35% and 65%');
  }
  if (otm_buy_percent_min >= otm_buy_percent_max) {
    errors.push('OTM buy minimum must be less than maximum');
  }

  // Validate Far OTM sell range
  if (far_otm_percent_min < 10 || far_otm_percent_min > 40) {
    errors.push('Far OTM sell minimum must be between 10% and 40%');
  }
  if (far_otm_percent_max < 15 || far_otm_percent_max > 45) {
    errors.push('Far OTM sell maximum must be between 15% and 45%');
  }
  if (far_otm_percent_min >= far_otm_percent_max) {
    errors.push('Far OTM sell minimum must be less than maximum');
  }

  // Ensure Far OTM is further out than OTM
  if (far_otm_percent_max >= otm_buy_percent_min) {
    errors.push('Far OTM range should be below OTM buy range');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
};

/**
 * Calculate premium ranges based on ATM premium
 * @param {number} atmPremium - ATM option premium
 * @param {Object} config - Strike configuration
 * @returns {Object} Premium ranges for each leg type
 */
export const calculatePremiumRanges = (atmPremium, config = DEFAULT_STRIKE_CONFIG) => {
  if (!atmPremium || atmPremium <= 0) {
    return null;
  }

  const {
    otm_buy_percent_min,
    otm_buy_percent_max,
    far_otm_percent_min,
    far_otm_percent_max,
  } = { ...DEFAULT_STRIKE_CONFIG, ...config };

  return {
    otm_buy: {
      min: Math.round(atmPremium * (otm_buy_percent_min / 100)),
      max: Math.round(atmPremium * (otm_buy_percent_max / 100)),
      percentMin: otm_buy_percent_min,
      percentMax: otm_buy_percent_max,
    },
    far_otm_sell: {
      min: Math.round(atmPremium * (far_otm_percent_min / 100)),
      max: Math.round(atmPremium * (far_otm_percent_max / 100)),
      percentMin: far_otm_percent_min,
      percentMax: far_otm_percent_max,
    },
  };
};

/**
 * Check if a premium falls within a target range
 * @param {number} premium - Option premium to check
 * @param {number} min - Minimum target
 * @param {number} max - Maximum target
 * @param {number} tolerance - Tolerance percentage (default 5%)
 * @returns {Object} Match result
 */
export const checkPremiumMatch = (premium, min, max, tolerance = 5) => {
  if (!premium || !min || !max) {
    return { matches: false, reason: 'Missing values' };
  }

  const toleranceAmount = max * (tolerance / 100);
  const adjustedMin = min - toleranceAmount;
  const adjustedMax = max + toleranceAmount;

  if (premium >= min && premium <= max) {
    return {
      matches: true,
      exact: true,
      reason: 'Premium within target range',
    };
  }

  if (premium >= adjustedMin && premium <= adjustedMax) {
    return {
      matches: true,
      exact: false,
      reason: 'Premium within tolerance',
      deviation: premium < min ? min - premium : premium - max,
    };
  }

  return {
    matches: false,
    reason: premium < min ? 'Premium too low' : 'Premium too high',
    deviation: premium < min ? min - premium : premium - max,
  };
};

/**
 * Format strike preview data for display
 * @param {Object} previewData - Strike preview from API
 * @returns {Array} Formatted rows for display
 */
export const formatStrikePreview = (previewData) => {
  if (!previewData) return [];

  const rows = [];

  // ATM strikes
  if (previewData.atm) {
    rows.push({
      leg: 'ATM CE Sell',
      strike: previewData.atm.strike,
      premium: previewData.atm.ce_premium,
      targetRange: '-',
      matches: true,
      side: 'SELL',
      qty: 1,
    });
    rows.push({
      leg: 'ATM PE Sell',
      strike: previewData.atm.strike,
      premium: previewData.atm.pe_premium,
      targetRange: '-',
      matches: true,
      side: 'SELL',
      qty: 1,
    });
  }

  // OTM Buy strikes
  if (previewData.otm_ce_buy) {
    rows.push({
      leg: 'OTM CE Buy',
      strike: previewData.otm_ce_buy.strike,
      premium: previewData.otm_ce_buy.premium,
      targetRange: previewData.otm_ce_buy.target_range,
      matches: previewData.otm_ce_buy.matches !== false,
      side: 'BUY',
      qty: 2,
    });
  }

  if (previewData.otm_pe_buy) {
    rows.push({
      leg: 'OTM PE Buy',
      strike: previewData.otm_pe_buy.strike,
      premium: previewData.otm_pe_buy.premium,
      targetRange: previewData.otm_pe_buy.target_range,
      matches: previewData.otm_pe_buy.matches !== false,
      side: 'BUY',
      qty: 2,
    });
  }

  // Far OTM Sell strikes
  if (previewData.far_otm_ce) {
    rows.push({
      leg: 'Far OTM CE Sell',
      strike: previewData.far_otm_ce.strike,
      premium: previewData.far_otm_ce.premium,
      targetRange: previewData.far_otm_ce.target_range,
      matches: previewData.far_otm_ce.matches !== false,
      side: 'SELL',
      qty: 1,
    });
  }

  if (previewData.far_otm_pe) {
    rows.push({
      leg: 'Far OTM PE Sell',
      strike: previewData.far_otm_pe.strike,
      premium: previewData.far_otm_pe.premium,
      targetRange: previewData.far_otm_pe.target_range,
      matches: previewData.far_otm_pe.matches !== false,
      side: 'SELL',
      qty: 1,
    });
  }

  return rows;
};

/**
 * Calculate total position metrics from strike preview
 * @param {Object} previewData - Strike preview from API
 * @returns {Object} Position metrics
 */
export const calculatePositionMetrics = (previewData) => {
  if (!previewData) {
    return {
      totalLegs: 0,
      totalLots: 0,
      netPremium: 0,
      maxProfit: 0,
      maxLoss: 0,
    };
  }

  const atmCePremium = previewData.atm?.ce_premium || 0;
  const atmPePremium = previewData.atm?.pe_premium || 0;
  const otmCePremium = previewData.otm_ce_buy?.premium || 0;
  const otmPePremium = previewData.otm_pe_buy?.premium || 0;
  const farOtmCePremium = previewData.far_otm_ce?.premium || 0;
  const farOtmPePremium = previewData.far_otm_pe?.premium || 0;

  // Net premium = (Sell premiums) - (Buy premiums)
  const sellPremiums = atmCePremium + atmPePremium + farOtmCePremium + farOtmPePremium;
  const buyPremiums = (otmCePremium * 2) + (otmPePremium * 2); // 2 lots each
  const netPremium = sellPremiums - buyPremiums;

  return {
    totalLegs: 6,
    totalLots: 8, // 1 + 1 + 2 + 2 + 1 + 1
    netPremium: Math.round(netPremium * 100) / 100,
    sellPremiums: Math.round(sellPremiums * 100) / 100,
    buyPremiums: Math.round(buyPremiums * 100) / 100,
    atmStrike: previewData.atm?.strike,
    otmCeStrike: previewData.otm_ce_buy?.strike,
    otmPeStrike: previewData.otm_pe_buy?.strike,
    farOtmCeStrike: previewData.far_otm_ce?.strike,
    farOtmPeStrike: previewData.far_otm_pe?.strike,
  };
};

/**
 * Suggest adjustments if strike selection fails
 * @param {Object} error - Error from strike selection
 * @param {Object} currentConfig - Current strike configuration
 * @returns {Object} Suggested configuration adjustments
 */
export const suggestConfigAdjustments = (error, currentConfig) => {
  const suggestions = [];

  if (error?.message?.includes('OTM CE') || error?.missing?.includes('otm_ce')) {
    suggestions.push({
      field: 'otm_buy_percent',
      action: 'widen',
      suggestion: 'Try widening OTM buy range (e.g., 40-55%)',
      newConfig: {
        otm_buy_percent_min: Math.max(30, currentConfig.otm_buy_percent_min - 5),
        otm_buy_percent_max: Math.min(60, currentConfig.otm_buy_percent_max + 5),
      },
    });
  }

  if (error?.message?.includes('OTM PE') || error?.missing?.includes('otm_pe')) {
    suggestions.push({
      field: 'otm_buy_percent',
      action: 'widen',
      suggestion: 'Try widening OTM buy range (e.g., 40-55%)',
      newConfig: {
        otm_buy_percent_min: Math.max(30, currentConfig.otm_buy_percent_min - 5),
        otm_buy_percent_max: Math.min(60, currentConfig.otm_buy_percent_max + 5),
      },
    });
  }

  if (error?.message?.includes('Far OTM') || error?.missing?.includes('far_otm')) {
    suggestions.push({
      field: 'far_otm_percent',
      action: 'widen',
      suggestion: 'Try widening Far OTM range (e.g., 15-35%)',
      newConfig: {
        far_otm_percent_min: Math.max(10, currentConfig.far_otm_percent_min - 5),
        far_otm_percent_max: Math.min(40, currentConfig.far_otm_percent_max + 5),
      },
    });
  }

  return {
    hasSuggestions: suggestions.length > 0,
    suggestions,
    recommendedConfig: suggestions.reduce((config, s) => ({
      ...config,
      ...s.newConfig,
    }), { ...currentConfig }),
  };
};

export default {
  DEFAULT_STRIKE_CONFIG,
  validateStrikeConfig,
  calculatePremiumRanges,
  checkPremiumMatch,
  formatStrikePreview,
  calculatePositionMetrics,
  suggestConfigAdjustments,
};
