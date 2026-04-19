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
    try {
      const { data } = await api.delete(`${BASE_URL}/session/${sessionId}`);
      return data;
    } catch (err) {
      // 404 = session already deleted. Treat as success so the circuit breaker
      // is never tripped by stale session IDs in the frontend list.
      if (err?.status === 404) {
        return { success: true, message: `Session ${sessionId} not found (already deleted)` };
      }
      throw err;
    }
  },

  // =========================================================================
  // Session Control
  // =========================================================================

  /**
   * Start a session
   * @param {string} sessionId
   * @param {boolean} forceStart - Pass true to override invariant/cap violations (recovery use only)
   */
  async startSession(sessionId, forceStart = false) {
    const body = forceStart ? { force_start: true } : undefined;
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/start`, body);
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

  /**
   * Global graceful exit: close all positions then stop the session.
   * Returns HTTP 202 with { success, session_id, initiated_at, positions_to_close }
   * @param {string} sessionId
   * @param {string} [reason]
   */
  async exitAllSession(sessionId, reason = 'user_requested') {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/exit_all`, { reason });
    return data;
  },

  /**
   * Emergency Kill Switch — square off ALL positions for this session immediately.
   * Marks session _kill_switch_triggered=true, sets EXITING, forces heartbeat.
   * Idempotent: safe to call multiple times.
   * @param {string} sessionId
   * @param {string} [reason]
   */
  async killSwitch(sessionId, reason = 'kill_switch') {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/kill_switch`, { reason });
    return data;
  },

  /**
   * Resolve a PARTIAL_ENTRY state by confirming both fill prices manually.
   * Use when one leg already filled on the exchange but the algo marked it as failed.
   * @param {string} sessionId
   * @param {number} ceFillPrice - Actual CE fill price
   * @param {number} peFillPrice - Actual PE fill price
   */
  async resolvePartialEntry(sessionId, ceFillPrice, peFillPrice) {
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/resolve-partial-entry`,
      { ce_fill_price: ceFillPrice, pe_fill_price: peFillPrice }
    );
    return data;
  },

  /**
   * Retry only the failed leg of a PARTIAL_ENTRY.
   * The algo auto-detects which side failed and retries it in the background.
   * @param {string} sessionId
   */
  async retryPartialLeg(sessionId) {
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/retry-partial-leg`
    );
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
   * Force an immediate heartbeat for a running session.
   * Skips the wait timer; heartbeat logic is unchanged.
   * @param {string} sessionId
   */
  async forceHeartbeat(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/force-heartbeat`);
    return data;
  },

  /**
   * Get heartbeat health telemetry: latency percentiles, miss rate,
   * health grade (A-F), circuit breaker state, watchdog status.
   * @param {string} sessionId
   */
  async getBeatHealth(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/beat-health`);
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

  /**
   * Operator-inject: Open a new short position and register it with the algo.
   * The algo will manage the injected position going forward.
   * @param {string} sessionId
   * @param {string} side     - 'ce' or 'pe'
   * @param {number} lots     - number of lots to sell
   * @param {number} strike   - strike price
   */
  async injectPosition(sessionId, side, lots, strike, adopt = false, fillPrice = null) {
    const body = { side, lots, strike };
    if (adopt) { body.adopt = true; body.fill_price = fillPrice; }
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/inject-position`,
      body
    );
    return data;
  },

  /**
   * Switch the algo's active monitoring strike to a different open strike.
   * No order is placed — purely a state update; trigger snapshots are reset.
   * @param {string} sessionId
   * @param {string} side   - 'ce' or 'pe'
   * @param {number} strike - target strike (must have open positions)
   */
  async setActiveStrike(sessionId, side, strike) {
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/set-active-strike`,
      { side, strike }
    );
    return data;
  },

  /**
   * Manually increase or decrease active lots on one side.
   * Positive delta → SELL at active_strike (add lots).
   * Negative delta → BUY at active_strike (partial close).
   * @param {string} sessionId
   * @param {string} side  - 'ce' or 'pe'
   * @param {number} delta - lots to add (positive) or remove (negative)
   */
  async adjustActiveLots(sessionId, side, delta) {
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/adjust-active-lots`,
      { side, delta }
    );
    return data;
  },

  /**
   * Buy back ALL lots at a specific strike and remove from the algo ledger.
   * Used to close a risky near-ATM strike before re-establishing farther away.
   * @param {string} sessionId
   * @param {string} side   - 'ce' or 'pe'
   * @param {number} strike - strike to close entirely
   */
  async closeStrike(sessionId, side, strike) {
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/close-strike`,
      { side, strike }
    );
    return data;
  },

  // =========================================================================
  // Phase 3+: Live Data Endpoints
  // =========================================================================

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

  /**
   * Get session performance intelligence (score, efficiency, exit quality)
   */
  async getSessionPerformance(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/performance`);
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
   * Get available DTE presets for multi-expiry support
   */
  async getDTEPresets() {
    const { data } = await api.get(`${BASE_URL}/dte-presets`);
    return data;
  },

  /**
   * Get aggregate PnL across all active sessions
   */
  async getAggregatePnL() {
    const { data } = await api.get(`${BASE_URL}/aggregate-pnl`);
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

  async previewAtmStraddle({ expiry, underlying = 'BTC' }) {
    const { data } = await api.post(`${BASE_URL}/preview_atm_straddle`, { expiry, underlying });
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

  /**
   * Fetch open SHORT BTC options positions from Delta Exchange.
   * Powers the "Adopt from Exchange" UI — shows what's on the exchange.
   * @param {string} [expiry] - Optional expiry filter (DDMMYYYY)
   */
  async getExchangePositions(expiry = null) {
    const params = expiry ? { expiry } : {};
    const { data } = await api.get(`${BASE_URL}/exchange-positions`, { params });
    return data;
  },

  /**
   * Adopt selected exchange positions into an IDLE session.
   * @param {string} sessionId
   * @param {Array} positions - Position objects with symbol, strike, lots, entry_price, side, role
   * @param {string} expiry - DDMMYYYY
   * @param {string} [triggerMode='current_prices'] - 'current_prices' | 'entry_prices'
   */
  async adoptPositions(sessionId, positions, expiry, triggerMode = 'current_prices') {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/adopt`, {
      positions,
      expiry,
      trigger_mode: triggerMode,
    });
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
   * @param {Object} [filters] - Additional query filters
   */
  async getActivities(limit = 50, sessionId = null, filters = {}) {
    const params = { limit, ...(filters || {}) };
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

  /**
   * Get regime controls status for a session
   * @param {string} sessionId
   */
  async getRegimeStatus(sessionId) {
    const { data } = await api.get(
      `${BASE_URL}/session/${sessionId}/regime`
    );
    return data;
  },

  // =========================================================================
  // Margin Guardian
  // =========================================================================

  /**
   * Get real-time margin utilization and guardian tier for a session.
   * Queries exchange wallet and returns current status.
   * @param {string} sessionId
   */
  async getMarginStatus(sessionId) {
    const { data } = await api.get(
      `${BASE_URL}/session/${sessionId}/margin`
    );
    return data;
  },

  /**
   * Get ACCOUNT-LEVEL exchange margin utilization.
   * Covers ALL positions from all algos + manual trades.
   * The exchange is the single source of truth for margin.
   */
  async getExchangeMargin() {
    const { data } = await api.get(`${BASE_URL}/exchange/margin`);
    return data;
  },

  // =========================================================================
  // Perp Delta Hedge (Section 26)
  // =========================================================================

  /**
   * Toggle perp hedge enabled/disabled
   * @param {string} sessionId
   */
  async togglePerpHedge(sessionId) {
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/hedge/toggle`
    );
    return data;
  },

  /**
   * Manually close all perp positions for a session
   * @param {string} sessionId
   */
  async closePerpHedge(sessionId) {
    const { data } = await api.post(
      `${BASE_URL}/session/${sessionId}/hedge/close`
    );
    return data;
  },

  // =========================================================================
  // Trade Audit (Trade Transparency System)
  // =========================================================================

  /** All fills for a session — position_audit_log rows */
  async getAuditTrades(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/audit/trades`);
    return data;
  },

  /** Per-strike P&L summary */
  async getAuditStrikeSummary(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/audit/strike_summary`);
    return data;
  },

  /** Realized P&L attribution breakdown */
  async getAuditPnL(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/audit/pnl`);
    return data;
  },

  /** Self-reconciliation: audit vs live session state */
  async getAuditReconcile(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/audit/reconcile`);
    return data;
  },

  /** Operational event log (session_event_log rows) */
  async getAuditEvents(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/audit/events`);
    return data;
  },

  /** Pre-fill execution intent events (ORDER_INTENT, ORDER_CONFIRMED, EXIT_ROUND_*) */
  async getExecutionEvents(sessionId, limit = 100) {
    const { data } = await api.get(
      `${BASE_URL}/session/${sessionId}/audit/execution-events?limit=${limit}`
    );
    return data;
  },

  /** Available OTM strikes with live premiums for the inject position strike picker */
  async getOptionChain(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/option-chain`);
    return data;
  },

  /**
   * Pin (or unpin) the trigger snapshot for one side.
   * Loosen-only: value must be above current premium.
   * Soft expiry: auto-clears after 3 adjustments (managed backend-side).
   *
   * @param {string} sessionId
   * @param {string} side - 'ce' or 'pe'
   * @param {number|null} value - new trigger baseline; ignored when clear=true
   * @param {boolean} clear - if true, unpin and resume normal ratchet
   */
  async pinTrigger(sessionId, side, value, clear = false) {
    const body = clear ? { side, clear: true } : { side, value };
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/pin-trigger`, body);
    return data; // caller must handle rejection (Promise rejects on non-2xx)
  },

  // =========================================================================
  // Reverse Mode Control
  // =========================================================================

  /**
   * Enable reverse mode for a session.
   * Resets slots/positions for a new activation window.
   * @param {string} sessionId
   */
  async enableReverseMode(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/reverse/enable`);
    return data;
  },

  /**
   * Disable reverse mode for a session.
   * Does NOT close open reverse positions — use closeAllReversePositions for that.
   * @param {string} sessionId
   * @param {string} [reason]
   */
  async disableReverseMode(sessionId, reason = 'manual_ui_disable') {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/reverse/disable`, { reason });
    return data;
  },

  /**
   * Close all open reverse positions for a session.
   * Sends real buy orders. Confirm with the user before calling.
   * @param {string} sessionId
   * @param {string} [reason]
   */
  async closeAllReversePositions(sessionId, reason = 'manual_ui_close_all') {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/reverse/close`, { reason });
    return data;
  },
};

export default mmmService;
