/**
 * GridBot WebUI v3 - API Client
 * 
 * Centralized API layer with error handling and type safety.
 * All API calls go through this module.
 */

import type { 
  ApiResponse, 
  Position, 
  Order, 
  PnL, 
  InstanceConfig,
  GuardianStatusResponse,
  BrainThought 
} from '@/types';

// API URL - must use NEXT_PUBLIC_ prefix to be available in client-side code
// This is embedded at BUILD time, so rebuild if you change .env.local
const API_URL = (typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
  : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5557')
).trim();

/**
 * Base fetch wrapper with error handling
 */
async function fetchApi<T>(
  endpoint: string, 
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = `${API_URL}${endpoint}`;
  
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      return {
        success: false,
        error: `HTTP ${response.status}: ${error}`,
        timestamp: Date.now(),
      };
    }

    const data = await response.json();
    return {
      success: true,
      data,
      timestamp: Date.now(),
    };
  } catch (error) {
    // Better error message handling for network errors
    let errorMessage = 'Network error';
    
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      // Network error - backend likely down, CORS issue, or network problem
      errorMessage = `Unable to connect to backend at ${API_URL}. Please check if the server is running and accessible.`;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }
    
    return {
      success: false,
      error: errorMessage,
      timestamp: Date.now(),
    };
  }
}

// ============================================================================
// INSTANCES API
// ============================================================================

export async function getInstances(): Promise<ApiResponse<InstanceConfig[]>> {
  const response = await fetchApi<{ instances: InstanceConfig[] }>('/api/instances/list');
  if (response.success && response.data) {
    return { ...response, data: response.data.instances };
  }
  return { success: false, error: response.error };
}

// ============================================================================
// POSITIONS API
// ============================================================================

interface PositionsResponse {
  positions: Position[];
  summary: {
    total_positions: number;
    total_pnl: number;
    total_pnl_usd: number;
    total_pnl_inr: number;
    portfolio_delta: number;
  };
}

export async function getPositions(instance?: string): Promise<ApiResponse<PositionsResponse>> {
  const params = instance ? `?instance=${instance}` : '';
  return fetchApi<PositionsResponse>(`/api/positions${params}`);
}

// ============================================================================
// ORDERS API
// ============================================================================

interface OrdersResponse {
  orders: Order[];
  total: number;
}

export async function getOrders(
  state: 'all' | 'open' | 'filled' | 'cancelled' = 'all',
  instance?: string
): Promise<ApiResponse<OrdersResponse>> {
  const params = new URLSearchParams({ state });
  if (instance) params.append('instance', instance);
  return fetchApi<OrdersResponse>(`/api/orders?${params}`);
}

// ============================================================================
// P&L API
// ============================================================================

interface PnLHistoryEntry {
  timestamp: string;
  time: string;
  total_pnl: number;
  unrealized_pnl: number;
  position_count: number;
}

export async function getPnLHistory(): Promise<ApiResponse<{ history: PnLHistoryEntry[] }>> {
  return fetchApi<{ history: PnLHistoryEntry[] }>('/api/pnl-history');
}

// ============================================================================
// GUARDIAN API
// ============================================================================

export async function getGuardianStatus(instance?: string): Promise<ApiResponse<GuardianStatusResponse>> {
  const params = instance ? `?instance=${instance}` : '';
  const response = await fetchApi<GuardianStatusResponse>(`/api/guardian/status${params}`);
  
  // Backend may return 500 error with {error, running, health} structure
  // Treat as successful response with error field
  if (!response.success && response.error?.includes('500')) {
    return {
      success: true,
      data: { 
        active: false, 
        running: false,
        lastCheck: undefined
      },
      timestamp: Date.now()
    };
  }
  
  return response;
}

export async function startGuardian(): Promise<ApiResponse<{ message: string }>> {
  return fetchApi<{ message: string }>('/api/guardian/start', { method: 'POST' });
}

export async function stopGuardian(): Promise<ApiResponse<{ message: string }>> {
  return fetchApi<{ message: string }>('/api/guardian/stop', { method: 'POST' });
}

// ============================================================================
// BOT CONTROL API
// ============================================================================

interface BotStatusResponse {
  running: boolean;
  pid?: number;
  pm2_managed?: boolean;
  uptime?: number;
}

export async function getBotStatus(instance?: string): Promise<ApiResponse<BotStatusResponse>> {
  const params = instance ? `?instance=${instance}` : '';
  return fetchApi<BotStatusResponse>(`/api/bot/status${params}`);
}

export async function startBot(): Promise<ApiResponse<{ message: string; pid?: number }>> {
  return fetchApi<{ message: string; pid?: number }>('/api/bot/start', { method: 'POST' });
}

export async function stopBot(): Promise<ApiResponse<{ message: string }>> {
  return fetchApi<{ message: string }>('/api/bot/stop', { method: 'POST' });
}

// ============================================================================
// TRADING STATUS API
// ============================================================================

export interface TradingStatusResponse {
  bot_running: boolean;
  trading_allowed: boolean;
  isPaused?: boolean;
  guardianActive?: boolean;
  blockers: Array<{ name: string; reason: string }>;
  total_blockers: number;
  positions: Position[];
  pending_orders: number;
  upnl_inr: number;
  rpnl_inr: number;
  net_pnl_inr: number;
}

export async function getTradingStatus(): Promise<ApiResponse<TradingStatusResponse>> {
  return fetchApi<TradingStatusResponse>('/api/trading_status');
}

export async function pauseTrading(instanceId?: string): Promise<ApiResponse<{ message: string }>> {
  const params = instanceId ? `?instance=${instanceId}` : '';
  return fetchApi<{ message: string }>(`/api/trading/pause${params}`, { method: 'POST' });
}

export async function resumeTrading(instanceId?: string): Promise<ApiResponse<{ message: string }>> {
  const params = instanceId ? `?instance=${instanceId}` : '';
  return fetchApi<{ message: string }>(`/api/trading/resume${params}`, { method: 'POST' });
}

// ============================================================================
// HEALTH API
// ============================================================================

interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: Record<string, { status: string; latency_ms?: number }>;
  uptime_seconds: number;
}

export async function getHealth(): Promise<ApiResponse<HealthResponse>> {
  return fetchApi<HealthResponse>('/api/health');
}

// ============================================================================
// BOT BRAIN API
// ============================================================================

interface BrainPredictResponse {
  success: boolean;
  predictions: {
    primary_prediction: {
      action: string;
      confidence: number;
      reasoning: string;
    };
    market_analysis: Record<string, unknown>;
    confidence_metrics: Record<string, number>;
    risk_factors: string[];
    monitoring_alerts: string[];
  };
  file_changes: Array<{
    file: string;
    change_type: string;
    impact_level: string;
  }>;
}

export async function getBrainPrediction(): Promise<ApiResponse<BrainPredictResponse>> {
  return fetchApi<BrainPredictResponse>('/api/brain/predict');
}

export async function getBrainScenarios(): Promise<ApiResponse<{
  scenarios: Record<string, unknown>;
  total_scenarios: number;
}>> {
  return fetchApi('/api/brain/master/scenarios');
}

// ============================================================================
// EMERGENCY API
// ============================================================================

export async function emergencyKillAll(instanceId?: string): Promise<ApiResponse<{ message: string; killed: number }>> {
  const params = instanceId ? `?instance=${instanceId}` : '';
  return fetchApi<{ message: string; killed: number }>(`/api/emergency/kill-all${params}`, { 
    method: 'POST' 
  });
}

export async function checkEmergencyFlag(): Promise<ApiResponse<{ exists: boolean; reason?: string }>> {
  return fetchApi<{ exists: boolean; reason?: string }>('/api/emergency/check_flag');
}

export async function clearEmergencyFlag(): Promise<ApiResponse<{ message: string }>> {
  return fetchApi<{ message: string }>('/api/emergency/clear_flag', { method: 'POST' });
}

// ============================================================================
// RISK API
// ============================================================================

interface RiskAnalyticsResponse {
  success: boolean;
  data: {
    var_95: number;
    cvar_95: number;
    sharpe_ratio: number;
    max_drawdown: number;
    volatility: number;
    grades: Record<string, string>;
  };
}

export async function getRiskAnalytics(): Promise<ApiResponse<RiskAnalyticsResponse>> {
  return fetchApi<RiskAnalyticsResponse>('/api/risk/analytics');
}

// ============================================================================
// CONFIG API
// ============================================================================

export async function getConfig(): Promise<ApiResponse<Record<string, unknown>>> {
  return fetchApi<Record<string, unknown>>('/api/config');
}

export async function updateConfig(config: Record<string, unknown>): Promise<ApiResponse<{ message: string }>> {
  return fetchApi<{ message: string }>('/api/config', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

// ============================================================================
// TRADING MODE API
// ============================================================================

export async function getTradingMode(): Promise<ApiResponse<{ mode: string; display?: any }>> {
  return fetchApi<{ mode: string; display?: any }>('/api/trading-mode');
}

export async function setTradingMode(mode: string): Promise<ApiResponse<{ message: string }>> {
  return fetchApi<{ message: string }>('/api/trading-mode', {
    method: 'POST',
    body: JSON.stringify({ mode }),
  });
}

// ============================================================================
// SYMBOLS API
// ============================================================================

export async function getSymbols(): Promise<ApiResponse<Array<{
  symbol: string;
  name: string;
  price?: number;
  change24h?: number;
  active?: boolean;
}>>> {
  return fetchApi<Array<{
    symbol: string;
    name: string;
    price?: number;
    change24h?: number;
    active?: boolean;
  }>>('/api/symbols');
}

// ============================================================================
// VOLATILITY API
// ============================================================================

export async function getVolatilitySignal(): Promise<ApiResponse<{
  volatility_signal: {
    value: string;
    color: string;
    iv: number;
    rv: number;
    spread: number;
  };
  market_regime: {
    value: string;
    risk: string;
    color: string;
    rv: number;
  };
  overall_risk_status: {
    value: string;
    score: number;
    color: string;
  };
  grid_suitability: {
    rating: string;
    score: number;
    score_max: number;
    color: string;
  };
}>> {
  const url = `${API_URL}/api/volatility/signal`;
  try {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      const error = await response.text();
      return {
        success: false,
        error: `HTTP ${response.status}: ${error}`,
        timestamp: Date.now(),
      };
    }
    const apiResponse = await response.json();
    // API returns {success, data}, unwrap it
    if (apiResponse.success && apiResponse.data) {
      return {
        success: true,
        data: apiResponse.data,
        timestamp: Date.now(),
      };
    }
    return {
      success: false,
      error: 'Invalid response format',
      timestamp: Date.now(),
    };
  } catch (error) {
    // Better error message handling for network errors
    let errorMessage = 'Network error';
    
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      // Network error - backend likely down, CORS issue, or network problem
      errorMessage = `Unable to connect to backend at ${API_URL}. Please check if the server is running and accessible.`;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }
    
    return {
      success: false,
      error: errorMessage,
      timestamp: Date.now(),
    };
  }
}

// ============================================================================
// SYSTEM HEALTH API
// ============================================================================

export async function getHealthDetailed(): Promise<ApiResponse<{
  status: string;
  uptime: {
    formatted: string;
    seconds: number;
  };
  version: string;
  resources: {
    cpu: {
      percent: number;
      cores: number;
      healthy: boolean;
    };
    memory: {
      percent_used: number;
      total_gb: number;
      used_gb: number;
      available_gb: number;
      healthy: boolean;
    };
    disk: {
      percent_used: number;
      total_gb: number;
      used_gb: number;
      free_gb: number;
      healthy: boolean;
    };
  };
  services: {
    trading_bot: {
      status: string;
      healthy: boolean;
    };
    guardian_bot: {
      status: string;
      healthy: boolean;
    };
  };
  dependencies?: Record<string, any>;
  circuit_breakers?: Record<string, any>;
}>> {
  const url = `${API_URL}/api/health/detailed`;
  try {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      const error = await response.text();
      return {
        success: false,
        error: `HTTP ${response.status}: ${error}`,
        timestamp: Date.now(),
      };
    }
    const apiResponse = await response.json();
    // API returns {success, data}, unwrap it
    if (apiResponse.success && apiResponse.data) {
      return {
        success: true,
        data: apiResponse.data,
        timestamp: Date.now(),
      };
    }
    return {
      success: false,
      error: 'Invalid response format',
      timestamp: Date.now(),
    };
  } catch (error) {
    // Better error message handling for network errors
    let errorMessage = 'Network error';
    
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      // Network error - backend likely down, CORS issue, or network problem
      errorMessage = `Unable to connect to backend at ${API_URL}. Please check if the server is running and accessible.`;
    } else if (error instanceof Error) {
      errorMessage = error.message;
    }
    
    return {
      success: false,
      error: errorMessage,
      timestamp: Date.now(),
    };
  }
}

export async function getSystemHealth(): Promise<ApiResponse<{
  overall_health: string;
  status: string;
  summary: {
    system: {
      cpu_percent: number;
      memory_percent: number;
      disk_percent: number;
      timestamp: string | null;
    };
    processes: {
      total: number;
      running: number;
      crashed: number;
    };
    apis: {
      total: number;
      up: number;
      down: number;
    };
    alerts: {
      total: number;
      warning: number;
      critical: number;
    };
  };
}>> {
  return fetchApi<{
    overall_health: string;
    status: string;
    summary: {
      system: {
        cpu_percent: number;
        memory_percent: number;
        disk_percent: number;
        timestamp: string | null;
      };
      processes: {
        total: number;
        running: number;
        crashed: number;
      };
      apis: {
        total: number;
        up: number;
        down: number;
      };
      alerts: {
        total: number;
        warning: number;
        critical: number;
      };
    };
  }>('/api/system-health/summary');
}
