/**
 * MMM Service — Money Mind & Method
 *
 * API service for MMM session management.
 * All REST calls to /api/mmm endpoints.
 *
 * Created: February 15, 2026
 */

import api from '../../utils/apiShim';

const BASE_URL = '/api/mmm';

/**
 * MMM API Service
 */
const mmmService = {
  // =========================================================================
  // Session CRUD
  // =========================================================================

  /**
   * List all sessions
   * @param {boolean} activeOnly - Only return active sessions
   * @param {boolean} summary - Return compact summaries
   */
  async getSessions(activeOnly = false, summary = false) {
    const { data } = await api.get(`${BASE_URL}/sessions`, {
      params: { active_only: activeOnly, summary },
    });
    return data;
  },

  /**
   * Get a specific session
   * @param {string} sessionId
   * @param {boolean} summary - Return compact summary
   */
  async getSession(sessionId, summary = false) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}`, {
      params: { summary },
    });
    return data;
  },

  /**
   * Create a new session
   * @param {Object} config
   * @param {string} config.mode - 'fresh' or 'import'
   * @param {Object} config.params - Algorithm parameters
   * @param {Object} [config.import_data] - For import mode: { ce: {strike, premium, lots}, pe: {strike, premium, lots} }
   */
  async createSession(config) {
    const { data } = await api.post(`${BASE_URL}/session/create`, config);
    return data;
  },

  /**
   * Delete a session (only IDLE or STOPPED)
   * @param {string} sessionId
   */
  async deleteSession(sessionId) {
    const { data } = await api.delete(`${BASE_URL}/session/${sessionId}`);
    return data;
  },

  // =========================================================================
  // Session Control
  // =========================================================================

  /**
   * Start a session
   * @param {string} sessionId
   */
  async startSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/start`);
    return data;
  },

  /**
   * Pause a running session
   * @param {string} sessionId
   */
  async pauseSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/pause`);
    return data;
  },

  /**
   * Resume a paused session
   * @param {string} sessionId
   */
  async resumeSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/resume`);
    return data;
  },

  /**
   * Stop a session
   * @param {string} sessionId
   * @param {string} [reason]
   */
  async stopSession(sessionId, reason = '') {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/stop`, { reason });
    return data;
  },

  // =========================================================================
  // Both-Sides-Up Decision (Section 8)
  // =========================================================================

  /**
   * Submit user's decision for both-sides-up scenario
   * @param {string} sessionId
   * @param {string} decision - 'adjust_ce' | 'adjust_pe' | 'skip'
   * @param {Object} [params] - Additional params for ADD/REDUCE actions
   */
  async submitBothSidesDecision(sessionId, decision, params = {}) {
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/both_sides_decision`,
      { decision, ...params }
    );
    return data;
  },

  // =========================================================================
  // Phase 3+: Monitor Control
  // =========================================================================

  /**
   * Get monitor status for a session
   * @param {string} sessionId
   */
  async getMonitorStatus(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/monitor`);
    return data;
  },

  /**
   * Get all active monitors
   */
  async getAllMonitors() {
    const { data } = await api.get(`${BASE_URL}/monitors`);
    return data;
  },

  /**
   * Force an immediate heartbeat for a running session.
   * Skips the wait timer; heartbeat logic is unchanged.
   * @param {string} sessionId
   */
  async forceHeartbeat(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/force-heartbeat`);
    return data;
  },

  // =========================================================================
  // Manual Position Reduction
  // =========================================================================

  /**
   * Manually buy back lots while the algo continues running.
   * Does NOT count as an adjustment. Trigger snapshots reset after fill.
   *
   * @param {string} sessionId
   * @param {'ce'|'pe'|'both'} side     - Which side(s) to reduce
   * @param {number}           lots     - Number of lots to buy back per side
   * @param {number|null}      strike   - Specific strike (null = LIFO auto)
   */
  async reducePosition(sessionId, side, lots, strike = null) {
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/reduce-position`,
      { side, lots, strike }
    );
    return data;
  },

  // =========================================================================
  // Phase 3+: Live Data Endpoints
  // =========================================================================

  /**
   * Get current positions for a session (active, adjustment, frozen)
   * @param {string} sessionId
   */
  async getPositions(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/positions`);
    return data;
  },

  /**
   * Get current trigger data for a session
   * @param {string} sessionId
   */
  async getTriggerData(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/triggers`);
    return data;
  },

  /**
   * Get P&L timeline data
   * @param {string} sessionId
   * @param {number} [limit=100] - Max data points
   */
  async getPnLTimeline(sessionId, limit = 100) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/pnl-timeline`, {
      params: { limit },
    });
    return data;
  },

  /**
   * Get safety status for a session
   * @param {string} sessionId
   */
  async getSafetyStatus(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/safety`);
    return data;
  },

  /**
   * Get session analytics (exposure tracking, milestones, etc.)
   * @param {string} sessionId
   */
  async getSessionAnalytics(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/analytics`);
    return data;
  },

  /**
   * Get aggregated institutional-grade analytics across ALL sessions
   * Provides capital requirements, risk analytics, profitability, and strategy performance
   */
  async getAggregatedAnalytics() {
    const { data } = await api.get(`${BASE_URL}/analytics/aggregated`);
    return data;
  },

  // =========================================================================
  // Parameters (Section 19)
  // =========================================================================

  /**
   * Get parameter metadata and defaults
   */
  async getParamsInfo() {
    const { data } = await api.get(`${BASE_URL}/params/info`);
    return data;
  },

  /**
   * Get current parameters for a session
   * @param {string} sessionId
   */
  async getSessionParams(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/params`);
    return data;
  },

  /**
   * Update parameters (hot-reload if running)
   * @param {string} sessionId
   * @param {Object} params - { param_name: value, ... }
   */
  async updateSessionParams(sessionId, params) {
    const { data } = await api.patch(`${BASE_URL}/session/${sessionId}/params`, params);
    return data;
  },

  // =========================================================================
  // History & Diagnostics
  // =========================================================================

  /**
   * Get adjustment history and P&L timeline
   * @param {string} sessionId
   * @param {number} [limit=200]
   */
  async getSessionHistory(sessionId, limit = 200) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/history`, {
      params: { limit },
    });
    return data;
  },

  /**
   * Get full CE/PE state for diagnostics
   * @param {string} sessionId
   */
  async getSessionState(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/state`);
    return data;
  },

  // =========================================================================
  // Phase 2: Initialization — Strike Selection & Entry
  // =========================================================================

  /**
   * Get available BTC option expiry dates
   * @param {string} [underlying='BTC']
   */
  async getExpiries(underlying = 'BTC') {
    const { data } = await api.get(`${BASE_URL}/expiries`, {
      params: { underlying },
    });
    return data;
  },

  /**
   * Get current BTC spot price
   * @param {string} [underlying='BTC']
   */
  async getSpotPrice(underlying = 'BTC') {
    const { data } = await api.get(`${BASE_URL}/spot-price`, {
      params: { underlying },
    });
    return data;
  },

  /**
   * Preview which strikes would be selected for given desired premiums
   * Section 3, Mode A: Auto-find strikes
   *
   * @param {Object} params
   * @param {number} params.desired_ce_premium - Target CE premium per lot
   * @param {number} params.desired_pe_premium - Target PE premium per lot
   * @param {string} params.expiry - Expiry date (any format)
   * @param {string} [params.underlying='BTC']
   */
  async previewStrikes({ desired_ce_premium, desired_pe_premium, expiry, underlying = 'BTC' }) {
    const { data } = await api.post(`${BASE_URL}/preview-strikes`, {
      desired_ce_premium,
      desired_pe_premium,
      expiry,
      underlying,
    });
    return data;
  },

  /**
   * Check bid-side liquidity for an option symbol
   * @param {string} symbol - Option symbol (e.g. 'C-BTC-100000-150226')
   * @param {number} lots - Number of lots to sell
   */
  async checkLiquidity(symbol, lots) {
    const { data } = await api.post(`${BASE_URL}/check-liquidity`, { symbol, lots });
    return data;
  },

  /**
   * Initialize session with fresh entry (Mode A — confirmed strikes)
   * @param {string} sessionId
   * @param {Object} entry
   * @param {number} entry.ce_strike
   * @param {number} entry.ce_premium
   * @param {string} entry.ce_symbol
   * @param {number} entry.pe_strike
   * @param {number} entry.pe_premium
   * @param {string} entry.pe_symbol
   * @param {number} entry.lots
   * @param {string} entry.expiry
   */
  async initSessionFresh(sessionId, entry) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/init-fresh`, entry);
    return data;
  },

  /**
   * Initialize session by importing existing position (Mode B)
   * @param {string} sessionId
   * @param {Object} entry
   * @param {number} entry.ce_strike
   * @param {number} entry.ce_fill_price
   * @param {string} entry.ce_symbol
   * @param {number} entry.pe_strike
   * @param {number} entry.pe_fill_price
   * @param {string} entry.pe_symbol
   * @param {number} entry.lots
   * @param {string} entry.expiry
   * @param {number} [entry.current_ce_price]
   * @param {number} [entry.current_pe_price]
   */
  async initSessionImport(sessionId, entry) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/init-import`, entry);
    return data;
  },

  // =========================================================================
  // Phase 2 Enhanced: Chain Data, Validation & Smart Execution
  // =========================================================================

  /**
   * Get full options chain for manual strike browsing
   * @param {string} expiry - Expiry date (any format)
   * @param {string} [underlying='BTC']
   */
  async getChainData(expiry, underlying = 'BTC') {
    const { data } = await api.get(`${BASE_URL}/chain-data`, {
      params: { expiry, underlying },
    });
    return data;
  },

  /**
   * Validate a manually selected CE+PE pair
   * @param {Object} params
   * @param {string} params.ce_symbol
   * @param {string} params.pe_symbol
   * @param {number} params.lots
   * @param {string} params.expiry
   * @param {string} [params.underlying='BTC']
   */
  async validateSelection({ ce_symbol, pe_symbol, lots, expiry, underlying = 'BTC' }) {
    const { data } = await api.post(`${BASE_URL}/validate-selection`, {
      ce_symbol, pe_symbol, lots, expiry, underlying,
    });
    return data;
  },

  /**
   * Execute smart entry — place CE+PE sell orders at mid-price
   * Uses 60s fill wait + auto-reprice cycle
   * @param {string} sessionId
   * @param {string} [mode='auto'] - 'auto' or 'manual'
   */
  async executeEntry(sessionId, mode = 'auto') {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/execute-entry`, { mode });
    return data;
  },

  // =========================================================================
  // Health
  // =========================================================================

  /**
   * Health check
   */
  async healthCheck() {
    const { data } = await api.get(`${BASE_URL}/health`);
    return data;
  },

  // =========================================================================
  // Background Activities
  // =========================================================================

  /**
   * Get recent background activity log
   * @param {number} [limit=50] - Max entries
   * @param {string} [sessionId] - Filter by session
   */
  async getActivities(limit = 50, sessionId = null) {
    const params = { limit };
    if (sessionId) params.session_id = sessionId;
    const { data } = await api.get(`${BASE_URL}/activities`, { params });
    return data;
  },

  // =========================================================================
  // Algo Walkthrough
  // =========================================================================

  /**
   * Get the algo-calculation walkthrough log for a session
   * @param {string} sessionId
   */
  async getWalkthrough(sessionId) {
    const { data } = await api.get(
      `${BASE_URL}/session/${sessionId}/walkthrough`
    );
    return data;
  },

  // =========================================================================
  // Greeks, IV & Position Analytics
  // =========================================================================

  /**
   * Get live Greeks, IV, and position data for all positions in a session.
   * Fetches from Delta Exchange tickers API.
   * @param {string} sessionId
   */
  async getGreeksIV(sessionId) {
    const { data } = await api.get(
      `${BASE_URL}/session/${sessionId}/greeks-iv`
    );
    return data;
  },
};

export default mmmService;
