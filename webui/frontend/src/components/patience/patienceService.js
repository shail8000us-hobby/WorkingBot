/**
 * Patience API service — thin axios wrapper for all /api/patience/* endpoints.
 * Matches the pattern used by mmmService.js.
 *
 * Created: March 14, 2026
 */

import axios from 'axios';

const BASE = '/api/patience';

const patienceAPI = {
  // ── Engine ────────────────────────────────────────────────────────
  getStatus: () => axios.get(`${BASE}/status`),
  startEngine: () => axios.post(`${BASE}/engine/start`),
  stopEngine: () => axios.post(`${BASE}/engine/stop`),

  // ── Cards ─────────────────────────────────────────────────────────
  getCards: (status) =>
    axios.get(`${BASE}/cards`, { params: status ? { status } : {} }),
  createCard: (data) => axios.post(`${BASE}/cards`, data),
  getCard: (id) => axios.get(`${BASE}/cards/${id}`),
  updateCard: (id, data) => axios.put(`${BASE}/cards/${id}`, data),
  deleteCard: (id) => axios.delete(`${BASE}/cards/${id}`),

  // ── Lifecycle ─────────────────────────────────────────────────────
  armCard: (id) => axios.post(`${BASE}/cards/${id}/arm`),
  disarmCard: (id) => axios.post(`${BASE}/cards/${id}/disarm`),
  pauseCard: (id) => axios.post(`${BASE}/cards/${id}/pause`),
  resumeCard: (id) => axios.post(`${BASE}/cards/${id}/resume`),
  cancelCard: (id) => axios.post(`${BASE}/cards/${id}/cancel`),
  executeNow: (id) => axios.post(`${BASE}/cards/${id}/execute-now`),
  closeCard: (id, data) => axios.post(`${BASE}/cards/${id}/close`, data || {}),

  // ── Leg updates ──────────────────────────────────────────────────
  updateLeg: (cardId, legId, data) =>
    axios.patch(`${BASE}/cards/${cardId}/legs/${legId}`, data),

  // ── MMM Handoff ───────────────────────────────────────────────────
  handoffLeg: (cardId, legId) =>
    axios.post(`${BASE}/cards/${cardId}/legs/${legId}/handoff`),

  // ── Execution log ─────────────────────────────────────────────────
  getLog: (cardId) => axios.get(`${BASE}/cards/${cardId}/log`),

  // ── Prices (bid/ask/mark) ────────────────────────────────────────
  getPrices: (cardId) => axios.get(`${BASE}/cards/${cardId}/prices`),

  // ── Options chain (for strike picker in leg editor) ───────────────
  getChainStrikes: (expiryDDMMYYYY) =>
    axios.get(`/api/options-chain/data?underlying=BTC&expiry=${expiryDDMMYYYY}`),

  // ── Templates ────────────────────────────────────────────────────
  getTemplates: () => axios.get(`${BASE}/templates`),
  saveTemplate: (data) => axios.post(`${BASE}/templates`, data),
  getTemplate: (id) => axios.get(`${BASE}/templates/${id}`),
  deleteTemplate: (id) => axios.delete(`${BASE}/templates/${id}`),

  // ── IV ───────────────────────────────────────────────────────────
  getIVCurrent: () => axios.get(`${BASE}/iv/current`),
  getIVHistory: (days = 30) =>
    axios.get(`${BASE}/iv/history`, { params: { days } }),

  // ── P&L ──────────────────────────────────────────────────────────
  getPnL: () => axios.get(`${BASE}/pnl`),

  // ── Performance ───────────────────────────────────────────────────
  getPerformance: () => axios.get(`${BASE}/performance`),

  // ── Bulk controls ─────────────────────────────────────────────────
  armAll: () => axios.post(`${BASE}/arm-all`),
  disarmAll: () => axios.post(`${BASE}/disarm-all`),
  killSwitch: () => axios.post(`${BASE}/kill-switch`),
};

export default patienceAPI;
