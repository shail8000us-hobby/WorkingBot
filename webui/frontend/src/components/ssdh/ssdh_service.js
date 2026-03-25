/**
 * SSDH Service — Short Straddle Double Hedge
 *
 * REST API calls + WebSocket event handling for the SSDH engine.
 * WebSocket connects to /ssdh namespace (separate from MMM's / namespace).
 *
 * Created: March 21, 2026
 */

import api from '../../utils/apiShim';
import { io } from 'socket.io-client';

const BASE_URL = '/api/ssdh';

// ============================================================================
// WebSocket (singleton)
// ============================================================================

let _socket = null;

const wsListeners = {};

function getSocket() {
  if (!_socket) {
    _socket = io('/ssdh', {
      transports: ['websocket', 'polling'],
      autoConnect: true,
    });

    _socket.on('connect', () => {
      console.log('[SSDH WS] Connected to /ssdh namespace');
    });
    _socket.on('disconnect', () => {
      console.log('[SSDH WS] Disconnected');
    });

    // Register all SSDH events
    const EVENTS = [
      'ssdh_state_update',
      'ssdh_leg_entry',
      'ssdh_leg_close',
      'ssdh_wind_down',
      'ssdh_session_closed',
      'ssdh_structure_break',
      'ssdh_vega_spike',
      'ssdh_kill_switch',
    ];
    EVENTS.forEach(event => {
      _socket.on(event, (data) => {
        (wsListeners[event] || []).forEach(cb => cb(data));
      });
    });
  }
  return _socket;
}

function on(event, callback) {
  if (!wsListeners[event]) wsListeners[event] = [];
  wsListeners[event].push(callback);
  getSocket(); // ensure connected
  return () => off(event, callback);
}

function off(event, callback) {
  if (wsListeners[event]) {
    wsListeners[event] = wsListeners[event].filter(cb => cb !== callback);
  }
}

// ============================================================================
// REST API
// ============================================================================

const ssdh_service = {

  // ── WebSocket ─────────────────────────────────────────────────────────────
  on,
  off,
  getSocket,

  // ── Sessions ──────────────────────────────────────────────────────────────

  async getSessions() {
    const { data } = await api.get(`${BASE_URL}/sessions`);
    return data;
  },

  async getSession(sessionId) {
    const { data } = await api.get(`${BASE_URL}/sessions/${sessionId}`);
    return data;
  },

  /**
   * Preview session entry — no execution.
   * Returns strikes, net credit, max loss, breakevens.
   */
  async previewSession(params) {
    const { data } = await api.post(`${BASE_URL}/sessions/start`, {
      ...params,
      confirm: false,
    });
    return data;
  },

  /**
   * Execute session entry.
   * Returns session_id immediately; monitor /sessions/:id for status.
   */
  async startSession(params) {
    const { data } = await api.post(`${BASE_URL}/sessions/start`, {
      ...params,
      confirm: true,
    });
    return data;
  },

  async stopSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/sessions/${sessionId}/stop`);
    return data;
  },

  async killSession(sessionId) {
    const { data } = await api.post(`${BASE_URL}/sessions/${sessionId}/kill`);
    return data;
  },

  async getPresets() {
    const { data } = await api.get(`${BASE_URL}/presets`);
    return data;
  },

  async getHealth() {
    const { data } = await api.get(`${BASE_URL}/health`);
    return data;
  },
};

export default ssdh_service;
