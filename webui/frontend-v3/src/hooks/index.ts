/**
 * Hooks - Barrel Export
 */

export { 
  useWebSocket,
  useWebSocketStatus,
  useWebSocketMessage,
  useWebSocketMessages,
  useWebSocketSend,
  type UseWebSocketOptions,
  type UseWebSocketReturn,
} from './useWebSocket';

export { 
  useLivePrice,
  type UseLivePriceOptions,
  type UseLivePriceReturn,
  type LivePriceData,
} from './useLivePrice';

export { 
  useBrainStream,
  type UseBrainStreamOptions,
  type UseBrainStreamReturn,
} from './useBrainStream';

// TanStack Query hooks
export {
  queryKeys,
  useInstances,
  usePositions,
  useOrders,
  usePnLHistory,
  useGuardianStatus,
  useStartGuardian,
  useStopGuardian,
  useBotStatus,
  useStartBot,
  useStopBot,
  useTradingStatus,
  usePauseTrading,
  useResumeTrading,
  useHealth,
  useBrainPrediction,
  useBrainScenarios,
  useEmergencyFlag,
  useEmergencyKillAll,
  useClearEmergencyFlag,
  useRiskAnalytics,
  useConfig,
  useUpdateConfig,
  useVolatility,
  useHealthDetailed,
  useSystemHealth,
} from './useQueries';

// Keyboard shortcuts
export {
  useKeyboardShortcuts,
  formatShortcut,
  type KeyboardShortcut,
  type UseKeyboardShortcutsOptions,
  type UseKeyboardShortcutsReturn,
} from './useKeyboardShortcuts';
