/**
 * Trading Store - Real-time Trading State
 * 
 * Manages:
 * - Live price data
 * - Position aggregates
 * - Order book state
 * - Trading alerts
 */

import { create } from 'zustand';
import type { Position, Order } from '@/types';

export interface TradingAlert {
  id: string;
  type: 'info' | 'warning' | 'error' | 'success';
  title: string;
  message: string;
  timestamp: number;
  read: boolean;
  actionUrl?: string;
}

export interface TradingState {
  // Live Price
  currentPrice: number | null;
  priceTimestamp: number | null;
  setCurrentPrice: (price: number) => void;
  
  // Position Summary (derived from API but cached here)
  totalPositions: number;
  totalPnL: number;
  totalPnLINR: number;
  unrealizedPnL: number;
  updatePositionSummary: (positions: Position[]) => void;
  
  // Order Summary
  openOrdersCount: number;
  pendingBuys: number;
  pendingSells: number;
  updateOrderSummary: (orders: Order[]) => void;
  
  // Trading Alerts
  alerts: TradingAlert[];
  addAlert: (alert: Omit<TradingAlert, 'id' | 'timestamp' | 'read'>) => void;
  markAlertRead: (id: string) => void;
  clearAlerts: () => void;
  unreadCount: () => number;
  
  // Emergency State
  emergencyActive: boolean;
  setEmergencyActive: (active: boolean) => void;
  
  // Trading Allowed
  tradingAllowed: boolean;
  tradingBlockers: Array<{ name: string; reason: string }>;
  setTradingStatus: (allowed: boolean, blockers: Array<{ name: string; reason: string }>) => void;
}

export const useTradingStore = create<TradingState>((set, get) => ({
  // Live Price
  currentPrice: null,
  priceTimestamp: null,
  setCurrentPrice: (price) => set({ 
    currentPrice: price, 
    priceTimestamp: Date.now() 
  }),
  
  // Position Summary
  totalPositions: 0,
  totalPnL: 0,
  totalPnLINR: 0,
  unrealizedPnL: 0,
  updatePositionSummary: (positions) => {
    const totalPnL = positions.reduce((sum, p) => sum + (p.profit_loss ?? p.unrealizedPnl ?? 0), 0);
    const totalPnLINR = positions.reduce((sum, p) => sum + (p.profit_loss_inr ?? 0), 0);
    const unrealizedPnL = positions.reduce((sum, p) => {
      if (p.status === 'OPEN' || !p.status) {
        return sum + (p.profit_loss ?? p.unrealizedPnl ?? 0);
      }
      return sum;
    }, 0);
    
    set({
      totalPositions: positions.length,
      totalPnL,
      totalPnLINR,
      unrealizedPnL,
    });
  },
  
  // Order Summary
  openOrdersCount: 0,
  pendingBuys: 0,
  pendingSells: 0,
  updateOrderSummary: (orders) => {
    const openOrders = orders.filter((o) => 
      o.status === 'PENDING' || 
      o.status === 'PARTIALLY_FILLED' || 
      o.status === 'pending' || 
      o.status === 'open'
    );
    const pendingBuys = openOrders.filter((o) => o.side === 'BUY').length;
    const pendingSells = openOrders.filter((o) => o.side === 'SELL').length;
    
    set({
      openOrdersCount: openOrders.length,
      pendingBuys,
      pendingSells,
    });
  },
  
  // Trading Alerts
  alerts: [],
  addAlert: (alert) => {
    const newAlert: TradingAlert = {
      ...alert,
      id: `alert-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
      read: false,
    };
    set((state) => ({
      alerts: [newAlert, ...state.alerts].slice(0, 100), // Keep last 100
    }));
  },
  markAlertRead: (id) => set((state) => ({
    alerts: state.alerts.map((a) => 
      a.id === id ? { ...a, read: true } : a
    ),
  })),
  clearAlerts: () => set({ alerts: [] }),
  unreadCount: () => get().alerts.filter((a) => !a.read).length,
  
  // Emergency State
  emergencyActive: false,
  setEmergencyActive: (active) => set({ emergencyActive: active }),
  
  // Trading Status
  tradingAllowed: true,
  tradingBlockers: [],
  setTradingStatus: (allowed, blockers) => set({ 
    tradingAllowed: allowed, 
    tradingBlockers: blockers 
  }),
}));

export default useTradingStore;
