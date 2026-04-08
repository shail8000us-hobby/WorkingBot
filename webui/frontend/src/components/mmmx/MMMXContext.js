/**
 * MMMXContext — React context for the MMMX algorithm dashboard.
 *
 * Subscribes to all mmmx_* SocketIO events and exposes derived state:
 *   session, tranches, hedges, risk, activity, isConnected
 *
 * Phase 8: WebUI Integration.
 */

import React, {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useEffect,
  useRef,
} from 'react';
import { mmmxService } from './mmmxService';
import {
  CONTRACT_STATUS,
  normalizeCircuitBreakerState,
  normalizeHeartbeatTimestamp,
  validateEventPayload,
} from './mmmxEventContracts';

// ── Initial state ─────────────────────────────────────────────────────────────

const INIT = {
  session: null,
  tranches: [],
  hedges: [],
  risk: {
    portfolio_delta: 0,
    portfolio_pnl: 0,
    hard_stop_usd: 0,
    whipsaw_score: 0,
    circuit_breaker_state: 'CLOSED',
    imbalance_pct: 0,
    last_beat_at: null,
    last_price_update_at: null,
    naked_positions: [],
    deployment_eligible_tranches: [],
    trigger_winner: null,
    trigger_ladder: [],
    last_trigger_eval_at: null,
    kill_switch_progress: null,
  },
  activity: [],
  pnlHistory: [],   // [{ at, pnl, delta }] — last 200 heartbeats, newest first
  reserveHistory: [], // [{ at, ce, pe }] — last 100 heartbeats, newest first
  isConnected: false,
  activeSessionId: null,
  contract: {
    status: CONTRACT_STATUS.SYNCED,
    violations: [],
    last_event_at: null,
    integrity: {
      stream_version: null,
      stream_checksum: null,
      stream_at: null,
      snapshot_version: null,
      snapshot_checksum: null,
      snapshot_at: null,
      mismatches: [],
    },
  },
  execution: {
    timeline: [],
    last_event_at: null,
  },
};

function computeIntegrityMismatches(integrity) {
  const mismatches = [];
  const sv = integrity?.stream_version;
  const ssv = integrity?.snapshot_version;
  const sc = integrity?.stream_checksum;
  const ssc = integrity?.snapshot_checksum;

  if (sv != null && ssv != null) {
    if (sv === ssv && sc && ssc && sc !== ssc) {
      mismatches.push({
        type: 'CHECKSUM_MISMATCH',
        message: 'Stream and snapshot checksums differ at the same state_version.',
      });
    }
    if (ssv > sv + 2) {
      mismatches.push({
        type: 'STREAM_LAG',
        message: `Stream version lags snapshot by ${ssv - sv}.`,
      });
    }
    if (sv > ssv + 5) {
      mismatches.push({
        type: 'SNAPSHOT_STALE',
        message: `Snapshot version lags stream by ${sv - ssv}.`,
      });
    }
  }

  return mismatches;
}

// ── Reducer ───────────────────────────────────────────────────────────────────

function reducer(state, action) {
  switch (action.type) {
    case 'SET_SESSION': {
      const s = action.payload;
      return {
        ...state,
        session: s,
        tranches: s?.tranches ?? [],
        hedges: s?.hedges ?? [],
        risk: {
          portfolio_delta: s?.portfolio_delta ?? 0,
          portfolio_pnl: s?.portfolio_pnl ?? 0,
          hard_stop_usd: s?.hard_stop_usd ?? 0,
          whipsaw_score: s?._whipsaw_score ?? 0,
          circuit_breaker_state: s?._circuit_breaker?.state ?? 'CLOSED',
          imbalance_pct: s?.ce_lot_balance?.imbalance_pct ?? 0,
          last_beat_at: s?._last_beat_at ?? null,
          last_price_update_at: s?._last_price_update_at ?? null,
          naked_positions: s?._naked_positions ?? [],
          deployment_eligible_tranches: s?.deployment_eligible_tranches ?? [],
          trigger_winner: s?._trigger_eval?.winner ?? null,
          trigger_ladder: s?._trigger_eval?.ladder ?? [],
          last_trigger_eval_at: s?._trigger_eval?.at ?? null,
        },
      };
    }
    case 'PATCH_SESSION':
      return {
        ...state,
        session: state.session ? { ...state.session, ...action.payload } : state.session,
        tranches: action.payload.tranches ?? state.tranches,
        hedges: action.payload.hedges ?? state.hedges,
      };
    case 'PATCH_RISK':
      return { ...state, risk: { ...state.risk, ...action.payload } };
    case 'PUSH_ACTIVITY': {
      const entries = Array.isArray(action.payload) ? action.payload : [action.payload];
      return {
        ...state,
        activity: [...entries, ...state.activity].slice(0, 50),
      };
    }
    case 'SET_CONNECTED':
      return { ...state, isConnected: action.payload };
    case 'SET_ACTIVE_SESSION': {
      const nextId = action.payload;
      const switched = state.activeSessionId && nextId && state.activeSessionId !== nextId;
      return {
        ...state,
        activeSessionId: nextId,
        execution: switched
          ? { ...state.execution, timeline: [], last_event_at: null }
          : state.execution,
      };
    }
    case 'ADD_NAKED_POSITION': {
      const existing = state.risk?.naked_positions ?? [];
      const symbol = action.payload;
      const next = symbol ? Array.from(new Set([...existing, symbol])) : existing;
      return {
        ...state,
        risk: {
          ...state.risk,
          naked_positions: next,
        },
      };
    }
    case 'CONTRACT_EVENT_OK':
      return {
        ...state,
        contract: {
          ...state.contract,
          last_event_at: action.payload.at,
          status: state.contract.status === CONTRACT_STATUS.UNKNOWN
            ? CONTRACT_STATUS.SYNCED
            : state.contract.status,
        },
      };
    case 'CONTRACT_VIOLATION':
      return {
        ...state,
        contract: {
          ...state.contract,
          status: action.payload.status || CONTRACT_STATUS.DRIFT,
          last_event_at: action.payload.at,
          violations: [action.payload, ...(state.contract.violations || [])].slice(0, 100),
        },
      };
    case 'UPDATE_INTEGRITY': {
      const mergedIntegrity = {
        ...(state.contract?.integrity || {}),
        ...action.payload,
      };
      const mismatches = computeIntegrityMismatches(mergedIntegrity);
      const nextStatus = mismatches.length > 0 ? CONTRACT_STATUS.DRIFT : state.contract.status;
      return {
        ...state,
        contract: {
          ...state.contract,
          status: nextStatus,
          integrity: {
            ...mergedIntegrity,
            mismatches,
          },
        },
      };
    }
    case 'PUSH_PNL_SNAPSHOT': {
      const snap = action.payload;
      return {
        ...state,
        pnlHistory: [snap, ...state.pnlHistory].slice(0, 200),
      };
    }
    case 'PUSH_RESERVE_SNAPSHOT': {
      return {
        ...state,
        reserveHistory: [action.payload, ...state.reserveHistory].slice(0, 100),
      };
    }
    case 'PUSH_ORDER_EVENT': {
      const entries = Array.isArray(action.payload) ? action.payload : [action.payload];
      const normalized = entries
        .filter(Boolean)
        .map((e) => ({
          ...e,
          timestamp: e.timestamp || new Date().toISOString(),
        }));

      if (!normalized.length) {
        return state;
      }

      return {
        ...state,
        execution: {
          ...state.execution,
          timeline: [...normalized, ...(state.execution?.timeline || [])].slice(0, 250),
          last_event_at: normalized[0]?.timestamp || state.execution?.last_event_at || null,
        },
      };
    }
    default:
      return state;
  }
}

// ── Context ───────────────────────────────────────────────────────────────────

export const MMMXContext = createContext(null);

export function MMMXProvider({ socket, children }) {
  const [state, dispatch] = useReducer(reducer, INIT);
  const sessionIdRef = useRef(null);
  const latestSessionRef = useRef(null);

  useEffect(() => {
    latestSessionRef.current = state.session;
  }, [state.session]);

  // ── REST: load session ──────────────────────────────────────────────────────
  const loadSession = useCallback(async (id) => {
    if (!id) return;
    sessionIdRef.current = id;
    dispatch({ type: 'SET_ACTIVE_SESSION', payload: id });
    try {
      const res = await mmmxService.getSession(id);
      if (res.ok && res.data) {
        dispatch({ type: 'SET_SESSION', payload: res.data });
        const sig = res.data?._integrity;
        if (sig) {
          dispatch({
            type: 'UPDATE_INTEGRITY',
            payload: {
              snapshot_version: sig.state_version ?? null,
              snapshot_checksum: sig.state_checksum ?? null,
              snapshot_at: sig.generated_at || new Date().toISOString(),
            },
          });
        }
      }
    } catch (e) {
      console.error('[MMMX] loadSession error', e);
      dispatch({
        type: 'PUSH_ACTIVITY',
        payload: {
          type: 'safety',
          safety_type: 'api_failure',
          level: 'warning',
          message: `Session load failed: ${String(e)}`,
          timestamp: new Date().toISOString(),
        },
      });
    }
  }, []);

  const loadActivity = useCallback(async () => {
    const id = sessionIdRef.current;
    if (!id) return;
    try {
      const res = await mmmxService.getActivityLog(id, 50);
      if (res.ok && res.data) {
        dispatch({ type: 'PUSH_ACTIVITY', payload: res.data });
      }
    } catch (e) {
      console.error('[MMMX] loadActivity error', e);
    }
  }, []);

  const validateContract = useCallback((eventName, payload) => {
    const result = validateEventPayload(eventName, payload);
    const at = new Date().toISOString();
    if (result.ok) {
      dispatch({
        type: 'CONTRACT_EVENT_OK',
        payload: { event: eventName, at },
      });
      return;
    }
    dispatch({
      type: 'CONTRACT_VIOLATION',
      payload: {
        event: eventName,
        at,
        status: result.status,
        issues: result.issues,
        payload_keys: payload && typeof payload === 'object' ? Object.keys(payload) : [],
      },
    });
  }, []);

  // ── Socket event handlers ───────────────────────────────────────────────────
  useEffect(() => {
    if (!socket) return;

    const onHeartbeat = (data) => {
      validateContract('mmmx_heartbeat', data);
      dispatch({
        type: 'PATCH_RISK',
        payload: {
          portfolio_delta: data.portfolio_delta ?? 0,
          portfolio_pnl: data.portfolio_pnl ?? 0,
          hard_stop_usd: data.hard_stop_usd ?? 0,
          last_beat_at: normalizeHeartbeatTimestamp(data),
        },
      });
      if (data?.integrity) {
        dispatch({
          type: 'UPDATE_INTEGRITY',
          payload: {
            stream_version: data.integrity.state_version ?? null,
            stream_checksum: data.integrity.state_checksum ?? null,
            stream_at: data.integrity.generated_at || data.timestamp || new Date().toISOString(),
          },
        });
      }
      dispatch({
        type: 'PATCH_SESSION',
        payload: {
          beat_number: data.beat_number,
          status: data.status,
        },
      });
      // Accumulate PnL history for sparkline/chart
      const beatAt = normalizeHeartbeatTimestamp(data);
      if (beatAt) {
        dispatch({
          type: 'PUSH_PNL_SNAPSHOT',
          payload: {
            at: beatAt,
            pnl: data.portfolio_pnl ?? 0,
            delta: data.portfolio_delta ?? 0,
          },
        });

        const ceRes = data.ce_reserve_remaining ?? latestSessionRef.current?.ce_reserve_remaining;
        const peRes = data.pe_reserve_remaining ?? latestSessionRef.current?.pe_reserve_remaining;

        if (ceRes != null && peRes != null) {
          dispatch({
            type: 'PUSH_RESERVE_SNAPSHOT',
            payload: { at: beatAt, ce: ceRes, pe: peRes },
          });
        }
      }
    };

    const onPnlUpdate = (data) => {
      validateContract('mmmx_pnl_update', data);
      dispatch({
        type: 'PATCH_SESSION',
        payload: {
          portfolio_pnl: data.portfolio_pnl,
          total_premium_collected: data.total_premium_collected,
          profit_booked_total: data.profit_booked_total,
        },
      });
    };

    const onTrancheDeployed = (data) => {
      validateContract('mmmx_tranche_deployed', data);
      if (Array.isArray(data?.tranches)) {
        dispatch({ type: 'PATCH_SESSION', payload: { tranches: data.tranches } });
        return;
      }
      if (sessionIdRef.current) loadSession(sessionIdRef.current);
    };

    const onTrancheClosed = (data) => {
      validateContract('mmmx_tranche_closed', data);
      if (Array.isArray(data?.tranches)) {
        dispatch({ type: 'PATCH_SESSION', payload: { tranches: data.tranches } });
        return;
      }
      if (sessionIdRef.current) loadSession(sessionIdRef.current);
    };

    const onHedgeExecuted = (data) => {
      validateContract('mmmx_hedge_executed', data);
      if (Array.isArray(data?.hedges)) {
        dispatch({ type: 'PATCH_SESSION', payload: { hedges: data.hedges } });
        return;
      }
      if (sessionIdRef.current) loadSession(sessionIdRef.current);
    };

    const onWhipsawUpdate = (data, eventName = 'mmmx_whipsaw') => {
      validateContract(eventName, data);
      dispatch({ type: 'PATCH_RISK', payload: { whipsaw_score: data.score } });
    };

    const onWhipsaw = (data) => onWhipsawUpdate(data, 'mmmx_whipsaw');
    const onWhipsawLegacy = (data) => onWhipsawUpdate(data, 'mmmx_whipsaw_update');

    const onCircuitBreaker = (data) => {
      validateContract('mmmx_circuit_breaker', data);
      dispatch({
        type: 'PATCH_RISK',
        payload: { circuit_breaker_state: normalizeCircuitBreakerState(data) },
      });
      dispatch({
        type: 'PUSH_ACTIVITY',
        payload: {
          type: 'circuit_breaker',
          old_state: data.old_state,
          new_state: data.new_state,
          state: normalizeCircuitBreakerState(data),
        },
      });
    };

    const onAtmShield = (data) => {
      validateContract('mmmx_atm_shield', data);
      dispatch({ type: 'PUSH_ACTIVITY', payload: { type: 'atm_shield', ...data } });
    };

    const onParamsChanged = (data) => {
      validateContract('mmmx_params_changed', data);
      if (sessionIdRef.current) loadSession(sessionIdRef.current);
    };

    const onStatusChange = (data) => {
      validateContract('mmmx_status_change', data);
      dispatch({ type: 'PATCH_SESSION', payload: { status: data.new_status } });
      loadActivity();
    };

    const onDeploymentQueue = (data) => {
      validateContract('mmmx_deployment_queue', data);
      dispatch({
        type: 'PATCH_RISK',
        payload: { deployment_eligible_tranches: data.queue ?? [] },
      });
    };

    const onSafety = (data) => {
      validateContract('mmmx_safety', data);
      dispatch({ type: 'PUSH_ACTIVITY', payload: { type: 'safety', ...data } });
    };

    const onNakedPosition = (data) => {
      validateContract('mmmx_naked_position', data);
      dispatch({
        type: 'ADD_NAKED_POSITION',
        payload: data.symbol || `${data.side || 'UNKNOWN'}:${data.tranche_id || 'unknown'}`,
      });
      dispatch({ type: 'PUSH_ACTIVITY', payload: { type: 'naked_position', ...data } });
    };

    const onSessionCreated = (data) => {
      validateContract('mmmx_session_created', data);
      dispatch({ type: 'PUSH_ACTIVITY', payload: { type: 'session_created', ...data } });
    };

    const onSessionStopped = (data) => {
      validateContract('mmmx_session_stopped', data);
      if (sessionIdRef.current && data.session_id === sessionIdRef.current) {
        dispatch({ type: 'PATCH_SESSION', payload: { status: 'COMPLETE' } });
      }
      dispatch({ type: 'PUSH_ACTIVITY', payload: { type: 'session_stopped', ...data } });
    };

    const onKillSwitchProgress = (data) => {
      validateContract('mmmx_kill_switch_progress', data);
      dispatch({
        type: 'PATCH_RISK',
        payload: {
          kill_switch_progress: {
            ...data,
            timestamp: data?.timestamp || new Date().toISOString(),
          },
        },
      });
      dispatch({ type: 'PUSH_ACTIVITY', payload: { type: 'kill_switch_progress', ...data } });
    };

    const onTriggerEvaluation = (data) => {
      validateContract('mmmx_trigger_evaluation', data);
      dispatch({
        type: 'PATCH_RISK',
        payload: {
          trigger_winner: data?.winner ?? null,
          trigger_ladder: Array.isArray(data?.ladder) ? data.ladder : [],
          last_trigger_eval_at: data?.timestamp ?? new Date().toISOString(),
        },
      });

      if (data?.winner?.trigger_name) {
        dispatch({
          type: 'PUSH_ACTIVITY',
          payload: {
            type: 'trigger_evaluation',
            trigger_name: data.winner.trigger_name,
            reason: data.winner.reason,
            severity: data.winner.severity,
            beat_number: data.beat_number,
          },
        });
      }
    };

    const onOrderLifecycle = (eventName) => (data) => {
      validateContract(eventName, data);
      const eventSessionId = data?.session_id;
      if (sessionIdRef.current && (!eventSessionId || eventSessionId !== sessionIdRef.current)) {
        return;
      }
      dispatch({
        type: 'PUSH_ORDER_EVENT',
        payload: {
          ...data,
          event_name: eventName,
        },
      });
    };

    const onOrderIntent = onOrderLifecycle('mmmx_order_intent');
    const onOrderAck = onOrderLifecycle('mmmx_order_ack');
    const onOrderPartial = onOrderLifecycle('mmmx_order_partial');
    const onOrderRetry = onOrderLifecycle('mmmx_order_retry');
    const onOrderFilled = onOrderLifecycle('mmmx_order_filled');
    const onOrderFailed = onOrderLifecycle('mmmx_order_failed');

    socket.on('mmmx_heartbeat',         onHeartbeat);
    socket.on('mmmx_pnl_update',        onPnlUpdate);
    socket.on('mmmx_tranche_deployed',  onTrancheDeployed);
    socket.on('mmmx_tranche_closed',    onTrancheClosed);
    socket.on('mmmx_hedge_executed',    onHedgeExecuted);
    socket.on('mmmx_whipsaw',           onWhipsaw);
    socket.on('mmmx_whipsaw_update',    onWhipsawLegacy);
    socket.on('mmmx_circuit_breaker',   onCircuitBreaker);
    socket.on('mmmx_atm_shield',        onAtmShield);
    socket.on('mmmx_params_changed',    onParamsChanged);
    socket.on('mmmx_status_change',     onStatusChange);
    socket.on('mmmx_deployment_queue',  onDeploymentQueue);
    socket.on('mmmx_safety',            onSafety);
    socket.on('mmmx_naked_position',    onNakedPosition);
    socket.on('mmmx_session_created',   onSessionCreated);
    socket.on('mmmx_session_stopped',   onSessionStopped);
    socket.on('mmmx_kill_switch_progress', onKillSwitchProgress);
    socket.on('mmmx_trigger_evaluation', onTriggerEvaluation);
    socket.on('mmmx_order_intent',      onOrderIntent);
    socket.on('mmmx_order_ack',         onOrderAck);
    socket.on('mmmx_order_partial',     onOrderPartial);
    socket.on('mmmx_order_retry',       onOrderRetry);
    socket.on('mmmx_order_filled',      onOrderFilled);
    socket.on('mmmx_order_failed',      onOrderFailed);

    dispatch({ type: 'SET_CONNECTED', payload: true });

    return () => {
      socket.off('mmmx_heartbeat',        onHeartbeat);
      socket.off('mmmx_pnl_update',       onPnlUpdate);
      socket.off('mmmx_tranche_deployed', onTrancheDeployed);
      socket.off('mmmx_tranche_closed',   onTrancheClosed);
      socket.off('mmmx_hedge_executed',   onHedgeExecuted);
      socket.off('mmmx_whipsaw',          onWhipsaw);
      socket.off('mmmx_whipsaw_update',   onWhipsawLegacy);
      socket.off('mmmx_circuit_breaker',  onCircuitBreaker);
      socket.off('mmmx_atm_shield',       onAtmShield);
      socket.off('mmmx_params_changed',   onParamsChanged);
      socket.off('mmmx_status_change',    onStatusChange);
      socket.off('mmmx_deployment_queue', onDeploymentQueue);
      socket.off('mmmx_safety',           onSafety);
      socket.off('mmmx_naked_position',   onNakedPosition);
      socket.off('mmmx_session_created',  onSessionCreated);
      socket.off('mmmx_session_stopped',  onSessionStopped);
      socket.off('mmmx_kill_switch_progress', onKillSwitchProgress);
      socket.off('mmmx_trigger_evaluation', onTriggerEvaluation);
      socket.off('mmmx_order_intent',     onOrderIntent);
      socket.off('mmmx_order_ack',        onOrderAck);
      socket.off('mmmx_order_partial',    onOrderPartial);
      socket.off('mmmx_order_retry',      onOrderRetry);
      socket.off('mmmx_order_filled',     onOrderFilled);
      socket.off('mmmx_order_failed',     onOrderFailed);
      dispatch({ type: 'SET_CONNECTED', payload: false });
    };
  }, [socket, loadSession, loadActivity, validateContract]);

  const value = {
    ...state,
    pnlHistory: state.pnlHistory,
    reserveHistory: state.reserveHistory,
    loadSession,
    loadActivity,
    dispatch,
  };

  return <MMMXContext.Provider value={value}>{children}</MMMXContext.Provider>;
}

export function useMMMX() {
  const ctx = useContext(MMMXContext);
  if (!ctx) throw new Error('useMMMX must be used inside MMMXProvider');
  return ctx;
}
