import { z, ZodTypeAny } from 'zod';
import {
  ConfigResponse,
  ConfigResponseSchema,
  PositionsResponse,
  PositionsResponseSchema,
  ReconciliationActionResponse,
  ReconciliationActionResponseSchema,
  ReconciliationOrdersStatus,
  ReconciliationOrdersStatusSchema,
  ReconciliationStatus,
  ReconciliationStatusSchema,
  ReconciliationTableResponse,
  ReconciliationTableResponseSchema,
  StateResponse,
  StateSchema,
  TradingStatusCommandResponse,
  TradingStatusCommandResponseSchema,
  TradingStatusResponse,
  TradingStatusResponseSchema,
} from './schemas';

export class ApiError extends Error {
  readonly status: number;
  readonly url: string;
  readonly details?: unknown;

  constructor(message: string, status: number, url: string, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.url = url;
    this.details = details;
  }
}

export type RequestOptions = Omit<RequestInit, 'body'> & {
  schema?: ZodTypeAny;
  body?: unknown;
};

export async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { schema, body, headers, ...rest } = options;
  const init: RequestInit = {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    ...rest,
  };

  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const response = await fetch(path, init);

  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      // ignore JSON parse failure
    }
    throw new ApiError(response.statusText, response.status, response.url, details);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json();
  if (schema) {
    return schema.parse(data) as T;
  }
  return data as T;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined);
  if (!entries.length) {
    return '';
  }
  return `?${new URLSearchParams(entries as [string, string][])}`;
}

// ---------------------------------------------------------------------------
// Core endpoints
// ---------------------------------------------------------------------------

export async function getState(): Promise<StateResponse> {
  return request<StateResponse>('/api/state', { schema: StateSchema });
}

export async function getPositions(): Promise<PositionsResponse> {
  return request<PositionsResponse>('/api/positions', { schema: PositionsResponseSchema });
}

export async function getConfig(): Promise<ConfigResponse> {
  return request<ConfigResponse>('/api/config', { schema: ConfigResponseSchema });
}

// ---------------------------------------------------------------------------
// Reconciliation endpoints
// ---------------------------------------------------------------------------

export interface ReconciliationTableParams {
  filter?: string;
  sortBy?: string;
  page?: number;
  perPage?: number;
}

export async function getReconciliationStatus(): Promise<ReconciliationStatus> {
  return request<ReconciliationStatus>('/api/recon/status', { schema: ReconciliationStatusSchema });
}

export async function getReconciliationTable(params: ReconciliationTableParams): Promise<ReconciliationTableResponse> {
  const query = buildQuery({
    filter: params.filter,
    sort_by: params.sortBy,
    page: params.page,
    per_page: params.perPage,
  });
  return request<ReconciliationTableResponse>(`/api/recon/table${query}`, {
    schema: ReconciliationTableResponseSchema,
  });
}

export async function getReconciliationOrdersStatus(): Promise<ReconciliationOrdersStatus> {
  return request<ReconciliationOrdersStatus>('/api/recon/orders-memory/status', {
    schema: ReconciliationOrdersStatusSchema,
  });
}

export async function resyncReconciliationOrders(orderIds: string[]): Promise<ReconciliationActionResponse> {
  return request<ReconciliationActionResponse>('/api/recon/resync-json', {
    method: 'POST',
    body: { order_ids: orderIds },
    schema: ReconciliationActionResponseSchema,
  });
}

export async function acknowledgeReconciliationOrders(orderIds: string[]): Promise<ReconciliationActionResponse> {
  return request<ReconciliationActionResponse>('/api/recon/acknowledge', {
    method: 'POST',
    body: { order_ids: orderIds },
    schema: ReconciliationActionResponseSchema,
  });
}

export async function ignoreReconciliationOrders(
  orderIds: string[],
  durationHours = 24,
): Promise<ReconciliationActionResponse> {
  return request<ReconciliationActionResponse>('/api/recon/ignore', {
    method: 'POST',
    body: { order_ids: orderIds, duration_hours: durationHours },
    schema: ReconciliationActionResponseSchema,
  });
}

export async function runReconciliation(): Promise<ReconciliationActionResponse> {
  return request<ReconciliationActionResponse>('/api/recon/run', {
    method: 'POST',
    schema: ReconciliationActionResponseSchema,
  });
}

export interface ClearOrdersMemoryRequest {
  confirmation: string;
  rebuildFromExchange?: boolean;
  triggeredBy?: string;
}

export async function clearReconciliationOrdersMemory(
  payload: ClearOrdersMemoryRequest,
): Promise<ReconciliationOrdersStatus> {
  return request<ReconciliationOrdersStatus>('/api/recon/clear-orders-memory', {
    method: 'POST',
    body: {
      confirmation: payload.confirmation,
      rebuild_from_exchange: payload.rebuildFromExchange,
      triggered_by: payload.triggeredBy,
    },
    schema: ReconciliationOrdersStatusSchema,
  });
}

// ---------------------------------------------------------------------------
// Reconciliation V2 endpoints (if enabled)
// ---------------------------------------------------------------------------

export async function getReconciliationV2Status(): Promise<unknown> {
  return request('/api/recon/v2/status');
}

export async function getReconciliationV2Mismatches(params: Record<string, string>): Promise<unknown> {
  const query = buildQuery(params);
  return request(`/api/recon/v2/mismatches${query}`);
}

export async function runReconciliationV2(): Promise<unknown> {
  return request('/api/recon/v2/run', { method: 'POST' });
}

// ---------------------------------------------------------------------------
// Trading status endpoints
// ---------------------------------------------------------------------------

export async function getTradingStatus(): Promise<TradingStatusResponse> {
  return request<TradingStatusResponse>('/api/trading_status', { schema: TradingStatusResponseSchema });
}

export async function startTrading(force = false): Promise<TradingStatusCommandResponse> {
  return request<TradingStatusCommandResponse>('/api/trading_status/start', {
    method: 'POST',
    body: { force },
    schema: TradingStatusCommandResponseSchema,
  });
}

export async function stopTrading(hardStop = false): Promise<TradingStatusCommandResponse> {
  return request<TradingStatusCommandResponse>('/api/trading_status/stop', {
    method: 'POST',
    body: { hard_stop: hardStop },
    schema: TradingStatusCommandResponseSchema,
  });
}

// ---------------------------------------------------------------------------
// Resolved System State endpoint (SINGLE SOURCE OF TRUTH)
// ---------------------------------------------------------------------------

export interface ResolvedSystemState {
  trading_allowed: boolean;
  guardian_active: boolean;
  safety_level: 'SAFE' | 'CAUTION' | 'BLOCKED';
  execution_mode: 'LIVE' | 'SIM' | 'TESTNET';
  net_exposure: {
    delta: number;
    delta_pct: number;
    label: 'Bullish' | 'Neutral' | 'Bearish';
    gamma: number;
    vega: number;
  };
  warning_list: Array<{
    severity: 'critical' | 'warning' | 'info';
    source: string;
    message: string;
    timestamp: string;
  }>;
  guardian: {
    state: 'ACTIVE' | 'STOPPED';
    reason: string;
    last_decision_time: string;
  };
  timestamp: string;
}

export async function getResolvedState(): Promise<ResolvedSystemState> {
  return request<ResolvedSystemState>('/api/resolved_state');
}

export const schemas = {
  StateSchema,
  PositionsResponseSchema,
  ConfigResponseSchema,
  ReconciliationActionResponseSchema,
  ReconciliationOrdersStatusSchema,
  ReconciliationStatusSchema,
  ReconciliationTableResponseSchema,
  TradingStatusResponseSchema,
  TradingStatusCommandResponseSchema,
};

export type {
  ConfigResponse,
  PositionsResponse,
  ReconciliationActionResponse,
  ReconciliationOrdersStatus,
  ReconciliationStatus,
  ReconciliationTableResponse,
  StateResponse,
  TradingStatusCommandResponse,
  TradingStatusResponse,
};
