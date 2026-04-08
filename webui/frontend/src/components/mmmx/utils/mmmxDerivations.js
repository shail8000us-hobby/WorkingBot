/**
 * MMMX derived state functions — incident queue, health score, integrity, confidence.
 * Pure functions: take state slices, return derived values. No React hooks.
 */

import { CONTRACT_STATUS } from '../mmmxEventContracts';
import { INCIDENT_RANK, INCIDENT_COLOR } from './mmmxConstants';
import { parseIsoToMs, heartbeatAgeSec, formatEta, nowIso } from './mmmxFormatters';
import { ORDER_EVENT_META } from './mmmxConstants';

export function deriveIntegrityState({ session, isConnected, contractStatus, hbAgeSec }) {
  if (!session) return 'UNKNOWN';
  if (!isConnected) return 'STALE';
  if (contractStatus === CONTRACT_STATUS.UNKNOWN) return 'UNKNOWN';
  if (contractStatus === CONTRACT_STATUS.DRIFT) return 'DRIFT';
  if (hbAgeSec != null && hbAgeSec > 600) return 'STALE';
  if (session?.reconcile_required) return 'DRIFT';
  return 'SYNCED';
}

export function deriveConfidence({ integrityState, hbAgeSec }) {
  if (integrityState === 'UNKNOWN') return 'UNKNOWN';
  if (integrityState === 'STALE') return 'LOW';
  if (integrityState === 'DRIFT') return 'MEDIUM';
  if (hbAgeSec != null && hbAgeSec > 180) return 'MEDIUM';
  return 'HIGH';
}

export function deriveExecutionIncidents(timeline = []) {
  if (!Array.isArray(timeline) || !timeline.length) return [];

  const lanes = new Map();
  for (const e of timeline) {
    const lane = e?.origin_client_order_id || e?.client_order_id || e?.order_id ||
      `${e?.symbol || 'UNKNOWN'}:${e?.side || 'NA'}:${e?.tranche_id || 'NA'}`;
    if (!lanes.has(lane)) lanes.set(lane, e);
  }

  const incidents = [];
  const riskyStages = new Set([
    'mmmx_order_intent',
    'mmmx_order_ack',
    'mmmx_order_partial',
    'mmmx_order_retry',
  ]);

  for (const [lane, e] of lanes.entries()) {
    const ageSec = (() => {
      const ts = parseIsoToMs(e?.timestamp);
      if (ts == null) return null;
      return Math.floor((Date.now() - ts) / 1000);
    })();

    if (riskyStages.has(e?.event_name) && ageSec != null && ageSec > 90) {
      incidents.push({
        id: `exec_uncertain:${lane}`,
        level: ageSec > 240 ? 'L3' : 'L2',
        type: 'execution_uncertain',
        title: `Execution uncertain · ${e?.symbol || 'unknown'}`,
        detail: `${ORDER_EVENT_META[e?.event_name]?.label || e?.event_name} stalled for ${ageSec}s`,
        timestamp: e?.timestamp || nowIso(),
        blocking: true,
        recommendedAction: 'Open Execution tab, verify chain, then reconcile if terminal event is missing.',
        escalates_in_sec: ageSec < 240 ? 240 - ageSec : null,
      });
    }

    if (e?.event_name === 'mmmx_order_partial' && Number(e?.residual_size || 0) > 0 && ageSec != null && ageSec > 120) {
      incidents.push({
        id: `residual_aging:${lane}`,
        level: ageSec > 300 ? 'L3' : 'L2',
        type: 'residual_aging',
        title: `Residual aging · ${e?.symbol || 'unknown'}`,
        detail: `Residual ${e.residual_size} pending for ${ageSec}s`,
        timestamp: e?.timestamp || nowIso(),
        blocking: true,
        recommendedAction: 'Force heartbeat and inspect retry lane before any new offensive action.',
        escalates_in_sec: ageSec < 300 ? 300 - ageSec : null,
      });
    }
  }

  return incidents;
}

export function buildIncidentQueue({ session, risk, activity, contract, execution, isConnected, hbAgeSec }) {
  const incidents = [];

  if (!isConnected) {
    incidents.push({
      id: 'ws_disconnected', level: 'L3', type: 'ws_disconnected',
      title: 'WebSocket disconnected',
      detail: 'Live state is stale; high-risk controls should be blocked.',
      timestamp: nowIso(), blocking: true,
      recommendedAction: 'Restore stream connectivity and run reconcile before resume/deploy.',
    });
  }

  if (hbAgeSec != null && hbAgeSec > 120 && ['RUNNING', 'PAUSED'].includes(session?.status)) {
    incidents.push({
      id: 'heartbeat_stale',
      level: hbAgeSec > 600 ? 'L3' : 'L2',
      type: 'heartbeat_stale',
      title: 'Heartbeat stale',
      detail: `Last confirmed heartbeat ${hbAgeSec}s ago`,
      timestamp: session?._last_beat_at || nowIso(),
      blocking: hbAgeSec > 600,
      recommendedAction: 'Force heartbeat and verify monitor/listener health.',
      escalates_in_sec: hbAgeSec < 600 ? 600 - hbAgeSec : null,
    });
  }

  if ((risk?.naked_positions || []).length > 0) {
    incidents.push({
      id: 'naked_positions', level: 'L3', type: 'naked_positions',
      title: 'Naked positions detected',
      detail: (risk?.naked_positions || []).join(', '),
      timestamp: nowIso(), blocking: true,
      recommendedAction: 'Prioritize protection workflow and reconcile position ledger now.',
    });
  }

  if (session?.reconcile_required) {
    incidents.push({
      id: 'reconcile_required', level: 'L2', type: 'reconcile_required',
      title: 'Reconcile required',
      detail: 'Resume/deploy controls are locked until divergence is resolved.',
      timestamp: nowIso(), blocking: true,
      recommendedAction: 'Open Reconcile tab and resolve all divergences.',
    });
  }

  if (risk?.circuit_breaker_state && risk.circuit_breaker_state !== 'CLOSED') {
    incidents.push({
      id: 'circuit_breaker_open', level: 'L3', type: 'circuit_breaker',
      title: `Circuit breaker ${risk.circuit_breaker_state}`,
      detail: 'Exchange circuit breaker is not CLOSED — offensive orders will likely fail or be rejected.',
      timestamp: nowIso(), blocking: true,
      recommendedAction: 'Pause offensive deployment. Monitor until circuit breaker returns to CLOSED before resuming.',
    });
  }

  const ceReserve = session?.ce_reserve_remaining ?? null;
  const peReserve = session?.pe_reserve_remaining ?? null;
  if (ceReserve != null && ceReserve <= 5 && ['RUNNING', 'PAUSED'].includes(session?.status)) {
    incidents.push({
      id: 'ce_reserve_low',
      level: ceReserve === 0 ? 'L3' : 'L2',
      type: 'reserve_exhaustion',
      title: `CE reserve ${ceReserve === 0 ? 'exhausted' : 'critically low'} (${ceReserve} lots)`,
      detail: `CE recovery tranche capacity: ${ceReserve} lots remaining.`,
      timestamp: nowIso(),
      blocking: ceReserve === 0,
      recommendedAction: ceReserve === 0
        ? 'CE recovery unavailable. Rely on PE hedge or manual close.'
        : 'Monitor CE reserve burn rate. Reduce CE-side deployment pace.',
    });
  }
  if (peReserve != null && peReserve <= 5 && ['RUNNING', 'PAUSED'].includes(session?.status)) {
    incidents.push({
      id: 'pe_reserve_low',
      level: peReserve === 0 ? 'L3' : 'L2',
      type: 'reserve_exhaustion',
      title: `PE reserve ${peReserve === 0 ? 'exhausted' : 'critically low'} (${peReserve} lots)`,
      detail: `PE recovery tranche capacity: ${peReserve} lots remaining.`,
      timestamp: nowIso(),
      blocking: peReserve === 0,
      recommendedAction: peReserve === 0
        ? 'PE recovery unavailable. Rely on CE hedge or manual close.'
        : 'Monitor PE reserve burn rate. Reduce PE-side deployment pace.',
    });
  }

  if (contract?.status === CONTRACT_STATUS.DRIFT) {
    const violationCount = (contract?.violations || []).length;
    const mismatchCount = (contract?.integrity?.mismatches || []).length;
    incidents.push({
      id: 'contract_drift', level: 'L3', type: 'contract_drift',
      title: 'Event contract drift detected',
      detail: `${violationCount} contract violation(s), ${mismatchCount} integrity mismatch(es)`,
      timestamp: contract?.last_event_at || nowIso(),
      blocking: true,
      recommendedAction: 'Treat state as uncertain; run integrity check and reconcile.',
    });
  }

  incidents.push(...deriveExecutionIncidents(execution?.timeline || []));

  const orphanedHedges = (session?.hedges || []).filter((h) => h?.status === 'ORPHANED').length;
  if (orphanedHedges > 0) {
    incidents.push({
      id: 'orphan_hedges',
      level: orphanedHedges > 3 ? 'L2' : 'L1',
      type: 'orphan_hedges',
      title: 'Orphaned hedges accumulating',
      detail: `${orphanedHedges} orphaned hedge leg(s) present`,
      timestamp: nowIso(),
      blocking: false,
      recommendedAction: 'Review hedge lifecycle and confirm expiry/runbook handling.',
    });
  }

  for (const ev of (activity || []).slice(0, 20)) {
    if (ev?.type !== 'safety') continue;
    const lvl = String(ev?.level || '').toLowerCase();
    incidents.push({
      id: `safety:${ev.timestamp || ev.message || Math.random()}`,
      level: lvl === 'critical' ? 'L3' : lvl === 'warning' ? 'L2' : 'L1',
      type: 'safety_event',
      title: ev?.safety_type ? `Safety · ${ev.safety_type}` : 'Safety event',
      detail: ev?.message || 'Safety event raised by backend',
      timestamp: ev?.timestamp || nowIso(),
      blocking: lvl === 'critical',
      recommendedAction: 'Open Status tab and follow the active safety recommendation.',
    });
  }

  const unique = new Map();
  incidents.forEach((i) => { if (!unique.has(i.id)) unique.set(i.id, i); });

  return Array.from(unique.values()).sort((a, b) => {
    const sr = (INCIDENT_RANK[b.level] || 0) - (INCIDENT_RANK[a.level] || 0);
    if (sr !== 0) return sr;
    return (parseIsoToMs(b.timestamp) || 0) - (parseIsoToMs(a.timestamp) || 0);
  });
}

export function deriveSystemHealth({ integrityState, confidence, incidents, risk, isConnected, hbAgeSec }) {
  let score = 100;
  if (!isConnected) score -= 35;
  if (integrityState === 'DRIFT') score -= 25;
  if (integrityState === 'STALE') score -= 35;
  if (integrityState === 'UNKNOWN') score -= 45;
  if ((risk?.circuit_breaker_state || 'CLOSED') !== 'CLOSED') score -= 15;
  if ((risk?.whipsaw_score || 0) >= 3) score -= 10;
  if (hbAgeSec != null && hbAgeSec > 120) score -= 10;

  const l3 = incidents.filter((i) => INCIDENT_RANK[i.level] >= INCIDENT_RANK.L3).length;
  const l2 = incidents.filter((i) => i.level === 'L2').length;
  score -= Math.min(30, l3 * 12 + l2 * 4);
  score = Math.max(0, Math.min(100, score));

  let state = 'NORMAL';
  if (confidence === 'UNKNOWN') state = 'UNKNOWN';
  else if (score < 55 || l3 > 0) state = 'CRITICAL';
  else if (score < 80 || l2 > 1) state = 'DEGRADED';

  return { score, state };
}

export function deriveRecommendations({ incidents, health, integrityState }) {
  const recs = [];
  const top = incidents[0];

  if (top) {
    recs.push({
      priority: INCIDENT_RANK[top.level] >= INCIDENT_RANK.L3 ? 'REQUIRED' : 'RECOMMENDED',
      text: top.recommendedAction || 'Investigate highest-severity incident.',
      reason: top.title,
    });
  }

  if (integrityState !== 'SYNCED') {
    recs.push({
      priority: 'REQUIRED',
      text: 'Run reconcile before resume/deploy and keep offensive controls paused.',
      reason: `Integrity ${integrityState}`,
    });
  }

  if (health.state === 'CRITICAL') {
    recs.push({
      priority: 'REQUIRED',
      text: 'Stay in protection-first mode; avoid new deployments until health recovers.',
      reason: `Health ${health.state} (${health.score})`,
    });
  }

  if (!recs.length) {
    recs.push({
      priority: 'OPTIONAL',
      text: 'System is stable. Continue monitoring command strip + trigger ladder.',
      reason: 'No active high-severity incidents',
    });
  }

  return recs.slice(0, 3);
}
