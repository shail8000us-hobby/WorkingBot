// WebUI v3 - Component Index
// All 70 components with full v1 parity

// TIER 1: Core Components
export { BotControlPanel } from './bot/BotControlPanel';
export { EmergencyControlsPanel } from './emergency/EmergencyControlsPanel';
export { SymbolSwitcher } from './trading/SymbolSwitcher';
export { GridModeToggle } from './grid/GridModeToggle';
export { OrderManagementPanel } from './orders/OrderManagementPanel';
export { GridConfigCard } from './grid/GridConfigCard';
export { SystemHealthPanel } from './health/SystemHealthPanel';
export { HealthDashboard } from './health/HealthDashboard';
export { NotificationProvider } from './notifications/NotificationProvider';

// TIER 2: Trading & Risk
export { TradeHistoryPanel } from './trades/TradeHistoryPanel';
export { PositionAnalysisPanel } from './positions/PositionAnalysisPanel';
export { RiskLimitsPanel } from './risk/RiskLimitsPanel';
export { RiskMetricsPanel } from './risk/RiskMetricsPanel';
export { OrderBookPanel } from './orderbook/OrderBookPanel';
export { default as PM2Panel } from './process/PM2Panel';

// TIER 3: Performance & Strategy
export { PerformanceMetricsPanel } from './performance/PerformanceMetricsPanel';
export { StrategyComparisonPanel } from './strategy/StrategyComparisonPanel';
export { BacktestPanel } from './backtest/BacktestPanel';
export { RSIPanel } from './rsi/RSIPanel';

// TIER 4: Advanced Features
export { MarketSignalPanel } from './signals/MarketSignalPanel';
export { BotActionsPanel } from './actions/BotActionsPanel';
export { AIAdvisorWidget } from './ai/AIAdvisorWidget';

// TIER 5: System & Management (34)
export { LogViewerPanel } from './logs/LogViewerPanel';
export { ExportDataPanel } from './export/ExportDataPanel';
export { SymbolManagementPanel } from './symbols/SymbolManagementPanel';
export { WebhookPanel } from './webhooks/WebhookPanel';
export { SettingsPanel } from './settings/SettingsPanel';
export { APIKeysPanel } from './api/APIKeysPanel';
export { ErrorLogPanel } from './errors/ErrorLogPanel';
export { AlertHistoryPanel } from './alerts/AlertHistoryPanel';
export { ThemePanel } from './theme/ThemePanel';
export { ChartPanel } from './charts/ChartPanel';
export { DashboardLayoutPanel } from './layout/DashboardLayoutPanel';
export { AnalyticsPanel } from './analytics/AnalyticsPanel';
export { NotificationSettingsPanel } from './notifications/NotificationSettingsPanel';
export { BackupPanel } from './backup/BackupPanel';
export { AuditLogPanel } from './audit/AuditLogPanel';
export { SchedulerPanel } from './scheduler/SchedulerPanel';
export { MarketDataPanel } from './market/MarketDataPanel';
export { SessionHistoryPanel } from './sessions/SessionHistoryPanel';
export { IntegrationPanel } from './integrations/IntegrationPanel';
export { ReconciliationPanel } from './reconciliation/ReconciliationPanel';
export { CompliancePanel } from './compliance/CompliancePanel';
export { DebugPanel } from './debug/DebugPanel';
export { APIMonitorPanel } from './monitor/APIMonitorPanel';
export { CachePanel } from './cache/CachePanel';
export { DatabasePanel } from './database/DatabasePanel';
export { NetworkPanel } from './network/NetworkPanel';
export { ResourcePanel } from './resources/ResourcePanel';
export { PluginPanel } from './plugins/PluginPanel';
export { TemplatePanel } from './templates/TemplatePanel';
export { ScriptPanel } from './scripts/ScriptPanel';
export { HelpPanel } from './help/HelpPanel';

// Common Components
export * from './common';
