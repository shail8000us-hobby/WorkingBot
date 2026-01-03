/**
 * GridBot WebUI v2.0 - Type Definitions
 * 
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

export type GuardianStatus = 
  | 'permitting'     // Trading allowed
  | 'blocking'       // Trading forbidden (risk breach)
  | 'warning';       // Trading allowed but close to limits

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
    status: GuardianStatus;
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
// TRADING STATE (Legacy - kept for compatibility)
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
  id: string;
  symbol: Symbol;
  side: 'LONG' | 'SHORT';
  size: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnl: number;
  unrealizedPnlPercent: number;
  openedAt: number;
}

export interface Order {
  id: string;
  symbol: Symbol;
  side: 'BUY' | 'SELL';
  type: 'LIMIT' | 'MARKET' | 'STOP';
  status: 'pending' | 'open' | 'filled' | 'cancelled' | 'rejected';
  price: number;
  size: number;
  filledSize: number;
  createdAt: number;
  updatedAt: number;
}

export interface PnL {
  realized: number;
  unrealized: number;
  total: number;
  todayRealized: number;
  todayUnrealized: number;
  todayTotal: number;
}

// ============================================================================
// GRID CONFIGURATION
// ============================================================================

export interface GridConfig {
  enabled: boolean;
  lowerPrice: number;
  upperPrice: number;
  gridLevels: number;
  orderSize: number;
  currentPrice: number;
  filledLevels: number;
  pendingLevels: number;
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
// INSTRUMENT STATE (Composite)
// ============================================================================

export interface InstrumentState {
  identity: InstanceIdentity;
  health: HealthState;
  
  // NEW: Authority layers - the three decision makers
  authority: AuthorityState;
  controlledBy: ControllingAuthority;  // Who is actually in charge right now?
  
  // Legacy field - derived from authority state
  tradingState: TradingState;
  
  positions: Position[];
  orders: Order[];
  pnl: PnL;
  grid: GridConfig | null;
  risk: RiskState;
  timeline: TimelineEvent[];
  
  // Metadata
  lastFullSync: number | null;
  partialDataFlags: {
    positions: boolean;
    orders: boolean;
    pnl: boolean;
    grid: boolean;
  };
}

/**
 * Derive the controlling authority from authority state.
 * Priority: Heartbeat > Guardian > Trading > User
 */
export function deriveControllingAuthority(authority: AuthorityState): ControllingAuthority {
  // Heartbeat has highest priority - if system is dead, nothing else matters
  if (authority.heartbeat.status === 'dead') {
    return 'heartbeat';
  }
  
  // Guardian comes next - if risk says no, strategy can't trade
  if (authority.guardian.status === 'blocking') {
    return 'guardian';
  }
  
  // User pause takes precedence over strategy
  if (authority.trading.pausedBy === 'user') {
    return 'user';
  }
  
  // Normal operation - trading strategy is in control
  return 'trading';
}

/**
 * Derive legacy tradingState from authority state.
 */
export function deriveTradingState(authority: AuthorityState): TradingState {
  if (authority.heartbeat.status === 'dead') return 'error';
  if (authority.guardian.status === 'blocking') return 'halted';
  if (authority.trading.pausedBy === 'user') return 'paused';
  if (authority.trading.intent === 'active') return 'active';
  return 'initializing';
}

// ============================================================================
// GLOBAL STATE
// ============================================================================

export interface GlobalState {
  tradingMode: GlobalTradingMode;
  instances: InstanceId[];
  systemHealth: {
    backend: 'healthy' | 'degraded' | 'down';
    database: 'healthy' | 'degraded' | 'down';
    exchange: 'healthy' | 'degraded' | 'down';
  };
  alerts: Alert[];
  lastHealthCheck: number;
}

export interface Alert {
  id: string;
  severity: EventSeverity;
  message: string;
  instanceId?: InstanceId;  // null = global alert
  createdAt: number;
  acknowledged: boolean;
}

// ============================================================================
// API CONTRACTS
// ============================================================================

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  timestamp: number;
  staleAfterMs: number;
  error?: {
    code: string;
    message: string;
  };
}

export interface WebSocketMessage<T = unknown> {
  channel: string;
  sequence: number;
  timestamp: number;
  staleAfterMs: number;
  data: T;
}

// ============================================================================
// UI STATE
// ============================================================================

export type ViewMode = 'grid' | 'focus';

export interface UIState {
  viewMode: ViewMode;
  focusedInstance: InstanceId | null;
  sidebarCollapsed: boolean;
  theme: 'light' | 'dark' | 'system';
  confirmDialogOpen: boolean;
  pendingAction: PendingAction | null;
}

export interface PendingAction {
  type: 'pause' | 'resume' | 'kill' | 'kill-all';
  instanceId?: InstanceId;
  requiresHold: boolean;
  holdDuration: number;  // ms
}
