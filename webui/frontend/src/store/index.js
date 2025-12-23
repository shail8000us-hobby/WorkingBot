/**
 * Zustand Store - Global State Management for WebUI
 * 
 * Replaces custom event store with battle-tested Zustand library.
 * Provides state persistence across page refreshes.
 * 
 * Date: November 12, 2025
 * Part of: WebUI Robustness Plan Week 2
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * Main application store
 * 
 * State includes:
 * - positions: Current trading positions
 * - orders: Active orders
 * - config: Bot configuration
 * - health: System health status
 * - pnl: Profit & Loss data
 * - lastUpdate: Timestamp of last data refresh
 */
export const useStore = create(
  persist(
    (set, get) => ({
      // =============================================
      // State
      // =============================================
      
      // Trading data
      positions: [],
      orders: [],
      pnl: {
        total_pnl_usd: 0,
        total_pnl_inr: 0,
        daily_pnl: 0,
        realized_pnl: 0,
        unrealized_pnl: 0
      },
      
      // System data
      config: {},
      health: { 
        status: 'unknown',
        services: {},
        resources: {},
        circuit_breakers: {}
      },
      
      // Metadata
      lastUpdate: null,
      isLoading: false,
      error: null,
      
      // =============================================
      // Actions
      // =============================================
      
      /**
       * Update positions data
       */
      updatePositions: (positions) => {
        set({ 
          positions: positions || [], 
          lastUpdate: Date.now(),
          error: null
        });
      },
      
      /**
       * Update orders data
       */
      updateOrders: (orders) => {
        set({ 
          orders: orders || [], 
          lastUpdate: Date.now(),
          error: null
        });
      },
      
      /**
       * Update health status
       */
      updateHealth: (health) => {
        set({ 
          health: health || { status: 'unknown' },
          lastUpdate: Date.now()
        });
      },
      
      /**
       * Update bot configuration
       */
      updateConfig: (config) => {
        set({ 
          config: config || {},
          lastUpdate: Date.now(),
          error: null
        });
      },
      
      /**
       * Update PnL data
       */
      updatePnL: (pnl) => {
        set({ 
          pnl: pnl || {
            total_pnl_usd: 0,
            total_pnl_inr: 0,
            daily_pnl: 0,
            realized_pnl: 0,
            unrealized_pnl: 0
          },
          lastUpdate: Date.now(),
          error: null
        });
      },
      
      /**
       * Set loading state
       */
      setLoading: (isLoading) => {
        set({ isLoading });
      },
      
      /**
       * Set error state
       */
      setError: (error) => {
        set({ error: error ? String(error) : null });
      },
      
      /**
       * Clear error
       */
      clearError: () => {
        set({ error: null });
      },
      
      /**
       * Reset all state (for logout/refresh)
       */
      reset: () => {
        set({
          positions: [],
          orders: [],
          config: {},
          health: { status: 'unknown' },
          pnl: {
            total_pnl_usd: 0,
            total_pnl_inr: 0,
            daily_pnl: 0,
            realized_pnl: 0,
            unrealized_pnl: 0
          },
          lastUpdate: null,
          isLoading: false,
          error: null
        });
      },
      
      /**
       * Bulk update (used by data aggregator)
       */
      bulkUpdate: (data) => {
        const updates = { lastUpdate: Date.now() };
        
        if (data.positions !== undefined) {
          updates.positions = data.positions || [];
        }
        if (data.orders !== undefined) {
          updates.orders = data.orders || [];
        }
        if (data.health !== undefined) {
          updates.health = data.health || { status: 'unknown' };
        }
        if (data.pnl !== undefined) {
          updates.pnl = data.pnl || {
            total_pnl_usd: 0,
            total_pnl_inr: 0,
            daily_pnl: 0,
            realized_pnl: 0,
            unrealized_pnl: 0
          };
        }
        if (data.config !== undefined) {
          updates.config = data.config || {};
        }
        
        set(updates);
      }
    }),
    {
      name: 'webui-storage', // localStorage key
      
      // Only persist config and lastUpdate (not dynamic data like health)
      partialize: (state) => ({
        config: state.config,
        lastUpdate: state.lastUpdate
      })
    }
  )
);

// =============================================
// Selector Hooks (prevent unnecessary re-renders)
// =============================================

/**
 * Use positions data
 * Only re-renders when positions change
 */
export const usePositions = () => useStore(state => state.positions);

/**
 * Use orders data
 * Only re-renders when orders change
 */
export const useOrders = () => useStore(state => state.orders);

/**
 * Use health status
 * Only re-renders when health changes
 */
export const useHealth = () => useStore(state => state.health);

/**
 * Use bot configuration
 * Only re-renders when config changes
 */
export const useConfig = () => useStore(state => state.config);

/**
 * Use PnL data
 * Only re-renders when pnl changes
 */
export const usePnL = () => useStore(state => state.pnl);

/**
 * Use loading state
 * Only re-renders when loading changes
 */
export const useLoading = () => useStore(state => state.isLoading);

/**
 * Use error state
 * Only re-renders when error changes
 */
export const useError = () => useStore(state => state.error);

/**
 * Use last update timestamp
 * Only re-renders when lastUpdate changes
 */
export const useLastUpdate = () => useStore(state => state.lastUpdate);

/**
 * Use store actions
 * Returns all action methods (doesn't cause re-renders)
 */
export const useStoreActions = () => useStore(state => ({
  updatePositions: state.updatePositions,
  updateOrders: state.updateOrders,
  updateHealth: state.updateHealth,
  updateConfig: state.updateConfig,
  updatePnL: state.updatePnL,
  setLoading: state.setLoading,
  setError: state.setError,
  clearError: state.clearError,
  reset: state.reset,
  bulkUpdate: state.bulkUpdate
}));

export default useStore;
