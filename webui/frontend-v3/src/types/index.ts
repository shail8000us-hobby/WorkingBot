/**
 * GridBot WebUI v3.0 - Type Definitions
 * 
 * Copied from v2 and enhanced for v3.
 * Core principle: Every type answers "what can this be?"
 * No `any`, no implicit types, no magic strings.
 */

// ============================================================================
// INSTANCE IDENTITY
// ============================================================================

export type Symbol = 'BTCUSD' | 'ETHUSD' | 'SOLUSD' | string;
export type TradingMode = 'LONG' | 'SHORT';
export type InstanceId = `${Symbol}_${TradingMode}`;

export interface InstanceIdentity {
  instanceId: InstanceId;
  symbol: Symbol;
  mode: TradingMode;
  exchange: string;
  displayName: string;
}

// ============================================================================
// CONNECTION & HEALTH
// ============================================================================

export type ConnectionState = 
  | 'connected'      // WebSocket active, data fresh
  | 'connecting'     // Attempting connection
  | 'disconnected'   // Not connected, user-initiated
  | 'reconnecting'   // Auto-reconnect in progress
  | 'failed';        // Connection failed, manual retry needed

export type DataFreshness = 
  | 'fresh'          // < 2s old
  | 'aging'          // 2-5s old
  | 'stale'          // > 5s old
  | 'unknown';       // No data received yet

export interface HealthState {
  connection: ConnectionState;
  freshness: DataFreshness;
  lastUpdate: number | null;  // Unix timestamp
  lastError: string | null;
  reconnectAttempts: number;
}

// ============================================================================
// AUTHORITY LAYERS (Critical Concept)
// ============================================================================

/**
 * The three independent authorities that govern trading:
 * 
 * 1. HEARTBEAT - Technical permission
 *    "Is the system alive and functioning?"
 *    Controls: Process health, connectivity, data freshness
 * 
 * 2. GUARDIAN - Capital permission  
 *    "Is trading ALLOWED by risk rules?"
 *    Controls: Drawdown limits, exposure limits, circuit breakers
 * 
 * 3. TRADING - Strategic intent
 *    "What does the strategy WANT to do?"
 *    Controls: Grid placement, position sizing, market timing
 * 
 * KEY INSIGHT: "No trades" can mean three VERY different things:
 * - Heartbeat down → System broken → FIX IT
 * - Guardian blocking → Risk protection → WAIT or ACKNOWLEDGE
 * - Trading paused → Strategic choice → RESUME when ready
 */

export type HeartbeatStatus = 
  | 'alive'          // Process running, data flowing
  | 'stale'          // Process running but data old
  | 'dead';          // Process not responding

export type GuardianSignal = 
  | 'GO'             // Trading allowed
  | 'STOP'           // Trading forbidden (risk breach)
  | 'WARNING';       // Trading allowed but close to limits

export type TradingIntent = 
  | 'active'         // Strategy wants to trade
  | 'paused'         // Strategy paused by user
  | 'idle';          // Strategy has nothing to do (no signals)

export interface AuthorityState {
  heartbeat: {
    status: HeartbeatStatus;
    lastSeen: number | null;
    processId: string | null;
    reason: string | null;  // Why it's dead/stale
  };
  guardian: {
    signal: GuardianSignal;
    blockedBy: string | null;  // e.g., "Daily loss limit exceeded"
    blockedSince: number | null;
    riskLevel: RiskLevel;
  };
  trading: {
    intent: TradingIntent;
    pausedBy: 'user' | 'system' | null;
    pausedReason: string | null;
    lastAction: string | null;
    lastActionTime: number | null;
  };
}

/**
 * Computed: Who is actually in control right now?
 * This answers: "Why is nothing happening?"
 */
export type ControllingAuthority = 
  | 'heartbeat'      // System is down - nothing can happen
  | 'guardian'       // Risk says no - trading is forbidden
  | 'trading'        // Strategy decides - normal operation
  | 'user';          // User paused - manual override

// ============================================================================
// TRADING STATE
// ============================================================================

export type TradingState = 
  | 'active'         // Strategy running, placing orders
  | 'paused'         // Strategy paused by user
  | 'halted'         // Halted by risk system
  | 'error'          // Strategy in error state
  | 'initializing';  // Strategy starting up

export type GlobalTradingMode = 
  | 'LIVE'           // Real money
  | 'SIMULATION'     // Paper trading
  | 'READ_ONLY';     // View only, no actions

// ============================================================================
// POSITIONS & ORDERS
// ============================================================================

export interface Position {
  id?: string;  // Optional - API doesn't always provide this
  symbol: Symbol;
  side: 'LONG' | 'SHORT';
  size: number;
  quantity?: number;  // Alias for size
  entryPrice: number;
  entry_price?: number;  // API format
  currentPrice: number;
  current_price?: number;  // API format
  unrealizedPnl: number;
  unrealizedPnlPercent: number;
  openedAt: number;
  status?: 'OPEN' | 'CLOSED';
  // P&L fields (snake_case from API)
  profit_loss?: number;
  profit_loss_inr?: number;
  profit_loss_percent?: number;
  // v3: Additional fields from API
  delta?: number;
  vega?: number;
  theta?: number;
  notionalDeployed?: number;
}

export interface Order {
  id: string;
  clientOrderId?: string;
  symbol: Symbol;
  side: 'BUY' | 'SELL';
  type: 'LIMIT' | 'MARKET' | 'STOP';
  status: 'pending' | 'open' | 'filled' | 'cancelled' | 'rejected' | 'PENDING' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELLED';
  price: number;
  size: number;
  filledSize: number;
  remainingSize?: number;
  createdAt: number;
  updatedAt: number;
  reduceOnly?: boolean;
  postOnly?: boolean;
}

export interface PnL {
  realized: number;
  unrealized: number;
  total: number;
  todayRealized: number;
  todayUnrealized: number;
  todayTotal: number;
  // v3: INR conversion
  totalInr?: number;
  todayTotalInr?: number;
}

// ============================================================================
// GRID CONFIGURATION
// ============================================================================

export interface GridConfig {
  enabled: boolean;
  lowerPrice: number;
  upperPrice: number;
  gridStep: number;
  gridLevels: number;
  orderSize: number;
  currentPrice: number;
  filledLevels: number;
  pendingLevels: number;
  reference?: number;
}

export interface GridLevel {
  price: number;
  status: 'empty' | 'pending' | 'filled';
  orderId?: string;
  side: 'BUY' | 'SELL';
}

// ============================================================================
// RISK
// ============================================================================

export type RiskLevel = 'normal' | 'elevated' | 'high' | 'critical';

export interface RiskState {
  level: RiskLevel;
  exposure: number;
  maxExposure: number;
  exposurePercent: number;
  dailyLoss: number;
  maxDailyLoss: number;
  breaches: RiskBreach[];
}

export interface RiskBreach {
  type: 'exposure' | 'loss' | 'drawdown' | 'volatility';
  message: string;
  triggeredAt: number;
  acknowledged: boolean;
}

// ============================================================================
// SAFETY CHECKS (v3: New for Safety-First UI)
// ============================================================================

export interface SafetyCheck {
  name: string;
  passed: boolean;
  value: string | number;
  threshold?: string | number;
  description?: string;
}

export interface SafetyGateState {
  allPassed: boolean;
  checks: SafetyCheck[];
  lastChecked: number;
}

// ============================================================================
// BOT BRAIN (v3: New)
// ============================================================================

export interface BrainThought {
  id: string;
  timestamp: number;
  type: 'check' | 'decision' | 'action' | 'safety' | 'error' | 'analysis' | 'prediction' | 'warning' | 'observation';
  message?: string;  // Simple message format
  
  reasoning?: {
    observation: string;
    evaluation: string;
    conclusion: string;
    confidence: number;  // 0-100
    evidence: SafetyCheck[];
  };
  
  action?: {
    type: 'order' | 'cancel' | 'adjust' | 'skip';
    details: Record<string, unknown>;
    safetyChecks: SafetyCheck[];
  };
  
  data?: Record<string, unknown>;  // Additional data
}

// ============================================================================
// EVENTS & TIMELINE
// ============================================================================

export type EventSeverity = 'info' | 'warning' | 'error' | 'critical';

export interface TimelineEvent {
  id: string;
  timestamp: number;
  type: string;
  severity: EventSeverity;
  message: string;
  details?: Record<string, unknown>;
}

// ============================================================================
// INSTANCE STATE (Composite)
// ============================================================================

export interface InstanceState {
  identity: InstanceIdentity;
  health: HealthState;
  authority: AuthorityState;
  controlledBy: ControllingAuthority;
  tradingState: TradingState;
  positions: Position[];
  orders: Order[];
  pnl: PnL;
  grid: GridConfig | null;
  risk: RiskState;
  timeline: TimelineEvent[];
  lastFullSync: number | null;
}

// ============================================================================
// API CONTRACTS
// ============================================================================

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp?: number;
}

export interface InstanceConfig {
  id?: string;         // Instance ID (e.g., "BTCUSD_LONG")
  name: string;
  symbol: string;
  mode: TradingMode;
  enabled: boolean;
  productId: number;
  grid: {
    lower: number;
    upper: number;
    step: number;
    reference: number;
  };
  limits: {
    maxOpenPositions: number;
    lotSize: number;
    maxQtyPerOrder: number;
  };
  safety: {
    maxAccountLossInr: number;
    minLiquidationDistancePct: number;
  };
  rsi: {
    enabled: boolean;
    stopThreshold: number;
    resumeThreshold: number;
  };
}

// ============================================================================
// GUARDIAN API RESPONSE
// ============================================================================

export interface GuardianCheckResult {
  passed: boolean;
  value?: number;
  message?: string;
}

export interface GuardianStatusResponse {
  running: boolean;
  active?: boolean;  // Alias for running
  signal?: GuardianSignal;
  reason?: string;
  lastCheck?: number;
  loss_inr?: number;
  max_loss_inr?: number;
  positions?: number;
  blockers?: Array<{ name: string; reason: string }>;
  checks?: {
    rsi?: GuardianCheckResult;
    volatility?: GuardianCheckResult;
    margin?: GuardianCheckResult;
    drawdown?: GuardianCheckResult;
  };
  rsi?: {
    value: number;
    threshold: number;
    blocked: boolean;
  };
  volatility?: {
    iv: number;
    threshold: number;
    blocked: boolean;
  };
  margin?: {
    used: number;
    limit: number;
    blocked: boolean;
  };
}

// ============================================================================
// UI STATE
// ============================================================================

export type ViewMode = 'grid' | 'focus';
export type FocusMode = 'zen' | 'battle' | 'normal';

export interface UIState {
  viewMode: ViewMode;
  focusMode: FocusMode;
  focusedInstance: InstanceId | null;
  sidebarCollapsed: boolean;
  theme: 'light' | 'dark' | 'system';
  commandPaletteOpen: boolean;
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Derive the controlling authority from authority state.
 * Priority: Heartbeat > Guardian > Trading > User
 */
export function deriveControllingAuthority(authority: AuthorityState): ControllingAuthority {
  if (authority.heartbeat.status === 'dead') {
    return 'heartbeat';
  }
  
  if (authority.guardian.signal === 'STOP') {
    return 'guardian';
  }
  
  if (authority.trading.pausedBy === 'user') {
    return 'user';
  }
  
  return 'trading';
}

/**
 * Derive trading state from authority state.
 */
export function deriveTradingState(authority: AuthorityState): TradingState {
  if (authority.heartbeat.status === 'dead') return 'error';
  if (authority.guardian.signal === 'STOP') return 'halted';
  if (authority.trading.pausedBy === 'user') return 'paused';
  if (authority.trading.intent === 'active') return 'active';
  return 'initializing';
}

/**
 * Calculate data freshness based on age
 */
export function calculateFreshness(timestamp: number | null): DataFreshness {
  if (!timestamp) return 'unknown';
  const age = Date.now() - timestamp;
  if (age < 2000) return 'fresh';
  if (age < 5000) return 'aging';
  return 'stale';
}

/**
 * Format instance ID for display
 */
export function formatInstanceName(instanceId: InstanceId): string {
  const [symbol, mode] = instanceId.split('_');
  return `${symbol} ${mode}`;
}
