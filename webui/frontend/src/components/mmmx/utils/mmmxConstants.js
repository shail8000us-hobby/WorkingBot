/**
 * MMMX shared constants — status colours, event meta, allowlists.
 * Import from here to keep all other files DRY.
 */

export const STATUS_CFG = {
  DRAFT:        { color: '#9e9e9e', bg: 'rgba(158,158,158,0.12)', label: 'Draft' },
  GATES_PASSED: { color: '#2196f3', bg: 'rgba(33,150,243,0.12)',  label: 'Gates Passed' },
  RUNNING:      { color: '#4caf50', bg: 'rgba(76,175,80,0.12)',   label: 'Running' },
  PAUSED:       { color: '#ff9800', bg: 'rgba(255,152,0,0.12)',   label: 'Paused' },
  COMPLETE:     { color: '#757575', bg: 'rgba(117,117,117,0.12)', label: 'Complete' },
  ERROR:        { color: '#f44336', bg: 'rgba(244,67,54,0.12)',   label: 'Error' },
};

export function scfg(status, reconcileRequired = false) {
  if (status === 'PAUSED' && reconcileRequired) {
    return { color: '#f44336', bg: 'rgba(244,67,54,0.10)', label: 'Paused · RECONCILE REQUIRED' };
  }
  return STATUS_CFG[status] || STATUS_CFG.DRAFT;
}

export const HEDGE_COLOR = {
  ACTIVE: 'success',
  DISPLACED: 'warning',
  ORPHANED: 'error',
  CLOSED: 'default',
};

export const WHIPSAW_LABEL = { 0: 'NORMAL', 1: 'NORMAL', 2: 'CAUTION', 3: 'RESTRICT', 4: 'COOLDOWN' };
export const WHIPSAW_COLOR = { NORMAL: 'success', CAUTION: 'warning', RESTRICT: 'error', COOLDOWN: 'error' };

export const ORDER_EVENT_META = {
  mmmx_order_intent:  { label: 'Intent',  color: 'default' },
  mmmx_order_ack:     { label: 'Ack',     color: 'info' },
  mmmx_order_partial: { label: 'Partial', color: 'warning' },
  mmmx_order_retry:   { label: 'Retry',   color: 'warning' },
  mmmx_order_filled:  { label: 'Filled',  color: 'success' },
  mmmx_order_failed:  { label: 'Failed',  color: 'error' },
};

export const HOT_RELOAD_ALLOWLIST = new Set([
  'tranche_deploy_move_pct','tranche_deploy_iv_delta','hard_stop_multiplier',
  'adjustment_interval_hours','delta_drift_threshold','portfolio_delta_threshold',
  'near_itm_delta','emergency_delta','iv_spike_threshold_pct','iv_catastrophe_pct',
  'atm_protect_threshold','atm_shield_max_shifts','fairness_gate_enabled',
  'fairness_threshold_pct','max_deployments_per_day','profit_booking_enabled',
  'profit_booking_targets','hedging_enabled','hedge_distance_pct',
  'hedge_execution_delay_minutes','hedge_capacity_threshold_lots','close_at_dte',
  'profit_target_pct','profit_target_enabled','whipsaw_window_mins',
  'whipsaw_spot_move_pct','whipsaw_caution_score','whipsaw_restrict_score',
  'whipsaw_cooldown_score','whipsaw_cooldown_interval_hours','otm_distance_pct',
]);

export const INCIDENT_RANK  = { L0: 0, L1: 1, L2: 2, L3: 3, L4: 4 };
export const INCIDENT_COLOR = { L0: 'default', L1: 'info', L2: 'warning', L3: 'error', L4: 'error' };
