/**
 * MMMX Control Safety Rules (Phase 2)
 *
 * Deterministic enable/disable + lock reasons for high-impact controls.
 */

import { CONTRACT_STATUS } from './mmmxEventContracts';

const allow = (tier = 'A') => ({ enabled: true, tier, reason: '' });
const lock = (tier, reason) => ({ enabled: false, tier, reason });

function isTierBC(tier) {
  return tier === 'B' || tier === 'C';
}

function staleContextLock(tier, isConnected, contractStatus, integrityState, heartbeatAgeSec) {
  if (!isTierBC(tier)) return null;
  if (!isConnected) return 'WebSocket disconnected — stale context';
  if (integrityState === 'STALE') return 'Integrity state STALE — refresh/reconcile first';
  if (integrityState === 'DRIFT') return 'Integrity drift detected — reconcile before action';
  if (integrityState === 'UNKNOWN') return 'Integrity UNKNOWN — verify state before action';
  if (heartbeatAgeSec != null && heartbeatAgeSec > 600) {
    return 'Heartbeat too old — stale context lock active';
  }
  if (contractStatus === CONTRACT_STATUS.UNKNOWN) {
    return 'Contract status UNKNOWN — refresh context before action';
  }
  return null;
}

export function evaluateControlSafety({
  session,
  isConnected,
  contractStatus,
  integrityState = 'SYNCED',
  heartbeatAgeSec = null,
  healthState = 'NORMAL',
  pending = {},
}) {
  const status = session?.status;
  const reconcileRequired = !!session?.reconcile_required;

  const p = (key) => !!pending[key];

  const out = {
    deploy_tranche1: allow('B'),
    pause: allow('B'),
    resume: allow('B'),
    stop: allow('C'),
    kill_switch: allow('C'),
    reconcile: allow('B'),
    force_heartbeat: allow('B'),
    hot_reload_apply: allow('B'),
  };

  // stale-context locks for Tier B/C (except explicit recovery controls)
  const staleLockedActions = new Set(['deploy_tranche1', 'pause', 'resume', 'stop', 'hot_reload_apply']);
  Object.entries(out).forEach(([key, conf]) => {
    if (!staleLockedActions.has(key)) return;
    const staleReason = staleContextLock(
      conf.tier,
      isConnected,
      contractStatus,
      integrityState,
      heartbeatAgeSec,
    );
    if (staleReason) out[key] = lock(conf.tier, staleReason);
  });

  if (!session) {
    Object.keys(out).forEach((key) => {
      out[key] = lock(out[key].tier, 'No session selected');
    });
    return out;
  }

  if (p('deploy_tranche1')) out.deploy_tranche1 = lock('B', 'Deploy command already pending');
  else if (!['DRAFT', 'GATES_PASSED', 'RUNNING'].includes(status)) {
    out.deploy_tranche1 = lock('B', `Deploy unavailable in ${status}`);
  } else if (reconcileRequired) {
    out.deploy_tranche1 = lock('B', 'Reconcile required before deployment');
  }

  if (p('pause')) out.pause = lock('B', 'Pause command already pending');
  else if (status !== 'RUNNING') out.pause = lock('B', 'Pause is only available while RUNNING');

  if (p('resume')) out.resume = lock('B', 'Resume command already pending');
  else if (status !== 'PAUSED') out.resume = lock('B', 'Resume is only available while PAUSED');
  else if (reconcileRequired) out.resume = lock('B', 'Reconcile required before resume');
  else if (contractStatus === CONTRACT_STATUS.DRIFT) {
    out.resume = lock('B', 'Integrity drift detected — reconcile before resume');
  }

  if (p('stop')) out.stop = lock('C', 'Stop command already pending');
  else if (!['RUNNING', 'PAUSED', 'GATES_PASSED'].includes(status)) {
    out.stop = lock('C', `Stop unavailable in ${status}`);
  }

  if (p('kill_switch')) out.kill_switch = lock('C', 'Kill-switch command already pending');
  else if (!['RUNNING', 'PAUSED', 'GATES_PASSED'].includes(status)) {
    out.kill_switch = lock('C', `Kill switch unavailable in ${status}`);
  }

  if (p('reconcile')) out.reconcile = lock('B', 'Reconcile command already pending');

  if (p('force_heartbeat')) out.force_heartbeat = lock('B', 'Force heartbeat already pending');
  else if (!['RUNNING', 'PAUSED'].includes(status)) {
    out.force_heartbeat = lock('B', `Force heartbeat unavailable in ${status}`);
  }

  if (p('hot_reload_apply')) out.hot_reload_apply = lock('B', 'Param apply already pending');

  if (healthState === 'CRITICAL') {
    if (out.deploy_tranche1.enabled) out.deploy_tranche1 = lock('B', 'Health CRITICAL — deployment blocked');
    if (out.resume.enabled) out.resume = lock('B', 'Health CRITICAL — resume blocked');
    if (out.hot_reload_apply.enabled) out.hot_reload_apply = lock('B', 'Health CRITICAL — hot reload blocked');
  }

  // UNKNOWN confidence is as dangerous as CRITICAL — lock all offensive actions
  if (healthState === 'UNKNOWN') {
    if (out.deploy_tranche1.enabled) out.deploy_tranche1 = lock('B', 'Health UNKNOWN — deployment blocked pending state recovery');
    if (out.resume.enabled) out.resume = lock('B', 'Health UNKNOWN — resume blocked pending state recovery');
    if (out.hot_reload_apply.enabled) out.hot_reload_apply = lock('B', 'Health UNKNOWN — hot reload blocked pending state recovery');
  }

  return out;
}
