/**
 * MMM Formatters — Money Mind & Method
 *
 * Number, time, and strike formatting utilities for the MMM dashboard.
 *
 * Created: February 15, 2026
 */

/**
 * Format a dollar amount with sign.
 * @param {number} amount
 * @param {number} decimals
 * @returns {string}
 */
export function formatPnl(amount, decimals = 2) {
  if (amount == null || isNaN(amount)) return '--';
  const prefix = amount >= 0 ? '+$' : '-$';
  return `${prefix}${Math.abs(amount).toFixed(decimals)}`;
}

/**
 * Format a premium value.
 * @param {number} premium
 * @returns {string}
 */
export function formatPremium(premium) {
  if (premium == null) return '--';
  return Number(premium).toFixed(2);
}

/**
 * Format a strike price with commas.
 * @param {number} strike
 * @returns {string}
 */
export function formatStrike(strike) {
  if (!strike) return '--';
  return Number(strike).toLocaleString();
}

/**
 * Format an ISO timestamp to a human-readable time.
 * @param {string} iso
 * @returns {string}
 */
export function formatTime(iso) {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return '--';
  }
}

/**
 * Format an ISO timestamp to a human-readable date + time.
 * @param {string} iso
 * @returns {string}
 */
export function formatDateTime(iso) {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    return (
      d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
      ' ' +
      d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    );
  } catch {
    return '--';
  }
}

/**
 * Format elapsed time from a start timestamp.
 * @param {string} startIso
 * @returns {string}
 */
export function formatElapsed(startIso) {
  if (!startIso) return '--';
  const start = new Date(startIso);
  const now = new Date();
  const diff = Math.max(0, Math.floor((now - start) / 1000));
  const hrs = Math.floor(diff / 3600);
  const mins = Math.floor((diff % 3600) / 60);
  const secs = diff % 60;
  if (hrs > 0) return `${hrs}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

/**
 * Format minutes to a countdown string.
 * @param {number} minutes
 * @returns {string}
 */
export function formatMinutes(minutes) {
  if (minutes == null) return '--';
  if (minutes < 1) return '< 1m';
  if (minutes < 60) return `${Math.floor(minutes)}m`;
  const hrs = Math.floor(minutes / 60);
  const mins = Math.floor(minutes % 60);
  return `${hrs}h ${mins}m`;
}

/**
 * Get color for a P&L value.
 * @param {number} pnl
 * @returns {string}
 */
export function pnlColor(pnl) {
  if (pnl > 0) return '#4caf50';
  if (pnl < 0) return '#f44336';
  return '#9e9e9e';
}

/**
 * Format lots with suffix.
 * @param {number} lots
 * @returns {string}
 */
export function formatLots(lots) {
  if (lots == null) return '--';
  return `${lots}L`;
}
