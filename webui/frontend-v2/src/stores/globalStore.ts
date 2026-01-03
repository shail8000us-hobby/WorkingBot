/**
 * Global Store
 * 
 * Manages system-wide state that is NOT instrument-specific.
 * This store is intentionally minimal - most state lives in instrument stores.
 */

import { create } from 'zustand';
import { subscribeWithSelector, persist } from 'zustand/middleware';
import type {
  InstanceId,
  GlobalTradingMode,
  Alert,
  ViewMode,
} from '../types';

// ============================================================================
// GLOBAL STATE INTERFACE
// ============================================================================

interface SystemHealth {
  backend: 'healthy' | 'degraded' | 'down';
  database: 'healthy' | 'degraded' | 'down';
  exchange: 'healthy' | 'degraded' | 'down';
  lastCheck: number;
}

// Instance-specific data stored by the DataAggregator
interface InstanceData {
  positions?: any[];
  positionsSummary?: any;
  orders?: any[];
  guardianStatus?: {
    running: boolean;
    active: boolean;
    riskStatus: string;
    totalLossInr: number;
    totalPositions: number;
    lastCheck?: string;
  };
  botStatus?: {
    running: boolean;
    status: string;
    uptime: number;
    pid?: number;
  };
  monitoringData?: any;
  pnl?: any;
  lastPositionsUpdate?: number;
  lastOrdersUpdate?: number;
  lastGuardianUpdate?: number;
  lastBotStatusUpdate?: number;
  lastMonitoringUpdate?: number;
  lastPnlUpdate?: number;
}

interface GlobalState {
  // Trading mode
  tradingMode: GlobalTradingMode;
  
  // Registered instruments
  instances: InstanceId[];
  
  // Instance data (keyed by instance ID)
  instanceData: Record<string, InstanceData>;
  
  // System health
  systemHealth: SystemHealth;
  
  // Global alerts
  alerts: Alert[];
  
  // UI state
  viewMode: ViewMode;
  focusedInstance: InstanceId | null;
  sidebarCollapsed: boolean;
  
  // User preferences (persisted)
  theme: 'light' | 'dark' | 'system';
  compactMode: boolean;
}

interface GlobalActions {
  // Trading mode
  setTradingMode: (mode: GlobalTradingMode) => void;
  
  // Instance management
  registerInstance: (instanceId: InstanceId) => void;
  unregisterInstance: (instanceId: InstanceId) => void;
  setInstances: (instances: InstanceId[]) => void;
  
  // Instance data (from DataAggregator)
  updateInstanceData: (instanceId: string, data: Partial<InstanceData>) => void;
  getInstanceData: (instanceId: string) => InstanceData | undefined;
  
  // System health
  updateSystemHealth: (health: Partial<SystemHealth>) => void;
  
  // Alerts
  addAlert: (alert: Omit<Alert, 'id' | 'createdAt'>) => void;
  acknowledgeAlert: (alertId: string) => void;
  dismissAlert: (alertId: string) => void;
  clearAllAlerts: () => void;
  
  // UI
  setViewMode: (mode: ViewMode) => void;
  focusInstance: (instanceId: InstanceId) => void;
  unfocusInstance: () => void;
  toggleSidebar: () => void;
  
  // Preferences
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  setCompactMode: (compact: boolean) => void;
  
  // Emergency
  killAllTrading: () => Promise<boolean>;
}

type GlobalStore = GlobalState & GlobalActions;

// ============================================================================
// STORE IMPLEMENTATION
// ============================================================================

export const useGlobalStore = create<GlobalStore>()(
  subscribeWithSelector(
    persist(
      (set, get) => ({
        // === Initial State ===
        tradingMode: 'READ_ONLY',
        instances: [],
        instanceData: {},
        systemHealth: {
          backend: 'down',
          database: 'down',
          exchange: 'down',
          lastCheck: 0,
        },
        alerts: [],
        viewMode: 'grid',
        focusedInstance: null,
        sidebarCollapsed: false,
        theme: 'dark',
        compactMode: false,
        
        // === Trading Mode ===
        setTradingMode: (mode) => {
          set({ tradingMode: mode });
          get().addAlert({
            severity: mode === 'LIVE' ? 'warning' : 'info',
            message: `Trading mode changed to ${mode}`,
            acknowledged: false,
          });
        },
        
        // === Instance Management ===
        registerInstance: (instanceId) => {
          set((state) => {
            if (state.instances.includes(instanceId)) return state;
            return { instances: [...state.instances, instanceId] };
          });
        },
        
        unregisterInstance: (instanceId) => {
          set((state) => ({
            instances: state.instances.filter((id) => id !== instanceId),
            focusedInstance: state.focusedInstance === instanceId 
              ? null 
              : state.focusedInstance,
          }));
        },
        
        setInstances: (instances) => {
          set({ instances });
        },
        
        // === Instance Data ===
        updateInstanceData: (instanceId, data) => {
          set((state) => ({
            instanceData: {
              ...state.instanceData,
              [instanceId]: {
                ...state.instanceData[instanceId],
                ...data,
              },
            },
          }));
        },
        
        getInstanceData: (instanceId) => {
          return get().instanceData[instanceId];
        },
        
        // === System Health ===
        updateSystemHealth: (health) => {
          set((state) => ({
            systemHealth: {
              ...state.systemHealth,
              ...health,
              lastCheck: Date.now(),
            },
          }));
        },
        
        // === Alerts ===
        addAlert: (alert) => {
          const newAlert: Alert = {
            ...alert,
            id: `alert-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            createdAt: Date.now(),
          };
          set((state) => ({
            alerts: [newAlert, ...state.alerts].slice(0, 50), // Keep last 50
          }));
        },
        
        acknowledgeAlert: (alertId) => {
          set((state) => ({
            alerts: state.alerts.map((alert) =>
              alert.id === alertId ? { ...alert, acknowledged: true } : alert
            ),
          }));
        },
        
        dismissAlert: (alertId) => {
          set((state) => ({
            alerts: state.alerts.filter((alert) => alert.id !== alertId),
          }));
        },
        
        clearAllAlerts: () => {
          set({ alerts: [] });
        },
        
        // === UI ===
        setViewMode: (mode) => {
          set({ viewMode: mode });
        },
        
        focusInstance: (instanceId) => {
          set({ focusedInstance: instanceId, viewMode: 'focus' });
        },
        
        unfocusInstance: () => {
          set({ focusedInstance: null, viewMode: 'grid' });
        },
        
        toggleSidebar: () => {
          set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }));
        },
        
        // === Preferences ===
        setTheme: (theme) => {
          set({ theme });
        },
        
        setCompactMode: (compact) => {
          set({ compactMode: compact });
        },
        
        // === Emergency ===
        killAllTrading: async () => {
          try {
            const response = await fetch('/api/v2/global/kill-all', {
              method: 'POST',
            });
            if (response.ok) {
              set({ tradingMode: 'READ_ONLY' });
              get().addAlert({
                severity: 'critical',
                message: 'EMERGENCY STOP: All trading halted',
                acknowledged: false,
              });
              return true;
            }
            return false;
          } catch (error) {
            get().addAlert({
              severity: 'critical',
              message: `Failed to kill all trading: ${error}`,
              acknowledged: false,
            });
            return false;
          }
        },
      }),
      {
        name: 'gridbot-global-store',
        partialize: (state) => ({
          // Only persist user preferences
          theme: state.theme,
          compactMode: state.compactMode,
          sidebarCollapsed: state.sidebarCollapsed,
        }),
      }
    )
  )
);

// ============================================================================
// SELECTORS
// ============================================================================

export const selectInstances = (state: GlobalStore) => state.instances;
export const selectTradingMode = (state: GlobalStore) => state.tradingMode;
export const selectSystemHealth = (state: GlobalStore) => state.systemHealth;
export const selectActiveAlerts = (state: GlobalStore) => 
  state.alerts.filter((a) => !a.acknowledged);
export const selectFocusedInstance = (state: GlobalStore) => state.focusedInstance;
export const selectViewMode = (state: GlobalStore) => state.viewMode;

// ============================================================================
// COMPUTED SELECTORS
// ============================================================================

export const selectSystemStatus = (state: GlobalStore) => {
  const { backend, database, exchange } = state.systemHealth;
  
  if (backend === 'down' || database === 'down' || exchange === 'down') {
    return 'critical';
  }
  if (backend === 'degraded' || database === 'degraded' || exchange === 'degraded') {
    return 'degraded';
  }
  return 'healthy';
};

export const selectUnacknowledgedAlertCount = (state: GlobalStore) =>
  state.alerts.filter((a) => !a.acknowledged).length;
