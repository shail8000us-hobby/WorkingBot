/**
 * SSR Algo Service
 * 
 * API service for SSR Algo session management.
 * Provides methods for all SSR Algo backend endpoints.
 * 
 * Created: February 2, 2026
 */

import api from '../../utils/apiShim';

const BASE_URL = '/api/ssr_algo';

/**
 * SSR Algo API Service
 */
const ssrAlgoService = {
  /**
   * Get all sessions
   * @param {boolean} activeOnly - If true, only return active sessions
   * @returns {Promise<{success: boolean, sessions: Array, count: number}>}
   */
  async getSessions(activeOnly = false) {
    const { data } = await api.get(`${BASE_URL}/sessions`, {
      params: { active_only: activeOnly }
    });
    return data;
  },

  /**
   * Get a specific session by ID
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, session: Object}>}
   */
  async getSession(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}`);
    return data;
  },

  /**
   * Create a new session
   * @param {Object} config - Session configuration
   * @param {string} config.underlying - BTC or ETH
   * @param {string} config.expiry - Expiry date (DDMMYYYY)
   * @param {number} config.auto_loop_rounds - Number of auto-loop rounds (1-10)
   * @param {string} config.order_type - Order type (ssr, maker, market)
   * @param {string} config.start_time - Start time (HH:MM)
   * @param {string} config.end_time - End time (HH:MM)
   * @param {Object} config.strike_config - Strike selection config
   * @returns {Promise<{success: boolean, session: Object, strikes_preview: Object}>}
   */
  async createSession(config) {
    const { data } = await api.post(`${BASE_URL}/session/create`, config);
    return data;
  },

  /**
   * Delete a session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, message: string}>}
   */
  async deleteSession(sessionId) {
    const { data } = await api.delete(`${BASE_URL}/session/${sessionId}`);
    return data;
  },

  /**
   * Preview strikes without creating a session
   * @param {Object} params - Preview parameters
   * @param {string} params.underlying - BTC or ETH
   * @param {string} params.expiry - Expiry date (DDMMYYYY)
   * @param {Object} params.strike_config - Strike selection config
   * @returns {Promise<{success: boolean, atm: Object, otm_ce_buy: Object, ...}>}
   */
  async previewStrikes(params) {
    const { data } = await api.post(`${BASE_URL}/preview_strikes`, params);
    return data;
  },

  /**
   * Start a session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, session_id: string, status: string, strikes: Object}>}
   */
  async startSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/start`);
    return data;
  },

  /**
   * Pause a session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, session_id: string, status: string}>}
   */
  async pauseSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/pause`);
    return data;
  },

  /**
   * Resume a paused session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, session_id: string, status: string}>}
   */
  async resumeSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/resume`);
    return data;
  },

  /**
   * Stop a session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, session_id: string, status: string}>}
   */
  async stopSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/stop`);
    return data;
  },

  /**
   * Retry a session in ERROR or STOPPED state
   * Clears error and resets to IDLE for fresh start
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, session_id: string, status: string, message: string}>}
   */
  async retrySession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/retry`);
    return data;
  },

  /**
   * Get status of all active sessions
   * @returns {Promise<{success: boolean, active_count: number, sessions: Array}>}
   */
  async getStatus() {
    const { data } = await api.get(`${BASE_URL}/status`);
    return data;
  },

  /**
   * Get payoff data for a session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, payoff_curve: Array, max_loss_points: Object, ...}>}
   */
  async getSessionPayoff(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/payoff`);
    return data;
  },

  /**
   * Get monitor status for a session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, monitor: Object, max_loss_points: Object}>}
   */
  async getMonitorStatus(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/monitor`);
    return data;
  },

  /**
   * Get all monitor statuses
   * @returns {Promise<{success: boolean, monitor_count: number, monitors: Object}>}
   */
  async getAllMonitors() {
    const { data } = await api.get(`${BASE_URL}/monitors`);
    return data;
  },

  /**
   * Get activity logs for a session
   * @param {string} sessionId - Session ID
   * @param {number} limit - Maximum logs to return (default: 50)
   * @returns {Promise<{success: boolean, logs: Array, count: number}>}
   */
  async getSessionLogs(sessionId, limit = 50) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/logs`, {
      params: { limit }
    });
    return data;
  },

  /**
   * Sync pending orders with exchange
   * Checks fill status and updates session state
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, filled: number, pending: number, fills: Array}>}
   */
  async syncOrders(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/sync_orders`);
    return data;
  },

  /**
   * Get pending orders for a session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, pending_count: number, pending_orders: Array}>}
   */
  async getPendingOrders(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/pending_orders`);
    return data;
  },

  /**
   * Exit a session — close all positions via market orders
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, orders_placed: number, message: string}>}
   */
  async exitSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/exit`);
    return data;
  },

  /**
   * Get live Greeks and MTM P&L for a session (forces fresh fetch)
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, live_greeks: Object, live_pnl: Object, position_greeks: Array}>}
   */
  async getSessionGreeks(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/greeks`);
    return data;
  },

  /**
   * Get analytics for a specific session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, analytics: Object}>}
   */
  async getSessionAnalytics(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/analytics`);
    return data;
  },

  /**
   * Get aggregate analytics across all sessions
   * @returns {Promise<{success: boolean, total_sessions: number, win_rate: number, total_pnl: number}>}
   */
  async getAggregateAnalytics() {
    const { data } = await api.get(`${BASE_URL}/analytics`);
    return data;
  },

  /**
   * Get RV/IV analysis for a session
   * @param {string} sessionId - Session ID
   * @returns {Promise<{success: boolean, snapshot: Object, history: Array}>}
   */
  async getSessionRvIv(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/rv_iv`);
    return data;
  },

  /**
   * Roll session to next expiry
   * @param {string} sessionId - Session ID
   * @param {string} nextExpiry - Next expiry in DDMMYYYY format
   * @returns {Promise<{success: boolean, new_session_id: string}>}
   */
  async rollSession(sessionId, nextExpiry) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/roll`, {
      next_expiry: nextExpiry
    });
    return data;
  },

  /**
   * Health check
   * @returns {Promise<{success: boolean, module: string, status: string}>}
   */
  async healthCheck() {
    const { data } = await api.get(`${BASE_URL}/health`);
    return data;
  }
};

export default ssrAlgoService;
