/**
 * Automation Module - Main entry point
 *
 * Export all automation components and utilities
 */

// Components
export { default as AutomationButton } from './components/AutomationButton';
export { default as AutomationDialog } from './components/AutomationDialog';
export { default as AutomationStatus } from './components/AutomationStatus';
export { default as ConditionChecks } from './components/ConditionChecks';
export { default as EntryConditionsTab } from './components/EntryConditionsTab';
export { default as ExecutionTab } from './components/ExecutionTab';
export { default as ExitConditionsTab } from './components/ExitConditionsTab';
export { default as RiskControlsTab } from './components/RiskControlsTab';

// Hooks
export { useAutomation } from './hooks/useAutomation';

// Core
export { default as conditionEvaluator } from './core/ConditionEvaluator';
export { default as orderExecutor } from './core/OrderExecutor';
export { default as riskValidator } from './core/RiskValidator';

// API
export { default as deltaExchangeAPI } from './api/DeltaExchangeAPI';

// Monitoring
export { default as automationMonitor } from './monitoring/AutomationMonitor';
export { default as notificationService } from './monitoring/NotificationService';

// Storage
export { default as automationStorage } from './storage/AutomationStorage';

// Types
export * from './types/constants';
