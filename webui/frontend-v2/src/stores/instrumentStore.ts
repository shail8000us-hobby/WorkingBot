/**
 * Instrument Store Factory
 * 
 * Creates isolated Zustand stores per instrument.
 * Each store is completely independent - one instrument's
 * failure cannot affect another's state.
 */

import { create, StateCreator } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type {
  InstanceId,
  InstrumentState,
  HealthState,
  TradingState,
  Position,
  Order,
  PnL,
  GridConfig,
  RiskState,
  TimelineEvent,
  ConnectionState,
  DataFreshness,
  AuthorityState,
  ControllingAuthority,
  HeartbeatStatus,
  GuardianStatus,
  TradingIntent,
} from '../types';
import { deriveControllingAuthority, deriveTradingState } from '../types';

// ============================================================================
// DEFAULT STATES
// ============================================================================

const defaultHealth: HealthState = {
  connection: 'disconnected',
  freshness: 'unknown',
  lastUpdate: null,
  lastError: null,
  reconnectAttempts: 0,
};

const defaultAuthority: AuthorityState = {
  heartbeat: {
    status: 'dead',
    lastSeen: null,
    processId: null,
    reason: 'Waiting for first heartbeat',
  },
  guardian: {
    status: 'permitting',
    blockedBy: null,
    blockedSince: null,
    riskLevel: 'normal',
  },
  trading: {
    intent: 'idle',
    pausedBy: null,
    pausedReason: null,
    lastAction: null,
    lastActionTime: null,
  },
};

const defaultPnL: PnL = {
  realized: 0,
  unrealized: 0,
  total: 0,
  todayRealized: 0,
  todayUnrealized: 0,
  todayTotal: 0,
};

const defaultRisk: RiskState = {
  level: 'normal',
  exposure: 0,
  maxExposure: 0,
  exposurePercent: 0,
  dailyLoss: 0,
  maxDailyLoss: 0,
  breaches: [],
};

// ============================================================================
// STORE ACTIONS INTERFACE
// ============================================================================

interface InstrumentActions {
  // Connection
  setConnectionState: (state: ConnectionState) => void;
  updateFreshness: () => void;
  recordError: (error: string) => void;
  clearError: () => void;
  
  // Authority updates (NEW)
  updateHeartbeat: (status: HeartbeatStatus, reason?: string) => void;
  updateGuardian: (status: GuardianStatus, blockedBy?: string) => void;
  updateTradingIntent: (intent: TradingIntent) => void;
  
  // Trading
  setTradingState: (state: TradingState) => void;
  pauseTrading: () => Promise<boolean>;
  resumeTrading: () => Promise<boolean>;
  killTrading: () => Promise<boolean>;
  
  // Data updates
  updatePositions: (positions: Position[]) => void;
  updateOrders: (orders: Order[]) => void;
  updatePnL: (pnl: Partial<PnL>) => void;
  updateGrid: (grid: GridConfig | null) => void;
  updateRisk: (risk: Partial<RiskState>) => void;
  addTimelineEvent: (event: TimelineEvent) => void;
  
  // Bulk update
  fullSync: (data: Partial<InstrumentState>) => void;
  
  // Partial data tracking
  markDataLoaded: (key: keyof InstrumentState['partialDataFlags']) => void;
  markDataFailed: (key: keyof InstrumentState['partialDataFlags']) => void;
  
  // Reset
  reset: () => void;
}

type InstrumentStore = InstrumentState & InstrumentActions;

// ============================================================================
// STORE FACTORY
// ============================================================================

const createInstrumentStore = (instanceId: InstanceId) => {
  // Parse instance ID
  const [symbol, mode] = instanceId.split('_') as [string, 'LONG' | 'SHORT'];
  
  const initialState: InstrumentState = {
    identity: {
      instanceId,
      symbol,
      mode,
      exchange: 'deribit', // TODO: Make configurable
      displayName: `${symbol} ${mode}`,
    },
    health: { ...defaultHealth },
    
    // Authority state (NEW)
    authority: { ...defaultAuthority },
    controlledBy: 'heartbeat',  // Start assuming system is down
    
    tradingState: 'initializing',
    positions: [],
    orders: [],
    pnl: { ...defaultPnL },
    grid: null,
    risk: { ...defaultRisk },
    timeline: [],
    lastFullSync: null,
    partialDataFlags: {
      positions: false,
      orders: false,
      pnl: false,
      grid: false,
    },
  };

  const storeCreator: StateCreator<InstrumentStore> = (set, get) => ({
    ...initialState,
    
    // === Connection ===
    setConnectionState: (connection: ConnectionState) => {
      set((state) => ({
        health: {
          ...state.health,
          connection,
          reconnectAttempts: connection === 'reconnecting' 
            ? state.health.reconnectAttempts + 1 
            : connection === 'connected' 
              ? 0 
              : state.health.reconnectAttempts,
        },
      }));
    },
    
    updateFreshness: () => {
      const lastUpdate = get().health.lastUpdate;
      if (!lastUpdate) {
        set((state) => ({
          health: { ...state.health, freshness: 'unknown' },
        }));
        return;
      }
      
      const age = Date.now() - lastUpdate;
      let freshness: DataFreshness;
      
      if (age < 2000) freshness = 'fresh';
      else if (age < 5000) freshness = 'aging';
      else freshness = 'stale';
      
      set((state) => ({
        health: { ...state.health, freshness },
      }));
    },
    
    recordError: (error: string) => {
      set((state) => ({
        health: { ...state.health, lastError: error },
      }));
      get().addTimelineEvent({
        id: `error-${Date.now()}`,
        timestamp: Date.now(),
        type: 'error',
        severity: 'error',
        message: error,
      });
    },
    
    clearError: () => {
      set((state) => ({
        health: { ...state.health, lastError: null },
      }));
    },
    
    // === Authority Updates (NEW) ===
    updateHeartbeat: (status: HeartbeatStatus, reason?: string) => {
      set((state) => {
        const newAuthority = {
          ...state.authority,
          heartbeat: {
            ...state.authority.heartbeat,
            status,
            lastSeen: status === 'alive' ? Date.now() : state.authority.heartbeat.lastSeen,
            reason: reason || null,
          },
        };
        return {
          authority: newAuthority,
          controlledBy: deriveControllingAuthority(newAuthority),
          tradingState: deriveTradingState(newAuthority),
        };
      });
    },
    
    updateGuardian: (status: GuardianStatus, blockedBy?: string) => {
      set((state) => {
        const newAuthority = {
          ...state.authority,
          guardian: {
            ...state.authority.guardian,
            status,
            blockedBy: blockedBy || null,
            blockedSince: status === 'blocking' ? Date.now() : null,
          },
        };
        return {
          authority: newAuthority,
          controlledBy: deriveControllingAuthority(newAuthority),
          tradingState: deriveTradingState(newAuthority),
        };
      });
    },
    
    updateTradingIntent: (intent: TradingIntent) => {
      set((state) => {
        const newAuthority = {
          ...state.authority,
          trading: {
            ...state.authority.trading,
            intent,
          },
        };
        return {
          authority: newAuthority,
          controlledBy: deriveControllingAuthority(newAuthority),
          tradingState: deriveTradingState(newAuthority),
        };
      });
    },
    
    // === Trading ===
    setTradingState: (tradingState: TradingState) => {
      set({ tradingState });
    },
    
    pauseTrading: async () => {
      const { instanceId } = get().identity;
      try {
        const response = await fetch(`/api/v2/instances/${instanceId}/trading/pause`, {
          method: 'POST',
        });
        if (response.ok) {
          // Update authority state - user paused
          set((state) => {
            const newAuthority = {
              ...state.authority,
              trading: {
                ...state.authority.trading,
                intent: 'paused' as TradingIntent,
                pausedBy: 'user' as const,
                pausedReason: 'Paused by user',
              },
            };
            return {
              authority: newAuthority,
              controlledBy: 'user' as ControllingAuthority,
              tradingState: 'paused' as TradingState,
            };
          });
          get().addTimelineEvent({
            id: `pause-${Date.now()}`,
            timestamp: Date.now(),
            type: 'trading_paused',
            severity: 'warning',
            message: 'Trading paused by user',
          });
          return true;
        }
        return false;
      } catch (error) {
        get().recordError(`Failed to pause trading: ${error}`);
        return false;
      }
    },
    
    resumeTrading: async () => {
      const { instanceId } = get().identity;
      try {
        const response = await fetch(`/api/v2/instances/${instanceId}/trading/resume`, {
          method: 'POST',
        });
        if (response.ok) {
          // Update authority state - user resumed
          set((state) => {
            const newAuthority = {
              ...state.authority,
              trading: {
                ...state.authority.trading,
                intent: 'active' as TradingIntent,
                pausedBy: null,
                pausedReason: null,
              },
            };
            return {
              authority: newAuthority,
              controlledBy: deriveControllingAuthority(newAuthority),
              tradingState: deriveTradingState(newAuthority),
            };
          });
          get().addTimelineEvent({
            id: `resume-${Date.now()}`,
            timestamp: Date.now(),
            type: 'trading_resumed',
            severity: 'info',
            message: 'Trading resumed by user',
          });
          return true;
        }
        return false;
      } catch (error) {
        get().recordError(`Failed to resume trading: ${error}`);
        return false;
      }
    },
    
    killTrading: async () => {
      const { instanceId } = get().identity;
      try {
        const response = await fetch(`/api/v2/instances/${instanceId}/trading/kill`, {
          method: 'POST',
        });
        if (response.ok) {
          set({ tradingState: 'halted' });
          get().addTimelineEvent({
            id: `kill-${Date.now()}`,
            timestamp: Date.now(),
            type: 'trading_killed',
            severity: 'critical',
            message: 'Trading killed by user - EMERGENCY STOP',
          });
          return true;
        }
        return false;
      } catch (error) {
        get().recordError(`Failed to kill trading: ${error}`);
        return false;
      }
    },
    
    // === Data Updates ===
    updatePositions: (positions: Position[]) => {
      set((state) => ({
        positions,
        health: { ...state.health, lastUpdate: Date.now(), freshness: 'fresh' },
        partialDataFlags: { ...state.partialDataFlags, positions: true },
      }));
    },
    
    updateOrders: (orders: Order[]) => {
      set((state) => ({
        orders,
        health: { ...state.health, lastUpdate: Date.now(), freshness: 'fresh' },
        partialDataFlags: { ...state.partialDataFlags, orders: true },
      }));
    },
    
    updatePnL: (pnl: Partial<PnL>) => {
      set((state) => ({
        pnl: { ...state.pnl, ...pnl },
        health: { ...state.health, lastUpdate: Date.now(), freshness: 'fresh' },
        partialDataFlags: { ...state.partialDataFlags, pnl: true },
      }));
    },
    
    updateGrid: (grid: GridConfig | null) => {
      set((state) => ({
        grid,
        health: { ...state.health, lastUpdate: Date.now(), freshness: 'fresh' },
        partialDataFlags: { ...state.partialDataFlags, grid: true },
      }));
    },
    
    updateRisk: (risk: Partial<RiskState>) => {
      set((state) => ({
        risk: { ...state.risk, ...risk },
      }));
    },
    
    addTimelineEvent: (event: TimelineEvent) => {
      set((state) => ({
        timeline: [event, ...state.timeline].slice(0, 100), // Keep last 100 events
      }));
    },
    
    fullSync: (data: Partial<InstrumentState>) => {
      set((state) => ({
        ...state,
        ...data,
        lastFullSync: Date.now(),
        health: {
          ...state.health,
          lastUpdate: Date.now(),
          freshness: 'fresh',
        },
      }));
    },
    
    markDataLoaded: (key) => {
      set((state) => ({
        partialDataFlags: { ...state.partialDataFlags, [key]: true },
      }));
    },
    
    markDataFailed: (key) => {
      set((state) => ({
        partialDataFlags: { ...state.partialDataFlags, [key]: false },
      }));
    },
    
    reset: () => {
      set(initialState);
    },
  });

  return create<InstrumentStore>()(
    subscribeWithSelector(storeCreator)
  );
};

// ============================================================================
// STORE REGISTRY
// ============================================================================

type StoreType = ReturnType<typeof createInstrumentStore>;

const instrumentStores = new Map<InstanceId, StoreType>();

/**
 * Get or create a store for an instrument.
 * Stores are cached and reused.
 */
export const getInstrumentStore = (instanceId: InstanceId): StoreType => {
  if (!instrumentStores.has(instanceId)) {
    console.log(`[StoreRegistry] Creating store for ${instanceId}`);
    instrumentStores.set(instanceId, createInstrumentStore(instanceId));
  }
  return instrumentStores.get(instanceId)!;
};

/**
 * Destroy a store when instrument is removed.
 * Cleans up subscriptions and memory.
 */
export const destroyInstrumentStore = (instanceId: InstanceId): void => {
  const store = instrumentStores.get(instanceId);
  if (store) {
    store.getState().reset();
    instrumentStores.delete(instanceId);
    console.log(`[StoreRegistry] Destroyed store for ${instanceId}`);
  }
};

/**
 * Get all active instrument stores.
 */
export const getAllInstrumentStores = (): Map<InstanceId, StoreType> => {
  return new Map(instrumentStores);
};

/**
 * Check if a store exists.
 */
export const hasInstrumentStore = (instanceId: InstanceId): boolean => {
  return instrumentStores.has(instanceId);
};

// ============================================================================
// CUSTOM HOOK FOR COMPONENTS
// ============================================================================

/**
 * Hook to use an instrument store in a component.
 * Automatically handles store creation and provides type safety.
 * 
 * Usage:
 * const { positions, pnl, pauseTrading } = useInstrumentStore('BTCUSD_LONG');
 */
export const useInstrumentStore = <T>(
  instanceId: InstanceId,
  selector: (state: InstrumentStore) => T
): T => {
  const store = getInstrumentStore(instanceId);
  return store(selector);
};

/**
 * Hook to use entire instrument state.
 * Use sparingly - prefer selecting specific fields.
 */
export const useFullInstrumentState = (instanceId: InstanceId): InstrumentStore => {
  const store = getInstrumentStore(instanceId);
  return store((state) => state);
};

export type { InstrumentStore };
