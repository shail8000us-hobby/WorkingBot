/**
 * MMMX REST service — all API calls for the MMMX algorithm.
 * Phase 8: WebUI Integration (MMMX_IMPLEMENTATION_PLAN.md).
 */

const BASE = '/api/mmmx';

async function _req(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(BASE + path, opts);
  const json = await res.json().catch(() => ({ ok: false, error: 'Invalid JSON' }));
  if (!res.ok && json.ok !== false) json.ok = false;
  return json;
}

export const mmmxService = {
  // Session CRUD
  createSession:  (params = {}) => _req('POST',  '/session', { params }),
  listSessions:   (status)      => _req('GET',   `/sessions${status ? `?status=${status}` : ''}`),
  getSession:     (id)          => _req('GET',   `/session/${id}`),

  // Param hot-reload
  hotReloadParams: (id, patch) => _req('PATCH', `/session/${id}/params`, { params: patch }),

  // Lifecycle
  stopSession:    (id, reason)  => _req('POST',  `/session/${id}/stop`,          { reason }),
  killSwitch:     ({ scope = 'session', session_id, reason = 'operator kill switch' } = {}) =>
    _req('POST', '/kill-switch', { scope, session_id, reason }),
  pauseSession:   (id)          => _req('POST',  `/session/${id}/pause`,          {}),
  resumeSession:  (id)          => _req('POST',  `/session/${id}/resume`,         {}),
  startMonitor:   (id)          => _req('POST',  `/session/${id}/start-monitor`,  {}),
  forceHeartbeat: (id, reason = 'operator_manual') =>
    _req('POST', `/session/${id}/force-heartbeat`, { reason }),

  // Manual actions
  deployTranche1: (id, payload)           => _req('POST', `/session/${id}/deploy_tranche1`, payload),
  profitBook:     (id, trancheId, tgtPct) => _req('POST', `/session/${id}/profit_book`,
                                                  { tranche_id: trancheId, target_pct: tgtPct }),
  reconcile:      (id)                    => _req('POST', `/session/${id}/reconcile`, {}),
  scanStrikes:    (id, otmPct = 15)       => _req('GET',  `/session/${id}/scan_strikes?otm_pct=${otmPct}`),

  // Logs
  getAuditLog:    (id, limit = 100) => _req('GET', `/session/${id}/audit?limit=${limit}`),
  getActivityLog: (id, limit = 100) => _req('GET', `/session/${id}/activity?limit=${limit}`),
  getParamHistory:(id, limit = 50)  => _req('GET', `/session/${id}/param-history?limit=${limit}`),

  // Reconciliation confirmation (Phase 9)
  confirmReconcile: (id, divergenceId, action, notes = '') =>
    _req('POST', `/session/${id}/confirm-reconcile`, {
      divergence_id: divergenceId,
      action,
      notes,
    }),

  // Entry gates / expiry
  checkGates:     (id, expiryDdmmyy)  => _req('POST', `/session/${id}/check-gates`,
                                               { expiry_ddmmyy: expiryDdmmyy }),

  // Health
  getHealth: () => _req('GET', '/health'),

  // Live expiries from Delta Exchange (via options-chain service)
  // Returns { expirations: [...], count, underlying } — no ok field, check expirations array directly
  getExpirations: (underlying = 'BTC') =>
    fetch(`/api/options-chain/expirations?underlying=${underlying}`)
      .then(r => r.json())
      .catch(() => ({ expirations: null, error: 'Failed to fetch expirations' })),
};
