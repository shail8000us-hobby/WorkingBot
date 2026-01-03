/**
 * API Service
 * 
 * Instrument-scoped REST API client.
 * All endpoints are per-instance, no global mutable state.
 * 
 * Enhanced with Circuit Breaker pattern for resilience.
 */

import type {
  InstanceId,
  ApiResponse,
  InstrumentState,
  Position,
  Order,
  GridConfig,
  InstanceIdentity,
} from '../types';
import { circuitBreakerManager } from '../utils/circuitBreaker';

// ============================================================================
// BASE CONFIG
// ============================================================================

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5555';

interface FetchOptions extends RequestInit {
  timeout?: number;
}

// ============================================================================
// FETCH WRAPPER
// ============================================================================

async function apiFetch<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<ApiResponse<T>> {
  const { timeout = 10000, ...fetchOptions } = options;
  
  // Extract service name from endpoint for circuit breaker
  const serviceName = endpoint.split('/')[1] || 'api';
  
  // Wrap fetch in circuit breaker
  try {
    return await circuitBreakerManager.execute(serviceName, async () => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
          ...fetchOptions,
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            ...fetchOptions.headers,
          },
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
          // Non-2xx responses count as failures for circuit breaker
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        return {
          success: true,
          data,
          timestamp: Date.now(),
          staleAfterMs: 5000, // Default 5s staleness
        };
      } catch (error) {
        clearTimeout(timeoutId);
        throw error; // Propagate to circuit breaker
      }
    });
  } catch (error) {
    // Circuit breaker threw error or fetch failed
    const isCircuitBreakerError = error instanceof Error && error.name === 'CircuitBreakerError';
    const isTimeout = error instanceof DOMException && error.name === 'AbortError';
    
    return {
      success: false,
      data: null as unknown as T,
      timestamp: Date.now(),
      staleAfterMs: 0,
      error: {
        code: isCircuitBreakerError ? 'CIRCUIT_OPEN' : (isTimeout ? 'TIMEOUT' : 'NETWORK_ERROR'),
        message: error instanceof Error ? error.message : 'Unknown error',
      },
    };
  }
}

// ============================================================================
// INSTANCE ENDPOINTS
// ============================================================================

/**
 * List all registered instances.
 */
export async function listInstances(): Promise<ApiResponse<InstanceIdentity[]>> {
  // Use symbols endpoint which has instance info
  const response = await apiFetch<any>('/api/symbols');
  if (response.success && response.data?.symbols) {
    const instances: InstanceIdentity[] = [];
    for (const symbol of response.data.symbols) {
      if (symbol.enabled && symbol.instances) {
        for (const instId of symbol.instances) {
          // Extract mode from instance ID (e.g., BTCUSD_LONG -> LONG)
          const mode = instId.includes('_LONG') ? 'LONG' : 'SHORT';
          instances.push({
            instanceId: instId as InstanceId,
            symbol: symbol.name,
            mode: mode as 'LONG' | 'SHORT',
            displayName: instId,
            exchange: 'delta',
          });
        }
      }
    }
    return { ...response, data: instances };
  }
  return response as ApiResponse<InstanceIdentity[]>;
}

/**
 * Get full state for a single instance.
 */
export async function getInstanceState(
  instanceId: InstanceId
): Promise<ApiResponse<InstrumentState>> {
  // Use symbols endpoint and filter
  const response = await apiFetch<any>('/api/symbols');
  if (response.success && response.data?.symbols) {
    for (const symbol of response.data.symbols) {
      if (symbol.instances?.includes(instanceId)) {
        const mode = instanceId.includes('_LONG') ? 'LONG' : 'SHORT';
        const state: InstrumentState = {
          identity: {
            instanceId,
            symbol: symbol.name,
            mode: mode as 'LONG' | 'SHORT',
            displayName: instanceId,
            exchange: 'delta',
          },
          health: {
            connection: 'connected',
            freshness: 'fresh',
            lastUpdate: Date.now(),
            lastError: null,
            reconnectAttempts: 0,
          },
          authority: {
            heartbeat: { status: 'alive', lastSeen: Date.now(), processId: null, reason: null },
            guardian: { status: 'permitting', blockedBy: null, blockedSince: null, riskLevel: 'normal' },
            trading: { intent: 'active', pausedBy: null, pausedReason: null, lastAction: null, lastActionTime: null },
          },
          controlledBy: 'trading',
          tradingState: symbol.enabled ? 'active' : 'paused',
          positions: [],
          orders: [],
          pnl: { realized: 0, unrealized: 0, total: 0, todayRealized: 0, todayUnrealized: 0, todayTotal: 0 },
          grid: symbol.grid ? {
            enabled: true,
            lowerPrice: parseFloat(symbol.grid?.lower || '0'),
            upperPrice: parseFloat(symbol.grid?.upper || '0'),
            gridLevels: 10,
            orderSize: parseFloat(symbol.limits?.lot_size || '1'),
            currentPrice: parseFloat(symbol.grid?.reference || '0'),
            filledLevels: 0,
            pendingLevels: 0,
          } : null,
          risk: { level: 'normal', exposure: 0, maxExposure: 10000, exposurePercent: 0, dailyLoss: 0, maxDailyLoss: 1000, breaches: [] },
          timeline: [],
          lastFullSync: Date.now(),
          partialDataFlags: { positions: false, orders: false, pnl: false, grid: false },
        };
        return { ...response, data: state };
      }
    }
  }
  return response as ApiResponse<InstrumentState>;
}

/**
 * Get positions for an instance.
 */
export async function getInstancePositions(
  instanceId: InstanceId
): Promise<ApiResponse<Position[]>> {
  // Extract symbol from instanceId (e.g., BTCUSD_LONG -> BTCUSD)
  const symbol = instanceId.replace(/_LONG|_SHORT/g, '');
  return apiFetch<Position[]>(`/api/positions?symbol=${symbol}`);
}

/**
 * Get orders for an instance.
 */
export async function getInstanceOrders(
  instanceId: InstanceId
): Promise<ApiResponse<Order[]>> {
  const symbol = instanceId.replace(/_LONG|_SHORT/g, '');
  return apiFetch<Order[]>(`/api/orders?symbol=${symbol}`);
}

/**
 * Get grid configuration for an instance.
 */
export async function getInstanceGrid(
  instanceId: InstanceId
): Promise<ApiResponse<GridConfig>> {
  const symbol = instanceId.replace(/_LONG|_SHORT/g, '');
  return apiFetch<GridConfig>(`/api/config/flat?symbol=${symbol}`);
}

// ============================================================================
// TRADING ACTIONS
// ============================================================================

/**
 * Pause trading for an instance.
 */
export async function pauseInstanceTrading(
  instanceId: InstanceId
): Promise<ApiResponse<{ success: boolean }>> {
  const symbol = instanceId.replace(/_LONG|_SHORT/g, '');
  return apiFetch<{ success: boolean }>(
    `/api/symbols/${symbol}/process/stop`,
    { method: 'POST' }
  );
}

/**
 * Resume trading for an instance.
 */
export async function resumeInstanceTrading(
  instanceId: InstanceId
): Promise<ApiResponse<{ success: boolean }>> {
  const symbol = instanceId.replace(/_LONG|_SHORT/g, '');
  return apiFetch<{ success: boolean }>(
    `/api/symbols/${symbol}/process/start`,
    { method: 'POST' }
  );
}

/**
 * Emergency stop for an instance.
 */
export async function killInstanceTrading(
  instanceId: InstanceId
): Promise<ApiResponse<{ success: boolean }>> {
  const symbol = instanceId.replace(/_LONG|_SHORT/g, '');
  return apiFetch<{ success: boolean }>(
    `/api/symbols/${symbol}/process/stop`,
    { method: 'POST' }
  );
}

// ============================================================================
// GLOBAL ENDPOINTS
// ============================================================================

/**
 * Get system health status.
 */
export async function getSystemHealth(): Promise<
  ApiResponse<{
    backend: 'healthy' | 'degraded' | 'down';
    database: 'healthy' | 'degraded' | 'down';
    exchange: 'healthy' | 'degraded' | 'down';
  }>
> {
  // Use existing v1 health endpoint
  const response = await apiFetch<any>('/api/health');
  if (response.success) {
    return {
      ...response,
      data: {
        backend: response.data?.status === 'healthy' ? 'healthy' : 'degraded',
        database: 'healthy', // Assume healthy if backend responds
        exchange: response.data?.exchange_connected ? 'healthy' : 'degraded',
      },
    };
  }
  return {
    ...response,
    data: { backend: 'down', database: 'down', exchange: 'down' },
  };
}

/**
 * Emergency stop all trading.
 */
export async function killAllTrading(): Promise<
  ApiResponse<{ success: boolean; instancesStopped: number }>
> {
  return apiFetch('/api/symbols/all/stop', { method: 'POST' });
}

// ============================================================================
// DATA SYNC
// ============================================================================

/**
 * Perform full sync for an instance.
 * Fetches all data in parallel and returns unified result.
 */
export async function syncInstance(instanceId: InstanceId): Promise<{
  positions: ApiResponse<Position[]>;
  orders: ApiResponse<Order[]>;
  grid: ApiResponse<GridConfig>;
}> {
  const [positions, orders, grid] = await Promise.all([
    getInstancePositions(instanceId),
    getInstanceOrders(instanceId),
    getInstanceGrid(instanceId),
  ]);
  
  return { positions, orders, grid };
}
