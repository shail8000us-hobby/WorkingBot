/**
 * MMMX Event Contracts (Phase 0)
 *
 * Source of truth for websocket payload expectations and lightweight
 * runtime validation. Used by MMMXContext to detect drift between
 * backend emitters and frontend consumers.
 */

export const CONTRACT_STATUS = {
  SYNCED: 'SYNCED',
  DRIFT: 'DRIFT',
  UNKNOWN: 'UNKNOWN',
};

export const EVENT_ISSUE_TYPE = {
  EVENT_MISSING: 'EVENT_MISSING',
  EVENT_MISMATCH: 'EVENT_MISMATCH',
  EVENT_INSUFFICIENT: 'EVENT_INSUFFICIENT',
};

/**
 * Contract registry keyed by websocket event name.
 * `required` keys must exist in payload.
 */
export const MMMX_EVENT_CONTRACTS = {
  mmmx_heartbeat: {
    required: ['session_id', 'status', 'beat_number'],
    optional: ['portfolio_pnl', 'portfolio_delta', 'hard_stop_usd', 'timestamp', 'beat_at', 'integrity'],
  },
  mmmx_pnl_update: {
    required: ['session_id', 'portfolio_pnl'],
    optional: ['hard_stop_usd', 'total_premium_collected', 'profit_booked_total', 'total_hedge_cost_paid'],
  },
  mmmx_tranche_deployed: {
    required: ['session_id', 'tranche_id'],
    optional: ['tranches', 'ce_strike', 'pe_strike', 'ce_premium', 'pe_premium', 'lots'],
  },
  mmmx_tranche_closed: {
    required: ['session_id', 'tranche_id'],
    optional: ['tranches', 'reason', 'realized_pnl'],
  },
  mmmx_hedge_executed: {
    required: ['session_id', 'hedge_id'],
    optional: ['hedges'],
  },
  mmmx_whipsaw: {
    required: ['session_id', 'score'],
    optional: ['level'],
  },
  mmmx_whipsaw_update: {
    required: ['session_id', 'score'],
    optional: ['level'],
  },
  mmmx_circuit_breaker: {
    required: ['session_id'],
    optional: ['state', 'old_state', 'new_state'],
  },
  mmmx_atm_shield: {
    required: ['session_id'],
    optional: [],
  },
  mmmx_params_changed: {
    required: ['session_id'],
    optional: ['diff'],
  },
  mmmx_status_change: {
    required: ['session_id', 'new_status'],
    optional: ['old_status', 'reason'],
  },
  mmmx_deployment_queue: {
    required: ['session_id'],
    optional: ['queue'],
  },
  mmmx_safety: {
    required: ['session_id', 'type', 'level', 'message'],
    optional: ['details'],
  },
  mmmx_naked_position: {
    required: ['session_id', 'tranche_id', 'side'],
    optional: ['symbol', 'since'],
  },
  mmmx_session_created: {
    required: ['session_id'],
    optional: ['summary'],
  },
  mmmx_session_stopped: {
    required: ['session_id'],
    optional: ['reason'],
  },
  mmmx_kill_switch_progress: {
    required: ['correlation_id', 'scope', 'stage', 'status'],
    optional: ['session_id', 'details', 'timestamp'],
  },
  mmmx_trigger_evaluation: {
    required: ['session_id', 'beat_number', 'status', 'ladder'],
    optional: ['winner', 'metrics', 'timestamp'],
  },
  mmmx_order_intent: {
    required: ['session_id', 'symbol', 'side', 'requested_size', 'mode', 'attempt', 'client_order_id'],
    optional: ['tranche_id', 'action', 'max_reprice_attempts', 'reduce_only', 'use_bid_entry', 'timestamp'],
  },
  mmmx_order_ack: {
    required: ['session_id', 'symbol', 'side', 'requested_size', 'mode', 'attempt', 'client_order_id', 'order_id'],
    optional: ['tranche_id', 'action', 'price', 'repriced', 'deduped', 'state', 'timestamp'],
  },
  mmmx_order_partial: {
    required: ['session_id', 'symbol', 'side', 'requested_size', 'mode', 'attempt', 'client_order_id', 'order_id', 'filled_size', 'residual_size'],
    optional: ['tranche_id', 'action', 'avg_price', 'timestamp'],
  },
  mmmx_order_retry: {
    required: ['session_id', 'symbol', 'side', 'requested_size', 'mode', 'attempt', 'client_order_id', 'reason_code', 'reason'],
    optional: ['tranche_id', 'action', 'order_id', 'max_slippage_pct', 'go_emergency', 'timestamp'],
  },
  mmmx_order_filled: {
    required: ['session_id', 'symbol', 'side', 'requested_size', 'mode', 'attempt', 'client_order_id', 'order_id', 'filled_size', 'residual_size', 'avg_price'],
    optional: ['tranche_id', 'action', 'fees_paid', 'timestamp'],
  },
  mmmx_order_failed: {
    required: ['session_id', 'symbol', 'side', 'requested_size', 'mode', 'attempt', 'client_order_id', 'reason_code', 'reason'],
    optional: ['tranche_id', 'action', 'order_id', 'filled_size', 'residual_size', 'timestamp'],
  },
};

export function validateEventPayload(eventName, payload) {
  const contract = MMMX_EVENT_CONTRACTS[eventName];
  if (!contract) {
    return {
      ok: false,
      status: CONTRACT_STATUS.UNKNOWN,
      issues: [{
        type: EVENT_ISSUE_TYPE.EVENT_MISSING,
        event: eventName,
        message: `No contract registered for event: ${eventName}`,
      }],
    };
  }

  const body = payload && typeof payload === 'object' ? payload : {};
  const missing = contract.required.filter((key) => !(key in body));
  if (missing.length === 0) {
    return { ok: true, status: CONTRACT_STATUS.SYNCED, issues: [] };
  }

  return {
    ok: false,
    status: CONTRACT_STATUS.DRIFT,
    issues: missing.map((key) => ({
      type: EVENT_ISSUE_TYPE.EVENT_INSUFFICIENT,
      event: eventName,
      key,
      message: `Missing required payload field: ${key}`,
    })),
  };
}

export function normalizeCircuitBreakerState(payload) {
  return payload?.state ?? payload?.new_state ?? payload?.old_state ?? 'UNKNOWN';
}

export function normalizeHeartbeatTimestamp(payload) {
  return payload?.beat_at ?? payload?.timestamp ?? null;
}
