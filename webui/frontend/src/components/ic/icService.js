/**
 * IC Service — Iron Condor
 *
 * API service for IC session management.
 * All REST calls to /api/ic endpoints.
 *
 * Created: 2026-03-24
 */

import api from '../../utils/apiShim';

const BASE_URL = '/api/ic';

const icService = {
  // =========================================================================
  // Session CRUD
  // =========================================================================

  async getSessions(activeOnly = false) {
    const { data } = await api.get(`${BASE_URL}/sessions`, {
      params: { active_only: activeOnly },
    });
    return data;
  },

  async getSession(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}`);
    return data;
  },

  async createSession(config) {
    const { data } = await api.post(`${BASE_URL}/session/create`, config);
    return data;
  },

  async deleteSession(sessionId) {
    try {
      const { data } = await api.delete(`${BASE_URL}/session/${sessionId}`);
      return data;
    } catch (err) {
      if (err?.status === 404) {
        return { success: true, message: `Session ${sessionId} already deleted` };
      }
      throw err;
    }
  },

  // =========================================================================
  // Session Control
  // =========================================================================

  async startSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/start`);
    return data;
  },

  async pauseSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/pause`);
    return data;
  },

  async resumeSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/resume`);
    return data;
  },

  async stopSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/session/${sessionId}/stop`);
    return data;
  },

  // =========================================================================
  // Parameters
  // =========================================================================

  async getDefaults() {
    const { data } = await api.get(`${BASE_URL}/defaults`);
    return data;
  },

  async getParams(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/params`);
    return data;
  },

  async updateParams(sessionId, params) {
    const { data } = await api.put(`${BASE_URL}/session/${sessionId}/params`, { params });
    return data;
  },

  // =========================================================================
  // Cycle History & Activities
  // =========================================================================

  async getCycleHistory(sessionId) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/cycles`);
    return data;
  },

  async getActivities(sessionId, count = 50) {
    const { data } = await api.get(`${BASE_URL}/session/${sessionId}/activities`, {
      params: { count },
    });
    return data;
  },
};

export default icService;
