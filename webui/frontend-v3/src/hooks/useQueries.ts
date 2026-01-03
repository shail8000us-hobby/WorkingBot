/**
 * TanStack Query Hooks
 * 
 * Pre-configured query hooks for all API endpoints.
 * Uses TanStack Query v5 for caching and synchronization.
 */

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '@/lib/api';

// ============================================================================
// QUERY KEYS
// ============================================================================

export const queryKeys = {
  // Instances
  instances: ['instances'] as const,
  
  // Positions
  positions: (instance?: string) => ['positions', instance] as const,
  
  // Orders
  orders: (state?: string, instance?: string) => ['orders', state, instance] as const,
  
  // P&L
  pnlHistory: ['pnl-history'] as const,
  
  // Guardian
  guardianStatus: (instance?: string) => ['guardian-status', instance] as const,
  
  // Bot
  botStatus: (instance?: string) => ['bot-status', instance] as const,
  
  // Trading
  tradingStatus: ['trading-status'] as const,
  
  // Health
  health: ['health'] as const,
  
  // Brain
  brainPrediction: ['brain-prediction'] as const,
  brainScenarios: ['brain-scenarios'] as const,
  
  // Risk
  riskAnalytics: ['risk-analytics'] as const,
  
  // Config
  config: ['config'] as const,
  
  // Emergency
  emergencyFlag: ['emergency-flag'] as const,
  
  // Trading Mode
  tradingMode: ['trading-mode'] as const,
  
  // Symbols
  symbols: ['symbols'] as const,
  
  // Volatility
  volatility: ['volatility'] as const,
  
  // System Health
  systemHealth: ['system-health'] as const,
} as const;

// ============================================================================
// INSTANCES QUERIES
// ============================================================================

export function useInstances() {
  return useQuery({
    queryKey: queryKeys.instances,
    queryFn: async () => {
      const response = await api.getInstances();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 30000, // 30 seconds
  });
}

// ============================================================================
// POSITIONS QUERIES
// ============================================================================

export function usePositions(instance?: string) {
  return useQuery({
    queryKey: queryKeys.positions(instance),
    queryFn: async () => {
      const response = await api.getPositions(instance);
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    refetchInterval: 5000, // Real-time feel
  });
}

// ============================================================================
// ORDERS QUERIES
// ============================================================================

export function useOrders(
  state: 'all' | 'open' | 'filled' | 'cancelled' = 'all',
  instance?: string
) {
  return useQuery({
    queryKey: queryKeys.orders(state, instance),
    queryFn: async () => {
      const response = await api.getOrders(state, instance);
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    refetchInterval: 5000,
  });
}

// ============================================================================
// P&L QUERIES
// ============================================================================

export function usePnLHistory() {
  return useQuery({
    queryKey: queryKeys.pnlHistory,
    queryFn: async () => {
      const response = await api.getPnLHistory();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    refetchInterval: 10000, // 10 seconds
  });
}

// ============================================================================
// GUARDIAN QUERIES & MUTATIONS
// ============================================================================

export function useGuardianStatus(instance?: string) {
  return useQuery({
    queryKey: queryKeys.guardianStatus(instance),
    queryFn: async () => {
      try {
        const response = await api.getGuardianStatus(instance);
        if (!response.success) {
          // Return a default offline status instead of throwing
          return { running: false, active: false } as import('@/types').GuardianStatusResponse;
        }
        return response.data!;
      } catch (error) {
        // Return offline status on error instead of throwing
        return { running: false, active: false } as import('@/types').GuardianStatusResponse;
      }
    },
    retry: false, // Don't retry - backend has known 500 error
    refetchInterval: 10000, // Slower updates to reduce errors (10s)
    refetchIntervalInBackground: false, // Don't refetch in background
    refetchOnWindowFocus: false, // Don't refetch on window focus
  });
}

export function useStartGuardian() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async () => {
      const response = await api.startGuardian();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['guardian-status'] });
    },
  });
}

export function useStopGuardian() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async () => {
      const response = await api.stopGuardian();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['guardian-status'] });
    },
  });
}

// ============================================================================
// BOT CONTROL QUERIES & MUTATIONS
// ============================================================================

export function useBotStatus(instance?: string) {
  return useQuery({
    queryKey: queryKeys.botStatus(instance),
    queryFn: async () => {
      try {
        const response = await api.getBotStatus(instance);
        if (!response.success) {
          return { running: false, status: 'offline' };
        }
        return response.data!;
      } catch (error) {
        return { running: false, status: 'offline' };
      }
    },
    retry: false,
    refetchInterval: 5000,
    refetchOnWindowFocus: false,
  });
}

export function useStartBot() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async () => {
      const response = await api.startBot();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
      queryClient.invalidateQueries({ queryKey: ['trading-status'] });
    },
  });
}

export function useStopBot() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async () => {
      const response = await api.stopBot();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
      queryClient.invalidateQueries({ queryKey: ['trading-status'] });
    },
  });
}

// ============================================================================
// TRADING STATUS
// ============================================================================

export function useTradingStatus(instanceId?: string) {
  return useQuery({
    queryKey: [...queryKeys.tradingStatus, instanceId],
    queryFn: async () => {
      try {
        const response = await api.getTradingStatus();
        if (!response.success) {
          return { 
            bot_running: false,
            trading_allowed: false, 
            blockers: [],
            total_blockers: 0,
            positions: [],
            pending_orders: 0,
            upnl_inr: 0,
            rpnl_inr: 0,
            net_pnl_inr: 0,
          } as import('@/lib/api').TradingStatusResponse;
        }
        return response.data!;
      } catch (error) {
        return { 
          bot_running: false,
          trading_allowed: false, 
          blockers: [],
          total_blockers: 0,
          positions: [],
          pending_orders: 0,
          upnl_inr: 0,
          rpnl_inr: 0,
          net_pnl_inr: 0,
        } as import('@/lib/api').TradingStatusResponse;
      }
    },
    retry: false,
    refetchInterval: 5000,
    refetchOnWindowFocus: false,
  });
}

export function usePauseTrading() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ instanceId }: { instanceId?: string }) => {
      const response = await api.pauseTrading(instanceId);
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trading-status'] });
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

export function useResumeTrading() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ instanceId }: { instanceId?: string }) => {
      const response = await api.resumeTrading(instanceId);
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trading-status'] });
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
    },
  });
}

// ============================================================================
// HEALTH
// ============================================================================

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: async () => {
      const response = await api.getHealth();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    refetchInterval: 10000,
  });
}

// ============================================================================
// BRAIN QUERIES
// ============================================================================

export function useBrainPrediction() {
  return useQuery({
    queryKey: queryKeys.brainPrediction,
    queryFn: async () => {
      const response = await api.getBrainPrediction();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 60000, // 1 minute - predictions don't change that fast
  });
}

export function useBrainScenarios() {
  return useQuery({
    queryKey: queryKeys.brainScenarios,
    queryFn: async () => {
      const response = await api.getBrainScenarios();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 60000,
  });
}

// ============================================================================
// EMERGENCY
// ============================================================================

export function useEmergencyFlag() {
  return useQuery({
    queryKey: queryKeys.emergencyFlag,
    queryFn: async () => {
      const response = await api.checkEmergencyFlag();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    refetchInterval: 5000,
  });
}

export function useEmergencyKillAll() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ instanceId }: { instanceId?: string }) => {
      const response = await api.emergencyKillAll(instanceId);
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      // Invalidate all relevant queries
      queryClient.invalidateQueries({ queryKey: ['bot-status'] });
      queryClient.invalidateQueries({ queryKey: ['guardian-status'] });
      queryClient.invalidateQueries({ queryKey: ['trading-status'] });
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  });
}

export function useClearEmergencyFlag() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async () => {
      const response = await api.clearEmergencyFlag();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emergency-flag'] });
    },
  });
}

// ============================================================================
// RISK
// ============================================================================

export function useRiskAnalytics() {
  return useQuery({
    queryKey: queryKeys.riskAnalytics,
    queryFn: async () => {
      const response = await api.getRiskAnalytics();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 30000,
  });
}

// ============================================================================
// CONFIG
// ============================================================================

export function useConfig() {
  return useQuery({
    queryKey: queryKeys.config,
    queryFn: async () => {
      const response = await api.getConfig();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 60000, // Config doesn't change often
  });
}

export function useUpdateConfig() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (config: Record<string, unknown>) => {
      const response = await api.updateConfig(config);
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
    },
  });
}

// ============================================================================
// TRADING MODE QUERIES
// ============================================================================

export function useTradingMode() {
  return useQuery({
    queryKey: queryKeys.tradingMode,
    queryFn: async () => {
      const response = await api.getTradingMode();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 10000,
  });
}

export function useUpdateTradingMode() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ mode }: { mode: string }) => {
      const response = await api.setTradingMode(mode);
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tradingMode });
    },
  });
}

// ============================================================================
// SYMBOLS QUERIES
// ============================================================================

export function useSymbols() {
  return useQuery({
    queryKey: queryKeys.symbols,
    queryFn: async () => {
      const response = await api.getSymbols();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 60000, // Symbols don't change often
  });
}

// ============================================================================
// VOLATILITY QUERIES
// ============================================================================

export function useVolatility() {
  return useQuery({
    queryKey: queryKeys.volatility,
    queryFn: async () => {
      const response = await api.getVolatilitySignal();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    refetchInterval: 30000, // Update every 30s
  });
}

// ============================================================================
// SYSTEM HEALTH QUERIES
// ============================================================================

export function useHealthDetailed() {
  return useQuery({
    queryKey: ['health-detailed'],
    queryFn: async () => {
      const response = await api.getHealthDetailed();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    refetchInterval: 10000, // Update every 10s
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: queryKeys.systemHealth,
    queryFn: async () => {
      const response = await api.getSystemHealth();
      if (!response.success) throw new Error(response.error);
      return response.data!;
    },
    refetchInterval: 10000, // Update every 10s
  });
}
