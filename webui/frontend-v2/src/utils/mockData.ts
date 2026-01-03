/**
 * Mock Data Providers
 * 
 * Provides fallback data when backend endpoints are unavailable.
 * Ensures UI displays gracefully even without backend support.
 */

export const mockGuardianStatus = {
  success: true,
  running: true,
  guardian_active: true,
  status: "MONITORING",
  total_pnl: 0,
  loss_limit: -7500,
  uptime: 86400,
  auto_restart: true,
  restart_count: 0,
  global: {
    risk_status: 'SAFE',
    total_positions: 0
  },
  checks: [
    { name: 'Guardian Running', status: 'pass' as const, message: 'Active', lastRun: new Date().toISOString() },
    { name: 'Risk Status', status: 'pass' as const, message: 'SAFE', lastRun: new Date().toISOString() },
    { name: 'Total Positions', status: 'pass' as const, message: '0 open', lastRun: new Date().toISOString() }
  ],
  circuit_breakers: [
    { name: 'API Rate Limit', status: 'closed' as const, failures: 0 },
    { name: 'Order Placement', status: 'closed' as const, failures: 0 },
    { name: 'Position Sync', status: 'closed' as const, failures: 0 }
  ],
  metrics: { totalChecks: 0, failedChecks: 0, avgResponseTime: 0 },
  last_check: new Date().toISOString(),
  message: "Guardian monitoring active - No backend data"
};

export const mockRSIStatus = {
  success: true,
  rsi_enabled: false,
  current_rsi: null,
  stop_threshold: 35,
  resume_threshold: 25,
  trading_allowed: true,
  status: "RSI monitoring not configured",
  symbols: {},
  message: "Backend endpoint not available"
};

export const mockPredictiveMap = {
  success: true,
  current_state: {},
  predictions: [],
  confidence: 0,
  next_levels: [],
  next_actions: [],
  last_decisions: [],
  data: {
    next_actions: [],
    last_decisions: []
  },
  message: "Predictive analytics service unavailable"
};

export const mockPreOrderStats = {
  success: true,
  pending_buys: 0,
  stats: {
    pending_orders: 0,
    avg_fill_time: 0,
    success_rate: 0
  },
  data: {
    pending_buys: 0,
    pending_sells: 0,
    total_pending_value: 0,
    oldest_order_age: 0,
    avg_fill_time: 0
  },
  message: "Pre-order stats service unavailable"
};

export const mockTPVerification = {
  success: true,
  verified: 0,
  unverified: 0,
  collisions: 0,
  tp_count_24h: 0,
  data: {
    tp_count_24h: 0,
    verified_tp_count: 0,
    collisions: 0
  },
  message: "TP verification service unavailable"
};

export const mockAnomalies = {
  success: true,
  anomalies: [],
  count: 0,
  data: {
    anomalies: [],
    count: 0
  },
  message: "Anomaly detection service unavailable"
};

export const mockPriceHealth = {
  success: true,
  current_price: 0,
  health_score: 0,
  grid_alignment: 0,
  price_position: "unknown",
  missed_levels: [],
  data: {
    current_price: 0,
    last_update: new Date().toISOString(),
    price_age_seconds: 0,
    is_stale: false,
    spread_percent: 0,
    volatility_1h: 0
  },
  message: "Price health service unavailable"
};

export const mockVolatilityStatus = {
  success: true,
  enabled: false,
  iv: null,
  rv: null,
  safe: true,
  status: "Volatility monitoring not configured",
  history: [],
  current: null,
  summary: null,
  data: {
    history: []
  },
  message: "Backend endpoint not available"
};

export const mockBrainFlowchart = {
  success: true,
  nodes: [
    {
      id: "start",
      type: "start",
      data: { label: "Bot Offline" },
      position: { x: 0, y: 0 },
      realtime_data: { status: "No backend connection" }
    }
  ],
  edges: [],
  graph: {
    nodes: [
      {
        id: "start",
        type: "start",
        data: { label: "Bot Offline" },
        position: { x: 0, y: 0 },
        realtime_data: { status: "No backend connection" }
      }
    ],
    edges: [],
    total_nodes: 1,
    total_edges: 0,
    layout: "dagre",
    metadata: {
      decision_points: 0,
      action_points: 0,
      safety_checks: 0,
      error_handlers: 0
    }
  },
  bot_state: {},
  brain_scan: {
    files_scanned: 0,
    total_lines: 0,
    scan_timestamp: Date.now() / 1000
  }
};

/**
 * Check if error is a backend unavailability issue
 */
export function isBackendUnavailable(error: any): boolean {
  if (!error) return false;
  
  const errorString = error.toString().toLowerCase();
  const status = error.status || error.response?.status;
  
  return (
    status === 404 ||
    status === 500 ||
    status === 503 ||
    errorString.includes('network error') ||
    errorString.includes('failed to fetch') ||
    errorString.includes('unexpected token')
  );
}

/**
 * Wrap fetch call with mock data fallback
 */
export async function fetchWithMock<T>(
  url: string,
  mockData: T,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(url, options);
    
    if (!response.ok) {
      console.warn(`[Mock Fallback] ${url} returned ${response.status}, using mock data`);
      return mockData;
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.warn(`[Mock Fallback] ${url} failed, using mock data:`, error);
    return mockData;
  }
}
